"""Webhook CLI commands."""

import argparse
import logging
import os
import signal
import sys
import time
import urllib.parse

from strava_sensor.mqtt.mqtt import MQTTClient
from strava_sensor.sources import initialize_sources
from strava_sensor.webhook.processor import ActivityProcessor
from strava_sensor.webhook.server import WebhookServer
from strava_sensor.webhook.subscription import WebhookSubscriptionManager

_logger = logging.getLogger(__name__)


def add_webhook_server_command(subparsers: argparse._SubParsersAction) -> None:
    """Add webhook server command to the argument parser.
    
    Args:
        subparsers: The subparsers object to add commands to
    """
    # Webhook server command
    server_parser = subparsers.add_parser(
        'webhook-server',
        help='Start webhook server to receive Strava events'
    )
    server_parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port to listen on (default: 8080)'
    )
    server_parser.add_argument(
        '--publish',
        action='store_true',
        help='Publish device data to MQTT when processing activities'
    )
    server_parser.add_argument(
        '--callback-url',
        help='Public URL where Strava will send webhook events (required for auto-subscription). '
             'Should include protocol and path, e.g., https://your-server.com/webhook'
    )
    server_parser.add_argument(
        '--no-auto-subscribe',
        action='store_true',
        help='Disable automatic webhook subscription management'
    )
    server_parser.add_argument(
        '--cleanup-on-exit',
        action='store_true',
        help='Remove webhook subscription when server shuts down'
    )
    server_parser.set_defaults(func=cmd_webhook_server)


def cmd_webhook_server(args: argparse.Namespace) -> None:
    """Start the webhook server."""
    # Get required environment variables
    verify_token = os.environ.get('STRAVA_WEBHOOK_VERIFY_TOKEN')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    client_id = os.environ.get('STRAVA_CLIENT_ID')
    
    if not verify_token:
        _logger.error('STRAVA_WEBHOOK_VERIFY_TOKEN environment variable is required')
        sys.exit(1)
    
    if not client_secret:
        _logger.error('STRAVA_CLIENT_SECRET environment variable is required')
        sys.exit(1)
    
    # Auto-subscription management requires callback URL and client credentials
    auto_subscribe = not args.no_auto_subscribe
    if auto_subscribe:
        if not args.callback_url:
            _logger.error('--callback-url is required for automatic subscription management. '
                         'Use --no-auto-subscribe to disable auto-management.')
            sys.exit(1)
        
        if not client_id:
            _logger.error('STRAVA_CLIENT_ID environment variable is required for auto-subscription')
            sys.exit(1)
    
    # Initialize MQTT client if publishing is enabled
    mqtt_client: MQTTClient | None = None
    if args.publish:
        mqtt_broker_url = os.environ.get('MQTT_BROKER_URL')
        mqtt_username = os.environ.get('MQTT_USERNAME')
        mqtt_password = os.environ.get('MQTT_PASSWORD')
        
        if not all([mqtt_broker_url, mqtt_username, mqtt_password]):
            _logger.error(
                'MQTT_BROKER_URL, MQTT_USERNAME, and MQTT_PASSWORD '
                'environment variables are required when using --publish'
            )
            sys.exit(1)
        
        mqtt_client = MQTTClient()
        mqtt_client.connect(mqtt_broker_url, mqtt_username, mqtt_password)
        
        # Wait for MQTT connection
        _logger.info('Waiting for MQTT connection...')
        while not mqtt_client.connected:
            time.sleep(0.1)
        _logger.info('MQTT connected')
    
    # Initialize sources and activity processor
    sources = initialize_sources()
    processor = ActivityProcessor(sources, mqtt_client)
    
    # Auto-manage webhook subscription
    subscription_manager = None
    current_subscription_id = None
    
    if auto_subscribe:
        subscription_manager = WebhookSubscriptionManager(client_id, client_secret)
        current_subscription_id = _setup_webhook_subscription(
            subscription_manager, args.callback_url, verify_token
        )
    
    # Create and start webhook server
    server = WebhookServer(
        port=args.port,
        verify_token=verify_token,
        client_secret=client_secret,
        event_callback=processor.process_webhook_event
    )
    
    try:
        server.start()
        _logger.info('Webhook server running on port %d. Press Ctrl+C to stop.', args.port)
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            _logger.info('Received signal %d, shutting down...', signum)
            _cleanup_and_exit(server, mqtt_client, subscription_manager, 
                            current_subscription_id, args.cleanup_on_exit)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        _logger.info('Keyboard interrupt received, shutting down...')
    finally:
        _cleanup_and_exit(server, mqtt_client, subscription_manager, 
                        current_subscription_id, args.cleanup_on_exit)


def _setup_webhook_subscription(manager: WebhookSubscriptionManager, callback_url: str, verify_token: str) -> int | None:
    """Set up webhook subscription, handling existing subscriptions.
    
    Args:
        manager: Subscription manager instance
        callback_url: URL for webhook callbacks
        verify_token: Verification token
        
    Returns:
        Subscription ID if successful, None otherwise
    """
    try:
        # Check for existing subscriptions
        existing_subscriptions = manager.list_subscriptions()
        
        if existing_subscriptions:
            _logger.info('Found %d existing subscription(s)', len(existing_subscriptions))
            
            # Check if any subscription matches our callback URL
            matching_subscription = None
            for sub in existing_subscriptions:
                # Parse and compare URLs to handle minor differences
                existing_parsed = urllib.parse.urlparse(sub.callback_url)
                new_parsed = urllib.parse.urlparse(callback_url)
                
                if (existing_parsed.netloc == new_parsed.netloc and 
                    existing_parsed.path == new_parsed.path):
                    matching_subscription = sub
                    break
            
            if matching_subscription:
                _logger.info('Found existing subscription (ID: %d) matching callback URL: %s', 
                           matching_subscription.id, matching_subscription.callback_url)
                return matching_subscription.id
            # Different callback URL - delete existing and create new
            _logger.info('Existing subscription(s) have different callback URLs. Cleaning up...')
            for sub in existing_subscriptions:
                _logger.info('Deleting subscription ID %d (callback: %s)', sub.id, sub.callback_url)
                manager.delete_subscription(sub.id)
        
        # Create new subscription
        _logger.info('Creating new webhook subscription for: %s', callback_url)
        subscription = manager.create_subscription(callback_url, verify_token)
        _logger.info('Successfully created subscription with ID: %d', subscription.id)
        return subscription.id
        
    except Exception as e:
        _logger.error('Failed to setup webhook subscription: %s', e)
        _logger.info('Server will continue without automatic subscription management')
        return None


def _cleanup_and_exit(server: WebhookServer, mqtt_client: MQTTClient | None, 
                     subscription_manager: WebhookSubscriptionManager | None,
                     subscription_id: int | None, cleanup_on_exit: bool) -> None:
    """Clean up resources and exit.
    
    Args:
        server: Webhook server instance
        mqtt_client: MQTT client instance (optional)
        subscription_manager: Subscription manager (optional)
        subscription_id: ID of subscription to clean up (optional)
        cleanup_on_exit: Whether to remove subscription on exit
    """
    # Stop server
    server.stop()
    
    # Disconnect MQTT
    if mqtt_client:
        mqtt_client.disconnect()
    
    # Clean up subscription if requested
    if cleanup_on_exit and subscription_manager and subscription_id:
        try:
            _logger.info('Removing webhook subscription (ID: %d)...', subscription_id)
            subscription_manager.delete_subscription(subscription_id)
            _logger.info('Webhook subscription removed')
        except Exception as e:
            _logger.warning('Failed to remove webhook subscription: %s', e)
    
    sys.exit(0)

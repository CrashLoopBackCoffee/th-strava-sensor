"""Webhook CLI commands."""

import argparse
import logging
import os
import signal
import sys
import time

from strava_sensor.sources import initialize_sources
from strava_sensor.mqtt.mqtt import MQTTClient
from strava_sensor.webhook.processor import ActivityProcessor
from strava_sensor.webhook.server import WebhookServer
from strava_sensor.webhook.subscription import WebhookSubscriptionManager

_logger = logging.getLogger(__name__)


def add_webhook_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Add webhook-related subcommands to the argument parser.
    
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
    server_parser.set_defaults(func=cmd_webhook_server)
    
    # Subscription management commands
    sub_parser = subparsers.add_parser(
        'webhook-subscription',
        help='Manage Strava webhook subscriptions'
    )
    sub_subparsers = sub_parser.add_subparsers(dest='subscription_action', required=True)
    
    # Create subscription
    create_parser = sub_subparsers.add_parser('create', help='Create a new webhook subscription')
    create_parser.add_argument(
        'callback_url',
        help='URL where Strava will send webhook events'
    )
    create_parser.add_argument(
        '--verify-token',
        help='Verification token (defaults to STRAVA_WEBHOOK_VERIFY_TOKEN env var)'
    )
    create_parser.set_defaults(func=cmd_create_subscription)
    
    # List subscriptions
    list_parser = sub_subparsers.add_parser('list', help='List existing webhook subscriptions')
    list_parser.set_defaults(func=cmd_list_subscriptions)
    
    # Delete subscription
    delete_parser = sub_subparsers.add_parser('delete', help='Delete a webhook subscription')
    delete_parser.add_argument('subscription_id', type=int, help='Subscription ID to delete')
    delete_parser.set_defaults(func=cmd_delete_subscription)
    
    # Delete all subscriptions
    delete_all_parser = sub_subparsers.add_parser('delete-all', help='Delete all webhook subscriptions')
    delete_all_parser.set_defaults(func=cmd_delete_all_subscriptions)


def cmd_webhook_server(args: argparse.Namespace) -> None:
    """Start the webhook server."""
    # Get required environment variables
    verify_token = os.environ.get('STRAVA_WEBHOOK_VERIFY_TOKEN')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    
    if not verify_token:
        _logger.error('STRAVA_WEBHOOK_VERIFY_TOKEN environment variable is required')
        sys.exit(1)
    
    if not client_secret:
        _logger.error('STRAVA_CLIENT_SECRET environment variable is required')
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
            server.stop()
            if mqtt_client:
                mqtt_client.disconnect()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        _logger.info('Keyboard interrupt received, shutting down...')
    finally:
        server.stop()
        if mqtt_client:
            mqtt_client.disconnect()


def cmd_create_subscription(args: argparse.Namespace) -> None:
    """Create a webhook subscription."""
    client_id = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    verify_token = args.verify_token or os.environ.get('STRAVA_WEBHOOK_VERIFY_TOKEN')
    
    if not client_id:
        _logger.error('STRAVA_CLIENT_ID environment variable is required')
        sys.exit(1)
    
    if not client_secret:
        _logger.error('STRAVA_CLIENT_SECRET environment variable is required')
        sys.exit(1)
    
    if not verify_token:
        _logger.error('Verification token is required (--verify-token or STRAVA_WEBHOOK_VERIFY_TOKEN)')
        sys.exit(1)
    
    manager = WebhookSubscriptionManager(client_id, client_secret)
    
    try:
        subscription = manager.create_subscription(args.callback_url, verify_token)
        print(f'Created subscription with ID: {subscription.id}')
        print(f'Callback URL: {subscription.callback_url}')
        print(f'Created at: {subscription.created_at}')
    except Exception as e:
        _logger.error('Failed to create subscription: %s', e)
        sys.exit(1)


def cmd_list_subscriptions(args: argparse.Namespace) -> None:
    """List webhook subscriptions."""
    client_id = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    
    if not client_id:
        _logger.error('STRAVA_CLIENT_ID environment variable is required')
        sys.exit(1)
    
    if not client_secret:
        _logger.error('STRAVA_CLIENT_SECRET environment variable is required')
        sys.exit(1)
    
    manager = WebhookSubscriptionManager(client_id, client_secret)
    
    try:
        subscriptions = manager.list_subscriptions()
        
        if not subscriptions:
            print('No webhook subscriptions found.')
            return
        
        print(f'Found {len(subscriptions)} subscription(s):')
        for sub in subscriptions:
            print(f'  ID: {sub.id}')
            print(f'  Callback URL: {sub.callback_url}')
            print(f'  Created: {sub.created_at}')
            print(f'  Updated: {sub.updated_at}')
            print()
    except Exception as e:
        _logger.error('Failed to list subscriptions: %s', e)
        sys.exit(1)


def cmd_delete_subscription(args: argparse.Namespace) -> None:
    """Delete a webhook subscription."""
    client_id = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    
    if not client_id:
        _logger.error('STRAVA_CLIENT_ID environment variable is required')
        sys.exit(1)
    
    if not client_secret:
        _logger.error('STRAVA_CLIENT_SECRET environment variable is required')
        sys.exit(1)
    
    manager = WebhookSubscriptionManager(client_id, client_secret)
    
    try:
        manager.delete_subscription(args.subscription_id)
        print(f'Deleted subscription {args.subscription_id}')
    except Exception as e:
        _logger.error('Failed to delete subscription: %s', e)
        sys.exit(1)


def cmd_delete_all_subscriptions(args: argparse.Namespace) -> None:
    """Delete all webhook subscriptions."""
    client_id = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
    
    if not client_id:
        _logger.error('STRAVA_CLIENT_ID environment variable is required')
        sys.exit(1)
    
    if not client_secret:
        _logger.error('STRAVA_CLIENT_SECRET environment variable is required')
        sys.exit(1)
    
    manager = WebhookSubscriptionManager(client_id, client_secret)
    
    try:
        subscriptions = manager.list_subscriptions()
        if not subscriptions:
            print('No subscriptions to delete.')
            return
        
        manager.delete_all_subscriptions()
        print(f'Deleted {len(subscriptions)} subscription(s)')
    except Exception as e:
        _logger.error('Failed to delete subscriptions: %s', e)
        sys.exit(1)
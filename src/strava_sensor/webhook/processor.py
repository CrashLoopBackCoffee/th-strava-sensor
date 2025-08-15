"""Webhook event processing and activity handling."""

import logging

from strava_sensor.fitfile.fitfile import CorruptedFitFileError, FitFile, NotAFitFileError
from strava_sensor.mqtt.mqtt import MQTTClient
from strava_sensor.source.base import BaseSource
from strava_sensor.webhook.server import WebhookEvent

_logger = logging.getLogger(__name__)


class ActivityProcessor:
    """Processes activities triggered by webhook events."""
    
    def __init__(self, sources: list[BaseSource], mqtt_client: MQTTClient | None = None):
        self.sources = sources
        self.mqtt_client = mqtt_client
    
    def process_webhook_event(self, event: WebhookEvent) -> None:
        """Process a webhook event and extract device data if it's an activity.
        
        Args:
            event: The webhook event from Strava
        """
        _logger.info('Processing webhook event: %s', event.model_dump())
        
        # Only process activity creation events
        if event.object_type != 'activity':
            _logger.debug('Ignoring non-activity event: %s', event.object_type)
            return
        
        if event.aspect_type != 'create':
            _logger.debug('Ignoring non-create event: %s', event.aspect_type)
            return
        
        # Process the activity
        try:
            self._process_activity(event.object_id)
        except Exception as e:
            _logger.error('Error processing activity %d: %s', event.object_id, e)
    
    def _process_activity(self, activity_id: int) -> None:
        """Process a single activity by ID.
        
        Args:
            activity_id: Strava activity ID
        """
        activity_uri = f'strava://{activity_id}'
        _logger.info('Processing activity %s', activity_uri)
        
        # Find appropriate source for the activity
        source = self._get_source_for_uri(activity_uri)
        if source is None:
            _logger.warning('No source found for activity %s', activity_uri)
            return
        
        try:
            # Read activity data
            _logger.debug('Reading activity data from %s', source.__class__.__name__)
            activity_data = source.read_activity(activity_uri)
            
            # Parse FIT file
            _logger.debug('Parsing FIT file for activity %d', activity_id)
            fitfile = FitFile(activity_data)
            
            _logger.info('Activity %d: Serial number: %s', activity_id, fitfile.activity_id)
            _logger.info('Activity %d: Start time: %s', activity_id, fitfile.start_time)
            
            # Extract and process device status
            devices_status = fitfile.get_devices_status()
            _logger.info('Found %d devices in activity %d', len(devices_status), activity_id)
            
            for device_status in devices_status:
                _logger.info('Device: %s (%s)', device_status.product, device_status.device_type)
                _logger.info('  Serial: %s', device_status.serial_number)
                _logger.info('  Battery: %s V, %s', device_status.battery_voltage, device_status.battery_status)
                
                # Publish to MQTT if configured
                if self.mqtt_client:
                    device_status.publish_on_mqtt(self.mqtt_client)
            
            _logger.info('Successfully processed activity %d', activity_id)
            
        except (NotAFitFileError, CorruptedFitFileError) as e:
            _logger.error('Error parsing FIT file for activity %d: %s', activity_id, e)
        except Exception as e:
            _logger.error('Unexpected error processing activity %d: %s', activity_id, e)
    
    def _get_source_for_uri(self, uri: str) -> BaseSource | None:
        """Get the appropriate source for a URI.
        
        Args:
            uri: The activity URI
            
        Returns:
            The appropriate source or None if not found
        """
        for source in self.sources:
            if source.matches_uri(uri):
                return source
        return None
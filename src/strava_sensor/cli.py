import collections.abc as c
import logging
import os
import time

import daiquiri

from strava_sensor.fitfile.fitfile import CorruptedFitFileError, FitFile, NotAFitFileError
from strava_sensor.mqtt.mqtt import MQTTClient
from strava_sensor.source.base import BaseSource
from strava_sensor.source.file import FileSource
from strava_sensor.source.garmin import GarminSource

_logger = logging.getLogger(__name__)


def setup_logging():
    daiquiri.setup(level=logging.DEBUG)
    daiquiri.set_default_log_levels([('paho', 'INFO')])


def initialize_sources() -> list[BaseSource]:
    """Initialize the sources for reading activities."""
    sources = []

    # Add file source
    sources.append(FileSource())

    # Add Garmin source
    garmin_username = os.environ.get('GARMIN_USERNAME')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    if garmin_username and garmin_password:
        sources.append(GarminSource(garmin_username, garmin_password))

    return sources


def get_source_for_uri(uri: str, sources: c.Iterable[BaseSource]) -> BaseSource | None:
    """Get the source for the given URI."""
    for source in sources:
        if source.matches_uri(uri):
            return source
    return None


def main() -> None:
    setup_logging()
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Parse a FIT file for debugging')
    parser.add_argument(
        '--publish',
        action='store_true',
        help='Publish to MQTT. Needs MQTT_BROKER_URL, MQTT_USERNAME and MQTT_PASSWORD set.',
    )
    parser.add_argument(
        'source',
        type=str,
        help='Source URI FIT file. Can be a file (file://path/to/file) '
        'or a Garmin activity ID (garmin://<activity-id>) '
        'or a link to the activity on Garmin Connect (https://connect.garmin.com/modern/activity/<activity-id>)',
    )
    args = parser.parse_args()

    mqtt_client: MQTTClient | None = None
    if args.publish:
        mqtt_broker_url = os.environ['MQTT_BROKER_URL']
        mqtt_username = os.environ['MQTT_USERNAME']
        mqtt_password = os.environ['MQTT_PASSWORD']
        mqtt_client = MQTTClient()
        mqtt_client.connect(mqtt_broker_url, mqtt_username, mqtt_password)
        while not mqtt_client.connected:
            _logger.debug('Waiting for MQTT connection')
            time.sleep(0.1)

    _logger.info('Initializing sources')
    sources = initialize_sources()

    try:
        _logger.debug('Finding source for %s', args.source)
        source = get_source_for_uri(args.source, sources)
        if source is None:
            raise ValueError(f'No source found for URI {args.source}')

        _logger.info('Reading activity from %s', args.source)
        activity_data = source.read_activity(args.source)

        _logger.info('Parsing %s', args.source)
        fitfile = FitFile(activity_data)
        _logger.info('Serial number: %s', fitfile.activity_id)
        _logger.info('Start time: %s', fitfile.start_time)

        devices_status = fitfile.get_devices_status()
        for device_status in devices_status:
            _logger.info('Device index: %s', device_status.device_index)
            _logger.info('Device type: %s', device_status.device_type)
            _logger.info('Serial number: %s', device_status.serial_number)
            _logger.info('Product: %s', device_status.product)
            _logger.info('Battery voltage: %s', device_status.battery_voltage)
            _logger.info('Battery status: %s', device_status.battery_status)
            _logger.info('Battery level: %s', device_status.battery_level)
            _logger.info('Manufacturer: %s', device_status.manufacturer)
            _logger.info('Source type: %s', device_status.source_type)
            _logger.info('Software version: %s', device_status.software_version)
            _logger.info('Hardware version: %s', device_status.hardware_version)
            _logger.info('---')

            if mqtt_client:
                device_status.publish_on_mqtt(mqtt_client)

        # If we are publishing to MQTT stay alive until interrupted
        if mqtt_client:
            try:
                time.sleep(3600)
            except KeyboardInterrupt:
                _logger.info('Keyboard interrupt, exiting')
            mqtt_client.disconnect()

    except (NotAFitFileError, CorruptedFitFileError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

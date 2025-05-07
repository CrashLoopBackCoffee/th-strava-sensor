import logging
import os
import pathlib
import time

import daiquiri

from strava_sensor.fitfile.fitfile import CorruptedFitFileError, FitFile, NotAFitFileError
from strava_sensor.mqtt.mqtt import MQTTClient

_logger = logging.getLogger(__name__)


def setup_logging():
    daiquiri.setup(level=logging.DEBUG)
    daiquiri.set_default_log_levels([('paho', 'INFO')])


def fitfile_main() -> None:
    setup_logging()
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Parse a FIT file for debugging')
    parser.add_argument(
        '--publish',
        action='store_true',
        help='Publish to MQTT. Needs MQTT_BROKER_URL, MQTT_USERNAME and MQTT_PASSWORD set.',
    )
    parser.add_argument('path', type=pathlib.Path, help='Path to the FIT file')
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

    try:
        _logger.info('Parsing %s', args.path)
        fitfile = FitFile.from_file(args.path)
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

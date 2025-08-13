import enum
import json
import logging
import typing as t

import pydantic

from strava_sensor.mqtt.mqtt import MQTTClient

_logger = logging.getLogger(__name__)

# Home Assistant discovery payload constants
STRAVA_TOOL_VERSION = '0.0.1'

MODEL_OVERRIDE = {
    'favero_electronics': {
        '22': 'assioma pro mx-2 spd',
    },
    'garmin': {
        '3592': 'varia rtl516',
    },
}


class BatteryStatus(enum.StrEnum):
    NEW = 'new'
    GOOD = 'good'
    OK = 'ok'
    LOW = 'low'
    CRITICAL = 'critical'
    CHARGING = 'charging'
    UNKNOWN = 'unknown'


class DeviceStatus(pydantic.BaseModel):
    model_config = {
        'extra': 'allow',
        'coerce_numbers_to_str': True,
    }

    device_index: int
    device_type: str
    serial_number: str
    product: str
    battery_voltage: float | None = None
    battery_status: BatteryStatus
    battery_level: int | None = None
    manufacturer: str
    source_type: str
    software_version: str | None = None
    hardware_version: str | None = None

    @pydantic.model_validator(mode='after')
    def override_model(self):
        product_key = f'{self.manufacturer}_product'
        # Override product with manufacturer specific model
        assert self.model_extra
        self.product = str(self.model_extra.get(product_key, self.product))

        # Override unknown product with our own mapping
        manufacturer_mapping = MODEL_OVERRIDE.get(self.manufacturer, {})
        self.product = manufacturer_mapping.get(self.product, self.product)
        return self

    @pydantic.model_validator(mode='after')
    def override_device_type(self):
        device_type_key = f'{self.source_type}_device_type'

        # Override device type with manufacturer specific model
        assert self.model_extra
        self.device_type = str(self.model_extra.get(device_type_key, self.device_type))
        return self

    def publish_on_mqtt(self, mqtt_client: MQTTClient):
        # Publish device status
        mqtt_path = f'strava/{self.serial_number}/status'
        mqtt_client.publish(mqtt_path, self.model_dump_json())

        # Publish home assistant discovery information
        device_id = f'strava-{self.serial_number}'
        payload: dict[str, t.Any] = {
            'dev': {
                'ids': device_id,
                'name': f'Strava {self.device_type} {self.serial_number}',
                'mf': self.manufacturer,
                'mdl': f'{self.product}',
                'sn': self.serial_number,
                'sw': self.software_version,
            },
            'o': {
                'name': 'Strava-Tool',
                'sw': STRAVA_TOOL_VERSION,
            },
            'cmps': {
                f'{device_id}_voltage': {
                    'p': 'sensor',
                    'device_class': 'voltage',
                    'unit_of_measurement': 'V',
                    'value_template': '{{ value_json.battery_voltage }}',
                    'unique_id': f'{device_id}_voltage',
                },
                f'{device_id}_battery_status': {
                    'p': 'sensor',
                    'device_class': 'enum',
                    'value_template': '{{ value_json.battery_status }}',
                    'unique_id': f'{device_id}_battery_status',
                    'icon': 'mdi:battery',
                    'name': 'Battery Status',
                },
            },
            'state_topic': mqtt_path,
        }

        if self.battery_level:
            payload['cmps'][f'{device_id}_battery_level'] = {
                'p': 'sensor',
                'device_class': 'battery',
                'unit_of_measurement': '%',
                'value_template': '{{ value_json.battery_level }}',
                'unique_id': f'{device_id}_battery_level',
            }

        # Add hardware version if available
        if self.hardware_version:
            payload['dev']['hw'] = self.hardware_version

        discovery_topic = f'homeassistant/device/strava-{self.serial_number}/config'
        _logger.debug('Publishing discovery topic: %s', discovery_topic)
        mqtt_client.publish(discovery_topic, json.dumps(payload))

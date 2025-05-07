import enum

import pydantic

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

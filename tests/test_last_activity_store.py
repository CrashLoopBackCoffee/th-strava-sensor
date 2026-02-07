import json

from strava_sensor.fitfile.model import BatteryStatus, DeviceStatus
from strava_sensor.last_activity_store import LastActivityStore


def _build_device_status(serial_number: str) -> DeviceStatus:
    return DeviceStatus(
        device_index=0,
        device_type='radar',
        serial_number=serial_number,
        product='rtl516',
        battery_voltage=3.8,
        battery_status=BatteryStatus.GOOD,
        battery_level=80,
        manufacturer='garmin',
        source_type='fit',
        software_version='1.0',
        hardware_version='1',
        extra_field='present',
    )


def test_last_activity_store_roundtrip(tmp_path):
    store = LastActivityStore(tmp_path / 'last-activity.json')
    device = _build_device_status('1234')

    store.save(activity_id=321, devices=[device])
    loaded = store.load()

    assert loaded is not None
    assert loaded.activity_id == 321
    assert len(loaded.devices) == 1
    assert loaded.devices[0].serial_number == '1234'


def test_last_activity_store_invalid_json_returns_none(tmp_path):
    path = tmp_path / 'last-activity.json'
    path.write_text(json.dumps({'invalid': True}), encoding='utf-8')
    store = LastActivityStore(path)

    assert store.load() is None

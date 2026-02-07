import datetime
import json

from strava_sensor.fitfile.model import BatteryStatus, DeviceStatus
from strava_sensor.last_activity_store import LastActivityMetadata, LastActivityStore


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
    assert loaded.updated_at is not None
    assert loaded.last_activity_id == 321
    assert loaded.last_activity_recorded_at is not None
    assert loaded.last_activity_device_serials == ['1234']
    assert len(loaded.devices) == 1
    assert loaded.devices[0].serial_number == '1234'


def test_last_activity_store_merges_devices_across_saves(tmp_path):
    store = LastActivityStore(tmp_path / 'last-activity.json')
    device_a = _build_device_status('1234')
    device_b = _build_device_status('9876')

    store.save(activity_id=1, devices=[device_a])
    store.save(activity_id=2, devices=[device_b])

    loaded = store.load()
    assert loaded is not None
    assert [device.serial_number for device in loaded.devices] == ['1234', '9876']
    assert loaded.last_activity_id == 2
    assert loaded.last_activity_device_serials == ['9876']


def test_last_activity_store_updates_existing_device_on_save(tmp_path):
    store = LastActivityStore(tmp_path / 'last-activity.json')
    device = _build_device_status('1234')
    updated_device = device.model_copy(update={'battery_level': 17})

    store.save(activity_id=1, devices=[device])
    store.save(activity_id=2, devices=[updated_device])

    loaded = store.load()
    assert loaded is not None
    assert len(loaded.devices) == 1
    assert loaded.devices[0].serial_number == '1234'
    assert loaded.devices[0].battery_level == 17


def test_last_activity_store_invalid_json_returns_none(tmp_path):
    path = tmp_path / 'last-activity.json'
    path.write_text(json.dumps({'invalid': True}), encoding='utf-8')
    store = LastActivityStore(path)

    assert store.load() is None


def test_last_activity_store_loads_legacy_activity_payload(tmp_path):
    path = tmp_path / 'last-activity.json'
    legacy = LastActivityMetadata(
        activity_id=321,
        recorded_at=datetime.datetime(2026, 2, 7, 20, 35, tzinfo=datetime.UTC),
        devices=[_build_device_status('1234')],
    )
    path.write_text(json.dumps(legacy.model_dump(mode='json')), encoding='utf-8')
    store = LastActivityStore(path)

    loaded = store.load()

    assert loaded is not None
    assert loaded.updated_at.isoformat() == '2026-02-07T20:35:00+00:00'
    assert loaded.last_activity_id is None
    assert loaded.last_activity_recorded_at is None
    assert loaded.last_activity_device_serials == []
    assert len(loaded.devices) == 1
    assert loaded.devices[0].serial_number == '1234'


def test_last_activity_store_loads_sensor_payload_without_last_activity_fields(tmp_path):
    path = tmp_path / 'last-activity.json'
    payload = {
        'updated_at': '2026-02-07T20:36:00Z',
        'devices': [_build_device_status('1234').model_dump(mode='json')],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')
    store = LastActivityStore(path)

    loaded = store.load()

    assert loaded is not None
    assert loaded.updated_at.isoformat() == '2026-02-07T20:36:00+00:00'
    assert loaded.last_activity_id is None
    assert loaded.last_activity_recorded_at is None
    assert loaded.last_activity_device_serials == []

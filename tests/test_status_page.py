import datetime

from strava_sensor.fitfile.model import BatteryStatus, DeviceStatus
from strava_sensor.last_activity_store import LastActivityMetadata
from strava_sensor.ui import status_page
from strava_sensor.ui.status_page import StatusViewModel


def _snapshot() -> dict[str, object]:
    return {
        'last_activity_id': 42,
        'last_activity_time': datetime.datetime(2026, 2, 7, 20, 34, tzinfo=datetime.UTC),
        'last_fit_error': None,
        'last_fit_error_time': None,
        'last_webhook_error': None,
        'last_webhook_error_time': None,
        'last_mqtt_publish_device': None,
        'last_mqtt_publish_success': None,
        'last_mqtt_publish_time': None,
        'mqtt_connected': True,
        'mqtt_status_time': None,
    }


def test_status_view_model_shows_persisted_last_activity_metadata(monkeypatch):
    monkeypatch.setattr(status_page.runtime_state, 'snapshot', _snapshot)

    metadata = LastActivityMetadata(
        activity_id=987,
        recorded_at=datetime.datetime(2026, 2, 7, 20, 35, tzinfo=datetime.UTC),
        devices=[
            DeviceStatus(
                device_index=1,
                device_type='bike_light',
                serial_number='1234',
                product='rtl516',
                battery_voltage=5.04,
                battery_status=BatteryStatus.GOOD,
                battery_level=87,
                manufacturer='garmin',
                source_type='antplus',
                software_version='3.00',
                hardware_version='A',
                garmin_product='rtl516',
                antplus_device_type='bike_light',
            )
        ],
    )

    def load_metadata() -> LastActivityMetadata | None:
        return metadata

    model = StatusViewModel(last_activity_loader=load_metadata)
    model.update()

    assert model.last_persisted_activity_id == '987'
    assert model.last_persisted_device_count == '1'
    assert len(model.last_persisted_devices) == 1
    device = model.last_persisted_devices[0]
    assert device.serial_number == '1234'
    assert device.battery_level == '87%'
    assert device.battery_status == 'good'
    assert device.battery_voltage == '5.040 V'


def test_status_view_model_handles_missing_persisted_activity(monkeypatch):
    monkeypatch.setattr(status_page.runtime_state, 'snapshot', _snapshot)

    def load_metadata() -> LastActivityMetadata | None:
        return None

    model = StatusViewModel(last_activity_loader=load_metadata)
    model.update()

    assert model.last_persisted_activity_id == '—'
    assert model.last_persisted_recorded_at == '—'
    assert model.last_persisted_device_count == '—'
    assert model.last_persisted_devices == []

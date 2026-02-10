import datetime

from strava_sensor.fitfile.model import BatteryStatus, DeviceStatus
from strava_sensor.last_activity_store import PersistedSensorState
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

    metadata = PersistedSensorState(
        updated_at=datetime.datetime(2026, 2, 7, 20, 35, tzinfo=datetime.UTC),
        last_activity_id=987,
        last_activity_recorded_at=datetime.datetime(2026, 2, 7, 20, 35, tzinfo=datetime.UTC),
        last_activity_device_serials=['1234'],
        devices=[
            DeviceStatus(
                device_index='1',
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
            ),
            DeviceStatus(
                device_index='2',
                device_type='heart_rate',
                serial_number='5678',
                product='hrm-pro',
                battery_voltage=3.75,
                battery_status=BatteryStatus.OK,
                battery_level=45,
                manufacturer='garmin',
                source_type='antplus',
                software_version='2.00',
                hardware_version='B',
                garmin_product='hrm-pro',
                antplus_device_type='heart_rate',
            ),
        ],
    )

    def load_metadata() -> PersistedSensorState | None:
        return metadata

    model = StatusViewModel(persisted_sensor_loader=load_metadata)
    model.update()

    assert model.persisted_sensor_updated_at == '2026-02-07T20:35:00+00:00'
    assert model.persisted_sensor_count == '2'
    assert model.persisted_last_activity_id == '987'
    assert model.persisted_last_activity_time == '2026-02-07T20:35:00+00:00'
    assert len(model.persisted_sensors) == 2
    latest_device = next(
        device for device in model.persisted_sensors if device.serial_number == '1234'
    )
    assert latest_device.battery_level == '87%'
    assert latest_device.battery_status == 'good'
    assert latest_device.battery_voltage == '5.040 V'
    assert latest_device.last_activity_marker == 'last activity'
    assert latest_device.last_activity_marker_color == 'positive'

    older_device = next(
        device for device in model.persisted_sensors if device.serial_number == '5678'
    )
    assert older_device.last_activity_marker == 'known (older)'
    assert older_device.last_activity_marker_color == 'grey'


def test_status_view_model_handles_missing_persisted_activity(monkeypatch):
    monkeypatch.setattr(status_page.runtime_state, 'snapshot', _snapshot)

    def load_metadata() -> PersistedSensorState | None:
        return None

    model = StatusViewModel(persisted_sensor_loader=load_metadata)
    model.update()

    assert model.persisted_sensor_updated_at == '—'
    assert model.persisted_sensor_count == '—'
    assert model.persisted_last_activity_id == '—'
    assert model.persisted_last_activity_time == '—'
    assert model.persisted_sensors == []

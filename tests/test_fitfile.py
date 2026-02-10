import copy
import datetime

import pytest

from strava_sensor.fitfile.fitfile import (
    CorruptedFitFileError,
    FitFile,
    InvalidActivityFileError,
    NotAFitFileError,
)


def test__fitfile__parse(fitfile_fixture):
    assert fitfile_fixture.messages
    assert fitfile_fixture.activity_id == 3415897090
    assert fitfile_fixture.start_time == datetime.datetime(
        2025, 4, 30, 14, 46, 57, tzinfo=datetime.timezone.utc
    )


def test__fitfile__parse_corrupted_not_a_fitfile():
    content = bytearray(b'not a fit file')
    with pytest.raises(NotAFitFileError):
        FitFile(content)


def test__fitfile__parse_corrupted(fixture_dir):
    content = bytearray((fixture_dir / 'test-1.fit').read_bytes())
    content[25] = 0
    with pytest.raises(CorruptedFitFileError):
        FitFile(content)


def test__fitfile__parse_corrupted_invalid_activity_file(fitfile_fixture):
    fitfile = fitfile_fixture

    # Check required messages
    required_messages = [
        'file_id_mesgs',
        'activity_mesgs',
        'session_mesgs',
        'lap_mesgs',
        'record_mesgs',
    ]
    for message_type in required_messages:
        corrupted_fitfile = copy.deepcopy(fitfile)
        del corrupted_fitfile.messages[message_type]
        with pytest.raises(InvalidActivityFileError):
            corrupted_fitfile.validate_activity_messages()

    # Check one file_id message
    corrupted_fitfile = copy.deepcopy(fitfile)
    corrupted_fitfile.messages['file_id_mesgs'] = [  # type: ignore
        {'serial_number': 1234567890, 'type': 'activity'},
        {'serial_number': 1234567891, 'type': 'activity'},
    ]
    with pytest.raises(InvalidActivityFileError):
        corrupted_fitfile.validate_activity_messages()

    # Check type property of file_id message
    corrupted_fitfile = copy.deepcopy(fitfile)
    corrupted_fitfile.messages['file_id_mesgs'][0]['type'] = 'not_activity'  # type: ignore
    with pytest.raises(InvalidActivityFileError):
        corrupted_fitfile.validate_activity_messages()


def test__fitfile__devices_status(fitfile_fixture):
    device_statuses = fitfile_fixture.get_devices_status()
    assert len(device_statuses) == 4

    bike_radar = [device for device in device_statuses if device.device_type == 'bike_radar'][0]
    assert bike_radar.device_index == '5'
    assert bike_radar.device_type == 'bike_radar'
    assert bike_radar.serial_number == '3359471441'
    assert bike_radar.product == 'varia rtl516'
    assert bike_radar.battery_voltage == 3.7109375
    assert bike_radar.battery_status == 'ok'
    assert bike_radar.battery_level is None
    assert bike_radar.manufacturer == 'garmin'
    assert bike_radar.source_type == 'antplus'
    assert bike_radar.software_version == '3.34'
    assert bike_radar.hardware_version == '66'

    bike_power_primary = [
        device
        for device in device_statuses
        if device.device_type == 'bike_power' and device.battery_identifier == 0
    ][0]
    assert bike_power_primary.device_index == '2'
    assert bike_power_primary.device_type == 'bike_power'
    assert bike_power_primary.serial_number == '7891445'
    assert bike_power_primary.product == 'assioma pro mx-2 spd'
    assert bike_power_primary.battery_voltage == 3.74609375
    assert bike_power_primary.battery_status == 'low'
    assert bike_power_primary.battery_level is None
    assert bike_power_primary.battery_identifier == 0
    assert bike_power_primary.manufacturer == 'favero_electronics'
    assert bike_power_primary.source_type == 'antplus'
    assert bike_power_primary.software_version == '6.1'
    assert bike_power_primary.hardware_version == '7'

    bike_power_secondary = [
        device
        for device in device_statuses
        if device.device_type == 'bike_power' and device.battery_identifier == 1
    ][0]
    assert bike_power_secondary.battery_voltage == 3.75390625
    assert bike_power_secondary.battery_status == 'low'

    bike_speed = [device for device in device_statuses if device.device_type == 'bike_speed'][0]
    assert bike_speed.device_index == '8'
    assert bike_speed.device_type == 'bike_speed'
    assert bike_speed.serial_number == '11699632'
    assert bike_speed.product == 'bsm'
    assert bike_speed.battery_voltage == 2.7734375
    assert bike_speed.battery_status == 'ok'
    assert bike_speed.battery_level is None
    assert bike_speed.manufacturer == 'garmin'
    assert bike_speed.source_type == 'antplus'
    assert bike_speed.software_version == '2.5'
    assert bike_speed.hardware_version == '187'


def test__fitfile__devices_status_ignores_invalid_device_info_message(fitfile_fixture):
    fitfile = copy.deepcopy(fitfile_fixture)
    fitfile.messages['device_info_mesgs'].append(  # type: ignore[arg-type]
        {
            'timestamp': datetime.datetime.now(datetime.UTC),
            'device_index': 2,
            'device_type': 'bike_power',
            'battery_status': 'good',
            # intentionally missing required fields like serial_number and manufacturer
        }
    )

    device_statuses = fitfile.get_devices_status()
    assert len(device_statuses) == 4
    bike_power = [device for device in device_statuses if device.device_type == 'bike_power'][0]
    assert bike_power.serial_number == '7891445'


def test__fitfile__devices_status_reuses_serial_number_from_same_device_index(fitfile_fixture):
    fitfile = copy.deepcopy(fitfile_fixture)
    fitfile.messages['device_info_mesgs'].append(  # type: ignore[arg-type]
        {
            'timestamp': datetime.datetime.now(datetime.UTC),
            'device_index': 2,
            'device_type': 'bike_power',
            'product': 22,
            'battery_status': 'new',
            'battery_voltage': 4.0,
            'manufacturer': 'favero_electronics',
            'source_type': 'antplus',
            # serial_number intentionally missing from latest battery sample
        }
    )

    device_statuses = fitfile.get_devices_status()
    bike_power = [
        device
        for device in device_statuses
        if device.device_type == 'bike_power' and device.battery_identifier == 0
    ][0]
    assert bike_power.serial_number == '7891445'
    assert bike_power.battery_status == 'low'
    assert bike_power.battery_voltage == 3.74609375


def test__fitfile__devices_status_uses_device_metadata_for_aux_batteries(fitfile_fixture):
    fitfile = copy.deepcopy(fitfile_fixture)

    for message in fitfile.messages['device_info_mesgs']:  # type: ignore[index]
        if message.get('device_index') == 2:
            message.pop('battery_status', None)
            message.pop('battery_voltage', None)

    device_statuses = fitfile.get_devices_status()
    bike_power_statuses = [
        device for device in device_statuses if device.device_type == 'bike_power'
    ]

    assert len(bike_power_statuses) == 2
    assert {device.battery_identifier for device in bike_power_statuses} == {0, 1}
    assert {device.battery_voltage for device in bike_power_statuses} == {3.74609375, 3.75390625}
    assert all(device.serial_number == '7891445' for device in bike_power_statuses)

import copy
import datetime

import pytest

from strava_sensor.fitfile.fitfile import (
    CorruptedFitFileError,
    FitFile,
    InvalidActivityFileError,
    NotAFitFileError,
)


def test__fitfile__parse(fixture_dir):
    fitfile = FitFile.from_file(fixture_dir / 'test-1.fit')
    assert fitfile.messages
    assert fitfile.activity_id == 3415897090
    assert fitfile.start_time == datetime.datetime(
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


def test__fitfile__parse_corrupted_invalid_activity_file(fixture_dir):
    content = bytearray((fixture_dir / 'test-1.fit').read_bytes())
    fitfile = FitFile(content)

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


def test__fitfile__devices_status(fixture_dir):
    fitfile = FitFile.from_file(fixture_dir / 'test-1.fit')

    device_statuses = fitfile.get_devices_status()
    assert len(device_statuses) == 3

    bike_radar = device_statuses[0]
    assert bike_radar.device_index == 5
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

    bike_power = device_statuses[1]
    assert bike_power.device_index == 2
    assert bike_power.device_type == 'bike_power'
    assert bike_power.serial_number == '7891445'
    assert bike_power.product == 'assioma pro mx-2 spd'
    assert bike_power.battery_voltage == 3.74609375
    assert bike_power.battery_status == 'low'
    assert bike_power.battery_level is None
    assert bike_power.manufacturer == 'favero_electronics'
    assert bike_power.source_type == 'antplus'
    assert bike_power.software_version == '6.1'
    assert bike_power.hardware_version == '7'

    bike_speed = device_statuses[2]
    assert bike_speed.device_index == 8
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

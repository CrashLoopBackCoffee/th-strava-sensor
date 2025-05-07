import pathlib

from strava_sensor.fitfile.fitfile import CorruptedFitFileError, FitFile, NotAFitFileError


def fitfile_main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Parse a FIT file for debugging')
    parser.add_argument('path', type=pathlib.Path, help='Path to the FIT file')
    args = parser.parse_args()

    try:
        print(f'Parsing {args.path}')
        fitfile = FitFile.from_file(args.path)
        print(f'Serial number: {fitfile.activity_id}')
        print(f'Start time: {fitfile.start_time}')
        print('---')

        devices_status = fitfile.get_devices_status()
        for device_status in devices_status:
            print(f'Device index: {device_status.device_index}')
            print(f'Device type: {device_status.device_type}')
            print(f'Serial number: {device_status.serial_number}')
            print(f'Product: {device_status.product}')
            print(f'Battery voltage: {device_status.battery_voltage}')
            print(f'Battery status: {device_status.battery_status}')
            print(f'Battery level: {device_status.battery_level}')
            print(f'Manufacturer: {device_status.manufacturer}')
            print(f'Source type: {device_status.source_type}')
            print(f'Software version: {device_status.software_version}')
            print(f'Hardware version: {device_status.hardware_version}')
            print('---')
    except (NotAFitFileError, CorruptedFitFileError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

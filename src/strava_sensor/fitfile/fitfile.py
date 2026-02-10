import collections.abc as c
import datetime
import enum
import logging
import pathlib
import typing as t

import garmin_fit_sdk
import pydantic

from strava_sensor.fitfile.model import DeviceStatus

type FitMessageList = c.Sequence[c.Mapping[str | int, t.Any]]
type FitMessages = c.MutableMapping[str, FitMessageList]

_logger = logging.getLogger(__name__)


class NotAFitFileError(ValueError):
    pass


class CorruptedFitFileError(ValueError):
    pass


class InvalidActivityFileError(ValueError):
    pass


class MessageType(enum.StrEnum):
    ACTIVITY = 'activity_mesgs'
    DEVICE_AUX_BATTERY_INFO = 'device_aux_battery_info_mesgs'
    DEVICE_INFO = 'device_info_mesgs'
    FILE_ID = 'file_id_mesgs'
    LAP = 'lap_mesgs'
    RECORD = 'record_mesgs'
    SESSION = 'session_mesgs'


class FitFile:
    def __init__(self, content: bytearray):
        _logger.info('Parsing FIT file')
        stream = garmin_fit_sdk.Stream.from_byte_array(content)
        decoder = garmin_fit_sdk.Decoder(stream)

        if not decoder.is_fit():
            raise NotAFitFileError()

        result: tuple[FitMessages, list[t.Any]] = decoder.read()
        messages, errors = result
        if errors:
            raise CorruptedFitFileError(errors)

        self.messages = messages

        self.validate_activity_messages()

    @staticmethod
    def from_file(path: pathlib.Path) -> 'FitFile':
        return FitFile(bytearray(path.read_bytes()))

    def validate_activity_messages(self) -> None:
        """Validate the mandatory activity messages in the FIT file."""

        # Validate required messages
        for message_type in (
            MessageType.FILE_ID,
            MessageType.ACTIVITY,
            MessageType.SESSION,
            MessageType.LAP,
            MessageType.RECORD,
        ):
            if not self.messages.get(message_type):
                raise InvalidActivityFileError(f'Missing {message_type} message')

        # There must be one file_id message
        if len(self.messages[MessageType.FILE_ID]) != 1:
            raise InvalidActivityFileError('There must be one file_id message')

        # Type property must be set to activity
        if self.messages[MessageType.FILE_ID][0]['type'] != 'activity':
            raise InvalidActivityFileError(
                'Type property of file_id message must be set to activity'
            )

    @property
    def activity_id(self) -> int:
        """Return the serial number of the activity."""
        return self.messages[MessageType.FILE_ID][0]['serial_number']

    @property
    def start_time(self) -> datetime.datetime:
        """Return the start time of the activity."""
        return self.messages[MessageType.SESSION][0]['start_time']

    def get_devices_status(self) -> list[DeviceStatus]:
        device_info = self.messages.get(MessageType.DEVICE_INFO.value, [])

        # Step 1: Build serial number and device info lookup by device_index
        serial_number_by_device_index: dict[str, str] = {}
        device_info_by_index: dict[str, c.Mapping[str | int, t.Any]] = {}
        for message in device_info:
            device_index = str(message.get('device_index', ''))
            serial_number = message.get('serial_number')
            if serial_number:
                serial_number_by_device_index[device_index] = str(serial_number)
            # Keep the latest device_info message for each device_index
            device_info_by_index[device_index] = message

        device_status_by_index: dict[str, DeviceStatus] = {}

        # Step 2: Process device_info messages with battery_status
        for message in device_info:
            if not message.get('battery_status'):
                continue

            # Strip message of int keys which break pydantic validation
            message_stripped = {k: v for k, v in message.items() if isinstance(k, str)}
            message_stripped['device_index'] = str(message_stripped.get('device_index', ''))

            if not message_stripped.get('serial_number'):
                message_stripped['serial_number'] = serial_number_by_device_index.get(
                    message_stripped['device_index']
                )

            try:
                device_status = DeviceStatus.model_validate(message_stripped)
            except pydantic.ValidationError as exc:
                _logger.warning(
                    'Skipping invalid device_info message with battery data: %s (message=%s)',
                    exc,
                    message_stripped,
                )
                continue
            device_status_by_index[device_status.device_index] = device_status

        # Step 3: Process device_aux_battery_info messages to add battery data for devices
        # that don't have battery_status in device_info (e.g., creator/main device)
        device_aux_battery_info = self.messages.get(MessageType.DEVICE_AUX_BATTERY_INFO.value, [])
        for aux_message in device_aux_battery_info:
            device_index = str(aux_message.get('device_index', ''))
            # Skip if aux message has no useful battery data
            has_battery_data = (
                aux_message.get('battery_status')
                or aux_message.get('battery_voltage') is not None
                or aux_message.get('battery_level') is not None
            )
            if not has_battery_data:
                continue

            # Only process aux battery info for devices not already in device_status_by_index
            # (i.e., devices that didn't have battery_status in device_info)
            if device_index not in device_status_by_index and device_index in device_info_by_index:
                # Create new device entry by merging device_info with aux battery info
                base_info = device_info_by_index[device_index]
                # Strip message of int keys which break pydantic validation
                merged_message = {k: v for k, v in base_info.items() if isinstance(k, str)}
                merged_message['device_index'] = device_index

                # Add battery info from aux message
                if aux_message.get('battery_voltage') is not None:
                    merged_message['battery_voltage'] = aux_message['battery_voltage']
                if aux_message.get('battery_status'):
                    merged_message['battery_status'] = aux_message['battery_status']
                if aux_message.get('battery_level') is not None:
                    merged_message['battery_level'] = aux_message['battery_level']

                # Ensure battery_status is present (required by DeviceStatus)
                # Derive from battery_level if not present
                if not merged_message.get('battery_status'):
                    battery_level = merged_message.get('battery_level')
                    if battery_level is not None:
                        # Derive battery_status from battery_level percentage
                        if battery_level > 75:
                            merged_message['battery_status'] = 'good'
                        elif battery_level > 50:
                            merged_message['battery_status'] = 'ok'
                        elif battery_level > 25:
                            merged_message['battery_status'] = 'low'
                        else:
                            merged_message['battery_status'] = 'critical'
                    else:
                        # Default to 'unknown' if we can't determine status
                        merged_message['battery_status'] = 'unknown'

                # Ensure serial number is present
                if not merged_message.get('serial_number'):
                    merged_message['serial_number'] = serial_number_by_device_index.get(
                        device_index
                    )

                # Ensure device_type is present (required by DeviceStatus)
                # For creator/main device, default to 'creator' if not present
                if not merged_message.get('device_type'):
                    merged_message['device_type'] = device_index

                try:
                    device_status = DeviceStatus.model_validate(merged_message)
                    device_status_by_index[device_index] = device_status
                except pydantic.ValidationError as exc:
                    _logger.warning(
                        'Skipping invalid device from aux_battery_info: %s (message=%s)',
                        exc,
                        merged_message,
                    )
                    continue

        return list(device_status_by_index.values())

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
type DeviceKey = tuple[str, int | None]  # (device_index, battery_identifier)

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

        serial_number_by_device_index: dict[str, str] = {}
        for message in device_info:
            serial_number = message.get('serial_number')
            if not serial_number:
                continue
            serial_number_by_device_index[str(message.get('device_index', ''))] = str(serial_number)

        # Build a lookup for device metadata by device_index
        device_metadata_by_index: dict[str, dict] = {}
        for message in device_info:
            device_index = str(message.get('device_index', ''))
            if device_index not in device_metadata_by_index:
                device_metadata_by_index[device_index] = {
                    k: v for k, v in message.items() if isinstance(k, str)
                }

        # Track device status by (device_index, battery_identifier) tuple
        # For devices without aux battery info, battery_identifier is None
        device_status_by_key: dict[DeviceKey, DeviceStatus] = {}

        # Process device_aux_battery_info messages (multiple batteries per device)
        device_aux_battery_info = self.messages.get(MessageType.DEVICE_AUX_BATTERY_INFO.value, [])

        # Track which devices have aux battery info
        devices_with_aux_battery: set[str] = set()

        for message in device_aux_battery_info:
            if not message.get('battery_status'):
                continue

            # Strip message of int keys which break pydantic validation
            message_stripped = {k: v for k, v in message.items() if isinstance(k, str)}
            device_index = str(message_stripped.get('device_index', ''))
            message_stripped['device_index'] = device_index

            # Track that this device has aux battery info
            devices_with_aux_battery.add(device_index)

            # Merge with device metadata
            if device_index in device_metadata_by_index:
                metadata = device_metadata_by_index[device_index].copy()
                # Update with aux battery info (override battery-specific fields)
                metadata.update(message_stripped)
                message_stripped = metadata

            # Ensure serial_number is set
            if not message_stripped.get('serial_number'):
                message_stripped['serial_number'] = serial_number_by_device_index.get(device_index)

            try:
                device_status = DeviceStatus.model_validate(message_stripped)
            except pydantic.ValidationError as exc:
                _logger.warning(
                    'Skipping invalid device_aux_battery_info message: %s (message=%s)',
                    exc,
                    message_stripped,
                )
                continue

            # Use battery_identifier as part of the key
            battery_id = device_status.battery_identifier
            key = (device_status.device_index, battery_id)
            device_status_by_key[key] = device_status

        # Process device_info messages (single battery per device)
        # Only include devices that don't have aux battery info
        for message in device_info:
            if not message.get('battery_status'):
                continue

            device_index = str(message.get('device_index', ''))

            # Skip if this device has aux battery info
            if device_index in devices_with_aux_battery:
                continue

            # Strip message of int keys which break pydantic validation
            message_stripped = {k: v for k, v in message.items() if isinstance(k, str)}
            message_stripped['device_index'] = device_index

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

            # Use None for battery_identifier to represent single-battery devices
            key = (device_status.device_index, None)
            device_status_by_key[key] = device_status

        return list(device_status_by_key.values())

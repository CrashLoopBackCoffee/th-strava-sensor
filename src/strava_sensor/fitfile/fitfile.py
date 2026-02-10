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
        aux_battery_info = self.messages.get(MessageType.DEVICE_AUX_BATTERY_INFO.value, [])

        serial_number_by_device_index: dict[str, str] = {}
        for message in device_info:
            serial_number = message.get('serial_number')
            if not serial_number:
                continue
            serial_number_by_device_index[str(message.get('device_index', ''))] = str(serial_number)

        latest_device_metadata_by_index: dict[
            str, tuple[datetime.datetime | None, dict[str, t.Any]]
        ] = {}
        device_status_by_index: dict[str, DeviceStatus] = {}
        aux_status_by_key: dict[tuple[str, int], tuple[datetime.datetime | None, DeviceStatus]] = {}

        for message in device_info:
            # Strip message of int keys which break pydantic validation
            message_stripped = {k: v for k, v in message.items() if isinstance(k, str)}
            device_index_raw = message_stripped.get('device_index')
            if device_index_raw is None:
                continue

            device_index = str(device_index_raw)
            message_stripped['device_index'] = device_index

            if not message_stripped.get('serial_number'):
                message_stripped['serial_number'] = serial_number_by_device_index.get(device_index)

            required_metadata_fields = ('serial_number', 'product', 'manufacturer', 'source_type')
            has_required_metadata = all(
                field in message_stripped and message_stripped[field] is not None
                for field in required_metadata_fields
            )
            if has_required_metadata:
                timestamp = message_stripped.get('timestamp')
                if not isinstance(timestamp, datetime.datetime):
                    timestamp = None

                previous_entry = latest_device_metadata_by_index.get(device_index)
                if (
                    previous_entry is None
                    or previous_entry[0] is None
                    or (timestamp is not None and previous_entry[0] <= timestamp)
                ):
                    latest_device_metadata_by_index[device_index] = (timestamp, message_stripped)

            if not message.get('battery_status'):
                continue

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

        for message in aux_battery_info:
            battery_identifier = message.get('battery_identifier')
            if not isinstance(battery_identifier, int):
                continue

            device_index_raw = message.get('device_index')
            if device_index_raw is None:
                continue
            device_index = str(device_index_raw)

            metadata_entry = latest_device_metadata_by_index.get(device_index)
            if metadata_entry is None:
                _logger.warning(
                    'Skipping aux battery message because no matching device metadata was found: %s',
                    message,
                )
                continue
            _, base_message = metadata_entry

            message_stripped = {
                k: v for k, v in message.items() if isinstance(k, str) and k != 'timestamp'
            }
            message_stripped['device_index'] = device_index
            merged_message = {
                **base_message,
                **message_stripped,
            }

            try:
                device_status = DeviceStatus.model_validate(merged_message)
            except pydantic.ValidationError as exc:
                _logger.warning(
                    'Skipping invalid device_aux_battery_info message: %s (message=%s)',
                    exc,
                    merged_message,
                )
                continue

            timestamp = message.get('timestamp')
            if not isinstance(timestamp, datetime.datetime):
                timestamp = None

            key = (device_index, battery_identifier)
            previous_status = aux_status_by_key.get(key)
            if (
                previous_status is None
                or previous_status[0] is None
                or (timestamp is not None and previous_status[0] <= timestamp)
            ):
                aux_status_by_key[key] = (timestamp, device_status)

        for device_index, device_status in device_status_by_index.items():
            aux_battery_exists = any(
                aux_device_index == device_index for aux_device_index, _ in aux_status_by_key
            )
            if not aux_battery_exists:
                aux_status_by_key[(device_index, 0)] = (None, device_status)

        return [status for _, status in aux_status_by_key.values()]

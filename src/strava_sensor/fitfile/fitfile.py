import collections.abc as c
import datetime
import enum
import pathlib
import typing as t

import garmin_fit_sdk

from strava_sensor.fitfile.model import DeviceStatus

type FitMessageList = c.Sequence[c.Mapping[str | int, t.Any]]
type FitMessages = c.MutableMapping[str, FitMessageList]


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

        device_status_by_index: dict[int, DeviceStatus] = {}

        for message in device_info:
            if not message.get('battery_status'):
                continue

            # Strip message of int keys which break pydantic validation
            message_stripped = {k: v for k, v in message.items() if isinstance(k, str)}

            device_status = DeviceStatus.model_validate(message_stripped)
            device_status_by_index[device_status.device_index] = device_status

        return list(device_status_by_index.values())

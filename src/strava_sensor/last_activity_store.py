import datetime
import json
import logging
import os
import pathlib
import typing as t

import pydantic

from strava_sensor.fitfile.model import DeviceStatus

_logger = logging.getLogger(__name__)
_LAST_ACTIVITY_METADATA_PATH_ENV = 'STRAVA_SENSOR_LAST_ACTIVITY_METADATA_PATH'
_DEFAULT_LAST_ACTIVITY_METADATA_PATH = '.strava_sensor_last_activity.json'


class LastActivityMetadata(pydantic.BaseModel):
    """Legacy persisted schema retained for backwards compatibility."""

    activity_id: int
    recorded_at: datetime.datetime
    devices: list[DeviceStatus]


class PersistedSensorState(pydantic.BaseModel):
    updated_at: datetime.datetime
    devices: list[DeviceStatus]
    last_activity_id: int | None = None
    last_activity_recorded_at: datetime.datetime | None = None
    last_activity_device_serials: list[str] = pydantic.Field(default_factory=list)


class LastActivityStore:
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path

    @classmethod
    def from_environment(cls) -> 'LastActivityStore':
        configured_path = os.environ.get(
            _LAST_ACTIVITY_METADATA_PATH_ENV,
            _DEFAULT_LAST_ACTIVITY_METADATA_PATH,
        )
        return cls(pathlib.Path(configured_path).expanduser())

    def save(self, activity_id: int, devices: list[DeviceStatus]) -> None:
        existing = self.load()
        merged_devices = self._merge_devices(existing.devices if existing else [], devices)
        now = datetime.datetime.now(datetime.UTC)

        metadata = PersistedSensorState(
            updated_at=now,
            devices=merged_devices,
            last_activity_id=activity_id,
            last_activity_recorded_at=now,
            last_activity_device_serials=sorted({str(device.serial_number) for device in devices}),
        )
        payload = metadata.model_dump(mode='json')

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f'{self.path.suffix}.tmp')
            tmp_path.write_text(json.dumps(payload), encoding='utf-8')
            tmp_path.replace(self.path)
        except OSError:
            _logger.exception('Failed to persist sensor state to %s', self.path)

    def load(self) -> PersistedSensorState | None:
        if not self.path.exists():
            return None

        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            _logger.exception('Failed to read persisted sensor state from %s', self.path)
            return None

        persisted_state = self._validate_state_payload(payload)
        if persisted_state is not None:
            return persisted_state

        _logger.error('Persisted sensor state in %s is invalid', self.path)
        return None

    @staticmethod
    def _merge_devices(
        existing_devices: list[DeviceStatus], incoming_devices: list[DeviceStatus]
    ) -> list[DeviceStatus]:
        merged: dict[str, DeviceStatus] = {
            str(device.serial_number): device for device in existing_devices
        }
        for device in incoming_devices:
            merged[str(device.serial_number)] = device
        return [merged[key] for key in sorted(merged)]

    @staticmethod
    def _validate_state_payload(payload: t.Any) -> PersistedSensorState | None:
        try:
            return PersistedSensorState.model_validate(payload)
        except pydantic.ValidationError:
            pass

        try:
            legacy = LastActivityMetadata.model_validate(payload)
        except pydantic.ValidationError:
            return None

        return PersistedSensorState(
            updated_at=legacy.recorded_at,
            devices=legacy.devices,
        )

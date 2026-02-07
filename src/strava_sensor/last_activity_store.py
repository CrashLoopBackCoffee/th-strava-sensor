import datetime
import json
import logging
import os
import pathlib

import pydantic

from strava_sensor.fitfile.model import DeviceStatus

_logger = logging.getLogger(__name__)
_LAST_ACTIVITY_METADATA_PATH_ENV = 'STRAVA_SENSOR_LAST_ACTIVITY_METADATA_PATH'
_DEFAULT_LAST_ACTIVITY_METADATA_PATH = '.strava_sensor_last_activity.json'


class LastActivityMetadata(pydantic.BaseModel):
    activity_id: int
    recorded_at: datetime.datetime
    devices: list[DeviceStatus]


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
        metadata = LastActivityMetadata(
            activity_id=activity_id,
            recorded_at=datetime.datetime.now(datetime.UTC),
            devices=devices,
        )
        payload = metadata.model_dump(mode='json')

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(f'{self.path.suffix}.tmp')
            tmp_path.write_text(json.dumps(payload), encoding='utf-8')
            tmp_path.replace(self.path)
        except OSError:
            _logger.exception('Failed to persist activity metadata to %s', self.path)

    def load(self) -> LastActivityMetadata | None:
        if not self.path.exists():
            return None

        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            _logger.exception('Failed to read persisted activity metadata from %s', self.path)
            return None

        try:
            return LastActivityMetadata.model_validate(payload)
        except pydantic.ValidationError:
            _logger.exception('Persisted activity metadata in %s is invalid', self.path)
            return None

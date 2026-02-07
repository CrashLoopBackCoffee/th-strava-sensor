import datetime
import threading
import typing as t


class RuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_activity_id: int | None = None
        self._last_activity_time: datetime.datetime | None = None
        self._last_fit_error: str | None = None
        self._last_fit_error_time: datetime.datetime | None = None
        self._last_webhook_error: str | None = None
        self._last_webhook_error_time: datetime.datetime | None = None
        self._last_mqtt_publish_success: bool | None = None
        self._last_mqtt_publish_time: datetime.datetime | None = None
        self._last_mqtt_publish_device: str | None = None
        self._mqtt_connected: bool | None = None
        self._mqtt_status_time: datetime.datetime | None = None

    def record_activity_start(self, activity_id: int) -> None:
        now = datetime.datetime.now(datetime.UTC)
        with self._lock:
            self._last_activity_id = activity_id
            self._last_activity_time = now
            self._last_fit_error = None
            self._last_fit_error_time = None

    def record_fit_error(self, message: str) -> None:
        now = datetime.datetime.now(datetime.UTC)
        with self._lock:
            self._last_fit_error = message
            self._last_fit_error_time = now

    def record_webhook_error(self, message: str) -> None:
        now = datetime.datetime.now(datetime.UTC)
        with self._lock:
            self._last_webhook_error = message
            self._last_webhook_error_time = now

    def record_mqtt_publish(self, device_serial: str, success: bool) -> None:
        now = datetime.datetime.now(datetime.UTC)
        with self._lock:
            self._last_mqtt_publish_device = device_serial
            self._last_mqtt_publish_success = success
            self._last_mqtt_publish_time = now

    def set_mqtt_connected(self, connected: bool | None) -> None:
        now = datetime.datetime.now(datetime.UTC)
        with self._lock:
            self._mqtt_connected = connected
            self._mqtt_status_time = now

    def snapshot(self) -> dict[str, t.Any]:
        with self._lock:
            return {
                'last_activity_id': self._last_activity_id,
                'last_activity_time': self._last_activity_time,
                'last_fit_error': self._last_fit_error,
                'last_fit_error_time': self._last_fit_error_time,
                'last_webhook_error': self._last_webhook_error,
                'last_webhook_error_time': self._last_webhook_error_time,
                'last_mqtt_publish_device': self._last_mqtt_publish_device,
                'last_mqtt_publish_success': self._last_mqtt_publish_success,
                'last_mqtt_publish_time': self._last_mqtt_publish_time,
                'mqtt_connected': self._mqtt_connected,
                'mqtt_status_time': self._mqtt_status_time,
            }


runtime_state = RuntimeState()

import importlib
import logging
import os
import threading
import typing as t

from strava_sensor.runtime_state import runtime_state

_logger = logging.getLogger(__name__)
_TRUTHY_ENV_VALUES = {'1', 'true', 'yes', 'on'}


def _is_truthy_env_var(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in _TRUTHY_ENV_VALUES


class TelemetryMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._initialized = False
        self._metrics_api: t.Any | None = None
        self._activity_started_counter: t.Any | None = None
        self._activity_completed_counter: t.Any | None = None
        self._activity_duration_histogram: t.Any | None = None
        self._fit_parse_error_counter: t.Any | None = None
        self._webhook_event_counter: t.Any | None = None
        self._device_discovered_counter: t.Any | None = None
        self._mqtt_publish_counter: t.Any | None = None

    def _import_module(self, name: str) -> t.Any:
        return importlib.import_module(name)

    def _load_otel_modules(self) -> dict[str, t.Any] | None:
        try:
            metrics_api = self._import_module('opentelemetry.metrics')
        except ModuleNotFoundError:
            return None

        modules: dict[str, t.Any] = {'metrics_api': metrics_api}
        for module_name in (
            'opentelemetry.sdk.metrics',
            'opentelemetry.sdk.metrics.export',
            'opentelemetry.exporter.otlp.proto.http.metric_exporter',
        ):
            try:
                modules[module_name] = self._import_module(module_name)
            except ModuleNotFoundError:
                pass

        return modules

    def _configure_otlp_metrics_export(self, modules: dict[str, t.Any]) -> None:
        otlp_endpoint = os.environ.get('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT') or os.environ.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT'
        )
        if not otlp_endpoint:
            return

        sdk_metrics = modules.get('opentelemetry.sdk.metrics')
        sdk_export = modules.get('opentelemetry.sdk.metrics.export')
        otlp_exporter_module = modules.get('opentelemetry.exporter.otlp.proto.http.metric_exporter')
        if not sdk_metrics or not sdk_export or not otlp_exporter_module:
            _logger.warning(
                'OTLP endpoint configured but OpenTelemetry SDK/exporter packages are missing'
            )
            return

        export_interval_ms = 60000
        raw_export_interval = os.environ.get('STRAVA_SENSOR_OTEL_EXPORT_INTERVAL_MS')
        if raw_export_interval:
            try:
                parsed_export_interval = int(raw_export_interval)
                if parsed_export_interval > 0:
                    export_interval_ms = parsed_export_interval
            except ValueError:
                _logger.warning(
                    'Invalid STRAVA_SENSOR_OTEL_EXPORT_INTERVAL_MS=%s, using default',
                    raw_export_interval,
                )

        exporter = otlp_exporter_module.OTLPMetricExporter()
        reader = sdk_export.PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=export_interval_ms,
        )
        provider = sdk_metrics.MeterProvider(metric_readers=[reader])
        modules['metrics_api'].set_meter_provider(provider)
        _logger.info('Configured OpenTelemetry OTLP metrics export to %s', otlp_endpoint)

    def _observe_mqtt_connection_state(self, _options: t.Any) -> list[t.Any]:
        metrics_api = self._metrics_api
        if metrics_api is None:
            return []

        connected = runtime_state.snapshot().get('mqtt_connected')
        if connected is None:
            state = -1
        elif connected:
            state = 1
        else:
            state = 0

        return [metrics_api.Observation(state, {'source': 'runtime_state'})]

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            self._initialized = True

        modules = self._load_otel_modules()
        if modules is None:
            _logger.info(
                'OpenTelemetry metrics are disabled because opentelemetry packages are not installed'
            )
            return

        if _is_truthy_env_var('STRAVA_SENSOR_OTEL_CONFIGURE_PROVIDER', default=True):
            self._configure_otlp_metrics_export(modules)

        metrics_api = modules['metrics_api']
        self._metrics_api = metrics_api
        meter = metrics_api.get_meter('strava_sensor', version='1.0.0')
        self._activity_started_counter = meter.create_counter(
            'strava_sensor.activities.started',
            unit='{activity}',
            description='Number of activity processing attempts',
        )
        self._activity_completed_counter = meter.create_counter(
            'strava_sensor.activities.completed',
            unit='{activity}',
            description='Number of completed activity processing attempts',
        )
        self._activity_duration_histogram = meter.create_histogram(
            'strava_sensor.activities.duration',
            unit='s',
            description='Activity processing duration',
        )
        self._fit_parse_error_counter = meter.create_counter(
            'strava_sensor.fit.parse_errors',
            unit='{error}',
            description='FIT parsing errors',
        )
        self._webhook_event_counter = meter.create_counter(
            'strava_sensor.webhook.events',
            unit='{event}',
            description='Webhook events observed by the server',
        )
        self._device_discovered_counter = meter.create_counter(
            'strava_sensor.devices.discovered',
            unit='{device}',
            description='Devices discovered while parsing FIT files',
        )
        self._mqtt_publish_counter = meter.create_counter(
            'strava_sensor.mqtt.publish',
            unit='{message}',
            description='MQTT publish attempts for device status',
        )
        meter.create_observable_gauge(
            'strava_sensor.mqtt.connection_state',
            callbacks=[self._observe_mqtt_connection_state],
            description='MQTT connection state (-1 unknown, 0 disconnected, 1 connected)',
            unit='{state}',
        )

    def record_activity_started(self, trigger: str) -> None:
        self.initialize()
        if self._activity_started_counter is None:
            return
        self._activity_started_counter.add(1, attributes={'trigger': trigger})

    def record_activity_completed(
        self,
        trigger: str,
        outcome: str,
        duration_seconds: float | None = None,
    ) -> None:
        self.initialize()
        attributes = {'trigger': trigger, 'outcome': outcome}
        if self._activity_completed_counter is not None:
            self._activity_completed_counter.add(1, attributes=attributes)
        if self._activity_duration_histogram is not None and duration_seconds is not None:
            self._activity_duration_histogram.record(duration_seconds, attributes=attributes)

    def record_fit_parse_error(self, trigger: str) -> None:
        self.initialize()
        if self._fit_parse_error_counter is None:
            return
        self._fit_parse_error_counter.add(1, attributes={'trigger': trigger})

    def record_webhook_event(
        self,
        aspect_type: str | None,
        object_type: str | None,
        *,
        handled: bool,
    ) -> None:
        self.initialize()
        if self._webhook_event_counter is None:
            return

        self._webhook_event_counter.add(
            1,
            attributes={
                'result': 'accepted' if handled else 'ignored',
                'aspect_type': aspect_type or 'unknown',
                'object_type': object_type or 'unknown',
            },
        )

    def record_discovered_devices(self, trigger: str, devices_count: int) -> None:
        self.initialize()
        if self._device_discovered_counter is None:
            return
        if devices_count <= 0:
            return
        self._device_discovered_counter.add(devices_count, attributes={'trigger': trigger})

    def record_mqtt_publish(self, trigger: str, *, success: bool) -> None:
        self.initialize()
        if self._mqtt_publish_counter is None:
            return
        self._mqtt_publish_counter.add(
            1,
            attributes={'trigger': trigger, 'result': 'success' if success else 'failure'},
        )


telemetry = TelemetryMetrics()

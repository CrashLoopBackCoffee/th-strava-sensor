from strava_sensor.telemetry import TelemetryMetrics


class FakeCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[int, dict[str, str]]] = []

    def add(self, value: int, attributes: dict[str, str]) -> None:
        self.calls.append((value, attributes))


class FakeHistogram:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def record(self, value: float, attributes: dict[str, str]) -> None:
        self.calls.append((value, attributes))


class FakeMeter:
    def __init__(self) -> None:
        self.counters: dict[str, FakeCounter] = {}
        self.histograms: dict[str, FakeHistogram] = {}
        self.gauge_callbacks = []

    def create_counter(self, name: str, **_kwargs) -> FakeCounter:
        counter = FakeCounter()
        self.counters[name] = counter
        return counter

    def create_histogram(self, name: str, **_kwargs) -> FakeHistogram:
        histogram = FakeHistogram()
        self.histograms[name] = histogram
        return histogram

    def create_observable_gauge(self, _name: str, callbacks, **_kwargs) -> None:
        self.gauge_callbacks.extend(callbacks)


class FakeMetricsAPI:
    class Observation:
        def __init__(self, value: int, attributes: dict[str, str]) -> None:
            self.value = value
            self.attributes = attributes

    def __init__(self, meter: FakeMeter) -> None:
        self._meter = meter

    def get_meter(self, _name: str, **_kwargs) -> FakeMeter:
        return self._meter

    def set_meter_provider(self, _provider) -> None:
        return None


def test_telemetry_metrics_records_key_events(monkeypatch):
    meter = FakeMeter()
    metrics_api = FakeMetricsAPI(meter)
    telemetry = TelemetryMetrics()
    monkeypatch.setenv('STRAVA_SENSOR_OTEL_CONFIGURE_PROVIDER', 'false')
    monkeypatch.setattr(
        telemetry,
        '_load_otel_modules',
        lambda: {'metrics_api': metrics_api},
    )

    telemetry.record_activity_started(trigger='webhook')
    telemetry.record_activity_completed(trigger='webhook', outcome='success', duration_seconds=1.5)
    telemetry.record_fit_parse_error(trigger='webhook')
    telemetry.record_webhook_event('create', 'activity', handled=True)
    telemetry.record_discovered_devices(trigger='webhook', devices_count=2)
    telemetry.record_mqtt_publish(trigger='webhook', success=True)

    assert meter.counters['strava_sensor.activities.started'].calls == [(1, {'trigger': 'webhook'})]
    assert meter.counters['strava_sensor.activities.completed'].calls == [
        (1, {'trigger': 'webhook', 'outcome': 'success'})
    ]
    assert meter.histograms['strava_sensor.activities.duration'].calls == [
        (1.5, {'trigger': 'webhook', 'outcome': 'success'})
    ]
    assert meter.counters['strava_sensor.fit.parse_errors'].calls == [(1, {'trigger': 'webhook'})]
    assert meter.counters['strava_sensor.webhook.events'].calls == [
        (
            1,
            {
                'result': 'accepted',
                'aspect_type': 'create',
                'object_type': 'activity',
            },
        )
    ]
    assert meter.counters['strava_sensor.devices.discovered'].calls == [(2, {'trigger': 'webhook'})]
    assert meter.counters['strava_sensor.mqtt.publish'].calls == [
        (1, {'trigger': 'webhook', 'result': 'success'})
    ]


def test_telemetry_metrics_is_noop_without_opentelemetry(monkeypatch):
    telemetry = TelemetryMetrics()
    monkeypatch.setattr(telemetry, '_load_otel_modules', lambda: None)

    telemetry.record_activity_started(trigger='cli')
    telemetry.record_activity_completed(trigger='cli', outcome='error', duration_seconds=0.1)
    telemetry.record_fit_parse_error(trigger='cli')
    telemetry.record_webhook_event(None, None, handled=False)
    telemetry.record_discovered_devices(trigger='cli', devices_count=1)
    telemetry.record_mqtt_publish(trigger='cli', success=False)

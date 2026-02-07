import asyncio

from unittest import mock

import pytest
import requests

from fastapi.testclient import TestClient

from strava_sensor import webhook_server
from strava_sensor.strava.webhook import StravaWebhookManager


class MockResponse:
    def __init__(self, status_code=200, json_data=None, should_raise=False):
        self.status_code = status_code
        self._json_data = json_data or {}
        self._should_raise = should_raise

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self._should_raise:
            raise requests.RequestException('boom')


class MockHttpClient:
    def __init__(self, get_response=None, post_response=None, delete_response=None):
        self.get_response = get_response or MockResponse()
        self.post_response = post_response or MockResponse()
        self.delete_response = delete_response or MockResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        if callable(self.get_response):
            return self.get_response()
        return self.get_response

    async def post(self, *args, **kwargs):
        if callable(self.post_response):
            return self.post_response()
        return self.post_response

    async def delete(self, *args, **kwargs):
        if callable(self.delete_response):
            return self.delete_response()
        return self.delete_response


class FakeDeviceStatus:
    def __init__(self, serial_number: str, battery_level: int = 50, publish_result: bool = True):
        self.serial_number = serial_number
        self.battery_level = battery_level
        self._publish_result = publish_result
        self.publish_calls = 0

    def publish_on_mqtt(self, _mqtt_client) -> bool:
        self.publish_calls += 1
        return self._publish_result


@pytest.fixture
def webhook_client():
    return TestClient(webhook_server.app)


@pytest.fixture
def strava_webhook_env(monkeypatch):
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'id')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('STRAVA_WEBHOOK_URL', 'https://cb/url')


@pytest.fixture
def strava_verify_env(monkeypatch):
    monkeypatch.setenv('STRAVA_VERIFY_TOKEN', 'abc')


def create_failing_then_success_get_response(fail_count=1):
    call_count = 0

    def get_response():
        nonlocal call_count
        call_count += 1
        if call_count <= fail_count:
            return MockResponse(should_raise=True)
        return MockResponse(200, [])

    return get_response, lambda: call_count


def create_always_failing_response(status_code=500, json_data=None):
    return lambda: MockResponse(status_code, json_data or {'error': 'server'})


def test_verification_success(strava_verify_env, webhook_client):
    r = webhook_client.get(
        '/strava/webhook',
        params={'hub.mode': 'subscribe', 'hub.verify_token': 'abc', 'hub.challenge': '123'},
    )
    assert r.status_code == 200
    assert r.json() == {'hub.challenge': '123'}


def test_verification_fail(strava_verify_env, webhook_client):
    r = webhook_client.get(
        '/strava/webhook',
        params={'hub.mode': 'subscribe', 'hub.verify_token': 'wrong', 'hub.challenge': '123'},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_manager_find_existing(strava_webhook_env):
    mgr = StravaWebhookManager()
    sample = [{'id': 42, 'callback_url': 'https://cb/url'}]
    mock_client = MockHttpClient(get_response=MockResponse(200, sample))

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 42


@pytest.mark.asyncio
async def test_manager_create(strava_webhook_env):
    mgr = StravaWebhookManager()
    mock_client = MockHttpClient(
        get_response=MockResponse(200, []), post_response=MockResponse(200, {'id': 55})
    )

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 55


@pytest.mark.asyncio
async def test_manager_delete():
    mgr = StravaWebhookManager()
    mgr._subscription_id = 99
    mock_client = MockHttpClient(delete_response=MockResponse(204))

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        await mgr.delete_subscription()
    assert mgr._subscription_id is None


@pytest.mark.asyncio
async def test_manager_missing_env_vars():
    mgr = StravaWebhookManager()
    with pytest.raises(RuntimeError):
        await mgr.ensure_subscription()


@pytest.mark.asyncio
async def test_manager_generates_verify_token(strava_webhook_env):
    mgr = StravaWebhookManager()
    mock_client = MockHttpClient(
        get_response=MockResponse(200, []), post_response=MockResponse(200, {'id': 77})
    )

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 77
    assert mgr.verify_token is not None and len(mgr.verify_token) > 10


def test_healthz_endpoint(webhook_client):
    r = webhook_client.get('/healthz')
    assert r.status_code == 200
    j = r.json()
    assert j['status'] == 'ok'
    assert 'subscription_id' in j


def test_mqtt_disconnect_endpoint(webhook_client, monkeypatch):
    async def fake_disconnect():
        return {'ok': True, 'connected': False, 'message': 'MQTT client disconnected'}

    monkeypatch.setattr(webhook_server, '_disconnect_mqtt_client', fake_disconnect)
    r = webhook_client.post('/api/mqtt/disconnect')
    assert r.status_code == 200
    assert r.json() == {'ok': True, 'connected': False, 'message': 'MQTT client disconnected'}


def test_mqtt_reconnect_endpoint(webhook_client, monkeypatch):
    async def fake_reconnect():
        return {'ok': False, 'connected': False, 'message': 'Failed to connect MQTT client'}

    monkeypatch.setattr(webhook_server, '_reconnect_mqtt_client', fake_reconnect)
    r = webhook_client.post('/api/mqtt/reconnect')
    assert r.status_code == 200
    assert r.json() == {'ok': False, 'connected': False, 'message': 'Failed to connect MQTT client'}


def test_main_uses_websockets_sansio(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setenv('WEBHOOK_PORT', '8010')
    monkeypatch.setattr(webhook_server, 'setup_logging', lambda: None)

    def fake_run(app, **kwargs):
        captured['app'] = app
        captured.update(kwargs)

    monkeypatch.setattr(webhook_server.uvicorn, 'run', fake_run)

    webhook_server.main()

    assert captured['app'] is webhook_server.app
    assert captured['host'] == '0.0.0.0'
    assert captured['port'] == 8010
    assert captured['ws'] == 'websockets-sansio'


@pytest.mark.asyncio
async def test_retry_list_then_success(strava_webhook_env, monkeypatch):
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRIES', '3')
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRY_DELAY', '0')
    mgr = StravaWebhookManager()

    get_response_func, get_call_counter = create_failing_then_success_get_response(fail_count=1)
    post_calls = []

    def post_response():
        post_calls.append(1)
        return MockResponse(200, {'id': 101})

    mock_client = MockHttpClient(get_response=get_response_func, post_response=post_response)

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 101
    assert get_call_counter() >= 2
    assert len(post_calls) == 1


@pytest.mark.asyncio
async def test_retry_create_fail(strava_webhook_env, monkeypatch):
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRIES', '2')
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRY_DELAY', '0')
    mgr = StravaWebhookManager()

    mock_client = MockHttpClient(
        get_response=MockResponse(200, []),
        post_response=create_always_failing_response(500, {'error': 'server'}),
    )

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        with pytest.raises(RuntimeError):
            await mgr.ensure_subscription()


@pytest.mark.asyncio
async def test_lifespan_does_not_block_on_webhook_registration(strava_webhook_env, monkeypatch):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_register_webhook():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def fake_delete_webhook():
        return None

    monkeypatch.setattr(webhook_server, '_register_webhook', fake_register_webhook)
    monkeypatch.setattr(webhook_server, '_delete_webhook', fake_delete_webhook)

    async def _run_lifespan_once():
        async with webhook_server.lifespan(webhook_server.app):
            await asyncio.wait_for(started.wait(), timeout=0.2)

    await asyncio.wait_for(_run_lifespan_once(), timeout=0.5)
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_register_webhook_applies_configured_delay(monkeypatch):
    monkeypatch.setenv('STRAVA_WEBHOOK_REGISTRATION_DELAY', '2.5')
    events = []

    async def fake_sleep(seconds):
        events.append(f'sleep:{seconds}')

    async def fake_ensure_subscription():
        events.append('ensure')
        return 123

    monkeypatch.setattr(webhook_server.asyncio, 'sleep', fake_sleep)
    monkeypatch.setattr(
        webhook_server.manager_singleton, 'ensure_subscription', fake_ensure_subscription
    )

    await webhook_server._register_webhook()
    assert events == ['sleep:2.5', 'ensure']


@pytest.mark.asyncio
async def test_register_webhook_invalid_delay_defaults_to_zero(monkeypatch):
    monkeypatch.setenv('STRAVA_WEBHOOK_REGISTRATION_DELAY', 'not-a-number')
    sleep_called = False
    ensure_called = False

    async def fake_sleep(_seconds):
        nonlocal sleep_called
        sleep_called = True

    async def fake_ensure_subscription():
        nonlocal ensure_called
        ensure_called = True
        return 456

    monkeypatch.setattr(webhook_server.asyncio, 'sleep', fake_sleep)
    monkeypatch.setattr(
        webhook_server.manager_singleton, 'ensure_subscription', fake_ensure_subscription
    )

    await webhook_server._register_webhook()
    assert ensure_called
    assert not sleep_called


@pytest.mark.asyncio
async def test_process_activity_persists_last_activity_metadata(monkeypatch):
    devices = [FakeDeviceStatus('1234')]
    save_calls = []

    class FakeStravaSource:
        def read_activity(self, _uri: str) -> bytes:
            return b'fit-bytes'

    class FakeFitFile:
        def __init__(self, _fit_bytes: bytes):
            pass

        def get_devices_status(self):
            return devices

    class FakeStore:
        def save(self, activity_id, saved_devices):
            save_calls.append((activity_id, saved_devices))

    monkeypatch.setattr(webhook_server, 'StravaSource', FakeStravaSource)
    monkeypatch.setattr(webhook_server, 'initialize_sources', lambda: [FakeStravaSource()])
    monkeypatch.setattr(webhook_server, 'FitFile', FakeFitFile)
    monkeypatch.setattr(webhook_server, '_last_activity_store', FakeStore())
    monkeypatch.setattr(webhook_server._state, 'mqtt_client', None)

    await webhook_server._process_activity_async(42)

    assert save_calls == [(42, devices)]


@pytest.mark.asyncio
async def test_process_manual_fit_upload_success(monkeypatch):
    devices = [FakeDeviceStatus('1234')]
    save_calls = []

    class FakeFitFile:
        def __init__(self, _fit_bytes: bytes):
            pass

        def get_devices_status(self):
            return devices

    class FakeStore:
        def save(self, activity_id, saved_devices):
            save_calls.append((activity_id, saved_devices))

    monkeypatch.setattr(webhook_server, 'FitFile', FakeFitFile)
    monkeypatch.setattr(webhook_server, '_last_activity_store', FakeStore())
    monkeypatch.setattr(webhook_server._state, 'mqtt_client', None)

    result = await webhook_server._process_manual_fit_upload('debug.fit', b'fit-bytes')

    assert result == {'ok': True, 'message': 'Processed "debug.fit" and found 1 device(s)'}
    assert len(save_calls) == 1
    assert isinstance(save_calls[0][0], int)
    assert save_calls[0][1] == devices


@pytest.mark.asyncio
async def test_process_manual_fit_upload_fit_parse_error(monkeypatch):
    fit_errors = []

    class FakeFitFile:
        def __init__(self, _fit_bytes: bytes):
            raise webhook_server.NotAFitFileError('invalid fit')

    def fake_record_fit_error(message):
        fit_errors.append(message)

    monkeypatch.setattr(webhook_server, 'FitFile', FakeFitFile)
    monkeypatch.setattr(
        webhook_server.runtime_state,
        'record_fit_error',
        fake_record_fit_error,
    )

    result = await webhook_server._process_manual_fit_upload('broken.fit', b'bad')

    assert result == {
        'ok': False,
        'message': 'Failed to parse FIT file "broken.fit": invalid fit',
    }
    assert fit_errors == ['invalid fit']


@pytest.mark.asyncio
async def test_reconnect_mqtt_republishes_persisted_metadata(monkeypatch):
    monkeypatch.setenv('MQTT_BROKER_URL', 'mqtt://broker:1883')
    monkeypatch.setenv('MQTT_USERNAME', 'user')
    monkeypatch.setenv('MQTT_PASSWORD', 'pass')

    device = FakeDeviceStatus('1234')
    saved_records = []

    class FakeMetadata:
        activity_id = 99
        devices = [device]

    class FakeStore:
        def load(self):
            return FakeMetadata()

    class FakeMQTTClient:
        def __init__(self, on_connect_callback=None):
            self._on_connect_callback = on_connect_callback
            self._connected = False

        def connect(self, _broker_url: str, _username: str, _password: str):
            self._connected = True
            if self._on_connect_callback:
                self._on_connect_callback(self)

        def disconnect(self):
            self._connected = False

        @property
        def connected(self):
            return self._connected

    monkeypatch.setattr(webhook_server, 'MQTTClient', FakeMQTTClient)
    monkeypatch.setattr(webhook_server, '_last_activity_store', FakeStore())
    monkeypatch.setattr(
        webhook_server.runtime_state,
        'record_mqtt_publish',
        lambda serial, success: saved_records.append((serial, success)),
    )
    monkeypatch.setattr(webhook_server._state, 'mqtt_client', None)

    result = await webhook_server._reconnect_mqtt_client()

    assert result == {'ok': True, 'connected': True, 'message': 'MQTT client connected'}
    assert device.publish_calls == 1
    assert saved_records == [('1234', True)]

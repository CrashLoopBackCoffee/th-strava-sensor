from unittest import mock

import pytest
import requests

from fastapi.testclient import TestClient

from strava_sensor.strava.webhook import StravaWebhookManager
from strava_sensor.webhook_server import app


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


@pytest.fixture
def webhook_client():
    return TestClient(app)


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


@pytest.mark.asyncio
async def test_retry_list_then_success(strava_webhook_env, monkeypatch):
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRIES', '3')
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
    mgr = StravaWebhookManager()

    mock_client = MockHttpClient(
        get_response=MockResponse(200, []),
        post_response=create_always_failing_response(500, {'error': 'server'}),
    )

    with mock.patch('httpx.AsyncClient', lambda *_args, **_kwargs: mock_client):
        with pytest.raises(RuntimeError):
            await mgr.ensure_subscription()

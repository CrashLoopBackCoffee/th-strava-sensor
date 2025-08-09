from unittest import mock

import pytest
import requests

from fastapi.testclient import TestClient

from strava_sensor.strava.webhook import StravaWebhookManager
from strava_sensor.webhook_server import app


def test_verification_success(monkeypatch):
    monkeypatch.setenv('STRAVA_VERIFY_TOKEN', 'abc')
    client = TestClient(app)
    r = client.get(
        '/strava/webhook',
        params={'hub.mode': 'subscribe', 'hub.verify_token': 'abc', 'hub.challenge': '123'},
    )
    assert r.status_code == 200
    assert r.json() == {'hub.challenge': '123'}


def test_verification_fail(monkeypatch):
    monkeypatch.setenv('STRAVA_VERIFY_TOKEN', 'abc')
    client = TestClient(app)
    r = client.get(
        '/strava/webhook',
        params={'hub.mode': 'subscribe', 'hub.verify_token': 'wrong', 'hub.challenge': '123'},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_manager_find_existing(monkeypatch):
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'id')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('STRAVA_WEBHOOK_URL', 'https://cb/url')
    mgr = StravaWebhookManager()

    sample = [{'id': 42, 'callback_url': 'https://cb/url'}]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *a, **k):
            class R:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return sample

            return R()

    with mock.patch('httpx.AsyncClient', FakeClient):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 42


@pytest.mark.asyncio
async def test_manager_create(monkeypatch):
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'id')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('STRAVA_WEBHOOK_URL', 'https://cb/url')
    mgr = StravaWebhookManager()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *a, **k):
            class R:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return []

            return R()

        async def post(self, *a, **k):
            class R:
                status_code = 200

                def json(self):
                    return {'id': 55}

            return R()

    with mock.patch('httpx.AsyncClient', FakeClient):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 55


@pytest.mark.asyncio
async def test_manager_delete(monkeypatch):
    mgr = StravaWebhookManager()
    mgr._subscription_id = 99

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def delete(self, *a, **k):
            class R:
                status_code = 204

            return R()

    with mock.patch('httpx.AsyncClient', FakeClient):
        await mgr.delete_subscription()
    assert mgr._subscription_id is None


@pytest.mark.asyncio
async def test_manager_missing_env_vars():
    mgr = StravaWebhookManager()
    with pytest.raises(RuntimeError):
        await mgr.ensure_subscription()


@pytest.mark.asyncio
async def test_manager_generates_verify_token(monkeypatch):
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'id')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('STRAVA_WEBHOOK_URL', 'https://cb/url')
    mgr = StravaWebhookManager()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *a, **k):
            class R:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return []

            return R()

        async def post(self, *a, **k):
            class R:
                status_code = 200

                def json(self):
                    return {'id': 77}

            return R()

    with mock.patch('httpx.AsyncClient', FakeClient):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 77
    assert mgr.verify_token is not None and len(mgr.verify_token) > 10


def test_healthz_endpoint():
    client = TestClient(app)
    r = client.get('/healthz')
    assert r.status_code == 200
    j = r.json()
    assert j['status'] == 'ok'
    assert 'subscription_id' in j


@pytest.mark.asyncio
async def test_retry_list_then_success(monkeypatch):
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'id')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('STRAVA_WEBHOOK_URL', 'https://cb/url')
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRIES', '3')
    mgr = StravaWebhookManager()

    # First call raises, second returns empty list, then create succeeds
    get_calls = []
    post_calls = []

    def fake_get(*args, **kwargs):
        get_calls.append(1)

        class R:
            def __init__(self, status_code=200, data=None):
                self.status_code = status_code
                self._data = data or []

            def raise_for_status(self):
                # Fail only on the first attempt
                if len(get_calls) == 1:
                    raise requests.RequestException('boom')

            def json(self):
                return self._data

        if len(get_calls) == 1:
            return R()
        return R(200, [])

    def fake_post(*args, **kwargs):
        post_calls.append(1)

        class R:
            status_code = 200

            def json(self):
                return {'id': 101}

        return R()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *a, **k):
            return fake_get()

        async def post(self, *a, **k):
            return fake_post()

    with mock.patch('httpx.AsyncClient', FakeClient):
        sub_id = await mgr.ensure_subscription()
    assert sub_id == 101
    assert len(get_calls) >= 2
    assert len(post_calls) == 1


@pytest.mark.asyncio
async def test_retry_create_fail(monkeypatch):
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'id')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('STRAVA_WEBHOOK_URL', 'https://cb/url')
    monkeypatch.setenv('STRAVA_SUBSCRIPTION_RETRIES', '2')
    mgr = StravaWebhookManager()

    def ok_get(*args, **kwargs):  # returns empty list
        class R:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return []

        return R()

    def failing_post(*args, **kwargs):
        class R:
            status_code = 500

            def json(self):
                return {'error': 'server'}

        return R()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *a, **k):
            return ok_get()

        async def post(self, *a, **k):
            return failing_post()

    with mock.patch('httpx.AsyncClient', FakeClient):
        with pytest.raises(RuntimeError):
            await mgr.ensure_subscription()

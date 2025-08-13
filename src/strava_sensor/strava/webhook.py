import asyncio
import logging
import os
import secrets

from typing import Any, Awaitable, Callable

import httpx

_logger = logging.getLogger(__name__)


class StravaWebhookManager:
    """Manage Strava push subscription lifecycle.

    Ensures subscription exists on startup (if env vars present) and
    deletes it on shutdown. Strava allows only a single subscription
    per app scoped by callback URL.
    """

    base_url = 'https://www.strava.com/api/v3'

    def __init__(self) -> None:
        self.client_id = os.environ.get('STRAVA_CLIENT_ID')
        self.client_secret = os.environ.get('STRAVA_CLIENT_SECRET')
        # May be auto-generated later if not supplied
        self.verify_token = os.environ.get('STRAVA_VERIFY_TOKEN')
        self.callback_url = os.environ.get('STRAVA_WEBHOOK_URL')
        self._subscription_id: int | None = None
        self._lock = asyncio.Lock()

    # ----- internal helpers -----
    def _auth_params(self) -> dict[str, str]:
        return {
            'client_id': self.client_id or '',
            'client_secret': self.client_secret or '',
        }

    # ----- lifecycle -----
    async def ensure_subscription(self) -> int:
        """Ensure a Strava push subscription exists.

        Returns the subscription id. Raises RuntimeError if required
        environment variables are missing or API calls fail.
        """
        if not (self.client_id and self.client_secret and self.callback_url):
            raise RuntimeError(
                'Missing one or more required env vars: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_WEBHOOK_URL'
            )
        # Generate a token if not provided
        if not self.verify_token:
            self.verify_token = secrets.token_urlsafe(24)
            _logger.info('Generated STRAVA_VERIFY_TOKEN %s', self.verify_token)
        async with self._lock:
            if self._subscription_id is not None:
                return self._subscription_id
            existing = await self._find_existing_subscription_id()
            if existing:
                self._subscription_id = existing
                _logger.info('Using existing Strava subscription %s', existing)
                return existing
            self._subscription_id = await self._create_subscription()
            _logger.info('Created Strava subscription %s', self._subscription_id)
            return self._subscription_id

    async def delete_subscription(self) -> None:
        async with self._lock:
            if not self._subscription_id:
                return
            sub_id = self._subscription_id
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.delete(
                        f'{self.base_url}/push_subscriptions/{sub_id}', params=self._auth_params()
                    )
                    if resp.status_code not in (200, 204, 404):
                        _logger.warning(
                            'Unexpected status %s deleting Strava subscription %s',
                            resp.status_code,
                            sub_id,
                        )
                    else:
                        _logger.info('Deleted Strava subscription %s', sub_id)
            except Exception:
                _logger.exception('Failed to delete Strava subscription %s', sub_id)
            finally:
                self._subscription_id = None

    # ----- API calls -----
    async def _retry(self, func: Callable[[], Awaitable[Any]], action: str) -> Any:
        attempts = int(os.environ.get('STRAVA_SUBSCRIPTION_RETRIES', '3'))
        base_delay = float(os.environ.get('STRAVA_SUBSCRIPTION_RETRY_DELAY', '1.0'))
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await func()
            except Exception as e:
                last_exc = e
                if attempt == attempts:
                    break
                sleep_for = base_delay * (2 ** (attempt - 1))
                _logger.warning(
                    'Attempt %s/%s to %s failed (%s); retrying in %.1fs',
                    attempt,
                    attempts,
                    action,
                    e,
                    sleep_for,
                )
                await asyncio.sleep(sleep_for)
        raise RuntimeError(f'Failed to {action} after {attempts} attempts: {last_exc}')

    async def _find_existing_subscription_id(self) -> int | None:
        async def _call():
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f'{self.base_url}/push_subscriptions', params=self._auth_params()
                )
                resp.raise_for_status()
                subs: list[dict[str, Any]] = resp.json()
                for sub in subs:
                    if sub.get('callback_url') == self.callback_url:
                        return int(sub['id'])
                return None

        return await self._retry(_call, 'list Strava subscriptions')

    async def _create_subscription(self) -> int:
        async def _call():
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f'{self.base_url}/push_subscriptions',
                    params=self._auth_params(),
                    data={'callback_url': self.callback_url, 'verify_token': self.verify_token},
                )
                if resp.status_code >= 400:
                    try:
                        detail = resp.json()
                    except Exception:
                        detail = resp.text[:500]
                    raise RuntimeError(
                        f'Failed to create Strava subscription (status={resp.status_code}): {detail}'
                    )
                data = resp.json()
                return int(data['id'])

        return await self._retry(_call, 'create Strava subscription')

    @property
    def subscription_id(self) -> int | None:  # convenience accessor
        return self._subscription_id


manager_singleton = StravaWebhookManager()

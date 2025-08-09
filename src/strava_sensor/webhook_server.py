"""Webhook server handling Strava subscription and persistent MQTT client.

Note: A module-level mqtt_client singleton is intentionally used for persistence across
webhook activity processing threads. Lint warning for global reassignment is acceptable.
"""

import asyncio
import contextlib
import logging
import os
import threading
import time

from typing import Any

import fastapi
import uvicorn

from strava_sensor.cli import initialize_sources, setup_logging
from strava_sensor.fitfile.fitfile import CorruptedFitFileError, FitFile, NotAFitFileError
from strava_sensor.mqtt.mqtt import MQTTClient
from strava_sensor.source.strava import StravaSource
from strava_sensor.strava.webhook import manager_singleton

_logger = logging.getLogger(__name__)


async def _register_webhook():
    """Register the Strava webhook subscription on startup."""

    _logger.info('Wait to register Strava webhook subscription')
    # Wait for 10 seconds to give the server time to start
    await asyncio.sleep(2)

    # Ensure subscription AFTER server is listening to avoid Strava verification race.
    _logger.info('Registering Strava webhook subscription')
    try:
        # Call async variant directly (avoid sync wrapper which uses asyncio.run())
        sub_id = await manager_singleton.ensure_subscription()
        if manager_singleton.verify_token and not os.environ.get('STRAVA_VERIFY_TOKEN'):
            _logger.info('Using generated STRAVA_VERIFY_TOKEN=%s', manager_singleton.verify_token)
        _logger.info('Active Strava subscription id=%s', sub_id)
    except Exception as e:  # fail hard so container/platform restarts
        _logger.error('Startup failed ensuring Strava subscription: %s', e)
        raise


async def _delete_webhook():
    # Use async deletion to avoid blocking event loop
    await manager_singleton.delete_subscription()


class _State:
    mqtt_client: MQTTClient | None = None


_state = _State()


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    """Lifespan event to ensure subscription + persistent MQTT on startup and cleanup on shutdown."""

    asyncio.create_task(_register_webhook())
    # Initialize persistent MQTT client if env vars provided
    # persistent MQTT client lives on _state
    if (
        os.environ.get('MQTT_BROKER_URL')
        and os.environ.get('MQTT_USERNAME')
        and os.environ.get('MQTT_PASSWORD')
    ):
        try:
            _state.mqtt_client = MQTTClient()
            _state.mqtt_client.connect(
                os.environ['MQTT_BROKER_URL'],
                os.environ['MQTT_USERNAME'],
                os.environ['MQTT_PASSWORD'],
            )
            # Wait briefly for connection (non-fatal if not connected yet)
            start = time.time()
            while not _state.mqtt_client.connected and time.time() - start < 5:
                await asyncio.sleep(0.1)
            if _state.mqtt_client.connected:
                _logger.info('Persistent MQTT client started')
            else:
                _logger.warning('Persistent MQTT client not connected after timeout')
        except Exception:  # don't fail whole app; log
            _logger.exception('Failed to start persistent MQTT client')
            _state.mqtt_client = None
    yield
    # Shutdown sequence
    if _state.mqtt_client:
        try:
            _state.mqtt_client.disconnect()
            _logger.info('Persistent MQTT client disconnected')
        except Exception:
            _logger.exception('Error disconnecting MQTT client')
    await _delete_webhook()


app = fastapi.FastAPI(lifespan=lifespan)


@app.get('/healthz')
def healthz():  # simple liveness/readiness probe
    # Try to expose subscription id if already ensured; do not trigger ensure side effects here.
    sub_id = getattr(manager_singleton, 'current_subscription_id', None)
    return {'status': 'ok', 'subscription_id': sub_id}


@app.get('/strava/webhook')
def verify_subscription(
    hub_mode: str | None = fastapi.Query(None, alias='hub.mode'),
    hub_verify_token: str | None = fastapi.Query(None, alias='hub.verify_token'),
    hub_challenge: str | None = fastapi.Query(None, alias='hub.challenge'),
):
    # Strava appears to first issue a plain GET (no hub.* params) to verify 200 responsiveness.
    # Return a simple OK payload in that case so subscription creation does not fail with 400.
    if hub_mode is None and hub_verify_token is None and hub_challenge is None:
        return {'status': 'ready'}
    expected = manager_singleton.verify_token or os.environ.get('STRAVA_VERIFY_TOKEN')
    if hub_mode == 'subscribe' and hub_verify_token == expected:
        _logger.info('Strava verification succeeded')
        return {'hub.challenge': hub_challenge}
    _logger.warning('Strava verification failed: mode=%s token=%s', hub_mode, hub_verify_token)
    raise fastapi.HTTPException(status_code=400, detail='Verification failed')


@app.post('/strava/webhook')
async def handle_event(payload: dict[str, Any]):
    aspect_type = payload.get('aspect_type')
    object_type = payload.get('object_type')
    object_id = payload.get('object_id')
    _logger.debug('Received webhook payload %s', payload)
    if aspect_type == 'create' and object_type == 'activity' and object_id:
        thread = threading.Thread(target=_process_activity, args=(int(object_id),), daemon=True)
        thread.start()
        return {'status': 'processing'}
    return {'status': 'ignored'}


def _process_activity(activity_id: int) -> None:
    _logger.info('Processing Strava activity %s from webhook', activity_id)
    try:
        activity_url = f'https://www.strava.com/activities/{activity_id}'
        sources = initialize_sources()
        strava_source: StravaSource | None = None
        for s in sources:
            if isinstance(s, StravaSource):
                strava_source = s
                break
        if not strava_source:
            _logger.error('Strava source not initialized; cannot process activity %s', activity_id)
            return
        _logger.info('Reading activity %s from Strava', activity_url)
        fit_bytes = strava_source.read_activity(activity_url)
        _logger.debug('Read %d bytes from Strava activity %s', len(fit_bytes), activity_id)
        fitfile = FitFile(fit_bytes)
        _logger.debug('Parsed FIT file for activity %s', activity_id)
        devices_status = fitfile.get_devices_status()
        # Reuse persistent MQTT client if available
        if _state.mqtt_client:
            start = time.time()
            while not _state.mqtt_client.connected and time.time() - start < 5:
                time.sleep(0.1)
        if not devices_status:
            _logger.info('No devices found in activity %s', activity_id)
        for device_status in devices_status:
            _logger.info(
                'Publishing device %s battery %s%%',
                device_status.serial_number,
                device_status.battery_level,
            )
            if _state.mqtt_client:
                device_status.publish_on_mqtt(_state.mqtt_client)
    # Do not disconnect persistent client here
    except (NotAFitFileError, CorruptedFitFileError) as e:
        _logger.error('FIT parse error for activity %s: %s', activity_id, e)
    except Exception:
        _logger.exception('Unhandled error processing activity %s', activity_id)


def main() -> None:  # entry point
    setup_logging()
    port = int(os.environ.get('WEBHOOK_PORT', '8000'))
    _logger.info('Starting webhook server on port %s', port)
    uvicorn.run(app, host='0.0.0.0', port=port)


if __name__ == '__main__':  # pragma: no cover
    main()

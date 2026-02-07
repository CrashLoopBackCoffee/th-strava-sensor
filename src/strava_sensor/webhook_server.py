"""Webhook server handling Strava subscription and persistent MQTT client.

Note: A module-level mqtt_client singleton is intentionally used for persistence across
webhook activity processing threads. Lint warning for global reassignment is acceptable.
"""

import asyncio
import contextlib
import datetime
import logging
import os
import time

from typing import Any

import fastapi
import uvicorn

from strava_sensor.cli import initialize_sources, setup_logging
from strava_sensor.fitfile.fitfile import (
    CorruptedFitFileError,
    FitFile,
    InvalidActivityFileError,
    NotAFitFileError,
)
from strava_sensor.fitfile.model import DeviceStatus
from strava_sensor.last_activity_store import LastActivityStore
from strava_sensor.mqtt.mqtt import MQTTClient
from strava_sensor.runtime_state import runtime_state
from strava_sensor.source.strava import StravaSource
from strava_sensor.strava.webhook import manager_singleton
from strava_sensor.ui.status_page import register_status_page

_logger = logging.getLogger(__name__)
_MQTT_ENV_VARS = ('MQTT_BROKER_URL', 'MQTT_USERNAME', 'MQTT_PASSWORD')
_last_activity_store = LastActivityStore.from_environment()


def _get_registration_delay_seconds() -> float:
    raw_delay = os.environ.get('STRAVA_WEBHOOK_REGISTRATION_DELAY', '0')
    try:
        delay_seconds = float(raw_delay)
    except ValueError:
        _logger.warning(
            'Invalid STRAVA_WEBHOOK_REGISTRATION_DELAY=%s; defaulting to 0 seconds',
            raw_delay,
        )
        return 0.0
    if delay_seconds < 0:
        _logger.warning(
            'Negative STRAVA_WEBHOOK_REGISTRATION_DELAY=%s; defaulting to 0 seconds',
            raw_delay,
        )
        return 0.0
    return delay_seconds


async def _register_webhook():
    """Register the Strava webhook subscription on startup."""
    try:
        delay_seconds = _get_registration_delay_seconds()
        if delay_seconds > 0:
            _logger.info('Delaying Strava webhook registration by %.1f seconds', delay_seconds)
            await asyncio.sleep(delay_seconds)

        _logger.info('Registering Strava webhook subscription')
        # Call async variant directly (avoid sync wrapper which uses asyncio.run())
        sub_id = await manager_singleton.ensure_subscription()
        if manager_singleton.verify_token and not os.environ.get('STRAVA_VERIFY_TOKEN'):
            _logger.info('Using generated STRAVA_VERIFY_TOKEN=%s', manager_singleton.verify_token)
        _logger.info('Active Strava subscription id=%s', sub_id)
    except asyncio.CancelledError:
        _logger.info('Webhook registration task cancelled')
        raise
    except Exception as exc:
        _logger.exception('Failed to register Strava webhook subscription')
        runtime_state.record_webhook_error(str(exc))


async def _delete_webhook():
    # Use async deletion to avoid blocking event loop
    await manager_singleton.delete_subscription()


class _State:
    mqtt_client: MQTTClient | None = None
    webhook_registration_task: asyncio.Task[None] | None = None


_state = _State()
_mqtt_client_lock = asyncio.Lock()


def _mqtt_env_is_configured() -> bool:
    return all(os.environ.get(name) for name in _MQTT_ENV_VARS)


def _persist_sensor_state(activity_id: int, devices_status: list[DeviceStatus]) -> None:
    _last_activity_store.save(activity_id, devices_status)


def _republish_persisted_sensor_state(mqtt_client: MQTTClient) -> None:
    persisted_state = _last_activity_store.load()
    if not persisted_state:
        _logger.debug('No persisted sensor state found to republish')
        return
    if not persisted_state.devices:
        _logger.info(
            'Persisted sensor state has no devices to republish',
        )
        return

    _logger.info(
        'Republishing %s persisted device statuses',
        len(persisted_state.devices),
    )
    for device_status in persisted_state.devices:
        success = device_status.publish_on_mqtt(mqtt_client)
        runtime_state.record_mqtt_publish(str(device_status.serial_number), success)
        if not success:
            _logger.warning(
                'Failed to republish persisted MQTT data for device %s',
                device_status.serial_number,
            )


def _on_mqtt_connect(mqtt_client: MQTTClient) -> None:
    runtime_state.set_mqtt_connected(True)
    try:
        _republish_persisted_sensor_state(mqtt_client)
    except Exception:
        _logger.exception('Failed to republish persisted sensor state on MQTT connect')


async def _sync_mqtt_state() -> None:
    if _state.mqtt_client:
        start = time.time()
        while not _state.mqtt_client.connected and time.time() - start < 5:
            await asyncio.sleep(0.1)
        runtime_state.set_mqtt_connected(_state.mqtt_client.connected)
        return
    runtime_state.set_mqtt_connected(None)


def _publish_devices_statuses(devices_status: list[DeviceStatus]) -> None:
    for device_status in devices_status:
        _logger.info(
            'Publishing device %s battery %s%%',
            device_status.serial_number,
            device_status.battery_level,
        )
        if _state.mqtt_client:
            success = device_status.publish_on_mqtt(_state.mqtt_client)
            runtime_state.record_mqtt_publish(
                str(device_status.serial_number),
                success,
            )
            if not success:
                _logger.warning(
                    'Failed to publish MQTT data for device %s',
                    device_status.serial_number,
                )


async def _process_fit_bytes_async(
    activity_id: int, fit_bytes: bytearray | bytes
) -> list[DeviceStatus]:
    loop = asyncio.get_event_loop()
    fit_payload = fit_bytes if isinstance(fit_bytes, bytearray) else bytearray(fit_bytes)
    fitfile = await loop.run_in_executor(None, FitFile, fit_payload)
    _logger.debug('Parsed FIT file for activity %s', activity_id)

    devices_status = fitfile.get_devices_status()
    _persist_sensor_state(activity_id, devices_status)
    await _sync_mqtt_state()

    if not devices_status:
        _logger.info('No devices found in activity %s', activity_id)

    _publish_devices_statuses(devices_status)
    return devices_status


async def _disconnect_mqtt_client() -> dict[str, Any]:
    async with _mqtt_client_lock:
        if not _state.mqtt_client:
            runtime_state.set_mqtt_connected(False)
            return {
                'ok': True,
                'connected': False,
                'message': 'MQTT client already disconnected',
            }

        mqtt_client = _state.mqtt_client
        _state.mqtt_client = None
        try:
            mqtt_client.disconnect()
        except Exception as exc:
            _logger.exception('Error disconnecting MQTT client')
            runtime_state.set_mqtt_connected(False)
            return {
                'ok': False,
                'connected': False,
                'message': f'Failed to disconnect MQTT client: {exc}',
            }

        runtime_state.set_mqtt_connected(False)
        _logger.info('Persistent MQTT client disconnected')
        return {'ok': True, 'connected': False, 'message': 'MQTT client disconnected'}


async def _reconnect_mqtt_client() -> dict[str, Any]:
    async with _mqtt_client_lock:
        if _state.mqtt_client:
            try:
                _state.mqtt_client.disconnect()
            except Exception:
                _logger.exception('Error disconnecting existing MQTT client before reconnect')
            finally:
                _state.mqtt_client = None

        if not _mqtt_env_is_configured():
            runtime_state.set_mqtt_connected(None)
            message = 'MQTT environment variables not fully set; cannot reconnect'
            _logger.warning(message)
            return {'ok': False, 'connected': None, 'message': message}

        mqtt_client = MQTTClient(on_connect_callback=_on_mqtt_connect)
        try:
            mqtt_client.connect(
                os.environ['MQTT_BROKER_URL'],
                os.environ['MQTT_USERNAME'],
                os.environ['MQTT_PASSWORD'],
            )
        except Exception as exc:
            runtime_state.set_mqtt_connected(False)
            _logger.exception('Failed to start persistent MQTT client')
            return {
                'ok': False,
                'connected': False,
                'message': f'Failed to connect MQTT client: {exc}',
            }

        _state.mqtt_client = mqtt_client
        start = time.time()
        while not mqtt_client.connected and time.time() - start < 5:
            await asyncio.sleep(0.1)

        runtime_state.set_mqtt_connected(mqtt_client.connected)
        if mqtt_client.connected:
            _logger.info('Persistent MQTT client started')
            return {'ok': True, 'connected': True, 'message': 'MQTT client connected'}

        _logger.warning('Persistent MQTT client not connected after timeout')
        return {
            'ok': True,
            'connected': False,
            'message': 'MQTT reconnect initiated; waiting for broker connection',
        }


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    """Lifespan event to ensure subscription + persistent MQTT on startup and cleanup on shutdown."""

    # Validate required environment variables upfront
    required_env_vars = ['STRAVA_CLIENT_ID', 'STRAVA_CLIENT_SECRET', 'STRAVA_WEBHOOK_URL']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        error_msg = f'Missing required environment variables: {", ".join(missing_vars)}'
        _logger.warning(error_msg)
        runtime_state.record_webhook_error(error_msg)

    # Initialize persistent MQTT client if env vars provided
    # persistent MQTT client lives on _state
    if _mqtt_env_is_configured():
        await _reconnect_mqtt_client()
    else:
        _logger.warning(
            'MQTT environment variables not fully set; skipping MQTT client initialization'
        )
        runtime_state.set_mqtt_connected(None)

    if not missing_vars:
        # Register webhook in background so startup can complete and Strava can verify callback URL.
        _state.webhook_registration_task = asyncio.create_task(
            _register_webhook(),
            name='strava-webhook-registration',
        )
    yield

    # Shutdown sequence
    if _state.webhook_registration_task:
        if not _state.webhook_registration_task.done():
            _state.webhook_registration_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _state.webhook_registration_task
        _state.webhook_registration_task = None

    if _state.mqtt_client:
        await _disconnect_mqtt_client()
    await _delete_webhook()


app = fastapi.FastAPI(lifespan=lifespan)


@app.get('/healthz')
def healthz():  # simple liveness/readiness probe
    # Try to expose subscription id if already ensured; do not trigger ensure side effects here.
    sub_id = getattr(manager_singleton, 'current_subscription_id', None)
    mqtt_status = (
        'connected' if _state.mqtt_client and _state.mqtt_client.connected else 'disconnected'
    )
    return {'status': 'ok', 'subscription_id': sub_id, 'mqtt_status': mqtt_status}


@app.post('/api/mqtt/disconnect')
async def disconnect_mqtt() -> dict[str, Any]:
    return await _disconnect_mqtt_client()


@app.post('/api/mqtt/reconnect')
async def reconnect_mqtt() -> dict[str, Any]:
    return await _reconnect_mqtt_client()


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
        # Use asyncio task instead of thread for better resource management
        asyncio.create_task(_process_activity_async(int(object_id)))
        return {'status': 'processing'}
    return {'status': 'ignored'}


async def _process_activity_async(activity_id: int) -> None:
    _logger.info('Processing Strava activity %s from webhook', activity_id)
    runtime_state.record_activity_start(activity_id)
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

        # Run the synchronous operations in a thread pool to avoid blocking the event loop
        fit_bytes = await asyncio.to_thread(strava_source.read_activity, activity_url)
        _logger.debug('Read %d bytes from Strava activity %s', len(fit_bytes), activity_id)
        await _process_fit_bytes_async(activity_id, fit_bytes)
    # Do not disconnect persistent client here
    except (NotAFitFileError, CorruptedFitFileError, InvalidActivityFileError) as e:
        runtime_state.record_fit_error(str(e))
        _logger.error('FIT parse error for activity %s: %s', activity_id, e)
    except Exception:
        runtime_state.record_fit_error(
            f'Unhandled error at {datetime.datetime.now(datetime.UTC).isoformat()}'
        )
        _logger.exception('Unhandled error processing activity %s', activity_id)


async def _process_manual_fit_upload(filename: str, fit_bytes: bytes) -> dict[str, Any]:
    # Use a timestamp-based synthetic id so manual debug uploads are visible in runtime state.
    activity_id = int(datetime.datetime.now(datetime.UTC).timestamp() * 1000)
    runtime_state.record_activity_start(activity_id)
    _logger.info(
        'Processing manually uploaded FIT file %s with synthetic id %s', filename, activity_id
    )
    try:
        devices_status = await _process_fit_bytes_async(activity_id, fit_bytes)
    except (NotAFitFileError, CorruptedFitFileError, InvalidActivityFileError) as e:
        error_message = str(e) or e.__class__.__name__
        runtime_state.record_fit_error(error_message)
        _logger.error('FIT parse error for manually uploaded file %s: %s', filename, error_message)
        return {'ok': False, 'message': f'Failed to parse FIT file "{filename}": {error_message}'}
    except Exception:
        runtime_state.record_fit_error(
            f'Unhandled error at {datetime.datetime.now(datetime.UTC).isoformat()}'
        )
        _logger.exception('Unhandled error processing manually uploaded file %s', filename)
        return {'ok': False, 'message': f'Unhandled error while processing "{filename}"'}

    return {
        'ok': True,
        'message': f'Processed "{filename}" and found {len(devices_status)} device(s)',
    }


def main() -> None:  # entry point
    setup_logging()
    port = int(os.environ.get('WEBHOOK_PORT', '8000'))
    _logger.info('Starting webhook server on http://localhost:%s', port)
    # Prefer websockets-sansio to avoid deprecated legacy protocol imports.
    uvicorn.run(app, host='0.0.0.0', port=port, ws='websockets-sansio', log_config=None)


register_status_page(
    app,
    mqtt_disconnect_action=_disconnect_mqtt_client,
    mqtt_reconnect_action=_reconnect_mqtt_client,
    fit_upload_action=_process_manual_fit_upload,
    persisted_sensor_loader=_last_activity_store.load,
)


if __name__ == '__main__':  # pragma: no cover
    main()

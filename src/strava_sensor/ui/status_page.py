import datetime
import os

import fastapi

from nicegui import ui

from strava_sensor.runtime_state import runtime_state
from strava_sensor.strava.webhook import manager_singleton


def _format_time(value: datetime.datetime | None) -> str:
    if not value:
        return '—'
    return value.isoformat()


def _env_value(name: str) -> str:
    return 'set' if os.environ.get(name) else 'missing'


class StatusViewModel:
    def __init__(self) -> None:
        self.subscription_id = '—'
        self.webhook_url = '—'
        self.webhook_error = '—'
        self.mqtt_status = 'unknown'
        self.mqtt_last_publish = '—'
        self.last_activity = '—'
        self.last_activity_time = '—'
        self.last_fit_error = '—'
        self.env_strava = '—'
        self.env_mqtt = '—'

    def update(self) -> None:
        snapshot = runtime_state.snapshot()
        subscription_id = manager_singleton.subscription_id
        mqtt_connected = snapshot['mqtt_connected']
        mqtt_status = 'unknown'
        if mqtt_connected is True:
            mqtt_status = 'connected'
        elif mqtt_connected is False:
            mqtt_status = 'disconnected'

        self.subscription_id = f'Subscription id: {subscription_id or "—"}'
        self.webhook_url = f'Webhook URL: {os.environ.get("STRAVA_WEBHOOK_URL", "—")}'
        self.webhook_error = (
            f'Webhook error: {snapshot["last_webhook_error"] or "—"} '
            f'at {_format_time(snapshot["last_webhook_error_time"])}'
        )
        self.mqtt_status = f'MQTT status: {mqtt_status}'
        self.mqtt_last_publish = (
            'Last publish: '
            f'{snapshot["last_mqtt_publish_device"] or "—"} '
            f'({snapshot["last_mqtt_publish_success"]}) '
            f'at {_format_time(snapshot["last_mqtt_publish_time"])}'
        )
        self.last_activity = f'Last activity: {snapshot["last_activity_id"] or "—"}'
        self.last_activity_time = (
            f'Last activity time: {_format_time(snapshot["last_activity_time"])}'
        )
        self.last_fit_error = (
            f'Last FIT error: {snapshot["last_fit_error"] or "—"} '
            f'at {_format_time(snapshot["last_fit_error_time"])}'
        )
        self.env_strava = (
            'Strava: '
            f'CLIENT_ID={_env_value("STRAVA_CLIENT_ID")}, '
            f'CLIENT_SECRET={_env_value("STRAVA_CLIENT_SECRET")}, '
            f'WEBHOOK_URL={_env_value("STRAVA_WEBHOOK_URL")}'
        )
        self.env_mqtt = (
            'MQTT: '
            f'BROKER_URL={_env_value("MQTT_BROKER_URL")}, '
            f'USERNAME={_env_value("MQTT_USERNAME")}, '
            f'PASSWORD={_env_value("MQTT_PASSWORD")}'
        )


def register_status_page(app: fastapi.FastAPI) -> None:
    @app.get('/status')
    def status_redirect() -> fastapi.responses.RedirectResponse:
        return fastapi.responses.RedirectResponse(url='/', status_code=307)

    @ui.page('/')
    def status_page() -> None:
        model = StatusViewModel()

        with ui.column().classes('w-full max-w-4xl mx-auto'):
            ui.label('Strava Sensor Status').classes('text-2xl font-bold')
            ui.label('Live overview of webhook, MQTT, and activity processing state.').classes(
                'text-sm text-gray-500'
            )

            with ui.row().classes('w-full gap-4'):
                with ui.card().classes('flex-1'):
                    ui.label('Webhook').classes('text-lg font-semibold')
                    ui.label().bind_text_from(model, 'subscription_id')
                    ui.label().bind_text_from(model, 'webhook_url')
                    ui.label().bind_text_from(model, 'webhook_error')

                with ui.card().classes('flex-1'):
                    ui.label('MQTT').classes('text-lg font-semibold')
                    ui.label().bind_text_from(model, 'mqtt_status')
                    ui.label().bind_text_from(model, 'mqtt_last_publish')

            with ui.card().classes('w-full'):
                ui.label('Last Activity').classes('text-lg font-semibold')
                ui.label().bind_text_from(model, 'last_activity')
                ui.label().bind_text_from(model, 'last_activity_time')
                ui.label().bind_text_from(model, 'last_fit_error')

            with ui.card().classes('w-full'):
                ui.label('Environment Readiness').classes('text-lg font-semibold')
                ui.label().bind_text_from(model, 'env_strava')
                ui.label().bind_text_from(model, 'env_mqtt')

        model.update()
        ui.timer(5.0, model.update)

    ui.run_with(app)

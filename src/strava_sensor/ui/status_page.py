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
        self.webhook_health = 'warn'
        self.mqtt_health = 'warn'
        self.activity_health = 'warn'
        self.env_health = 'warn'

    def update(self) -> None:
        snapshot = runtime_state.snapshot()
        subscription_id = manager_singleton.subscription_id
        strava_env_ready = all(
            os.environ.get(name)
            for name in ('STRAVA_CLIENT_ID', 'STRAVA_CLIENT_SECRET', 'STRAVA_WEBHOOK_URL')
        )
        mqtt_env_ready = all(
            os.environ.get(name) for name in ('MQTT_BROKER_URL', 'MQTT_USERNAME', 'MQTT_PASSWORD')
        )
        mqtt_connected = snapshot['mqtt_connected']
        mqtt_status = 'unknown'
        if mqtt_connected is True:
            mqtt_status = 'connected'
        elif mqtt_connected is False:
            mqtt_status = 'disconnected'

        self.webhook_health = 'warn'
        if snapshot['last_webhook_error'] or not strava_env_ready:
            self.webhook_health = 'error'
        elif subscription_id:
            self.webhook_health = 'ok'

        self.mqtt_health = 'warn'
        if mqtt_connected is True:
            self.mqtt_health = 'ok'
        elif mqtt_connected is False:
            self.mqtt_health = 'error'

        self.activity_health = 'warn'
        if snapshot['last_fit_error']:
            self.activity_health = 'error'
        elif snapshot['last_activity_id']:
            self.activity_health = 'ok'

        self.env_health = 'warn'
        if strava_env_ready and mqtt_env_ready:
            self.env_health = 'ok'
        elif not strava_env_ready and not mqtt_env_ready:
            self.env_health = 'error'

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

        def _render_health_badge(prefix: str, status_field: str) -> None:
            ui.badge(f'{prefix}: OK').props('color=positive').bind_visibility_from(
                model, status_field, value='ok'
            )
            ui.badge(f'{prefix}: Attention').props('color=warning').bind_visibility_from(
                model, status_field, value='warn'
            )
            ui.badge(f'{prefix}: Error').props('color=negative').bind_visibility_from(
                model, status_field, value='error'
            )

        with ui.column().classes('w-full max-w-5xl mx-auto gap-4 px-4 py-6'):
            ui.label('Strava Sensor Status').classes('text-3xl font-bold text-slate-900')
            ui.label('Live overview of webhook, MQTT, and activity processing state.').classes(
                'text-sm text-slate-600'
            )
            with ui.row().classes('w-full gap-2 flex-wrap'):
                _render_health_badge('Webhook', 'webhook_health')
                _render_health_badge('MQTT', 'mqtt_health')
                _render_health_badge('Activity', 'activity_health')
                _render_health_badge('Env', 'env_health')

            with ui.row().classes('w-full gap-4 items-stretch'):
                with ui.card().classes('flex-1 min-w-[320px] border border-slate-200 shadow-sm'):
                    ui.label('Webhook').classes('text-lg font-semibold text-slate-900')
                    ui.label().bind_text_from(model, 'subscription_id').classes(
                        'text-base text-slate-800'
                    )
                    ui.label().bind_text_from(model, 'webhook_url').classes(
                        'text-base text-slate-800'
                    )
                    ui.label().bind_text_from(model, 'webhook_error').classes(
                        'text-base text-slate-800'
                    )

                with ui.card().classes('flex-1 min-w-[320px] border border-slate-200 shadow-sm'):
                    ui.label('MQTT').classes('text-lg font-semibold text-slate-900')
                    ui.label().bind_text_from(model, 'mqtt_status').classes(
                        'text-base text-slate-800'
                    )
                    ui.label().bind_text_from(model, 'mqtt_last_publish').classes(
                        'text-base text-slate-800'
                    )

            with ui.card().classes('w-full border border-slate-200 shadow-sm'):
                ui.label('Last Activity').classes('text-lg font-semibold text-slate-900')
                ui.label().bind_text_from(model, 'last_activity').classes(
                    'text-base text-slate-800'
                )
                ui.label().bind_text_from(model, 'last_activity_time').classes(
                    'text-base text-slate-800'
                )
                ui.label().bind_text_from(model, 'last_fit_error').classes(
                    'text-base text-slate-800'
                )

            with ui.card().classes('w-full border border-slate-200 shadow-sm'):
                ui.label('Environment Readiness').classes('text-lg font-semibold text-slate-900')
                ui.label().bind_text_from(model, 'env_strava').classes('text-base text-slate-800')
                ui.label().bind_text_from(model, 'env_mqtt').classes('text-base text-slate-800')

        model.update()
        ui.timer(5.0, model.update)

    ui.run_with(app)

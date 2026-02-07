import dataclasses
import datetime
import os
import typing as t

import fastapi

from nicegui import events, ui

from strava_sensor.fitfile.model import DeviceStatus
from strava_sensor.last_activity_store import LastActivityMetadata
from strava_sensor.runtime_state import runtime_state
from strava_sensor.strava.webhook import manager_singleton


def _format_time(value: datetime.datetime | None) -> str:
    if not value:
        return '—'
    return value.isoformat()


def _env_value(name: str) -> str:
    return 'set' if os.environ.get(name) else 'missing'


def _show_or_na(value: t.Any) -> str:
    return str(value) if value is not None else 'n/a'


def _pretty_name(value: str) -> str:
    return value.replace('_', ' ')


def _format_battery_level(level: int | None) -> str:
    if level is None:
        return 'n/a'
    return f'{level}%'


def _format_voltage(voltage: float | None) -> str:
    if voltage is None:
        return 'n/a'
    return f'{voltage:.3f} V'


@dataclasses.dataclass
class PersistedDeviceView:
    title: str
    battery_level: str
    battery_status: str
    battery_voltage: str
    serial_number: str
    manufacturer: str
    product: str
    source_type: str
    software_version: str
    hardware_version: str


class StatusViewModel:
    def __init__(
        self,
        last_activity_loader: t.Callable[[], LastActivityMetadata | None] | None = None,
    ) -> None:
        self._last_activity_loader = last_activity_loader
        self.subscription_id = '—'
        self.webhook_url = '—'
        self.webhook_error = '—'
        self.webhook_error_time = '—'
        self.mqtt_status = 'Unknown'
        self.mqtt_connected: bool | None = None
        self.mqtt_action_label = 'Reconnect MQTT'
        self.mqtt_last_publish_device = '—'
        self.mqtt_last_publish_success = '—'
        self.mqtt_last_publish_time = '—'
        self.last_activity_id = '—'
        self.last_activity_time = '—'
        self.last_fit_error_message = '—'
        self.last_fit_error_time = '—'
        self.last_persisted_activity_id = '—'
        self.last_persisted_recorded_at = '—'
        self.last_persisted_device_count = '—'
        self.last_persisted_devices: list[PersistedDeviceView] = []
        self.env_strava_client_id = 'missing'
        self.env_strava_client_secret = 'missing'
        self.env_strava_webhook_url = 'missing'
        self.env_mqtt_broker_url = 'missing'
        self.env_mqtt_username = 'missing'
        self.env_mqtt_password = 'missing'
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
        self.mqtt_connected = mqtt_connected
        mqtt_status = 'Unknown'
        if mqtt_connected is True:
            mqtt_status = 'Connected'
        elif mqtt_connected is False:
            mqtt_status = 'Disconnected'

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

        self.subscription_id = str(subscription_id or '—')
        self.webhook_url = os.environ.get('STRAVA_WEBHOOK_URL') or '—'
        self.webhook_error = snapshot['last_webhook_error'] or '—'
        self.webhook_error_time = _format_time(snapshot['last_webhook_error_time'])
        self.mqtt_status = mqtt_status
        self.mqtt_action_label = 'Disconnect MQTT' if mqtt_connected is True else 'Reconnect MQTT'
        self.mqtt_last_publish_device = str(snapshot['last_mqtt_publish_device'] or '—')
        mqtt_success = snapshot['last_mqtt_publish_success']
        if mqtt_success is True:
            self.mqtt_last_publish_success = 'true'
        elif mqtt_success is False:
            self.mqtt_last_publish_success = 'false'
        else:
            self.mqtt_last_publish_success = '—'
        self.mqtt_last_publish_time = _format_time(snapshot['last_mqtt_publish_time'])
        self.last_activity_id = str(snapshot['last_activity_id'] or '—')
        self.last_activity_time = _format_time(snapshot['last_activity_time'])
        self.last_fit_error_message = snapshot['last_fit_error'] or '—'
        self.last_fit_error_time = _format_time(snapshot['last_fit_error_time'])
        self.env_strava_client_id = _env_value('STRAVA_CLIENT_ID')
        self.env_strava_client_secret = _env_value('STRAVA_CLIENT_SECRET')
        self.env_strava_webhook_url = _env_value('STRAVA_WEBHOOK_URL')
        self.env_mqtt_broker_url = _env_value('MQTT_BROKER_URL')
        self.env_mqtt_username = _env_value('MQTT_USERNAME')
        self.env_mqtt_password = _env_value('MQTT_PASSWORD')
        self._update_last_activity_metadata()

    def _update_last_activity_metadata(self) -> None:
        if self._last_activity_loader is None:
            self.last_persisted_activity_id = '—'
            self.last_persisted_recorded_at = '—'
            self.last_persisted_device_count = '—'
            self.last_persisted_devices = []
            return

        metadata = self._last_activity_loader()
        if not metadata:
            self.last_persisted_activity_id = '—'
            self.last_persisted_recorded_at = '—'
            self.last_persisted_device_count = '—'
            self.last_persisted_devices = []
            return

        self.last_persisted_activity_id = str(metadata.activity_id)
        self.last_persisted_recorded_at = _format_time(metadata.recorded_at)
        self.last_persisted_device_count = str(len(metadata.devices))
        self.last_persisted_devices = self._format_devices(metadata.devices)

    @staticmethod
    def _format_devices(devices: list[DeviceStatus]) -> list[PersistedDeviceView]:
        views: list[PersistedDeviceView] = []
        for device in devices:
            views.append(
                PersistedDeviceView(
                    title=f'#{device.device_index} {_pretty_name(device.device_type)}',
                    battery_level=_format_battery_level(device.battery_level),
                    battery_status=str(device.battery_status),
                    battery_voltage=_format_voltage(device.battery_voltage),
                    serial_number=str(device.serial_number),
                    manufacturer=_pretty_name(device.manufacturer),
                    product=device.product,
                    source_type=_pretty_name(device.source_type),
                    software_version=_show_or_na(device.software_version),
                    hardware_version=_show_or_na(device.hardware_version),
                )
            )
        return views


def register_status_page(
    app: fastapi.FastAPI,
    mqtt_disconnect_action: t.Callable[[], t.Awaitable[dict[str, t.Any]]] | None = None,
    mqtt_reconnect_action: t.Callable[[], t.Awaitable[dict[str, t.Any]]] | None = None,
    fit_upload_action: t.Callable[[str, bytes], t.Awaitable[dict[str, t.Any]]] | None = None,
    last_activity_loader: t.Callable[[], LastActivityMetadata | None] | None = None,
) -> None:
    @app.get('/status')
    def status_redirect() -> fastapi.responses.RedirectResponse:
        return fastapi.responses.RedirectResponse(url='/', status_code=307)

    @ui.page('/')
    def status_page() -> None:
        model = StatusViewModel(last_activity_loader=last_activity_loader)
        device_cards_container: t.Any | None = None
        fit_upload_input: t.Any | None = None
        ui.add_head_html(
            """
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link
                href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap"
                rel="stylesheet"
            >
            <style>
                body {
                    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
                    background:
                        radial-gradient(1200px 400px at -5% -10%, #e0f2fe 0%, transparent 70%),
                        radial-gradient(1000px 320px at 110% 10%, #dcfce7 0%, transparent 70%),
                        #f8fafc;
                    color: #0f172a;
                }
                .status-shell {
                    max-width: 1100px;
                }
                .status-card {
                    border-radius: 16px;
                    border: 1px solid #d9e2ec;
                    background: rgba(255, 255, 255, 0.94);
                    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
                }
                .status-field {
                    display: grid;
                    grid-template-columns: 12rem minmax(0, 1fr);
                    gap: 0.75rem;
                    align-items: start;
                    margin: 0.45rem 0;
                }
                .status-key {
                    font-size: 0.78rem;
                    letter-spacing: 0.04em;
                    font-weight: 700;
                    text-transform: uppercase;
                    color: #64748b;
                }
                .status-value {
                    font-size: 1rem;
                    line-height: 1.45rem;
                    color: #0f172a;
                    word-break: break-word;
                }
                .status-value--mono {
                    font-family: "IBM Plex Mono", "SFMono-Regular", ui-monospace, monospace;
                    font-size: 0.93rem;
                }
                .status-device-card {
                    border-radius: 12px;
                    border: 1px solid #e2e8f0;
                    background: #f8fafc;
                    box-shadow: none;
                }
                .status-device-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 0.55rem 1.1rem;
                    width: 100%;
                }
                .status-device-k {
                    font-size: 0.72rem;
                    letter-spacing: 0.04em;
                    font-weight: 700;
                    text-transform: uppercase;
                    color: #64748b;
                }
                .status-device-v {
                    font-size: 0.92rem;
                    line-height: 1.35rem;
                    color: #0f172a;
                    word-break: break-word;
                }
                @media (max-width: 680px) {
                    .status-field {
                        grid-template-columns: minmax(0, 1fr);
                        gap: 0.25rem;
                    }
                }
            </style>
            """
        )

        async def _run_mqtt_action(
            action: t.Callable[[], t.Awaitable[dict[str, t.Any]]] | None,
            unavailable_message: str,
        ) -> None:
            if action is None:
                ui.notify(unavailable_message, color='warning')
                return

            result = await action()
            _refresh_model()
            ui.notify(result['message'], color='positive' if result['ok'] else 'negative')

        async def _toggle_mqtt() -> None:
            _refresh_model()
            if model.mqtt_connected is True:
                await _run_mqtt_action(
                    mqtt_disconnect_action,
                    unavailable_message='MQTT disconnect action is unavailable',
                )
                return
            await _run_mqtt_action(
                mqtt_reconnect_action,
                unavailable_message='MQTT reconnect action is unavailable',
            )

        async def _handle_fit_upload(event: events.UploadEventArguments) -> None:
            if fit_upload_action is None:
                ui.notify('Manual FIT upload action is unavailable', color='warning')
                return

            upload_name = event.file.name
            fit_bytes = await event.file.read()
            result = await fit_upload_action(upload_name, fit_bytes)
            _refresh_model()
            ui.notify(result['message'], color='positive' if result['ok'] else 'negative')
            if fit_upload_input is not None:
                fit_upload_input.reset()

        def _render_health_badge(prefix: str, status_field: str) -> None:
            ui.badge(f'{prefix}: OK').props('color=positive').classes(
                'text-sm px-3 py-1 rounded-full font-semibold'
            ).bind_visibility_from(model, status_field, value='ok')
            ui.badge(f'{prefix}: Attention').props('color=warning').classes(
                'text-sm px-3 py-1 rounded-full font-semibold'
            ).bind_visibility_from(model, status_field, value='warn')
            ui.badge(f'{prefix}: Error').props('color=negative').classes(
                'text-sm px-3 py-1 rounded-full font-semibold'
            ).bind_visibility_from(model, status_field, value='error')

        def _render_field(
            label: str,
            field_name: str,
            *,
            monospace: bool = False,
        ) -> None:
            with ui.element('div').classes('status-field'):
                ui.label(label).classes('status-key')
                value_label = ui.label().bind_text_from(model, field_name).classes('status-value')
                if monospace:
                    value_label.classes('status-value--mono')

        def _battery_status_color(status: str) -> str:
            if status in {'good', 'new', 'ok'}:
                return 'positive'
            if status in {'low'}:
                return 'warning'
            if status in {'critical'}:
                return 'negative'
            if status in {'charging'}:
                return 'info'
            return 'grey'

        def _render_device_value(label: str, value: str) -> None:
            with ui.column().classes('gap-0'):
                ui.label(label).classes('status-device-k')
                ui.label(value).classes('status-device-v')

        def _render_persisted_devices(container: t.Any) -> None:
            container.clear()
            with container:
                if not model.last_persisted_devices:
                    ui.label('No persisted device status available yet.').classes(
                        'text-sm text-slate-500'
                    )
                    return

                for device in model.last_persisted_devices:
                    with ui.card().classes('status-device-card w-full'):
                        with ui.row().classes(
                            'w-full items-center justify-between gap-2 flex-wrap'
                        ):
                            ui.label(device.title).classes('text-base font-semibold text-slate-900')
                            ui.badge(f'{device.battery_level} ({device.battery_status})').props(
                                f'color={_battery_status_color(device.battery_status)}'
                            ).classes('text-xs px-3 py-1 rounded-full font-semibold')
                        with ui.element('div').classes('status-device-grid'):
                            _render_device_value('Serial', device.serial_number)
                            _render_device_value(
                                'Model',
                                f'{device.manufacturer} {device.product}',
                            )
                            _render_device_value('Voltage', device.battery_voltage)
                            _render_device_value('Source', device.source_type)
                            _render_device_value('Software', device.software_version)
                            _render_device_value('Hardware', device.hardware_version)

        def _refresh_model() -> None:
            model.update()
            if device_cards_container is not None:
                _render_persisted_devices(device_cards_container)

        with ui.column().classes('status-shell w-full mx-auto gap-5 px-4 py-7'):
            ui.label('Strava Sensor Status').classes(
                'text-4xl font-bold tracking-tight text-slate-900'
            )
            ui.label('Live overview of webhook, MQTT, and activity processing state.').classes(
                'text-base text-slate-600'
            )
            with ui.row().classes('w-full gap-2 flex-wrap'):
                _render_health_badge('Webhook', 'webhook_health')
                _render_health_badge('MQTT', 'mqtt_health')
                _render_health_badge('Activity', 'activity_health')
                _render_health_badge('Env', 'env_health')

            with ui.row().classes('w-full gap-4 items-stretch flex-wrap'):
                with ui.card().classes('status-card w-full lg:flex-1 lg:min-w-[320px]'):
                    ui.label('Webhook').classes('text-xl font-semibold text-slate-900')
                    _render_field('Subscription ID', 'subscription_id', monospace=True)
                    _render_field('Webhook URL', 'webhook_url', monospace=True)
                    _render_field('Last Error', 'webhook_error')
                    _render_field('Error Time', 'webhook_error_time', monospace=True)

                with ui.card().classes('status-card w-full lg:flex-1 lg:min-w-[320px]'):
                    ui.label('MQTT').classes('text-xl font-semibold text-slate-900')
                    _render_field('Connection', 'mqtt_status')
                    _render_field('Last Device', 'mqtt_last_publish_device', monospace=True)
                    _render_field('Last Publish OK', 'mqtt_last_publish_success', monospace=True)
                    _render_field('Last Publish Time', 'mqtt_last_publish_time', monospace=True)
                    with ui.row().classes('gap-2 pt-2'):
                        ui.button(on_click=_toggle_mqtt).bind_text_from(
                            model, 'mqtt_action_label'
                        ).props('color=primary').classes('font-semibold px-5')

            with ui.card().classes('status-card w-full'):
                ui.label('Last Activity').classes('text-xl font-semibold text-slate-900')
                _render_field('Activity ID', 'last_activity_id', monospace=True)
                _render_field('Activity Time', 'last_activity_time', monospace=True)
                _render_field('Last FIT Error', 'last_fit_error_message')
                _render_field('Error Time', 'last_fit_error_time', monospace=True)
                _render_field(
                    'Persisted Activity ID',
                    'last_persisted_activity_id',
                    monospace=True,
                )
                _render_field(
                    'Persisted At',
                    'last_persisted_recorded_at',
                    monospace=True,
                )
                _render_field(
                    'Device Count',
                    'last_persisted_device_count',
                    monospace=True,
                )
                ui.label('Devices').classes('status-key pt-3')
                device_cards_container = ui.column().classes('w-full gap-3')

            with ui.card().classes('status-card w-full'):
                ui.label('Manual FIT Upload').classes('text-xl font-semibold text-slate-900')
                ui.label(
                    'Upload a FIT file to run the same parse and MQTT publish flow for debugging.'
                ).classes('text-sm text-slate-600')
                fit_upload_input = (
                    ui.upload(
                        on_upload=_handle_fit_upload,
                        auto_upload=True,
                        multiple=False,
                        max_files=1,
                    )
                    .props('accept=.fit')
                    .classes('w-full max-w-[420px]')
                )

            with ui.card().classes('status-card w-full'):
                ui.label('Environment Readiness').classes('text-xl font-semibold text-slate-900')
                with ui.row().classes('w-full gap-6 flex-wrap'):
                    with ui.column().classes('flex-1 min-w-[260px] gap-1'):
                        ui.label('Strava').classes(
                            'text-xs uppercase tracking-wide font-semibold text-slate-500'
                        )
                        _render_field('Client ID', 'env_strava_client_id', monospace=True)
                        _render_field('Client Secret', 'env_strava_client_secret', monospace=True)
                        _render_field('Webhook URL', 'env_strava_webhook_url', monospace=True)
                    with ui.column().classes('flex-1 min-w-[260px] gap-1'):
                        ui.label('MQTT').classes(
                            'text-xs uppercase tracking-wide font-semibold text-slate-500'
                        )
                        _render_field('Broker URL', 'env_mqtt_broker_url', monospace=True)
                        _render_field('Username', 'env_mqtt_username', monospace=True)
                        _render_field('Password', 'env_mqtt_password', monospace=True)

        _refresh_model()
        ui.timer(5.0, _refresh_model)

    ui.run_with(app)

import logging
import typing as t
import urllib.parse

import paho.mqtt.client
import paho.mqtt.enums
import paho.mqtt.properties
import paho.mqtt.reasoncodes

_logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self):
        self.client = paho.mqtt.client.Client(paho.mqtt.enums.CallbackAPIVersion.VERSION2)

        self.client.enable_logger()

    def connect(self, broker_url: str, username: str, password: str):
        parts = urllib.parse.urlparse(broker_url)
        assert parts.scheme in ('mqtt', 'mqtts'), f'Invalid scheme: {parts.scheme}'
        assert parts.hostname, 'Hostname is required'

        self.client.username_pw_set(username, password)
        if parts.scheme == 'mqtts':
            self.client.tls_set()

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.client.connect(parts.hostname, parts.port or 1883)
        self.client.loop_start()

    def disconnect(self):
        self.client.disconnect()
        self.client.loop_stop()

    def publish(self, topic: str, payload: str):
        self.client.publish(topic, payload)

    # The callback for when the client receives a CONNACK response from the server.
    def _on_connect(
        self,
        client: paho.mqtt.client.Client,
        userdata: t.Any,
        flags: dict[str, t.Any],
        reason_code: paho.mqtt.reasoncodes.ReasonCode,
        properties: paho.mqtt.properties.Properties | None = None,
    ):
        _logger.info('Connected with result code %s', reason_code)
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe('$SYS/#')

    # The callback for when a PUBLISH message is received from the server.
    def _on_message(
        self,
        client: paho.mqtt.client.Client,
        userdata: t.Any,
        msg: paho.mqtt.client.MQTTMessage,
    ):
        pass

    @property
    def connected(self):
        return self.client.is_connected()

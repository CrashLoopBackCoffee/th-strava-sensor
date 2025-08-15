import logging
import time
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

        # Enable automatic reconnection with exponential backoff
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        self.client.enable_logger()

    def connect(self, broker_url: str, username: str, password: str):
        parts = urllib.parse.urlparse(broker_url)
        assert parts.scheme in ('mqtt', 'mqtts'), f'Invalid scheme: {parts.scheme}'
        assert parts.hostname, 'Hostname is required'

        self.client.username_pw_set(username, password)
        if parts.scheme == 'mqtts':
            self.client.tls_set()

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_socket_close = self._on_socket_close

        self.client.connect(parts.hostname, parts.port or 1883)
        self.client.loop_start()

    def disconnect(self):
        self.client.disconnect()
        self.client.loop_stop()

    def publish(self, topic: str, payload: str, retries: int = 3) -> bool:
        """Publish a message with retry logic and error handling.

        Args:
            topic: MQTT topic to publish to
            payload: Message payload
            retries: Number of retry attempts (default: 3)

        Returns:
            True if publish succeeded, False otherwise
        """
        for attempt in range(retries):
            try:
                if not self.connected:
                    _logger.warning('MQTT not connected for publish attempt %s', attempt + 1)
                    if attempt < retries - 1:
                        time.sleep(2**attempt)  # Exponential backoff
                    continue

                result = self.client.publish(topic, payload)
                if result.rc == paho.mqtt.client.MQTT_ERR_SUCCESS:
                    _logger.debug('Successfully published to topic %s', topic)
                    return True

                _logger.warning('Publish attempt %s failed with code %s', attempt + 1, result.rc)

            except Exception as e:
                _logger.warning('Publish exception on attempt %s: %s', attempt + 1, e)

            if attempt < retries - 1:
                time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s

        _logger.error('Failed to publish to %s after %s attempts', topic, retries)
        return False

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

    def _on_disconnect(
        self,
        client: paho.mqtt.client.Client,
        userdata: t.Any,
        disconnect_flags: paho.mqtt.client.DisconnectFlags,
        reason_code: paho.mqtt.reasoncodes.ReasonCode,
        properties: paho.mqtt.properties.Properties | None = None,
    ):
        _logger.warning('Disconnected with result code %s', reason_code)
        if reason_code != 0:
            _logger.warning(
                'Unexpected MQTT disconnection, automatic reconnection will be attempted'
            )

    def _on_socket_close(
        self,
        client: paho.mqtt.client.Client,
        userdata: t.Any,
        socket,
    ):
        _logger.warning('MQTT socket closed unexpectedly')

    @property
    def connected(self):
        return self.client.is_connected()

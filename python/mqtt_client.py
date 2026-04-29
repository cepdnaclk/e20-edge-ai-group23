"""
mqtt_client.py – Reusable MQTT client wrapper (paho-mqtt).

Handles:
  • Automatic reconnection with exponential back-off
  • TLS support (when port 8883 is used)
  • Thread-safe publish queue
"""

import json
import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import paho.mqtt.client as mqtt

import config

logger = logging.getLogger(__name__)


class _NumpyEncoder(json.JSONEncoder):
    """Converts numpy scalar types to native Python types for JSON serialization."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class MQTTClient:
    def __init__(
        self,
        client_id: str = "batch-reactor-edge",
        on_message_cb: Optional[Callable] = None,
    ):
        self._client_id    = client_id
        self._on_message   = on_message_cb
        self._connected    = threading.Event()
        self._lock         = threading.Lock()

        self._client = mqtt.Client(
            client_id           = client_id,
            protocol            = mqtt.MQTTv311,
            clean_session       = True,
        )

        # Credentials
        if config.MQTT_USERNAME:
            self._client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

        # TLS for port 8883
        if config.MQTT_PORT == 8883:
            self._client.tls_set()

        # Callbacks
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish    = self._on_publish
        if on_message_cb:
            self._client.on_message = on_message_cb

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✅ Connected to MQTT broker %s:%d",
                        config.MQTT_BROKER, config.MQTT_PORT)
            self._connected.set()
        else:
            logger.error("❌ Connection failed, return code %d", rc)
            self._connected.clear()

    def _on_disconnect(self, client, userdata, rc):
        logger.warning("⚠️  Disconnected from broker (rc=%d). Reconnecting…", rc)
        self._connected.clear()

    def _on_publish(self, client, userdata, mid):
        logger.debug("Message published (mid=%d)", mid)

    # ── Connection management ──────────────────────────────────────────────────

    def connect(self, timeout: int = 30) -> bool:
        """Connect with retry back-off. Returns True if connected."""
        backoff = 1
        while True:
            try:
                logger.info("Connecting to %s:%d …",
                            config.MQTT_BROKER, config.MQTT_PORT)
                self._client.connect(
                    config.MQTT_BROKER,
                    config.MQTT_PORT,
                    keepalive=60,
                )
                self._client.loop_start()
                if self._connected.wait(timeout=timeout):
                    return True
            except Exception as exc:
                logger.error("Connection error: %s. Retry in %ds", exc, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("Disconnected from MQTT broker.")

    # ── Publish ────────────────────────────────────────────────────────────────

    def publish(
        self,
        topic:   str,
        payload: dict,
        qos:     int = 1,
        retain:  bool = False,
    ) -> bool:
        if not self._connected.is_set():
            logger.warning("Not connected – skipping publish to %s", topic)
            return False

        with self._lock:
            message = json.dumps(payload, cls=_NumpyEncoder)
            result  = self._client.publish(topic, message, qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error("Publish failed: %s", mqtt.error_string(result.rc))
                return False
            logger.debug("Published to %s: %s", topic, message[:120])
            return True

    # ── Subscribe ──────────────────────────────────────────────────────────────

    def subscribe(self, topic: str, qos: int = 1):
        self._client.subscribe(topic, qos=qos)
        logger.info("Subscribed to %s", topic)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

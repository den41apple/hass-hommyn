"""Single MQTT cloud connection shared by all Hommyn entities."""
from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import uuid
from collections import defaultdict
from typing import Any, Callable

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    APP_PASSWORD,
    APP_USERNAME,
    CLIENT_ID_PREFIX,
    CLOUD_HOST,
    CLOUD_PORT,
    SIGNAL_AVAILABILITY,
    SIGNAL_STATE_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

# Connection-loss codes that indicate "broker dropped us" rather than
# normal shutdown; paho-mqtt may surface any of these depending on version.
_LOST_RC = {mqtt.MQTT_ERR_CONN_LOST, mqtt.MQTT_ERR_NO_CONN, 7}


class HommynCoordinator:
    """Owns one MQTT session to mqtt.cloud.rusklimat.ru.

    All devices share this connection. Each device's state-tree
    (`rusclimate/{type}/{token}/state/#`) is sub'd once on startup.
    State updates are fanned out to entities via the Home Assistant
    dispatcher, keyed by token.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        # token -> latest payload dict (e.g. {"temperature": "23", "mode": "1"})
        self.state: dict[str, dict[str, str]] = defaultdict(dict)
        # token -> whether the device is currently reachable
        self.available: dict[str, bool] = {}
        # Each registered device, kept so we can re-subscribe on reconnect.
        self._subscriptions: dict[str, tuple[int, str]] = {}  # token -> (devtype, vendor)
        self._client: mqtt.Client | None = None
        self._client_id = CLIENT_ID_PREFIX + uuid.uuid4().hex.lower()
        self._connect_lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._tls_ctx = self._build_tls_context()
        self._loop_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """Open the cloud session in the background."""
        if self._loop_task is not None:
            return
        self._loop_task = self.hass.async_create_background_task(
            self._runner(), name="hommyn_mqtt"
        )

    async def async_stop(self) -> None:
        """Disconnect cleanly."""
        self._stop.set()
        if self._client is not None:
            await self.hass.async_add_executor_job(self._client.disconnect)
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._loop_task = None

    def add_device(self, vendor: str, devtype: int, token: str) -> None:
        """Register a device for state mirroring.

        Safe to call before the coordinator is started — subscription will
        happen as soon as the cloud session is up.
        """
        self._subscriptions[token] = (devtype, vendor)
        if self._is_connected():
            self._subscribe(token, devtype, vendor)

    def remove_device(self, token: str) -> None:
        """Stop mirroring this device's state."""
        if token not in self._subscriptions:
            return
        devtype, vendor = self._subscriptions.pop(token)
        if self._is_connected():
            assert self._client is not None
            self._client.unsubscribe(f"{vendor}/{devtype}/{token}/state/#")
        self.state.pop(token, None)
        self.available.pop(token, None)

    def publish_control(
        self, vendor: str, devtype: int, token: str, key: str, value: str
    ) -> None:
        """Send a control command to the device (e.g. set temperature)."""
        if not self._is_connected():
            _LOGGER.warning(
                "Cloud not connected, dropping cmd %s/%s/%s/control/%s=%s",
                vendor, devtype, token, key, value,
            )
            return
        topic = f"{vendor}/{devtype}/{token}/control/{key}"
        assert self._client is not None
        self._client.publish(topic, value, qos=1, retain=False)
        _LOGGER.debug("HA -> AC %s = %s", topic, value)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected()

    @staticmethod
    def _build_tls_context() -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_default_certs()
        return ctx

    def _create_socket(self) -> ssl.SSLSocket:
        # paho calls this every reconnect; resolve hostname each time so DNS
        # changes (e.g. failover) are picked up.
        raw = socket.create_connection((CLOUD_HOST, CLOUD_PORT), timeout=15)
        return self._tls_ctx.wrap_socket(raw, server_hostname=CLOUD_HOST)

    def _subscribe(self, token: str, devtype: int, vendor: str) -> None:
        assert self._client is not None
        topic = f"{vendor}/{devtype}/{token}/state/#"
        self._client.subscribe(topic, qos=0)
        _LOGGER.debug("Subscribed: %s", topic)

    # --- paho callbacks (executor thread) --------------------------------

    def _on_connect(self, _c, _u, _f, rc: int) -> None:  # noqa: ANN001
        if rc != 0:
            _LOGGER.error("Cloud MQTT connect failed rc=%s", rc)
            return
        _LOGGER.info("Cloud MQTT connected as %s", self._client_id)
        for token, (devtype, vendor) in self._subscriptions.items():
            self._subscribe(token, devtype, vendor)

    def _on_disconnect(self, _c, _u, rc: int) -> None:  # noqa: ANN001
        if rc in _LOST_RC:
            _LOGGER.warning("Cloud MQTT lost connection rc=%s; will reconnect", rc)
        else:
            _LOGGER.debug("Cloud MQTT disconnected rc=%s", rc)
        # Mark all devices unavailable. They'll come back as soon as
        # state/error/connection arrives.
        for token in list(self._subscriptions):
            self._mark_availability(token, False)

    def _on_message(self, _c, _u, msg: mqtt.MQTTMessage) -> None:  # noqa: ANN001
        # topic: rusclimate/{type}/{token}/state/{key} or .../state/{group}/{key}
        parts = msg.topic.split("/", 4)
        if len(parts) < 5 or parts[3] != "state":
            return
        token = parts[2]
        key = parts[4]
        try:
            value = msg.payload.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            value = ""
        _LOGGER.debug(
            "AC -> HA %s = %s%s",
            msg.topic, value, " (retained)" if msg.retain else "",
        )
        self.state[token][key] = value

        # Availability handling.
        #
        # `state/error/connection` is the device's own connectivity flag,
        # published retained as an MQTT last-will: "false" = online, "true" =
        # the broker fired the LWT because the device's TCP session dropped.
        # Some firmwares (e.g. the Ballu ASP breezer, devtype 69) never
        # republish "false" after reconnecting, so a stale retained "true"
        # would latch the device offline forever even while it keeps
        # publishing live telemetry. So: treat any *live* (non-retained)
        # message as proof the device is talking right now, and never latch
        # offline on a *retained* "true".
        is_live = not msg.retain
        if key == "error/connection":
            online = value.strip().lower() == "false"
            if is_live or online:
                # Live connect/disconnect is authoritative; a retained "false"
                # is safe to trust. A retained "true" is ignored here — live
                # telemetry (below) decides reachability instead.
                self._mark_availability(token, online)
        elif is_live:
            # Any live state update proves the device is online right now.
            self._mark_availability(token, True)

        # Bounce into HA's event loop to fire dispatcher signals.
        self.hass.loop.call_soon_threadsafe(
            self._dispatch_state, token, key, value
        )

    def _mark_availability(self, token: str, ok: bool) -> None:
        prev = self.available.get(token)
        if prev == ok:
            return
        self.available[token] = ok
        self.hass.loop.call_soon_threadsafe(
            async_dispatcher_send,
            self.hass,
            SIGNAL_AVAILABILITY.format(token=token),
            ok,
        )

    @callback
    def _dispatch_state(self, token: str, key: str, value: str) -> None:
        async_dispatcher_send(
            self.hass,
            SIGNAL_STATE_UPDATE.format(token=token),
            key,
            value,
        )

    # --- background runner ---------------------------------------------

    async def _runner(self) -> None:
        backoff = 5
        while not self._stop.is_set():
            try:
                await self.hass.async_add_executor_job(self._run_once)
                backoff = 5
            except Exception as exc:  # noqa: BLE001
                _LOGGER.error("Cloud MQTT loop crashed: %s", exc)
            if self._stop.is_set():
                break
            _LOGGER.info("Reconnecting to cloud broker in %ds", backoff)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60)

    def _run_once(self) -> None:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id=self._client_id,
            clean_session=True,
        )
        client.username_pw_set(APP_USERNAME, APP_PASSWORD)
        client._create_socket = self._create_socket  # noqa: SLF001
        client.reconnect_delay_set(min_delay=5, max_delay=60)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self._client = client
        try:
            client.connect(CLOUD_HOST, CLOUD_PORT, keepalive=30)
            # loop_forever blocks until the broker drops us or .disconnect().
            client.loop_forever(retry_first_connection=False)
        finally:
            self._client = None

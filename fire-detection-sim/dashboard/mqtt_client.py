"""Subscribes to the simulated device and stores everything in SQLite.

This is the 'Cloud Service' box: heartbeat check, event detection, log storage.
"""
import json
import time
import uuid

import paho.mqtt.client as mqtt

import config
import db

_state = {"last_fire": None}


def handle_message(topic: str, payload: bytes):
    """Separate from the MQTT callbacks so it can be tested without a broker."""
    text = payload.decode("utf-8", errors="replace")

    if topic == config.TOPIC_STATUS:
        db.set_meta("device_status", text)
        db.add_event("DEVICE_" + text.upper(), "status message (LWT/online)")
        return

    if topic != config.TOPIC_TELEMETRY:
        return
    try:
        d = json.loads(text)
        epoch = float(d.get("epoch") or 0)
        buffered = int(d.get("buffered", 0))
        ts = epoch if epoch > 1_600_000_000 else time.time()
        fire = int(d["fire"])
        db.add_reading(
            ts, int(d.get("seq", 0)), int(d["smoke"]), int(d["flame"]),
            fire, int(d.get("siren", 0)), int(d.get("pump", 0)), buffered,
        )
    except (ValueError, KeyError, TypeError) as e:  # malformed message
        db.add_event("BAD_MESSAGE", f"{e}: {text[:80]}")
        return

    # Only LIVE telemetry counts as a heartbeat; buffered records are old data.
    if not buffered:
        db.set_meta("last_seen", time.time())
        db.set_meta("device_status", "online")

    prev = _state["last_fire"]
    tag = " (buffered)" if buffered else ""
    if fire and prev != 1:
        db.add_event("FIRE_DETECTED", f"smoke={d['smoke']} flame={d['flame']}{tag}", ts)
    elif not fire and prev == 1:
        db.add_event("FIRE_CLEARED", f"alarm reset{tag}", ts)
    _state["last_fire"] = fire


def start():
    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            db.set_meta("mqtt_connected", "0")
            return
        client.subscribe([(config.TOPIC_TELEMETRY, 0), (config.TOPIC_STATUS, 1)])
        db.set_meta("mqtt_connected", "1")

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        db.set_meta("mqtt_connected", "0")

    def on_message(client, userdata, msg):
        handle_message(msg.topic, msg.payload)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"fire-dashboard-{uuid.uuid4().hex[:8]}",
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(1, 10)
    client.connect_async(config.BROKER_HOST, config.BROKER_PORT, keepalive=30)
    client.loop_start()
    return client

"""Shared settings. Override with environment variables if you like.

IMPORTANT: TOPIC_BASE must be identical in wokwi/sketch.ino and here.
The public MQTT broker is shared by everyone, so pick a unique name
(e.g. add your student IDs) to avoid seeing other people's data.
"""
import os

BROKER_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_BASE = os.getenv("TOPIC_BASE", "fire-sim-CHANGE-ME/bldg1")
DB_PATH = os.getenv("DB_PATH", "fire_sim.db")

# Device is shown as "Disconnected" if no telemetry (heartbeat) for this long.
HEARTBEAT_TIMEOUT_S = int(os.getenv("HEARTBEAT_TIMEOUT_S", "8"))

TOPIC_TELEMETRY = f"{TOPIC_BASE}/telemetry"
TOPIC_STATUS = f"{TOPIC_BASE}/status"

"""Fake device for testing the dashboard WITHOUT Wokwi.

Plays: normal -> fire -> normal -> network outage (with a fire inside it,
buffered) -> reconnect + back-fill.   Run:  python tools/fake_device.py
"""
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import config  # noqa: E402

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fake-device-" + str(int(time.time())))
client.will_set(config.TOPIC_STATUS, "offline", qos=1, retain=True)
client.connect(config.BROKER_HOST, config.BROKER_PORT, 30)
client.loop_start()
client.publish(config.TOPIC_STATUS, "online", qos=1, retain=True)


def phase(t):
    """returns (smoke, flame, fire, offline) for second t"""
    if 10 <= t < 25:
        return 3400, 300, 1, False      # fire (flame sensor is active-low)
    if 35 <= t < 55:
        fire = 40 <= t < 48
        return (3300, 300, 1, True) if fire else (400, 3900, 0, True)
    return 400, 3900, 0, False


buf, seq = [], 0
for t in range(0, 70, 2):
    smoke, flame, fire, offline = phase(t)
    seq += 1
    rec = dict(epoch=int(time.time()), seq=seq, smoke=smoke, flame=flame,
               fire=fire, siren=fire, pump=fire, buffered=0)
    if offline:
        rec["buffered"] = 1
        buf.append(rec)
        print(f"[offline] buffered seq={seq}")
    else:
        for b in buf:
            client.publish(config.TOPIC_TELEMETRY, json.dumps(b))
            print(f"[flush] seq={b['seq']}")
        buf.clear()
        client.publish(config.TOPIC_TELEMETRY, json.dumps(rec))
        print(f"[live] seq={seq} smoke={smoke} fire={fire}")
    time.sleep(2)

client.publish(config.TOPIC_STATUS, "offline", qos=1, retain=True)
client.loop_stop()

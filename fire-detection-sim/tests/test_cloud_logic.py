"""Run:  python -m pytest -q   (from repo root)"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TOPIC_BASE"] = "test/bldg"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

import config, db, mqtt_client  # noqa: E402

db.init()


def msg(**kw):
    base = dict(epoch=int(time.time()), seq=1, smoke=400, flame=3900, fire=0, siren=0, pump=0, buffered=0)
    base.update(kw)
    mqtt_client.handle_message(config.TOPIC_TELEMETRY, json.dumps(base).encode())


def test_fire_event_and_clear():
    msg(fire=0)
    msg(fire=1, smoke=3300, siren=1, pump=1)
    msg(fire=0)
    kinds = [e["kind"] for e in db.events()]
    assert "FIRE_DETECTED" in kinds and "FIRE_CLEARED" in kinds


def test_buffered_does_not_count_as_heartbeat():
    db.set_meta("last_seen", 0)
    msg(buffered=1, epoch=int(time.time()) - 300)
    assert float(db.get_meta("last_seen")) == 0
    msg(buffered=0)
    assert float(db.get_meta("last_seen")) > 0


def test_bad_message_is_logged_not_crashing():
    mqtt_client.handle_message(config.TOPIC_TELEMETRY, b"not json")
    assert any(e["kind"] == "BAD_MESSAGE" for e in db.events())

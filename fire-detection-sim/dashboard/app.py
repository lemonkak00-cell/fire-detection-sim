"""Streamlit dashboard = 'Smartphone App' in the architecture (runs on the laptop)."""
import datetime as dt
import time

import pandas as pd
import streamlit as st

import config
import db
import mqtt_client

st.set_page_config(page_title="Fire Detection Simulation", page_icon="🔥", layout="wide")
db.init()


@st.cache_resource
def start_mqtt():
    return mqtt_client.start()


start_mqtt()

# ---------------- sidebar (static) ----------------
with st.sidebar:
    st.header("Settings")
    st.caption("Broker")
    st.code(f"{config.BROKER_HOST}:{config.BROKER_PORT}")
    st.caption("Topic base (must match sketch.ino)")
    st.code(config.TOPIC_BASE)
    if "CHANGE-ME" in config.TOPIC_BASE:
        st.warning("Using the default topic. Change TOPIC_BASE so you don't mix "
                   "data with other people on the public broker.")
    if st.button("Clear stored data"):
        db.clear()
        st.rerun()
    st.caption(f"Heartbeat timeout: {config.HEARTBEAT_TIMEOUT_S}s")

st.title("🔥 Building Fire Detection System (Simulation)")
st.caption("Device: ESP32 in Wokwi  →  MQTT broker  →  this dashboard on the laptop")


def fmt(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


@st.fragment(run_every=2)
def live():
    last = db.latest()
    last_seen = float(db.get_meta("last_seen", 0) or 0)
    age = time.time() - last_seen if last_seen else None
    dev_status = db.get_meta("device_status", "unknown")
    online = (age is not None) and age <= config.HEARTBEAT_TIMEOUT_S and dev_status != "offline"

    # --- Function 2: notification (toast + banner) ---
    newest = db.last_event_id("FIRE_DETECTED")
    if "seen_alert" not in st.session_state:
        st.session_state.seen_alert = newest  # don't toast old history on first load
    elif newest > st.session_state.seen_alert:
        st.toast("🔥 FIRE DETECTED!", icon="🚨")
        st.session_state.seen_alert = newest

    # --- Function 4: device health via heartbeat ---
    if online:
        st.success(f"🟢 Device ONLINE (last heartbeat {age:.0f}s ago)")
    elif last_seen:
        st.error(f"🔴 Device DISCONNECTED – no heartbeat for {age:.0f}s. "
                 "Check the real device on site. (Local siren/pump keep working.)")
    else:
        st.info("⏳ Waiting for the first message from the device…")

    if last and last["fire"] and not last["buffered"]:
        st.error("🔥🔥 FIRE DETECTED – siren and fire pump are ON")
    elif last:
        st.success("✅ No fire detected")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Smoke (ADC)", last["smoke"] if last else "–")
    c2.metric("Flame (ADC)", last["flame"] if last else "–")
    c3.metric("Siren", ("ON 🔊" if last["siren"] else "OFF") if last else "–")
    c4.metric("Fire pump", ("ON 💦" if last["pump"] else "OFF") if last else "–")

    rows = db.recent(300)
    if rows:
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["ts"], unit="s")
        st.subheader("Sensor history (Function 3: logs)")
        st.line_chart(df.set_index("time")[["smoke", "flame"]])
        n_buf = int(df["buffered"].sum())
        if n_buf:
            st.info(f"{n_buf} record(s) in this chart were back-filled from the device "
                    "buffer after a network outage.")

    st.subheader("Event log")
    ev = db.events(30)
    if ev:
        edf = pd.DataFrame(ev)
        edf["time"] = edf["ts"].map(fmt)
        st.dataframe(edf[["time", "kind", "detail"]], hide_index=True, width="stretch")
    else:
        st.caption("No events yet.")


live()

# Building Fire Detection System – Simulation (Wokwi + Python + Streamlit)

Everything runs on one laptop:

```
Wokwi (ESP32, browser)  --Wi-Fi/MQTT-->  public MQTT broker  -->  Streamlit dashboard + SQLite (laptop)
 smoke/flame sensors                       (broker.hivemq.com)      alerts, heartbeat, logs, charts
 siren (buzzer), pump (LED)
```

| Function (from worksheet W04) | Where it runs |
|---|---|
| F1 Sensors → siren + fire pump | **Device** (ESP32 sketch) – works with no network |
| F2 Fire alert to "phone" | **Cloud/dashboard** – toast + red banner |
| F3 Log history | **Cloud** (SQLite); device keeps a 120-record RAM buffer while offline and back-fills later |
| F4 Device health | **Cloud** – device sends telemetry every 2 s (heartbeat); dashboard shows *Disconnected* after 8 s of silence |

> Why ESP32 and not Arduino Uno? Uno has no Wi-Fi, so it cannot talk MQTT in Wokwi. The sketch uses the Arduino framework, so the logic is the same.
> Why a public broker? Wokwi runs in the browser and cannot reach `localhost` on your laptop without the paid Wokwi Gateway.

## 1. Run the dashboard

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# pick a UNIQUE topic (public broker!) and use the same one in wokwi/sketch.ino
set TOPIC_BASE=fire-sim-yourteam-1234/bldg1      # Windows cmd   (macOS/Linux: export ...)
streamlit run dashboard/app.py
```

No Wokwi yet? Test the dashboard with the fake device (normal → fire → outage with buffered data → back-fill):

```bash
python tools/fake_device.py
```

## 2. Set up Wokwi

1. https://wokwi.com → New Project → **ESP32**.
2. Replace the contents of `sketch.ino`, `diagram.json`, `libraries.txt` with the files in `wokwi/`.
3. In `sketch.ino` change `TOPIC_BASE` to exactly the same string as above.
4. Press ▶. Open the Serial Monitor.

Wiring (also in `diagram.json`):

| Part | ESP32 pin |
|---|---|
| Gas (smoke) sensor AOUT | D34 |
| Flame sensor AOUT | D35 |
| Buzzer (siren) | D25 |
| Blue LED via 220 Ω (pump) | D26 |
| Red LED via 220 Ω (siren indicator) | D13 |
| RESET button | D27 → GND |
| NET CUT button | D14 → GND |
| Sensors VCC / GND | 3V3 / GND |

## 3. Demo script (matches the report)

1. Dashboard shows 🟢 Online, "No fire".
2. Click the gas sensor in Wokwi and raise the slider (or lower the flame sensor value) → buzzer + pump LED turn on, dashboard turns red and toasts.
3. Press **RESET** after lowering the sensors → alarm clears.
4. Press **NET CUT** → Serial shows `NETWORK CUT`; dashboard goes 🔴 Disconnected after ~8 s. Raise smoke again: **siren and pump still work locally**.
5. Press **NET CUT** again → Serial shows buffer flushing; the dashboard chart and event log back-fill (marked *buffered*).
6. Stop the simulation → 🔴 Disconnected (LWT + missing heartbeat).

## Calibration notes

- Watch `smoke=… flame=…` in the Serial Monitor and adjust `SMOKE_THRESHOLD`, `FLAME_THRESHOLD`.
- If the Wokwi flame sensor behaves the opposite way, flip `FLAME_ACTIVE_LOW`.
- `tone()` needs ESP32 Arduino core 3.x (current Wokwi default). On old cores, swap in `ledcWriteTone`.

## Tests

```bash
pip install pytest
python -m pytest -q
```

## Publish to GitHub

```bash
git init
git add .
git commit -m "Fire detection simulation: Wokwi + Streamlit"
git branch -M main
git remote add origin https://github.com/<user>/fire-detection-sim.git
git push -u origin main
```

## Limitations

Simulation only: sensor values are entered by hand, network loss is simulated with a button, latency is not measured on real hardware. A public MQTT broker has no authentication, so do not use it for real systems. This is not a certified fire-protection system.

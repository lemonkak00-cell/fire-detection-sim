/*
 * Building Fire Detection System - SIMULATION (Wokwi, ESP32 + Arduino framework)
 *
 * Function placement (see report):
 *   F1  smoke/flame -> siren + pump ........ runs HERE on the device (works offline)
 *   F2  push alert to phone ................ cloud/dashboard (needs network)
 *   F3  log history ........................ cloud DB; device keeps a RAM buffer while offline
 *   F4  device health ...................... cloud watches the heartbeat (telemetry every 2 s)
 *
 * Buttons (simulation helpers):
 *   RESET button (GPIO27): clear the latched alarm once the danger is gone
 *   NET   button (GPIO14): toggle "network cut" to simulate Wi-Fi/Internet loss
 *
 * IMPORTANT: change TOPIC_BASE (must equal TOPIC_BASE in dashboard/config.py).
 */
#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>

// ---------------- network config ----------------
const char* WIFI_SSID  = "Wokwi-GUEST";
const char* WIFI_PASS  = "";
const char* MQTT_HOST  = "broker.hivemq.com";
const uint16_t MQTT_PORT = 1883;
const char* TOPIC_BASE = "fire-sim-CHANGE-ME/bldg1";   // <-- change me

// ---------------- pins ----------------
const int PIN_SMOKE     = 34;  // gas sensor AOUT (ADC1)
const int PIN_FLAME     = 35;  // flame sensor AOUT (ADC1)
const int PIN_SIREN     = 25;  // buzzer
const int PIN_PUMP      = 26;  // blue LED = fire pump
const int PIN_SIREN_LED = 13;  // red LED mirrors the siren
const int PIN_RESET     = 27;  // push button to GND
const int PIN_NET       = 14;  // push button to GND

// ---------------- thresholds (calibrate by watching the Serial Monitor) ----------------
const int  SMOKE_THRESHOLD = 2000;   // 0..4095, higher = more smoke
const int  FLAME_THRESHOLD = 2000;   // see FLAME_ACTIVE_LOW
const bool FLAME_ACTIVE_LOW = true;  // typical flame module: lower voltage = more flame
                                     // set to false if Wokwi's slider behaves the other way

const unsigned long SAMPLE_MS = 2000;     // telemetry / heartbeat period
const unsigned long MQTT_RETRY_MS = 5000;

// ---------------- offline ring buffer (graceful degradation) ----------------
struct Rec { uint32_t epoch; uint32_t seq; uint16_t smoke, flame; uint8_t fire, siren, pump; };
const int BUF_N = 120;                    // 120 x 2 s = 4 min  (RAM is limited: this is the trade-off)
Rec ring[BUF_N];
int ringHead = 0, ringCount = 0;

WiFiClient wifi;
PubSubClient mqtt(wifi);

bool alarmLatched = false;
bool netCut = false;
bool timeConfigured = false;
uint32_t seqNo = 0;
unsigned long lastSample = 0, lastMqttTry = 0, lastSirenToggle = 0;
bool sirenHigh = false;
bool lastFireReported = false;

String tTelemetry, tStatus;

// ---------------- helpers ----------------
uint32_t nowEpoch() {
  time_t t = time(nullptr);
  return t > 1600000000 ? (uint32_t)t : 0;   // 0 = clock not synced yet
}

bool flameDetected(int v) { return FLAME_ACTIVE_LOW ? (v < FLAME_THRESHOLD) : (v > FLAME_THRESHOLD); }

bool pressed(int pin) { return digitalRead(pin) == LOW; }

// debounced edge detection
bool buttonEdge(int pin, bool &prev) {
  bool p = pressed(pin);
  bool edge = p && !prev;
  prev = p;
  return edge;
}

void ringPush(const Rec &r) {
  int idx = (ringHead + ringCount) % BUF_N;
  ring[idx] = r;
  if (ringCount < BUF_N) ringCount++;
  else ringHead = (ringHead + 1) % BUF_N;   // overwrite oldest
}

bool publishRec(const Rec &r, bool buffered) {
  char msg[220];
  snprintf(msg, sizeof(msg),
           "{\"epoch\":%lu,\"seq\":%lu,\"smoke\":%u,\"flame\":%u,\"fire\":%u,"
           "\"siren\":%u,\"pump\":%u,\"buffered\":%u}",
           (unsigned long)r.epoch, (unsigned long)r.seq, r.smoke, r.flame,
           r.fire, r.siren, r.pump, buffered ? 1 : 0);
  return mqtt.publish(tTelemetry.c_str(), msg);
}

void flushBuffer() {
  int n = 0;
  while (ringCount > 0 && n < 10 && mqtt.connected()) {   // 10 per loop keeps device responsive
    if (!publishRec(ring[ringHead], true)) break;
    ringHead = (ringHead + 1) % BUF_N;
    ringCount--;
    n++;
    mqtt.loop();
  }
  if (n) Serial.printf("[buffer] flushed %d, %d left\n", n, ringCount);
}

void goOffline() {
  if (mqtt.connected()) mqtt.disconnect();
  WiFi.disconnect(true);
  Serial.println("[net] NETWORK CUT (simulated) - local control continues");
}

void maintainNetwork() {
  if (netCut) return;
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastTry = 0;
    if (millis() - lastTry > 8000 || lastTry == 0) {
      lastTry = millis();
      Serial.println("[net] connecting Wi-Fi...");
      WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
    }
    return;
  }
  if (!timeConfigured) {
    configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");
    timeConfigured = true;
  }
  if (!mqtt.connected() && millis() - lastMqttTry > MQTT_RETRY_MS) {
    lastMqttTry = millis();
    String cid = "fire-esp32-" + String((uint32_t)esp_random(), HEX);
    // Last Will: broker publishes "offline" if we vanish without saying goodbye
    if (mqtt.connect(cid.c_str(), nullptr, nullptr, tStatus.c_str(), 1, true, "offline")) {
      mqtt.publish(tStatus.c_str(), "online", true);
      Serial.println("[mqtt] connected");
    } else {
      Serial.printf("[mqtt] failed rc=%d\n", mqtt.state());
    }
  }
  if (mqtt.connected()) mqtt.loop();
}

// ---------------- Arduino entry points ----------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_SIREN, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT);
  pinMode(PIN_SIREN_LED, OUTPUT);
  pinMode(PIN_RESET, INPUT_PULLUP);
  pinMode(PIN_NET, INPUT_PULLUP);
  analogReadResolution(12);

  tTelemetry = String(TOPIC_BASE) + "/telemetry";
  tStatus    = String(TOPIC_BASE) + "/status";
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  WiFi.mode(WIFI_STA);
  Serial.println("Fire detection simulation started");
}

void loop() {
  static bool prevReset = false, prevNet = false;
  static unsigned long lastRead = 0;
  static int smoke = 0, flame = 4095;

  // ---- F1: local safety logic - NEVER depends on the network ----
  if (millis() - lastRead >= 100) {
    lastRead = millis();
    smoke = analogRead(PIN_SMOKE);
    flame = analogRead(PIN_FLAME);
  }
  bool fireNow = (smoke >= SMOKE_THRESHOLD) || flameDetected(flame);
  if (fireNow) alarmLatched = true;
  if (buttonEdge(PIN_RESET, prevReset) && !fireNow) {
    alarmLatched = false;
    Serial.println("[local] alarm reset");
  }

  digitalWrite(PIN_PUMP, alarmLatched);
  if (alarmLatched) {                       // two-tone siren
    if (millis() - lastSirenToggle > 400) {
      lastSirenToggle = millis();
      sirenHigh = !sirenHigh;
      tone(PIN_SIREN, sirenHigh ? 1200 : 800);
    }
  } else {
    noTone(PIN_SIREN);
  }
  digitalWrite(PIN_SIREN_LED, alarmLatched);

  // ---- simulated network cut toggle ----
  if (buttonEdge(PIN_NET, prevNet)) {
    netCut = !netCut;
    if (netCut) goOffline();
    else Serial.println("[net] network restored (simulated)");
  }

  // ---- F3/F4: telemetry = heartbeat + log, buffered when offline ----
  maintainNetwork();

  bool changed = (alarmLatched != lastFireReported);
  if (changed || millis() - lastSample >= SAMPLE_MS) {
    lastSample = millis();
    lastFireReported = alarmLatched;

    Rec r;
    r.epoch = nowEpoch();
    r.seq = ++seqNo;
    r.smoke = smoke;
    r.flame = flame;
    r.fire = alarmLatched;
    r.siren = alarmLatched;
    r.pump = alarmLatched;

    if (mqtt.connected()) {
      flushBuffer();                        // old data first, then live
      publishRec(r, false);
    } else {
      ringPush(r);
      Serial.printf("[buffer] offline, stored seq=%lu (%d in RAM)\n", (unsigned long)r.seq, ringCount);
    }
    Serial.printf("smoke=%d flame=%d alarm=%d net=%s\n", smoke, flame, alarmLatched,
                  mqtt.connected() ? "online" : "offline");
  } else if (mqtt.connected() && ringCount > 0) {
    flushBuffer();
  }
}

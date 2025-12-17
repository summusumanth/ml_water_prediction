#include "secrets.h"
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <BearSSLHelpers.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <WiFiUdp.h>
#include <NTPClient.h>
#include <ArduinoJson.h>

// -------------------- Pins --------------------
#define DHTPIN 4          // GPIO4 = D2 on NodeMCU / Wemos
#define DHTTYPE DHT11

#define FLOW_SENSOR_PIN D1
#define RAIN_DIGITAL_PIN D5
const int SOIL_SENSOR_PIN = A0;

// -------------------- Sensors --------------------
DHT dht(DHTPIN, DHTTYPE);

float calibrationFactor = 4.5;
volatile byte pulseCount = 0;
float flowRate = 0.0;
unsigned int flowMilliLitres = 0;
unsigned long totalMilliLitres = 0;
unsigned long oldTime = 0;

// -------------------- Network --------------------
WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);

WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "time.google.com", 19800); // IST +5:30

BearSSL::X509List *caCertList = nullptr;
BearSSL::X509List *clientCertList = nullptr;
BearSSL::PrivateKey *clientPrivKey = nullptr;

// -------------------- ISR --------------------
void IRAM_ATTR pulseCounter() {
  pulseCount++;
}

// -------------------- Setup --------------------
void setup() {
  Serial.begin(9600);
  delay(100);
  Serial.println("\n=== Agriculture Irrigation ESP8266 ===");

  // DHT11
  dht.begin();
  delay(2000);  // Important!

  // Other sensors
  pinMode(RAIN_DIGITAL_PIN, INPUT);
  pinMode(FLOW_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(FLOW_SENSOR_PIN), pulseCounter, RISING);
  oldTime = millis();

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());

  // Time sync
  configTime(19800, 0, "pool.ntp.org");
  Serial.print("Waiting for time");
  while (time(nullptr) < 8 * 3600 * 2) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nTime synced");

  // Load certificates
  caCertList = new BearSSL::X509List(caCert);
  clientCertList = new BearSSL::X509List(deviceCert);
  clientPrivKey = new BearSSL::PrivateKey(deviceKey);

  secureClient.setTrustAnchors(caCertList);
  secureClient.setClientRSACert(clientCertList, clientPrivKey);

  // MQTT
  mqttClient.setServer(awsEndpoint, 8883);

  Serial.println("Setup done. Starting loop...\n");
}

// -------------------- MQTT Reconnect --------------------
void reconnectMQTT() {
  if (mqttClient.connected()) return;

  // String clientId = "irregation_esp8266_" + String(ESP.getChipId(), HEX);
  String clientId = "iotconsole-6d9ecc8c-23ca-43f2-8ad3-7a3359277ee6";
  Serial.print("[MQTT] Connecting as ");
  Serial.println(clientId);

  // This is the CORRECT way with X.509 cert auth
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("[MQTT] Connected successfully!");
    // mqttClient.subscribe(subTopic);
    // Serial.println("[MQTT] Subscribed to irregation/sub");
  } else {
    Serial.print("[MQTT] Failed, rc=");
    Serial.println(mqttClient.state());
    delay(3000);
  }
}

// -------------------- Loop --------------------
void loop() {
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  static unsigned long lastPublish = 0;
  if (millis() - lastPublish < 20000) return;
  lastPublish = millis();

  // === DHT11 Read with NAN Protection ===
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("[DHT] First read failed, retrying...");
    delay(500);
    h = dht.readHumidity();
    t = dht.readTemperature();
  }

  // Fallback if still NAN
  if (isnan(h)) h = 0;
  if (isnan(t)) t = 0;

  Serial.printf("[DHT] Temp: %.1f°C  Humidity: %.1f%%\n", t, h);

  // === Flow Sensor ===
  if (millis() - oldTime > 1000) {
    detachInterrupt(digitalPinToInterrupt(FLOW_SENSOR_PIN));
    flowRate = ((float)pulseCount / calibrationFactor) * 60.0;
    unsigned long interval = millis() - oldTime;
    flowMilliLitres = (flowRate / 60.0) * (interval / 1000.0) * 1000;
    totalMilliLitres += flowMilliLitres;

    Serial.printf("[FLOW] Rate: %.3f L/min  Total: %.3f L\n",
                  flowRate, totalMilliLitres / 1000.0);

    pulseCount = 0;
    oldTime = millis();
    attachInterrupt(digitalPinToInterrupt(FLOW_SENSOR_PIN), pulseCounter, RISING);
  }

  // === Other Sensors ===
  int rawSoil = analogRead(SOIL_SENSOR_PIN);
  float moisturePct = map(rawSoil, 0, 1023, 100, 0);
  int rain = digitalRead(RAIN_DIGITAL_PIN);

  timeClient.update();
  String timeStr = timeClient.getFormattedTime();

  // === JSON Payload (STRING FORMAT LIKE BEFORE) ===
  String payload = "{";
  payload += "\"temperature\":" + String(t, 1);
  payload += ",\"humidity\":" + String(h, 1);
  payload += ",\"flowRate\":" + String(flowRate, 3);
  payload += ",\"volume_l\":" + String(totalMilliLitres / 1000.0, 3);
  payload += ",\"soil_moisture_pct\":" + String(moisturePct, 1);
  payload += ",\"rain\":" + String(rain);
  payload += ",\"time\":\"" + timeStr + "\"";
  payload += "}";

  Serial.println("[PUB] " + payload);

  if (mqttClient.connected()) {
    mqttClient.publish(pubTopic, payload.c_str());
    Serial.println("[MQTT] Published successfully!\n");
  }

  yield();
}

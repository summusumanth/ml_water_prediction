#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ---------------- WiFi Credentials ----------------
const char* SSID = "Sri";
const char* PASSWORD = "woho9303";

// ---------------- AWS IoT Core ----------------
const char* AWS_IOT_ENDPOINT = "a25qi08bvrm85c-ats.iot.ap-south-1.amazonaws.com";
const int AWS_IOT_PORT = 8883;

// Unique client ID for THIS ESP device
const char* CLIENT_ID = "esp8266-irrigation-motor";

// MQTT Topic
const char* TOPIC_SUB = "irregation/motor";

// Relay
const int RELAY_PIN = D1;

// ---------------- AWS IoT Certificates ----------------
const char AWS_ROOT_CA[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----

-----END CERTIFICATE-----
)EOF";

const char DEVICE_CERT[] PROGMEM = R"KEY(
-----BEGIN CERTIFICATE-----

-----END CERTIFICATE-----
)KEY";

const char DEVICE_PRIVATE_KEY[] PROGMEM = R"KEY(
-----BEGIN RSA PRIVATE KEY-----

-----END RSA PRIVATE KEY-----
)KEY";


// ----------------------------------------------------------------
BearSSL::X509List rootCA(AWS_ROOT_CA);
BearSSL::X509List cert(DEVICE_CERT);
BearSSL::PrivateKey key(DEVICE_PRIVATE_KEY);

WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);

bool motorState = false;

// =============================================================
// WIFI CONNECT — RUNS ONCE
// =============================================================
void connectWiFi() {
  Serial.printf("Connecting to WiFi: %s\n", SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(400);
  }

  Serial.println("\nWiFi connected!");
  Serial.println(WiFi.localIP());

  configTime(19800, 0, "pool.ntp.org", "time.nist.gov");
  delay(1500);
}

// =============================================================
// MQTT CALLBACK — handles {"motor": 0/1}
// =============================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.printf("\nMessage on %s: ", topic);

  String msg;
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.println(msg);

  StaticJsonDocument<200> doc;
  if (deserializeJson(doc, msg)) {
    Serial.println("JSON parse error!");
    return;
  }

  if (doc.containsKey("motor")) {
    int val = doc["motor"].as<int>();  // 0 or 1
    motorState = (val == 1);

    digitalWrite(RELAY_PIN, motorState ? HIGH : LOW);

    Serial.println(motorState ? "Motor ON" : "Motor OFF");
  }
}

// =============================================================
// MQTT CONNECT
// =============================================================
void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.println("Connecting to AWS IoT...");

    if (mqttClient.connect(CLIENT_ID)) {
      Serial.println("Connected!");
      mqttClient.subscribe(TOPIC_SUB, 1);
      Serial.println("Subscribed to irregation/motor");
    } else {
      Serial.print("MQTT error: ");
      Serial.println(mqttClient.state());
      delay(3000);
    }
  }
}

// =============================================================
// SETUP
// =============================================================
void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  connectWiFi();

  wifiClient.setTrustAnchors(&rootCA);
  wifiClient.setClientRSACert(&cert, &key);

  mqttClient.setServer(AWS_IOT_ENDPOINT, AWS_IOT_PORT);
  mqttClient.setCallback(mqttCallback);

  connectMQTT();
}

// =============================================================
// MAIN LOOP
// =============================================================
void loop() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();
}

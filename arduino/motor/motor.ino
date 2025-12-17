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
MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF
ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UEChMGQW1hem9uMRkwFwYDVQQDExBBbWF6
b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoTBkFtYXpvbjEZMBcGA1UEAxMQQW1hem9uIFJv
b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj
ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM
9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw
IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6
VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L
93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm
jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA
A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI
U5PMCCjjmCXPI6T53iHTfIUJrU6adTrCC2qJeHZERxhlbI1Bjjt/msv0tadQ1wUs
N+gDS63pYaACbvXy8MWy7Vu33PqUXHeeE6V/Uq2V8viTO96LXFvKWlJbYK8U90vv
o/ufQJVtMVT8QtPHRh8jrdkPSHCa2XV4cdFyQzR1bldZwgJcJmApzyMZFo6IQ6XU
5MsI+yMRQ+hDKXJioaldXgjUkK642M4UwtBV8ob2xJNDd2ZhwLnoQdeXeGADbkpy
rqXRfboQnoZsG4q5WTP468SQvvG5
-----END CERTIFICATE-----
)EOF";

const char DEVICE_CERT[] PROGMEM = R"KEY(
-----BEGIN CERTIFICATE-----
MIIDWTCCAkGgAwIBAgIUWGSbqJaDtiKgBZ7miYYaCXsCKBUwDQYJKoZIhvcNAQEL
BQAwTTFLMEkGA1UECwxCQW1hem9uIFdlYiBTZXJ2aWNlcyBPPUFtYXpvbi5jb20g
SW5jLiBMPVNlYXR0bGUgU1Q9V2FzaGluZ3RvbiBDPVVTMB4XDTI1MTIxMzA2NDU1
OVoXDTQ5MTIzMTIzNTk1OVowHjEcMBoGA1UEAwwTQVdTIElvVCBDZXJ0aWZpY2F0
ZTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAK4rC3SVem8fqerVfh5t
nVnmh15wn6MDTqwalp/LLed6gEtNmyDspll5/KYDW4vJ9uPllDweHRVTJwLKQsYr
R3jXWVUqMOuTKo9ClSOWYSmDNtaqYa/6GORbU/ETGaQQwxEvytiMeuWYvxTh4ngV
cLew75NFQ5RcmrhW5BU9RpMF9yFPdvogzUiWwrTFheFB0rmkuTPGXL3RMsGet6cU
hCMAi6Hoj6X8YYYX73K0zuEIfsWYeD66wDGwRhdPjf0TqP3I0Kl3CwK+jCA5mP0w
06LpCEU20xlnk0pakubLmrizUF9pZUtmyRSvzLDIqv3CkT6HbNz9U1UAqnOGSFAY
guMCAwEAAaNgMF4wHwYDVR0jBBgwFoAUz8NREXVXFNGbepgGSxTeSHaOah4wHQYD
VR0OBBYEFA+Ecb+uDlJs7FK4bsOKYUrhIXiUMAwGA1UdEwEB/wQCMAAwDgYDVR0P
AQH/BAQDAgeAMA0GCSqGSIb3DQEBCwUAA4IBAQDl263+W9ZF0uMacul9Ys8wOQh6
I+u0t1Rz0RsQAERFlztTf7qCblrkkaq01wwlaPLv2gPXc0Lm5yCORHMvpKBNH2pj
Ycb88vUQ+z7rAnRnblXvyxeQPae114oDHimcUD79uxhITZQUsHmGsMYPhCyagNmD
8w0Ka35gKj/zbXjOahPQd9s9jBhAtGGIhj/KQTigI+Odyj02OZE651e4H3hDhheO
5tq//zCBzPV0AxMvlpzpuOe1nRCMVnyMjhGxz8YTmOQMfrxv95U9RKxNBZPWflZ8
f/fgbG42ejv52olcq3JncdKOn5JdpSNxIBQGIpPrhDCPY7E4CGMSodfW2Kfi
-----END CERTIFICATE-----
)KEY";

const char DEVICE_PRIVATE_KEY[] PROGMEM = R"KEY(
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEArisLdJV6bx+p6tV+Hm2dWeaHXnCfowNOrBqWn8st53qAS02b
IOymWXn8pgNbi8n24+WUPB4dFVMnAspCxitHeNdZVSow65Mqj0KVI5ZhKYM21qph
r/oY5FtT8RMZpBDDES/K2Ix65Zi/FOHieBVwt7Dvk0VDlFyauFbkFT1GkwX3IU92
+iDNSJbCtMWF4UHSuaS5M8ZcvdEywZ63pxSEIwCLoeiPpfxhhhfvcrTO4Qh+xZh4
PrrAMbBGF0+N/ROo/cjQqXcLAr6MIDmY/TDToukIRTbTGWeTSlqS5suauLNQX2ll
S2bJFK/MsMiq/cKRPods3P1TVQCqc4ZIUBiC4wIDAQABAoIBACOuKdCedtChGfxD
9GxjZGLweTb9t5Z7rPhREh52T1cmn3XN1kPudz3JYdrYwT5oB640cCPIv4iI2msV
6IwUfbXh2Ck8VX1NTuC+cTMzMYCBoxBjI1Qb1lGh7BZtJUmZLX0t305xqRO0MSEk
DXMwYUEgfFQdUnToa8Hr+xnmzbh8n85iBUi8+eSJGlmmlVWjkZrLsf7LjwwVNt8j
iwop7pg3y44N4/whm8zpYDl3QqdPsJCXn2wlzAooz+CrTzaxiJxaEXSz2lpgwBpF
llQv9EQhAbIgrQasZAlnKicPuwr8woM2emI4LIU5apw6R1mkFpmMVQWuNJ8lGeXj
CHD1JZECgYEA2hCL1tfHP2Is5RN35Ja82WgS/tcoKK2n/wiy9xz5e1vpvVh9ir1b
X5IKci/EY8sazc0PzDRiCwhvZn5dcZYdtNRvi3dhU20j/4hckkVsFYoD6CEiia4t
4zXCPTmJcO3HhnIr1Xs57JuKZfgg26EYh9CLkyskpjKKHkUb8gKEpD0CgYEAzHeU
Tm9DWQQjy4BpwT5zmUmwTBDtt7//C3HxnxnHlJ2hAuC1w1DvkSPjv3xhVWoCcGco
6jRsnExIf+09ULkqXU1CR1EGhO/PW2EvCwgJh4ZHq20jhM6xQ/jFkjsVqGMVU8j+
TbZFXi6EZgqqt2BpggTxPOvwz1qkIxnEQMuLlZ8CgYB5bM9BYcP8ImHXaSDQs7MS
6GXza8Fb7V7nn2NwQL0XGNYt7jFx6QERVZPlg327B+S0BmSuk9ioRhkqHGFSF4IR
KF24blBOkS6DYt4RQQDveXu1bYX63neE1nGDgB9tN6przfVkmYpmmzHUl/dL9Qdg
0Rp3Z4Wv2eKY+miWORq9DQKBgQC7G66u/CiQXDZ5csDUY1cb7pATe+ZeIae+jH4F
D21RNdJzNLmAzB7/He27fJIBvOoQfIa3lFPT0AcEclCK/3eiPCIr6xzhKCcEQ3Hu
UWOPDrWlTVGUpiUXw57hS4ptNob8zlDRQrxGDKGCU76X4vWKUwWDr5IF3reXm2u5
s8q/lwKBgA0HapdnZFg06S+FKfoz6YaI7uyGRIbfBmxbQK+dmiT0wiMJDaWOyfF6
QJ2eauMFhNZYDQ0KbMBuxAHwykhwcZOropP8Y4Q32yN6qUtPOWedoYLow0C5KdPW
pvMUq5cH1ZH2L6cYIaw6DAAthsimb//bAua2vKzGwz0GSehR5+Da
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

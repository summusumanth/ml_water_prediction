import json
import logging
import ssl
import time
from pathlib import Path
import threading

import paho.mqtt.client as mqtt
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ml_predit import MaizeETCPredictor
from openweather import WeatherETcCalculator

app = FastAPI()

maize_predictor = MaizeETCPredictor()
weather_calculator = WeatherETcCalculator()

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
_LOGGER = logging.getLogger(__name__)

# ---------- CONFIG ----------
AWS_IOT_ENDPOINT = "a25qi08bvrm85c-ats.iot.ap-south-1.amazonaws.com"

# Sensor subscriber client (receives data from Arduino)
SENSOR_CLIENT_ID = "iotconsole-bc2ee19b-6a70-4846-9ae7-487339ff8ff0"
SENSOR_TOPIC = "irregation/pub"

# Motor publisher client (sends commands to Arduino)
MOTOR_CLIENT_ID = "python-backend-irrigation-api"
MOTOR_TOPIC = "irregation/motor"

PORT = 8883
# ----------------------------

latest_water_flow = None
latest_soil_moisture = None


# ========= MQTT CALLBACKS =========

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        _LOGGER.info("Connected to AWS IoT (rc=%s)", rc)
        # Subscribe to sensor data from Arduino
        client.subscribe(SENSOR_TOPIC, qos=1)
        _LOGGER.info("Subscribed to SENSOR_TOPIC: %s", SENSOR_TOPIC)
    else:
        _LOGGER.error("Connection failed with rc=%s", rc)


def on_disconnect(client, userdata, rc):
    _LOGGER.warning("Disconnected (rc=%s)", rc)


def on_message(client, userdata, msg):
    global latest_water_flow, latest_soil_moisture

    try:
        payload = msg.payload.decode("utf-8")
        payload_json = json.loads(payload)
    except Exception as e:
        _LOGGER.warning("Failed to decode message: %s", e)
        return

    _LOGGER.info("Message on topic %s: %s", msg.topic, payload)

    if msg.topic == SENSOR_TOPIC:
        latest_water_flow = payload_json.get("volume_l", 0) / 1000  # Convert to L
        latest_soil_moisture = payload_json.get("soil_moisture_pct", 0)

        _LOGGER.info(
            "Sensor data received → water_flow=%.3f L, soil_moisture=%.1f%%",
            latest_water_flow, latest_soil_moisture
        )


# ========= CREATE MQTT CLIENTS =========

# Certificate paths for sensor subscriber
SENSOR_ROOT_CA = Path(r"certs\AmazonRootCA1.pem")
SENSOR_CERTFILE = Path(r"certs\d39f84316d274e1542308607ff0891ce8d323cff9fd5a6720e990f69c1512a82-certificate.pem.crt")
SENSOR_KEYFILE = Path(r"certs\d39f84316d274e1542308607ff0891ce8d323cff9fd5a6720e990f69c1512a82-private.pem.key")

# Certificate paths for motor publisher
MOTOR_ROOT_CA = Path(r"motor_certs\AmazonRootCA1.pem")
MOTOR_CERTFILE = Path(r"motor_certs\4dd7563f753ce07f741656e55880b94d90ced655465f78c7a639506dbabc0640-certificate.pem.crt")
MOTOR_KEYFILE = Path(r"motor_certs\4dd7563f753ce07f741656e55880b94d90ced655465f78c7a639506dbabc0640-private.pem.key")


def create_mqtt_client(client_id, root_ca, certfile, keyfile, client_type="sensor"):
    """Create and configure MQTT client with TLS."""
    client = mqtt.Client(client_id=client_id, clean_session=True)

    if client_type == "sensor":
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
    else:
        # Motor publisher doesn't need message callback
        client.on_connect = lambda c, u, f, rc: _LOGGER.info("Motor publisher connected (rc=%s)", rc)
        client.on_disconnect = lambda c, u, rc: _LOGGER.warning("Motor publisher disconnected (rc=%s)", rc)

    # Verify certificate files exist
    if not (root_ca.exists() and certfile.exists() and keyfile.exists()):
        _LOGGER.error("Certificate files not found for %s client!", client_type)
        _LOGGER.error("  ROOT_CA: %s (exists: %s)", root_ca, root_ca.exists())
        _LOGGER.error("  CERTFILE: %s (exists: %s)", certfile, certfile.exists())
        _LOGGER.error("  KEYFILE: %s (exists: %s)", keyfile, keyfile.exists())
        raise SystemExit(1)

    tls_version = getattr(ssl, "PROTOCOL_TLS_CLIENT", ssl.PROTOCOL_TLSv1_2)

    try:
        client.tls_set(
            ca_certs=str(root_ca),
            certfile=str(certfile),
            keyfile=str(keyfile),
            tls_version=tls_version,
            cert_reqs=ssl.CERT_REQUIRED
        )
        _LOGGER.info("TLS configured successfully for %s client", client_type)
    except Exception as e:
        _LOGGER.error("TLS configuration failed for %s client: %s", client_type, e)
        raise

    client.tls_insecure_set(False)
    return client


# Create both clients
sensor_client = create_mqtt_client(SENSOR_CLIENT_ID, SENSOR_ROOT_CA, SENSOR_CERTFILE, SENSOR_KEYFILE, "sensor")
motor_client = create_mqtt_client(MOTOR_CLIENT_ID, MOTOR_ROOT_CA, MOTOR_CERTFILE, MOTOR_KEYFILE, "motor")


sensor_loop_started = False
motor_loop_started = False

_LOGGER.info("Python Backend Configuration:")
_LOGGER.info("  AWS Endpoint: %s", AWS_IOT_ENDPOINT)
_LOGGER.info("  Sensor Client ID: %s", SENSOR_CLIENT_ID)
_LOGGER.info("  Motor Client ID: %s", MOTOR_CLIENT_ID)
_LOGGER.info("  Sensor Topic (Subscribe): %s", SENSOR_TOPIC)
_LOGGER.info("  Motor Topic (Publish): %s", MOTOR_TOPIC)


def mqtt_sensor_loop():
    """Continuous MQTT connection loop for sensor subscriber with automatic reconnection."""
    global sensor_loop_started
    attempt = 0
    max_backoff = 30
    
    # Start the network loop once
    if not sensor_loop_started:
        sensor_client.loop_start()
        sensor_loop_started = True
    
    while True:
        if not sensor_client.is_connected():
            try:
                _LOGGER.info("Attempting sensor client connect (attempt=%d)", attempt + 1)
                sensor_client.connect(AWS_IOT_ENDPOINT, PORT, keepalive=60)
                attempt = 0
            except Exception as e:
                _LOGGER.warning("Sensor connect failed: %s", e)
                wait_seconds = min(1 << attempt if attempt < 6 else max_backoff, max_backoff)
                _LOGGER.info("Waiting %d seconds before retry...", wait_seconds)
                time.sleep(wait_seconds)
                attempt += 1
                continue
        
        time.sleep(1)


def mqtt_motor_loop():
    """Continuous MQTT connection loop for motor publisher with automatic reconnection."""
    global motor_loop_started
    attempt = 0
    max_backoff = 30
    
    # Start the network loop once
    if not motor_loop_started:
        motor_client.loop_start()
        motor_loop_started = True
    
    while True:
        if not motor_client.is_connected():
            try:
                _LOGGER.info("Attempting motor client connect (attempt=%d)", attempt + 1)
                motor_client.connect(AWS_IOT_ENDPOINT, PORT, keepalive=60)
                attempt = 0
            except Exception as e:
                _LOGGER.warning("Motor connect failed: %s", e)
                wait_seconds = min(1 << attempt if attempt < 6 else max_backoff, max_backoff)
                _LOGGER.info("Waiting %d seconds before retry...", wait_seconds)
                time.sleep(wait_seconds)
                attempt += 1
                continue
        
        time.sleep(1)


mqtt_thread = threading.Thread(target=mqtt_sensor_loop, daemon=True)
mqtt_thread.start()

mqtt_motor_thread = threading.Thread(target=mqtt_motor_loop, daemon=True)
mqtt_motor_thread.start()


# ========= FASTAPI ROUTE =========

@app.get("/status")
def get_status():
    """Check MQTT connection status and sensor data."""
    return JSONResponse(
        content={
            "sensor_client_connected": sensor_client.is_connected(),
            "motor_client_connected": motor_client.is_connected(),
            "latest_water_flow": latest_water_flow,
            "latest_soil_moisture": latest_soil_moisture
        }
    )


@app.get("/awsData")
def get_latest_payload(das: int):
    """Calculate ETC and publish motor control command."""

    # 1. Weather
    weather_data = weather_calculator.get_weather_data()

    pred_input = {
        "min_temp": weather_data["min_temp"],
        "max_temp": weather_data["max_temp"],
        "humidity": round(weather_data["humidity"], 2),
        "wind": round(weather_data["wind"], 2),
        "sun_hours": round(weather_data["sun_hours"],2),
        "radiation": weather_data["radiation"]
    }

    # 2. ML & FAO predictions
    pred_etc = maize_predictor.predict_etc(pred_input, das)
    calc_etc = weather_calculator.calculate_etc(das)

    # 3. MQTT sensor values
    wf = round(latest_water_flow,2) if latest_water_flow is not None else 0
    sm = latest_soil_moisture if latest_soil_moisture is not None else 0

    # 4. Motor rule
    threshold = min(pred_etc["etc"], calc_etc["etc"])
    motor_status = not (wf > threshold or sm > 15)

    # 5. Publish command
    if motor_client and motor_client.is_connected():
        try:
            payload = json.dumps({"motor": motor_status})
            result = motor_client.publish(MOTOR_TOPIC, payload, qos=1)
            _LOGGER.info("Published to %s: %s (result=%s)", MOTOR_TOPIC, payload, result.rc)
        except Exception as e:
            _LOGGER.error("Failed to publish motor command: %s", e)
    else:
        _LOGGER.warning("Motor client not connected - cannot publish motor command")

    # 6. FINAL RESPONSE (Old structure + new structure + new params)
    return JSONResponse(
        content={
            "status": "success",

            # NEW debug parameters (keep these)
            "sensor_client_connected": sensor_client.is_connected(),
            "motor_client_connected": motor_client.is_connected(),

            # OLD structure restored
            "data": {
                "pred_etc_dict": {
                    **pred_input,
                    "etc": pred_etc["etc"],
                    "water_flow": wf,
                    "soil_moisture": sm
                },
                "calc_etc_dict": {
                    **calc_etc,
                    "water_flow": wf,
                    "soil_moisture": sm
                }
            },

            # NEW structure also preserved
            "sensor_data": {
                "water_flow": wf,
                "soil_moisture": sm
            },
            "predicted_etc": pred_etc["etc"],
            "calculated_etc": calc_etc["etc"],
            "threshold": threshold,

            # Motor result
            "motor": motor_status
        }
    )



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

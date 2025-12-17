import requests
import json
from datetime import datetime
import math


class WeatherETcCalculator:
    def __init__(self):
        self.api_key = "36d15ab85147a133c827677a60d9ce4b"
        self.lat = 13.936811
        self.lon = 7.270029
        self.altitude = 545

    # ---------------------------------------------------
    # 1. Fetch today's weather data
    # ---------------------------------------------------
    def fetch_today_weather(self):
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={self.lat}&lon={self.lon}&appid={self.api_key}&units=metric"

        response = requests.get(url)
        data = response.json()

        today = datetime.utcnow().date()

        temps_min, temps_max = [], []
        humidities, winds, clouds = [], [], []

        for entry in data["list"]:
            dt = datetime.utcfromtimestamp(entry["dt"]).date()
            if dt == today:
                temps_min.append(entry["main"]["temp_min"])
                temps_max.append(entry["main"]["temp_max"])
                humidities.append(entry["main"]["humidity"])
                winds.append(entry["wind"]["speed"])
                clouds.append(entry["clouds"]["all"])

        if not temps_min:
            raise ValueError("No weather data for today.")

        # Aggregate values
        min_temp = min(temps_min)
        max_temp = max(temps_max)
        humidity = sum(humidities) / len(humidities)
        wind = sum(winds) / len(winds)
        avg_clouds = sum(clouds) / len(clouds)

        return min_temp, max_temp, humidity, wind, avg_clouds

    # ---------------------------------------------------
    # 2. Compute radiation, sun hours
    # ---------------------------------------------------
    def compute_radiation(self, clouds):
        # sun hours estimate
        sun_hours = 12 * (1 - clouds / 100)

        # solar radiation (FAO clear-sky)
        phi = math.radians(self.lat)
        day_of_year = datetime.utcnow().timetuple().tm_yday

        dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
        delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
        ws = math.acos(-math.tan(phi) * math.tan(delta))

        Ra = (24 * 60 / math.pi) * 0.0820 * dr * (
            ws * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.sin(ws)
        )

        radiation = (0.25 + 0.50 * (1 - clouds / 100)) * Ra

        return sun_hours, radiation


    def get_weather_data(self):
        min_temp, max_temp, humidity, wind, clouds = self.fetch_today_weather()
        sun_hours, radiation = self.compute_radiation(clouds)
        return {
            "min_temp": min_temp,
            "max_temp": max_temp,
            "humidity": humidity,
            "wind": wind,
            "sun_hours": sun_hours,
            "radiation": radiation
        }

    # ---------------------------------------------------
    # 3. FAO-56 Penman–Monteith ETo
    # ---------------------------------------------------
    @staticmethod
    def saturation_vapor_pressure(T):
        return 0.6108 * math.exp((17.27 * T) / (T + 237.3))

    def compute_eto(self, min_temp, max_temp, humidity, wind, sun_hours, radiation):
        T = (min_temp + max_temp) / 2

        es_min = self.saturation_vapor_pressure(min_temp)
        es_max = self.saturation_vapor_pressure(max_temp)
        es = (es_min + es_max) / 2
        ea = (humidity / 100) * es
        vpd = es - ea
        delta = (4098 * es) / ((T + 237.3) ** 2)

        pressure = 101.3 * ((293 - 0.0065 * self.altitude) / 293) ** 5.26
        gamma = 0.000665 * pressure

        albedo = 0.23
        Rns = (1 - albedo) * radiation

        sigma = 4.903e-9
        Tmax_K = max_temp + 273.16
        Tmin_K = min_temp + 273.16

        Rnl = sigma * ((Tmax_K ** 4 + Tmin_K ** 4) / 2) * \
              (0.34 - 0.14 * math.sqrt(ea)) * \
              (1.35 - 0.35 * (sun_hours / 12))

        Rn = Rns - Rnl
        G = 0

        ETo = (
            0.408 * delta * (Rn - G)
            + gamma * (900 / (T + 273)) * wind * vpd
        ) / (delta + gamma * (1 + 0.34 * wind))

        return ETo

    # ---------------------------------------------------
    # 4. Maize Kc from DAS
    # ---------------------------------------------------
    @staticmethod
    def get_maize_kc(das):
        if das < 0:
            return 0.3

        if 0 <= das < 25:
            kc_start, kc_end = 0.30, 0.40
            d0, d1 = 0, 25
        elif 25 <= das < 55:
            kc_start, kc_end = 0.40, 0.80
            d0, d1 = 25, 55
        elif 55 <= das < 95:
            kc_start, kc_end = 1.15, 1.20
            d0, d1 = 55, 95
        elif 95 <= das <= 120:
            kc_start, kc_end = 0.70, 0.35
            d0, d1 = 95, 120
        else:
            return 0.35

        return kc_start + (kc_end - kc_start) * ((das - d0) / (d1 - d0))

    # ---------------------------------------------------
    # 5. Main function: compute today’s ETc
    # ---------------------------------------------------
    def calculate_etc(self, das):
        min_temp, max_temp, humidity, wind, clouds = self.fetch_today_weather()
        sun_hours, radiation = self.compute_radiation(clouds)
        eto = self.compute_eto(min_temp, max_temp, humidity, wind, sun_hours, radiation)
        kc = self.get_maize_kc(das)
        etc = eto * kc

        return {
            "min_temp": round(min_temp, 2),
            "max_temp": round(max_temp, 2),
            "humidity": round(humidity, 2),
            "wind": round(wind, 2),
            "sun_hours": round(sun_hours, 2),
            "radiation": round(radiation, 2),
            "eto": round(eto, 4),
            "kc": round(kc, 3),
            "etc": round(etc, 4)
        }


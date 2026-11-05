"""Project settings: which cities to track and which air-quality fields to request."""

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    name: str
    province: str
    latitude: float
    longitude: float


# Major cities across every province/region. Coordinates are city centres.
CITIES: dict[str, City] = {
    # Punjab
    "lahore": City("Lahore", "Punjab", 31.5497, 74.3436),
    "faisalabad": City("Faisalabad", "Punjab", 31.4504, 73.1350),
    "rawalpindi": City("Rawalpindi", "Punjab", 33.5651, 73.0169),
    "gujranwala": City("Gujranwala", "Punjab", 32.1877, 74.1945),
    "multan": City("Multan", "Punjab", 30.1575, 71.5249),
    "sialkot": City("Sialkot", "Punjab", 32.4945, 74.5229),
    "sargodha": City("Sargodha", "Punjab", 32.0740, 72.6861),
    "bahawalpur": City("Bahawalpur", "Punjab", 29.3956, 71.6836),
    "sheikhupura": City("Sheikhupura", "Punjab", 31.7167, 73.9850),
    "kasur": City("Kasur", "Punjab", 31.1167, 74.4500),
    # Sindh
    "karachi": City("Karachi", "Sindh", 24.8607, 67.0011),
    "hyderabad": City("Hyderabad", "Sindh", 25.3960, 68.3578),
    "sukkur": City("Sukkur", "Sindh", 27.7052, 68.8574),
    # Khyber Pakhtunkhwa
    "peshawar": City("Peshawar", "Khyber Pakhtunkhwa", 34.0151, 71.5249),
    "abbottabad": City("Abbottabad", "Khyber Pakhtunkhwa", 34.1688, 73.2215),
    # Balochistan
    "quetta": City("Quetta", "Balochistan", 30.1798, 66.9750),
    # Federal capital
    "islamabad": City("Islamabad", "Islamabad Capital Territory", 33.6844, 73.0479),
    # Gilgit-Baltistan & Azad Kashmir
    "gilgit": City("Gilgit", "Gilgit-Baltistan", 35.9208, 74.3089),
    "muzaffarabad": City("Muzaffarabad", "Azad Kashmir", 34.3700, 73.4711),
}

# Hourly fields we ask Open-Meteo for (names must match their docs exactly).
HOURLY_FIELDS = ["pm2_5", "pm10", "us_aqi", "nitrogen_dioxide", "carbon_monoxide"]

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEZONE = "Asia/Karachi"

# Be polite: identify the project, batch cities, and wait between requests.
USER_AGENT = "SmogTrackerPK/0.2 (portfolio project)"
BATCH_SIZE = 10            # cities per API request (Open-Meteo accepts comma-separated coordinates)
REQUEST_DELAY_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

DATA_FILE = "data/air_quality.csv"             # model estimates (Open-Meteo)
STATIONS_LATEST_FILE = "data/stations_latest.csv"   # measured, ground stations (OpenAQ)
STATIONS_HISTORY_FILE = "data/stations_history.csv"
CHART_DIR = "charts"

# Data credit required by Open-Meteo's terms (non-commercial use).
ATTRIBUTION = "Data: CAMS ENSEMBLE via Open-Meteo.com"
STATION_ATTRIBUTION = "Measured data: OpenAQ.org (ground monitoring stations)"

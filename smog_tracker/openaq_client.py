"""Real, measured PM2.5 from ground monitoring stations in Pakistan via the OpenAQ API (v3).

Get a free API key at https://explore.openaq.org (Account → API Key), then set it:
    Windows (PowerShell):  $env:OPENAQ_API_KEY="your-key"
    Mac/Linux:             export OPENAQ_API_KEY="your-key"
"""

import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests

from smog_tracker import config
from smog_tracker.aqi import pm25_to_us_aqi

log = logging.getLogger(__name__)

BASE_URL = "https://api.openaq.org/v3"
MAX_AGE_HOURS = 6           # ignore stations whose latest reading is older than this
CITY_RADIUS_KM = 35         # a station counts towards a city if it is this close to the centre
REQUEST_DELAY_SECONDS = 1.2  # free tier allows ~60 requests/minute
MAX_STATIONS_PER_CITY = 3   # keeps total requests low (rate limits)
TIME_BUDGET_SECONDS = 90    # never let station fetching block the app for longer than this
MAX_RATE_LIMIT_WAIT = 15   # seconds; give up quickly instead of blocking the page
OPENAQ_RETRIES = 2


class OpenAQError(Exception):
    pass


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_city(lat: float, lon: float):
    """Return (City, distance_km) for the closest tracked city."""
    city = min(config.CITIES.values(), key=lambda c: haversine_km(lat, lon, c.latitude, c.longitude))
    return city, haversine_km(lat, lon, city.latitude, city.longitude)


def select_stations(stations: list[dict], now: datetime,
                    per_city: int = MAX_STATIONS_PER_CITY) -> list[dict]:
    """Keep stations that reported recently and sit near a tracked city; best few per city."""
    picked: dict[str, list[dict]] = {}
    for st in stations:
        last = st.get("last_utc")
        if not last:
            continue
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if now - last_dt > timedelta(hours=MAX_AGE_HOURS):
            continue  # offline station: don't waste a request on it
        city, dist = nearest_city(st["lat"], st["lon"])
        if dist > CITY_RADIUS_KM:
            continue
        st = {**st, "_city": city.name, "_last": last_dt}
        picked.setdefault(city.name, []).append(st)

    result = []
    for city_stations in picked.values():
        # reference monitors first, then the most recently updated
        city_stations.sort(key=lambda x: (not x["is_monitor"], -x["_last"].timestamp()))
        result.extend(city_stations[:per_city])
    log.info("Selected %d fresh stations near tracked cities (of %d total)", len(result), len(stations))
    return result


class OpenAQClient:
    def __init__(self, api_key: str | None = None, session: requests.Session | None = None):
        self.api_key = api_key or os.getenv("OPENAQ_API_KEY")
        if not self.api_key:
            raise OpenAQError("No OpenAQ API key. Set the OPENAQ_API_KEY environment variable.")
        self.session = session or requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key, "User-Agent": config.USER_AGENT})

    def _get(self, path: str, params: dict | None = None) -> dict:
        for attempt in range(1, OPENAQ_RETRIES + 1):
            try:
                r = self.session.get(f"{BASE_URL}{path}", params=params,
                                     timeout=config.REQUEST_TIMEOUT_SECONDS)
                if r.status_code == 401:
                    raise OpenAQError("API key rejected (HTTP 401) — check OPENAQ_API_KEY")
                if r.status_code == 429:
                    wait = min(int(r.headers.get("x-ratelimit-reset", 30) or 30), MAX_RATE_LIMIT_WAIT)
                    log.warning("Rate limited (attempt %d), waiting %ss", attempt, wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except OpenAQError:
                raise
            except (requests.RequestException, ValueError) as exc:
                log.warning("OpenAQ attempt %d failed: %s", attempt, exc)
                time.sleep(2 ** attempt)
        raise OpenAQError(f"OpenAQ request failed after {OPENAQ_RETRIES} attempts: {path}")

    def list_pm25_stations(self) -> list[dict]:
        """Fresh PM2.5 stations near the tracked cities (at most a few per city)."""
        return select_stations(self._all_pm25_stations(), datetime.now(timezone.utc))

    def _all_pm25_stations(self) -> list[dict]:
        """All stationary locations in Pakistan that have a PM2.5 sensor."""
        stations, page = [], 1
        while True:
            data = self._get("/locations", {"iso": "PK", "limit": 1000, "page": page})
            results = data.get("results", [])
            for loc in results:
                pm25 = next((s for s in loc.get("sensors", [])
                             if (s.get("parameter") or {}).get("name") == "pm25"), None)
                coords = loc.get("coordinates") or {}
                if pm25 and coords.get("latitude") is not None and not loc.get("isMobile"):
                    stations.append({
                        "location_id": loc["id"],
                        "station": loc.get("name") or f"Station {loc['id']}",
                        "locality": loc.get("locality"),
                        "pm25_sensor_id": pm25["id"],
                        "lat": coords["latitude"],
                        "lon": coords["longitude"],
                        "is_monitor": bool(loc.get("isMonitor")),
                        "provider": (loc.get("provider") or {}).get("name"),
                        "last_utc": ((loc.get("datetimeLast") or {}).get("utc")),
                    })
            if len(results) < 1000:
                break
            page += 1
        log.info("Found %d PM2.5 stations in Pakistan", len(stations))
        return stations

    def latest_readings(self, stations: list[dict],
                        time_budget: float = TIME_BUDGET_SECONDS) -> list[dict]:
        """Latest PM2.5 value for each station, converted to US AQI. Skips stale stations.

        Stops early when the time budget runs out, so the dashboard never hangs.
        """
        now = datetime.now(timezone.utc)
        started = time.monotonic()
        rows = []
        for st in stations:
            if time.monotonic() - started > time_budget:
                log.warning("Time budget reached; using %d stations collected so far", len(rows))
                break
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                data = self._get(f"/locations/{st['location_id']}/latest")
            except OpenAQError as exc:
                log.warning("Skipping %s: %s", st["station"], exc)
                continue
            reading = next((r for r in data.get("results", [])
                            if r.get("sensorsId") == st["pm25_sensor_id"]), None)
            row = self.to_row(st, reading, now)
            if row:
                rows.append(row)
        log.info("Got fresh readings from %d of %d stations", len(rows), len(stations))
        return rows

    @staticmethod
    def to_row(station: dict, reading: dict | None, now: datetime) -> dict | None:
        if not reading or reading.get("value") is None or reading["value"] < 0:
            return None
        utc = datetime.fromisoformat(reading["datetime"]["utc"].replace("Z", "+00:00"))
        if now - utc > timedelta(hours=MAX_AGE_HOURS):
            return None  # stale: station offline
        city, dist = nearest_city(station["lat"], station["lon"])
        pkt = utc.astimezone(timezone(timedelta(hours=5)))
        return {
            "station": station["station"],
            "city": city.name if dist <= CITY_RADIUS_KM else None,
            "province": city.province if dist <= CITY_RADIUS_KM else None,
            "lat": station["lat"],
            "lon": station["lon"],
            "time": pkt.strftime("%Y-%m-%dT%H:%M"),
            "pm2_5": round(reading["value"], 1),
            "us_aqi": pm25_to_us_aqi(reading["value"]),
            "is_monitor": station["is_monitor"],
            "provider": station["provider"],
        }

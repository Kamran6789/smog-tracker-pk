"""Small client for the Open-Meteo Air Quality API with batching, retries and error handling."""

import logging
import time

import requests

from smog_tracker import config
from smog_tracker.config import City

log = logging.getLogger(__name__)


class AirQualityAPIError(Exception):
    """Raised when the API keeps failing or returns something unexpected."""


class AirQualityClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})

    def fetch_cities(self, cities: list[City], past_days: int = 1,
                     forecast_days: int = 1) -> list[dict]:
        """Fetch hourly readings for many cities, a batch at a time (one request per batch)."""
        rows: list[dict] = []
        for start in range(0, len(cities), config.BATCH_SIZE):
            batch = cities[start:start + config.BATCH_SIZE]
            try:
                rows.extend(self._fetch_batch(batch, past_days, forecast_days))
                log.info("Fetched %s", ", ".join(c.name for c in batch))
            except AirQualityAPIError as exc:
                log.error("Batch failed (%s): %s", ", ".join(c.name for c in batch), exc)
            time.sleep(config.REQUEST_DELAY_SECONDS)
        return rows

    def fetch_city(self, city: City, past_days: int = 1, forecast_days: int = 1) -> list[dict]:
        """Convenience wrapper for a single city."""
        return self._fetch_batch([city], past_days, forecast_days)

    def _fetch_batch(self, cities: list[City], past_days: int, forecast_days: int) -> list[dict]:
        params = {
            "latitude": ",".join(str(c.latitude) for c in cities),
            "longitude": ",".join(str(c.longitude) for c in cities),
            "hourly": ",".join(config.HOURLY_FIELDS),
            "timezone": config.TIMEZONE,
            "past_days": past_days,
            "forecast_days": forecast_days,
        }
        payload = self._get_with_retries(params)

        # One location -> the API returns a dict; several -> a list in the same order we sent.
        payloads = payload if isinstance(payload, list) else [payload]
        if len(payloads) != len(cities):
            raise AirQualityAPIError(
                f"Expected {len(cities)} locations in response, got {len(payloads)}")

        rows: list[dict] = []
        for city, city_payload in zip(cities, payloads):
            rows.extend(self._to_rows(city, city_payload))
        return rows

    def _get_with_retries(self, params: dict) -> dict | list:
        last_error: Exception | None = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    config.API_URL, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
                )
                if response.status_code == 429:
                    raise AirQualityAPIError("Rate limited (HTTP 429)")
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and data.get("error"):
                    raise AirQualityAPIError(data.get("reason", "Unknown API error"))
                return data
            except (requests.RequestException, ValueError, AirQualityAPIError) as exc:
                last_error = exc
                wait = 2 ** attempt  # 2s, 4s, 8s
                log.warning("Attempt %d/%d failed: %s (retrying in %ss)",
                            attempt, config.MAX_RETRIES, exc, wait)
                time.sleep(wait)
        raise AirQualityAPIError(f"Giving up after {config.MAX_RETRIES} attempts: {last_error}")

    @staticmethod
    def _to_rows(city: City, payload: dict) -> list[dict]:
        hourly = payload.get("hourly")
        if not hourly or "time" not in hourly:
            raise AirQualityAPIError(f"Response for {city.name} has no 'hourly' data")

        rows = []
        for i, timestamp in enumerate(hourly["time"]):
            row = {"city": city.name, "province": city.province, "time": timestamp}
            for field in config.HOURLY_FIELDS:
                values = hourly.get(field, [])
                row[field] = values[i] if i < len(values) else None
            rows.append(row)
        return rows

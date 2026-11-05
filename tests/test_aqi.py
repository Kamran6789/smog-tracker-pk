import math
from unittest.mock import MagicMock

import pandas as pd
import pytest

from smog_tracker import config
from smog_tracker.analysis import latest_observed
from smog_tracker.aqi import aqi_advice, aqi_category, aqi_colour
from smog_tracker.client import AirQualityAPIError, AirQualityClient
from smog_tracker.config import City

LAHORE = City("Lahore", "Punjab", 31.5, 74.3)


@pytest.mark.parametrize("aqi, expected", [
    (0, "Good"), (50, "Good"), (51, "Moderate"), (150, "Unhealthy for Sensitive Groups"),
    (175, "Unhealthy"), (250, "Very Unhealthy"), (450, "Hazardous"),
    (None, "Unknown"), (math.nan, "Unknown"),
])
def test_aqi_category(aqi, expected):
    assert aqi_category(aqi) == expected


def test_colour_and_advice_exist_for_every_level():
    for value in (10, 80, 120, 180, 260, 400):
        assert aqi_colour(value).startswith("#")
        assert len(aqi_advice(value)) > 10


def test_negative_aqi_raises():
    with pytest.raises(ValueError):
        aqi_category(-5)


def test_all_cities_have_province_and_valid_coordinates():
    assert len(config.CITIES) >= 15
    for city in config.CITIES.values():
        assert city.province
        assert 23 < city.latitude < 37 and 60 < city.longitude < 78  # inside Pakistan's box


def test_to_rows_parses_hourly_payload():
    payload = {"hourly": {"time": ["2026-11-05T00:00", "2026-11-05T01:00"],
                          "pm2_5": [180.0, 210.5], "us_aqi": [230, 260]}}
    rows = AirQualityClient._to_rows(LAHORE, payload)
    assert len(rows) == 2
    assert rows[1]["province"] == "Punjab"
    assert rows[1]["pm2_5"] == 210.5
    assert rows[0]["pm10"] is None  # missing field -> None, no crash


def test_to_rows_rejects_empty_payload():
    with pytest.raises(AirQualityAPIError):
        AirQualityClient._to_rows(LAHORE, {})


def test_batch_request_maps_list_response_to_cities(monkeypatch):
    monkeypatch.setattr(config, "REQUEST_DELAY_SECONDS", 0)
    karachi = City("Karachi", "Sindh", 24.8, 67.0)
    one_hour = {"hourly": {"time": ["2026-11-05T00:00"], "us_aqi": [300]}}
    other = {"hourly": {"time": ["2026-11-05T00:00"], "us_aqi": [120]}}
    response = MagicMock(status_code=200)
    response.json.return_value = [one_hour, other]  # API returns a list for multiple coordinates
    client = AirQualityClient()
    client.session.get = MagicMock(return_value=response)

    rows = client.fetch_cities([LAHORE, karachi])

    assert [(r["city"], r["us_aqi"]) for r in rows] == [("Lahore", 300), ("Karachi", 120)]
    params = client.session.get.call_args.kwargs["params"]
    assert params["latitude"] == "31.5,24.8"  # one request for both cities


def test_latest_observed_ignores_future_forecast_hours():
    df = pd.DataFrame({
        "city": ["Lahore", "Lahore", "Karachi"],
        "time": ["2026-11-05T10:00", "2026-11-05T20:00", "2026-11-05T10:00"],
        "us_aqi": [250, 999, 120],
    })
    latest = latest_observed(df, now=pd.Timestamp("2026-11-05T12:00"))
    assert latest.iloc[0]["city"] == "Lahore" and latest.iloc[0]["us_aqi"] == 250


# ---- measured data (OpenAQ) ----
from datetime import datetime, timezone

from smog_tracker.analysis import combine_latest
from smog_tracker.aqi import pm25_to_us_aqi
from smog_tracker.openaq_client import OpenAQClient


@pytest.mark.parametrize("pm25, aqi", [
    (0, 0), (9.0, 50), (35.4, 100), (55.4, 150), (125.4, 200), (225.4, 300), (500, 500), (None, None),
])
def test_pm25_to_us_aqi_breakpoints(pm25, aqi):
    assert pm25_to_us_aqi(pm25) == aqi


def test_openaq_row_maps_station_to_city_and_skips_stale():
    station = {"station": "Lahore US Consulate", "lat": 31.56, "lon": 74.36,
               "is_monitor": True, "provider": "AirNow", "pm25_sensor_id": 7}
    now = datetime(2026, 11, 5, 7, 0, tzinfo=timezone.utc)
    fresh = {"value": 180.0, "datetime": {"utc": "2026-11-05T06:00:00Z"}, "sensorsId": 7}
    row = OpenAQClient.to_row(station, fresh, now)
    assert row["city"] == "Lahore" and row["time"] == "2026-11-05T11:00"  # converted to PKT
    assert row["us_aqi"] == pm25_to_us_aqi(180.0)
    stale = {"value": 90.0, "datetime": {"utc": "2026-11-04T06:00:00Z"}, "sensorsId": 7}
    assert OpenAQClient.to_row(station, stale, now) is None


def test_combine_prefers_measured_over_model():
    model = pd.DataFrame({"city": ["Lahore", "Quetta"], "us_aqi": [250, 80], "pm2_5": [150, 20],
                          "time": ["2026-11-05T11:00"] * 2})
    stations = pd.DataFrame({"station": ["A", "B"], "city": ["Lahore", "Lahore"],
                             "us_aqi": [300, 320], "pm2_5": [250.0, 270.0],
                             "time": ["2026-11-05T11:00"] * 2})
    out = combine_latest(model, stations).set_index("city")
    assert out.loc["Lahore", "us_aqi"] == 310 and out.loc["Lahore", "source"].startswith("Measured")
    assert out.loc["Quetta", "source"] == "Model estimate"

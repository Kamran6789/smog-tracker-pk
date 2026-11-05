"""Small helpers that turn raw hourly rows into insights (used by the CLI, charts and dashboard)."""

import pandas as pd


def latest_observed(df: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Latest reading per city at or before `now` (ignores future forecast hours)."""
    if df.empty:
        return df
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    now = now or pd.Timestamp.now(tz="Asia/Karachi").tz_localize(None)
    past = df[df["time"] <= now]
    if past.empty:  # e.g. sample data from another week -> fall back to whatever exists
        past = df
    idx = past.groupby("city")["time"].idxmax()
    return past.loc[idx].sort_values("us_aqi", ascending=False).reset_index(drop=True)


def daily_average(df: pd.DataFrame) -> pd.DataFrame:
    """Average AQI per city per day — good for weekly trend posts."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["time"]).dt.date
    return (df.groupby(["city", "date"])["us_aqi"].mean().round(0)
              .reset_index().rename(columns={"us_aqi": "avg_aqi"}))


def combine_latest(model_latest: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """Per city: use the median of real station readings when available, else the model value.

    Adds a `source` column so the UI can always show where each number comes from.
    """
    out = model_latest.copy()
    out["source"] = "Model estimate"
    out["stations"] = 0
    if stations is None or stations.empty:
        return out

    measured = (stations.dropna(subset=["city", "us_aqi"])
                        .groupby("city")
                        .agg(us_aqi=("us_aqi", "median"), pm2_5=("pm2_5", "median"),
                             stations=("station", "count"), time=("time", "max")))
    for city, m in measured.iterrows():
        mask = out["city"] == city
        if mask.any():
            out.loc[mask, ["us_aqi", "pm2_5", "stations", "time"]] = [
                round(m.us_aqi), round(m.pm2_5, 1), int(m.stations), m.time]
            out.loc[mask, "source"] = f"Measured · {int(m.stations)} station{'s' * (m.stations > 1)}"
    return out.sort_values("us_aqi", ascending=False).reset_index(drop=True)

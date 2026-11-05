"""Save readings to a CSV file without creating duplicate rows."""

import logging
from pathlib import Path

import pandas as pd

from smog_tracker.aqi import aqi_category

log = logging.getLogger(__name__)


def save_readings(rows: list[dict], path: str) -> pd.DataFrame:
    """Merge new rows into the CSV. Newer values replace older ones for the same city+hour."""
    if not rows:
        log.warning("No rows to save")
        return load_readings(path)

    new = pd.DataFrame(rows)
    new["aqi_category"] = new["us_aqi"].apply(aqi_category)

    file = Path(path)
    if file.exists():
        old = pd.read_csv(file)
        combined = pd.concat([old, new], ignore_index=True)
    else:
        file.parent.mkdir(parents=True, exist_ok=True)
        combined = new

    # Forecast hours get updated on later runs, so keep the latest value per city+time.
    combined = (combined.drop_duplicates(subset=["city", "time"], keep="last")
                        .sort_values(["city", "time"]))
    combined.to_csv(file, index=False)
    log.info("Saved %d rows (%d total) to %s", len(new), len(combined), file)
    return combined


def load_readings(path: str) -> pd.DataFrame:
    file = Path(path)
    if not file.exists():
        return pd.DataFrame()
    df = pd.read_csv(file)
    df["time"] = pd.to_datetime(df["time"])
    return df


def save_station_readings(rows: list[dict], latest_path: str, history_path: str) -> pd.DataFrame:
    """Overwrite the 'latest' snapshot and append to a de-duplicated history file."""
    if not rows:
        log.warning("No station readings to save")
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["aqi_category"] = df["us_aqi"].apply(aqi_category)
    Path(latest_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(latest_path, index=False)

    hist = Path(history_path)
    if hist.exists():
        df_all = pd.concat([pd.read_csv(hist), df], ignore_index=True)
    else:
        df_all = df
    df_all.drop_duplicates(subset=["station", "time"], keep="last").to_csv(hist, index=False)
    log.info("Saved %d station readings", len(df))
    return df


def load_station_readings(path: str) -> pd.DataFrame:
    file = Path(path)
    return pd.read_csv(file) if file.exists() else pd.DataFrame()

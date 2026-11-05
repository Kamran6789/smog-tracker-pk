"""LinkedIn-ready PNG charts: a city ranking and an AQI trend, both on a dark theme."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no screen needed
import matplotlib.pyplot as plt
import pandas as pd

from smog_tracker import config
from smog_tracker.analysis import latest_observed
from smog_tracker.aqi import AQI_BANDS, aqi_category, aqi_colour

BG = "#0f1117"
PANEL = "#161a23"
TEXT = "#e6e6e6"
MUTED = "#8b93a7"


def _style(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.xaxis.label.set_color(MUTED)


def _save(fig, out_file: str) -> str:
    fig.text(0.99, 0.015, config.ATTRIBUTION, ha="right", fontsize=8, color=MUTED)
    fig.text(0.01, 0.015, "Smog Tracker PK", ha="left", fontsize=8, color=MUTED, weight="bold")
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_file


def plot_city_ranking(df: pd.DataFrame, out_file: str) -> str:
    """Horizontal bar chart of the latest AQI per city, coloured by EPA category."""
    latest = latest_observed(df)
    if latest.empty:
        raise ValueError("No data to plot yet — run a fetch first")
    latest = latest.sort_values("us_aqi")  # worst at the top of a horizontal bar chart

    fig, ax = plt.subplots(figsize=(12, 0.42 * len(latest) + 2.2))
    _style(ax, fig)
    colours = [aqi_colour(v) for v in latest["us_aqi"]]
    bars = ax.barh(latest["city"], latest["us_aqi"], color=colours, height=0.65)

    for bar, value in zip(bars, latest["us_aqi"]):
        ax.text(bar.get_width() + 4, bar.get_y() + bar.get_height() / 2,
                f"{value:.0f}  {aqi_category(value)}", va="center", fontsize=9, color=TEXT)

    stamp = pd.to_datetime(latest["time"]).max().strftime("%d %b %Y, %I:%M %p")
    ax.set_title(f"Pakistan air quality ranking  ·  {stamp}", color=TEXT,
                 fontsize=15, weight="bold", loc="left", pad=14)
    ax.set_xlabel("US AQI (higher = worse)")
    ax.tick_params(axis="y", colors=TEXT, labelsize=10)
    ax.set_xlim(0, latest["us_aqi"].max() * 1.35)
    ax.grid(axis="x", color="#2a2f3a", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, out_file)


def plot_aqi(df: pd.DataFrame, cities: list[str], out_file: str, days: int = 3) -> str:
    """Hourly US AQI trend for a few cities over the last `days` days, with EPA colour bands."""
    if df.empty:
        raise ValueError("No data to plot yet — run a fetch first")

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    cutoff = df["time"].max() - pd.Timedelta(days=days)
    recent = df[(df["time"] >= cutoff) & (df["city"].isin(cities))]
    if recent.empty:
        raise ValueError(f"No data for {cities} in the last {days} days")

    fig, ax = plt.subplots(figsize=(12, 6.3))  # close to LinkedIn's 1.91:1 image ratio
    _style(ax, fig)

    top = max(320, recent["us_aqi"].max() * 1.1)
    lower = 0
    for upper, label, colour, _advice in AQI_BANDS:
        if lower >= top:
            break
        ax.axhspan(lower, min(upper, top), color=colour, alpha=0.10, lw=0)
        ax.text(recent["time"].max(), (lower + min(upper, top)) / 2, f"{label} ",
                va="center", ha="right", fontsize=8, color=colour, alpha=0.9)
        lower = upper

    palette = ["#4cc9f0", "#f72585", "#ffd166", "#06d6a0", "#b8b8ff", "#ff9f1c"]
    for colour, city in zip(palette, cities):
        city_data = recent[recent["city"] == city]
        if not city_data.empty:
            ax.plot(city_data["time"], city_data["us_aqi"], label=city, linewidth=2.2, color=colour)

    ax.set_ylim(0, top)
    ax.set_title(f"Air quality trend (US AQI) · last {days} days", color=TEXT,
                 fontsize=15, weight="bold", loc="left", pad=14)
    ax.set_ylabel("US AQI (higher = worse)")
    legend = ax.legend(loc="upper left", frameon=False)
    for text in legend.get_texts():
        text.set_color(TEXT)
    ax.grid(color="#2a2f3a", linewidth=0.6)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, out_file)

"""Turn a US AQI number into a category, colour and plain-English health advice (US EPA scale)."""

# (upper bound, label, hex colour, short advice) — standard US EPA AQI bands.
AQI_BANDS = [
    (50, "Good", "#2ecc71", "Air is clean. Enjoy outdoor activities."),
    (100, "Moderate", "#f1c40f", "Acceptable. Very sensitive people should limit long outdoor effort."),
    (150, "Unhealthy for Sensitive Groups", "#e67e22",
     "Children, elderly and people with asthma should reduce time outdoors."),
    (200, "Unhealthy", "#e74c3c", "Everyone should limit outdoor activity. Wear a mask outside."),
    (300, "Very Unhealthy", "#8e44ad", "Avoid outdoor activity. Keep windows closed, use a purifier."),
    (float("inf"), "Hazardous", "#7b1e3a", "Health emergency. Stay indoors and avoid all outdoor effort."),
]


def _band(aqi: float | None):
    if aqi is None or aqi != aqi:  # second check catches NaN
        return None
    if aqi < 0:
        raise ValueError(f"AQI cannot be negative: {aqi}")
    for band in AQI_BANDS:
        if aqi <= band[0]:
            return band
    return AQI_BANDS[-1]


def aqi_category(aqi: float | None) -> str:
    """Return the EPA category name for an AQI value, or 'Unknown' if missing."""
    band = _band(aqi)
    return band[1] if band else "Unknown"


def aqi_colour(aqi: float | None) -> str:
    band = _band(aqi)
    return band[2] if band else "#7f8c8d"


def aqi_advice(aqi: float | None) -> str:
    band = _band(aqi)
    return band[3] if band else "No data."


# US EPA PM2.5 breakpoints (2024 revision): (conc_low, conc_high, aqi_low, aqi_high)
PM25_BREAKPOINTS = [
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
]


def pm25_to_us_aqi(pm25: float | None) -> float | None:
    """Convert a PM2.5 concentration (µg/m³) to US AQI using the EPA linear formula.

    Note: official AQI uses a 24-hour (NowCast) average; applying it to one hourly
    reading gives an hourly estimate, which is how most live trackers show it.
    """
    if pm25 is None or pm25 != pm25 or pm25 < 0:
        return None
    c = int(pm25 * 10) / 10  # EPA truncates to one decimal
    for c_lo, c_hi, i_lo, i_hi in PM25_BREAKPOINTS:
        if c <= c_hi:
            c_lo_eff = c_lo if c >= c_lo else c  # handles gaps like 9.05
            return round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo_eff) + i_lo)
    return 500.0  # beyond the scale -> cap at 500

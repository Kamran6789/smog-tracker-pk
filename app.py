"""Smog Tracker PK — interactive dashboard.

Run:  streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from smog_tracker import config
from smog_tracker.analysis import combine_latest, latest_observed
from smog_tracker.aqi import AQI_BANDS, aqi_advice, aqi_category, aqi_colour
from smog_tracker.client import AirQualityClient
from smog_tracker.openaq_client import OpenAQClient, OpenAQError
from smog_tracker.storage import (load_readings, load_station_readings, save_readings,
                                  save_station_readings)

st.set_page_config(page_title="Smog Tracker PK", page_icon="🌫️", layout="wide")

try:  # phones get a wider map view, shorter charts and no chart toolbars
    IS_MOBILE = "mobi" in st.context.headers.get("User-Agent", "").lower()
except Exception:
    IS_MOBILE = False
MAP_ZOOM = 3.7 if IS_MOBILE else 4.3
MAP_HEIGHT = 420 if IS_MOBILE else 520
CHART_CONFIG = {"displayModeBar": False}

# ---------- styling ----------
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
.hero {background: linear-gradient(135deg, #1b1f2b 0%, #10131b 100%);
       border: 1px solid #262b38; border-radius: 18px; padding: 26px 30px; margin-bottom: 18px;}
.hero h1 {font-size: 2.1rem; margin: 0; letter-spacing: -0.5px;}
.hero p {color: #8b93a7; margin: 6px 0 0 0;}
.card {background: #161a23; border: 1px solid #262b38; border-radius: 16px;
       padding: 18px 20px; height: 100%;}
.card .label {color: #8b93a7; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 1px;}
.card .value {font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin-top: 6px;}
.card .sub {color: #c9cede; font-size: 0.95rem; margin-top: 4px;}
.pill {display: inline-block; white-space: nowrap; padding: 3px 12px; border-radius: 999px; font-size: 0.8rem;
       font-weight: 700; color: #0f1117; margin-top: 8px; font-size: 0.74rem;}
.advice {background: #161a23; border-left: 4px solid; border-radius: 10px;
         padding: 12px 16px; margin-top: 10px; color: #dfe3ee;}
.hero, .card, .advice {animation: fadeUp 0.7s ease both;}
.card {transition: transform 0.25s ease, box-shadow 0.25s ease;}
.card:hover {transform: translateY(-4px); box-shadow: 0 10px 30px rgba(247,37,133,0.15);}
@keyframes fadeUp {from {opacity: 0; transform: translateY(14px);} to {opacity: 1; transform: none;}}
.live-dot {display:inline-block; width:10px; height:10px; border-radius:50%; background:#f72585;
           margin-right:8px; animation: pulse 1.6s infinite;}
@keyframes pulse {0% {box-shadow: 0 0 0 0 rgba(247,37,133,0.7);} 70% {box-shadow: 0 0 0 12px rgba(247,37,133,0);}
                  100% {box-shadow: 0 0 0 0 rgba(247,37,133,0);}}
.footer {color: #6b7286; font-size: 0.8rem; margin-top: 28px; text-align: center;}
.kpis {display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;}
.kpis .card:nth-child(2) {animation-delay: 0.1s;}
.kpis .card:nth-child(3) {animation-delay: 0.2s;}
.kpis .card:nth-child(4) {animation-delay: 0.3s;}
@media (max-width: 900px) {.kpis {grid-template-columns: repeat(2, 1fr);}}
@media (max-width: 640px) {
  .block-container {padding: 1rem 0.8rem 2rem 0.8rem;}
  .hero {padding: 16px 16px; border-radius: 14px;}
  .hero h1 {font-size: 1.45rem;}
  .hero p {font-size: 0.85rem;}
  .kpis {gap: 10px;}
  .card {padding: 12px 12px; border-radius: 12px;}
  .card .label {font-size: 0.66rem; letter-spacing: 0.5px;}
  .card .value {font-size: 1.8rem;}
  .card .sub {font-size: 0.78rem;}
  .pill {font-size: 0.66rem; padding: 2px 9px;}
  .advice {font-size: 0.88rem;}
  h4 {font-size: 1.1rem !important;}
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600)
def load() -> pd.DataFrame:
    return load_readings(config.DATA_FILE)


@st.cache_data(ttl=600)
def load_stations() -> pd.DataFrame:
    return load_station_readings(config.STATIONS_LATEST_FILE)

def refresh_all() -> str:
    """Fetch model data for all cities + measured station data (if an OpenAQ key is set)."""
    rows = AirQualityClient().fetch_cities(list(config.CITIES.values()), past_days=3)
    save_readings(rows, config.DATA_FILE)
    msg = f"{len(rows)} model readings"
    try:
        oaq = OpenAQClient()
        readings = oaq.latest_readings(oaq.list_pm25_stations())
        save_station_readings(readings, config.STATIONS_LATEST_FILE, config.STATIONS_HISTORY_FILE)
        msg += f" + {len(readings)} live station readings"
    except OpenAQError as exc:
        msg += f" (stations skipped: {exc})"
    load.clear()
    load_stations.clear()
    return msg



def card(label: str, value: str, sub: str = "", colour: str = "#e6e6e6", pill: str = "") -> str:
    pill_html = (f'<div class="pill" style="background:{colour}">{pill}</div>' if pill else "")
    return (f'<div class="card"><div class="label">{label}</div>'
            f'<div class="value" style="color:{colour}">{value}</div>'
            f'<div class="sub">{sub}</div>{pill_html}</div>')


# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### 🌫️ Smog Tracker PK")
    if st.button("🔄 Refresh live data", width="stretch"):
        with st.spinner("Fetching model data and live station readings…"):
            st.success("Updated: " + refresh_all())

df = load()
if df.empty:
    # First visit on a fresh server (e.g. Streamlit Cloud after a restart): fetch automatically.
    with st.spinner("Loading live air-quality data for Pakistan… (first load takes ~1 minute)"):
        refresh_all()
    df = load()
if df.empty:
    st.markdown('<div class="hero"><h1>🌫️ Smog Tracker PK</h1>'
                '<p>No data yet. Click <b>Refresh live data</b> in the sidebar, '
                'or run <code>python main.py --past-days 3</code>.</p></div>', unsafe_allow_html=True)
    st.stop()

with st.sidebar:
    provinces = sorted(df["province"].dropna().unique()) if "province" in df else []
    region = st.selectbox("Region", ["All Pakistan"] + provinces)
    days = st.slider("Trend window (days)", 1, 7, 3)

if region != "All Pakistan":
    df = df[df["province"] == region]

stations_df = load_stations()
if region != "All Pakistan" and not stations_df.empty:
    stations_df = stations_df[stations_df["province"] == region]
latest = combine_latest(latest_observed(df), stations_df)
if latest.empty:
    st.warning("No readings for the selected provinces.")
    st.stop()

worst, best = latest.iloc[0], latest.iloc[-1]
updated = pd.to_datetime(latest["time"]).max().strftime("%d %b %Y · %I:%M %p")
unhealthy = int((latest["us_aqi"] > 150).sum())
n_measured = int(latest["source"].str.startswith("Measured").sum())

# ---------- hero + KPI cards ----------
st.markdown(f'<div class="hero"><h1><span class="live-dot"></span>Pakistan Air Quality, Live</h1>'
            f'<p>Hourly US AQI for {len(latest)} cities · last updated {updated} (PKT) · '
            f'<b style="color:#06d6a0">{n_measured} measured by ground stations</b>, '
            f'{len(latest) - n_measured} model estimates</p></div>',
            unsafe_allow_html=True)

avg = latest["us_aqi"].mean()
st.markdown('<div class="kpis">'
            + card("Worst right now", f"{worst.us_aqi:.0f}", f"{worst.city} · {worst.source}",
                   aqi_colour(worst.us_aqi), aqi_category(worst.us_aqi))
            + card("National average", f"{avg:.0f}", "across tracked cities",
                   aqi_colour(avg), aqi_category(avg))
            + card("Cities unhealthy+", f"{unhealthy}/{len(latest)}", "AQI above 150",
                   "#e74c3c" if unhealthy else "#2ecc71")
            + card("Cleanest air", f"{best.us_aqi:.0f}", f"{best.city} · {best.source}",
                   aqi_colour(best.us_aqi), aqi_category(best.us_aqi))
            + '</div>', unsafe_allow_html=True)

st.markdown(f'<div class="advice" style="border-color:{aqi_colour(worst.us_aqi)}">'
            f'<b>Advice for {worst.city}:</b> {aqi_advice(worst.us_aqi)}</div>',
            unsafe_allow_html=True)
st.write("")

# ---------- map + ranking ----------
latest["colour"] = latest["us_aqi"].apply(aqi_colour)
latest["category"] = latest["us_aqi"].apply(aqi_category)
coords = {c.name: (c.latitude, c.longitude) for c in config.CITIES.values()}
latest["lat"] = latest["city"].map(lambda n: coords[n][0])
latest["lon"] = latest["city"].map(lambda n: coords[n][1])

left, right = st.columns([3, 2])
with left:
    tab3d, tabmap, tabplay = st.tabs(["🌫️ Smog view", "🗺️ Map", "⏯️ Animate last 48h"])

    with tab3d:
        st.caption("Smog haze over Pakistan · drag to move · two-finger drag to tilt · tap a city"
                   if IS_MOBILE else "Smog haze over Pakistan · drag to move · right-click/two-finger drag to tilt · hover a city")
        latest["label"] = latest["city"]
        latest["rgb"] = latest["colour"].apply(lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)])
        latest["radius"] = latest["us_aqi"].clip(lower=20) * 180  # bigger glow = worse air
        smog = pdk.Layer(
            "HeatmapLayer", data=latest, get_position="[lon, lat]", get_weight="us_aqi",
            radius_pixels=60 if IS_MOBILE else 90, intensity=1.2, threshold=0.05, opacity=0.55,
            color_range=[[46, 204, 113], [241, 196, 15], [230, 126, 34],
                         [231, 76, 60], [142, 68, 173], [123, 30, 58]],
        )
        dots = pdk.Layer(
            "ScatterplotLayer", data=latest, get_position="[lon, lat]", get_radius="radius",
            get_fill_color="rgb", opacity=0.35, stroked=True, get_line_color="rgb",
            line_width_min_pixels=2, pickable=True, auto_highlight=True,
        )
        major = {"Lahore", "Karachi", "Islamabad", "Peshawar", "Quetta", "Multan", "Gilgit"}
        labels = pdk.Layer(
            "TextLayer", data=latest[latest["city"].isin(major)], get_position="[lon, lat]", get_text="city", get_size=14, font_weight="bold",
            get_color=[230, 230, 230], get_alignment_baseline="'top'", get_pixel_offset=[0, 12],
        )
        layers = [smog, dots, labels]
        if not stations_df.empty:
            st_pts = stations_df.dropna(subset=["us_aqi"]).copy()
            st_pts["label"] = st_pts["station"]
            st_pts["source"] = "Measured station · PM2.5 " + st_pts["pm2_5"].astype(str) + " µg/m³"
            layers.append(pdk.Layer(
                "ScatterplotLayer", data=st_pts, get_position="[lon, lat]", get_radius=4500,
                get_fill_color=[6, 214, 160, 230], pickable=True, stroked=True,
                get_line_color=[255, 255, 255], line_width_min_pixels=1,
            ))
            st.caption(f"🟢 Green dots = {len(st_pts)} real monitoring stations reporting right now")
        view = (pdk.ViewState(latitude=30.0, longitude=69.6, zoom=3.9, pitch=30, bearing=0) if IS_MOBILE
                else pdk.ViewState(latitude=29.8, longitude=70.0, zoom=4.7, pitch=45, bearing=-15))
        st.pydeck_chart(pdk.Deck(
            layers=layers, initial_view_state=view, map_style="dark",
            tooltip={"html": "<b>{label}</b><br/>AQI {us_aqi}<br/>{source}",
                     "style": {"background": "#161a23", "color": "#e6e6e6"}},
        ), height=MAP_HEIGHT)

    with tabmap:
        fig_map = px.scatter_map(
            latest, lat="lat", lon="lon", size="us_aqi", size_max=38, color="category",
            color_discrete_map={b[1]: b[2] for b in AQI_BANDS}, hover_name="city",
            hover_data={"us_aqi": ":.0f", "pm2_5": ":.0f", "lat": False, "lon": False, "category": True},
            zoom=MAP_ZOOM, center={"lat": 30.2, "lon": 69.8}, map_style="carto-darkmatter", height=MAP_HEIGHT,
        )
        fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                              legend=dict(title="", bgcolor="rgba(15,17,23,0.7)", font=dict(color="#e6e6e6")))
        st.plotly_chart(fig_map, width="stretch", config=CHART_CONFIG)

    with tabplay:
        st.caption("Press ▶ to watch smog move across Pakistan hour by hour")
        anim = df.copy()
        anim["time"] = pd.to_datetime(anim["time"])
        anim = anim[anim["time"] > anim["time"].max() - pd.Timedelta(hours=48)].dropna(subset=["us_aqi"])
        anim["lat"] = anim["city"].map(lambda n: coords[n][0])
        anim["lon"] = anim["city"].map(lambda n: coords[n][1])
        anim["hour"] = anim["time"].dt.strftime("%d %b %H:00")
        anim = anim.sort_values("time")
        fig_anim = px.scatter_map(
            anim, lat="lat", lon="lon", size="us_aqi", size_max=40, color="us_aqi",
            color_continuous_scale=[[0, "#2ecc71"], [0.17, "#f1c40f"], [0.33, "#e67e22"],
                                    [0.5, "#e74c3c"], [0.75, "#8e44ad"], [1, "#7b1e3a"]],
            range_color=[0, 400], animation_frame="hour", hover_name="city",
            zoom=MAP_ZOOM, center={"lat": 30.2, "lon": 69.8}, map_style="carto-darkmatter", height=MAP_HEIGHT,
        )
        fig_anim.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                               coloraxis_colorbar=dict(title="AQI"))
        if fig_anim.layout.updatemenus:
            fig_anim.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 250
        st.plotly_chart(fig_anim, width="stretch", config=CHART_CONFIG)

with right:
    st.markdown("#### 🏆 City ranking (worst → best)")
    ranked = latest.sort_values("us_aqi")
    fig_rank = go.Figure(go.Bar(
        x=ranked["us_aqi"], y=ranked["city"], orientation="h", marker_color=ranked["colour"],
        text=[f"{v:.0f}" for v in ranked["us_aqi"]], textposition="outside",
        hovertext=ranked["category"] + " · " + ranked["source"], hoverinfo="text+x",
    ))
    fig_rank.update_layout(height=480 if IS_MOBILE else 520, margin=dict(l=0, r=30, t=0, b=0), template="plotly_dark",
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           xaxis_title="US AQI", showlegend=False,
                           xaxis_range=[0, ranked["us_aqi"].max() * 1.18])
    st.plotly_chart(fig_rank, width="stretch", config=CHART_CONFIG)

# ---------- trend ----------
st.markdown("#### 📈 Hourly trend")
default_cities = latest["city"].head(4).tolist()
picked = st.multiselect("Compare cities", sorted(latest["city"]), default=default_cities)

trend = df.copy()
trend["time"] = pd.to_datetime(trend["time"])
trend = trend[(trend["time"] >= trend["time"].max() - pd.Timedelta(days=days))
              & trend["city"].isin(picked)]

fig_trend = px.line(trend, x="time", y="us_aqi", color="city", template="plotly_dark", height=360 if IS_MOBILE else 430,
                    color_discrete_sequence=["#4cc9f0", "#f72585", "#ffd166", "#06d6a0",
                                             "#b8b8ff", "#ff9f1c"])
lower = 0
top = max(320, (trend["us_aqi"].max() if not trend.empty else 0) * 1.1)
for upper, label, colour, _ in AQI_BANDS:
    if lower >= top:
        break
    fig_trend.add_hrect(y0=lower, y1=min(upper, top), fillcolor=colour, opacity=0.08, line_width=0)
    lower = upper
fig_trend.update_layout(margin=dict(l=0, r=10, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", yaxis_title="US AQI", xaxis_title="",
                        legend=dict(title="", orientation="h", y=-0.15, x=0), yaxis_range=[0, top])
st.plotly_chart(fig_trend, width="stretch", config=CHART_CONFIG)

# ---------- legend ----------
with st.expander("What do the AQI levels mean?"):
    for upper, label, colour, advice in AQI_BANDS:
        rng = "301+" if upper == float("inf") else f"≤ {upper}"
        st.markdown(f'<span class="pill" style="background:{colour}">{label} ({rng})</span> '
                    f'&nbsp; {advice}', unsafe_allow_html=True)

st.markdown(f'<div class="footer">{config.STATION_ATTRIBUTION} · {config.ATTRIBUTION} (model '
            f'estimates where no station reports) · AQI computed with the US EPA PM2.5 formula '
            f'from hourly readings · built by Kamran Anwar</div>', unsafe_allow_html=True)

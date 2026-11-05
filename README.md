# Smog Tracker PK 🌫️

Live air quality for **19 cities across every province of Pakistan**, with an interactive **3D dashboard**: real measured data from ground monitoring stations where available, model estimates everywhere else, and every number labelled with its source.

Built in public as a learning project: Python → SQL → APIs → deployment.

## Features
- **Authentic data first.** Real PM2.5 readings from ground monitoring stations (OpenAQ). When a city has no reporting station, it falls back to a model estimate (CAMS via Open-Meteo), clearly labelled.
- **US EPA AQI.** PM2.5 is converted with the official EPA formula (2024 breakpoints) and labelled Good → Hazardous, with health advice.
- **Dashboard (Streamlit):** dark theme, animated cards, a 3D map you can rotate (column height = AQI), a play-button animation of the last 48 hours, city ranking, hourly trends, and a region filter.
- **LinkedIn-ready PNGs:** national ranking and trend charts.
- Tests (`pytest`), retries, rate-limit handling, de-duplicated storage.

## Setup
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### Get a free OpenAQ key (for real measured data)
1. Sign up at https://explore.openaq.org → Account → API Key
2. Set it in your terminal:
   - Windows PowerShell: `$env:OPENAQ_API_KEY="your-key"`
   - Mac/Linux: `export OPENAQ_API_KEY="your-key"`

Without a key the app still works, using model estimates only, and says so.

## Run
```bash
python main.py --past-days 3 --chart   # fetch data + print ranking + save charts
streamlit run app.py                   # open the dashboard at http://localhost:8501
python -m pytest                       # run tests
```

## Project structure
```
smog_tracker/
  config.py          # cities, API settings, file paths
  client.py          # Open-Meteo model data (batched, retries)
  openaq_client.py   # OpenAQ measured station data
  aqi.py             # EPA categories, colours, advice, PM2.5 -> AQI
  analysis.py        # latest values, measured-vs-model merge
  storage.py         # CSV storage with de-duplication
  chart.py           # PNG charts
app.py               # Streamlit dashboard
main.py              # command line
tests/               # pytest
```

## Data sources & honesty notes
- **Measured:** [OpenAQ](https://openaq.org) ground stations. AQI is computed from the latest hourly PM2.5 reading. Official AQI uses a 24-hour average, so treat it as an hourly estimate.
- **Model:** CAMS ENSEMBLE via [Open-Meteo.com](https://open-meteo.com) (free for non-commercial use). These are forecast-model estimates, not sensor readings.
- Stations more than 6 hours old are ignored. A station counts toward a city if it's within 35 km of the centre.

## Roadmap
- [x] Python data collection, AQI logic, charts, tests
- [x] Measured station data + 3D dashboard
- [ ] Postgres database + SQL insights
- [ ] FastAPI endpoints
- [ ] Docker + daily schedule + public deployment

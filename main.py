"""Command-line entry point.

Examples:
    python main.py                              # fetch all cities (last 1 day + today)
    python main.py --past-days 7 --chart        # fetch a week and save charts
    python main.py --cities lahore karachi      # only some cities
    streamlit run app.py                        # open the dashboard
"""

import argparse
import logging

from smog_tracker import config
from smog_tracker.analysis import combine_latest, latest_observed
from smog_tracker.chart import plot_aqi, plot_city_ranking
from smog_tracker.client import AirQualityClient
from smog_tracker.openaq_client import OpenAQClient, OpenAQError
from smog_tracker.storage import (load_readings, load_station_readings, save_readings,
                                  save_station_readings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track air quality across Pakistani cities")
    parser.add_argument("--cities", nargs="+", default=sorted(config.CITIES),
                        choices=sorted(config.CITIES), help="Cities to fetch (default: all)")
    parser.add_argument("--past-days", type=int, default=1, help="Days of history (0-92)")
    parser.add_argument("--chart", action="store_true", help="Save ranking + trend chart PNGs")
    parser.add_argument("--chart-days", type=int, default=3, help="Days shown on the trend chart")
    parser.add_argument("--no-stations", action="store_true",
                        help="Skip measured station data (OpenAQ) and use model data only")
    return parser.parse_args()


def print_ranking(df, stations=None) -> None:
    latest = combine_latest(latest_observed(df), stations)
    if latest.empty:
        return
    print("\n  Rank  City            AQI   Source")
    print("  " + "-" * 56)
    for rank, row in enumerate(latest.itertuples(), start=1):
        print(f"  {rank:>4}  {row.city:<14} {row.us_aqi:>4.0f}   {row.source}")
    print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    cities = [config.CITIES[key] for key in args.cities]
    rows = AirQualityClient().fetch_cities(cities, past_days=args.past_days)
    save_readings(rows, config.DATA_FILE)

    stations = None
    if not args.no_stations:
        try:
            oaq = OpenAQClient()
            readings = oaq.latest_readings(oaq.list_pm25_stations())
            stations = save_station_readings(readings, config.STATIONS_LATEST_FILE,
                                             config.STATIONS_HISTORY_FILE)
        except OpenAQError as exc:
            logging.warning("Measured station data skipped: %s", exc)

    df = load_readings(config.DATA_FILE)
    print_ranking(df, stations)

    if args.chart and not df.empty:
        ranking = plot_city_ranking(df, f"{config.CHART_DIR}/pakistan_ranking.png")
        worst5 = latest_observed(df)["city"].head(5).tolist()
        trend = plot_aqi(df, worst5, f"{config.CHART_DIR}/trend_worst5_{args.chart_days}d.png",
                         days=args.chart_days)
        logging.info("Charts saved: %s, %s", ranking, trend)


if __name__ == "__main__":
    main()

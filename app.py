import os
import re
import json
import requests
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # For Python 3.9+; use pytz if older Python
from icalendar import Calendar, Event
from flask import Flask, Response

##############################################################################
# Load Configuration
##############################################################################
def load_config(config_path: str) -> dict:
    """
    Loads JSON configuration from the specified file.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config

##############################################################################
# Create Flask App
##############################################################################
app = Flask(__name__)

##############################################################################
# Caching + ICS Fetching
##############################################################################
def fetch_ics_with_cache(config: dict, calendar_name: str) -> bytes:
    """
    Fetch an ICS file from config["ical_url"], using a time-based cache.
    Returns the raw ICS data as bytes.
    """
    ics_url = config["ical_url"]
    cache_file = os.path.join("cache", f"cached_calendar_{calendar_name}.ics")
    cache_timestamp_file = os.path.join("cache", f"cached_calendar_{calendar_name}.txt")
    cache_expiry_hours = config.get("cache_expiry_hours", 4)

    # Check if the cache is still valid
    if os.path.exists(cache_file) and os.path.exists(cache_timestamp_file):
        with open(cache_timestamp_file, "r", encoding='utf-8') as ts_file:
            cached_time_str = ts_file.read().strip()
            if cached_time_str:
                cached_time = datetime.fromisoformat(cached_time_str)
                if datetime.now() - cached_time < timedelta(hours=cache_expiry_hours):
                    # Use cached file
                    with open(cache_file, "rb") as f:
                        return f.read()

    # Cache is invalid or doesn't exist; fetch from the URL
    response = requests.get(ics_url)
    response.raise_for_status()
    ics_data = response.content

    if not os.path.isdir("cache"):
        os.mkdir("cache")

    # Store new data in cache
    with open(cache_file, "wb") as f:
        f.write(ics_data)
    with open(cache_timestamp_file, "w", encoding='utf-8') as ts_file:
        ts_file.write(datetime.now().isoformat())

    return ics_data

##############################################################################
# Applying Overrides
##############################################################################
def apply_overrides(ics_data: str, config: dict, calendar_name: str) -> bytes:
    """
    Given raw ICS data, parse and apply time/location overrides from config.
    Return new ICS data (bytes).
    """

    # Prepare compiled regex patterns ahead of time
    time_overrides = []
    for rule in config.get("time_overrides", []):
        pattern = re.compile(rule["regex"], re.IGNORECASE)
        time_overrides.append({
            "pattern":    pattern,
            "start_time": rule["start_time"],
            "end_time":   rule["end_time"],
            "timezone":   rule["timezone"]
        })

    location_overrides = []
    for rule in config.get("location_overrides", []):
        pattern = re.compile(rule["regex"], re.IGNORECASE)
        location_overrides.append({
            "pattern":  pattern,
            "location": rule["location"]
        })

    cal = Calendar.from_ical(ics_data)

    # Iterate over each component in the calendar
    for component in cal.walk():
        if component.name == "VEVENT":
            summary = component.get("SUMMARY", "")

            # 1) Time Overrides
            for rule in time_overrides:
                if rule["pattern"].search(summary):
                    # We have a match; override times
                    start_str = rule["start_time"]  # "HH:MM:SS"
                    end_str   = rule["end_time"]    # "HH:MM:SS"
                    override_tz = ZoneInfo(rule["timezone"])

                    # Get existing event's start/end
                    dtstart = component.get("DTSTART").dt
                    dtend   = component.get("DTEND").dt

                    # Determine the event's timezone from DTSTART (or fallback to UTC)
                    if hasattr(dtstart, 'tzinfo') and dtstart.tzinfo is not None:
                        event_tz = dtstart.tzinfo
                    else:
                        event_tz = ZoneInfo("UTC")

                    # Build naive datetime from override times using the same date as dtstart
                    original_date = dtstart.date()
                    start_naive = datetime.combine(
                        original_date,
                        datetime.strptime(start_str, "%H:%M:%S").time()
                    )
                    end_naive = datetime.combine(
                        original_date,
                        datetime.strptime(end_str, "%H:%M:%S").time()
                    )

                    # Attach the override timezone, then convert to event timezone
                    start_localized = start_naive.replace(tzinfo=override_tz)
                    end_localized   = end_naive.replace(tzinfo=override_tz)

                    new_start = start_localized.astimezone(event_tz)
                    new_end   = end_localized.astimezone(event_tz)

                    component["DTSTART"].dt = new_start
                    component["DTEND"].dt = new_end

                    # Stop after the first time override match
                    break

            # 2) Location Overrides
            for rule in location_overrides:
                if rule["pattern"].search(summary):
                    component["LOCATION"] = rule["location"]  # Set or override location
                    # Stop after the first location override match
                    break

    # Convert Calendar object back to ICS bytes
    return cal.to_ical()

##############################################################################
# Flask Route
##############################################################################
@app.route("/<calendar>/events.ics")
def calendar_proxy(calendar):
    """
    Fetch ICS from the configured URL (with caching),
    apply transformations, and return the resulting ICS.
    """
    config = app.config["CALPROXY_CONFIG"]

    if calendar not in config:
        return Response(f"The calendar {calendar} does not exist.", status=404, mimetype="text/plain")

    # Fetch from cache or remote
    ics_data = fetch_ics_with_cache(config[calendar], calendar)

    # Apply overrides
    transformed_ics = apply_overrides(ics_data.decode("utf-8"), config[calendar], calendar)

    # Return ICS
    return Response(transformed_ics, mimetype="text/calendar")

##############################################################################
# Main Entry Point
##############################################################################
def main():
    """
    Load configuration and run the Flask app.
    """
    parser = argparse.ArgumentParser(
        description="Run the iCal proxy with overrides from a JSON config."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the JSON config file (default: config.json)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to listen on (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        default=5000,
        type=int,
        help="Port to listen on (default: 5000)"
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    app.config["CALPROXY_CONFIG"] = config

    # Run Flask app
    app.run(host=args.host, port=args.port)

if __name__ == "__main__":
    main()

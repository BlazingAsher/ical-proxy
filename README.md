## ICalendar Proxy

This will transform an ics file (that may contain many events) from some URL given some rules and return it.

There are two types of rules: time override and location override. Rules are selected by a regex to match the summary of an event.

A time override will set a new starting and ending time for the event. The new time is given in HH:MM:SS format along with a timezone.

A location override will just set the location property to the given value. If a location didn't exist on the original event, it will be added.

## General Overview
Calendars are configured by creating a new entry in `config.json` (or whatever path given in the `--config` flag).

The proxied calendar will be available at `/<calendar name>/events.ics`.

When a request is made, the service pulls the original calendar file and applies the transformations (if more than one transformation of a given type matches an event, any one of the matching transformations may be applied).

The transformed calendar is also cached for a period of time that can be configured.

See the `config.json.example` for more details.

## Running
1. Install Python requirements in requirements.txt
2. Run `app.py`: `python3 app.py`
   1. The default listening address and port is 127.0.0.1:5000
   2. Options can be found by running with `-h`: `python3 app.py -h`

**WARNING**: There is no authentication functionality! This service should most likely be behind a reverse proxy that can provide authentication or only host calendars that should be publicly-available.
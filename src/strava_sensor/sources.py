"""Source initialization utilities."""

import os

import stravalib

from strava_sensor.source.base import BaseSource
from strava_sensor.source.file import FileSource
from strava_sensor.source.garmin import GarminSource
from strava_sensor.source.strava import StravaSource


def initialize_sources() -> list[BaseSource]:
    """Initialize the sources for reading activities."""
    sources = []

    # Add file source
    sources.append(FileSource())

    # Add Garmin source
    garmin_username = os.environ.get('GARMIN_USERNAME')
    garmin_password = os.environ.get('GARMIN_PASSWORD')
    if garmin_username and garmin_password:
        sources.append(GarminSource(garmin_username, garmin_password))

    # Strava doesn't support downloading FIT files directly.
    # So we need to create it last and give it downstream sources.
    strava_refresh_token = os.environ['STRAVA_REFRESH_TOKEN']
    if strava_refresh_token:
        client = stravalib.Client(
            refresh_token=strava_refresh_token,
            # Hack to avoid an access token in the first place
            token_expires=1,
        )
        sources.append(StravaSource(client, sources))

    return sources
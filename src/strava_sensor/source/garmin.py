import datetime
import io
import logging
import os
import pathlib
import urllib.parse
import zipfile

from typing import override

import garminconnect

from strava_sensor.source.base import BaseSource

_logger = logging.getLogger(__name__)


class GarminSource(BaseSource):
    uri_scheme = 'garmin'
    http_hosts = ['connect.garmin.com']

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def _get_client(self) -> garminconnect.Garmin:
        tokenstore = pathlib.Path(os.getenv('GARMINTOKENS', '~/.garminconnect')).expanduser()
        _logger.debug('Token store: %s (exists: %s)', tokenstore, tokenstore.exists())

        garmin = garminconnect.Garmin(self.username, self.password)
        garmin.login(tokenstore=str(tokenstore) if tokenstore.exists() else None)

        # Save oauth tokens for next login
        garmin.garth.dump(str(tokenstore))
        return garmin

    @override
    def read_activity(self, uri: str) -> bytearray:
        """Read an activity from Garmin Connect.
        Args:
            uri: The activity ID to read.
        Returns:
            The activity data as bytes.
        """
        _logger.info('Downloading activity %s', uri)

        parts = urllib.parse.urlparse(uri)
        if parts.scheme == self.uri_scheme:
            activity_id = parts.netloc
        elif parts.scheme == 'https':
            activity_id = parts.path.split('/')[-1]
        else:
            raise ValueError(f'Invalid URI: {uri}')

        garmin = self._get_client()
        activity_data_zip = garmin.download_activity(
            activity_id, dl_fmt=garminconnect.Garmin.ActivityDownloadFormat.ORIGINAL
        )

        # Unzip the data
        with zipfile.ZipFile(io.BytesIO(activity_data_zip), 'r') as zip_ref:
            content_files = zip_ref.namelist()
            assert len(content_files) == 1, 'Expected only one file in the zip'
            return bytearray(zip_ref.read(content_files[0]))

    @override
    def find_activity(
        self, date: datetime.date, elapsed_time_in_s: int, distance_in_m: int
    ) -> str | None:
        """Find an activity in the source.

        Args:
            date: The date of the activity.
            elapsed_time_in_s: The elapsed time of the activity in seconds.
            distance_in_m: The distance of the activity in meters.

        Returns:
            The URI of the activity, or None if not found.
        """
        _logger.debug(
            'Finding activity for date %s, elapsed time %s, distance %s',
            date,
            elapsed_time_in_s,
            distance_in_m,
        )

        garmin = self._get_client()
        activities = garmin.get_activities_by_date(
            startdate=date, enddate=date + datetime.timedelta(days=1)
        )

        for activity in activities:
            _logger.debug('Matching activity %s', activity['activityId'])
            activity_elapsed_time = activity['duration']
            activity_distance = activity['distance']

            # Check if the activity matches elapsed time within 60 seconds
            if abs(activity_elapsed_time - elapsed_time_in_s) > 60:
                continue

            # Check if the activity matches distance within 100 meters
            if abs(activity_distance - distance_in_m) > 100:
                continue

            _logger.debug(
                'Found activity %s with elapsed time %s and distance %s',
                activity['activityId'],
                activity_elapsed_time,
                activity_distance,
            )

            return f'{self.uri_scheme}://{activity["activityId"]}'

        return None

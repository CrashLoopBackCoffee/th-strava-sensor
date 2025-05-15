import collections.abc as c
import logging
import urllib.parse

import stravalib

from strava_sensor.source.base import BaseSource

_logger = logging.getLogger(__name__)


class StravaSource(BaseSource):
    """Strava source for reading FIT files."""

    uri_scheme = 'strava'
    http_hosts = ['www.strava.com', 'strava.com']

    def __init__(self, client: stravalib.Client, downstream_sources: c.Iterable[BaseSource]):
        self.client = client

        # Strava doesn't offer a way to download the original FIT file
        # So we need to use the downstream sources to do that
        self.downstream_sources = downstream_sources

    def read_activity(self, uri: str) -> bytearray:
        """Read an activity from Strava.

        Args:
            uri: The activity ID to read.

        Returns:
            The activity data as bytes.
        """
        _logger.info('Downloading activity %s', uri)

        parts = urllib.parse.urlparse(uri)
        if parts.scheme == self.uri_scheme:
            activity_id = int(parts.netloc)
        elif parts.scheme == 'https':
            activity_id = int(parts.path.split('/')[-1])
        else:
            raise ValueError(f'Invalid URI: {uri}')

        activity = self.client.get_activity(activity_id)
        if activity is None:
            raise ValueError(f'Activity {activity_id} not found')
        external_id = activity.external_id
        if external_id is None:
            raise ValueError(f'Activity {activity_id} has no external ID')

        assert activity.start_date
        activity_date = activity.start_date.date()

        for source in self.downstream_sources:
            _logger.debug('Checking downstream source %s', source.__class__.__name__)
            assert activity.elapsed_time
            assert activity.distance
            downstream_uri = source.find_activity(
                date=activity_date,
                elapsed_time_in_s=int(activity.elapsed_time),
                distance_in_m=int(activity.distance),
            )

            if not downstream_uri:
                continue
            _logger.debug('Found activity %s in %s', downstream_uri, source.__class__.__name__)

            return source.read_activity(downstream_uri)

        _logger.warning('No downstream source found for activity %s', uri)
        raise ValueError(f'No downstream source found for activity {uri}')

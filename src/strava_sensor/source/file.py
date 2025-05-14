import pathlib

from strava_sensor.source.base import BaseSource


class FileSource(BaseSource):
    """File source for reading FIT files."""

    uri_scheme = 'file'

    def read_activity(self, uri: str) -> bytearray:
        """Read an activity from the file.

        Args:
            identifier: The path to the activity to read.

        Returns:
            The activity data as bytes.
        """
        with open(pathlib.Path.from_uri(uri), 'rb') as f:
            return bytearray(f.read())

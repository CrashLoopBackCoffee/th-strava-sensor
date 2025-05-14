import abc
import logging
import urllib.parse

_logger = logging.getLogger(__name__)


class BaseSource(metaclass=abc.ABCMeta):
    """Base class for all sources."""

    uri_scheme = None
    """The URI scheme for the source."""

    http_hosts = []
    """The HTTP hosts for the source."""

    def matches_uri(self, uri: str) -> bool:
        """Check if the URI matches the source.
        Args:
            uri: The URI to check.
        Returns:
            True if the URI matches the source, False otherwise.
        """
        _logger.debug('Checking URI %s against %s', uri, self.__class__.__name__)
        result = urllib.parse.urlparse(uri)
        if result.scheme == self.uri_scheme:
            return True

        _logger.debug('Checking URI %s against HTTP hosts %s', uri, self.http_hosts)
        if result.hostname in self.http_hosts:
            return True

        return False

    @abc.abstractmethod
    def read_activity(self, uri: str) -> bytearray:
        """Read an activity from the source.

        Args:
            uri: The uri of the activity to read.

        Returns:
            The activity data as bytes.
        """
        ...

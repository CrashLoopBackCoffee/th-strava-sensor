import logging

import stravalib
import stravalib.model

_logger = logging.getLogger(__name__)


class StravaClient:
    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token

        self.client = stravalib.Client(
            refresh_token=self.refresh_token,
            # Hack to avoid an access token in the first place
            token_expires=1,
        )

        athlete = self.client.get_athlete()
        _logger.info('Authenticated as %s %s', athlete.firstname, athlete.lastname)

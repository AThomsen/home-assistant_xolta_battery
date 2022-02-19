import json
import logging

import requests

from homeassistant import exceptions

_LOGGER = logging.getLogger(__name__)

_TokenURL = "https://xolta.b2clogin.com/145c2c43-a8da-46ab-b5da-1d4de444ed82/b2c_1_sisu/oauth2/v2.0/token"
_ApiBaseURL = "https://xoltarmcluster2.northeurope.cloudapp.azure.com:19081/Xolta.Rm.Base.App/Xolta.Rm.Base.Api/api/"
_RequestTimeout = 30  # seconds

_DefaultHeaders = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "token": '{"version":"","client":"ios","language":"en"}',
}


class XoltaApi:
    """Interface to the Xolta API."""

    def __init__(self, hass, refresh_token, site_id):
        """Init dummy hub."""
        self._hass = hass
        self._refresh_token = refresh_token
        self._access_token = None
        self._site_id = site_id

    def test_authentication(self) -> bool:
        """Test if we can authenticate with the host."""
        try:
            self.renewTokens()
            return self._access_token is not None
        except Exception as exception:
            _LOGGER.exception("API Authentication exception " + exception)
            return False

    def renewTokens(self):
        """Get an access token for the Xolta API from a refresh token"""
        try:
            # Get our Authentication Token from SEMS Portal API
            _LOGGER.debug("Xolta - Getting API access token")

            login_data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }

            # Make POST request to retrieve Authentication Token from SEMS API
            login_response = requests.post(
                _TokenURL,
                headers=_DefaultHeaders,
                data=login_data,
                timeout=_RequestTimeout,
            )
            _LOGGER.debug("Login Response: %s", login_response)
            # _LOGGER.debug("Login Response text: %s", login_response.text)

            login_response.raise_for_status()

            # Process response as JSON
            jsonResponse = login_response.json()
            # _LOGGER.debug("Login JSON response %s", jsonResponse)
            # Get all the details from our response, needed to make the next POST request (the one that really fetches the data)
            self._access_token = jsonResponse["access_token"]
            self._refresh_token = jsonResponse["refresh_token"]

            _LOGGER.debug("Xolta - API Token received: %s", self._access_token)

        except Exception as exception:
            _LOGGER.error("Unable to fetch login token from Xolta API. %s", exception)

    def getData(self, powerStationId, renewToken=False, maxTokenRetries=2):
        """Get the latest data from the SEMS API and updates the state."""
        try:
            # Get the status of our SEMS Power Station
            _LOGGER.debug("SEMS - Making Power Station Status API Call")
            if maxTokenRetries <= 0:
                _LOGGER.info(
                    "SEMS - Maximum token fetch tries reached, aborting for now"
                )
                raise OutOfRetries
            if self._access_token is None or renewToken:
                _LOGGER.debug(
                    "API token not set (%s) or new token requested (%s), fetching",
                    self._access_token,
                    renewToken,
                )
                self.renewTokens()

            # Prepare Power Station status Headers
            headers = {
                # "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "Authorization": "Bearer " + self._access_token,
            }

            _LOGGER.debug("Querying SEMS API for power station id: %s", powerStationId)

            # data = '{"powerStationId":"' + powerStationId + '"}'

            response = requests.get(
                _ApiBaseURL + "siteStatus",
                headers=headers,
                params={"siteId": self._site_id},
                timeout=_RequestTimeout,
            )

            # try again and renew token is unsuccessful
            if response.status_code == 401:
                _LOGGER.debug(
                    "Query not successful (%s), retrying with new token, %s retries remaining",
                    jsonResponse["msg"],
                    maxTokenRetries,
                )
                return self.getData(
                    powerStationId, True, maxTokenRetries=maxTokenRetries - 1
                )

            response.raise_for_status()

            jsonResponse = response.json()
            return jsonResponse["data"]
        except Exception as exception:
            _LOGGER.error("Unable to fetch data from SEMS. %s", exception)


class OutOfRetries(exceptions.HomeAssistantError):
    """Error to indicate too many error attempts."""

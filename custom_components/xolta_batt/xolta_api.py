import json
import logging
import aiohttp
from sqlalchemy import true

from homeassistant.config_entries import ConfigEntry
from homeassistant import exceptions
from .const import CONF_SITE_ID, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

_TokenURL = "https://xolta.b2clogin.com/145c2c43-a8da-46ab-b5da-1d4de444ed82/b2c_1_sisu/oauth2/v2.0/token"
_ApiBaseURL = "https://xoltarmcluster2.northeurope.cloudapp.azure.com:19081/Xolta.Rm.Base.App/Xolta.Rm.Base.Api/api/"
_RequestTimeout = aiohttp.ClientTimeout(total=20)  # seconds


class XoltaApi:
    """Interface to the Xolta API."""

    def __init__(
        self,
        hass,
        webclient: aiohttp.ClientSession,
        site_id,
        refresh_token,
        config_entry: ConfigEntry,
    ):
        """Init dummy hub for config testing"""
        self._hass = hass
        self._webclient = webclient
        self._config_entry = config_entry
        self._site_id = site_id
        self._refresh_token = refresh_token
        self._access_token = None

    async def test_authentication(self) -> bool:
        """Test if we can authenticate with the host."""
        try:
            await self.renewTokens()
            return self._access_token is not None
        except Exception as exception:
            _LOGGER.exception("API Authentication exception " + exception)
            return False

    async def renewTokens(self):
        """Get an access token for the Xolta API from a refresh token"""
        try:
            _LOGGER.debug("Xolta - Getting API access token")

            login_data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }

            # Make POST request to retrieve Authentication Token from Xolta API
            async with self._webclient.post(
                _TokenURL, data=login_data, timeout=_RequestTimeout
            ) as login_response:
                _LOGGER.debug("Login Response: %s", login_response)

                login_response.raise_for_status()

                # Process response as JSON
                jsonResponse = await login_response.json()
                # _LOGGER.debug("Login JSON response %s", jsonResponse)
                # Get all the details from our response, needed to make the next POST request (the one that really fetches the data)
                self._access_token = jsonResponse["access_token"]
                self._refresh_token = jsonResponse["refresh_token"]

                if self._config_entry is not None:
                    self._hass.config_entries.async_update_entry(
                        self._config_entry,
                        data={
                            **self._config_entry.data,
                            CONF_REFRESH_TOKEN: self._refresh_token,
                        },
                    )

                _LOGGER.debug("Xolta - API Token received: %s", self._access_token)

        except Exception as exception:
            _LOGGER.error("Unable to fetch login token from Xolta API. %s", exception)

    async def getData(self, renewToken=False, maxTokenRetries=2):
        """Get the latest data from the Xolta API and updates the state."""
        try:
            while True:
                if maxTokenRetries <= 0:
                    _LOGGER.info(
                        "Xolta - Maximum token fetch tries reached, aborting for now"
                    )
                    raise OutOfRetries

                if self._access_token is None or renewToken:
                    _LOGGER.debug(
                        "API token not set (%s) or new token requested (%s), fetching",
                        self._access_token,
                        renewToken,
                    )
                    await self.renewTokens()

                # Prepare Power Station status Headers
                headers = {
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                    "Authorization": "Bearer " + self._access_token,
                }

                async with await self._webclient.get(
                    _ApiBaseURL + "siteStatus",
                    headers=headers,
                    params={"siteId": self._site_id},
                    timeout=_RequestTimeout,
                ) as response:

                    # try again and renew token is unsuccessful
                    if response.status == 401:
                        _LOGGER.debug(
                            "Unauthorized call to Xolta API. Renewing token (trying %s time(s))",
                            maxTokenRetries,
                        )
                        maxTokenRetries -= 1
                        renewToken = true
                        continue

                    response.raise_for_status()

                    jsonResponse = await response.json()
                    return jsonResponse["data"]

        except Exception as exception:
            _LOGGER.error("Unable to fetch data from Xolta api. %s", exception)


class OutOfRetries(exceptions.HomeAssistantError):
    """Error to indicate too many error attempts."""

import asyncio
from datetime import timedelta, timezone, datetime as dt
import ciso8601
import json
import logging
import aiohttp
import uuid
from homeassistant.config_entries import ConfigEntry
from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import datetime
from .const import CONF_SITE_ID

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_PREFIX = "xolta_batt_auth_"
STORAGE_VERSION = 1
STORAGE_ACCESS_TOKEN = "access_token"
STORAGE_REFRESH_TOKEN = "refresh_token"

_TokenURL = "https://xolta.b2clogin.com/145c2c43-a8da-46ab-b5da-1d4de444ed82/b2c_1_sisu/oauth2/v2.0/token"
_ApiBaseURL = "https://xoltarmcluster2.northeurope.cloudapp.azure.com:19081/Xolta.Rm.Base.App/Xolta.Rm.Base.Api/api/"
_RequestTimeout = aiohttp.ClientTimeout(total=20)  # seconds


class XoltaApi:
    """Interface to the Xolta API."""

    def __init__(
        self,
        hass: HomeAssistant,
        webclient: aiohttp.ClientSession,
        site_id,
        username,
        password,
    ):
        self._hass = hass
        self._webclient = webclient
        self._site_id = site_id

        self._username = username
        self._password = password

        self._prefs = None
        self._store = hass.helpers.storage.Store(
            STORAGE_VERSION, STORAGE_KEY_PREFIX + site_id
        )

        self._auth_event = asyncio.Event()
        self._auth_corr_id = None
        hass.bus.async_listen("XOLTA_BATT_AUTH_RESPONSE", self.auth_appdaemon_cb)

        self._telemetry_data_ts = None
        self._data = {}

    async def test_authentication(self) -> bool:
        """Test if we can authenticate with the host."""
        try:
            if self._prefs is None:
                await self.async_load_preferences()
            await self.renewTokens()
            return True
        except Exception as exception:
            _LOGGER.exception("API Authentication exception " + exception)
            raise

    async def auth_appdaemon_cb(self, event):
        if event.data.get("corr_id") == self._auth_corr_id:
            self._prefs[STORAGE_ACCESS_TOKEN] = event.data.get("access_token")
            self._prefs[STORAGE_REFRESH_TOKEN] = event.data.get("refresh_token")
            await self._store.async_save(self._prefs)
            self._auth_event.set()

    async def wait_for_auth(self):
        # todo - check for re-entrant...
        self._auth_corr_id = str(uuid.uuid4())
        data = {
            "username": self._username,
            "password": self._password,
            "corr_id": self._auth_corr_id,
        }
        self._hass.bus.async_fire("XOLTA_BATT_AUTH_REQUEST", data)
        await self._auth_event.wait()

    async def login(self):
        # wait for up to ½ min to be sure everything is started up...
        await asyncio.wait_for(self.wait_for_auth(), 30)
        self._auth_event.clear()

    async def renewTokens(self):
        if self._prefs is None:
            await self.async_load_preferences()

        """Get an access token for the Xolta API from a refresh token"""
        try:
            if self._prefs[STORAGE_REFRESH_TOKEN] is None:
                await self.login()
                return

            _LOGGER.debug("Xolta - Getting API access token from refresh token")

            login_data = {
                "grant_type": "refresh_token",
                "refresh_token": self._prefs[STORAGE_REFRESH_TOKEN],
            }

            # Make POST request to retrieve Authentication Token from Xolta API
            async with self._webclient.post(
                _TokenURL, data=login_data, timeout=_RequestTimeout
            ) as login_response:
                _LOGGER.debug("Login Response: %s", login_response)

                if login_response.status == 400:
                    txt = await login_response.text()
                    if "AADB2C90080" in txt:
                        _LOGGER.info(
                            "Could not authenticate against Xolta. Refresh token expired. Logging in with appdaemon..."
                        )

                        await self.login()

                        # todo: handle errors...
                        return

                        # raise exceptions.ConfigEntryAuthFailed(
                        #     "Could not authenticate against Xolta. Refresh token expired."
                        # )

                login_response.raise_for_status()

                # Process response as JSON
                jsonResponse = await login_response.json()
                # _LOGGER.debug("Login JSON response %s", jsonResponse)
                # Get all the details from our response, needed to make the next POST request (the one that really fetches the data)
                self._prefs[STORAGE_ACCESS_TOKEN] = jsonResponse["access_token"]
                self._prefs[STORAGE_REFRESH_TOKEN] = jsonResponse["refresh_token"]

                await self._store.async_save(self._prefs)

                _LOGGER.debug(
                    "Xolta - API Token received: %s", self._prefs[STORAGE_ACCESS_TOKEN]
                )

        except Exception as exception:
            _LOGGER.error("Unable to fetch login token from Xolta API. %s", exception)
            raise

    async def getData(self, renewToken=False, maxTokenRetries=2):
        """Get the latest data from the Xolta API and updates the state."""
        if self._prefs is None:
            await self.async_load_preferences()

        try:
            while True:
                if maxTokenRetries <= 0:
                    _LOGGER.info(
                        "Xolta - Maximum token fetch tries reached, aborting for now"
                    )
                    raise OutOfRetries

                if self._prefs[STORAGE_ACCESS_TOKEN] is None or renewToken:
                    _LOGGER.debug(
                        "API token not set (%s) or new token requested (%s), fetching",
                        self._prefs[STORAGE_ACCESS_TOKEN],
                        renewToken,
                    )
                    await self.renewTokens()

                headers = {
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                    "Authorization": "Bearer " + self._prefs[STORAGE_ACCESS_TOKEN],
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
                        renewToken = True
                        continue

                    response.raise_for_status()

                    json_response = await response.json()
                    self._data["sensors"] = json_response["data"][0]

                now = dt.now(timezone.utc)

                if (
                    self._telemetry_data_ts is None
                    or ((now - self._telemetry_data_ts).total_seconds() / 60) >= 10
                ):
                    resolution_min = 10
                    resolution_hour = resolution_min / 60

                    # TODO: hvordan ser dette ud hvis den kaldes lige efter midnat?
                    params = {
                        "siteId": self._site_id,
                        "CalculateConsumptionNeeded": "true",
                        "fromDateTime": f"{now.date().isoformat()}Z",
                        "toDateTime": f"{now.isoformat()[:-3]}Z",
                        "resolutionMin": resolution_min,
                    }
                    async with await self._webclient.get(
                        _ApiBaseURL + "GetDataSummary",
                        headers=headers,
                        params=params,
                        timeout=_RequestTimeout,
                    ) as response:

                        # try again and renew token is unsuccessful
                        if response.status == 401:
                            _LOGGER.debug(
                                "Unauthorized call to Xolta API. Renewing token (trying %s time(s))",
                                maxTokenRetries,
                            )
                            maxTokenRetries -= 1
                            renewToken = True
                            continue

                        response.raise_for_status()

                        json_response = await response.json()
                        telemetry_data = json_response["telemetry"]

                        energy_data = {
                            "pv": sum(
                                t["meterPvActivePowerAggAvgSiteSingle"]
                                for t in telemetry_data
                            )
                            * resolution_hour,
                            "consumption": sum(
                                t["calculatedConsumption"] for t in telemetry_data
                            )
                            * resolution_hour,
                            "battery_charged": sum(
                                min(0, t["inverterActivePowerAggAvgSiteSum"])
                                for t in telemetry_data
                            )
                            * -resolution_hour,
                            "battery_discharged": sum(
                                max(0, t["inverterActivePowerAggAvgSiteSum"])
                                for t in telemetry_data
                            )
                            * resolution_hour,
                            "grid_exported": sum(
                                min(0, t["meterGridActivePowerAggAvgSiteSingle"])
                                for t in telemetry_data
                            )
                            * -resolution_hour,
                            "grid_imported": sum(
                                max(0, t["meterGridActivePowerAggAvgSiteSingle"])
                                for t in telemetry_data
                            )
                            * resolution_hour,
                            "last_reset": now.date(),
                            "dt": telemetry_data
                            and ciso8601.parse_datetime(
                                telemetry_data[-1]["utcEndTime"]
                            )
                            or None,
                        }
                        self._telemetry_data_ts = energy_data["dt"] or now
                        self._data["energy"] = energy_data

                return self._data

        except Exception as exception:
            _LOGGER.error("Unable to fetch data from Xolta api. %s", exception)
            raise

    async def async_load_preferences(self):
        """Load preferences with stored tokens."""
        self._prefs = await self._store.async_load()

        if self._prefs is None:
            self._prefs = {
                STORAGE_ACCESS_TOKEN: None,
                STORAGE_REFRESH_TOKEN: None,
                # STORAGE_EXPIRE_TIME: None,
            }

    # async def _async_update_preferences(self, access_token, refresh_token):
    #     """Update user preferences."""
    #     if self._prefs is None:
    #         await self.async_load_preferences()

    #     if access_token is not None:
    #         self._prefs[STORAGE_ACCESS_TOKEN] = access_token
    #     if refresh_token is not None:
    #         self._prefs[STORAGE_REFRESH_TOKEN] = refresh_token
    #     #if expire_time is not None:
    #     #    self._prefs[STORAGE_EXPIRE_TIME] = expire_time
    #     await self._store.async_save(self._prefs)


class OutOfRetries(exceptions.HomeAssistantError):
    """Error to indicate too many error attempts."""

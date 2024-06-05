import asyncio
from datetime import timedelta, timezone, datetime as dt
import hashlib
import ciso8601
import json
import logging
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_PREFIX = "xolta_batt_auth_"
STORAGE_VERSION = 1
STORAGE_ACCESS_TOKEN = "access_token"
STORAGE_REFRESH_TOKEN = "refresh_token"

_LoginUrl = "http://70f0fc4b-xolta-batt-auth-addon:8000/login"
_TokenURL = "https://xolta.b2clogin.com/145c2c43-a8da-46ab-b5da-1d4de444ed82/b2c_1_sisu/oauth2/v2.0/token"
_ApiBaseURL = "https://xoltarmcluster2.northeurope.cloudapp.azure.com:19081/Xolta.Rm.Base.App/Xolta.Rm.Base.Api/api/"
_RequestTimeout = aiohttp.ClientTimeout(total=20)  # seconds


class XoltaApi:
    """Interface to the Xolta API."""

    def __init__(
        self,
        hass: HomeAssistant,
        webclient: aiohttp.ClientSession,
        username,
        password,
    ):
        self._hass = hass
        self._webclient = webclient

        self._username = username
        self._password = password

        self._prefs = None
        self._store = hass.helpers.storage.Store(
            STORAGE_VERSION,
            STORAGE_KEY_PREFIX + hashlib.md5(username.encode()).hexdigest(),
        )

        self._telemetry_data_ts = None
        self._data = {"sites": None, "sensors": {}, "energy": {}}

    async def login(self):
        """Call Xolta Battery authenticator add-on to exchange username+password for access token"""
        try:
            if self._prefs is None:
                await self.async_load_preferences()

            login_data = {"username": self._username, "password": self._password}

            async with self._webclient.post(
                _LoginUrl, json=login_data
            ) as login_response:

                login_response.raise_for_status()

                # Process response as JSON
                json_response = await login_response.json()

                if json_response["status"] == "200":
                    self._prefs[STORAGE_ACCESS_TOKEN] = json_response["access_token"]
                    self._prefs[STORAGE_REFRESH_TOKEN] = json_response["refresh_token"]
                    await self._store.async_save(self._prefs)
                    return True

                if json_response["status"] == "400":
                    # 400 is returned with unknown username / invalid password
                    raise exceptions.ConfigEntryAuthFailed(
                        f"Status { json_response['status'] }: { json_response['message'] }"
                    )

                # other error:
                raise Exception(
                    f"Error logging in. Status: { json_response['status'] }: { json_response['message'] }"
                )

        except exceptions.ConfigEntryAuthFailed:
            raise

        except Exception as ex:
            _LOGGER.exception("Error calling Xolta authentication add-on: %s ", ex)
            raise exceptions.ConfigEntryNotReady from ex

    async def test_authentication(self) -> bool:
        """Test if we can authenticate with the host."""
        try:
            await self.refresh_tokens()
            return True
        except Exception as exception:
            _LOGGER.exception("API Authentication exception: %s", exception)
            raise

    async def refresh_tokens(self):
        """Get an access token for the Xolta API from a refresh token"""

        if self._prefs is None:
            await self.async_load_preferences()

        try:
            _LOGGER.debug("Xolta - Getting API access token from refresh token")

            if self._prefs[STORAGE_REFRESH_TOKEN] is None:
                _LOGGER.debug("No refresh token set. Logging in")
                await self.login()
                return

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
                            "Could not authenticate against Xolta. Refresh token expired. Logging in using add-on"
                        )
                        await self.login()
                        return

                login_response.raise_for_status()

                # Process response as JSON
                json_response = await login_response.json()

                self._prefs[STORAGE_ACCESS_TOKEN] = json_response["access_token"]
                self._prefs[STORAGE_REFRESH_TOKEN] = json_response["refresh_token"]
                await self._store.async_save(self._prefs)

                _LOGGER.debug(
                    "Xolta - API Token received: %s", self._prefs[STORAGE_ACCESS_TOKEN]
                )

        except Exception as exception:
            _LOGGER.error("Unable to fetch login token from Xolta API. %s", exception)
            raise

    async def get_data(self, force_renew_token=False, max_token_retries=2):
        """Get the latest data from the Xolta API and updates the state."""
        if self._prefs is None:
            await self.async_load_preferences()

        try:
            for try_number in range(max_token_retries):

                if self._prefs[STORAGE_ACCESS_TOKEN] is None or force_renew_token:
                    _LOGGER.debug(
                        "API token not set (%s) or new token requested (%s), fetching",
                        self._prefs[STORAGE_ACCESS_TOKEN],
                        force_renew_token,
                    )
                    await self.refresh_tokens()

                try:
                    headers = {
                        "Accept": "application/json",
                        "Cache-Control": "no-cache",
                        "Authorization": "Bearer " + self._prefs[STORAGE_ACCESS_TOKEN],
                    }

                    if self._data["sites"] is None:

                        # Read sites. These probably never changes, so only read them once.
                        async with await self._webclient.get(
                            _ApiBaseURL + "SiteGroup",
                            headers=headers,
                            timeout=_RequestTimeout,
                        ) as response:

                            response.raise_for_status()
                            json_response = await response.json()
                            self._data["sites"] = json_response["sites"]

                    for site in self._data["sites"]:

                        site_id = site["siteId"]

                        async with await self._webclient.get(
                            _ApiBaseURL + "siteStatus",
                            headers=headers,
                            params={"siteId": site_id},
                            timeout=_RequestTimeout,
                        ) as response:

                            response.raise_for_status()
                            json_response = await response.json()
                            self._data["sensors"][site_id] = json_response["data"][0]
                        

                        # Only refresh energy data every 10 minutes
                        now_utc = dt_util.utcnow()

                        if (
                            self._telemetry_data_ts is None or 
                            ((now_utc - self._telemetry_data_ts).total_seconds() / 60) >= 10
                        ):
                            resolution_min = 10
                            resolution_hour = resolution_min / 60

                            # Query data from midnight (local tz) to now, but query in UTC
                            now_local = dt_util.as_local(now_utc)
                            start_of_local_day_utc = dt_util.as_utc(dt_util.start_of_local_day(now_local))

                            params = {
                                "siteId": site_id,
                                "CalculateConsumptionNeeded": "true",
                                "fromDateTime": f"{start_of_local_day_utc.replace(tzinfo=None).isoformat()}Z",
                                "toDateTime": f"{now_utc.replace(tzinfo=None, microsecond=0).isoformat()}Z",
                                "resolutionMin": resolution_min,
                            }
                            async with await self._webclient.get(
                                _ApiBaseURL + "GetDataSummary",
                                headers=headers,
                                params=params,
                                timeout=_RequestTimeout,
                            ) as response:

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
                                        t["calculatedConsumption"]
                                        for t in telemetry_data
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
                                        min(
                                            0, t["meterGridActivePowerAggAvgSiteSingle"]
                                        )
                                        for t in telemetry_data
                                    )
                                    * -resolution_hour,
                                    "grid_imported": sum(
                                        max(
                                            0, t["meterGridActivePowerAggAvgSiteSingle"]
                                        )
                                        for t in telemetry_data
                                    )
                                    * resolution_hour,
                                    "dt": telemetry_data
                                    and ciso8601.parse_datetime(
                                        telemetry_data[-1]["utcEndTime"]
                                    )
                                    or None,
                                }
                                self._telemetry_data_ts = energy_data["dt"] or now_utc
                                self._data["energy"][site_id] = energy_data

                    return self._data

                except aiohttp.ClientResponseError as err:
                    if err.status == 401:
                        _LOGGER.debug(
                            "Unauthorized call to Xolta API. Renewing token (try %s of %s time(s))",
                            try_number + 1,
                            max_token_retries,
                        )
                        force_renew_token = True
                        continue

                    raise

            _LOGGER.info("Xolta - Maximum token fetch tries reached, aborting for now")
            raise OutOfRetries

        except Exception as exception:
            _LOGGER.error("Unable to fetch data from Xolta api. %s", exception)
            raise

    async def async_load_preferences(self):
        """Load preferences with stored tokens."""
        self._prefs = await self._store.async_load()

        if self._prefs is None:
            self._prefs = {STORAGE_ACCESS_TOKEN: None, STORAGE_REFRESH_TOKEN: None}


class OutOfRetries(exceptions.HomeAssistantError):
    """Error to indicate too many error attempts."""

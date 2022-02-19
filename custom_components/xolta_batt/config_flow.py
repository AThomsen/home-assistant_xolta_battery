"""Config flow for xolta integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, XOLTA_CONFIG_SCHEMA, CONF_SITE_ID, CONF_REFRESH_TOKEN
from .xolta_api import XoltaApi

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    _LOGGER.debug("Xolta - Start validation config flow user input")
    api = XoltaApi(
        hass,
        aiohttp_client.async_create_clientsession(hass),
        data[CONF_SITE_ID],
        data[CONF_REFRESH_TOKEN],
        None,
    )

    authenticated = await api.test_authentication()
    if not authenticated:
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xolta."""

    _LOGGER.debug("Xolta - new config flow")

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=XOLTA_CONFIG_SCHEMA)

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info[CONF_SITE_ID], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=XOLTA_CONFIG_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

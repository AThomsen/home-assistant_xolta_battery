"""Config flow for xolta integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, CONN_CLASS_CLOUD_POLL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, XOLTA_CONFIG_SCHEMA, CONF_SITE_ID, CONF_REFRESH_TOKEN
from .xolta_api import XoltaApi

_LOGGER = logging.getLogger(__name__)


class XoltaBatteryFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Xolta Battery config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize config flow."""
        self._site_id = None
        self._refresh_token = None

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=XOLTA_CONFIG_SCHEMA,
            errors=errors or {},
        )

    async def _show_reauth_form(self, errors=None):
        """Show the reauth form to the user."""
        return self.async_show_form(
            step_id="reauth",
            description_placeholders={"site_id": f"{self._site_id}"},
            data_schema=vol.Schema({vol.Required(CONF_REFRESH_TOKEN): str}),
            errors=errors or {},
        )

    async def _check_setup(self):
        """Check the setup of the flow."""
        errors = {}

        api = XoltaApi(
            self.hass,
            aiohttp_client.async_create_clientsession(self.hass),
            self._site_id,
            self._refresh_token,
            None,
        )

        try:
            authenticated = await api.test_authentication()
            if authenticated:
                return None
            errors["base"] = "invalid_auth"
        except Exception as ex:
            errors["base"] = ex
        return errors

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._site_id = user_input[CONF_SITE_ID]
        self._refresh_token = user_input[CONF_REFRESH_TOKEN]

        await self.async_set_unique_id(f"{self._site_id}")
        self._abort_if_unique_id_configured()

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_setup_form(errors)
        return self._async_create_entry()

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        if user_input.get(CONF_SITE_ID):
            self._site_id = user_input[CONF_SITE_ID]
        self._pat = user_input[CONF_REFRESH_TOKEN]

        self.context["title_placeholders"] = {"site_id": f"{self._site_id}"}

        await self.async_set_unique_id(f"{self._site_id}")

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_reauth_form(errors)

        entry = await self.async_set_unique_id(self.unique_id)
        self.hass.config_entries.async_update_entry(
            entry,
            data={CONF_SITE_ID: self._site_id, CONF_REFRESH_TOKEN: self._refresh_token},
        )
        return self.async_abort(reason="reauth_successful")

    def _async_create_entry(self):
        """Handle create entry."""
        return self.async_create_entry(
            title=f"{self._site_id}",
            data={CONF_SITE_ID: self._site_id, CONF_REFRESH_TOKEN: self._refresh_token},
        )


############
# async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
#     """Validate the user input allows us to connect.

#     Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
#     """

#     _LOGGER.debug("Xolta - Start validation config flow user input")
#     api = XoltaApi(
#         hass,
#         aiohttp_client.async_create_clientsession(hass),
#         data[CONF_SITE_ID],
#         data[CONF_REFRESH_TOKEN],
#         None,
#     )

#     authenticated = await api.test_authentication()
#     if not authenticated:
#         raise InvalidAuth

#     # Return info that you want to store in the config entry.
#     return data


# class XoltaBatteryConfigFlow(ConfigFlow, domain=DOMAIN):
#     """Handle a config flow for Xolta."""

#     _LOGGER.debug("Xolta - new config flow")

#     VERSION = 1
#     CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

#     async def async_step_user(
#         self, user_input: dict[str, Any] | None = None
#     ) -> dict[str, Any]:
#         """Handle the initial step."""
#         if user_input is None:
#             return self.async_show_form(step_id="user", data_schema=XOLTA_CONFIG_SCHEMA)

#         errors = {}

#         try:
#             info = await validate_input(self.hass, user_input)
#         except CannotConnect:
#             errors["base"] = "cannot_connect"
#         except InvalidAuth:
#             errors["base"] = "invalid_auth"
#         except Exception:  # pylint: disable=broad-except
#             _LOGGER.exception("Unexpected exception")
#             errors["base"] = "unknown"
#         else:
#             return self.async_create_entry(title=info[CONF_SITE_ID], data=user_input)

#         return self.async_show_form(
#             step_id="user", data_schema=XOLTA_CONFIG_SCHEMA, errors=errors
#         )


# class CannotConnect(HomeAssistantError):
#     """Error to indicate we cannot connect."""


# class InvalidAuth(HomeAssistantError):
#     """Error to indicate there is invalid auth."""

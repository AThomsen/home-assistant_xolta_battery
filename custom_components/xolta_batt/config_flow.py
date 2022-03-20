"""Config flow for xolta integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.config_entries import ConfigFlow, CONN_CLASS_CLOUD_POLL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, XOLTA_CONFIG_SCHEMA
from .xolta_api import XoltaApi

_LOGGER = logging.getLogger(__name__)


class XoltaBatteryFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Xolta Battery config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize config flow."""
        self._username = None
        self._password = None

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
            data_schema=XOLTA_CONFIG_SCHEMA,
            errors=errors or {},
        )

    async def _check_setup(self):
        """Check the setup of the flow."""
        errors = {}

        api = XoltaApi(
            self.hass,
            aiohttp_client.async_create_clientsession(self.hass),
            self._username,
            self._password,
        )

        try:
            authenticated = await api.test_authentication()
            if authenticated:
                return None
            errors["base"] = "invalid_auth"
        except ConfigEntryAuthFailed as ex:
            errors[CONF_PASSWORD] = str(ex.args)
        except Exception as ex:
            errors[CONF_PASSWORD] = str(ex.args)
        return errors

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        await self.async_set_unique_id(f"{self._username}")
        self._abort_if_unique_id_configured()

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_setup_form(errors)
        return self._async_create_entry()

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""

        # not sure what's going on here...
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

        # self.context["title_placeholders"] = {"site_id": f"{self._site_id}"}

        await self.async_set_unique_id(f"{self._username}")

        errors = await self._check_setup()
        if errors is not None:
            return await self._show_reauth_form(errors)

        entry = await self.async_set_unique_id(self.unique_id)
        self.hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
            },
        )
        return self.async_abort(reason="reauth_successful")

    def _async_create_entry(self):
        """Handle create entry."""
        return self.async_create_entry(
            title=f"{self._username}",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
            },
        )

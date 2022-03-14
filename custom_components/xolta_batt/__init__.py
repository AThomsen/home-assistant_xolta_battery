from __future__ import annotations

import asyncio

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_SITE_ID, DOMAIN
from .xolta_api import XoltaApi

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Xolta Solar Battery component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up sems from a config entry."""
    api = XoltaApi(
        hass,
        aiohttp_client.async_create_clientsession(hass),
        entry.data[CONF_SITE_ID],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await api.renewTokens()
    except Exception as ex:
        # this causes ha to try again later...
        # todo: better exeption handling...
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN][entry.entry_id] = api

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

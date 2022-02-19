import site
from homeassistant.core import HomeAssistant
import homeassistant
import logging

from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
    POWER_KILO_WATT,
    POWER_WATT,
    # CONF_SCAN_INTERVAL,
    DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.helpers.entity import Entity
from .const import DOMAIN, CONF_SITE_ID, UPDATE_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    # _LOGGER.debug("hass.data[DOMAIN] %s", hass.data[DOMAIN])
    xoltaApi = hass.data[DOMAIN][config_entry.entry_id]
    siteId = config_entry.data[CONF_SITE_ID]

    # _LOGGER.debug("config_entry %s", config_entry.data)
    update_interval = timedelta(seconds=UPDATE_INTERVAL_SEC)

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            # async with async_timeout.timeout(10):
            result = await xoltaApi.getData()
            _LOGGER.debug("Resulting result: %s", result)

            sites = result

            # TODO: make sure it's the real site
            data = {"site_data": sites[0]}
            # if inverters is None:
            #     # something went wrong, probably token could not be fetched
            #     raise UpdateFailed(
            #         "Error communicating with API, probably token could not be fetched, see debug logs"
            #     )
            # for inverter in inverters:
            #     name = inverter["invert_full"]["name"]
            #     sn = inverter["invert_full"]["sn"]
            #     _LOGGER.debug("Found inverter attribute %s %s", name, sn)
            #     data[sn] = inverter["invert_full"]

            # hasPowerflow = result["hasPowerflow"]
            # hasEnergeStatisticsCharts = result["hasEnergeStatisticsCharts"]

            # if hasPowerflow:
            #     if hasEnergeStatisticsCharts:
            #         StatisticsCharts = {
            #             f"Charts_{key}": val
            #             for key, val in result["energeStatisticsCharts"].items()
            #         }
            #         StatisticsTotals = {
            #             f"Totals_{key}": val
            #             for key, val in result["energeStatisticsTotals"].items()
            #         }
            #         powerflow = {
            #             **result["powerflow"],
            #             **StatisticsCharts,
            #             **StatisticsTotals,
            #         }
            #     else:
            #         powerflow = result["powerflow"]

            #     powerflow["sn"] = result["homKit"]["sn"]
            #     # _LOGGER.debug("homeKit sn: %s", result["homKit"]["sn"])
            #     data["homeKit"] = powerflow

            # _LOGGER.debug("Resulting data: %s", data)
            return data
        # except ApiError as err:
        except Exception as err:
            # logging.exception("Something awful happened!")
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="XOLTA API",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=update_interval,
    )

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    # _LOGGER.debug("Initial coordinator data: %s", coordinator.data)
    async_add_entities(
        [XoltaBatterySensor(coordinator, siteId), XoltaGridSensor(coordinator, siteId)]
        # for idx, ent in enumerate(coordinator.data)
    )
    # async_add_entities(
    #     SemsStatisticsSensor(coordinator, ent)
    #     for idx, ent in enumerate(coordinator.data)
    # )
    # async_add_entities(
    #     SemsPowerflowSensor(coordinator, ent)
    #     for idx, ent in enumerate(coordinator.data) if ent == "homeKit"
    # )
    # async_add_entities(
    #     SemsTotalImportSensor(coordinator, ent)
    #     for idx, ent in enumerate(coordinator.data) if ent == "homeKit"
    # )
    # async_add_entities(
    #     SemsTotalExportSensor(coordinator, ent)
    #     for idx, ent in enumerate(coordinator.data) if ent == "homeKit"
    # )


class XoltaBatterySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, site_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.site_id = site_id
        # self.sn = sn
        _LOGGER.debug("Creating XoltaBatterySensor with id %s", self.site_id)

    @property
    def device_class(self):
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        return PERCENTAGE

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        # return f"Battery {self.coordinator.data['site_data']['name']}"
        return f"Battery {self.site_id}"

    @property
    def unique_id(self) -> str:
        return f"{self.site_id}-battery"

    @property
    def state(self):
        """Return the state of the device."""
        data = self.coordinator.data["site_data"]
        return (
            data["bmsSocRawArrayCloudTrimmedAggAvg"]
            if data["state"] == "Running"
            else 0
        )

    def statusText(self, status) -> str:
        data = self.coordinator.data["site_data"]
        return data["state"]

    # For backwards compatibility
    @property
    def extra_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        data = self.coordinator.data["site_data"]
        # _LOGGER.debug("state, self data: %s", data.items())
        # attributes = {k: v for k, v in data.items() if k is not None and v is not None}
        attributes = {}
        attributes["statusText"] = data["state"]
        return attributes

    # @property
    # def is_on(self) -> bool:
    #     self.coordinator.data["site_data"]["state"] == "Running"

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        # _LOGGER.debug("self.device_state_attributes: %s", self.device_state_attributes)
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.site_id)
            },
            "name": self.name,
            "manufacturer": "Xolta",
            # "model": self.extra_state_attributes.get("model_type", "unknown"),
            # "sw_version": self.extra_state_attributes.get("firmwareversion", "unknown"),
            # "via_device": (DOMAIN, self.api.bridgeid),
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()


class XoltaGridSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, site_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.site_id = site_id
        # self.sn = sn
        _LOGGER.debug("Creating XoltaGridSensor with id %s", self.site_id)

    @property
    def device_class(self):
        return DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        return POWER_KILO_WATT

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        # return f"Battery {self.coordinator.data['site_data']['name']}"
        return f"Grid {self.site_id}"

    @property
    def unique_id(self) -> str:
        return f"{self.site_id}-grid"

    @property
    def state(self):
        """Return the state of the device."""
        data = self.coordinator.data["site_data"]
        return data["meterGridActivePowerAggAvg"] if data["state"] == "Running" else 0

    def statusText(self, status) -> str:
        data = self.coordinator.data["site_data"]
        return data["state"]

    # For backwards compatibility
    # @property
    # def extra_state_attributes(self):
    #     """Return the state attributes of the monitored installation."""
    #     data = self.coordinator.data[self.sn]
    #     # _LOGGER.debug("state, self data: %s", data.items())
    #     attributes = {k: v for k, v in data.items() if k is not None and v is not None}
    #     attributes["statusText"] = self.statusText(data["status"])
    #     return attributes

    @property
    def is_on(self) -> bool:
        self.coordinator.data["site_data"]["state"] == "Running"

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        # _LOGGER.debug("self.device_state_attributes: %s", self.device_state_attributes)
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.site_id)
            },
            "name": self.name,
            "manufacturer": "Xolta",
            # "model": self.extra_state_attributes.get("model_type", "unknown"),
            # "sw_version": self.extra_state_attributes.get("firmwareversion", "unknown"),
            # "via_device": (DOMAIN, self.api.bridgeid),
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()


# class XoltaSensor(CoordinatorEntity, SensorEntity):

#     def __init__(self, coordinator, sn):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator)
#         self.coordinator = coordinator
#         self.sn = sn
#         _LOGGER.debug("Creating XoltaSensor with id %s", self.sn)

#     @property
#     def device_class(self):
#         return DEVICE_CLASS_POWER

#     @property
#     def unit_of_measurement(self):
#         return POWER_WATT

#     @property
#     def name(self) -> str:
#         """Return the name of the sensor."""
#         return f"Inverter {self.coordinator.data[self.sn]['name']}"

#     @property
#     def unique_id(self) -> str:
#         return self.coordinator.data[self.sn]["sn"]

#     @property
#     def state(self):
#         """Return the state of the device."""
#         # _LOGGER.debug("state, coordinator data: %s", self.coordinator.data)
#         # _LOGGER.debug("self.sn: %s", self.sn)
#         # _LOGGER.debug(
#         #     "state, self data: %s", self.coordinator.data[self.sn]
#         # )
#         data = self.coordinator.data[self.sn]
#         return data["pac"] if data["status"] == 1 else 0

#     def statusText(self, status) -> str:
#         labels = {-1: "Offline", 0: "Waiting", 1: "Normal", 2: "Fault"}
#         return labels[status] if status in labels else "Unknown"

#     # For backwards compatibility
#     @property
#     def extra_state_attributes(self):
#         """Return the state attributes of the monitored installation."""
#         data = self.coordinator.data[self.sn]
#         # _LOGGER.debug("state, self data: %s", data.items())
#         attributes = {k: v for k, v in data.items() if k is not None and v is not None}
#         attributes["statusText"] = self.statusText(data["status"])
#         return attributes

#     @property
#     def is_on(self) -> bool:
#         """Return entity status."""
#         self.coordinator.data[self.sn]["status"] == 1

#     @property
#     def should_poll(self) -> bool:
#         """No need to poll. Coordinator notifies entity of updates."""
#         return False

#     @property
#     def available(self):
#         """Return if entity is available."""
#         return self.coordinator.last_update_success

#     @property
#     def device_info(self):
#         # _LOGGER.debug("self.device_state_attributes: %s", self.device_state_attributes)
#         return {
#             "identifiers": {
#                 # Serial numbers are unique identifiers within a specific domain
#                 (DOMAIN, self.sn)
#             },
#             "name": self.name,
#             "manufacturer": "GoodWe",
#             "model": self.extra_state_attributes.get("model_type", "unknown"),
#             "sw_version": self.extra_state_attributes.get("firmwareversion", "unknown"),
#             # "via_device": (DOMAIN, self.api.bridgeid),
#         }

#     async def async_added_to_hass(self):
#         """When entity is added to hass."""
#         self.async_on_remove(
#             self.coordinator.async_add_listener(self.async_write_ha_state)
#         )

#     async def async_update(self):
#         """Update the entity.

#         Only used by the generic entity update service.
#         """
#         await self.coordinator.async_request_refresh()


# class SemsStatisticsSensor(CoordinatorEntity, SensorEntity):
#     """Sensor in kWh to enable HA statistics, in the end usable in the power component."""

#     def __init__(self, coordinator, sn):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator)
#         self.coordinator = coordinator
#         self.sn = sn
#         _LOGGER.debug("Creating SemsStatisticsSensor with id %s", self.sn)

#     @property
#     def device_class(self):
#         return DEVICE_CLASS_ENERGY

#     @property
#     def unit_of_measurement(self):
#         return ENERGY_KILO_WATT_HOUR

#     @property
#     def name(self) -> str:
#         """Return the name of the sensor."""
#         return f"Inverter {self.coordinator.data[self.sn]['name']} Energy"

#     @property
#     def unique_id(self) -> str:
#         return f"{self.coordinator.data[self.sn]['sn']}-energy"

#     @property
#     def state(self):
#         """Return the state of the device."""
#         # _LOGGER.debug("state, coordinator data: %s", self.coordinator.data)
#         # _LOGGER.debug("self.sn: %s", self.sn)
#         # _LOGGER.debug(
#         #     "state, self data: %s", self.coordinator.data[self.sn]
#         # )
#         data = self.coordinator.data[self.sn]
#         return data["etotal"]

#     @property
#     def should_poll(self) -> bool:
#         """No need to poll. Coordinator notifies entity of updates."""
#         return False

#     @property
#     def device_info(self):
#         # _LOGGER.debug("self.device_state_attributes: %s", self.device_state_attributes)
#         data = self.coordinator.data[self.sn]
#         return {
#             "identifiers": {
#                 # Serial numbers are unique identifiers within a specific domain
#                 (DOMAIN, self.sn)
#             },
#             # "name": self.name,
#             "manufacturer": "GoodWe",
#             "model": data.get("model_type", "unknown"),
#             "sw_version": data.get("firmwareversion", "unknown"),
#             # "via_device": (DOMAIN, self.api.bridgeid),
#         }

#     @property
#     def state_class(self):
#         """used by Metered entities / Long Term Statistics"""
#         return STATE_CLASS_TOTAL_INCREASING

#     async def async_added_to_hass(self):
#         """When entity is added to hass."""
#         self.async_on_remove(
#             self.coordinator.async_add_listener(self.async_write_ha_state)
#         )

#     async def async_update(self):
#         """Update the entity.

#         Only used by the generic entity update service.
#         """
#         await self.coordinator.async_request_refresh()

# class SemsTotalImportSensor(CoordinatorEntity, SensorEntity):
#     """Sensor in kWh to enable HA statistics, in the end usable in the power component."""

#     def __init__(self, coordinator, sn):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator)
#         self.coordinator = coordinator
#         self.sn = sn
#         _LOGGER.debug("Creating SemsStatisticsSensor with id %s", self.sn)

#     @property
#     def device_class(self):
#         return DEVICE_CLASS_ENERGY

#     @property
#     def unit_of_measurement(self):
#         return ENERGY_KILO_WATT_HOUR

#     @property
#     def name(self) -> str:
#         """Return the name of the sensor."""
#         return f"HomeKit {self.coordinator.data[self.sn]['sn']} Import"

#     @property
#     def unique_id(self) -> str:
#         return f"{self.coordinator.data[self.sn]['sn']}-import-energy"

#     @property
#     def state(self):
#         """Return the state of the device."""
#         data = self.coordinator.data[self.sn]
#         return data["Totals_buy"]
#     def statusText(self, status) -> str:
#         labels = {-1: "Offline", 0: "Waiting", 1: "Normal", 2: "Fault"}
#         return labels[status] if status in labels else "Unknown"


#     @property
#     def should_poll(self) -> bool:
#         """No need to poll. Coordinator notifies entity of updates."""
#         return False

#     @property
#     def device_info(self):
#         return {
#             "identifiers": {
#                 # Serial numbers are unique identifiers within a specific domain
#                 (DOMAIN, self.sn)
#             },
#             "name": "Homekit",
#             "manufacturer": "GoodWe",
#         }

#     @property
#     def state_class(self):
#         """used by Metered entities / Long Term Statistics"""
#         return STATE_CLASS_TOTAL_INCREASING

#     async def async_added_to_hass(self):
#         """When entity is added to hass."""
#         self.async_on_remove(
#             self.coordinator.async_add_listener(self.async_write_ha_state)
#         )

#     async def async_update(self):
#         """Update the entity.

#         Only used by the generic entity update service.
#         """
#         await self.coordinator.async_request_refresh()

# class SemsTotalExportSensor(CoordinatorEntity, SensorEntity):
#     """Sensor in kWh to enable HA statistics, in the end usable in the power component."""

#     def __init__(self, coordinator, sn):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator)
#         self.coordinator = coordinator
#         self.sn = sn
#         _LOGGER.debug("Creating SemsStatisticsSensor with id %s", self.sn)

#     @property
#     def device_class(self):
#         return DEVICE_CLASS_ENERGY

#     @property
#     def unit_of_measurement(self):
#         return ENERGY_KILO_WATT_HOUR

#     @property
#     def name(self) -> str:
#         """Return the name of the sensor."""
#         return f"HomeKit {self.coordinator.data[self.sn]['sn']} Export"

#     @property
#     def unique_id(self) -> str:
#         return f"{self.coordinator.data[self.sn]['sn']}-export-energy"

#     @property
#     def state(self):
#         """Return the state of the device."""
#         data = self.coordinator.data[self.sn]
#         return data["Totals_sell"]
#     def statusText(self, status) -> str:
#         labels = {-1: "Offline", 0: "Waiting", 1: "Normal", 2: "Fault"}
#         return labels[status] if status in labels else "Unknown"

#     @property
#     def should_poll(self) -> bool:
#         """No need to poll. Coordinator notifies entity of updates."""
#         return False

#     @property
#     def device_info(self):
#         return {
#             "identifiers": {
#                 # Serial numbers are unique identifiers within a specific domain
#                 (DOMAIN, self.sn)
#             },
#             "name": "Homekit",
#             "manufacturer": "GoodWe",
#         }

#     @property
#     def state_class(self):
#         """used by Metered entities / Long Term Statistics"""
#         return STATE_CLASS_TOTAL_INCREASING

#     async def async_added_to_hass(self):
#         """When entity is added to hass."""
#         self.async_on_remove(
#             self.coordinator.async_add_listener(self.async_write_ha_state)
#         )

#     async def async_update(self):
#         """Update the entity.

#         Only used by the generic entity update service.
#         """
#         await self.coordinator.async_request_refresh()

# class SemsPowerflowSensor(CoordinatorEntity, SensorEntity):
#     """SemsPowerflowSensor using CoordinatorEntity.

#     The CoordinatorEntity class provides:
#       should_poll
#       async_update
#       async_added_to_hass
#       available
#     """

#     def __init__(self, coordinator, sn):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator)
#         self.coordinator = coordinator
#         self.sn = sn

#     @property
#     def device_class(self):
#         return DEVICE_CLASS_POWER

#     @property
#     def unit_of_measurement(self):
#         return POWER_WATT

#     @property
#     def name(self) -> str:
#         """Return the name of the sensor."""
#         return f"HomeKit {self.coordinator.data[self.sn]['sn']}"

#     @property
#     def unique_id(self) -> str:
#         return self.coordinator.data[self.sn]["sn"]

#     @property
#     def state(self):
#         """Return the state of the device."""
#         data = self.coordinator.data[self.sn]
#         load = data["load"]

#         if load:
#             load = load.replace('(W)', '')

#         return load if data["gridStatus"] == 1 else 0

#     def statusText(self, status) -> str:
#         labels = {-1: "Offline", 0: "Waiting", 1: "Normal", 2: "Fault"}
#         return labels[status] if status in labels else "Unknown"

#     # For backwards compatibility
#     @property
#     def extra_state_attributes(self):
#         """Return the state attributes of the monitored installation."""
#         data = self.coordinator.data[self.sn]

#         attributes = {k: v for k, v in data.items() if k is not None and v is not None}

#         attributes["pv"] = data["pv"].replace('(W)', '')
#         attributes["bettery"] = data["bettery"].replace('(W)', '')
#         attributes["load"] = data["load"].replace('(W)', '')
#         attributes["grid"] = data["grid"].replace('(W)', '')

#         attributes["statusText"] = self.statusText(data["gridStatus"])

#         if data['loadStatus'] == -1 :
#             attributes['PowerFlowDirection'] = 'Export %s' % data['grid']
#         if data['loadStatus'] == 1 :
#             attributes['PowerFlowDirection'] = 'Import %s' % data['grid']

#         return attributes

#     @property
#     def is_on(self) -> bool:
#         """Return entity status."""
#         self.coordinator.data[self.sn]["gridStatus"] == 1

#     @property
#     def should_poll(self) -> bool:
#         """No need to poll. Coordinator notifies entity of updates."""
#         return False

#     @property
#     def available(self):
#         """Return if entity is available."""
#         return self.coordinator.last_update_success

#     @property
#     def device_info(self):
#         return {
#             "identifiers": {
#                 # Serial numbers are unique identifiers within a specific domain
#                 (DOMAIN, self.sn)
#             },
#             "name": "Homekit",
#             "manufacturer": "GoodWe",
#         }

#     async def async_added_to_hass(self):
#         """When entity is added to hass."""
#         self.async_on_remove(
#             self.coordinator.async_add_listener(self.async_write_ha_state)
#         )

#     async def async_update(self):
#         """Update the entity.

#         Only used by the generic entity update service.
#         """
#         await self.coordinator.async_request_refresh()

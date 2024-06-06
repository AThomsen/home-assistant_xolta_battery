from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.exceptions import ConfigEntryAuthFailed
import logging

from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.const import (
    PERCENTAGE
)
from .const import DOMAIN, UPDATE_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    xoltaApi = hass.data[DOMAIN][config_entry.entry_id]

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
            result = await xoltaApi.get_data()
            return result

        except ConfigEntryAuthFailed as err:
            raise

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

    for site in coordinator.data["sites"]:
        siteId = site["siteId"]
        async_add_entities(
            [
                XoltaSensor(
                    coordinator,
                    siteId,
                    "Battery power flow",
                    SensorDeviceClass.POWER,
                    UnitOfPower.KILO_WATT,
                    # negative means charging, positive means discharging
                    "inverterActivePowerAggAvg",
                ),
                XoltaSensor(
                    coordinator,
                    siteId,
                    "PV power",
                    SensorDeviceClass.POWER,
                    UnitOfPower.KILO_WATT,
                    "meterPvActivePowerAggAvg",
                ),
                XoltaSensor(
                    coordinator,
                    siteId,
                    "Power consumption",
                    SensorDeviceClass.POWER,
                    UnitOfPower.KILO_WATT,
                    "consumption",
                ),
                XoltaSensor(
                    coordinator,
                    siteId,
                    "Battery charge level",
                    SensorDeviceClass.BATTERY,
                    PERCENTAGE,
                    "bmsSocRawArrayCloudTrimmedAggAvg",
                ),
                XoltaSensor(
                    coordinator,
                    siteId,
                    "Grid power flow",
                    SensorDeviceClass.POWER,
                    UnitOfPower.KILO_WATT,
                    # negative means sell, positive means buy
                    "meterGridActivePowerAggAvg",
                ),
                # Energy sensors:
                XoltaEnergySensor(
                    coordinator,
                    siteId,
                    "Grid energy imported",
                    "grid_imported",
                ),
                XoltaEnergySensor(
                    coordinator,
                    siteId,
                    "Grid energy exported",
                    "grid_exported",
                ),
                XoltaEnergySensor(
                    coordinator,
                    siteId,
                    "Battery energy charged",
                    "battery_charged",
                ),
                XoltaEnergySensor(
                    coordinator,
                    siteId,
                    "Battery energy discharged",
                    "battery_discharged",
                ),
                XoltaEnergySensor(
                    coordinator,
                    siteId,
                    "PV energy",
                    "pv",
                ),
                XoltaEnergySensor(
                    coordinator,
                    siteId,
                    "Energy consumption",
                    "consumption",
                ),
            ]
        )


class XoltaBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self, coordinator, site_id, sensor_type  # , device_class, units, data_property
    ):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._site_id = site_id
        self._sensor_type = sensor_type
        # self._units = units
        # self._data_property = data_property

    # @property
    # def unit_of_measurement(self):
    #     return self._units

    @property
    def name(self) -> str:
        return f"{self._sensor_type}"

    # @property
    # def unique_id(self) -> str:
    #     return f"{self._site_id}-energy-{self._sensor_type}"

    # def statusText(self, status) -> str:
    #     data = self.coordinator.data["sensors"]
    #     return data["state"]

    # # For backwards compatibility
    # @property
    # def extra_state_attributes(self):
    #     """Return the state attributes of the monitored installation."""
    #     data = self.coordinator.data["sensors"]
    #     # _LOGGER.debug("state, self data: %s", data.items())
    #     # attributes = {k: v for k, v in data.items() if k is not None and v is not None}
    #     attributes = {}
    #     attributes["statusText"] = data["state"]
    #     return attributes

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
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._site_id)
            },
            "name": f"Battery {self._site_id}",
            "manufacturer": "Xolta",
            "model": "Battery",
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


class XoltaSensor(XoltaBaseSensor):
    def __init__(
        self, coordinator, site_id, sensor_type, device_class, units, data_property
    ):
        super().__init__(coordinator, site_id, sensor_type)
        self.coordinator = coordinator
        self.entity_id = f"sensor.{self._site_id}_{self._sensor_type}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = units
        self._data_property = data_property
        _LOGGER.debug("Creating XoltaBatterySensor with id %s", self._site_id)

    @property
    def unique_id(self) -> str:
        return f"{self._site_id}-{self._sensor_type}"

    @property
    def state(self):
        data = self.coordinator.data["sensors"][self._site_id]
        return data[self._data_property] if data["state"] == "Running" else 0

    # For backwards compatibility
    @property
    def extra_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        data = self.coordinator.data["sensors"][self._site_id]
        attributes = {}
        attributes["statusText"] = data["state"]
        return attributes


class XoltaEnergySensor(XoltaBaseSensor):

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, site_id, sensor_type, data_property):
        super().__init__(coordinator, site_id, sensor_type)
        self.entity_id = f"sensor.{self._site_id}_energy_{self._sensor_type}"
        self._data_property = data_property

    @property
    def unique_id(self) -> str:
        return f"{self._site_id}-energy-{self._sensor_type}"

    @property
    def native_value(self) -> float:
        data = self.coordinator.data["energy"][self._site_id]
        return data[self._data_property]

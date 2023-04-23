# Xolta Solar Battery for Home Assistant

Unofficial integration for Xolta Solar battery.

Uses the existing api of the web app as it seems no public api is available.

## Installation

The integration requires a [helper-add-on](https://github.com/AThomsen/home-assistant_xolta_battery_authentication-addon) that takes care of getting an API access token from a username and password. Install this first. Make sure to enable *Start at boot*.

Then Install integration using HACS: HACS -> Integrations -> (kebab menu) -> Custom repositories -> Repsitory `https://github.com/AThomsen/home-assistant_xolta_battery` Category: Integration.


## Example usage

Example of using the integration with the [tesla-style-solar-power-card](https://github.com/reptilex/tesla-style-solar-power-card) (update repo [here](https://github.com/matban666/tesla-style-solar-power-card)).

Start with adding some templates - replace `<replace-with-id>` with your battery id:

~~~yaml
template:
  - sensor:
      - name: "Xolta Card Grid Consumption"
        unique_id: "xolta_card_grid_consumption"
        state: "{{ (states('sensor.<replace-with-id>_power_consumption') | float(0)) - (states('sensor.xolta_card_solar_consumption') | float(0)) - (states('sensor.xolta_card_battery_consumption') | float(0)) | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Card Grid Feed In"
        unique_id: "xolta_card_grid_feed_in"
        state: "{{ [[ -(states('sensor.<replace-with-id>_grid_power_flow') | float(0)), 0.0 ] | max, (states('sensor.<replace-with-id>_pv_power') | float(0)) - (states('sensor.xolta_card_solar_consumption') | float(0)) - (states('sensor.xolta_card_battery_charging_from_pv') | float(0))] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Card Solar Consumption"
        unique_id: "xolta_card_solar_consumption"
        state: "{{ [states('sensor.<replace-with-id>_pv_power') | float(0), states('sensor.<replace-with-id>_power_consumption') | float(0)] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Card Battery Consumption"
        unique_id: "xolta_card_battery_consumption"
        state: "{{ [ ([states('sensor.<replace-with-id>_battery_power_flow') | float(0), 0.0] | max),  (states('sensor.<replace-with-id>_power_consumption') | float(0)) - (states('sensor.xolta_card_solar_consumption') | float(0)) ] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Card Battery Charging from PV"
        unique_id: "xolta_card_battery_charging_from_pv"
        state: "{{ [ (states('sensor.<replace-with-id>_pv_power') | float(0)) - (states('sensor.xolta_card_solar_consumption') | float(0)), [0.0, -(states('sensor.<replace-with-id>_battery_power_flow') | float(0))] | max] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Card Battery Charging from grid"
        unique_id: "xolta_card_battery_charging_from_grid"
        state: "{{ (([-(states('sensor.<replace-with-id>_battery_power_flow') | float(0)), 0] | max) - (states('sensor.xolta_card_battery_charging_from_pv') | float(0)) ) | round(1) }}"
        device_class: power
        unit_of_measurement: kW
~~~

Then do the card configuration:

~~~yaml
type: custom:tesla-style-solar-power-card
name: My Flows
generation_to_house_entity: sensor.xolta_card_solar_consumption
generation_to_battery_entity: sensor.xolta_card_battery_charging_from_pv
grid_to_battery_entity: sensor.xolta_card_battery_charging_from_grid
battery_to_house_entity: sensor.xolta_card_battery_consumption
grid_to_house_entity: sensor.xolta_card_grid_consumption
generation_to_grid_entity: sensor.xolta_card_grid_feed_in
battery_extra_entity: sensor.<replace-with-id>_battery_charge_level
generation_icon: mdi:solar-power
grid_extra_entity: sensor.elpris  # <-- optional - for use with https://github.com/MTrab/energidataservice
show_gap: true
~~~
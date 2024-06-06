# Xolta Solar Battery for Home Assistant

**Unofficial integration for Xolta Solar battery 🔋☀️**

Uses the existing api of the web app as it seems no public api is available.

## Installation

⚠️ IMPORTANT ⚠️  
The integration requires a [helper-add-on](https://github.com/AThomsen/home-assistant_xolta_battery_authentication-addon) that takes care of getting an API access token from a username and password. Install this first. Make sure to enable *Start at boot*.

Then Install integration using HACS: HACS -> Integrations -> (kebab menu) -> Custom repositories -> Repsitory `https://github.com/AThomsen/home-assistant_xolta_battery` Category: Integration.


## Example usage

### Power flow card plus

Example of using the integration with the [power-flow-card-plus](https://github.com/flixlix/power-flow-card-plus).

It shows the current flow of power in a card similar to the one in Home Assistant showing todays energy flow.

~~~yaml
type: custom:power-flow-card-plus
entities:
  battery:
    entity: sensor.<replace-with-id>_battery_power_flow
    state_of_charge: sensor.<replace-with-id>_battery_charge_level
  grid:
    entity: sensor.<replace-with-id>_grid_power_flow
    name: Grid
    secondary_info:
      # optional - for use with https://github.com/MTrab/energidataservice
      entity: sensor.elpris
      unit_of_measurement: # currency
      decimals: 2
      display_zero: true
      unit_white_space: false
      color_value: false
  solar:
    entity: sensor.<replace-with-id>_pv_power
    display_zero_state: true
    name: Solar
    use_metadata: false
    color_value: true
  home:
    entity: sensor.<replace-with-id>_power_consumption
clickable_entities: true
use_new_flow_rate_model: true
dashboard_link: /energy
title: Flow
~~~


### Some helper templates

Here are some power template sensors that may be useful.

They assume that power is consumed from the following sources in order: solar, battery, grid.

~~~yaml
template:
  - sensor:
      - name: "Xolta Grid Consumption"
        # Amount of currently consumed power imported from grid.
        unique_id: "xolta_grid_consumption"
        state: "{{ (states('sensor.<replace-with-id>_power_consumption') | float(0)) - (states('sensor.xolta_solar_consumption') | float(0)) - (states('sensor.xolta_battery_consumption') | float(0)) | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Grid Feed In"
        # Power currently exported to grid
        unique_id: "xolta_grid_feed_in"
        state: "{{ [[ -(states('sensor.<replace-with-id>_grid_power_flow') | float(0)), 0.0 ] | max, (states('sensor.<replace-with-id>_pv_power') | float(0)) - (states('sensor.xolta_solar_consumption') | float(0)) - (states('sensor.xolta_battery_charging_from_pv') | float(0))] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Solar Consumption"
        # Amount of currently consumed power coming from solar.
        unique_id: "xolta_solar_consumption"
        state: "{{ [states('sensor.<replace-with-id>_pv_power') | float(0), states('sensor.<replace-with-id>_power_consumption') | float(0)] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Battery Consumption"
        # Amount of currently consumed power coming from battery.
        unique_id: "xolta_battery_consumption"
        state: "{{ [ ([states('sensor.<replace-with-id>_battery_power_flow') | float(0), 0.0] | max),  (states('sensor.<replace-with-id>_power_consumption') | float(0)) - (states('sensor.xolta_solar_consumption') | float(0)) ] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Battery Charging from PV"
        # Amount of solar power currently used to charge battery.
        unique_id: "xolta_battery_charging_from_pv"
        state: "{{ [ (states('sensor.<replace-with-id>_pv_power') | float(0)) - (states('sensor.xolta_solar_consumption') | float(0)), [0.0, -(states('sensor.<replace-with-id>_battery_power_flow') | float(0))] | max] | min | round(1) }}"
        device_class: power
        unit_of_measurement: kW

      - name: "Xolta Battery Charging from grid"
        # Amount of grid power currently used to charge battery.
        unique_id: "xolta_battery_charging_from_grid"
        state: "{{ (([-(states('sensor.<replace-with-id>_battery_power_flow') | float(0)), 0] | max) - (states('sensor.xolta_battery_charging_from_pv') | float(0)) ) | round(1) }}"
        device_class: power
        unit_of_measurement: kW
~~~

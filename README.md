[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Irrigation Estimator

**_Note_ This is not updated.**

Smart Irrigation custom component for Home Assistant. Partly based on the excellent work at https://github.com/hhaim/hass/.
This component calculates the time to run your irrigation system to compensate for moisture lost by evaporation / evapotranspiration. Using this component you water your garden, lawn or crops precisely enough to compensate what has evaporated. It takes into account precipitation (rain,snow) and adjusts accordingly, so if it rains or snows less or no irrigation is required. By adding multiple instances of this component multiple zones can be supported as each zone will have its own sprinkler and flow configuration.

> **Note - use this component at your own risk - we do not assume responsibility for any inconvience caused by using this component. Always use common sense before deciding to irrigate using the calculations this component provides. For example, irrigating during excessive rainfall might cause flooding. Again - we assume no responsibility for any inconvience caused.**

The component keeps track of hourly precipitation and at 23:00 (11:00 PM) local time stores it in a daily value.
It then calculates the exact runtime in seconds to compensate for the net evaporation.
Note that this is the default behavior and this can be disabled if you want more control. Also, the time auto refresh happens (if not disabled) is configurable.
This is all the component does, and this is on purpose to provide maximum flexibility. Users are expected to use the value of `sensor.smart_irrigation.daily_adjusted_run_time` to interact with their irrigation system and afterwards call the `smart_irrigation.reset_bucket` service. [See the example automations below](#step-3-creating-automation).

This component uses reference evapotranspiration values and calculates base schedule indexes and water budgets from that. This is an industry-standard approach. Information can be found at https://www.rainbird.com/professionals/irrigation-scheduling-use-et-save-water, amongst others.
The component uses the [PyETo module to calculate the evapotranspiration value (fao56)](https://pyeto.readthedocs.io/en/latest/fao56_penman_monteith.html). Also, please see the [How this works](https://github.com/jeroenterheerdt/HAsmartirrigation/wiki/How-this-component-works) Wiki page.

## Visual representation of what this component does

![](images/smart_irrigation_diagram.png?raw=true)

1. Snow and rain fall on the ground add moisture. This is tracked /predicted hourly depending on the [operation mode](#operation-modes) by the `rain` and `snow` attributes Together, this makes up the `precipitation`.
2. Sunshine, temperature, wind speed, place on earth and other factors influence the amount of moisture lost from the ground(`evapotranspiration`). This is tracked / predicted hourly depending on the [operation mode](#operation-modes).
3. The difference between `precipitation` and `evapotranspiration` is the `netto precipitation`: negative values mean more moisture is lost than gets added by rain/snow, while positive values mean more moisture is added by rain/snow than what evaporates.
4. Once a day (time is configurable) the `netto precipitation` is added/substracted from the `bucket,` which starts as empty. If the `bucket` is below zero, irrigation is required.
5. Irrigation should be run for `daily_adjusted_run_time` amount of time (which is 0 is `bucket`>=0). Afterwards, the `bucket` needs to be reset (using `reset_bucket`). It's up to the user of the component to build the automation for this final step.

There are many more options available, see below. To understand how `precipitation`, `netto precipitation`, the `bucket` and irrigation interact, see [example behavior on the Wiki](https://github.com/jeroenterheerdt/HAsmartirrigation/wiki/Example-behavior-in-a-week).

## Getting the best results

In order to get the most accurate results using sensors is preferable either from your own weather station or from another, from example through [Weatherflow Smart Weather](https://github.com/briis/smartweather). If you have a weather station that provides evapotranspiration (ET) values, use that (mode 4). If you do not have that, use sensors including solar radiation (mode 3). If you do not have access to a sensor that provides solar radiation, let this component estimate it but use sensors for the other inputs (modified mode 3). If you do have access to limited amount of sensors (say only temperature) use that and use Open Weather Map for the rest (mode 2). If you do not have access to any sensors at all use Open Weather Map (mode 1).

Since this component provides multiple configuration options it might get confusing about in which scenario what behavior can be expected and what input is required. In the table below we summarize the configuration modes, their accuracy, the required input and how daily adjusted run time is calculated. Keep in mind that daily adjusted run time is based on the netto precipitation (precipitation - evapotranspiration) and the bucket value for previous days.
|Mode|Accuracy|Input|How adjusted run time is calculated|
|---|---|---|---|
|Mode 1 - Full Open Weather Map|Low|No sensor input required, just an API key for Open Weather Map|Average of precipitation and evapotranspiration.|
|Mode 2 - Full Sensor, but calculating evapotranspiration|High|Sensors are required for all inputs. All inputs are expected to be point-in-time, _except precipitation_. That sensor is normally provided by a weather station or weather service as a daily accumulative / 'total precipitation today' sensor and that is what is expected by the component|Most recent value for precipitation and average of evapotranspiration.
|Mode 3 - Mixed|Medium|API key is required for any inputs that have not been provided sensors. All inputs are expected to be point-in-time, _except precipitation_. That sensor is normally provided by a weather station or weather service as a 'total precipitation today' sensor and that is what is expected by the component|If a sensor is provided for precipitation, most recent value for precipitation is used. Otherwise the average of both precipitation and evapotranspiration.|

## Configuration

In this section:

- [One-time set up](#step-1-configuration-of-component)
- [List of events, services entities and attributes created](#step-2-checking-entities)
- [Example automation](#step-3-creating-automation)

### Step 1: configuration of component

Install the custom component (preferably using HACS) and then use the Configuration --> Integrations pane to search for 'Smart Irrigation'.
You will need to specify the following:

- Names of sensors that supply required measurements (optional). Only required in mode 2) and 3). See [Measurements and Units](https://github.com/jeroenterheerdt/HAsmartirrigation/wiki/Measurements-and-Units) for more information on the measurements and units expected by this component.
- API Key for Open Weather Map (optional). Only required in mode 1) and 3). See [Getting Open Weater Map API Key](#getting-open-weather-map-api-key) below for instructions.
- Reference Evapotranspiration for all months of the year. See [Getting Monthly ET values](#getting-monthly-et-values) below for instructions. Note that you can specify these in inches or mm, depending on your Home Assistant settings.
- Number of sprinklers in your irrigation system
- Flow per spinkler in gallons per minute or liters per minute. Refer to your sprinkler's manual for this information.
- Area that the sprinklers cover in square feet or m<sup>2</sup>
  After setting up the component, you can use the options flow to configure the following:
  | Option | Description | Default |
  | --- | --- | --- |
  |Maximum duration| Maximum duration in seconds for any irrigation, including any `lead_time`. -1 means no maximum.|-1|
  |Solar Radiation calculation|From v0.0.50 onwards, the component estimates solar radiation using temperature, which seems to be more accurate. If for whatever reason you wanted to revert back to the pre v0.0.50 behavior (which used a estimation of sun hours) disable this.|True|

### Step 2: checking services, events and entities

After successful configuration, you should end up with three entities and their attributes, listed below as well as [three services](#available-services).

#### Services

For each instance of the component the following services will be available:
| Service | Description|
| --- | --- |
|`smart_irrigation.]instance]_reset_bucket`|Resets the bucket to 0. Needs to be called after done irrigating (see below).|

#### Entities

#### `sensor.smart_irrigation_base_schedule_index`

The number of seconds the irrigation system needs to run assuming maximum evapotranspiration and no rain / snow. This value and the attributes are static for your configuration.
Attributes:
| Attribute | Description |
| --- | --- |
|`number of sprinklers`|number of sprinklers in the system|
|`flow`|amount of water that flows through a single sprinkler in liters or gallon per minute|
|`throughput`|total amount of water that flows through the irrigation system in liters or gallon per minute.|
|`area`|the total area the irrigation system reaches in m<sup>2</sup> or sq ft.|
|`precipitation rate`|the output of the irrigation system across the whole area in mm or inch per hour|

Sample screenshot:

![](images/bsi_entity.png?raw=true)

#### `sensor.smart_irrigation_hourly_adjusted_run_time`

The adjusted run time in seconds to compensate for any net moisture lost. Updated approx. every 60 minutes.
Attributes:
| Attribute | Description |
| --- | --- |
|`precipitation`|the total precipitation (which is the sum of `rain` and `snow` in mm or inch)|
|`evapotranspiration`|the expected evapotranspiration|
|`netto precipitation`|the net evapotranspiration in mm or inch, negative values mean more moisture is lost than gets added by rain/snow, while positive values mean more moisture is added by rain/snow than what evaporates, equal to `precipitation - evapotranspiration`|
|`adjusted run time minutes`|adjusted run time in minutes instead of seconds.|

Sample screenshot:

![](images/hart.png?raw=true)

#### `sensor.smart_irrigation_daily_adjusted_run_time`

The adjusted run time in seconds to compensate for any net moisture lost. Updated every day at 11:00 PM / 23:00 hours local time. Use this value for your automation (see step 3, below).
Attributes:
| Attribute | Description |
| --- | --- |
|`bucket`|running total of net precipitation. Negative values mean that irrigation is required. Positive values mean that more moisture was added than has evaporated yet, so irrigation is not required. Should be reset to `0` after each irrigation, using the `smart_irrigation.reset_bucket` service|
|`maximum_duration`|maximum duration in seconds for any irrigation, including any `lead_time`.|
|`adjusted run time minutes`|adjusted run time in minutes instead of seconds.|

You will use `sensor.smart_irrigation_daily_adjusted_run_time` to create an automation (see step 3, below).

### Step 3: creating automation

Since this component does not interface with your irrigation system directly, you will need to use the data it outputs to create an automation that will start and stop your irrigation system for you. This way you can use this custom component with any irrigation system you might have, regardless of how that interfaces with Home Assistant. In order for this to work correctly, you should base your automation on the value of `sensor.smart_irrigation_daily_adjusted_run_time` as long as you run your automation after it was updated (11:00 PM / 23:00 hours local time). If that value is above 0 it is time to irrigate. Note that the value is the run time in seconds. Also, after irrigation, you need to call the `smart_irrigation.reset_bucket` service to reset the net irrigation tracking to 0.

> **The last step in any automation is very important, since you will need to let the component know you have finished irrigating and the evaporation counter can be reset by calling the `smart_irrigation.reset_bucket` service**

#### Example automation 1: one valve, potentially daily irrigation

Here is an example automation that runs when the `smart_irrigation_start` event is fired. It checks if `sensor.smart_irrigation_daily_adjusted_run_time` is above 0 and if it is it turns on `switch.irrigation_tap1`, waits the number of seconds as indicated by `sensor.smart_irrigation_daily_adjusted_run_time` and then turns off `switch.irrigation_tap1`. Finally, it resets the bucket by calling the `smart_irrigation.reset_bucket` service. If you have multiple instances you will need to adjust the event, entities and service names accordingly.

```
- alias: Smart Irrigation
  description: 'Start Smart Irrigation at 06:00 and run it only if the adjusted_run_time is >0 and run it for precisely that many seconds'
  trigger:
   - event_data: {}
     event_type: smart_irrigation_start
     platform: event
  condition:
  - above: '0'
    condition: numeric_state
    entity_id: sensor.smart_irrigation_daily_adjusted_run_time
  action:
  - data: {}
    entity_id: switch.irrigation_tap1
    service: switch.turn_on
  - delay:
      seconds: '{{states("sensor.smart_irrigation_daily_adjusted_run_time")}}'
  - data: {}
    entity_id: switch.irrigation_tap1
    service: switch.turn_off
  - data: {}
    service: smart_irrigation.reset_bucket
```

[See more advanced examples in the Wiki](https://github.com/jeroenterheerdt/HAsmartirrigation/wiki/Automation-examples).

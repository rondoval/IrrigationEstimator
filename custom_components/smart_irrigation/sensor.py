"""Sensor platform for Smart Irrigation."""
import datetime
import asyncio
import logging

from homeassistant.core import callback, Event
from homeassistant.const import CONF_ICON

from .const import (
    DOMAIN,
    ICON,
    CONF_NUMBER_OF_SPRINKLERS,
    CONF_FLOW,
    CONF_THROUGHPUT,
    CONF_AREA,
    CONF_PRECIPITATION_RATE,
    CONF_PRECIPITATION,
    CONF_NETTO_PRECIPITATION,
    CONF_EVAPOTRANSPIRATION,
    CONF_RAIN,
    CONF_SNOW,
    CONF_BUCKET,
    EVENT_BUCKET_UPDATED,
    CONF_MAXIMUM_DURATION,
    CONF_ADJUSTED_RUN_TIME_MINUTES,
    EVENT_HOURLY_DATA_UPDATED,
    KMH_TO_MS_FACTOR,
    CONF_SPRINKLER_ICON,
    W_TO_J_DAY_FACTOR,
    J_TO_MJ_FACTOR,
    CONF_SENSOR_PRECIPITATION,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_WINDSPEED,
    CONF_SENSOR_SOLAR_RADIATION,
)
from .entity import SmartIrrigationEntity
from .helpers import estimate_fao56_daily

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # async_add_devices([SmartIrrigationSensor(coordinator, entry)])
    async_add_devices(
        [
            SmartIrrigationSensor(
                hass, coordinator, entry, TYPE_CURRENT_ADJUSTED_RUN_TIME
            ),
            SmartIrrigationSensor(hass, coordinator, entry, TYPE_ADJUSTED_RUN_TIME),
        ]
    )


class SmartIrrigationSensor(SmartIrrigationEntity):
    """SmartIrrigation Sensor class."""

    def __init__(self, hass, coordinator, entity, thetype):
        """Initialize SmartIrrigation Sensor."""
        super(SmartIrrigationSensor, self).__init__(coordinator, entity, thetype)
        self._unit_of_measurement = UNIT_OF_MEASUREMENT_SECONDS
        self._state = 0.0
        if self.type == TYPE_CURRENT_ADJUSTED_RUN_TIME:
            self.precipitation = 0.0
            self.rain = 0.0
            self.snow = 0.0
            self.evapotranspiration = 0.0
            self.bucket_delta = 0
        if self.type == TYPE_ADJUSTED_RUN_TIME:
            self.bucket = 0

    @asyncio.coroutine
    async def async_added_to_hass(self):
        """Complete the initialization."""
        await super().async_added_to_hass()
        # register this sensor in the coordinator
        self.coordinator.register_entity(self.type, self.entity_id)

        # listen to the bucket update event and force mode toggle event only for the adjusted run time sensor
        if self.type == TYPE_ADJUSTED_RUN_TIME:
            event_to_listen = f"{self.coordinator.name}_{EVENT_BUCKET_UPDATED}"
            self.hass.bus.async_listen(
                event_to_listen,
                lambda event: self._bucket_updated(  # pylint: disable=unnecessary-lambda
                    event
                ),
            )
        # listen to the hourly data updated event only for the current adjusted run time sensor
        if self.type == TYPE_CURRENT_ADJUSTED_RUN_TIME:
            event_to_listen = f"{self.coordinator.name}_{EVENT_HOURLY_DATA_UPDATED}"
            self.hass.bus.async_listen(
                event_to_listen,
                lambda event: self._hourly_data_updated(  # pylint: disable=unnecessary-lambda
                    event
                ),
            )

        state = await self.async_get_last_state()
        if (  # pylint: disable=too-many-nested-blocks
            state is not None and state.state != "unavailable"
        ):
            self._state = float(state.state)
            confs = (
                CONF_EVAPOTRANSPIRATION,
                CONF_NETTO_PRECIPITATION,
                CONF_PRECIPITATION,
                CONF_RAIN,
                CONF_SNOW,
                CONF_BUCKET,
                CONF_ADJUSTED_RUN_TIME_MINUTES,
            )
            for attr in confs:
                if attr in state.attributes:
                    try:
                        a_val = state.attributes[attr]
                        numeric_part = float(a_val)
                        if attr in (
                            CONF_EVAPOTRANSPIRATION,
                            CONF_NETTO_PRECIPITATION,
                            CONF_PRECIPITATION,
                            CONF_RAIN,
                            CONF_SNOW,
                            CONF_BUCKET,
                        ):
                            # we need to convert this back and forth from imperial to metric...
                            if attr == CONF_EVAPOTRANSPIRATION:
                                self.evapotranspiration = numeric_part
                            elif attr == CONF_NETTO_PRECIPITATION:
                                self.bucket_delta = numeric_part
                            elif attr == CONF_PRECIPITATION:
                                self.precipitation = numeric_part
                            elif attr == CONF_RAIN:
                                self.rain = numeric_part
                            elif attr == CONF_SNOW:
                                self.snow = numeric_part
                            elif attr == CONF_BUCKET:
                                self.bucket = numeric_part
                                self.coordinator.bucket = self.bucket
                        # set the attribute
                        setattr(self, attr, f"{numeric_part}")

                    except Exception as ex:  # pylint: disable=broad-except
                        _LOGGER.error(ex)

    def update_adjusted_run_time_from_event(self):
        """Update the adjusted run time. Should only be called from _bucket_update and _force_mode_toggled event handlers."""
        result = self.calculate_water_budget_and_adjusted_run_time(
            self.bucket, self.type
        )
        art_entity_id = self.coordinator.entities[TYPE_ADJUSTED_RUN_TIME]
        attr = self.get_attributes_for_daily_adjusted_run_time(self.bucket, result)
        self.hass.states.set(
            art_entity_id,
            result,
            attr,
        )

    @callback
    def _bucket_updated(self, event: Event):
        """Receive the bucket updated event."""
        # update the sensor status.
        event_dict = event.as_dict()
        self.bucket = float(event_dict["data"][CONF_BUCKET])
        self.update_adjusted_run_time_from_event()

    @callback
    def _hourly_data_updated(self, event: Event):
        """Receive the hourly data updated event."""
        self._state = self.update_state()
        self.hass.add_job(self.async_update_ha_state)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.type}"

    def update_state(self):
        """Update the state."""
        # hourly adjusted run time
        if self.type == TYPE_CURRENT_ADJUSTED_RUN_TIME:
            data = {}
            # retrieve the data from the sensors (if set) and build the data or overwrite what we got from the API
            if self.coordinator.sensors:
                for sensor, entity in self.coordinator.sensors.items():
                    # this is a sensor we will need to use.
                    sensor_state = self.hass.states.get(entity)
                    if sensor_state is not None:
                        sensor_state = sensor_state.state

                        if sensor == CONF_SENSOR_PRECIPITATION:
                            # get precipitation from sensor, assuming there is no separate snow sensor
                            data["snow"] = 0.0
                            # metric: mm, imperial: inch
                            data["rain"] = sensor_state
                        if sensor == CONF_SENSOR_HUMIDITY:
                            rh_min = sensor_state
                            rh_max = sensor_state
                        if sensor == CONF_SENSOR_MAXIMUM_TEMPERATURE:
                            t_max = sensor_state
                        if sensor == CONF_SENSOR_MINIMUM_TEMPERATURE:
                            t_min = sensor_state
                        if sensor == CONF_SENSOR_PRESSURE:
                            pressure = sensor_state
                        if sensor == CONF_SENSOR_WINDSPEED:
                            wind_speed = float(sensor_state / KMH_TO_MS_FACTOR)
                        if sensor == CONF_SENSOR_SOLAR_RADIATION:
                            # get the solar radiation from sensor
                            # metric: W/m2, imperial: W/sq ft
                            # store in: MJ/m2
                            solrad = float(sensor_state * W_TO_J_DAY_FACTOR)
                            solrad = float(solrad / J_TO_MJ_FACTOR)
                            data["solar_radiation"] = solrad

            # parse precipitation out of the today data
            self.precipitation = self.get_precipitation(data)
            # calculate et out of the today data or from sensor if that is the configuration
            self.evapotranspiration = estimate_fao56_daily(
                datetime.datetime.now().timetuple().tm_yday,
                self.coordinator.latitude,
                self.coordinator.elevation,
                wind_meas_height,
                t_min,
                t_max,
                rh_min,
                rh_max,
                pressure,
                wind_speed,
                sunshine_hours,
            )

            # calculate the adjusted runtime!
            self.bucket_delta = self.precipitation - self.evapotranspiration

            result = self.calculate_water_budget_and_adjusted_run_time(
                self.bucket_delta, self.type
            )
            return result

        # daily adjusted run time
        result = self.calculate_water_budget_and_adjusted_run_time(
            self.coordinator.bucket, self.type
        )
        return result

    @property
    def state(self):
        """Return the state of the sensor."""
        self._state = self.update_state()
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the sensor."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.type == TYPE_CURRENT_ADJUSTED_RUN_TIME:
            return {
                CONF_RAIN: self.rain,
                CONF_SNOW: self.snow,
                CONF_PRECIPITATION: self.precipitation,
                CONF_EVAPOTRANSPIRATION: self.evapotranspiration,
                CONF_NETTO_PRECIPITATION: self.bucket_delta,
            }
        return {
            CONF_NUMBER_OF_SPRINKLERS: self.coordinator.number_of_sprinklers,
            CONF_FLOW: self.coordinator.flow,
            CONF_THROUGHPUT: self.coordinator.throughput,
            CONF_AREA: self.coordinator.area,
            CONF_PRECIPITATION_RATE: self.coordinator.precipitation_rate,
            CONF_BUCKET: self.bucket,
            CONF_MAXIMUM_DURATION: self.coordinator.maximum_duration,
            CONF_ICON: CONF_SPRINKLER_ICON,
        }

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    def get_precipitation(self, data):
        """Parse out precipitation info from OWM data."""
        if data is not None:
            # if rain or snow are missing from the OWM data set them to 0
            if "rain" in data:
                self.rain = float(data["rain"])
            else:
                self.rain = 0
            if "snow" in data:
                self.snow = float(data["snow"])
            else:
                self.snow = 0
            _LOGGER.info(
                "rain: {}, snow: {}".format(  # pylint: disable=logging-format-interpolation
                    self.rain, self.snow
                )
            )
            if isinstance(self.rain, str):
                self.rain = 0
            if isinstance(self.snow, str):
                self.snow = 0
            retval = self.rain + self.snow
            if isinstance(retval, str):
                if retval.count(".") > 1:
                    retval = retval.split(".")[0] + "." + retval.split(".")[1]
            retval = float(retval)
            return retval
        return 0.0

    def calculate_water_budget_and_adjusted_run_time(self, bucket_val, thetype):
        """Calculate water budget and adjusted run time based on bucket_val."""
        adjusted_run_time = 0
        if (
            bucket_val is None
            or isinstance(bucket_val, str)
            or (isinstance(bucket_val, (float, int)) and bucket_val >= 0)
        ):
            # return 0 for adjusted runtime
            adjusted_run_time = 0
        else:
            # we need to irrigate
            adjusted_run_time = abs(bucket_val) / self.coordinator.precipitation_rate
            if self.coordinator.maxium_duration > 0:
                adjusted_run_time = min(
                    self.coordinator.maximum_duration, adjusted_run_time
                )
        return adjusted_run_time

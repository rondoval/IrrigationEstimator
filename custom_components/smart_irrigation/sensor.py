"""SmartIrrigationEntity class."""
import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LENGTH_MILLIMETERS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TIME_SECONDS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_ELEVATION,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_state_change_event,
)
from .helpers import get_config_value, estimate_fao56_daily, MinMaxAvgTracker

from .const import (
    CONF_AREA,
    CONF_FLOW,
    CONF_MAXIMUM_DURATION,
    CONF_NUMBER_OF_SPRINKLERS,
    CONF_PRECIPITATION,
    CONF_PRECIPITATION_RATE,
    CONF_RAIN,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_PRECIPITATION,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_SOLAR_RADIATION,
    CONF_SENSOR_WINDSPEED,
    CONF_SENSOR_TEMPERATURE,
    CONF_SNOW,
    CONF_THROUGHPUT,
    DOMAIN,
    ENTITY_BUCKET,
    ENTITY_BUCKET_DELTA,
    ENTITY_EVAPOTRANSPIRATION,
    ENTITY_RUNTIME,
    ICON,
    SENSOR,
    SERVICE_RESET_BUCKET,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [
            EvapotranspirationSensor(hass, config_entry),
            DailyBucketDelta(hass, config_entry),
        ]
    )
    # TODO


class IrrigationSensor(RestoreSensor, SensorEntity):
    """Smart Irrigation Entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_icon = ICON

    def __init__(self, config_entry: ConfigEntry, sensor_name: str) -> None:
        """Initialize the entity."""
        self._attr_unique_id = config_entry.entry_id + sensor_name
        self._attr_name = config_entry.title + sensor_name
        self._attr_device_info = DeviceInfo(name=config_entry.title)


class EvapotranspirationSensor(IrrigationSensor):
    """Daily evapotranspiration"""

    _attr_native_unit_of_measurement = LENGTH_MILLIMETERS

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry, ENTITY_EVAPOTRANSPIRATION)
        self._sensors = {
            CONF_SENSOR_TEMPERATURE: get_config_value(
                config_entry, CONF_SENSOR_TEMPERATURE
            ),
            CONF_SENSOR_HUMIDITY: get_config_value(config_entry, CONF_SENSOR_HUMIDITY),
            CONF_SENSOR_PRESSURE: get_config_value(config_entry, CONF_SENSOR_PRESSURE),
            CONF_SENSOR_WINDSPEED: get_config_value(
                config_entry, CONF_SENSOR_WINDSPEED
            ),
            CONF_SENSOR_SOLAR_RADIATION: get_config_value(
                config_entry, CONF_SENSOR_SOLAR_RADIATION
            ),  # todo check units
        }
        self._wind_meas_height = 10  # todo
        self._sunshine_hours = 4  # todo from radiaton sensor
        self._temp_tracker = MinMaxAvgTracker()
        self._wind_tracker = MinMaxAvgTracker()  # todo check units
        self._rh_tracker = MinMaxAvgTracker()
        self._pressure_tracker = MinMaxAvgTracker()

        self._latitude = hass.config.as_dict().get(CONF_LATITUDE)
        self._longitude = hass.config.as_dict().get(CONF_LONGITUDE)
        self._elevation = hass.config.as_dict().get(CONF_ELEVATION)

        self._attr_native_value = 0

        self.async_on_remove(
            async_track_state_change_event(
                hass, self._sensors.values, self.async_sensor_state_listener
            )
        )

        async_track_time_change(
            hass,
            self._update,
            hour=23,
            minute=59,
            second=0,
        )

    @callback
    def async_sensor_state_listener(self, event: Event):
        """Sensor state listener"""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.status in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return

        if new_state.entity_id == self._sensors[CONF_SENSOR_TEMPERATURE]:
            self._temp_tracker.update(new_state.state)
        if new_state.entity_id == self._sensors[CONF_SENSOR_HUMIDITY]:
            self._rh_tracker.update(new_state.state)
        if new_state.entity_id == self._sensors[CONF_SENSOR_WINDSPEED]:
            self._wind_tracker.update(new_state.state)
        if new_state.entity_id == self._sensors[CONF_SENSOR_PRESSURE]:
            self._pressure_tracker.update(new_state.state)

    @callback
    def _update(self):
        self._attr_native_value = estimate_fao56_daily(
            datetime.datetime.now().timetuple().tm_yday,
            self._latitude,
            self._elevation,
            self._wind_meas_height,
            self._temp_tracker.min,
            self._temp_tracker.max,
            self._rh_tracker.min,
            self._rh_tracker.max,
            self._pressure_tracker.avg,
            self._wind_tracker.avg,
            self._sunshine_hours,
        )
        self._wind_tracker.reset()
        self._temp_tracker.reset()
        self._rh_tracker.reset()
        self._pressure_tracker.reset()
        self.async_write_ha_state()


class DailyBucketDelta(IrrigationSensor):
    """Daily precipitation-evapotranspiration delta"""

    _attr_native_unit_of_measurement = LENGTH_MILLIMETERS

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry, ENTITY_BUCKET_DELTA)

        self._sensors = {
            CONF_SENSOR_PRECIPITATION: get_config_value(
                config_entry, CONF_SENSOR_PRECIPITATION
            ),
            ENTITY_EVAPOTRANSPIRATION: f"{SENSOR}.{ENTITY_EVAPOTRANSPIRATION}",
        }
        self._precipitation = 0.0
        self._rain = 0.0
        self._snow = 0.0
        self._attr_native_value = 0

        self.async_on_remove(
            async_track_state_change_event(
                hass,
                self._sensors.values,
                self.async_sensor_state_listener,
            )
        )

    @callback
    def async_sensor_state_listener(self, event: Event):
        """Handle sensor state changes"""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return

        if new_state.entity_id == ENTITY_EVAPOTRANSPIRATION:
            evapotranspiration = new_state.state
            self._attr_native_value = self._precipitation - evapotranspiration
            self.async_write_ha_state()  # todo async won't work
            self._reset()
            return

        self._rain = new_state.state  # todo should accumulate - check openweathermap?
        self._precipitation = self._rain + self._snow

    # async def async_added_to_hass(self):
    #     if (data := await self.async_get_last_sensor_data()) is not None:
    #         self._attr_native_value = data.native_value
    #         self._rain = data.rain

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            CONF_RAIN: self._rain,
            CONF_SNOW: self._snow,
            CONF_PRECIPITATION: self._precipitation,
        }

    @callback
    def _reset(self):
        self._precipitation = 0
        self._rain = 0
        self._snow = 0


class CumulativeBucket(IrrigationSensor):
    """Daily cumulative bucket"""

    _attr_native_unit_of_measurement = LENGTH_MILLIMETERS

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry, ENTITY_BUCKET)
        self._attr_native_value = 0
        self.async_on_remove(
            async_track_state_change_event(
                hass,
                f"{SENSOR}.{ENTITY_BUCKET_DELTA}",
                self.async_sensor_state_listener,
            )
        )
        # register the services
        hass.services.async_register(
            DOMAIN,
            f"{self._attr_name}_{SERVICE_RESET_BUCKET}",
            self._reset,
        )

    @callback
    def async_sensor_state_listener(self, event: Event):
        """Handle sensor state changes"""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return

        bucket_delta = new_state.state
        self._attr_native_value += bucket_delta
        self.async_write_ha_state()

    def _reset(self):
        self._attr_native_value = 0


class CumulativeRunTime(IrrigationSensor):
    """Daily run time"""

    _attr_native_unit_of_measurement = TIME_SECONDS
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry, ENTITY_RUNTIME)
        self._number_of_sprinklers = get_config_value(
            config_entry, CONF_NUMBER_OF_SPRINKLERS
        )
        self._area = get_config_value(config_entry, CONF_AREA)
        self._flow = get_config_value(config_entry, CONF_FLOW)
        self._maximum_duration = get_config_value(config_entry, CONF_MAXIMUM_DURATION)
        self._throughput = self._number_of_sprinklers * self._flow
        self._precipitation_rate = (self._throughput * 60) / self._area
        self._attr_native_value = 0
        self.async_on_remove(
            async_track_state_change_event(
                hass, f"{SENSOR}.{ENTITY_BUCKET}", self.async_sensor_state_listener
            )
        )

    @callback
    def async_sensor_state_listener(self, event: Event):
        """Update sensor"""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return

        bucket = new_state.state
        self._attr_native_value = 0
        if bucket is not None and bucket < 0:
            self._attr_native_value = abs(bucket) / self._precipitation_rate
            if self._maximum_duration > 0:
                self._attr_native_value = min(
                    self._maximum_duration, self._attr_native_value
                )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            CONF_NUMBER_OF_SPRINKLERS: self._number_of_sprinklers,
            CONF_FLOW: self._flow,
            CONF_THROUGHPUT: self._throughput,
            CONF_AREA: self._area,
            CONF_PRECIPITATION_RATE: self._precipitation_rate,
            CONF_MAXIMUM_DURATION: self._maximum_duration,
        }

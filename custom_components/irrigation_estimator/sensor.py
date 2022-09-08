"""SmartIrrigationEntity class."""
from __future__ import annotations
import datetime
import logging

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
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
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
    ATTR_PRECIPITATION,
    ATTR_PRECIPITATION_RATE,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_PRECIPITATION,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_SOLAR_RADIATION,
    CONF_SENSOR_WINDSPEED,
    CONF_SENSOR_TEMPERATURE,
    ATTR_THROUGHPUT,
    CONF_WIND_MEASUREMENT_HEIGHT,
    DOMAIN,
    ENTITY_BUCKET,
    ENTITY_BUCKET_DELTA,
    ENTITY_EVAPOTRANSPIRATION,
    ENTITY_RUNTIME,
    ICON,
    SERVICE_RESET_BUCKET,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    calc_engine = CalculationEngine(hass, config_entry)

    async_add_entities(
        [
            EvapotranspirationSensor(calc_engine, config_entry),
            DailyBucketDelta(calc_engine, config_entry),
            CumulativeBucket(hass, calc_engine, config_entry),
            CumulativeRunTime(calc_engine, config_entry),
        ]
    )


class CalculationEngine:
    """Listens to sensors and makes backend calculations"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self._latitude = hass.config.as_dict().get(CONF_LATITUDE)
        self._longitude = hass.config.as_dict().get(CONF_LONGITUDE)
        self._elevation = hass.config.as_dict().get(CONF_ELEVATION)
        self.number_of_sprinklers = get_config_value(
            config_entry, CONF_NUMBER_OF_SPRINKLERS
        )
        self.flow = get_config_value(config_entry, CONF_FLOW)
        self.throughput = self.number_of_sprinklers * self.flow
        self.area = get_config_value(config_entry, CONF_AREA)
        self.precipitation_rate = round((self.throughput * 60) / self.area, 2)
        self.maximum_duration = get_config_value(config_entry, CONF_MAXIMUM_DURATION)
        self._wind_meas_height = get_config_value(
            config_entry, CONF_WIND_MEASUREMENT_HEIGHT
        )

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
            CONF_SENSOR_PRECIPITATION: get_config_value(
                config_entry, CONF_SENSOR_PRECIPITATION
            ),
        }

        self._sunshine_hours = 4  # todo from radiaton sensor
        self._temp_tracker = MinMaxAvgTracker()
        self._wind_tracker = MinMaxAvgTracker()  # todo check units
        self._rh_tracker = MinMaxAvgTracker()
        self._pressure_tracker = MinMaxAvgTracker()

        self.evapotranspiration = 0
        self.rain = 0.0  # todo conf cumulative/hourly
        self.precipitation = 0.0
        self.bucket_delta = 0.0
        self.bucket = 0.0
        self.runtime = 0

        self._listeners: dict[CALLBACK_TYPE, CALLBACK_TYPE] = {}
        self._unsub_status: CALLBACK_TYPE | None = None
        self._unsub_time: CALLBACK_TYPE | None = None

    @callback
    def _subscribe_events(self):
        self._unsubscribe_events()
        self._unsub_status = async_track_state_change_event(
            self.hass, self._sensors.values(), self._async_sensor_state_listener
        )
        self._unsub_time = async_track_time_change(
            self.hass,
            self._update_daily,
            hour=0,
            minute=0,
            second=10,
        )

    @callback
    def _unsubscribe_events(self):
        if self._unsub_status:
            self._unsub_status()
            self._unsub_status = None
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE):
        """Subscribe to updates"""
        subscribe = not self._listeners

        @callback
        def remove_listener() -> None:
            self._listeners.pop(remove_listener)
            if not self._listeners:
                self._unsubscribe_events()

        self._listeners[remove_listener] = update_callback
        if subscribe:
            self._subscribe_events()

        return remove_listener

    @callback
    def _async_update_listeners(self):
        for update_callback in list(self._listeners.values()):
            update_callback()

    @callback
    def _async_sensor_state_listener(self, event: Event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return

        # TODO ugly
        entity_id = new_state.entity_id
        value = float(new_state.state)
        if entity_id == self._sensors[CONF_SENSOR_TEMPERATURE]:
            self._temp_tracker.update(value)
        if entity_id == self._sensors[CONF_SENSOR_HUMIDITY]:
            self._rh_tracker.update(value)
        if entity_id == self._sensors[CONF_SENSOR_WINDSPEED]:
            # todo convert units
            self._wind_tracker.update(value)
        if entity_id == self._sensors[CONF_SENSOR_PRESSURE]:
            self._pressure_tracker.update(value)
        if entity_id == self._sensors[CONF_SENSOR_PRECIPITATION]:
            self.precipitation = value  # todo should accumulate - check openweathermap?

    def _update_daily(self, _):
        self._update_eto()
        self._update_bucket()
        self._update_runtime()
        self._async_update_listeners()

    def _update_runtime(self):
        self.runtime = 0
        if self.bucket is not None and self.bucket < 0:
            self.runtime = abs(self.bucket) / self.precipitation_rate * 3600
            if self.maximum_duration > 0:
                self.runtime = min(self.maximum_duration, self.runtime)

    def _update_bucket(self):
        self.bucket_delta = self.precipitation - self.evapotranspiration
        self.precipitation = 0.0
        self.bucket += self.bucket_delta

    def _update_eto(self):
        if all(
            x.is_tracking()
            for x in [
                self._temp_tracker,
                self._rh_tracker,
                self._pressure_tracker,
                self._wind_tracker,
            ]
        ):
            eto = estimate_fao56_daily(
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
            self.evapotranspiration = round(eto, 2)
            self._wind_tracker.reset()
            self._temp_tracker.reset()
            self._rh_tracker.reset()
            self._pressure_tracker.reset()


class IrrigationSensor(RestoreSensor, SensorEntity):
    """Smart Irrigation Entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_icon = ICON

    def __init__(
        self,
        coordinator: CalculationEngine,
        config_entry: ConfigEntry,
        sensor_name: str,
    ) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_name}"
        self._attr_name = f"{config_entry.title} {sensor_name}"
        self._attr_device_info = DeviceInfo(
            name=config_entry.title,
            identifiers={(DOMAIN, config_entry.entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvapotranspirationSensor(IrrigationSensor):
    """Daily evapotranspiration"""

    _attr_native_unit_of_measurement = LENGTH_MILLIMETERS

    def __init__(
        self, coordinator: CalculationEngine, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry, ENTITY_EVAPOTRANSPIRATION)
        self._attr_native_value = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.evapotranspiration
        return super()._handle_coordinator_update()


class DailyBucketDelta(IrrigationSensor):
    """Daily precipitation-evapotranspiration delta"""

    _attr_native_unit_of_measurement = LENGTH_MILLIMETERS

    def __init__(
        self, coordinator: CalculationEngine, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry, ENTITY_BUCKET_DELTA)
        self._attr_native_value = 0.0

    # async def async_added_to_hass(self):
    #     if (data := await self.async_get_last_sensor_data()) is not None:
    #         self._attr_native_value = data.native_value
    #         self._rain = data.rain

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.bucket_delta
        return super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_PRECIPITATION: self.coordinator.precipitation,
        }


class CumulativeBucket(IrrigationSensor):
    """Daily cumulative bucket"""

    _attr_native_unit_of_measurement = LENGTH_MILLIMETERS

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: CalculationEngine,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, config_entry, ENTITY_BUCKET)

        # register the services
        hass.services.async_register(
            DOMAIN,
            f"{self._attr_name}_{SERVICE_RESET_BUCKET}",
            self._reset,
        )

    @callback
    def _reset(self):
        self.coordinator.bucket = 0.0
        self._attr_native_value = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.bucket
        return super()._handle_coordinator_update()


class CumulativeRunTime(IrrigationSensor):
    """Daily run time"""

    _attr_native_unit_of_measurement = TIME_SECONDS
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(
        self, coordinator: CalculationEngine, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry, ENTITY_RUNTIME)
        self._attr_native_value = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.runtime
        return super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            CONF_NUMBER_OF_SPRINKLERS: self.coordinator.number_of_sprinklers,
            CONF_FLOW: self.coordinator.flow,
            ATTR_THROUGHPUT: self.coordinator.throughput,
            CONF_AREA: self.coordinator.area,
            ATTR_PRECIPITATION_RATE: self.coordinator.precipitation_rate,
            CONF_MAXIMUM_DURATION: self.coordinator.maximum_duration,
        }

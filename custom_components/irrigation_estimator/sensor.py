"""SmartIrrigationEntity class."""
from __future__ import annotations

import datetime
from enum import IntFlag
from functools import partial
import logging

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .const import (
    ATTR_MAX_RH,
    ATTR_MAX_TEMP,
    ATTR_MEAN_PRESSURE,
    ATTR_MEAN_RADIATION,
    ATTR_MEAN_WIND,
    ATTR_MIN_RH,
    ATTR_MIN_TEMP,
    ATTR_PRECIPITATION,
    ATTR_PRECIPITATION_RATE,
    ATTR_SUNSHINE_HOURS,
    ATTR_THROUGHPUT,
    CONF_ACCURATE_SOLAR_RADIATION,
    CONF_AREA,
    CONF_FLOW,
    CONF_MAXIMUM_DURATION,
    CONF_NUMBER_OF_SPRINKLERS,
    CONF_PRECIPITATION_SENSOR_TYPE,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_PRECIPITATION,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_SOLAR_RADIATION,
    CONF_SENSOR_TEMPERATURE,
    CONF_SENSOR_WINDSPEED,
    CONF_SOLAR_RADIATION_THRESHOLD,
    CONF_WIND_MEASUREMENT_HEIGHT,
    DOMAIN,
    ENTITY_BUCKET,
    ENTITY_BUCKET_DELTA,
    ENTITY_EVAPOTRANSPIRATION,
    ENTITY_RUNTIME,
    ICON,
    OPTION_CUMULATIVE,
    OPTION_HOURLY,
    SERVICE_FORCE_DAILY_UPDATE,
    SERVICE_RESET_BUCKET,
)
from .helpers import (
    MinMaxAvgTracker,
    SunshineTracker,
    estimate_fao56_daily,
    get_config_value,
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
            CumulativeBucket(calc_engine, config_entry),
            CumulativeRunTime(calc_engine, config_entry),
        ]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RESET_BUCKET, {}, "async_reset", [
            IrrigationEntityFeature.RESET]
    )
    platform.async_register_entity_service(
        SERVICE_FORCE_DAILY_UPDATE,
        {},
        "async_update_daily",
        [IrrigationEntityFeature.UPDATE],
    )


class CalculationEngine:
    """Listens to sensors and makes backend calculations."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the ET calculation engine."""
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
        self._precipitation_sensor_type = get_config_value(
            config_entry, CONF_PRECIPITATION_SENSOR_TYPE
        )
        self._solar_radiation_threshold = get_config_value(
            config_entry, CONF_SOLAR_RADIATION_THRESHOLD
        )
        self.maximum_duration = get_config_value(
            config_entry, CONF_MAXIMUM_DURATION)
        self._wind_meas_height = get_config_value(
            config_entry, CONF_WIND_MEASUREMENT_HEIGHT
        )
        self._accurate_solar_radiation = get_config_value(
            config_entry, CONF_ACCURATE_SOLAR_RADIATION
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
            ),
            CONF_SENSOR_PRECIPITATION: get_config_value(
                config_entry, CONF_SENSOR_PRECIPITATION
            ),
        }

        self.sunshine_tracker = SunshineTracker(
            self._solar_radiation_threshold)
        self.solar_radiation_tracker = MinMaxAvgTracker()
        self.temp_tracker = MinMaxAvgTracker()
        self.wind_tracker = MinMaxAvgTracker()
        self.rh_tracker = MinMaxAvgTracker()
        self.pressure_tracker = MinMaxAvgTracker()

        self.evapotranspiration = 0
        self.precipitation = 0.0
        self.bucket_delta = 0.0
        self.bucket = 0.0
        self.runtime = 0

        self._listeners: dict[CALLBACK_TYPE, CALLBACK_TYPE] = {}
        self._unsub_status: CALLBACK_TYPE | None = None
        self._unsub_time: CALLBACK_TYPE | None = None
        self._unsub_hourly: CALLBACK_TYPE | None = None
        self._unsub_update_entities: CALLBACK_TYPE | None = None

    @callback
    def _subscribe_events(self):
        self._unsubscribe_events()
        self._unsub_status = async_track_state_change_event(
            self.hass, self._sensors.values(), self._async_sensor_state_listener
        )
        self._unsub_time = async_track_time_change(
            self.hass,
            self.update_daily,
            hour=0,
            minute=0,
            second=10,
        )
        self._unsub_update_entities = async_track_time_change(
            self.hass,
            self._update_entities,
            second=40,
        )
        if self._precipitation_sensor_type == OPTION_HOURLY:
            self._unsub_hourly = async_track_time_change(
                self.hass, self._update_hourly, minute=0, second=0
            )

    @callback
    def _unsubscribe_events(self):
        if self._unsub_status:
            self._unsub_status()
            self._unsub_status = None
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None
        if self._unsub_hourly:
            self._unsub_hourly()
            self._unsub_hourly = None
        if self._unsub_update_entities:
            self._unsub_update_entities()
            self._unsub_update_entities = None

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE):
        """Subscribe to updates."""
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
            None,
        ):
            return

        entity_id = new_state.entity_id
        value = float(new_state.state)
        unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if entity_id == self._sensors[CONF_SENSOR_TEMPERATURE]:
            self.temp_tracker.update(
                TemperatureConverter.convert(
                    value, unit, UnitOfTemperature.CELSIUS)
            )
        elif entity_id == self._sensors[CONF_SENSOR_HUMIDITY]:
            self.rh_tracker.update(value)
        elif entity_id == self._sensors[CONF_SENSOR_WINDSPEED]:
            self.wind_tracker.update(
                SpeedConverter.convert(
                    value, unit, UnitOfSpeed.METERS_PER_SECOND)
            )
        elif entity_id == self._sensors[CONF_SENSOR_PRESSURE]:
            self.pressure_tracker.update(
                PressureConverter.convert(value, unit, UnitOfPressure.HPA)
            )
        elif entity_id == self._sensors[CONF_SENSOR_SOLAR_RADIATION]:
            if self._accurate_solar_radiation:
                self.solar_radiation_tracker.update(value)
            else:
                self.sunshine_tracker.update(value)
        elif entity_id == self._sensors[CONF_SENSOR_PRECIPITATION]:
            if self._precipitation_sensor_type == OPTION_CUMULATIVE:
                self.precipitation = DistanceConverter.convert(
                    value, unit, UnitOfLength.MILLIMETERS
                )

    @callback
    def _update_entities(self, _):
        self._async_update_listeners()

    @callback
    def _update_hourly(self, _):
        new_state = self.hass.states.get(
            self._sensors[CONF_SENSOR_PRECIPITATION])
        if new_state is not None and new_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            value = float(new_state.state)
            unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            self.precipitation += DistanceConverter.convert(
                value, unit, UnitOfLength.MILLIMETERS
            )

    @callback
    def update_daily(self, _):
        """Performs daily calculations"""
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
                self.temp_tracker,
                self.rh_tracker,
                self.pressure_tracker,
                self.wind_tracker,
            ]
        ):
            eto = estimate_fao56_daily(
                datetime.datetime.now(tz=datetime.UTC).timetuple().tm_yday,
                self._latitude,
                self._elevation,
                self._wind_meas_height,
                self.temp_tracker.min,
                self.temp_tracker.max,
                self.rh_tracker.min,
                self.rh_tracker.max,
                self.pressure_tracker.avg,
                self.wind_tracker.avg,
                self.solar_radiation_tracker.avg,
                self.sunshine_tracker.get_hours(),
            )
            self.evapotranspiration = round(eto, 2)
            self.wind_tracker.reset()
            self.temp_tracker.reset()
            self.rh_tracker.reset()
            self.pressure_tracker.reset()
            self.sunshine_tracker.reset()
            self.solar_radiation_tracker.reset()

    async def async_retrieve_history(self):
        """Recreates avg records from base sensor history."""
        if "recorder" not in self.hass.config.components:
            return

        to_update = [
            (self._sensors[CONF_SENSOR_WINDSPEED], self.wind_tracker),
            (self._sensors[CONF_SENSOR_PRESSURE], self.pressure_tracker),
        ]
        if self._accurate_solar_radiation:
            to_update.append(
                (
                    self._sensors[CONF_SENSOR_SOLAR_RADIATION],
                    self.solar_radiation_tracker,
                )
            )
        for entity_id, tracker in to_update:
            start = dt_util.start_of_local_day()
            filter_history = await get_instance(self.hass).async_add_executor_job(
                partial(
                    history.state_changes_during_period,
                    self.hass,
                    start,
                    entity_id=entity_id,
                    no_attributes=True,
                )
            )
            if entity_id in filter_history:
                tracker.load_history(filter_history.get(entity_id, []))


class IrrigationEntityFeature(IntFlag):
    """Services are not supported by all sensors"""

    RESET = 1
    UPDATE = 2


class IrrigationSensor(RestoreSensor, SensorEntity):
    """Smart Irrigation Entity."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_supported_features: IrrigationEntityFeature = IrrigationEntityFeature(
        0)
    _attr_has_entity_name = True
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
        self._attr_name = sensor_name
        self._attr_device_info = DeviceInfo(
            name=config_entry.title,
            identifiers={(DOMAIN, config_entry.entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvapotranspirationSensor(IrrigationSensor):
    """Daily evapotranspiration."""

    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_supported_features: IrrigationEntityFeature = IrrigationEntityFeature.UPDATE

    def __init__(
        self, coordinator: CalculationEngine, config_entry: ConfigEntry
    ) -> None:
        """Initialize the evapotranspiration sensor."""
        super().__init__(coordinator, config_entry, ENTITY_EVAPOTRANSPIRATION)
        self._attr_native_value = coordinator.evapotranspiration

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.evapotranspiration
        return super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_SUNSHINE_HOURS: self.coordinator.sunshine_tracker.get_hours()
        }

        if self.coordinator.temp_tracker.min:
            attributes[ATTR_MIN_TEMP] = self.coordinator.temp_tracker.min
        if self.coordinator.temp_tracker.max:
            attributes[ATTR_MAX_TEMP] = self.coordinator.temp_tracker.max
        if self.coordinator.rh_tracker.min:
            attributes[ATTR_MIN_RH] = self.coordinator.rh_tracker.min
        if self.coordinator.rh_tracker.max:
            attributes[ATTR_MAX_RH] = self.coordinator.rh_tracker.max
        if self.coordinator.wind_tracker.avg:
            attributes[ATTR_MEAN_WIND] = self.coordinator.wind_tracker.avg
        if self.coordinator.pressure_tracker.avg:
            attributes[ATTR_MEAN_PRESSURE] = self.coordinator.pressure_tracker.avg
        if self.coordinator.solar_radiation_tracker.avg:
            attributes[
                ATTR_MEAN_RADIATION
            ] = self.coordinator.solar_radiation_tracker.avg
        return attributes

    async def async_added_to_hass(self) -> None:
        """Restore state once added to hass."""
        await super().async_added_to_hass()
        if data := await self.async_get_last_sensor_data():
            self._attr_native_value = data.native_value
            self.coordinator.evapotranspiration = data.native_value

        if data := await self.async_get_last_state():
            # No need to restore avg from history for these
            self.coordinator.temp_tracker.min = data.attributes.get(
                ATTR_MIN_TEMP)
            self.coordinator.temp_tracker.max = data.attributes.get(
                ATTR_MAX_TEMP)
            self.coordinator.rh_tracker.min = data.attributes.get(ATTR_MIN_RH)
            self.coordinator.rh_tracker.max = data.attributes.get(ATTR_MAX_RH)
            self.coordinator.sunshine_tracker.sunshine_hours = datetime.timedelta(
                hours=1
            ) * data.attributes.get(ATTR_SUNSHINE_HOURS)
        await self.coordinator.async_retrieve_history()

    @callback
    def async_update_daily(self):
        """Recalculate ET0 and reset trackers"""
        self.coordinator.update_daily(None)


class DailyBucketDelta(IrrigationSensor):
    """Daily precipitation-evapotranspiration delta."""

    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS

    def __init__(
        self, coordinator: CalculationEngine, config_entry: ConfigEntry
    ) -> None:
        """Initialize the bucket delta sensor."""
        super().__init__(coordinator, config_entry, ENTITY_BUCKET_DELTA)
        self._attr_native_value = coordinator.bucket_delta

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

    async def async_added_to_hass(self) -> None:
        """Restore state once added to hass."""
        await super().async_added_to_hass()
        if data := await self.async_get_last_sensor_data():
            self._attr_native_value = data.native_value
            self.coordinator.bucket_delta = data.native_value

        if data := await self.async_get_last_state():
            self.coordinator.precipitation = data.attributes.get(
                ATTR_PRECIPITATION)


class CumulativeBucket(IrrigationSensor):
    """Daily cumulative bucket."""

    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_supported_features: IrrigationEntityFeature = IrrigationEntityFeature.RESET

    def __init__(
        self,
        coordinator: CalculationEngine,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the cumulative bucket sensor."""
        super().__init__(coordinator, config_entry, ENTITY_BUCKET)
        self._attr_native_value = coordinator.bucket

    @callback
    def async_reset(self):
        """Reset the bucket."""
        self.coordinator.bucket = 0.0
        self._attr_native_value = 0.0
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.bucket
        return super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Restore state once added to hass."""
        await super().async_added_to_hass()
        if data := await self.async_get_last_sensor_data():
            self._attr_native_value = data.native_value
            self.coordinator.bucket = data.native_value


class CumulativeRunTime(IrrigationSensor):
    """Daily run time."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_supported_features: IrrigationEntityFeature = IrrigationEntityFeature.RESET

    def __init__(
        self, coordinator: CalculationEngine, config_entry: ConfigEntry
    ) -> None:
        """Initialize the cumulative run time sensor."""
        super().__init__(coordinator, config_entry, ENTITY_RUNTIME)
        self._attr_native_value = coordinator.runtime

    @callback
    def async_reset(self):
        """Reset the run time."""
        self.coordinator.runtime = 0
        self._attr_native_value = 0
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.runtime
        return super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Restore state once added to hass."""
        await super().async_added_to_hass()
        if data := await self.async_get_last_sensor_data():
            self._attr_native_value = data.native_value
            self.coordinator.runtime = data.native_value

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

"""The Smart Irrigation integration."""
import asyncio
from datetime import timedelta
import logging
import datetime
import weakref

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_point_in_time,
)

from homeassistant.const import (
    CONF_LATITUDE,
    CONF_ELEVATION,
    CONF_LONGITUDE,
)

from .const import (
    CONF_NUMBER_OF_SPRINKLERS,
    CONF_FLOW,
    CONF_AREA,
    DOMAIN,
    CONF_BUCKET,
    EVENT_BUCKET_UPDATED,
    SERVICE_RESET_BUCKET,
    SERVICE_CALCULATE_DAILY_EVAPOTRANSPIRATION,
    CONF_MAXIMUM_DURATION,
    EVENT_HOURLY_DATA_UPDATED,
    CONF_SENSORS,
    DEFAULT_MAXIMUM_DURATION,
    CONF_SENSOR_PRECIPITATION,
)


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=58)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
    area = entry.data.get(CONF_AREA)
    flow = entry.data.get(CONF_FLOW)
    number_of_sprinklers = entry.data.get(CONF_NUMBER_OF_SPRINKLERS)
    sensors = entry.data.get(CONF_SENSORS)

    throughput = number_of_sprinklers * flow
    precipitation_rate = (throughput * 60) / area
    latitude = hass.config.as_dict().get(CONF_LATITUDE)
    longitude = hass.config.as_dict().get(CONF_LONGITUDE)
    elevation = hass.config.as_dict().get(CONF_ELEVATION)

    name = entry.title
    name = name.replace(" ", "_")

    # handle options: lead time, change_percent, max duration, force_mode_duration, show units, auto refresh, auto refresh time
    maximum_duration = entry.options.get(
        CONF_MAXIMUM_DURATION, DEFAULT_MAXIMUM_DURATION
    )

    # set up coordinator
    coordinator = SmartIrrigationUpdateCoordinator(
        hass,
        longitude=longitude,
        latitude=latitude,
        elevation=elevation,
        area=area,
        flow=flow,
        number_of_sprinklers=number_of_sprinklers,
        throughput=throughput,
        precipitation_rate=precipitation_rate,
        maximum_duration=maximum_duration,
        sensors=sensors,
        name=name,
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        coordinator.platforms.append(platform)
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    # add update listener if not already added.
    if weakref.ref(async_reload_entry) not in entry.update_listeners:
        entry.add_update_listener(async_reload_entry)

    # register the services
    hass.services.async_register(
        DOMAIN,
        f"{name}_{SERVICE_RESET_BUCKET}",
        coordinator.handle_reset_bucket,
    )
    hass.services.async_register(
        DOMAIN,
        f"{name}_{SERVICE_CALCULATE_DAILY_EVAPOTRANSPIRATION}",
        coordinator.handle_calculate_daily_adjusted_run_time,
    )
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.entry_setup_completed:
        await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


class SmartIrrigationUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API and storing settings."""

    def __init__(
        self,
        hass,
        longitude,
        latitude,
        elevation,
        area,
        flow,
        number_of_sprinklers,
        throughput,
        precipitation_rate,
        maximum_duration,
        sensors,
        name,
    ):
        """Initialize."""
        self.longitude = longitude
        self.latitude = latitude
        self.elevation = elevation
        self.area = area
        self.flow = flow
        self.number_of_sprinklers = number_of_sprinklers
        self.throughput = throughput
        self.precipitation_rate = precipitation_rate
        self.maximum_duration = maximum_duration
        self.name = name
        self.sensors = sensors
        self.hourly_precipitation_list = []
        self.hourly_evapotranspiration_list = []
        self.platforms = []
        self.bucket = 0
        self.hass = hass
        self.entities = {}
        self.entry_setup_completed = False
        super().__init__(hass, _LOGGER, name=name, update_interval=SCAN_INTERVAL)

        # last update of the day happens at specified local time
        async_track_time_change(
            hass,
            self._async_update_last_of_day,
            hour=0,
            minute=1,
            second=0,
        )
        self.entry_setup_completed = True

    def register_entity(self, thetype, entity):
        """Register an entity."""
        self.entities[thetype] = entity

    def fire_bucket_updated_event(self):
        """Fire bucket_updated event so the sensor can update itself."""
        event_to_fire = f"{self.name}_{EVENT_BUCKET_UPDATED}"
        self.hass.bus.fire(event_to_fire, {CONF_BUCKET: self.bucket})

    def handle_reset_bucket(self, call):
        """Handle the service reset_bucket call."""
        self.bucket = 0
        self.fire_bucket_updated_event()

    async def handle_calculate_daily_adjusted_run_time(self, call):
        """Handle the service calculate_daily_adjusted_run_time call."""
        await self._async_update_last_of_day

    async def handle_calculate_hourly_adjusted_run_time(self, call):
        """Handle the service calculate_hourly_adjusted_run_time call."""
        # fire an event so the sensor can update itself.
        event_to_fire = f"{self.name}_{EVENT_HOURLY_DATA_UPDATED}"
        self.hass.bus.fire(event_to_fire, {})

    async def _async_update_last_of_day(self, *args):
        # if bucket has a unit, parse it out
        if len(self.hourly_precipitation_list) > 0:
            # when using a sensor for precipitation just take the most recent (last item in the list) because we assume it is a daily actual value (cumulative)
            precip = self.hourly_precipitation_list
            evapotranspiration = self.hourly_evapotranspiration_list
            bucket_delta = precip - evapotranspiration

        else:
            bucket_delta = 0

        # empty the hourly precipitation list
        self.hourly_precipitation_list = []
        self.hourly_evapotranspiration_list = []
        self.bucket = self.bucket + bucket_delta
        # fire an event so the sensor can update itself.
        event_to_fire = f"{self.name}_{EVENT_BUCKET_UPDATED}"
        self.hass.bus.fire(event_to_fire, {CONF_BUCKET: self.bucket})

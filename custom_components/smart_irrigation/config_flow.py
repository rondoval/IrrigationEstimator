"""Config flow for Smart Irrigation integration."""
from .const import (
    CONF_NUMBER_OF_SPRINKLERS,
    CONF_FLOW,
    CONF_AREA,
    NAME,
    CONF_MAXIMUM_DURATION,
    CONF_SHOW_UNITS,
    CONF_AUTO_REFRESH_TIME,
    CONF_NAME,
    DEFAULT_MAXIMUM_DURATION,
    DEFAULT_SHOW_UNITS,
    CONF_INITIAL_UPDATE_DELAY,
    DEFAULT_INITIAL_UPDATE_DELAY,
    DOMAIN,
    CONF_SENSOR_TEMPERATURE,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_WINDSPEED,
    CONF_SENSOR_SOLAR_RADIATION,
    UNIT_OF_MEASUREMENT_M2
)

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=NAME): str,
        vol.Required(CONF_NUMBER_OF_SPRINKLERS): vol.Coerce(float),
        vol.Required(CONF_FLOW): vol.Coerce(float),
        vol.Required(CONF_AREA): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step="0.1",
                unit_of_measurement=UNIT_OF_MEASUREMENT_M2,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SENSOR_TEMPERATURE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SENSOR_HUMIDITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SENSOR_PRESSURE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SENSOR_WINDSPEED): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SENSOR_SOLAR_RADIATION): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)

OPTION_SCHEMA = vol.Schema(
    {
        # vol.Required(
        #    CONF_NUMBER_OF_SPRINKLERS,
        #    default=self.options.get(
        #        CONF_NUMBER_OF_SPRINKLERS,
        #        self.config_entry.data.get(CONF_NUMBER_OF_SPRINKLERS),
        #    ),
        # ): vol.Coerce(float),
        # vol.Required(
        #    CONF_FLOW,
        #    default=self.options.get(
        #        CONF_FLOW, self.config_entry.data.get(CONF_FLOW),
        #    ),
        # ): vol.Coerce(float),
        # vol.Required(
        #    CONF_AREA,
        #    default=self.options.get(
        #        CONF_AREA, self.config_entry.data.get(CONF_AREA),
        #    ),
        # ): vol.Coerce(float),
        vol.Required(
            CONF_MAXIMUM_DURATION,
            default=self.options.get(
                CONF_MAXIMUM_DURATION, DEFAULT_MAXIMUM_DURATION
            ),
        ): int,
        vol.Required(
            CONF_SHOW_UNITS,
            default=self.options.get(CONF_SHOW_UNITS, DEFAULT_SHOW_UNITS),
        ): bool,
        vol.Required(
            CONF_INITIAL_UPDATE_DELAY,
            default=self.options.get(
                CONF_INITIAL_UPDATE_DELAY, DEFAULT_INITIAL_UPDATE_DELAY
            ),
        ): int,
    },
)


class SmartIrrigationConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Irrigation."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title=self._name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow."""
        return SmartIrrigationOptionsFlowHandler(config_entry)


class SmartIrrigationOptionsFlowHandler(config_entries.OptionsFlow):
    """Smart Irrigation config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self._errors = {}

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def _show_options_form(self, user_input):
        """Show the options form to edit info."""
        return self.async_show_form(
            step_id="user",
            data_schema=OPTION_SCHEMA,
            errors=self._errors,
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}
        if user_input is not None:

            valid_time = check_time(user_input[CONF_AUTO_REFRESH_TIME])
            if not valid_time:
                self._errors["base"] = "auto_refresh_time_error"
                return await self._show_options_form(user_input)
            if int(user_input[CONF_MAXIMUM_DURATION]) < -1:
                self._errors["base"] = "maximum_duration_error"
                return await self._show_options_form(user_input)
            if int(user_input[CONF_INITIAL_UPDATE_DELAY]) < 0:
                self._errors["base"] = "initial_update_delay_error"
                return await self._show_options_form(user_input)

            # commented out for later right now this results in a NoneType object is not subscriptable in core/homeassistant/data_entry_flow.py (#214)
            # store num_sprinklers, flow, area in data settings as well!
            # data = {**self.config_entry.data}
            # data[CONF_NUMBER_OF_SPRINKLERS] = float(
            #    user_input[CONF_NUMBER_OF_SPRINKLERS]
            # )
            # data[CONF_FLOW] = float(user_input[CONF_FLOW])
            # data[CONF_AREA] = float(user_input[CONF_AREA])
            # _LOGGER.debug("data: {}".format(data))
            # self.hass.config_entries.async_update_entry(
            #    self.config_entry, data=data
            # )
            # settings = {}
            # for x in self.config_entry.data:
            #    settings[x] = self.config_entry.data[x]
            # settings[CONF_NUMBER_OF_SPRINKLERS] = user_input[
            #    CONF_NUMBER_OF_SPRINKLERS
            # ]
            # settings[CONF_FLOW] = user_input[CONF_FLOW]
            # settings[CONF_AREA] = user_input[CONF_AREA]
            # _LOGGER.debug("settings: {}".format(settings))
            # _LOGGER.debug("unique id: {}".format(self.config_entry.unique_id))
            # LOGGER.info("name: {}".format(settings[CONF_NAME]))
            # await self._update_options(user_input)
            # return self.hass.config_entries.async_update_entry(
            #    self.config_entry,
            #    # unique_id=self.config_entry.unique_id,
            #    title=settings[CONF_NAME],
            #    data=settings,
            #    options=user_input,
            # )
            return await self._update_options(user_input)

        return await self._show_options_form(user_input)

    async def _update_options(self, user_input=None):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(NAME), data=user_input
        )

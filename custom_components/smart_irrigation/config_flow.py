"""Config flow for Irrigation Estimator integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol
from homeassistant.const import AREA_SQUARE_METERS, TIME_SECONDS
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_AREA,
    CONF_FLOW,
    CONF_MAXIMUM_DURATION,
    CONF_NAME,
    CONF_NUMBER_OF_SPRINKLERS,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_SOLAR_RADIATION,
    CONF_SENSOR_TEMPERATURE,
    CONF_SENSOR_WINDSPEED,
    DEFAULT_MAXIMUM_DURATION,
    DOMAIN,
    NAME,
    VOLUME_FLOW_RATE_LITRES_PER_MINUTE,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NUMBER_OF_SPRINKLERS): selector.NumberSelector(
            selector.NumberSelectorConfig(step=1, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_FLOW): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step=0.1,
                unit_of_measurement=VOLUME_FLOW_RATE_LITRES_PER_MINUTE,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_AREA): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step="0.1",
                unit_of_measurement=AREA_SQUARE_METERS,
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
        vol.Required(
            CONF_MAXIMUM_DURATION,
            default=DEFAULT_MAXIMUM_DURATION,
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=1,
                unit_of_measurement=TIME_SECONDS,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    },
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=NAME): selector.TextSelector(
            selector.TextSelectorConfig(type="text")
        ),
    }
).extend(OPTIONS_SCHEMA)

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA)
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
}


class IrrigationEstimatorConfigFlow(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Irrigation Estimator."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

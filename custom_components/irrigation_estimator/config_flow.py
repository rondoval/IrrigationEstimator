"""Config flow for Irrigation Estimator integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONF_NAME,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TIME_SECONDS,
    Platform,
    UnitOfLength,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
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
    DEFAULT_MAXIMUM_DURATION,
    DEFAULT_SOLAR_RADIATION_THRESHOLD,
    DOMAIN,
    NAME,
    OPTION_CUMULATIVE,
    OPTION_HOURLY,
    VOLUME_FLOW_RATE_LITRES_PER_MINUTE,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NUMBER_OF_SPRINKLERS): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step=PRECISION_WHOLE, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_FLOW): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step=PRECISION_TENTHS,
                unit_of_measurement=VOLUME_FLOW_RATE_LITRES_PER_MINUTE,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
        vol.Required(CONF_AREA): selector.NumberSelector(
            selector.NumberSelectorConfig(
                step=PRECISION_TENTHS,
                unit_of_measurement=AREA_SQUARE_METERS,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
        vol.Required(CONF_SENSOR_TEMPERATURE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SENSOR),
        ),
        vol.Required(CONF_SENSOR_HUMIDITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SENSOR),
        ),
        vol.Required(CONF_SENSOR_PRESSURE): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SENSOR),
        ),
        vol.Required(CONF_SENSOR_WINDSPEED): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SENSOR),
        ),
        vol.Required(CONF_WIND_MEASUREMENT_HEIGHT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.0,
                step=PRECISION_TENTHS,
                unit_of_measurement=UnitOfLength.METERS,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
        vol.Required(CONF_SENSOR_SOLAR_RADIATION): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SENSOR),
        ),
        vol.Required(
            CONF_ACCURATE_SOLAR_RADIATION, default=False
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_SOLAR_RADIATION_THRESHOLD, default=DEFAULT_SOLAR_RADIATION_THRESHOLD
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
        vol.Required(CONF_SENSOR_PRECIPITATION): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SENSOR),
        ),
        vol.Required(CONF_PRECIPITATION_SENSOR_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=OPTION_CUMULATIVE, label="cumulative"
                    ),
                    selector.SelectOptionDict(
                        value=OPTION_HOURLY, label="hourly average"
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            ),
        ),
        vol.Required(
            CONF_MAXIMUM_DURATION,
            default=DEFAULT_MAXIMUM_DURATION,
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                step=PRECISION_WHOLE,
                unit_of_measurement=TIME_SECONDS,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=NAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
        ),
    }
).extend(OPTIONS_SCHEMA.schema)

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

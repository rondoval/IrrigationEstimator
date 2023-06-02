"""Constants for the Smart Irrigation integration."""

from homeassistant.const import Platform


DOMAIN = "irrigation_estimator"
NAME = "Irrigation Estimator"
VERSION = "1.0.4"

ISSUE_URL = "https://github.com/rondoval/IrrigationEstimator/issues"

# Icons
ICON = "mdi:sprinkler"

# Platforms
PLATFORMS = [Platform.SENSOR]

ATTR_THROUGHPUT = "throughput"
ATTR_PRECIPITATION_RATE = "precipitation_rate"
ATTR_PRECIPITATION = "precipitation"
ATTR_MIN_TEMP = "min_temp"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_RH = "min_rh"
ATTR_MAX_RH = "max_rh"
ATTR_MEAN_WIND = "mean_wind"
ATTR_MEAN_PRESSURE = "mean_pressure"
ATTR_SUNSHINE_HOURS = "sunshine_hours"
ATTR_MEAN_RADIATION = "mean_radiation"

# Configuration and options
CONF_NUMBER_OF_SPRINKLERS = "number_of_sprinklers"
CONF_FLOW = "flow"
CONF_AREA = "area"
CONF_MAXIMUM_DURATION = "maximum_duration"
CONF_WIND_MEASUREMENT_HEIGHT = "wind_meas_height"

# Sensors settings
CONF_SENSOR_TEMPERATURE = "sensor_temperature"
CONF_SENSOR_HUMIDITY = "sensor_humidity"
CONF_SENSOR_PRESSURE = "sensor_pressure"
CONF_SENSOR_WINDSPEED = "sensor_windspeed"
CONF_SENSOR_SOLAR_RADIATION = "sensor_solar_radiation"
CONF_ACCURATE_SOLAR_RADIATION = "sensor_solar_radiation_accuracy"
CONF_SOLAR_RADIATION_THRESHOLD = "solar_radiation_threshold"
CONF_SENSOR_PRECIPITATION = "sensor_precipitation"
CONF_PRECIPITATION_SENSOR_TYPE = "precipitation_sensor_type"

# Entities
ENTITY_EVAPOTRANSPIRATION = "Evapotranspiration"
ENTITY_RUNTIME = "Run time"
ENTITY_BUCKET = "Bucket"
ENTITY_BUCKET_DELTA = "Bucket delta"

# Selector values
OPTION_CUMULATIVE = "cumulative"
OPTION_HOURLY = "hourly"

# Services
SERVICE_RESET_BUCKET = "reset_bucket"
SERVICE_FORCE_DAILY_UPDATE = "force_daily_update"

# UNITS
VOLUME_FLOW_RATE_LITRES_PER_MINUTE = "l/min"

# OPTIONS DEFAULTS
DEFAULT_MAXIMUM_DURATION = 0  # seconds
DEFAULT_SOLAR_RADIATION_THRESHOLD = 3500

CONVERT_W_M2_TO_MJ_M2_DAY = 0.0864

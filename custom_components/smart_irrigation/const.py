"""Constants for the Smart Irrigation integration."""

DOMAIN = "irrigation_estimator"
NAME = "Irrigation Estimator"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"

ISSUE_URL = "https://github.com/rondoval/IrrigationEstimator/issues"

# Icons
ICON = "mdi:sprinkler"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

# Configuration and options
CONF_NUMBER_OF_SPRINKLERS = "number_of_sprinklers"
CONF_FLOW = "flow"
CONF_AREA = "area"
CONF_THROUGHPUT = "throughput"
CONF_PRECIPITATION_RATE = "precipitation_rate"
CONF_RAIN = "rain"
CONF_SNOW = "snow"
CONF_PRECIPITATION = "precipitation"
CONF_EVAPOTRANSPIRATION = "evapotranspiration"
CONF_BUCKET = "bucket"
CONF_NETTO_PRECIPITATION = "netto_precipitation"
CONF_MAXIMUM_DURATION = "maximum_duration"
CONF_ADJUSTED_RUN_TIME_MINUTES = "adjusted_run_time_minutes"
CONF_SPRINKLER_ICON = "mdi:sprinkler"

# Sensors setting labels
CONF_SENSOR_TEMPERATURE = "sensor_temperature"
CONF_SENSOR_HUMIDITY = "sensor_humidity"
CONF_SENSOR_PRESSURE = "sensor_pressure"
CONF_SENSOR_WINDSPEED = "sensor_windspeed"
CONF_SENSOR_SOLAR_RADIATION = "sensor_solar_radiation"
CONF_SENSOR_PRECIPITATION = "sensor_precipitation"

# Events
EVENT_BUCKET_UPDATED = "bucketUpd"
EVENT_HOURLY_DATA_UPDATED = "hourlyUpd"

# Services
SERVICE_RESET_BUCKET = "reset_bucket"
SERVICE_CALCULATE_DAILY_EVAPOTRANSPIRATION = "calculate_daily_evapotranspiration"

# METRIC TO IMPERIAL (US) FACTORS
KMH_TO_MS_FACTOR = 3.6
W_TO_J_DAY_FACTOR = 86400
J_TO_MJ_FACTOR = 1000000

# Defaults
DEFAULT_NAME = NAME

# UNITS
VOLUME_FLOW_RATE_LITRES_PER_MINUTE = "l/min"

# OPTIONS DEFAULTS
DEFAULT_MAXIMUM_DURATION = 0  # seconds

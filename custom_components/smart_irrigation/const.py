"""Constants for the Smart Irrigation integration."""

DOMAIN = "smart_irrigation"
NAME = "Smart Irrigation"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.76"

ISSUE_URL = "https://github.com/jeroenterheerdt/HASmartIrrigation/issues"

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
CONF_LEAD_TIME = "lead_time"
CONF_MAXIMUM_DURATION = "maximum_duration"
CONF_ADJUSTED_RUN_TIME_MINUTES = "adjusted_run_time_minutes"
CONF_SHOW_UNITS = "show_units"
CONF_AUTO_REFRESH = "auto_refresh"
CONF_AUTO_REFRESH_TIME = "auto_refresh_time"
CONF_NAME = "name"
CONF_CONFIG = "config"
CONF_SOURCE_SWITCHES = "sources"
CONF_SENSORS = "sensors"
CONF_INITIAL_UPDATE_DELAY = "initial_update_delay"
CONF_ICON = "icon"  # used to set attributes on entities in events
CONF_SPRINKLER_ICON = "mdi:sprinkler"

# Sensors setting labels
CONF_SENSOR_TEMPERATURE = "sensor_temperature"
CONF_SENSOR_HUMIDITY = "sensor_humidity"
CONF_SENSOR_PRESSURE = "sensor_pressure"
CONF_SENSOR_WINDSPEED = "sensor_windspeed"
CONF_SENSOR_SOLAR_RADIATION = "sensor_solar_radiation"

# Events
EVENT_BUCKET_UPDATED = "bucketUpd"
EVENT_HOURLY_DATA_UPDATED = "hourlyUpd"
EVENT_FORCE_MODE_TOGGLED = "forceModeTog"
EVENT_IRRIGATE_START = "start"

# Services
SERVICE_RESET_BUCKET = "reset_bucket"
SERVICE_CALCULATE_DAILY_ADJUSTED_RUN_TIME = "calculate_daily_adjusted_run_time"

# METRIC TO IMPERIAL (US) FACTORS
KMH_TO_MS_FACTOR = 3.6
W_TO_J_DAY_FACTOR = 86400
J_TO_MJ_FACTOR = 1000000
# Defaults
DEFAULT_NAME = NAME

# Types
TYPE_PRECIPITATION = "Precipitation"
TYPE_RAIN = "Rain"
TYPE_SNOW = "Snow"
TYPE_THROUGHPUT = "Throughput"
TYPE_PRECIPITATION_RATE = TYPE_PRECIPITATION + " Rate"
TYPE_EVAPOTRANSPIRATION = "Evapotranspiration"
TYPE_ADJUSTED_RUN_TIME = "Daily Adjusted Run Time"

# UNITS
UNIT_OF_MEASUREMENT_SECONDS = "s"
UNIT_OF_MEASUREMENT_MINUTES = "min"
UNIT_OF_MEASUREMENT_UNKNOWN = "unknown"
UNIT_OF_MEASUREMENT_LITERS = "l"
UNIT_OF_MEASUREMENT_MMS = "mm"
UNIT_OF_MEASUREMENT_M2 = "m2"
UNIT_OF_MEASUREMENT_MMS_HOUR = "mm/hr"
UNIT_OF_MEASUREMENT_LPM = "l/min"

# OPTIONS DEFAULTS
DEFAULT_MAXIMUM_DURATION = -1  # seconds
DEFAULT_SHOW_UNITS = False  # bool
DEFAULT_INITIAL_UPDATE_DELAY = 300  # seconds, 5 minutes

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

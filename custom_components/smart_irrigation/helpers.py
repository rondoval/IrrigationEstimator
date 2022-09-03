"""Helper functions."""

from .const import (
    CONF_SWITCH_SOURCE_PRECIPITATION,
    CONF_SWITCH_SOURCE_DAILY_TEMPERATURE,
    CONF_SWITCH_SOURCE_MINIMUM_TEMPERATURE,
    CONF_SWITCH_SOURCE_MAXIMUM_TEMPERATURE,
    CONF_SWITCH_SOURCE_DEWPOINT,
    CONF_SWITCH_SOURCE_PRESSURE,
    CONF_SWITCH_SOURCE_HUMIDITY,
    CONF_SWITCH_SOURCE_WINDSPEED,
    CONF_SENSOR_PRECIPITATION,
    CONF_SENSOR_DAILY_TEMPERATURE,
    CONF_SENSOR_DEWPOINT,
    CONF_SENSOR_HUMIDITY,
    CONF_SENSOR_MAXIMUM_TEMPERATURE,
    CONF_SENSOR_MINIMUM_TEMPERATURE,
    CONF_SENSOR_PRESSURE,
    CONF_SENSOR_WINDSPEED,
    CONF_SENSOR_SOLAR_RADIATION,
    CONF_SWITCH_SOURCE_SOLAR_RADIATION,
    CONF_SWITCH_CALCULATE_ET,
    CONF_SENSOR_ET,
)

from ..smart_irrigation import pyeto


def map_source_to_sensor(source):
    """Return the sensor setting for the source."""
    if source == CONF_SWITCH_SOURCE_PRECIPITATION:
        return CONF_SENSOR_PRECIPITATION
    if source == CONF_SWITCH_SOURCE_DAILY_TEMPERATURE:
        return CONF_SENSOR_DAILY_TEMPERATURE
    if source == CONF_SWITCH_SOURCE_DEWPOINT:
        return CONF_SENSOR_DEWPOINT
    if source == CONF_SWITCH_SOURCE_HUMIDITY:
        return CONF_SENSOR_HUMIDITY
    if source == CONF_SWITCH_SOURCE_MAXIMUM_TEMPERATURE:
        return CONF_SENSOR_MAXIMUM_TEMPERATURE
    if source == CONF_SWITCH_SOURCE_MINIMUM_TEMPERATURE:
        return CONF_SENSOR_MINIMUM_TEMPERATURE
    if source == CONF_SWITCH_SOURCE_PRESSURE:
        return CONF_SENSOR_PRESSURE
    if source == CONF_SWITCH_SOURCE_WINDSPEED:
        return CONF_SENSOR_WINDSPEED
    if source == CONF_SWITCH_SOURCE_SOLAR_RADIATION:
        return CONF_SENSOR_SOLAR_RADIATION
    if source == CONF_SWITCH_CALCULATE_ET:
        return CONF_SENSOR_ET
    return None


def check_all(settings, boolval):
    """Return true if all of the elements in the dictionary are equal to b (true/false)."""
    retval = True
    for aval in settings:
        if settings[aval] != boolval:
            retval = False
            break
    return retval


def check_time(itime):
    """Check time."""
    timesplit = itime.split(":")
    if len(timesplit) != 2:
        return False
    try:
        hours = int(timesplit[0])
        minutes = int(timesplit[1])
        if hours in range(0, 24) and minutes in range(
            0, 60
        ):  # range does not include upper bound
            return True
        return False
    except ValueError:
        return False


def convert_to_float(float_value):
    """Try to convert to float, otherwise returns 0."""
    try:
        return float(float_value)
    except ValueError:
        return 0


def average_of_list(the_list):
    """Return average of provided list."""
    if len(the_list) == 0:
        return 0
    return (sum(the_list) * 1.0) / len(the_list)

def last_of_list(the_list):
    """Return the last item of the provided list."""
    if len(the_list) == 0:
        return None
    return the_list[len(the_list) - 1]

def estimate_fao56_daily(  # pylint: disable=invalid-name
    day_of_year,
    temp_c,
    temp_c_min,
    temp_c_max,
    tdew,
    elevation,
    latitude,
    rh,
    wind_m_s,
    atmos_pres,
    coastal=False,
    calculate_solar_radiation=True,
    estimate_solrad_from_temp=True,
    sol_rad=None,
):
    """Estimate fao56 from weather."""
    sha = pyeto.sunset_hour_angle(pyeto.deg2rad(latitude), pyeto.sol_dec(day_of_year))
    daylight_hours = pyeto.daylight_hours(sha)

    ird = pyeto.inv_rel_dist_earth_sun(day_of_year)
    et_rad = pyeto.et_rad(pyeto.deg2rad(latitude), pyeto.sol_dec(day_of_year), sha, ird)

    cs_rad = pyeto.cs_rad(elevation, et_rad)

    # if we need to calculate solar_radiation we need to override the value passed in.
    if calculate_solar_radiation or sol_rad is None:
        if estimate_solrad_from_temp:
            sol_rad = pyeto.sol_rad_from_t(
                et_rad, cs_rad, temp_c_min, temp_c_max, coastal
            )
        else:
            # this is the default behavior for version < 0.0.50
            sol_rad = pyeto.sol_rad_from_sun_hours(
                daylight_hours, 0.8 * daylight_hours, et_rad
            )
    net_in_sol_rad = pyeto.net_in_sol_rad(sol_rad=sol_rad, albedo=0.23)
    avp = pyeto.avp_from_tdew(tdew)
    net_out_lw_rad = pyeto.net_out_lw_rad(
        pyeto.convert.celsius2kelvin(temp_c_min),
        pyeto.convert.celsius2kelvin(temp_c_max),
        sol_rad,
        cs_rad,
        avp,
    )
    net_rad = pyeto.net_rad(net_in_sol_rad, net_out_lw_rad)

    # experiment in v0.0.71: do not pass in day temperature (temp_c) but instead the average of temp_max and temp_min
    # see https://github.com/jeroenterheerdt/HAsmartirrigation/issues/70
    temp_c = (temp_c_min + temp_c_max) / 2.0

    eto = pyeto.fao56_penman_monteith(
        net_rad=net_rad,
        t=pyeto.convert.celsius2kelvin(temp_c),
        ws=wind_m_s,
        svp=pyeto.svp_from_t(temp_c),
        avp=avp,
        delta_svp=pyeto.delta_svp(temp_c),
        psy=pyeto.psy_const(
            atmos_pres / 10
        ),  # value stored is in hPa, but needs to be provided in kPa
    )
    return eto

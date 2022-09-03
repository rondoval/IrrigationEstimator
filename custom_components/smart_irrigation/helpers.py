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
    """Return true if all of the elements in the dictionary are equal to b."""
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


def estimate_fao56_hourly(
    day_of_year,
    temp_c,         # avg hourly temp [C]
    temp_c_min,     # 24h minimum temp [C]
    temp_c_max,     # 24h max temp [C]
    elevation,      # above sea level [m]
    latitude,
    rh,             # avg hourly relative humidity [%]
    wind_m_s,       # avg hourly wind speed [m/s]
    z,              # wind speed meas height [m]
    atmos_pres,     # atm. pressure, absolute [hPa]
    daylight,       # day=True
    sunshine_hours  # 24h sunshine hours
):

    """Estimate fao56 from weather."""

    svp = pyeto.svp_from_t(temp_c)
    avp = pyeto.avp_from_rhmax(svp, rh)

    sha = pyeto.sunset_hour_angle(
        pyeto.deg2rad(latitude),
        pyeto.sol_dec(day_of_year))

    et_rad = pyeto.et_rad(
        pyeto.deg2rad(latitude),
        pyeto.sol_dec(day_of_year),
        sha,
        pyeto.inv_rel_dist_earth_sun(day_of_year)
    )

    daylight_hours = pyeto.daylight_hours(sha)
    sol_rad = pyeto.sol_rad_from_sun_hours(
        daylight_hours,
        sunshine_hours,
        et_rad
    )

    net_in_sol_rad = pyeto.net_in_sol_rad(sol_rad, 0.23)
    net_out_lw_rad = pyeto.net_out_lw_rad(
        pyeto.convert.celsius2kelvin(temp_c_min),
        pyeto.convert.celsius2kelvin(temp_c_max),
        sol_rad,
        pyeto.cs_rad(elevation, et_rad),
        avp,
    )
    net_rad = pyeto.net_rad(net_in_sol_rad, net_out_lw_rad)

    eto = pyeto.fao56_penman_monteith(
        net_rad=net_rad,
        t=pyeto.convert.celsius2kelvin(temp_c),
        ws=pyeto.wind_speed_2m(wind_m_s, z),
        svp=svp,
        avp=avp,
        delta_svp=pyeto.delta_svp(temp_c),
        psy=pyeto.psy_const(
            atmos_pres / 10
        ),  # value stored is in hPa, but needs to be provided in kPa
        shf=soil_heat_flux(net_rad, daylight)
    )

    return eto


def soil_heat_flux(net_rad, daylight):
    if daylight:
        return 0.1 * net_rad
    else:
        return 0.5 * net_rad


def fao56_penman_monteith_hourly(net_rad, t, ws, svp, avp,
                                 delta_svp, psy, shf):
    """
    Estimate reference evapotranspiration (ETo) from a hypothetical
    short grass reference surface using the FAO-56 Penman-Monteith equation.

    Based on equation 53 in Allen et al (1998).

    :param net_rad: Net radiation at grass surface [MJ m-2 hour-1]. If
        necessary this can be estimated using ``net_rad()``.
    :param t: Mean hourly air temperature at 2 m height [deg Kelvin].
    :param ws: Average hourly wind speed at 2 m height [m s-1]. If not
        measured at 2m, convert using ``wind_speed_at_2m()``.
    :param svp: Saturation vapour pressure [kPa] at t. Can be estimated using
        ``svp_from_t()''.
    :param avp: Average hourly actual vapour pressure [kPa]. Can be estimated
        using a range of functions with names beginning with 'avp_from'.
    :param delta_svp: Slope of saturation vapour pressure curve [kPa degC-1].
        Can be estimated using ``delta_svp()``.
    :param psy: Psychrometric constant [kPa deg C]. Can be estimatred using
        ``psy_const_of_psychrometer()`` or ``psy_const()``.
    :param shf: Soil heat flux (G) [MJ m-2 hour-1] (default is 0.0, which is
        reasonable for a daily or 10-day time steps).
    :return: Reference evapotranspiration (ETo) from a hypothetical
        grass reference surface [mm hour-1].
    :rtype: float
    """
    a1 = (0.408 * (net_rad - shf) * delta_svp /
          (delta_svp + (psy * (1 + 0.34 * ws))))
    a2 = (37 * ws / t * (svp - avp) * psy /
          (delta_svp + (psy * (1 + 0.34 * ws))))
    return a1 + a2

"""Helper functions."""

from ..smart_irrigation import pyeto


def estimate_fao56_daily(
    day_of_year,
    latitude,
    elevation,  # above sea level [m]
    wind_meas_height,  # wind speed meas height [m]
    temp_c_min,  # 24h minimum temp [C]
    temp_c_max,  # 24h max temp [C]
    rh_min,  # 24h minimum relative humidity [%]
    rh_max,  # 24h max relative humidity [%]
    atmos_pres,  # 24h avg atm. pressure, absolute [hPa]
    wind_m_s,  # 24h avg wind speed [m/s]
    sunshine_hours,  # 24h sunshine hours
):

    """Estimate fao56 from weather."""
    temp_c_mean = pyeto.daily_mean_t(temp_c_min, temp_c_max)

    svp = pyeto.mean_svp(temp_c_min, temp_c_max)
    avp = pyeto.avp_from_rhmin_rhmax(
        pyeto.svp_from_t(temp_c_min), pyeto.svp_from_t(temp_c_max), rh_min, rh_max
    )

    sha = pyeto.sunset_hour_angle(pyeto.deg2rad(latitude), pyeto.sol_dec(day_of_year))

    et_rad = pyeto.et_rad(
        pyeto.deg2rad(latitude),
        pyeto.sol_dec(day_of_year),
        sha,
        pyeto.inv_rel_dist_earth_sun(day_of_year),
    )

    sol_rad = pyeto.sol_rad_from_sun_hours(
        pyeto.daylight_hours(sha), sunshine_hours, et_rad
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
        t=pyeto.convert.celsius2kelvin(temp_c_mean),
        ws=pyeto.wind_speed_2m(wind_m_s, wind_meas_height),
        svp=svp,
        avp=avp,
        delta_svp=pyeto.delta_svp(temp_c_mean),
        psy=pyeto.psy_const(
            atmos_pres / 10
        ),  # value stored is in hPa, but needs to be provided in kPa
        shf=0,
    )

    return eto

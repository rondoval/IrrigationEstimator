"""Helper functions."""

from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

import aquacropeto

from .const import CONVERT_W_M2_TO_MJ_M2_DAY


def get_config_value(config_entry: ConfigEntry, key: str) -> Any:
    """Get val from options or initial config"""
    if config_entry.options:
        return config_entry.options[key]
    return config_entry.data[key]


class MinMaxAvgTracker:
    """Tracking min, max and avg of a sensor"""

    def __init__(self):
        self.min = None
        self.max = None
        self.avg = None
        self._accumulator = 0
        self._count = 0

    def reset(self):
        """Reset values, restart tracking"""
        self.min = None
        self.max = None
        self.avg = None
        self._accumulator = 0
        self._count = 0

    def update(self, new_value):
        """Update with new value"""
        if self.min is None or self.min > new_value:
            self.min = new_value
        if self.max is None or self.max < new_value:
            self.max = new_value
        self._accumulator += new_value
        self._count += 1
        self.avg = self._accumulator / self._count

    def load_history(self, history_data) -> None:
        """Loads stats from source sensor history"""
        self.reset()
        for state in history_data:
            if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
                continue

            val = float(state.state)
            if self.min is None or self.min > val:
                self.min = val
            if self.max is None or self.max < val:
                self.max = val
            self._accumulator += val
            self._count += 1
        if self._count > 0:
            self.avg = self._accumulator / self._count

    def is_tracking(self):
        """Check if data is available"""
        return any(item is not None for item in (self.min, self.max, self.avg))


class SunshineTracker:
    """Calculates amount of bright sunshine hours based on input value that is related to solar radiation"""

    def __init__(self, radiation_watermark: float) -> None:
        self._radiation_watermark = radiation_watermark
        self._timestamp: datetime = None
        self.sunshine_hours = timedelta(seconds=0)

    def reset(self) -> None:
        """Resets the internal counter"""
        self.sunshine_hours = timedelta(seconds=0)

    def update(self, radiation: float) -> None:
        """Updates counters using a new value"""
        if self._timestamp is not None and radiation >= self._radiation_watermark:
            self.sunshine_hours += datetime.now() - self._timestamp
        self._timestamp = datetime.now()

    def get_hours(self) -> float:
        """Returns amount of sunshine hours counted"""
        return self.sunshine_hours / timedelta(hours=1)


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
    sol_rad=None,  # solar radioation [W*m-2]
    sunshine_hours=None,  # 24h sunshine hours
):

    """Estimate fao56 from weather."""
    temp_c_mean = aquacropeto.daily_mean_t(temp_c_min, temp_c_max)

    svp = aquacropeto.mean_svp(temp_c_min, temp_c_max)
    avp = aquacropeto.avp_from_rhmin_rhmax(
        aquacropeto.svp_from_t(temp_c_min),
        aquacropeto.svp_from_t(temp_c_max),
        rh_min,
        rh_max,
    )

    sha = aquacropeto.sunset_hour_angle(
        aquacropeto.deg2rad(latitude), aquacropeto.sol_dec(day_of_year)
    )

    et_rad = aquacropeto.et_rad(
        aquacropeto.deg2rad(latitude),
        aquacropeto.sol_dec(day_of_year),
        sha,
        aquacropeto.inv_rel_dist_earth_sun(day_of_year),
    )

    if sol_rad is None:
        sol_rad = aquacropeto.sol_rad_from_sun_hours(
            aquacropeto.daylight_hours(sha), sunshine_hours, et_rad
        )
    else:
        sol_rad *= CONVERT_W_M2_TO_MJ_M2_DAY

    net_in_sol_rad = aquacropeto.net_in_sol_rad(sol_rad, 0.23)
    net_out_lw_rad = aquacropeto.net_out_lw_rad(
        aquacropeto.celsius2kelvin(temp_c_min),
        aquacropeto.celsius2kelvin(temp_c_max),
        sol_rad,
        aquacropeto.cs_rad(elevation, et_rad),
        avp,
    )
    net_rad = aquacropeto.net_rad(net_in_sol_rad, net_out_lw_rad)

    eto = aquacropeto.fao56_penman_monteith(
        net_rad=net_rad,
        t=aquacropeto.celsius2kelvin(temp_c_mean),
        ws=aquacropeto.wind_speed_2m(wind_m_s, wind_meas_height),
        svp=svp,
        avp=avp,
        delta_svp=aquacropeto.delta_svp(temp_c_mean),
        psy=aquacropeto.psy_const(
            atmos_pres / 10
        ),  # value stored is in hPa, but needs to be provided in kPa
        shf=0,
    )

    return eto

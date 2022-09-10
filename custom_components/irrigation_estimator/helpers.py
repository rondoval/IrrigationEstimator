"""Helper functions."""

from datetime import datetime, timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from ..irrigation_estimator import pyeto
from homeassistant.config_entries import ConfigEntry
from typing import Any


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
        self.avg = self._accumulator / self._count

    def is_tracking(self):
        """Check if data is available"""
        return all(item is not None for item in (self.min, self.max, self.avg))


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

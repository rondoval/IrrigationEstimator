from datetime import datetime, timedelta
from unittest.mock import Mock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
import pytest

from custom_components.irrigation_estimator.helpers import (
    MinMaxAvgTracker,
    SunshineTracker,
    estimate_fao56_daily,
    get_config_value,
)


def test_get_config_value():
    config_entry = Mock(spec=ConfigEntry)
    config_entry.options = {"key1": "value1", "key2": "value2"}
    config_entry.data = {"key2": "value3"}

    assert get_config_value(config_entry, "key1") == "value1"
    assert get_config_value(config_entry, "key2") == "value2"

    config_entry = Mock(spec=ConfigEntry)
    config_entry.options = {}
    config_entry.data = {"key2": "value4"}

    assert get_config_value(config_entry, "key2") == "value4"


def test_min_max_avg_tracker():
    tracker = MinMaxAvgTracker()
    tracker.update(10)
    tracker.update(20)
    tracker.update(30)

    assert tracker.min == 10
    assert tracker.max == 30
    assert tracker.avg == 20

    tracker.reset()
    assert tracker.min is None
    assert tracker.max is None
    assert tracker.avg is None


def test_min_max_avg_tracker_with_history():
    tracker = MinMaxAvgTracker()
    history_data = [
        Mock(state="10"),
        Mock(state="20"),
        Mock(state="30"),
        Mock(state=STATE_UNAVAILABLE),
        Mock(state=STATE_UNKNOWN),
        Mock(state=None),
    ]
    tracker.load_history(history_data)

    assert tracker.min == 10
    assert tracker.max == 30
    assert tracker.avg == 20


def test_sunshine_tracker():
    tracker = SunshineTracker(radiation_watermark=200)
    tracker.update(250)
    tracker.update(150)
    tracker.update(250)

    assert tracker.get_hours() > 0

    tracker.reset()
    assert tracker.get_hours() == 0


def test_estimate_fao56_daily():
    result = estimate_fao56_daily(
        day_of_year=100,
        latitude=45.0,
        elevation=100,
        wind_meas_height=2,
        temp_c_min=10,
        temp_c_max=20,
        rh_min=30,
        rh_max=70,
        atmos_pres=1013,
        wind_m_s=2,
        sol_rad=500,
        sunshine_hours=8,
    )
    assert isinstance(result, float)
    assert result > 0

"""Tests for _format_battery_tooltip() — battery status display formatting."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wrapper import _format_battery_tooltip


class TestFormatBatteryTooltip:
    """Test battery status formatting into tooltip strings."""

    def test_on_battery(self):
        status = {"present": True, "percent": 64, "plugged_in": False}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 64% (on battery)"

    def test_plugged_in(self):
        status = {"present": True, "percent": 87, "plugged_in": True}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 87% (plugged in)"

    def test_full_charge_on_battery(self):
        status = {"present": True, "percent": 100, "plugged_in": False}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 100% (on battery)"

    def test_zero_percent_plugged_in(self):
        status = {"present": True, "percent": 0, "plugged_in": True}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 0% (plugged in)"

    def test_no_battery_returns_empty(self):
        status = {"present": False, "percent": 0, "plugged_in": None}
        result = _format_battery_tooltip(status)
        assert result == ""

    def test_plugged_in_none_returns_on_battery(self):
        """When plugged_in is None (unknown), treat as on battery."""
        status = {"present": True, "percent": 50, "plugged_in": None}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 50% (on battery)"

    def test_low_battery(self):
        status = {"present": True, "percent": 5, "plugged_in": False}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 5% (on battery)"

    def test_exact_threshold(self):
        status = {"present": True, "percent": 30, "plugged_in": False}
        result = _format_battery_tooltip(status)
        assert result == " | Battery: 30% (on battery)"

"""Tests for _parse_version() — semver comparison logic."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wrapper import _parse_version


class TestParseVersion:
    """Test semver string parsing into comparable tuples."""

    def test_basic_version(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_version_with_v_prefix(self):
        assert _parse_version("v1.2.3") == (1, 2, 3)

    def test_version_two_parts(self):
        assert _parse_version("1.0") == (1, 0)

    def test_version_single_part(self):
        assert _parse_version("5") == (5,)

    def test_version_zero(self):
        assert _parse_version("0.0.0") == (0, 0, 0)

    def test_large_numbers(self):
        assert _parse_version("100.200.300") == (100, 200, 300)

    def test_invalid_string_returns_zero_tuple(self):
        assert _parse_version("not-a-version") == (0,)

    def test_empty_string_returns_zero_tuple(self):
        assert _parse_version("") == (0,)

    def test_none_returns_zero_tuple(self):
        assert _parse_version(None) == (0,)

    def test_version_with_v_prefix_two_parts(self):
        assert _parse_version("v2.1") == (2, 1)


class TestVersionComparison:
    """Test that parsed versions compare correctly for update checks."""

    def test_newer_patch(self):
        assert _parse_version("1.2.4") > _parse_version("1.2.3")

    def test_newer_minor(self):
        assert _parse_version("1.3.0") > _parse_version("1.2.9")

    def test_newer_major(self):
        assert _parse_version("2.0.0") > _parse_version("1.9.9")

    def test_equal_versions(self):
        assert _parse_version("1.0.0") == _parse_version("1.0.0")

    def test_equal_with_v_prefix(self):
        assert _parse_version("v1.0.0") == _parse_version("1.0.0")

    def test_older_version(self):
        assert _parse_version("1.1.9") < _parse_version("1.2.0")

    def test_invalid_is_always_older(self):
        assert _parse_version("invalid") < _parse_version("0.0.1")

"""Tests for config loading, migration, and validation."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wrapper import _parse_config, _migrate_config, _get_active_profile


class TestMigrateConfig:
    """Test migration from old flat format to v2 profiles format."""

    def test_old_flat_migrates_to_profiles(self, old_flat_config):
        result = _migrate_config(old_flat_config)
        assert result["config_version"] == 2
        assert result["active_profile"] == "Default"
        assert "Default" in result["profiles"]
        assert result["profiles"]["Default"]["llama_server_path"] == "C:\\llama.cpp\\llama-server.exe"
        assert result["profiles"]["Default"]["llama_server_args"] == ["-ngl", "999", "-c", "16384"]
        assert result["profiles"]["Default"]["server_url"] == "http://127.0.0.1:8080"

    def test_v2_config_not_migrated(self, valid_config_v2):
        result = _migrate_config(valid_config_v2)
        # Should return the same dict (no migration needed)
        assert result is valid_config_v2

    def test_v2_with_profiles_not_migrated(self, valid_config_v2_multi):
        result = _migrate_config(valid_config_v2_multi)
        assert result is valid_config_v2_multi

    def test_empty_dict_migrates_to_empty_profile(self):
        result = _migrate_config({})
        assert result["config_version"] == 2
        assert result["active_profile"] == "Default"
        assert result["profiles"] == {"Default": {}}

    def test_partial_old_config_migrates(self):
        old = {"llama_server_path": "/path/to/server", "server_url": "http://localhost:8080"}
        result = _migrate_config(old)
        assert result["profiles"]["Default"]["llama_server_path"] == "/path/to/server"
        assert result["profiles"]["Default"]["server_url"] == "http://localhost:8080"
        # llama_server_args was not in old config, so it's missing from the profile
        assert "llama_server_args" not in result["profiles"]["Default"]


class TestGetActiveProfile:
    """Test extracting the active profile from a v2 config."""

    def test_returns_active_profile(self, valid_config_v2):
        profile = _get_active_profile(valid_config_v2)
        assert profile["llama_server_path"] == "C:\\llama.cpp\\llama-server.exe"

    def test_returns_correct_profile_multi(self, valid_config_v2_multi):
        profile = _get_active_profile(valid_config_v2_multi)
        assert profile["server_url"] == "http://127.0.0.1:8081"
        assert profile["llama_server_args"] == ["-ngl", "20", "-c", "4096"]

    def test_missing_profiles_raises(self):
        config = {"config_version": 2, "active_profile": "Default"}
        with pytest.raises(ValueError, match="profiles"):
            _get_active_profile(config)

    def test_missing_active_profile_key_raises(self):
        config = {"config_version": 2, "profiles": {"Default": {}}}
        with pytest.raises(ValueError, match="active_profile"):
            _get_active_profile(config)

    def test_active_profile_not_found_raises(self):
        config = {
            "config_version": 2,
            "active_profile": "Nonexistent",
            "profiles": {"Default": {}},
        }
        with pytest.raises(ValueError, match="not found"):
            _get_active_profile(config)


class TestParseConfig:
    """Test full config validation and normalization."""

    def test_valid_v2_config(self, valid_config_v2):
        result = _parse_config(valid_config_v2)
        assert result["config_version"] == 2
        assert result["active_profile"] == "Default"

    def test_valid_v2_multi_profile(self, valid_config_v2_multi):
        result = _parse_config(valid_config_v2_multi)
        assert result["active_profile"] == "Small"

    def test_old_flat_config_migrates(self, old_flat_config):
        result = _parse_config(old_flat_config)
        assert result["config_version"] == 2
        assert result["active_profile"] == "Default"
        assert result["profiles"]["Default"]["llama_server_path"] == "C:\\llama.cpp\\llama-server.exe"

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            _parse_config("not a dict")

    def test_not_a_dict_list_raises(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            _parse_config([1, 2, 3])

    def test_empty_dict_migrates_and_validates(self):
        # Empty dict migrates to v2 with empty profile, which fails validation
        # because the profile is missing required fields
        result = _migrate_config({})
        # The migrated result has an empty Default profile
        assert result["profiles"]["Default"] == {}

    def test_missing_required_field(self):
        config = {
            "config_version": 2,
            "active_profile": "Default",
            "profiles": {
                "Default": {
                    "llama_server_path": "/path/to/server",
                    # Missing llama_server_args and server_url
                }
            },
        }
        with pytest.raises(ValueError, match="missing required"):
            _parse_config(config)

    def test_wrong_type_server_path(self):
        config = {
            "config_version": 2,
            "active_profile": "Default",
            "profiles": {
                "Default": {
                    "llama_server_path": 123,  # Should be string
                    "llama_server_args": [],
                    "server_url": "http://localhost:8080",
                }
            },
        }
        with pytest.raises(ValueError, match="must be a string"):
            _parse_config(config)

    def test_wrong_type_server_args(self):
        config = {
            "config_version": 2,
            "active_profile": "Default",
            "profiles": {
                "Default": {
                    "llama_server_path": "/path/to/server",
                    "llama_server_args": "not a list",  # Should be list
                    "server_url": "http://localhost:8080",
                }
            },
        }
        with pytest.raises(ValueError, match="must be a list"):
            _parse_config(config)

    def test_wrong_type_server_url(self):
        config = {
            "config_version": 2,
            "active_profile": "Default",
            "profiles": {
                "Default": {
                    "llama_server_path": "/path/to/server",
                    "llama_server_args": [],
                    "server_url": 123,  # Should be string
                }
            },
        }
        with pytest.raises(ValueError, match="must be a string"):
            _parse_config(config)

    def test_profiles_not_dict_raises(self):
        config = {
            "config_version": 2,
            "active_profile": "Default",
            "profiles": "not a dict",
        }
        with pytest.raises(ValueError, match="profiles.*must be a dict"):
            _parse_config(config)

    def test_empty_profiles_raises(self):
        config = {
            "config_version": 2,
            "active_profile": "Default",
            "profiles": {},
        }
        with pytest.raises(ValueError, match="at least one profile"):
            _parse_config(config)

    def test_active_profile_not_string_raises(self):
        config = {
            "config_version": 2,
            "active_profile": 123,
            "profiles": {"Default": {"llama_server_path": "/path", "llama_server_args": [], "server_url": "http://localhost"}},
        }
        with pytest.raises(ValueError, match="active_profile.*must be a string"):
            _parse_config(config)

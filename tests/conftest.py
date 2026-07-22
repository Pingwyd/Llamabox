"""Shared test fixtures for LlamaBox smoke tests."""
import sys
import os
import pytest

# Add the project root to sys.path so we can import wrapper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Valid config fixtures (v2 profiles format)
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_config_v2():
    """A valid v2 config dict with one profile."""
    return {
        "config_version": 2,
        "active_profile": "Default",
        "profiles": {
            "Default": {
                "llama_server_path": "C:\\llama.cpp\\llama-server.exe",
                "llama_server_args": ["-ngl", "999", "-c", "16384"],
                "server_url": "http://127.0.0.1:8080",
            }
        },
    }


@pytest.fixture
def valid_config_v2_multi():
    """A valid v2 config dict with multiple profiles."""
    return {
        "config_version": 2,
        "active_profile": "Small",
        "profiles": {
            "Default": {
                "llama_server_path": "C:\\llama.cpp\\llama-server.exe",
                "llama_server_args": ["-ngl", "999", "-c", "16384"],
                "server_url": "http://127.0.0.1:8080",
            },
            "Small": {
                "llama_server_path": "C:\\llama.cpp\\llama-server.exe",
                "llama_server_args": ["-ngl", "20", "-c", "4096"],
                "server_url": "http://127.0.0.1:8081",
            },
        },
    }


@pytest.fixture
def old_flat_config():
    """An old v1 flat-format config (before profiles were added)."""
    return {
        "llama_server_path": "C:\\llama.cpp\\llama-server.exe",
        "llama_server_args": ["-ngl", "999", "-c", "16384"],
        "server_url": "http://127.0.0.1:8080",
    }

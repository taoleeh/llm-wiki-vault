"""Tests for valhopper.config."""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.config import load_config, write_default_config, DEFAULTS


def test_load_config_missing_file():
    cfg = load_config("/nonexistent/path.yaml")
    assert cfg["network"] == "finney"
    assert cfg["risk_level"] == "moderate"


def test_load_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("network: local\nrisk_level: aggressive\n")
        f.flush()
        cfg = load_config(f.name)
        os.unlink(f.name)
    assert cfg["network"] == "local"
    assert cfg["risk_level"] == "aggressive"


def test_load_config_ignores_unknown_keys():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("network: finney\nunknown_key: 123\n")
        f.flush()
        cfg = load_config(f.name)
        os.unlink(f.name)
    assert "unknown_key" not in cfg


def test_load_config_none_values_not_overriding():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("coldkey: null\nnetwork: finney\n")
        f.flush()
        cfg = load_config(f.name)
        os.unlink(f.name)
    assert cfg["coldkey"] is None


def test_write_default_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "config.yaml")
        result = write_default_config(path)
        assert result.is_file()
        cfg = load_config(path)
        assert cfg["network"] == "finney"
        assert cfg["risk_level"] == "moderate"


def test_defaults_structure():
    assert "coldkey" in DEFAULTS
    assert "network" in DEFAULTS
    assert "risk_level" in DEFAULTS
    assert "min_improvement" in DEFAULTS
    assert "discord_webhook_url" in DEFAULTS
    assert "format" in DEFAULTS

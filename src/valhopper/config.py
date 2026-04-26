"""ValHopper configuration file loading."""

import os
from pathlib import Path
from typing import Optional

import yaml


CONFIG_DIR = Path.home() / ".valhopper"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULTS = {
    "coldkey": None,
    "wallet_name": None,
    "wallet_hotkey": "default",
    "wallet_path": "~/.bittensor/wallets",
    "network": "finney",
    "risk_level": "moderate",
    "min_improvement": 0.0,
    "format": "table",
    "discord_webhook_url": None,
}


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_config(config_path: Optional[str] = None) -> dict:
    """Load config from YAML file, falling back to defaults.

    Priority: CLI args > config file > env vars > defaults.
    This function returns config file + defaults merged.
    CLI arg overriding is handled in the CLI layer.
    """
    path = Path(config_path) if config_path else CONFIG_FILE
    file_data = _load_yaml(path)
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in file_data.items() if k in DEFAULTS and v is not None})
    return merged


def write_default_config(path: Optional[str] = None) -> Path:
    """Write a default config file with comments."""
    target = Path(path) if path else CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    content = """\
# ValHopper Configuration
# See: https://github.com/taoleeh/valhopper for docs

# Coldkey SS58 address (override with --coldkey)
coldkey: null

# Wallet settings
wallet_name: null
wallet_hotkey: default
wallet_path: ~/.bittensor/wallets

# Network
network: finney

# Default risk level: conservative, moderate, aggressive
risk_level: moderate

# Minimum return_per_1000 improvement to justify a move (0 = no minimum)
min_improvement: 0.0

# Output format: table, json
format: table

# Discord webhook URL for notifications (null = disabled)
discord_webhook_url: null
"""
    target.write_text(content, encoding="utf-8")
    return target

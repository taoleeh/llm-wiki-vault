"""Tests for valhopper_logging — format_json_output."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.valhopper_logging import format_json_output


def test_format_json_output_basic():
    result = format_json_output("list-stakes", {"coldkey": "abc", "positions": []})
    parsed = json.loads(result)
    assert parsed["command"] == "list-stakes"
    assert parsed["coldkey"] == "abc"
    assert parsed["positions"] == []


def test_format_json_output_with_float():
    result = format_json_output("optimize", {
        "total_daily_gain": 1.5,
        "dry_run": True,
    })
    parsed = json.loads(result)
    assert parsed["total_daily_gain"] == 1.5
    assert parsed["dry_run"] is True


def test_format_json_output_default_str():
    result = format_json_output("test", {"value": set([1, 2])})
    parsed = json.loads(result)
    assert isinstance(parsed["value"], str)

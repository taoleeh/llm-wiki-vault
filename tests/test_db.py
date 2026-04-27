"""Tests for valhopper.db — SQLite yield history."""
import os
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.db import (
    _get_db,
    record_validator_snapshot,
    record_position_snapshot,
    get_validator_history,
    get_subnet_history,
    get_position_history,
    detect_declining_validators,
)


def _fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = _get_db(path)
    return conn, path


def _cleanup(conn, path):
    conn.close()
    os.unlink(path)


def test_record_and_get_validator_history():
    conn, path = _fresh_db()
    record_validator_snapshot(conn, "2026-04-20", 1, "hk1", 100.0, trust=0.9)
    record_validator_snapshot(conn, "2026-04-21", 1, "hk1", 95.0, trust=0.9)
    history = get_validator_history(conn, 1, "hk1")
    assert len(history) == 2
    assert history[0]["snapshot_date"] == "2026-04-21"
    assert history[0]["return_per_1000"] == 95.0
    _cleanup(conn, path)


def test_record_validator_snapshot_upsert():
    conn, path = _fresh_db()
    record_validator_snapshot(conn, "2026-04-20", 1, "hk1", 100.0)
    record_validator_snapshot(conn, "2026-04-20", 1, "hk1", 110.0)
    history = get_validator_history(conn, 1, "hk1")
    assert len(history) == 1
    assert history[0]["return_per_1000"] == 110.0
    _cleanup(conn, path)


def test_get_subnet_history():
    conn, path = _fresh_db()
    record_validator_snapshot(conn, "2026-04-20", 1, "hk1", 100.0)
    record_validator_snapshot(conn, "2026-04-20", 1, "hk2", 50.0)
    record_validator_snapshot(conn, "2026-04-21", 1, "hk1", 90.0)
    result = get_subnet_history(conn, 1)
    assert len(result) == 2
    assert result[0]["return_per_1000"] >= result[1]["return_per_1000"]
    _cleanup(conn, path)


def test_position_snapshots():
    conn, path = _fresh_db()
    record_position_snapshot(conn, "2026-04-20", "cold1", 1, "hk1", 10.0, 50.0, 0.5)
    record_position_snapshot(conn, "2026-04-21", "cold1", 1, "hk1", 10.0, 55.0, 0.55)
    history = get_position_history(conn, "cold1")
    assert len(history) == 2
    assert history[0]["snapshot_date"] == "2026-04-21"
    _cleanup(conn, path)


def test_detect_declining_validators():
    conn, path = _fresh_db()
    record_validator_snapshot(conn, "2026-04-10", 1, "hk1", 100.0)
    record_validator_snapshot(conn, "2026-04-17", 1, "hk1", 50.0)
    declining = detect_declining_validators(conn, 1, min_days=7, decline_threshold=0.3)
    assert len(declining) == 1
    assert declining[0]["hotkey"] == "hk1"
    _cleanup(conn, path)


def test_detect_declining_validators_no_decline():
    conn, path = _fresh_db()
    record_validator_snapshot(conn, "2026-04-10", 1, "hk1", 100.0)
    record_validator_snapshot(conn, "2026-04-17", 1, "hk1", 110.0)
    declining = detect_declining_validators(conn, 1, min_days=7, decline_threshold=0.3)
    assert len(declining) == 0
    _cleanup(conn, path)


def test_empty_history():
    conn, path = _fresh_db()
    assert get_validator_history(conn, 999, "nonexistent") == []
    assert get_position_history(conn, "nonexistent") == []
    assert get_subnet_history(conn, 999) == []
    _cleanup(conn, path)

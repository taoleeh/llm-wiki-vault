"""Tests for optimize command logic — now using models.StakePosition."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.models import StakePosition


def test_max_stake_filter_logic():
    positions = [
        StakePosition(hotkey="hk1", netuid=1, stake_tao=10.0,
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk2"),
        StakePosition(hotkey="hk3", netuid=1, stake_tao=50.0,
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk4"),
        StakePosition(hotkey="hk5", netuid=1, stake_tao=5.0,
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk6"),
    ]
    max_stake = 20.0
    filtered = [p for p in positions if p.stake_tao <= max_stake]
    assert len(filtered) == 2
    assert filtered[0].stake_tao == 10.0
    assert filtered[1].stake_tao == 5.0


def test_stake_position_daily_earn():
    pos = StakePosition(
        hotkey="hk1", netuid=1, stake_tao=2000.0,
        current_validator_return=0.5, best_validator_return=1.0,
        best_validator_hotkey="hk2",
    )
    assert pos.current_daily_earn == 1.0
    assert pos.new_daily_earn == 2.0
    assert pos.return_delta == 0.5
    assert pos.potential_additional_daily == 1.0


def test_movability_filter():
    pos1 = StakePosition(
        hotkey="hk1", netuid=1, stake_tao=10.0,
        current_validator_return=0.2, best_validator_return=0.2,
        best_validator_hotkey="hk1",
    )
    pos2 = StakePosition(
        hotkey="hk2", netuid=1, stake_tao=10.0,
        current_validator_return=0.1, best_validator_return=0.0,
        best_validator_hotkey="",
    )
    pos3 = StakePosition(
        hotkey="hk3", netuid=1, stake_tao=10.0,
        current_validator_return=0.1, best_validator_return=0.2,
        best_validator_hotkey="hk4",
    )
    movable = [
        p for p in [pos1, pos2, pos3]
        if p.best_validator_hotkey
        and p.hotkey != p.best_validator_hotkey
        and p.return_delta > 0
    ]
    assert len(movable) == 1
    assert movable[0].hotkey == "hk3"

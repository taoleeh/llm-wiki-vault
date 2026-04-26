"""Tests for optimize command logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bittensor import Balance
from valhopper.valhopper_cli import StakePosition


def test_max_stake_filter_logic():
    """Test the max stake filter logic."""
    positions = [
        StakePosition(
            hotkey="hk1", netuid=1, stake=Balance.from_tao(10.0),
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk2",
        ),
        StakePosition(
            hotkey="hk3", netuid=1, stake=Balance.from_tao(50.0),
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk4",
        ),
        StakePosition(
            hotkey="hk5", netuid=1, stake=Balance.from_tao(5.0),
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk6",
        ),
    ]

    max_stake = 20.0
    filtered = [p for p in positions if p.stake.tao <= max_stake]

    assert len(filtered) == 2
    assert filtered[0].stake.tao == 10.0
    assert filtered[1].stake.tao == 5.0
    print("✓ Max stake filter logic")


def test_stake_position_daily_earn():
    """Test daily earn calculations."""
    pos = StakePosition(
        hotkey="hk1", netuid=1, stake=Balance.from_tao(2000.0),
        current_validator_return=0.5, best_validator_return=1.0,
        best_validator_hotkey="hk2",
    )

    # daily_earn = (stake / 1000) * return_per_1k
    assert pos.current_daily_earn == 1.0    # (2000/1000) * 0.5
    assert pos.new_daily_earn == 2.0        # (2000/1000) * 1.0
    assert pos.return_delta == 0.5
    assert pos.potential_additional_daily == 1.0
    print("✓ Daily earn calculations")


def test_movability_filter():
    """Test that movable positions are correctly identified."""
    stake = Balance.from_tao(10.0)

    # Already with best validator
    pos1 = StakePosition(
        hotkey="hk1", netuid=1, stake=stake,
        current_validator_return=0.2, best_validator_return=0.2,
        best_validator_hotkey="hk1",
    )

    # No best validator
    pos2 = StakePosition(
        hotkey="hk2", netuid=1, stake=stake,
        current_validator_return=0.1, best_validator_return=0.0,
        best_validator_hotkey="",
    )

    # Better validator available
    pos3 = StakePosition(
        hotkey="hk3", netuid=1, stake=stake,
        current_validator_return=0.1, best_validator_return=0.2,
        best_validator_hotkey="hk4",
    )

    positions = [pos1, pos2, pos3]
    movable = [
        p for p in positions
        if p.best_validator_hotkey
        and p.hotkey != p.best_validator_hotkey
        and p.return_delta > 0
    ]

    assert len(movable) == 1
    assert movable[0].hotkey == "hk3"
    print("✓ Movability filter")


if __name__ == '__main__':
    print("Running optimize logic tests...\n")
    test_max_stake_filter_logic()
    test_stake_position_daily_earn()
    test_movability_filter()
    print("\n✓ All tests passed!")

"""Tests for valhopper.models."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.models import (
    ReturnError,
    ReturnResult,
    StakePosition,
    get_token_symbol,
    fmt_ret,
    color_trust,
    color_age,
    RISK_LEVELS,
    BLOCKS_PER_DAY,
    SECONDS_PER_BLOCK,
)


def test_return_result_success():
    result = ReturnResult(value=1.5, error=ReturnError.NO_ERROR, message="")
    assert result.value == 1.5
    assert not result.is_error
    assert result.to_dict()["error"] == "no_error"


def test_return_result_not_in_metagraph():
    result = ReturnResult(
        value=0.0, error=ReturnError.VALIDATOR_NOT_IN_METAGRAPH, message="Not found"
    )
    assert result.is_error


def test_return_result_network_error():
    result = ReturnResult(
        value=0.0, error=ReturnError.NETWORK_ERROR, message="Connection timeout"
    )
    assert result.is_error


def test_return_result_no_stake():
    result = ReturnResult(value=0.0, error=ReturnError.NO_STAKE, message="No stake")
    assert result.error == ReturnError.NO_STAKE


def test_return_result_no_emission():
    result = ReturnResult(value=0.0, error=ReturnError.NO_EMISSION, message="No emission")
    assert result.error == ReturnError.NO_EMISSION


def test_stake_position_daily_earn():
    pos = StakePosition(
        hotkey="hk1",
        netuid=1,
        stake_tao=2000.0,
        current_validator_return=0.5,
        best_validator_return=1.0,
        best_validator_hotkey="hk2",
    )
    assert pos.current_daily_earn == 1.0
    assert pos.new_daily_earn == 2.0
    assert pos.return_delta == 0.5
    assert pos.potential_additional_daily == 1.0


def test_stake_position_to_dict():
    pos = StakePosition(
        hotkey="hk1",
        netuid=1,
        stake_tao=10.0,
        current_validator_return=0.1,
        best_validator_return=0.2,
        best_validator_hotkey="hk2",
    )
    d = pos.to_dict()
    assert d["hotkey"] == "hk1"
    assert d["netuid"] == 1
    assert d["stake_tao"] == 10.0
    assert d["return_delta"] == 0.1


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
    positions = [pos1, pos2, pos3]
    movable = [
        p for p in positions
        if p.best_validator_hotkey
        and p.hotkey != p.best_validator_hotkey
        and p.return_delta > 0
    ]
    assert len(movable) == 1
    assert movable[0].hotkey == "hk3"


def test_max_stake_filter():
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


def test_fmt_ret():
    assert fmt_ret(0) == "0"
    assert fmt_ret(0.001) == "0.001000"
    assert fmt_ret(0.5) == "0.5000"
    assert fmt_ret(50.0) == "50.00"
    assert fmt_ret(500.0) == "500.0"


def test_get_token_symbol():
    assert get_token_symbol(0) == "\u03c4"
    assert get_token_symbol(1) == "\u03b1"
    assert get_token_symbol(99) == "S99"


def test_color_trust():
    assert "[green]" in color_trust(0.96)
    assert "[yellow]" in color_trust(0.85)
    assert "[red]" in color_trust(0.3)
    assert color_trust(0.0) == "-"


def test_color_age():
    assert color_age(0) == "-"
    assert "[green]" in color_age(100)
    assert "[yellow]" in color_age(45)
    assert "[red]" in color_age(10)


def test_constants():
    assert SECONDS_PER_BLOCK == 12
    assert BLOCKS_PER_DAY == 7200


def test_risk_levels_keys():
    assert set(RISK_LEVELS.keys()) == {"conservative", "moderate", "aggressive"}


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

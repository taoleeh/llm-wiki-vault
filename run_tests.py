#!/usr/bin/env python3
"""Test runner for ValHopper."""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bittensor import Balance
from valhopper.valhopper_cli import BittensorClient, ReturnError, ReturnResult, StakePosition

passed = 0
failed = 0


def run(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✓ {name}")
        passed += 1
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        failed += 1


# --- Cache tests ---

def test_cache_none_invalid():
    client = BittensorClient('finney')
    assert not client._cache_is_valid(None)

def test_cache_fresh_valid():
    client = BittensorClient('finney')
    assert client._cache_is_valid(("data", time.time()))

def test_cache_stale_invalid():
    client = BittensorClient('finney')
    assert not client._cache_is_valid(("data", time.time() - 400))

def test_refresh_clears_all():
    client = BittensorClient('finney')
    client._delegates_cache = ([], time.time())
    client._metagraph_cache = {1: ({}, time.time())}
    client._current_block = (1000, time.time())
    client._tempo_cache = {1: (360, time.time())}
    client.refresh_caches()
    assert client._delegates_cache is None
    assert client._metagraph_cache == {}
    assert client._current_block is None
    assert client._tempo_cache == {}


# --- ReturnResult tests ---

def test_return_result_success():
    r = ReturnResult(1.5, ReturnError.NO_ERROR, "")
    assert r.value == 1.5
    assert not r.is_error

def test_return_result_network_error():
    r = ReturnResult(0.0, ReturnError.NETWORK_ERROR, "timeout")
    assert r.is_error

def test_return_result_no_stake():
    r = ReturnResult(0.0, ReturnError.NO_STAKE, "no stake")
    assert r.error == ReturnError.NO_STAKE
    assert r.is_error

def test_return_result_no_emission():
    r = ReturnResult(0.0, ReturnError.NO_EMISSION, "no emission")
    assert r.error == ReturnError.NO_EMISSION
    assert r.is_error


# --- StakePosition tests ---

def test_daily_earn():
    pos = StakePosition(
        hotkey="hk1", netuid=1, stake=Balance.from_tao(2000.0),
        current_validator_return=0.5, best_validator_return=1.0,
        best_validator_hotkey="hk2",
    )
    assert pos.current_daily_earn == 1.0
    assert pos.new_daily_earn == 2.0
    assert pos.return_delta == 0.5
    assert pos.potential_additional_daily == 1.0

def test_max_stake_filter():
    positions = [
        StakePosition(hotkey="hk1", netuid=1, stake=Balance.from_tao(10.0),
                      current_validator_return=0.1, best_validator_return=0.2,
                      best_validator_hotkey="hk2"),
        StakePosition(hotkey="hk3", netuid=1, stake=Balance.from_tao(50.0),
                      current_validator_return=0.1, best_validator_return=0.2,
                      best_validator_hotkey="hk4"),
    ]
    filtered = [p for p in positions if p.stake.tao <= 20.0]
    assert len(filtered) == 1
    assert filtered[0].hotkey == "hk1"

def test_movability_filter():
    stake = Balance.from_tao(10.0)
    positions = [
        StakePosition(hotkey="hk1", netuid=1, stake=stake,
                      current_validator_return=0.2, best_validator_return=0.2,
                      best_validator_hotkey="hk1"),  # same validator
        StakePosition(hotkey="hk2", netuid=1, stake=stake,
                      current_validator_return=0.1, best_validator_return=0.0,
                      best_validator_hotkey=""),  # no best
        StakePosition(hotkey="hk3", netuid=1, stake=stake,
                      current_validator_return=0.1, best_validator_return=0.2,
                      best_validator_hotkey="hk4"),  # movable
    ]
    movable = [p for p in positions
               if p.best_validator_hotkey
               and p.hotkey != p.best_validator_hotkey
               and p.return_delta > 0]
    assert len(movable) == 1
    assert movable[0].hotkey == "hk3"


if __name__ == '__main__':
    print("=== ValHopper Test Suite ===\n")

    print("Cache:")
    run("None data invalid", test_cache_none_invalid)
    run("Fresh data valid", test_cache_fresh_valid)
    run("Stale data invalid", test_cache_stale_invalid)
    run("Refresh clears all", test_refresh_clears_all)

    print("\nReturnResult:")
    run("Success case", test_return_result_success)
    run("Network error", test_return_result_network_error)
    run("No stake", test_return_result_no_stake)
    run("No emission", test_return_result_no_emission)

    print("\nStakePosition:")
    run("Daily earn calc", test_daily_earn)
    run("Max stake filter", test_max_stake_filter)
    run("Movability filter", test_movability_filter)

    print(f"\n{'='*30}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

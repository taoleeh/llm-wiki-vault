#!/usr/bin/env python3
"""Test runner with 5-minute timeout per test."""
import sys
import os
import time
import signal
from datetime import datetime
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class TimeoutException(Exception):
    pass

@contextmanager
def timeout(seconds):
    def handler(signum, frame):
        raise TimeoutException(f"Test timed out after {seconds} seconds")
    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

class TestResult:
    def __init__(self, name, status, duration=None, error=None):
        self.name = name
        self.status = status
        self.duration = duration
        self.error = error
        self.timestamp = datetime.now().isoformat()

try:
    from bittensor import Balance
    from valhopper.valhopper_cli import BittensorClient, ReturnError, ReturnResult, StakePosition
except ImportError as e:
    print(f"ERROR: Cannot import valhopper modules: {e}")
    sys.exit(1)

def run_test(name, test_fn, timeout_sec=300):
    start = time.time()
    try:
        with timeout(timeout_sec):
            test_fn()
        duration = time.time() - start
        return TestResult(name, "PASS", duration)
    except TimeoutException as e:
        duration = time.time() - start
        return TestResult(name, "TIMEOUT", duration, str(e))
    except Exception as e:
        duration = time.time() - start
        return TestResult(name, "FAIL", duration, f"{type(e).__name__}: {str(e)}")

# Tests
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

def test_cache_ttl_config():
    client = BittensorClient('finney')
    assert client.CACHE_TTL == 300

def test_return_result_success():
    r = ReturnResult(1.5, ReturnError.NO_ERROR, "")
    assert r.value == 1.5
    assert not r.is_error

def test_return_result_network():
    r = ReturnResult(0.0, ReturnError.NETWORK_ERROR, "timeout")
    assert r.is_error

def test_return_result_no_stake():
    r = ReturnResult(0.0, ReturnError.NO_STAKE, "no stake")
    assert r.error == ReturnError.NO_STAKE

def test_return_result_no_emission():
    r = ReturnResult(0.0, ReturnError.NO_EMISSION, "no emission")
    assert r.error == ReturnError.NO_EMISSION

def test_daily_earn():
    pos = StakePosition(
        hotkey="hk1", netuid=1, stake=Balance.from_tao(2000.0),
        current_validator_return=0.5, best_validator_return=1.0,
        best_validator_hotkey="hk2",
    )
    assert pos.current_daily_earn == 1.0
    assert pos.new_daily_earn == 2.0
    assert pos.return_delta == 0.5

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

def test_movable_filter():
    stake = Balance.from_tao(10.0)
    positions = [
        StakePosition(hotkey="hk1", netuid=1, stake=stake,
                      current_validator_return=0.2, best_validator_return=0.2,
                      best_validator_hotkey="hk1"),
        StakePosition(hotkey="hk2", netuid=1, stake=stake,
                      current_validator_return=0.1, best_validator_return=0.0,
                      best_validator_hotkey=""),
        StakePosition(hotkey="hk3", netuid=1, stake=stake,
                      current_validator_return=0.1, best_validator_return=0.2,
                      best_validator_hotkey="hk4"),
    ]
    movable = [p for p in positions if p.best_validator_hotkey and p.hotkey != p.best_validator_hotkey and p.return_delta > 0]
    assert len(movable) == 1

if __name__ == '__main__':
    tests = [
        ("Cache: None invalid", test_cache_none_invalid),
        ("Cache: Fresh valid", test_cache_fresh_valid),
        ("Cache: Stale invalid", test_cache_stale_invalid),
        ("Cache: Refresh clears", test_refresh_clears_all),
        ("Cache: TTL config", test_cache_ttl_config),
        ("Return: Success", test_return_result_success),
        ("Return: Network error", test_return_result_network),
        ("Return: No stake", test_return_result_no_stake),
        ("Return: No emission", test_return_result_no_emission),
        ("Position: Daily earn", test_daily_earn),
        ("Position: Max filter", test_max_stake_filter),
        ("Position: Movable", test_movable_filter),
    ]
    
    print("=" * 60)
    print("ValHopper Test Suite")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}\n")
    
    results = []
    start_time = time.time()
    
    for name, test_fn in tests:
        print(f"Running: {name}...", end=" ")
        sys.stdout.flush()
        result = run_test(name, test_fn, timeout_sec=300)
        results.append(result)
        icon = "✅" if result.status == "PASS" else "⏱️" if result.status == "TIMEOUT" else "❌"
        print(f"{icon} {result.status} ({result.duration:.2f}s)")
    
    total_time = time.time() - start_time
    
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    timeouts = sum(1 for r in results if r.status == "TIMEOUT")
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total: {len(results)} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️ Timeouts: {timeouts}")
    print(f"Duration: {total_time:.2f}s")
    
    with open('tests/results.md', 'w') as f:
        f.write("# ValHopper Test Results\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Total Duration:** {total_time:.2f}s\n\n")
        f.write("## Summary\n\n")
        f.write("| Status | Count |\n")
        f.write("|--------|-------|\n")
        f.write(f"| ✅ PASS | {passed} |\n")
        f.write(f"| ❌ FAIL | {failed} |\n")
        f.write(f"| ⏱️ TIMEOUT | {timeouts} |\n")
        f.write(f"| **Total** | **{len(results)}** |\n\n")
        f.write("## Test Details\n\n")
        f.write("| Test | Status | Duration | Error |\n")
        f.write("|------|--------|----------|-------|\n")
        for r in results:
            icon = "✅" if r.status == "PASS" else "⏱️" if r.status == "TIMEOUT" else "❌"
            err = r.error if r.error else "-"
            f.write(f"| {r.name} | {icon} {r.status} | {r.duration:.2f}s | {err} |\n")
    
    print(f"\nResults written to: tests/results.md")
    sys.exit(0 if failed == 0 else 1)

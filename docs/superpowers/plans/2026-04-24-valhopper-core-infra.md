# ValHopper Core Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Goal:** Refactor ValHopper's internals for performance, testability, and extensibility; add config file, SQLite yield history, JSON output, and delete dead code.
> **Architecture:** Split the monolithic `valhopper_cli.py` into focused modules. Add a `ValhopperDB` SQLite layer for yield history. Add a `config.py` for YAML config loading. Refactor `BittensorClient` to accept injected subtensor and index delegates by hotkey.
> **Tech Stack:** Python 3.10+, bittensor SDK, click, rich, sqlite3 (stdlib), pyyaml (add to deps)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/valhopper/__init__.py` | Package init, expose version |
| `src/valhopper/config.py` | **NEW** — YAML config file loading, defaults, validation |
| `src/valhopper/models.py` | **NEW** — StakePosition, ReturnResult, ReturnError, risk level constants, formatting helpers (extracted from cli) |
| `src/valhopper/client.py` | **NEW** — BittensorClient class (extracted from cli), with delegate indexing, DI for subtensor |
| `src/valhopper/valhopper_cli.py` | **MODIFIED** — CLI commands only, imports from models/client/transactions/logging |
| `src/valhopper/valhopper_transactions.py` | **MODIFIED** — Add retry/backoff on move_stake failures |
| `src/valhopper/valhopper_logging.py` | **MODIFIED** — Add JSON output formatter |
| `src/valhopper/db.py` | **NEW** — SQLite yield history storage and querying |
| `tests/test_config.py` | **NEW** — Config loading tests |
| `tests/test_models.py` | **NEW** — Models tests (moved from test_return_result, test_optimize) |
| `tests/test_client.py` | **NEW** — Client tests (moved from test_cache) |
| `tests/test_db.py` | **NEW** — DB tests |
| `tests/test_transactions.py` | **NEW** — Transaction retry tests |
| `patch_return.py` | **DELETE** |
| `pyproject.toml` | **MODIFIED** — Add pyyaml dep, bump version |
| `README.md` | **MODIFIED** — Update at end |

---

### Task 1: Delete dead code (`patch_return.py`)

**Files:**
- Delete: `patch_return.py`

- [ ] **Step 1: Delete the file**
  ```bash
  rm patch_return.py
  ```

- [ ] **Step 2: Verify tests still pass**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 3: Commit**
  ```bash
  git add -A && git commit -m "chore: remove obsolete patch_return.py"
  ```

---

### Task 2: Extract models into `models.py`

**Files:**
- Create: `src/valhopper/models.py`
- Modify: `src/valhopper/valhopper_cli.py`

This extracts all data classes, enums, constants, and formatting helpers from `valhopper_cli.py` into a standalone module with zero bittensor imports.

- [ ] **Step 1: Create `src/valhopper/models.py`** with the following content:

```python
"""ValHopper data models, constants, and formatting helpers."""

import enum


SECONDS_PER_BLOCK = 12
BLOCKS_PER_DAY = 86400 // SECONDS_PER_BLOCK  # 7200

RISK_LEVELS = {
    "conservative": {
        "min_trust": 0.95,
        "min_age_days": 90,
        "min_validator_permits": 1,
        "min_nominators": 100,
        "fallback_min_trust": 0.80,
        "fallback_min_age_days": 30,
    },
    "moderate": {
        "min_trust": 0.80,
        "min_age_days": 30,
        "min_validator_permits": 1,
        "min_nominators": 10,
        "fallback_min_trust": 0.50,
        "fallback_min_age_days": 7,
    },
    "aggressive": {
        "min_trust": 0.50,
        "min_age_days": 7,
        "min_validator_permits": 0,
        "min_nominators": 0,
        "fallback_min_trust": 0.0,
        "fallback_min_age_days": 0,
    },
}


class ReturnError(enum.Enum):
    NO_ERROR = "no_error"
    VALIDATOR_NOT_IN_METAGRAPH = "validator_not_in_metagraph"
    NO_STAKE = "no_stake"
    NO_EMISSION = "no_emission"
    NETWORK_ERROR = "network_error"


class ReturnResult:
    """Result of return computation with status."""

    def __init__(self, value: float, error: ReturnError, message: str = ""):
        self.value = value
        self.error = error
        self.message = message

    @property
    def is_error(self) -> bool:
        return self.error != ReturnError.NO_ERROR

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "error": self.error.value,
            "message": self.message,
        }


class StakePosition:
    """Represents a stake position with return-per-1000 calculations."""

    def __init__(
        self,
        hotkey: str,
        netuid: int,
        stake_tao: float,
        current_validator_return: float = 0.0,
        best_validator_return: float = 0.0,
        best_validator_hotkey: str = "",
        best_validator_trust: float = 0.0,
        best_validator_age_days: float = 0.0,
        best_validator_nominators: int = 0,
        best_validator_permits: int = 0,
        best_validator_take: float = 0.0,
        current_validator_trust: float = 0.0,
        current_validator_name: str = "",
        best_validator_name: str = "",
    ):
        self.hotkey = hotkey
        self.netuid = netuid
        self.stake_tao = stake_tao
        self.current_validator_return = current_validator_return
        self.best_validator_return = best_validator_return
        self.best_validator_hotkey = best_validator_hotkey
        self.best_validator_trust = best_validator_trust
        self.best_validator_age_days = best_validator_age_days
        self.best_validator_nominators = best_validator_nominators
        self.best_validator_permits = best_validator_permits
        self.best_validator_take = best_validator_take
        self.current_validator_trust = current_validator_trust
        self.current_validator_name = current_validator_name
        self.best_validator_name = best_validator_name

    @property
    def token_symbol(self) -> str:
        return get_token_symbol(self.netuid)

    @property
    def current_return_per_1000(self) -> float:
        return self.current_validator_return

    @property
    def best_return_per_1000(self) -> float:
        return self.best_validator_return

    @property
    def return_delta(self) -> float:
        return self.best_validator_return - self.current_validator_return

    @property
    def current_daily_earn(self) -> float:
        return (self.stake_tao / 1000) * self.current_validator_return

    @property
    def new_daily_earn(self) -> float:
        return (self.stake_tao / 1000) * self.best_validator_return

    @property
    def potential_additional_daily(self) -> float:
        return self.new_daily_earn - self.current_daily_earn

    def to_dict(self) -> dict:
        return {
            "hotkey": self.hotkey,
            "netuid": self.netuid,
            "stake_tao": self.stake_tao,
            "token_symbol": self.token_symbol,
            "current_return_per_1000": self.current_return_per_1000,
            "best_return_per_1000": self.best_return_per_1000,
            "return_delta": self.return_delta,
            "current_daily_earn": self.current_daily_earn,
            "new_daily_earn": self.new_daily_earn,
            "potential_additional_daily": self.potential_additional_daily,
            "current_validator_trust": self.current_validator_trust,
            "best_validator_hotkey": self.best_validator_hotkey,
            "best_validator_trust": self.best_validator_trust,
            "best_validator_age_days": self.best_validator_age_days,
            "best_validator_nominators": self.best_validator_nominators,
            "best_validator_permits": self.best_validator_permits,
            "best_validator_take": self.best_validator_take,
        }


def get_token_symbol(netuid: int) -> str:
    symbols = {0: "\u03c4", 1: "\u03b1", 2: "\u03b2", 3: "\u03b3", 4: "\u03b4", 5: "\u03b5"}
    return symbols.get(netuid, f"S{netuid}")


def fmt_ret(val: float) -> str:
    if val == 0:
        return "0"
    if val < 0.01:
        return f"{val:.6f}"
    if val < 1:
        return f"{val:.4f}"
    if val < 100:
        return f"{val:.2f}"
    return f"{val:.1f}"


def color_trust(trust: float) -> str:
    s = f"{trust:.4f}"
    if trust >= 0.95:
        return f"[green]{s}[/green]"
    if trust >= 0.80:
        return f"[yellow]{s}[/yellow]"
    if trust > 0:
        return f"[red]{s}[/red]"
    return "-"


def color_age(age_days: float) -> str:
    if age_days <= 0:
        return "-"
    s = f"{age_days:.0f}d"
    if age_days >= 90:
        return f"[green]{s}[/green]"
    if age_days >= 30:
        return f"[yellow]{s}[/yellow]"
    return f"[red]{s}[/red]"
```

Key change: `StakePosition.stake_tao` is now a plain `float` instead of a `bittensor.Balance` object. This eliminates the bittensor dependency from the models layer entirely. The client layer will extract `.tao` when constructing positions.

- [ ] **Step 2: Write tests for models**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they pass**
  Run: `pytest tests/test_models.py -v`
  Expected: All pass

- [ ] **Step 4: Update existing test files to import from models**

Update `tests/test_return_result.py` — replace entire file with:

```python
"""Tests for ReturnResult — now in valhopper.models."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.models import ReturnError, ReturnResult


def test_return_result_success():
    result = ReturnResult(value=1.5, error=ReturnError.NO_ERROR, message="")
    assert result.value == 1.5
    assert result.error == ReturnError.NO_ERROR
    assert not result.is_error


def test_return_result_not_in_metagraph():
    result = ReturnResult(
        value=0.0, error=ReturnError.VALIDATOR_NOT_IN_METAGRAPH, message="Not found"
    )
    assert result.value == 0.0
    assert result.error == ReturnError.VALIDATOR_NOT_IN_METAGRAPH
    assert result.is_error


def test_return_result_network_error():
    result = ReturnResult(
        value=0.0, error=ReturnError.NETWORK_ERROR, message="Connection timeout"
    )
    assert result.is_error


def test_return_result_no_stake():
    result = ReturnResult(value=0.0, error=ReturnError.NO_STAKE, message="Validator has no stake")
    assert result.error == ReturnError.NO_STAKE


def test_return_result_no_emission():
    result = ReturnResult(value=0.0, error=ReturnError.NO_EMISSION, message="No emission")
    assert result.error == ReturnError.NO_EMISSION
```

Update `tests/test_optimize.py` — replace entire file with:

```python
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
```

- [ ] **Step 5: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 6: Commit**
  ```bash
  git add -A && git commit -m "feat: extract models.py with StakePosition, ReturnResult, constants"
  ```

---

### Task 3: Extract BittensorClient into `client.py` with delegate indexing and DI

**Files:**
- Create: `src/valhopper/client.py`
- Modify: `src/valhopper/valhopper_cli.py`

This is the biggest refactor. `BittensorClient` moves to its own module with two key improvements:
1. Accept an optional `subtensor` parameter in `__init__` (dependency injection for tests)
2. Build a `hotkey→delegate` dict from `get_delegates()` to avoid O(N) scans

- [ ] **Step 1: Create `src/valhopper/client.py`**

```python
"""Bittensor blockchain client with caching and risk filtering."""

import time
import logging
from typing import Optional

import bittensor

from .models import (
    StakePosition,
    ReturnResult,
    ReturnError,
    RISK_LEVELS,
    BLOCKS_PER_DAY,
    SECONDS_PER_BLOCK,
)

logger = logging.getLogger("valhopper")


class BittensorClient:
    """Client for interacting with the Bittensor blockchain."""

    def __init__(self, subtensor: Optional[bittensor.Subtensor] = None, network: str = "finney"):
        if subtensor is not None:
            self.subtensor = subtensor
        else:
            self.subtensor = bittensor.Subtensor(network=network)
        self.network = network
        self._delegates_cache = None  # (list, dict, timestamp)
        self._delegates_by_hotkey = {}  # hotkey_ss58 -> delegate
        self._metagraph_cache = {}  # netuid -> (data, timestamp)
        self._current_block = None  # (block, timestamp)
        self._tempo_cache = {}  # netuid -> (tempo, timestamp)
        self.CACHE_TTL = 300  # 5 minutes

    def _cache_is_valid(self, cached) -> bool:
        if cached is None:
            return False
        data, timestamp = cached
        return time.time() - timestamp < self.CACHE_TTL

    def refresh_caches(self):
        self._delegates_cache = None
        self._delegates_by_hotkey = {}
        self._metagraph_cache = {}
        self._current_block = None
        self._tempo_cache = {}

    # -- caching data fetchers -----------------------------------------------

    def get_delegates(self) -> list:
        """Get all delegates, with caching. Also builds the hotkey index."""
        if not self._cache_is_valid(self._delegates_cache):
            delegates = self.subtensor.get_delegates()
            by_hotkey = {d.hotkey_ss58: d for d in delegates}
            self._delegates_cache = (delegates, by_hotkey, time.time())
            self._delegates_by_hotkey = by_hotkey
        return self._delegates_cache[0]

    def _get_delegate_by_hotkey(self, hotkey: str):
        """O(1) delegate lookup by hotkey."""
        self.get_delegates()  # ensure loaded
        return self._delegates_by_hotkey.get(hotkey)

    def _get_take(self, hotkey: str) -> float:
        d = self._get_delegate_by_hotkey(hotkey)
        return d.take if d else 0.18

    def _get_subnet_tempo(self, netuid: int) -> int:
        if netuid not in self._tempo_cache or not self._cache_is_valid(self._tempo_cache[netuid]):
            hp = self.subtensor.get_subnet_hyperparameters(netuid)
            self._tempo_cache[netuid] = (hp.tempo, time.time())
        return self._tempo_cache[netuid][0]

    def get_metagraph(self, netuid: int):
        if netuid not in self._metagraph_cache or not self._cache_is_valid(self._metagraph_cache[netuid]):
            self._metagraph_cache[netuid] = (self.subtensor.metagraph(netuid), time.time())
            time.sleep(0.1)
        return self._metagraph_cache[netuid][0]

    def get_current_block(self) -> int:
        if self._current_block is None or time.time() - self._current_block[1] > 60:
            self._current_block = (self.subtensor.get_current_block(), time.time())
        return self._current_block[0]

    # -- identity -----------------------------------------------------------

    def get_validator_identity(self, hotkey: str) -> str:
        try:
            identity = self.subtensor.get_identity(hotkey_ss58=hotkey)
            if identity and identity.name:
                return f"{identity.name.strip()} ({hotkey[:8]}...)"
        except Exception:
            pass
        return f"{hotkey[:16]}..."

    # -- risk info ----------------------------------------------------------

    def _get_validator_risk_info(self, hotkey: str, netuid: int) -> dict:
        info = {
            "trust": 0.0,
            "age_days": 0.0,
            "validator_permits": 0,
            "nominators": 0,
            "take": 0.0,
            "in_metagraph": False,
        }
        try:
            meta = self.get_metagraph(netuid)
            cur_block = self.get_current_block()
            uid = None
            for i, hk in enumerate(meta.hotkeys):
                if hk == hotkey:
                    uid = i
                    break
            if uid is not None:
                info["in_metagraph"] = True
                if uid < len(meta.Tv):
                    info["trust"] = float(meta.Tv[uid])
                reg_block = (
                    meta.block_at_registration[uid]
                    if uid < len(meta.block_at_registration)
                    else 0
                )
                if reg_block > 0:
                    info["age_days"] = (cur_block - reg_block) * SECONDS_PER_BLOCK / 86400
        except Exception:
            pass

        d = self._get_delegate_by_hotkey(hotkey)
        if d:
            info["validator_permits"] = len(d.validator_permits)
            info["nominators"] = len(d.nominators)
            info["take"] = d.take
        return info

    def _apply_risk_filters(self, delegates: list, netuid: int, risk_level: str = "moderate") -> list:
        config = RISK_LEVELS.get(risk_level, RISK_LEVELS["moderate"])
        candidates = []
        for d in delegates:
            risk = self._get_validator_risk_info(d.hotkey_ss58, netuid)
            if not risk["in_metagraph"]:
                continue
            candidates.append((d, risk))

        primary = []
        for d, risk in candidates:
            if risk["trust"] < config["min_trust"]:
                continue
            if risk["age_days"] < config["min_age_days"]:
                continue
            if risk_level == "moderate":
                if risk["validator_permits"] < 1 and risk["nominators"] < config["min_nominators"]:
                    continue
            else:
                if risk["validator_permits"] < config["min_validator_permits"]:
                    continue
                if risk["nominators"] < config["min_nominators"]:
                    continue
            primary.append((d, risk))

        if primary:
            return primary

        fallback = []
        for d, risk in candidates:
            if risk["trust"] < config["fallback_min_trust"]:
                continue
            if risk["age_days"] < config["fallback_min_age_days"]:
                continue
            fallback.append((d, risk))
        return fallback

    # -- per-subnet return computation -----------------------------------------

    def _compute_return_per_1k(self, hotkey: str, netuid: int) -> float:
        result = self._compute_return_per_1k_with_status(hotkey, netuid)
        logger.debug(
            f"Return {result.value:.6f} for {hotkey[:12]} on subnet {netuid}: {result.error.value}"
        )
        return result.value

    def _compute_return_per_1k_with_status(self, hotkey: str, netuid: int) -> ReturnResult:
        try:
            meta = self.get_metagraph(netuid)
            uid = None
            for i, hk in enumerate(meta.hotkeys):
                if hk == hotkey:
                    uid = i
                    break
            if uid is None:
                return ReturnResult(0.0, ReturnError.VALIDATOR_NOT_IN_METAGRAPH, "Validator not in metagraph")

            take = self._get_take(hotkey)
            tempo = self._get_subnet_tempo(netuid)
            if tempo <= 0:
                logger.warning(f"Invalid tempo {tempo} for subnet {netuid}")
                tempo = 360
            tempos_per_day = BLOCKS_PER_DAY / tempo
            stake = float(meta.S[uid])
            if stake <= 0:
                return ReturnResult(0.0, ReturnError.NO_STAKE, "Validator has no stake")

            if netuid == 0:
                tao_div = meta.tao_dividends_per_hotkey[uid]
                if isinstance(tao_div, tuple):
                    tao_div = tao_div[1]
                tao_div = float(tao_div)
                if tao_div <= 0:
                    emission = float(meta.emission[uid])
                    if emission <= 0:
                        return ReturnResult(0.0, ReturnError.NO_EMISSION, "No root emission")
                    daily_tao = emission * tempos_per_day * (1 - take)
                    return ReturnResult(daily_tao / stake * 1000, ReturnError.NO_ERROR, "")
                daily_tao = tao_div * tempos_per_day * (1 - take)
                return ReturnResult(daily_tao / stake * 1000, ReturnError.NO_ERROR, "")
            else:
                alpha_div = meta.alpha_dividends_per_hotkey[uid]
                tao_div = meta.tao_dividends_per_hotkey[uid]
                if isinstance(alpha_div, tuple):
                    alpha_div = alpha_div[1]
                if isinstance(tao_div, tuple):
                    tao_div = tao_div[1]
                alpha_div = float(alpha_div)
                tao_div = float(tao_div)

                price = meta.pool.moving_price
                total_alpha = alpha_div
                if price > 0:
                    total_alpha += tao_div / price

                if total_alpha <= 0:
                    return ReturnResult(0.0, ReturnError.NO_EMISSION, "No alpha subnet emission")

                daily_alpha = total_alpha * tempos_per_day * (1 - take)
                return ReturnResult(daily_alpha / stake * 1000, ReturnError.NO_ERROR, "")
        except Exception as e:
            logger.warning(f"Network error for {hotkey[:12]}... on subnet {netuid}: {e}")
            return ReturnResult(0.0, ReturnError.NETWORK_ERROR, str(e))

    # -- best validator -----------------------------------------------------

    def get_best_validator_for_subnet(self, netuid: int, risk_level: str = "moderate") -> Optional[dict]:
        delegates = self.get_delegates()
        subnet_delegates = [d for d in delegates if netuid in d.registrations]
        if not subnet_delegates:
            return None

        filtered = self._apply_risk_filters(subnet_delegates, netuid, risk_level)
        if not filtered:
            return None

        scored = []
        for d, risk in filtered:
            ret = self._compute_return_per_1k(d.hotkey_ss58, netuid)
            if ret > 0:
                scored.append((d, risk, ret))

        if not scored:
            return None

        scored.sort(key=lambda x: x[2], reverse=True)
        best, risk, ret = scored[0]
        return {
            "hotkey": best.hotkey_ss58,
            "return_per_1000": ret,
            "take": best.take,
            "trust": risk["trust"],
            "age_days": risk["age_days"],
            "nominators": risk["nominators"],
            "validator_permits": risk["validator_permits"],
        }

    # -- validator return ---------------------------------------------------

    def get_validator_return(self, hotkey: str, netuid: int) -> float:
        return self._compute_return_per_1k(hotkey, netuid)

    # -- stakes -------------------------------------------------------------

    def get_stakes(self, coldkey_ss58: str, risk_level: str = "moderate") -> list[StakePosition]:
        try:
            stake_infos = self.subtensor.get_stake_info_for_coldkey(coldkey_ss58)
        except Exception as e:
            logger.error(f"Error fetching stakes: {e}")
            return []

        positions = []
        for si in stake_infos:
            if si.stake.tao > 0:
                current_return = self.get_validator_return(si.hotkey_ss58, si.netuid)
                best_validator = self.get_best_validator_for_subnet(si.netuid, risk_level)
                current_risk = self._get_validator_risk_info(si.hotkey_ss58, si.netuid)
                position = StakePosition(
                    hotkey=si.hotkey_ss58,
                    netuid=si.netuid,
                    stake_tao=si.stake.tao,
                    current_validator_return=current_return,
                    best_validator_return=best_validator["return_per_1000"] if best_validator else 0,
                    best_validator_hotkey=best_validator["hotkey"] if best_validator else "",
                    best_validator_trust=best_validator.get("trust", 0.0) if best_validator else 0.0,
                    best_validator_age_days=best_validator.get("age_days", 0.0) if best_validator else 0.0,
                    best_validator_nominators=best_validator.get("nominators", 0) if best_validator else 0,
                    best_validator_permits=best_validator.get("validator_permits", 0) if best_validator else 0,
                    best_validator_take=best_validator.get("take", 0.0) if best_validator else 0.0,
                    current_validator_trust=current_risk["trust"],
                )
                positions.append(position)
        return positions
```

- [ ] **Step 2: Write client tests**

Create `tests/test_client.py`:

```python
"""Tests for BittensorClient — delegate indexing and cache."""
import time
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.client import BittensorClient


def _make_mock_delegate(hotkey="hk1", take=0.18, registrations=None, validator_permits=None, nominators=None):
    d = MagicMock()
    d.hotkey_ss58 = hotkey
    d.take = take
    d.registrations = registrations or [1]
    d.validator_permits = validator_permits or [1]
    d.nominators = nominators or ["nom1"]
    return d


def test_cache_is_valid_with_none():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    assert not client._cache_is_valid(None)


def test_cache_is_valid_with_fresh_data():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    fresh = ("data", time.time())
    assert client._cache_is_valid(fresh)


def test_cache_is_valid_with_stale_data():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    stale = ("data", time.time() - 400)
    assert not client._cache_is_valid(stale)


def test_refresh_caches_clears_all():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    client._delegates_cache = ([], {}, time.time())
    client._delegates_by_hotkey = {"hk1": MagicMock()}
    client._metagraph_cache = {1: ({}, time.time())}
    client._current_block = (1000, time.time())
    client._tempo_cache = {1: (360, time.time())}

    client.refresh_caches()

    assert client._delegates_cache is None
    assert client._delegates_by_hotkey == {}
    assert client._metagraph_cache == {}
    assert client._current_block is None
    assert client._tempo_cache == {}


def test_delegate_indexing():
    mock_sub = MagicMock()
    d1 = _make_mock_delegate(hotkey="hk_alpha")
    d2 = _make_mock_delegate(hotkey="hk_beta")
    mock_sub.get_delegates.return_value = [d1, d2]

    client = BittensorClient(subtensor=mock_sub)
    delegates = client.get_delegates()

    assert len(delegates) == 2
    assert client._get_delegate_by_hotkey("hk_alpha") is d1
    assert client._get_delegate_by_hotkey("hk_beta") is d2
    assert client._get_delegate_by_hotkey("nonexistent") is None


def test_get_take_from_index():
    mock_sub = MagicMock()
    d1 = _make_mock_delegate(hotkey="hk1", take=0.10)
    mock_sub.get_delegates.return_value = [d1]

    client = BittensorClient(subtensor=mock_sub)
    assert client._get_take("hk1") == 0.10
    assert client._get_take("unknown") == 0.18  # default


def test_di_subtensor():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    assert client.subtensor is mock_sub
```

- [ ] **Step 3: Run client tests**
  Run: `pytest tests/test_client.py -v`
  Expected: All pass

- [ ] **Step 4: Update `valhopper_cli.py` to import from models and client**

Replace the top of `valhopper_cli.py` (lines 1-175 approximately — everything before the CLI group definition) with imports from the new modules. The file should be reduced to CLI commands only.

In `valhopper_cli.py`, remove:
- `ReturnError`, `ReturnResult` classes
- `RISK_LEVELS`, `SECONDS_PER_BLOCK`, `BLOCKS_PER_DAY` constants
- `get_token_symbol`, `fmt_ret`, `_color_trust`, `_color_age` functions
- `StakePosition` class
- `BittensorClient` class

Replace with:
```python
#!/usr/bin/env python3
"""ValHopper - Bittensor Alpha Token Stake Optimizer

A CLI tool to help Alpha token holders maximize their yields by
moving stakes to the most profitable validators.
"""

import os
import json as json_lib
import logging

os.environ["BT_NO_PARSE_CLI_ARGS"] = "1"

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import (
    StakePosition,
    ReturnResult,
    fmt_ret,
    get_token_symbol,
    color_trust,
    color_age,
)
from .client import BittensorClient
from .valhopper_transactions import load_wallet, execute_stake_move, format_transaction_results
from .valhopper_logging import write_transaction_log

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("valhopper")

console = Console()
```

Then update all references in the CLI commands:
- `p.stake.tao` → `p.stake_tao` (since StakePosition now stores plain float)
- `_color_trust` → `color_trust`
- `_color_age` → `color_age`
- `BittensorClient(network=...)` stays the same (the old constructor still works)

- [ ] **Step 5: Delete old test_cache.py (replaced by test_client.py)**
  ```bash
  rm tests/test_cache.py
  ```

- [ ] **Step 6: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 7: Commit**
  ```bash
  git add -A && git commit -m "feat: extract client.py with delegate indexing and DI"
  ```

---

### Task 4: Add config file support (`config.py`)

**Files:**
- Create: `src/valhopper/config.py`
- Create: `tests/test_config.py`
- Modify: `pyproject.toml` — add `pyyaml` dependency

- [ ] **Step 1: Add pyyaml to pyproject.toml**

In `pyproject.toml`, update the `dependencies` list to include `"pyyaml>=6.0"`.

- [ ] **Step 2: Create `src/valhopper/config.py`**

```python
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
```

- [ ] **Step 3: Write config tests**

Create `tests/test_config.py`:

```python
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
```

- [ ] **Step 4: Run config tests**
  Run: `pytest tests/test_config.py -v`
  Expected: All pass

- [ ] **Step 5: Integrate config into CLI**

In `valhopper_cli.py`, update the `cli` group to load config and merge with CLI args:

```python
from .config import load_config

@click.group()
@click.option('--network', default=None, help='Bittensor network')
@click.option('--coldkey', default=None, help='Coldkey SS58 address')
@click.option('--wallet-name', default=None, help='Wallet name for transactions')
@click.option('--wallet-hotkey', default=None, help='Hotkey name in wallet')
@click.option('--wallet-path', default=None, help='Wallet path')
@click.option('--risk-level',
              type=click.Choice(['conservative', 'moderate', 'aggressive']),
              default=None,
              help='Risk level for validator selection')
@click.option('--config', 'config_path', default=None, help='Path to config YAML file')
@click.option('--format', 'output_format',
              type=click.Choice(['table', 'json']),
              default=None,
              help='Output format')
@click.pass_context
def cli(ctx, network, coldkey, wallet_name, wallet_hotkey, wallet_path, risk_level, config_path, output_format):
    """ValHopper - Optimize your Bittensor Alpha token stakes."""
    ctx.ensure_object(dict)
    cfg = load_config(config_path)
    # CLI args override config file values
    ctx.obj['network'] = network or cfg['network']
    ctx.obj['coldkey'] = coldkey or cfg.get('coldkey')
    ctx.obj['wallet_name'] = wallet_name or cfg.get('wallet_name')
    ctx.obj['wallet_hotkey'] = wallet_hotkey or cfg['wallet_hotkey']
    ctx.obj['wallet_path'] = wallet_path or cfg['wallet_path']
    ctx.obj['risk_level'] = risk_level or cfg['risk_level']
    ctx.obj['output_format'] = output_format or cfg.get('format', 'table')
    ctx.obj['discord_webhook_url'] = cfg.get('discord_webhook_url')
    ctx.obj['min_improvement'] = cfg.get('min_improvement', 0.0)
```

- [ ] **Step 6: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 7: Commit**
  ```bash
  git add -A && git commit -m "feat: add config.py with YAML config file support"
  ```

---

### Task 5: Add JSON output formatter

**Files:**
- Modify: `src/valhopper/valhopper_logging.py`
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add JSON output helper to `valhopper_logging.py`**

Append to `valhopper_logging.py`:

```python
def format_json_output(command: str, data: dict) -> str:
    """Format command output as JSON string.

    Args:
        command: The CLI command name (e.g. 'list-stakes', 'optimize')
        data: Dict of output data

    Returns:
        JSON string
    """
    import json as json_lib

    output = {"command": command, **data}
    return json_lib.dumps(output, indent=2, default=str)
```

- [ ] **Step 2: Add `--format json` support to each CLI command in `valhopper_cli.py`**

In each command (`list_stakes`, `optimize`, `top_validators`), before rendering the Rich table, check `ctx.obj.get('output_format')`:

For `list_stakes`, after computing `positions`:
```python
if ctx.obj.get('output_format') == 'json':
    from .valhopper_logging import format_json_output
    data = {
        "coldkey": coldkey,
        "risk_level": risk_level,
        "positions": [p.to_dict() for p in positions],
    }
    console.print(format_json_output("list-stakes", data))
    return
```

For `optimize` (dry-run path), after computing `movable_positions`:
```python
if ctx.obj.get('output_format') == 'json':
    from .valhopper_logging import format_json_output
    data = {
        "coldkey": coldkey,
        "risk_level": effective_risk,
        "dry_run": dry_run,
        "positions_to_move": [p.to_dict() for p in movable_positions],
        "total_stake_to_move": total_stake_to_move,
        "total_daily_gain": total_daily_gain,
    }
    console.print(format_json_output("optimize", data))
    if dry_run:
        return
    # If not dry_run, continue to live execution (JSON output for results added later)
```

For `top_validators`, after computing `scored`:
```python
if ctx.obj.get('output_format') == 'json':
    from .valhopper_logging import format_json_output
    data = {
        "netuid": netuid,
        "risk_level": effective_risk,
        "validators": [
            {
                "rank": i,
                "hotkey": d.hotkey_ss58,
                "return_per_1000": ret,
                "trust": risk["trust"],
                "age_days": risk["age_days"],
                "nominators": risk["nominators"],
                "take": d.take,
            }
            for i, (d, risk, ret) in enumerate(scored[:20], 1)
        ],
    }
    console.print(format_json_output("top-validators", data))
    return
```

- [ ] **Step 3: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add JSON output format (--format json)"
  ```

---

### Task 6: Add SQLite yield history database (`db.py`)

**Files:**
- Create: `src/valhopper/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Create `src/valhopper/db.py`**

```python
"""SQLite yield history storage for ValHopper.

Stores daily snapshots of validator return_per_1000 per subnet
so users can track yield trends over time.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional

DB_DIR = Path.home() / ".valhopper"
DB_PATH = DB_DIR / "history.db"


def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS yield_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            hotkey TEXT NOT NULL,
            return_per_1000 REAL NOT NULL,
            trust REAL NOT NULL DEFAULT 0.0,
            stake REAL NOT NULL DEFAULT 0.0,
            nominators INTEGER NOT NULL DEFAULT 0,
            take REAL NOT NULL DEFAULT 0.0,
            UNIQUE(snapshot_date, netuid, hotkey)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_netuid
            ON yield_snapshots(netuid, snapshot_date DESC);

        CREATE INDEX IF NOT EXISTS idx_snapshots_hotkey
            ON yield_snapshots(hotkey, snapshot_date DESC);

        CREATE TABLE IF NOT EXISTS position_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            coldkey TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            hotkey TEXT NOT NULL,
            stake_tao REAL NOT NULL,
            return_per_1000 REAL NOT NULL,
            daily_earn REAL NOT NULL,
            UNIQUE(snapshot_date, coldkey, netuid, hotkey)
        );

        CREATE INDEX IF NOT EXISTS idx_positions_coldkey
            ON position_snapshots(coldkey, snapshot_date DESC);
    """)
    conn.commit()


def record_validator_snapshot(
    conn: sqlite3.Connection,
    snapshot_date: str,
    netuid: int,
    hotkey: str,
    return_per_1000: float,
    trust: float = 0.0,
    stake: float = 0.0,
    nominators: int = 0,
    take: float = 0.0,
):
    """Insert or replace a validator yield snapshot for a given date."""
    conn.execute(
        """INSERT OR REPLACE INTO yield_snapshots
           (snapshot_date, netuid, hotkey, return_per_1000, trust, stake, nominators, take)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_date, netuid, hotkey, return_per_1000, trust, stake, nominators, take),
    )
    conn.commit()


def record_position_snapshot(
    conn: sqlite3.Connection,
    snapshot_date: str,
    coldkey: str,
    netuid: int,
    hotkey: str,
    stake_tao: float,
    return_per_1000: float,
    daily_earn: float,
):
    """Insert or replace a position snapshot for a given date."""
    conn.execute(
        """INSERT OR REPLACE INTO position_snapshots
           (snapshot_date, coldkey, netuid, hotkey, stake_tao, return_per_1000, daily_earn)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_date, coldkey, netuid, hotkey, stake_tao, return_per_1000, daily_earn),
    )
    conn.commit()


def get_validator_history(
    conn: sqlite3.Connection,
    netuid: int,
    hotkey: str,
    days: int = 30,
) -> list[dict]:
    """Get yield history for a specific validator on a subnet."""
    rows = conn.execute(
        """SELECT snapshot_date, return_per_1000, trust, stake, nominators, take
           FROM yield_snapshots
           WHERE netuid = ? AND hotkey = ?
           ORDER BY snapshot_date DESC
           LIMIT ?""",
        (netuid, hotkey, days),
    ).fetchall()
    return [dict(r) for r in rows]


def get_subnet_history(
    conn: sqlite3.Connection,
    netuid: int,
    days: int = 30,
) -> list[dict]:
    """Get yield history for all validators on a subnet (latest snapshot per validator)."""
    rows = conn.execute(
        """SELECT y.hotkey, y.snapshot_date, y.return_per_1000, y.trust, y.stake, y.nominators, y.take
           FROM yield_snapshots y
           INNER JOIN (
               SELECT hotkey, MAX(snapshot_date) as max_date
               FROM yield_snapshots
               WHERE netuid = ?
               GROUP BY hotkey
           ) latest ON y.hotkey = latest.hotkey AND y.snapshot_date = latest.max_date
           WHERE y.netuid = ?
           ORDER BY y.return_per_1000 DESC""",
        (netuid, netuid),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position_history(
    conn: sqlite3.Connection,
    coldkey: str,
    days: int = 30,
) -> list[dict]:
    """Get position history for a coldkey."""
    rows = conn.execute(
        """SELECT snapshot_date, netuid, hotkey, stake_tao, return_per_1000, daily_earn
           FROM position_snapshots
           WHERE coldkey = ?
           ORDER BY snapshot_date DESC
           LIMIT ?""",
        (coldkey, days),
    ).fetchall()
    return [dict(r) for r in rows]


def detect_declining_validators(
    conn: sqlite3.Connection,
    netuid: int,
    min_days: int = 7,
    decline_threshold: float = 0.5,
) -> list[dict]:
    """Find validators whose yield has declined by more than decline_threshold over min_days.

    Returns list of dicts with hotkey, old_return, new_return, decline_pct.
    """
    rows = conn.execute(
        """WITH recent AS (
               SELECT hotkey, return_per_1000 as recent_ret,
                      ROW_NUMBER() OVER (PARTITION BY hotkey ORDER BY snapshot_date DESC) as rn
               FROM yield_snapshots WHERE netuid = ?
           ),
           older AS (
               SELECT hotkey, return_per_1000 as older_ret,
                      ROW_NUMBER() OVER (PARTITION BY hotkey ORDER BY snapshot_date DESC) as rn
               FROM yield_snapshots WHERE netuid = ?
           )
           SELECT r.hotkey, o.older_ret as old_return, r.recent_ret as new_return,
                  CASE WHEN o.older_ret > 0 THEN (o.older_ret - r.recent_ret) / o.older_ret
                       ELSE 0 END as decline_pct
           FROM recent r
           JOIN older o ON r.hotkey = o.hotkey
           WHERE r.rn = 1 AND o.rn = ?
             AND o.older_ret > 0
             AND (o.older_ret - r.recent_ret) / o.older_ret > ?""",
        (netuid, netuid, min_days, decline_threshold),
    ).fetchall()
    return [dict(r) for r in rows]


def snapshot_today(
    client,
    conn: sqlite3.Connection,
    coldkey: Optional[str] = None,
):
    """Record a full snapshot of validator yields (and optionally positions) for today.

    This is the main entry point for the `vh snapshot` command.
    """
    today = date.today().isoformat()
    delegates = client.get_delegates()
    current_block = client.get_current_block()

    for d in delegates:
        for netuid in d.registrations:
            ret = client._compute_return_per_1k_with_status(d.hotkey_ss58, netuid)
            if ret.is_error:
                continue
            risk = client._get_validator_risk_info(d.hotkey_ss58, netuid)
            record_validator_snapshot(
                conn,
                today,
                netuid,
                d.hotkey_ss58,
                ret.value,
                trust=risk["trust"],
                stake=0.0,  # filled from metagraph if needed
                nominators=risk["nominators"],
                take=d.take,
            )

    if coldkey:
        positions = client.get_stakes(coldkey)
        for p in positions:
            record_position_snapshot(
                conn,
                today,
                coldkey,
                p.netuid,
                p.hotkey,
                p.stake_tao,
                p.current_return_per_1000,
                p.current_daily_earn,
            )

    conn.commit()
```

- [ ] **Step 2: Write DB tests**

Create `tests/test_db.py`:

```python
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
    record_validator_snapshot(conn, "2026-04-20", 1, "hk1", 110.0)  # same date+netuid+hotkey
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
    # Should be sorted by return_per_1000 DESC
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
    # Validator declining from 100 to 50 (50% decline)
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
```

- [ ] **Step 3: Run DB tests**
  Run: `pytest tests/test_db.py -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add db.py with SQLite yield history tracking"
  ```

---

### Task 7: Add retry/backoff to `execute_stake_move`

**Files:**
- Modify: `src/valhopper/valhopper_transactions.py`
- Create: `tests/test_transactions.py`

- [ ] **Step 1: Update `execute_stake_move` with retry logic**

In `valhopper_transactions.py`, add a retry wrapper:

```python
import time

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds


def execute_stake_move(subtensor, wallet, position, max_retries: int = MAX_RETRIES):
    """Execute a single stake move transaction with retry logic.

    Args:
        subtensor: Bittensor subtensor instance
        wallet: Wallet instance
        position: StakePosition to move
        max_retries: Maximum number of retry attempts for transient errors

    Returns:
        (success: bool, message: str, details: dict) tuple
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            response = subtensor.move_stake(
                wallet=wallet,
                origin_netuid=position.netuid,
                origin_hotkey_ss58=position.hotkey,
                destination_netuid=position.netuid,
                destination_hotkey_ss58=position.best_validator_hotkey,
                move_all_stake=True,
                wait_for_inclusion=True,
                wait_for_finalization=True,
            )

            if response.success:
                details = {}
                if hasattr(response, "transaction_tao_fee") and response.transaction_tao_fee:
                    details["tao_fee"] = response.transaction_tao_fee
                if hasattr(response, "transaction_alpha_fee") and response.transaction_alpha_fee:
                    details["alpha_fee"] = response.transaction_alpha_fee
                if hasattr(response, "data") and response.data:
                    details.update(response.data)
                parts = []
                if hasattr(response, "extrinsic_receipt") and response.extrinsic_receipt:
                    receipt = response.extrinsic_receipt
                    if hasattr(receipt, "block_hash"):
                        parts.append(f"block: {str(receipt.block_hash)[:16]}...")
                    if hasattr(receipt, "block_number"):
                        parts.append(f"height: {receipt.block_number}")
                msg = "Success"
                if parts:
                    msg += f" ({', '.join(parts)})"
                if details.get("tao_fee"):
                    msg += f" fee: {details['tao_fee']}"
                return True, msg, details
            else:
                error_parts = []
                if response.message:
                    error_parts.append(str(response.message))
                if response.error:
                    error_parts.append(str(response.error))
                error_msg = " | ".join(error_parts) if error_parts else "Transaction failed (no details returned by SDK)"
                if _is_retryable(error_msg) and attempt < max_retries:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    time.sleep(delay)
                    continue
                return False, error_msg, {}

        except Exception as e:
            last_exception = e
            if _is_retryable(str(e)) and attempt < max_retries:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                time.sleep(delay)
                continue
            return False, f"Exception: {type(e).__name__}: {e}", {}

    return False, f"Failed after {max_retries} retries. Last: {last_exception}", {}


def _is_retryable(error_msg: str) -> bool:
    """Check if an error is likely transient and worth retrying."""
    retryable_patterns = [
        "rate limit",
        "timeout",
        "connection",
        "network",
        "busy",
        "temporarily",
        "503",
        "429",
        "Too many",
        "pool",
    ]
    lower = error_msg.lower()
    return any(p in lower for p in retryable_patterns)
```

- [ ] **Step 2: Write transaction tests**

Create `tests/test_transactions.py`:

```python
"""Tests for valhopper_transactions retry logic."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.valhopper_transactions import _is_retryable


def test_is_retryable_rate_limit():
    assert _is_retryable("Rate limit exceeded")


def test_is_retryable_timeout():
    assert _is_retryable("Connection timeout")


def test_is_retryable_network():
    assert _is_retryable("Network error")


def test_is_retryable_429():
    assert _is_retryable("HTTP 429 Too Many Requests")


def test_is_retryable_503():
    assert _is_retryable("503 Service Unavailable")


def test_not_retryable_insufficient_balance():
    assert not _is_retryable("Insufficient balance")


def test_not_retryable_coldkey_mismatch():
    assert not _is_retryable("Coldkey mismatch")


def test_not_retryable_empty():
    assert not _is_retryable("")


def test_retryable_case_insensitive():
    assert _is_retryable("RATE LIMIT exceeded")
```

- [ ] **Step 3: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add retry/backoff to execute_stake_move"
  ```

---

### Task 8: Move `BT_NO_PARSE_CLI_ARGS` guard to entry point

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

The `os.environ['BT_NO_PARSE_CLI_ARGS'] = '1'` at module level is a side effect that runs on import. Move it into the `cli()` function.

- [ ] **Step 1: Move the env var set into the CLI function**

Remove `os.environ['BT_NO_PARSE_CLI_ARGS'] = '1'` from the module top-level in `valhopper_cli.py`.

Add it as the first line inside the `cli()` function body, before `ctx.ensure_object(dict)`:

```python
def cli(ctx, network, coldkey, wallet_name, wallet_hotkey, wallet_path, risk_level, config_path, output_format):
    """ValHopper - Optimize your Bittensor Alpha token stakes."""
    os.environ['BT_NO_PARSE_CLI_ARGS'] = '1'
    ctx.ensure_object(dict)
    # ... rest unchanged
```

- [ ] **Step 2: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 3: Commit**
  ```bash
  git add -A && git commit -m "fix: move BT_NO_PARSE_CLI_ARGS env guard into CLI entry point"
  ```

---

### Task 9: Add fee estimation before execution

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`
- Modify: `src/valhopper/valhopper_transactions.py`

- [ ] **Step 1: Add `estimate_stake_move_fee` function to `valhopper_transactions.py`**

```python
def estimate_stake_move_fee(subtensor, position) -> dict:
    """Estimate transaction fees for a stake move without executing it.

    Uses a dry-run / fee estimation approach. Falls back to a
    hardcoded estimate if the SDK doesn't expose fee estimation.

    Args:
        subtensor: Bittensor subtensor instance
        position: StakePosition to estimate fees for

    Returns:
        dict with 'estimated_tao_fee' key
    """
    try:
        if hasattr(subtensor, "get_transfer_fee"):
            fee = subtensor.get_transfer_fee()
            return {"estimated_tao_fee": float(fee)}
    except Exception:
        pass
    # Conservative default: 0.001 TAO per move_stake
    return {"estimated_tao_fee": 0.001}
```

- [ ] **Step 2: Show fee estimates in the optimize command before confirmation**

In `valhopper_cli.py`, in the `optimize` command, after the "Planned Stake Moves" table and before the confirmation prompt, add:

```python
from .valhopper_transactions import estimate_stake_move_fee

# Show estimated fees
total_estimated_fee = 0.0
fee_estimates = []
for pos in validated_positions:
    est = estimate_stake_move_fee(client.subtensor, pos)
    fee_estimates.append(est)
    total_estimated_fee += est.get("estimated_tao_fee", 0.001)

console.print(f"\n[bold]Estimated transaction fees:[/bold] ~{total_estimated_fee:.6f} TAO for {len(validated_positions)} move(s)")
console.print("[dim]Actual fees may vary slightly[/dim]")
```

- [ ] **Step 3: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: show fee estimates before optimize execution"
  ```

---

### Task 10: Bump version and clean up

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md` — add config file docs, JSON output docs, yield history docs

- [ ] **Step 1: Bump version in pyproject.toml**

Change `version = "0.1.0"` to `version = "0.2.0"`.

- [ ] **Step 2: Update README.md**

Add sections for:
- **Configuration**: Document `~/.valhopper/config.yaml` and the `--config` flag. Show a sample config.
- **JSON Output**: Document `--format json` flag with example output.
- **Yield History**: Document `vh snapshot` and `vh history` commands (to be implemented in Plan B, but mention the DB exists).
- **Fee Estimation**: Note that optimize now shows fee estimates before confirmation.
- **Retry Logic**: Note that transient transaction failures are retried up to 3 times.

- [ ] **Step 3: Run full test suite**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "chore: bump version to 0.2.0, update README"
  ```

---

## Scheduling Guidance (not code changes)

For **automated/scheduled rebalancing**, do NOT create systemd services or cron jobs. Instead:

1. **Use a simple wrapper script** the user can run from their own scheduler:
   ```bash
   #!/bin/bash
   # save as: rebalance.sh
   # Usage: ./rebalance.sh   (or schedule with your preferred tool)
   valhopper --coldkey YOUR_KEY optimize --dry-run --min-improvement 20 --format json > /tmp/vh_last_run.json
   # If you want auto-execution, remove --dry-run and add --wallet-name
   ```

2. **Recommend the user set up their own scheduling** using whatever they prefer:
   - `crontab -e` if they want cron
   - A systemd timer if they use systemd
   - A `launchd` plist on macOS
   - A simple `while true; do ./rebalance.sh; sleep 86400; done` loop in tmux

3. **Document this** in the README with a "Automated Rebalancing" section showing the wrapper script pattern and the scheduling options above.

This gives the user full control without ValHopper owning a daemon process.

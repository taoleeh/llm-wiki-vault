# ValHopper

**Bittensor Alpha Token Stake Optimizer**

A CLI tool that helps Alpha token holders maximize their yields by moving stakes to the most profitable validators in one command.

## Overview

When you stake TAO into a subnet (buying Alpha tokens), you choose a validator to stake with. But not all validators are equally profitable - their yields (return_per_1000) can vary significantly. ValHopper helps you:

1. **View your current stakes** - See all your delegations across subnets
2. **Identify yield gaps** - Compare your current validator's yield vs the best available
3. **Optimize in one command** - Move all stakes to the highest-yielding validators

## Installation

```bash
# Clone the repository
git clone https://github.com/wiggly/valhopper
cd valhopper

# Install dependencies
pip install -e .
```

This installs two CLI entry points: `valhopper` and `vh` (alias).

## Quick Start

```bash
# List all stakes for a coldkey
./valhopper --coldkey YOUR_COLDKEY_SS58 list-stakes

# See top validators for a subnet
./valhopper top-validators 1

# Preview stake optimization (dry-run)
./valhopper --coldkey YOUR_COLDKEY_SS58 optimize --dry-run

# Execute optimization (requires wallet)
./valhopper --wallet-name mywallet optimize
```

## Commands

### `list-stakes`

Show all stakes for a given wallet/coldkey, including:
- Current stake amount per subnet/validator
- Current yield (return_per_1000 TAO)
- Best available yield on that subnet
- Potential daily/monthly gains from optimizing

```bash
./valhopper --coldkey 5ABC123... list-stakes
```

### `optimize`

Move all stakes to the most profitable validators. For each subnet you're staked in:
1. Find the validator with highest return_per_1000
2. Move your stake to that validator

```bash
# Dry run - preview changes without executing
./valhopper --coldkey YOUR_COLDKEY optimize --dry-run

# Execute (requires unlocked wallet)
./valhopper --wallet-name mywallet optimize
```

### `top-validators NETUID`

Show the top validators for a specific subnet, ranked by return_per_1000.

```bash
./valhopper top-validators 1
./valhopper top-validators 34
```

### `subnets`

List all available subnets with their prices and names.

```bash
./valhopper subnets
```

## Risk Levels

ValHopper filters validators using on-chain trust and stability signals before selecting the best yield. Three risk levels are available (see [USER_GUIDE.md](USER_GUIDE.md) for full details):

| Level | Trust | Age | Use Case |
|-------|-------|-----|----------|
| `conservative` | >= 0.95 | >= 90 days | Large stakes, infrequent checks |
| `moderate` (default) | >= 0.80 | >= 30 days | Most users |
| `aggressive` | >= 0.50 | >= 7 days | Small stakes, daily monitoring |

```bash
# Use conservative filtering
./valhopper --coldkey <SS58> --risk-level conservative optimize --dry-run
```

## Understanding return_per_1000

The `return_per_1000` metric represents the daily yield per 1000 tokens staked with a validator. For example:

- return_per_1000 = 50 means ~5% daily yield
- return_per_1000 = 208 means ~20.8% daily yield

Yields vary dramatically between validators and subnets. A stake earning 0/day could potentially earn 200+/day by moving to the best validator.

**How it's computed**: ValHopper calculates per-subnet returns from on-chain metagraph dividend data (`tao_dividends_per_hotkey` for root, `alpha_dividends_per_hotkey` + `tao_dividends_per_hotkey` for alpha subnets), not from the broken aggregate `get_delegates().return_per_1000` which mixes alpha/tao units across subnets.

## How It Works

1. **Fetch delegates** - Query all registered validators and their metadata
2. **Analyze stakes** - Get your stake positions via `get_stake_info_for_coldkey`
3. **Apply risk filters** - Filter validators by trust, age, permits, and nominator count
4. **Compare yields** - For each position, find the best validator on that subnet
5. **Move stakes** - Use `move_stake` to transfer to the best validator (same subnet, different hotkey)

## Configuration

ValHopper supports a YAML config file at `~/.valhopper/config.yaml`. Generate a default:

```bash
# Create default config
python -c "from valhopper.config import write_default_config; print(write_default_config())"
```

Sample config:

```yaml
# ~/.valhopper/config.yaml
coldkey: null
wallet_name: null
wallet_hotkey: default
wallet_path: ~/.bittensor/wallets
network: finney
risk_level: moderate
min_improvement: 0.0
format: table
discord_webhook_url: null
```

## JSON Output

All commands support `--format json` for machine-readable output:

```bash
vh --coldkey YOUR_KEY --format json list-stakes
vh --coldkey YOUR_KEY --format json optimize --dry-run
vh --format json top-validators 1
```

JSON output includes a `command` field and structured data, suitable for piping to `jq` or scripts.

## Yield History

ValHopper stores daily yield snapshots in a local SQLite database at `~/.valhopper/history.db`. This enables tracking validator yield trends over time. (CLI commands for snapshotting and querying history coming in a future release.)

## Fee Estimation

The `optimize` command now displays estimated transaction fees before execution, so you can evaluate cost vs. benefit before confirming moves.

## Retry Logic

Transient transaction failures (rate limits, timeouts, network errors) are automatically retried up to 3 times with increasing delays (2s, 5s, 10s). Non-retryable errors (insufficient balance, permission denied) fail immediately.

## Automated Rebalancing

For scheduled rebalancing, use a simple wrapper script:

```bash
#!/bin/bash
# rebalance.sh
valhopper --coldkey YOUR_KEY optimize --dry-run --format json > /tmp/vh_last_run.json
# Remove --dry-run and add --wallet-name for auto-execution
```

Schedule with your preferred tool (`cron`, systemd timer, `launchd`, or a tmux loop).

## Security Notes

- **Never share your coldkey private key** - The CLI only needs the SS58 address for read operations
- **Wallet required for writes** - Actual stake moves require an unlocked wallet
- **Coldkey mismatch protection** - ValHopper verifies the wallet coldkey matches `--coldkey` before executing moves
- **Review before confirming** - Always review the planned moves before executing
- **Dry-run available** - Use `--dry-run` to preview moves without executing

## Example Output

### list-stakes

```
Stakes for 5EnY2zjcVse2riNN...
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Subnet ┃ Stake(TAO)┃ Current ┃ Best ┃ Potential┃ Best ┃
┃ ┃ ┃ Yield ┃ Yield ┃ Daily ┃ Validator ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ 34 │ 0.1000 │ 0.00 │ 208.89 │ +0.0209 │ 5G9hfkx...│
│ 1 │ 5.2341 │ 7.14 │ 48861157 │ +256.2 │ 5D1saV... │
└────────┴───────────┴───────────┴───────────┴──────────┴───────────┘
```

### top-validators

```
Top Validators on Subnet 34
┏━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Rank ┃ Hotkey ┃ Return/1000 ┃ Daily Yield % ┃ Take ┃
┡━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ 1 │ 5G9hfkx9wGB1… │ 208.78 │ 20.8782% │ 0.00% │
│ 2 │ 5HbScNssaEfi… │ 34.79 │ 3.4788% │ 9.00% │
│ 3 │ 5E2LP6EnZ54m… │ 33.86 │ 3.3862% │ 0.00% │
└──────┴───────────────┴────────────────┴───────────────┴────────┘
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
```

## Changelog

### v0.2.0 - Core infrastructure refactor

- **Modular architecture**: Split monolithic CLI into focused modules (`models.py`, `client.py`, `config.py`, `db.py`)
- **Config file support**: YAML config at `~/.valhopper/config.yaml` with sensible defaults
- **JSON output**: `--format json` flag on all commands for machine-readable output
- **Yield history DB**: SQLite database at `~/.valhopper/history.db` for tracking validator yield trends
- **Fee estimation**: `optimize` command shows estimated fees before execution
- **Retry/backoff**: Transient transaction failures retry up to 3 times (2s, 5s, 10s delays)
- **DI for BittensorClient**: Subtensor instance injectable for testing
- **Delegate hotkey index**: O(1) lookup by hotkey instead of linear scan
- **Moved env guard**: `BT_NO_PARSE_CLI_ARGS` no longer set on import; moved to CLI entry point
- **Removed dead code**: Deleted obsolete `patch_return.py`

### v0.1.1 - Bug fixes

- **Fixed `ReturnResult.is_error` logic**: The `VALIDATOR_NOT_IN_METAGRAPH` enum was incorrectly used as a "no error" sentinel. Added a proper `NO_ERROR` enum value. `is_error` now correctly returns `True` for all error conditions including `VALIDATOR_NOT_IN_METAGRAPH`.
- **Fixed `vh` entry point**: The `vh` CLI alias referenced a nonexistent `main` function; now correctly points to `cli`.
- **Fixed package structure**: Moved source modules into a proper `valhopper` package under `src/` so `pip install -e .` and entry points work correctly.
- **Fixed relative imports**: Changed bare `from valhopper_transactions import ...` to a relative import (`.valhopper_transactions`) so the package works when installed via pip.
- **Fixed indentation bug in `_compute_return_per_1k_with_status`**: The `if netuid == 0:` / `else` block was incorrectly outside the `try` block, causing a `SyntaxError` where the `except` clause became unreachable.
- **Fixed optimize command flow**: Removed dead-code duplicate `not movable_positions` check; the "already optimal" message now correctly prints before the max-stake filter is applied.
- **Fixed hardcoded test paths**: Test files used absolute paths (`/home/wiggly/...`); replaced with portable relative paths.
- **Removed unused imports**: Cleaned up `dataclass` and `Tuple` imports that were never used.
- **Deprecated `patch_return.py`**: The return calculation patch has already been applied; the script is now marked as obsolete.

## License

MIT

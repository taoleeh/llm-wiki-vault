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
# Dry run (default) - preview changes without executing
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

## Understanding return_per_1000

The `return_per_1000` metric represents the daily yield per 1000 TAO staked with a validator. For example:

- return_per_1000 = 50 TAO means ~5% daily yield
- return_per_1000 = 208 TAO means ~20.8% daily yield

Yields vary dramatically between validators and subnets. A stake earning 0 TAO/day could potentially earn 200+ TAO/day by moving to the best validator.

## How It Works

1. **Fetch delegates** - Query all registered validators and their return_per_1000
2. **Analyze stakes** - Get your stake positions via `get_stake_info_for_coldkey`
3. **Compare yields** - For each position, find the best validator on that subnet
4. **Move stakes** - Use `move_stake` to transfer to the best validator (same subnet, different hotkey)

## Security Notes

- **Never share your coldkey private key** - The CLI only needs the SS58 address for read operations
- **Wallet required for writes** - Actual stake moves require an unlocked wallet
- **Dry-run by default** - The `optimize` command defaults to `--dry-run` for safety
- **Review before confirming** - Always review the planned moves before executing

## Example Output

### list-stakes

```
Stakes for 5EnY2zjcVse2riNN...
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Subnet ┃ Stake(TAO)┃ Current   ┃ Best      ┃ Potential┃ Best      ┃
┃        ┃           ┃ Yield     ┃ Yield     ┃ Daily    ┃ Validator ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ 34     │ 0.1000    │ 0.00      │ 208.89    │ +0.0209  │ 5G9hfkx...│
│ 1      │ 5.2341    │ 7.14      │ 48861157  │ +256.2   │ 5D1saV... │
└────────┴───────────┴───────────┴───────────┴──────────┴───────────┘

Portfolio Summary
Total Staked: 5.3341 TAO
Potential Additional Daily: +256.22 TAO
Potential Additional Monthly: +7686.60 TAO
```

### top-validators

```
Top Validators on Subnet 34
┏━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Rank ┃ Hotkey        ┃ Return/1000    ┃ Daily Yield % ┃ Take   ┃
┡━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ 1    │ 5G9hfkx9wGB1… │ 208.78         │ 20.8782%      │ 0.00%  │
│ 2    │ 5HbScNssaEfi… │ 34.79          │ 3.4788%       │ 9.00%  │
│ 3    │ 5E2LP6EnZ54m… │ 33.86          │ 3.3862%       │ 0.00%  │
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

## License

MIT

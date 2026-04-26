# ValHopper User Guide

## Table of Contents
1. [Understanding Risk Levels](#understanding-risk-levels)
2. [Step-by-Step Usage Guide](#step-by-step-usage-guide)
3. [Rebalancing Strategy](#rebalancing-strategy)
4. [Backend Process Explanation](#backend-process-explanation)

---

## Understanding Risk Levels

ValHopper filters validators using **on-chain trust and stability signals** — not raw APY. A validator returning 500 alpha/1K/day with high validator trust and 1,000 days uptime is *less risky* than one returning 80 alpha/1K/day with zero trust and a 4-day track record.

### The Five Risk Signals

ValHopper uses these on-chain metrics to assess validator quality:

| Signal | Source | What It Measures |
|--------|--------|-----------------|
| **Validator Trust (vtrust)** | Metagraph `Tv` | How much the network trusts this validator's outputs. 1.0 = fully trusted, 0.0 = untrusted. Validators with low trust may be producing poor or invalid work. |
| **Registration Age** | Metagraph `block_at_registration` | How long the validator has been active. Older = more proven. A validator registered 4 days ago is inherently riskier than one running for 300+ days. |
| **Validator Permits** | DelegateInfo `validator_permits` | How many subnets this validator is permitted to validate on. More permits = more network confidence. A validator with 0 permits is a delegate-only node. |
| **Commission (take)** | DelegateInfo `take` | Percentage of yield the validator keeps. Range: 0.0–0.18. Zero-take validators pass 100% yield to stakers, but may be unsustainable or have hidden motives. |
| **Nominator Count** | DelegateInfo `nominators` | How many unique stakers delegate to this validator. More nominators = more social proof. Very few nominators may indicate a new or untested validator. |

### Why NOT Use Raw Return as a Risk Signal?

Return per 1000 (`return_per_1000`) tells you **yield**, not **reliability**. A high-return validator could be:
- New and unsustainable (yield will drop)
- On a volatile subnet with inconsistent emissions
- Running a zero-take strategy that may change

A low-return validator could be:
- Extremely stable and trusted
- On a mature, low-emission subnet
- The safest place for large capital

**Return is the output you optimize for. Trust, age, permits, and nominators are the inputs that determine whether that return is reliable.**

---

### Conservative Level (--risk-level conservative)

**Philosophy**: Only move stake to validators with proven track records and high network trust.

**Filters**:
- Validator trust >= 0.95 (near-perfect network confidence)
- Registration age >= 90 days
- Validator permits >= 1 (must be actively validating, not just delegating)
- Nominator count >= 100 (significant social proof)
- Commission: any (not filtered — take is a business choice, not a risk signal)

**What This Means in Practice**:
- Skips brand-new validators regardless of their return
- Skips validators the network doesn't fully trust
- Skips delegate-only nodes (no validator permits)
- May result in lower return if all "safe" validators have modest returns
- **Fallback**: If no validators pass all filters on a subnet, relaxes age to >= 30 days and trust to >= 0.80

**Best For**:
- Large stakes (100+ alpha) where capital preservation matters
- Users who check positions monthly or less
- Anyone who values sleep over marginal yield

---

### Moderate Level (--risk-level moderate) [DEFAULT]

**Philosophy**: Accept some newness for better yield, but still require basic network trust.

**Filters**:
- Validator trust >= 0.80
- Registration age >= 30 days
- Validator permits >= 1 OR nominator count >= 50
- Nominator count >= 10

**What This Means in Practice**:
- Allows validators with a month-long track record
- Accepts delegate-only nodes if they have significant social proof
- Balances yield opportunity with reasonable safety
- **Fallback**: If no validators pass, relaxes age to >= 7 days and trust to >= 0.50

**Best For**:
- Most users (recommended starting point)
- Medium stakes (10–100 alpha)
- Users who check positions weekly

---

### Aggressive Level (--risk-level aggressive)

**Philosophy**: Maximize yield. Accept new and unproven validators if their return is high.

**Filters**:
- Validator trust >= 0.50
- Registration age >= 7 days
- No minimum nominator count
- No validator permit requirement

**What This Means in Practice**:
- Will move stake to a validator registered last week
- Accepts low-trust validators if they're the highest yield
- Maximum return capture but maximum volatility
- A validator's return may drop sharply if it loses trust or deregisters
- **Fallback**: If no validators pass, removes all filters except trust > 0

**Best For**:
- Small stakes (< 10 alpha) where downside is limited
- Users who monitor positions daily
- Yield chasers comfortable with volatility

---

### Risk Level Comparison at a Glance

| Filter | Conservative | Moderate | Aggressive |
|--------|-------------|----------|------------|
| Validator Trust | >= 0.95 | >= 0.80 | >= 0.50 |
| Age | >= 90 days | >= 30 days | >= 7 days |
| Validator Permits | >= 1 | >= 1 or nominators >= 50 | any |
| Nominator Count | >= 100 | >= 10 | any |
| Fallback Trust | >= 0.80 | >= 0.50 | > 0 |
| Fallback Age | >= 30 days | >= 7 days | 0 days |

---

## Step-by-Step Usage Guide

### Prerequisites

1. **Install Bittensor**:
   ```bash
   pip install bittensor
   ```

2. **Have a wallet** at `~/.bittensor/wallets/`:
   - Wallet name (e.g., "mywallet")
   - Coldkey SS58 address
   - Hotkey for signing (e.g., "default")

3. **Ensure you have**:
   - TAO for transaction fees (~0.01 TAO sufficient)
   - Alpha tokens staked with validators

---

### Phase 1: See Your Current Stakes

```bash
./valhopper --coldkey 5YourColdkeySS58Address list-stakes
```

**What happens in the backend**:
1. Connects to Bittensor Finney mainnet via RPC
2. Calls `subtensor.get_stake_info_for_coldkey()` — queries the Substrate chain's StakeInfo storage for your coldkey
3. Returns every stake position: subnet ID, validator hotkey, amount
4. For each validator, calls `subtensor.get_delegates()` to fetch return_per_1000
5. Calculates your current return per position
6. Displays results in a table

**Time**: ~5–10 seconds total

---

### Phase 2: Dry Run (Preview Moves)

```bash
./valhopper --coldkey 5YourColdkeySS58Address optimize --dry-run
```

**Note**: `--dry-run` is a flag (opt-in). Without it, the `optimize` command will attempt live execution (which requires a wallet and confirmation prompt). Always use `--dry-run` first to preview.

**What happens in the backend**:
1. Same data gathering as list-stakes
2. For each subnet you're staked on:
   - Fetches all delegates registered on that subnet
   - Applies risk-level filters (trust, age, permits, nominators)
   - Among passing validators, finds highest `return_per_1000`
   - If current validator IS already the best: skips (no move needed)
   - If better validator found: calculates return improvement and daily yield gain
3. Displays "Planned Stake Moves" table with from/to validators and return delta
4. Shows summary: total stake to move, average improvement, daily/monthly extra yield
5. **NO transactions are created, signed, or submitted**

**Time**: ~8–15 seconds total

**What to check**:
- Are the target validators names you recognize?
- Are return improvements significant enough to justify a move?
- For small stakes (< 1 alpha), the yield gain may not be worth the effort

---

### Phase 3: Live Execution

```bash
./valhopper \
  --coldkey 5YourColdkeySS58Address \
  --wallet-name mywallet \
  --wallet-hotkey default \
  optimize
```

**What happens in the backend**:

1. **Analysis** (same as dry run) — identifies which positions to move

2. **Security confirmation** — prompts you to confirm before proceeding

3. **Wallet loading** — reads your wallet from disk:
   - Loads coldkey from `~/.bittensor/wallets/mywallet/coldkey` (encrypted, prompts for password)
   - Loads hotkey from `~/.bittensor/wallets/mywallet/hotkeys/default`
   - Verifies both files exist

4. **Transaction loop** — for each position to move:
   a. **Constructs the extrinsic**: `subtensor.move_stake()` creates a `StakeMoved` call:
      - `origin_netuid`: your current subnet
      - `origin_hotkey_ss58`: current validator hotkey
      - `destination_netuid`: same subnet (we only swap validators, not subnets)
      - `destination_hotkey_ss58`: target validator hotkey
      - `move_all_stake=True`: transfers entire position at once
   b. **Signs the transaction**: your hotkey signs the extrinsic
   c. **Submits to mempool**: the signed transaction enters the Bittensor mempool
   d. **Waits for inclusion**: the next block producer picks up the transaction (~12 seconds per block)
   e. **Waits for finalization**: after inclusion, Bittensor requires additional block confirmations before the state change is irreversible (~36 seconds total)
   f. **Records result**: success (with transaction hash) or failure (with error message)

5. **Results display** — shows a table with per-transaction status

**Time per transaction**: ~12–15 seconds (mostly waiting for finality)
**Total time**: ~12–15 seconds × number of positions being moved

**Important**: If a transaction fails (rate limit, network error), the tool continues with remaining positions. Failed transactions can be retried by re-running the command.

---

## Rebalancing Strategy

### How Often Should You Rebalance?

Each `move_stake` costs a small TAO fee (~0.0001–0.001 TAO). The question is: does the return improvement cover the cost before your next rebalance?

#### Frequency by Stake Size

| Total Stake | Frequency | Reasoning |
|-------------|-----------|-----------|
| < 5 alpha | Monthly | Gains are small; don't over-optimize |
| 5–50 alpha | Every 2 weeks | Good balance of yield vs effort |
| 50–200 alpha | Weekly | Larger gains justify more attention |
| > 200 alpha | 2x per week | Even small return improvements compound significantly |

#### Only Move When the Improvement Is Meaningful

Don't rebalance for marginal gains. Use these thresholds:

| Your Current Ret/1K α | Move When Better By | Example |
|------------------|--------------------|---------|
| < 100% | +20 percentage points | 80% -> 100% |
| 100–300% | +30 percentage points | 200% -> 260% |
| 300–500% | +50 percentage points | 400% -> 600% |
| > 500% | +100 percentage points | 500% -> 1000% |

**Why these thresholds?** Higher-return positions are more volatile — a validator returning 1000% today may return 200% next week. A +20% improvement at low return is relatively stable; a +100% improvement at high return may be fleeting.

#### Break-Even Calculation

```
Daily gain = (Stake / 1000) x (new_return_per_1000 - old_return_per_1000)
Break-even days = Transaction Fee / Daily Gain
```

**Example**: Moving 10 alpha for +100% return improvement:
- Daily gain = ~0.027 alpha
- Transaction cost = ~0.001 TAO
- Break-even = 0.04 days (~1 hour)
- Rebalancing weekly: 0.189 alpha gained vs 0.001 TAO cost

**Rule of thumb**: Only rebalance if expected monthly gain exceeds 10x the transaction cost.

#### Why Not Rebalance Daily?

1. **Yield volatility**: Today's best validator may not be tomorrow's. Moving daily chases noise.
2. **Rate limits**: Bittensor throttles frequent stake operations.
3. **Transaction costs**: Small fees add up, especially on small stakes.
4. **Emission timing**: Validator yields update per epoch (every 360 blocks ≈ 72 minutes). More frequent checks don't get fresh data.

---

## Backend Process Explanation

### Data Flow Diagram

```
Your Machine                    RPC Node                  Bittensor Chain
    |                              |                           |
    |--- get_delegates() --------->|--- query DelegateInfo --->|
    |<-- 5700+ validators ---------|<-- delegate list ---------|
    |                              |                           |
    |--- get_stake_info() -------->|--- query StakeInfo ------>|
    |<-- your positions -----------|<-- stake list ------------|
    |                              |                           |
    |--- metagraph(netuid) ------->|--- query SubtensorState ->|
    |<-- trust, age, etc ----------|<-- metagraph -------------|
    |                              |                           |
    |  (filters + selects best)    |                           |
    |                              |                           |
    |--- move_stake() ------------>|--- submit extrinsic ----->|
    |<-- tx hash ------------------|<-- inclusion/finality ----|
```

### Step-by-Step Chain Interactions

**Step 1: Connect** (~2–5s)
```python
subtensor = bittensor.Subtensor(network="finney")
```
Establishes WebSocket connection to a Bittensor RPC node. Gets chain metadata (runtime version, genesis hash).

**Step 2: Fetch Delegates** (~1–3s)
```python
delegates = subtensor.get_delegates()
```
Queries the `DelegateInfo` storage map. Returns all 5700+ delegates with their hotkey, return_per_1000, take, registrations, validator_permits, nominators, and total_stake per subnet.

**Step 3: Fetch Metagraph** (~1–2s per subnet)
```python
meta = subtensor.metagraph(netuid)
```
Queries the full metagraph for a specific subnet. Returns per-UID arrays:
- `Tv` (validator trust): 0.0–1.0, how much the network trusts this validator
- `S` (stake): total stake on this UID
- `C` (consensus): consensus weight
- `I` (incentive): reward incentive
- `D` (dividends): dividends to delegators
- `block_at_registration`: block number when UID was created

**Step 4: Get Your Stakes** (~1–2s)
```python
stake_infos = subtensor.get_stake_info_for_coldkey(coldkey_ss58)
```
Returns every stake position tied to your coldkey: subnet ID, validator hotkey, and staked amount.

**Step 5: Apply Risk Filters** (~0.1s, local computation)
For each subnet where you have a position:
1. Get all delegates serving that subnet
2. Look up each delegate's validator trust from the metagraph
3. Look up registration age from the metagraph
4. Apply risk-level thresholds (trust, age, permits, nominators)
5. Sort passing validators by `return_per_1000` descending
6. Pick the best

**Step 6: Execute move_stake** (~12–15s per transaction)
```python
response = subtensor.move_stake(
    wallet=wallet,
    origin_netuid=pos.netuid,
    origin_hotkey_ss58=pos.hotkey,
    destination_netuid=pos.netuid,
    destination_hotkey_ss58=pos.best_validator_hotkey,
    move_all_stake=True,
    wait_for_inclusion=True,
    wait_for_finalization=True,
)
```

On-chain, this executes a `StakeMoved` extrinsic:
1. Validates the coldkey owns the stake at origin
2. Deducts stake from origin validator
3. Credits stake to destination validator
4. Emits `StakeMoved` event
5. Charges TAO computation fee

### Security Considerations

1. **Hotkey cannot withdraw**: Your hotkey can only move stake between validators. It cannot transfer TAO or alpha out of your wallet. Only the coldkey can unstake/withdraw.
2. **Finality**: Bittensor uses GRANDPA consensus. After finalization (~36 seconds), the state change is irreversible.
3. **No undo**: The only way to reverse a move is to move stake back, which costs another transaction fee.
4. **Validator risk**: Even "conservative" validators can have issues. Diversifying across multiple validators on a subnet is not possible with `move_stake` (it moves all stake to one target).

---

## Quick Reference

### List Current Stakes
```bash
./valhopper --coldkey <SS58> list-stakes
```

### Preview Moves (Dry Run)
```bash
./valhopper --coldkey <SS58> optimize --dry-run
```

### Execute Moves (Live)
```bash
./valhopper --coldkey <SS58> --wallet-name <name> optimize
```

### With Risk Level
```bash
./valhopper --coldkey <SS58> optimize --dry-run --risk-level conservative
```

### View Top Validators for a Subnet
```bash
./valhopper --coldkey <SS58> top-validators <netuid>
```

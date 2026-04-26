# ValHopper New Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Goal:** Add all new CLI commands (optimize with min-improvement/split/capacity, watch with Discord, history, snapshot, portfolio, diff, rollback) and multi-coldkey support.
> **Architecture:** Build on top of the refactored core from Plan A (models.py, client.py, db.py, config.py). Each new command is a self-contained Click command in valhopper_cli.py. Discord integration uses urllib to avoid new dependencies.
> **Tech Stack:** Python 3.10+, bittensor SDK, click, rich, sqlite3, urllib (stdlib for webhooks)

**Prerequisite:** Plan A (core infrastructure) must be completed first.

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/valhopper/valhopper_cli.py` | **MODIFIED** — Add all new CLI commands |
| `src/valhopper/client.py` | **MODIFIED** — Add capacity/slippage estimation, best-validator-per-netuid caching in get_stakes |
| `src/valhopper/valhopper_transactions.py` | **MODIFIED** — Add partial move_stake support, rollback state saving |
| `src/valhopper/db.py` | **MODIFIED** — Add rollback state storage table |
| `src/valhopper/notifications.py` | **NEW** — Discord webhook notification sender |
| `src/valhopper/valhopper_logging.py` | **MODIFIED** — Add rollback state serializer |
| `tests/test_notifications.py` | **NEW** — Discord webhook tests |
| `tests/test_db.py` | **MODIFIED** — Add rollback table tests |
| `README.md` | **MODIFIED** — Update at end |

---

### Task 1: Add `--min-improvement` flag to optimize command

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

This enforces the USER_GUIDE's threshold logic. Positions where `return_delta < min_improvement` are skipped.

- [ ] **Step 1: Add `--min-improvement` option to the optimize command**

In `valhopper_cli.py`, add to the `optimize` command's options:

```python
@click.option('--min-improvement', type=float, default=None,
              help='Minimum return_per_1000 improvement to justify a move (default: from config or 0)')
```

Update the function signature:
```python
def optimize(ctx, dry_run, risk_level, max_stake_per_move, min_improvement):
```

- [ ] **Step 2: Apply min-improvement filter**

After computing `movable_positions` (the existing filter), add:

```python
effective_min_improvement = min_improvement if min_improvement is not None else ctx.obj.get('min_improvement', 0.0)

if effective_min_improvement > 0:
    before_count = len(movable_positions)
    movable_positions = [
        p for p in movable_positions
        if p.return_delta >= effective_min_improvement
    ]
    skipped = before_count - len(movable_positions)
    if skipped > 0:
        console.print(
            f"[dim]Skipped {skipped} position(s) with improvement < {effective_min_improvement}[/dim]"
        )
    if not movable_positions:
        console.print(Panel(
            f"[green]No positions with improvement >= {effective_min_improvement} "
            f"return_per_1000. All positions are good enough.[/green]"
        ))
        return
```

- [ ] **Step 3: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add --min-improvement flag to optimize command"
  ```

---

### Task 2: Add post-move yield estimation (slippage/capacity awareness)

**Files:**
- Modify: `src/valhopper/client.py`

- [ ] **Step 1: Add `estimate_post_move_return` method to BittensorClient**

In `client.py`, add:

```python
def estimate_post_move_return(self, hotkey: str, netuid: int, additional_stake_tao: float) -> Optional[float]:
    """Estimate the return_per_1000 after adding additional_stake_tao to a validator.

    If the additional stake would dilute the yield by >20%, return the diluted
    estimate. Otherwise return the current return_per_1000 (no significant dilution).
    """
    try:
        meta = self.get_metagraph(netuid)
        uid = None
        for i, hk in enumerate(meta.hotkeys):
            if hk == hotkey:
                uid = i
                break
        if uid is None:
            return None

        current_stake = float(meta.S[uid])
        if current_stake <= 0:
            return None

        current_ret = self._compute_return_per_1k(hotkey, netuid)
        if current_ret <= 0:
            return None

        # Estimate: assume emission stays constant, yield is inversely proportional to stake
        new_stake = current_stake + additional_stake_tao
        diluted_ret = current_ret * (current_stake / new_stake)
        return diluted_ret
    except Exception:
        return None
```

- [ ] **Step 2: Show slippage warning in optimize command**

In `valhopper_cli.py`, in the optimize command, after building the `movable_positions` table, add a slippage check column or warning:

```python
# After the table display, before the summary panel:
slippage_warnings = []
for p in movable_positions:
    post_move = client.estimate_post_move_return(
        p.best_validator_hotkey, p.netuid, p.stake_tao
    )
    if post_move is not None and post_move < p.best_validator_return * 0.8:
        slippage_warnings.append(
            f"Subnet {p.netuid}: Your {p.stake_tao:.2f} stake would dilute "
            f"yield from {fmt_ret(p.best_validator_return)} to ~{fmt_ret(post_move)} "
            f"({(1 - post_move/p.best_validator_return)*100:.0f}% reduction)"
        )

if slippage_warnings:
    console.print("\n[yellow]⚠ Yield Dilution Warnings:[/yellow]")
    for w in slippage_warnings:
        console.print(f"  [yellow]{w}[/yellow]")
```

- [ ] **Step 3: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add yield dilution/slippage estimation to optimize"
  ```

---

### Task 3: Add stake splitting across multiple validators

**Files:**
- Modify: `src/valhopper/valhopper_transactions.py`
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add `execute_partial_stake_move` to `valhopper_transactions.py`**

```python
def execute_partial_stake_move(subtensor, wallet, position, amount_tao: float):
    """Execute a partial stake move (move a specific amount, not all).

    Args:
        subtensor: Bittensor subtensor instance
        wallet: Wallet instance
        position: StakePosition to move
        amount_tao: Amount of stake to move in TAO

    Returns:
        (success: bool, message: str, details: dict) tuple
    """
    last_exception = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = subtensor.move_stake(
                wallet=wallet,
                origin_netuid=position.netuid,
                origin_hotkey_ss58=position.hotkey,
                destination_netuid=position.netuid,
                destination_hotkey_ss58=position.best_validator_hotkey,
                amount=amount_tao,
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
                msg = f"Success (moved {amount_tao:.4f})"
                if details.get("tao_fee"):
                    msg += f" fee: {details['tao_fee']}"
                return True, msg, details
            else:
                error_parts = []
                if response.message:
                    error_parts.append(str(response.message))
                if response.error:
                    error_parts.append(str(response.error))
                error_msg = " | ".join(error_parts) if error_parts else "Transaction failed"
                if _is_retryable(error_msg) and attempt < MAX_RETRIES:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    time.sleep(delay)
                    continue
                return False, error_msg, {}

        except Exception as e:
            last_exception = e
            if _is_retryable(str(e)) and attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                time.sleep(delay)
                continue
            return False, f"Exception: {type(e).__name__}: {e}", {}

    return False, f"Failed after {MAX_RETRIES} retries. Last: {last_exception}", {}
```

- [ ] **Step 2: Add `--split` option to optimize command**

In `valhopper_cli.py`, add to the optimize command options:

```python
@click.option('--split', type=int, default=None,
              help='Distribute stake across top N validators instead of moving all to one')
```

- [ ] **Step 3: Implement split logic in the optimize command body**

After computing `movable_positions` and before execution, add split logic:

```python
if split and split > 1:
    # For each position, compute the top-N validators and allocate stake
    split_positions = []
    for p in movable_positions:
        delegates = client.get_delegates()
        subnet_delegates = [d for d in delegates if p.netuid in d.registrations]
        filtered = client._apply_risk_filters(subnet_delegates, p.netuid, effective_risk)
        scored = []
        for d, risk in filtered:
            ret = client._compute_return_per_1k(d.hotkey_ss58, p.netuid)
            if ret > 0:
                scored.append((d, risk, ret))
        scored.sort(key=lambda x: x[2], reverse=True)
        top_n = scored[:split]

        if len(top_n) <= 1:
            split_positions.append((p, [(p.best_validator_hotkey, p.stake_tao)]))
            continue

        # Equal distribution across top N
        per_validator = p.stake_tao / len(top_n)
        allocations = [(d.hotkey_ss58, per_validator) for d, _, _ in top_n]
        split_positions.append((p, allocations))

    # Display split plan
    table = Table(title=f"Planned Stake Splits (top-{split})")
    table.add_column("Subnet", justify="right", style="cyan")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Distributions", style="dim")

    for p, allocs in split_positions:
        dist_str = ", ".join(
            f"{amt:.4f} -> {hk[:12]}..." for hk, amt in allocs
        )
        table.add_row(
            str(p.netuid),
            f"{p.stake_tao:.4f} {p.token_symbol}",
            dist_str,
        )

    console.print(table)

    if dry_run:
        console.print("\n[yellow]DRY RUN - No actual transactions will be made.[/yellow]")
        return

    # Execute split moves (if not dry run)
    if not click.confirm(f"\nProceed with {len(split_positions)} split moves?"):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    wallet_name = ctx.obj.get("wallet_name")
    if not wallet_name:
        console.print("[red]Error:[/red] --wallet-name required for live execution")
        return

    try:
        wallet = load_wallet(wallet_name, ctx.obj.get("wallet_hotkey", "default"), ctx.obj.get("wallet_path"))
    except Exception as e:
        console.print(f"[red]Wallet error:[/red] {e}")
        return

    results = []
    for p, allocs in split_positions:
        for dest_hotkey, amount in allocs:
            # Create a temporary position with the destination hotkey
            split_pos = StakePosition(
                hotkey=p.hotkey,
                netuid=p.netuid,
                stake_tao=amount,
                current_validator_return=p.current_validator_return,
                best_validator_return=p.best_validator_return,
                best_validator_hotkey=dest_hotkey,
            )
            console.print(
                f"  Subnet {p.netuid}: {p.hotkey[:8]}... -> {dest_hotkey[:8]}... ({amount:.4f})",
                end=" ",
            )
            success, msg, details = execute_partial_stake_move(client.subtensor, wallet, split_pos, amount)
            status = "[green]OK[/green]" if success else f"[red]{msg[:80]}[/red]"
            console.print(status)
            results.append((split_pos, success, msg, details))

    format_transaction_results(results, console)
    log_path = write_transaction_log(results)
    if log_path:
        console.print(f"[dim]Transaction log: {log_path}[/dim]")
    return  # Skip the normal execution path
```

- [ ] **Step 4: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 5: Commit**
  ```bash
  git add -A && git commit -m "feat: add --split option for multi-validator stake distribution"
  ```

---

### Task 4: Add Discord webhook notifications (`notifications.py`)

**Files:**
- Create: `src/valhopper/notifications.py`
- Create: `tests/test_notifications.py`

- [ ] **Step 1: Create `src/valhopper/notifications.py`**

```python
"""Discord webhook notifications for ValHopper."""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("valhopper")


def send_discord_webhook(webhook_url: str, content: str, embed: Optional[dict] = None) -> bool:
    """Send a notification to a Discord channel via webhook.

    Args:
        webhook_url: Discord webhook URL
        content: Plain text message content
        embed: Optional Discord embed dict

    Returns:
        True if sent successfully, False otherwise
    """
    if not webhook_url:
        return False

    payload = {"content": content}
    if embed:
        payload["embeds"] = [embed]

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204 or resp.status == 200
    except urllib.error.HTTPError as e:
        logger.warning(f"Discord webhook HTTP error: {e.code} {e.reason}")
        return False
    except Exception as e:
        logger.warning(f"Discord webhook failed: {e}")
        return False


def format_optimize_message(results: list, dry_run: bool, coldkey: str) -> str:
    """Format optimize results as a Discord message."""
    success_count = sum(1 for _, s, _, _ in results if s)
    fail_count = len(results) - success_count

    mode = "DRY RUN" if dry_run else "LIVE"
    lines = [f"**ValHopper Optimize ({mode})**"]
    lines.append(f"Coldkey: `{coldkey[:16]}...`")

    if success_count > 0:
        total_daily_gain = sum(
            p.potential_additional_daily for p, s, _, _ in results if s
        )
        lines.append(f"Moved {success_count} position(s)")
        lines.append(f"Additional daily yield: +{total_daily_gain:.4f} alpha")
    if fail_count > 0:
        lines.append(f"Failed: {fail_count}")

    return "\n".join(lines)


def format_watch_message(positions: list, coldkey: str) -> str:
    """Format watch/alert results as a Discord message."""
    improvable = [p for p in positions if p.best_validator_hotkey and p.return_delta > 0]

    if not improvable:
        return f"**ValHopper Watch**: All {len(positions)} position(s) optimal for `{coldkey[:16]}...`"

    total_gain = sum(p.potential_additional_daily for p in improvable)
    lines = [
        f"**ValHopper Watch Alert** :chart_with_upwards_trend:",
        f"Coldkey: `{coldkey[:16]}...`",
        f"{len(improvable)} position(s) could improve yield",
        f"Potential additional daily: +{total_gain:.4f} alpha",
    ]

    for p in improvable[:5]:
        lines.append(
            f"  Subnet {p.netuid}: {fmt_ret_simple(p.current_return_per_1000)} -> "
            f"{fmt_ret_simple(p.best_return_per_1000)} (+{fmt_ret_simple(p.return_delta)})"
        )

    if len(improvable) > 5:
        lines.append(f"  ... and {len(improvable) - 5} more")

    return "\n".join(lines)


def fmt_ret_simple(val: float) -> str:
    if val == 0:
        return "0"
    if val < 0.01:
        return f"{val:.6f}"
    if val < 1:
        return f"{val:.4f}"
    if val < 100:
        return f"{val:.2f}"
    return f"{val:.1f}"
```

- [ ] **Step 2: Write notification tests**

Create `tests/test_notifications.py`:

```python
"""Tests for valhopper.notifications."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.notifications import (
    send_discord_webhook,
    format_optimize_message,
    format_watch_message,
    fmt_ret_simple,
)
from valhopper.models import StakePosition


def test_fmt_ret_simple():
    assert fmt_ret_simple(0) == "0"
    assert fmt_ret_simple(0.001) == "0.001000"
    assert fmt_ret_simple(0.5) == "0.5000"
    assert fmt_ret_simple(50.0) == "50.00"
    assert fmt_ret_simple(500.0) == "500.0"


def test_format_optimize_message_dry_run():
    pos = StakePosition(
        hotkey="hk1", netuid=1, stake_tao=10.0,
        current_validator_return=0.1, best_validator_return=0.2,
        best_validator_hotkey="hk2",
    )
    results = [(pos, True, "OK", {})]
    msg = format_optimize_message(results, dry_run=True, coldkey="5TestColdkey1234567890")
    assert "DRY RUN" in msg
    assert "1 position" in msg


def test_format_optimize_message_live():
    pos = StakePosition(
        hotkey="hk1", netuid=1, stake_tao=10.0,
        current_validator_return=0.1, best_validator_return=0.2,
        best_validator_hotkey="hk2",
    )
    results = [(pos, True, "OK", {})]
    msg = format_optimize_message(results, dry_run=False, coldkey="5TestColdkey1234567890")
    assert "LIVE" in msg


def test_format_watch_message_with_improvements():
    positions = [
        StakePosition(
            hotkey="hk1", netuid=1, stake_tao=10.0,
            current_validator_return=0.1, best_validator_return=0.2,
            best_validator_hotkey="hk2",
        ),
        StakePosition(
            hotkey="hk3", netuid=2, stake_tao=5.0,
            current_validator_return=0.5, best_validator_return=0.5,
            best_validator_hotkey="hk3",  # already optimal
        ),
    ]
    msg = format_watch_message(positions, coldkey="5TestColdkey1234567890")
    assert "1 position" in msg
    assert "Subnet 1" in msg


def test_format_watch_message_all_optimal():
    positions = [
        StakePosition(
            hotkey="hk1", netuid=1, stake_tao=10.0,
            current_validator_return=0.5, best_validator_return=0.5,
            best_validator_hotkey="hk1",
        ),
    ]
    msg = format_watch_message(positions, coldkey="5TestColdkey1234567890")
    assert "optimal" in msg


def test_send_discord_webhook_no_url():
    assert send_discord_webhook("", "test") is False
    assert send_discord_webhook(None, "test") is False
```

- [ ] **Step 3: Run notification tests**
  Run: `pytest tests/test_notifications.py -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add Discord webhook notifications module"
  ```

---

### Task 5: Add `watch` command with Discord integration

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add the `watch` command**

In `valhopper_cli.py`, add after the `top_validators` command:

```python
@cli.command()
@click.option('--interval', type=int, default=3600, help='Check interval in seconds (default: 3600)')
@click.option('--once', is_flag=True, default=False, help='Run once and exit (no loop)')
@click.option('--discord', 'send_discord', is_flag=True, default=False,
              help='Send alerts to Discord webhook from config')
@click.pass_context
def watch(ctx, interval, once, send_discord):
    """Monitor stakes and alert when better validators are available."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    client = BittensorClient(network=ctx.obj['network'])
    risk_level = ctx.obj.get('risk_level', 'moderate')
    discord_url = ctx.obj.get('discord_webhook_url') if send_discord else None

    def _check():
        positions = client.get_stakes(coldkey, risk_level)
        if not positions:
            console.print(f"[yellow]No stakes found for {coldkey[:16]}...[/yellow]")
            return

        improvable = [
            p for p in positions
            if p.best_validator_hotkey and p.hotkey != p.best_validator_hotkey and p.return_delta > 0
        ]

        if not improvable:
            console.print(f"[green][{_now()}] All {len(positions)} position(s) optimal[/green]")
        else:
            total_gain = sum(p.potential_additional_daily for p in improvable)
            console.print(
                f"[yellow][{_now()}] {len(improvable)} position(s) could improve "
                f"+{total_gain:.4f} alpha/day[/yellow]"
            )
            for p in improvable:
                console.print(
                    f"  Subnet {p.netuid}: {fmt_ret(p.current_return_per_1000)} -> "
                    f"{fmt_ret(p.best_return_per_1000)} (+{fmt_ret(p.return_delta)})"
                )

        if send_discord and improvable:
            from .notifications import format_watch_message, send_discord_webhook
            msg = format_watch_message(positions, coldkey)
            ok = send_discord_webhook(discord_url, msg)
            if ok:
                console.print("[dim]Discord notification sent[/dim]")
            else:
                console.print("[dim]Discord notification failed[/dim]")

    if once:
        _check()
        return

    console.print(
        f"[bold]Watching stakes for {coldkey[:16]}...[/bold] "
        f"(interval: {interval}s, risk: {risk_level})"
    )
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    import signal
    running = True

    def _handler(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _handler)

    while running:
        try:
            _check()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        if not running:
            break
        console.print(f"[dim]Next check in {interval}s...[/dim]")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            break

    console.print("\n[yellow]Watch stopped.[/yellow]")


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")
```

- [ ] **Step 2: Send Discord notification after optimize execution**

In the `optimize` command, after `format_transaction_results(results, console)` and the log write, add:

```python
discord_url = ctx.obj.get('discord_webhook_url')
if discord_url:
    from .notifications import format_optimize_message, send_discord_webhook
    msg = format_optimize_message(results, dry_run=False, coldkey=coldkey)
    send_discord_webhook(discord_url, msg)
    console.print("[dim]Discord notification sent[/dim]")
```

- [ ] **Step 3: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add watch command with Discord webhook alerts"
  ```

---

### Task 6: Add `snapshot` and `history` commands

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add the `snapshot` command**

```python
@cli.command()
@click.pass_context
def snapshot(ctx):
    """Record a yield snapshot of all validators (and your positions) to local DB."""
    coldkey = ctx.obj.get('coldkey')
    client = BittensorClient(network=ctx.obj['network'])

    from .db import _get_db, snapshot_today

    conn = _get_db()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Recording yield snapshot...", total=None)
        snapshot_today(client, conn, coldkey)

    conn.close()
    console.print("[green]Yield snapshot recorded.[/green]")
    if coldkey:
        console.print(f"[dim]Position snapshot also recorded for {coldkey[:16]}...[/dim]")
```

- [ ] **Step 2: Add the `history` command**

```python
@cli.command()
@click.argument('netuid', type=int)
@click.option('--hotkey', default=None, help='Filter by specific validator hotkey')
@click.option('--days', type=int, default=30, help='Number of days to show (default: 30)')
@click.pass_context
def history(ctx, netuid, hotkey, days):
    """Show yield history for validators on a subnet."""
    from .db import _get_db, get_validator_history, get_subnet_history, detect_declining_validators

    conn = _get_db()

    if hotkey:
        rows = get_validator_history(conn, netuid, hotkey, days)
        if not rows:
            console.print(f"[yellow]No history found for {hotkey[:16]}... on subnet {netuid}[/yellow]")
            conn.close()
            return

        table = Table(title=f"Yield History for {hotkey[:16]}... on Subnet {netuid}")
        table.add_column("Date", style="cyan")
        table.add_column("Ret/1K", justify="right", style="green")
        table.add_column("Trust", justify="right")
        table.add_column("Nominators", justify="right")

        for r in rows:
            table.add_row(
                r["snapshot_date"],
                fmt_ret(r["return_per_1000"]),
                color_trust(r["trust"]),
                str(r["nominators"]),
            )

        console.print(table)
    else:
        rows = get_subnet_history(conn, netuid)
        declining = detect_declining_validators(conn, netuid, min_days=7, decline_threshold=0.3)

        if not rows:
            console.print(f"[yellow]No history found for subnet {netuid}[/yellow]")
            conn.close()
            return

        symbol = get_token_symbol(netuid)
        table = Table(title=f"Latest Yield Snapshot — Subnet {netuid}")
        table.add_column("Hotkey", style="blue")
        table.add_column(f"Ret/1K {symbol}", justify="right", style="green")
        table.add_column("Trust", justify="right")
        table.add_column("Nominators", justify="right")
        table.add_column("Date", style="dim")

        for r in rows[:20]:
            hk = r["hotkey"]
            table.add_row(
                f"{hk[:20]}...",
                fmt_ret(r["return_per_1000"]),
                color_trust(r["trust"]),
                str(r["nominators"]),
                r["snapshot_date"],
            )

        console.print(table)

        if declining:
            console.print("\n[yellow]⚠ Declining Validators (>=30% drop over 7+ days):[/yellow]")
            for d in declining:
                console.print(
                    f"  {d['hotkey'][:16]}... : {fmt_ret(d['old_return'])} -> "
                    f"{fmt_ret(d['new_return'])} ({d['decline_pct']*100:.0f}% decline)"
                )

    conn.close()
```

- [ ] **Step 3: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 4: Commit**
  ```bash
  git add -A && git commit -m "feat: add snapshot and history commands for yield tracking"
  ```

---

### Task 7: Add `portfolio` command

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add the `portfolio` command**

```python
@cli.command()
@click.pass_context
def portfolio(ctx):
    """Show portfolio overview across all subnets with optimization opportunities."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    client = BittensorClient(network=ctx.obj['network'])
    risk_level = ctx.obj.get('risk_level', 'moderate')

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Analyzing portfolio...", total=None)
        positions = client.get_stakes(coldkey, risk_level)

    if not positions:
        console.print(Panel(f"[yellow]No stakes found for coldkey:[/yellow]\n[cyan]{coldkey}[/cyan]"))
        return

    # Group by subnet
    from collections import defaultdict
    subnet_positions = defaultdict(list)
    for p in positions:
        subnet_positions[p.netuid].append(p)

    table = Table(title=f"Portfolio for {coldkey[:16]}...", show_lines=True)
    table.add_column("Subnet", justify="right", style="cyan")
    table.add_column("Positions", justify="right")
    table.add_column("Total Stake", justify="right", style="green")
    table.add_column("Avg Yield", justify="right")
    table.add_column("Best Yield", justify="right", style="yellow")
    table.add_column("Δ Daily α", justify="right", style="magenta")
    table.add_column("Opportunity", justify="right")

    total_stake = 0
    total_daily_earn = 0
    total_potential_gain = 0

    for netuid in sorted(subnet_positions.keys()):
        subnet_pos = subnet_positions[netuid]
        stake_sum = sum(p.stake_tao for p in subnet_pos)
        daily_sum = sum(p.current_daily_earn for p in subnet_pos)
        potential_sum = sum(p.potential_additional_daily for p in subnet_pos)
        best_yield = max(p.best_return_per_1000 for p in subnet_pos) if subnet_pos else 0
        avg_yield = sum(p.current_return_per_1000 for p in subnet_pos) / len(subnet_pos) if subnet_pos else 0

        symbol = get_token_symbol(netuid)

        if potential_sum > 0.01:
            opportunity = f"[green]HIGH[/green]"
        elif potential_sum > 0.001:
            opportunity = f"[yellow]LOW[/yellow]"
        else:
            opportunity = "-"

        table.add_row(
            str(netuid),
            str(len(subnet_pos)),
            f"{stake_sum:.4f} {symbol}",
            fmt_ret(avg_yield),
            fmt_ret(best_yield),
            f"[green]+{fmt_ret(potential_sum)}[/green]" if potential_sum > 0 else "-",
            opportunity,
        )

        total_stake += stake_sum
        total_daily_earn += daily_sum
        total_potential_gain += potential_sum

    console.print(table)
    console.print(Panel(
        f"[bold]Total Stake:[/bold] {total_stake:.4f} across {len(subnet_positions)} subnet(s)\n"
        f"[bold]Current Daily Earn:[/bold] {fmt_ret(total_daily_earn)} alpha\n"
        f"[bold]Potential Additional Daily:[/bold] +{fmt_ret(total_potential_gain)} alpha\n"
        f"[bold]Potential Additional Monthly:[/bold] +{total_potential_gain * 30:.4f} alpha",
        title="[bold]Portfolio Summary[/bold]",
        border_style="green",
    ))

    if ctx.obj.get('output_format') == 'json':
        from .valhopper_logging import format_json_output
        data = {
            "coldkey": coldkey,
            "total_stake": total_stake,
            "total_daily_earn": total_daily_earn,
            "total_potential_gain": total_potential_gain,
            "subnets": {
                str(netuid): {
                    "positions": len(subnet_positions[netuid]),
                    "stake": sum(p.stake_tao for p in subnet_positions[netuid]),
                    "potential_daily_gain": sum(
                        p.potential_additional_daily for p in subnet_positions[netuid]
                    ),
                }
                for netuid in sorted(subnet_positions.keys())
            },
        }
        console.print(format_json_output("portfolio", data))
```

- [ ] **Step 2: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 3: Commit**
  ```bash
  git add -A && git commit -m "feat: add portfolio command for cross-subnet overview"
  ```

---

### Task 8: Add `diff` command

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add the `diff` command**

```python
@cli.command()
@click.argument('netuid', type=int)
@click.pass_context
def diff(ctx, netuid):
    """Compare validator picks across risk levels for a subnet."""
    coldkey = ctx.obj.get('coldkey')
    client = BittensorClient(network=ctx.obj['network'])

    risk_levels = ['conservative', 'moderate', 'aggressive']

    # Get best validator at each risk level
    results = {}
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        for rl in risk_levels:
            progress.add_task(f"Analyzing {rl}...", total=None)
            best = client.get_best_validator_for_subnet(netuid, rl)
            results[rl] = best

    # Also get current stake info if coldkey provided
    current_hotkey = None
    current_return = None
    if coldkey:
        positions = client.get_stakes(coldkey)
        for p in positions:
            if p.netuid == netuid:
                current_hotkey = p.hotkey
                current_return = p.current_return_per_1000
                break

    table = Table(title=f"Risk Level Comparison — Subnet {netuid}")
    table.add_column("Risk Level", style="cyan")
    table.add_column("Best Validator", style="blue")
    table.add_column("Ret/1K", justify="right", style="green")
    table.add_column("Trust", justify="right")
    table.add_column("Age", justify="right")
    table.add_column("Nominators", justify="right")
    table.add_column("Take", justify="right")

    for rl in risk_levels:
        best = results[rl]
        if best:
            table.add_row(
                rl,
                f"{best['hotkey'][:16]}...",
                fmt_ret(best['return_per_1000']),
                color_trust(best['trust']),
                f"{best['age_days']:.0f}d" if best['age_days'] else "-",
                str(best['nominators']),
                f"{best['take']*100:.1f}%",
            )
        else:
            table.add_row(rl, "[dim]No validator found[/dim]", "-", "-", "-", "-", "-")

    console.print(table)

    if current_hotkey and current_return is not None:
        console.print(f"\n[dim]Your current validator on subnet {netuid}: {current_hotkey[:16]}... "
                      f"(ret/1K: {fmt_ret(current_return)})[/dim]")

    if ctx.obj.get('output_format') == 'json':
        from .valhopper_logging import format_json_output
        data = {
            "netuid": netuid,
            "current_hotkey": current_hotkey,
            "current_return": current_return,
            "risk_levels": {rl: results[rl] for rl in risk_levels},
        }
        console.print(format_json_output("diff", data))
```

- [ ] **Step 2: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 3: Commit**
  ```bash
  git add -A && git commit -m "feat: add diff command for risk level comparison"
  ```

---

### Task 9: Add rollback support

**Files:**
- Modify: `src/valhopper/db.py`
- Modify: `src/valhopper/valhopper_transactions.py`
- Modify: `src/valhopper/valhopper_cli.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Add rollback state table to `db.py`**

Add to the `_init_schema` function in `db.py`:

```python
        CREATE TABLE IF NOT EXISTS rollback_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            coldkey TEXT NOT NULL,
            state_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_rollback_coldkey
            ON rollback_states(coldkey, created_at DESC);
```

Add helper functions to `db.py`:

```python
import json as json_lib


def save_rollback_state(
    conn: sqlite3.Connection,
    coldkey: str,
    positions: list,
) -> int:
    """Save current stake state before a move for potential rollback.

    Args:
        conn: SQLite connection
        coldkey: Coldkey SS58
        positions: List of StakePosition dicts (before the move)

    Returns:
        Row ID of the saved state
    """
    created_at = datetime.now().isoformat()
    state = [
        {
            "netuid": p.netuid,
            "origin_hotkey": p.hotkey,
            "stake_tao": p.stake_tao,
        }
        for p in positions
    ]
    cursor = conn.execute(
        "INSERT INTO rollback_states (created_at, coldkey, state_json) VALUES (?, ?, ?)",
        (created_at, coldkey, json_lib.dumps(state)),
    )
    conn.commit()
    return cursor.lastrowid


def get_last_rollback_state(conn: sqlite3.Connection, coldkey: str) -> Optional[dict]:
    """Get the most recent rollback state for a coldkey."""
    row = conn.execute(
        "SELECT id, created_at, state_json FROM rollback_states WHERE coldkey = ? ORDER BY id DESC LIMIT 1",
        (coldkey,),
    ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "created_at": row["created_at"], "state": json_lib.loads(row["state_json"])}
```

- [ ] **Step 2: Save rollback state before optimize execution**

In `valhopper_cli.py`, in the `optimize` command, before the execution loop (after validation and confirmation), add:

```python
from .db import _get_db, save_rollback_state

db_conn = _get_db()
rollback_id = save_rollback_state(db_conn, coldkey, validated_positions)
console.print(f"[dim]Rollback state saved (ID: {rollback_id}). Use 'vh rollback' to reverse.[/dim]")
db_conn.close()
```

- [ ] **Step 3: Add the `rollback` command**

```python
@cli.command()
@click.option('--last', is_flag=True, default=True, help='Rollback the most recent execution')
@click.pass_context
def rollback(ctx, last):
    """Reverse the most recent stake moves by moving stakes back to previous validators."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    wallet_name = ctx.obj.get('wallet_name')
    if not wallet_name:
        console.print("[red]Error:[/red] --wallet-name required for rollback execution")
        return

    from .db import _get_db, get_last_rollback_state

    db_conn = _get_db()
    state = get_last_rollback_state(db_conn, coldkey)

    if not state:
        console.print(f"[yellow]No rollback state found for {coldkey[:16]}...[/yellow]")
        db_conn.close()
        return

    console.print(Panel(
        f"[bold]Rollback State ID:[/bold] {state['id']}\n"
        f"[bold]Saved At:[/bold] {state['created_at']}\n"
        f"[bold]Positions:[/bold] {len(state['state'])}",
        title="[bold]Most Recent Rollback State[/bold]",
        border_style="yellow",
    ))

    # Show what would be rolled back
    client = BittensorClient(network=ctx.obj['network'])

    table = Table(title="Rollback Moves")
    table.add_column("Subnet", justify="right", style="cyan")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Current Validator", style="red")
    table.add_column("Rollback To", style="green")

    rollback_positions = []
    for entry in state['state']:
        # Find current position to know where stake is now
        current_positions = client.get_stakes(coldkey)
        for p in current_positions:
            if p.netuid == entry['netuid']:
                # The origin_hotkey is where we want to move back to
                rollback_pos = StakePosition(
                    hotkey=p.hotkey,  # current validator (where stake is now)
                    netuid=p.netuid,
                    stake_tao=p.stake_tao,
                    best_validator_hotkey=entry['origin_hotkey'],  # where to move back
                )
                rollback_positions.append(rollback_pos)
                table.add_row(
                    str(p.netuid),
                    f"{p.stake_tao:.4f}",
                    f"{p.hotkey[:12]}...",
                    f"{entry['origin_hotkey'][:12]}...",
                )
                break

    if not rollback_positions:
        console.print("[yellow]No matching current positions found for rollback.[/yellow]")
        db_conn.close()
        return

    console.print(table)

    if not click.confirm("\nProceed with rollback?"):
        console.print("[yellow]Cancelled.[/yellow]")
        db_conn.close()
        return

    try:
        wallet = load_wallet(
            wallet_name, ctx.obj.get('wallet_hotkey', 'default'), ctx.obj.get('wallet_path')
        )
    except Exception as e:
        console.print(f"[red]Wallet error:[/red] {e}")
        db_conn.close()
        return

    results = []
    for pos in rollback_positions:
        console.print(
            f"  Subnet {pos.netuid}: {pos.hotkey[:8]}... -> {pos.best_validator_hotkey[:8]}...",
            end=" ",
        )
        success, msg, details = execute_stake_move(client.subtensor, wallet, pos)
        status = "[green]OK[/green]" if success else f"[red]{msg[:80]}[/red]"
        console.print(status)
        results.append((pos, success, msg, details))

    format_transaction_results(results, console)
    log_path = write_transaction_log(results)
    if log_path:
        console.print(f"[dim]Transaction log: {log_path}[/dim]")

    db_conn.close()
```

- [ ] **Step 4: Add rollback table tests to `tests/test_db.py`**

Append to `tests/test_db.py`:

```python
from valhopper.db import save_rollback_state, get_last_rollback_state


def test_save_and_get_rollback_state():
    conn, path = _fresh_db()
    positions = [
        type("P", (), {"netuid": 1, "hotkey": "hk1", "stake_tao": 10.0})(),
        type("P", (), {"netuid": 2, "hotkey": "hk2", "stake_tao": 5.0})(),
    ]
    rid = save_rollback_state(conn, "cold1", positions)
    assert rid > 0

    state = get_last_rollback_state(conn, "cold1")
    assert state is not None
    assert state["id"] == rid
    assert len(state["state"]) == 2
    assert state["state"][0]["netuid"] == 1
    assert state["state"][0]["origin_hotkey"] == "hk1"
    _cleanup(conn, path)


def test_get_rollback_state_none():
    conn, path = _fresh_db()
    assert get_last_rollback_state(conn, "nonexistent") is None
    _cleanup(conn, path)
```

- [ ] **Step 5: Run all tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 6: Commit**
  ```bash
  git add -A && git commit -m "feat: add rollback command and pre-move state saving"
  ```

---

### Task 10: Add multi-coldkey support

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

- [ ] **Step 1: Add `--coldkey-file` option to the CLI group**

In the `cli` group function, add:

```python
@click.option('--coldkey-file', default=None,
              help='File with one coldkey SS58 per line (processes multiple coldkeys)')
```

And in the function body:
```python
ctx.obj['coldkey_file'] = coldkey_file
```

- [ ] **Step 2: Add a helper to load coldkeys from file**

In `valhopper_cli.py`, add:

```python
def _load_coldkeys(coldkey: str = None, coldkey_file: str = None) -> list[str]:
    """Load coldkeys from --coldkey or --coldkey-file."""
    keys = []
    if coldkey:
        keys.append(coldkey)
    if coldkey_file:
        path = os.path.expanduser(coldkey_file)
        if not os.path.isfile(path):
            console.print(f"[red]Coldkey file not found: {path}[/red]")
        else:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        keys.append(line)
    if not keys:
        console.print("[red]Please provide --coldkey or --coldkey-file[/red]")
    return keys
```

- [ ] **Step 3: Update `list_stakes` and `optimize` to iterate over multiple coldkeys**

For `list_stakes`, replace the coldkey check at the top:

```python
coldkeys = _load_coldkeys(ctx.obj.get('coldkey'), ctx.obj.get('coldkey_file'))
if not coldkeys:
    return
```

Then wrap the existing logic in a loop:

```python
for coldkey in coldkeys:
    # ... existing list_stakes logic ...
```

For `optimize`, same pattern:

```python
coldkeys = _load_coldkeys(ctx.obj.get('coldkey'), ctx.obj.get('coldkey_file'))
if not coldkeys:
    return

for coldkey in coldkeys:
    # ... existing optimize logic ...
    console.print(f"\n[bold]--- Coldkey: {coldkey[:16]}... ---[/bold]\n")
    # ... rest of optimize for this coldkey ...
```

- [ ] **Step 4: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 5: Commit**
  ```bash
  git add -A && git commit -m "feat: add --coldkey-file for multi-coldkey support"
  ```

---

### Task 11: Add `subnets` command

**Files:**
- Modify: `src/valhopper/valhopper_cli.py`

The README already documents a `subnets` command but it doesn't exist in the code.

- [ ] **Step 1: Add the `subnets` command**

```python
@cli.command()
@click.pass_context
def subnets(ctx):
    """List all available subnets with names and prices."""
    client = BittensorClient(network=ctx.obj['network'])

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Fetching subnet info...", total=None)

        all_netuids = client.subtensor.get_all_subnet_netuids()

    table = Table(title="Bittensor Subnets")
    table.add_column("Netuid", justify="right", style="cyan")
    table.add_column("Symbol", style="blue")
    table.add_column("Price (TAO)", justify="right", style="green")
    table.add_column("Emission", justify="right")

    for netuid in sorted(all_netuids):
        try:
            meta = client.get_metagraph(netuid)
            symbol = get_token_symbol(netuid)
            price = float(meta.pool.moving_price) if hasattr(meta, 'pool') else 0
            emission = sum(float(e) for e in meta.emission) if hasattr(meta, 'emission') else 0

            table.add_row(
                str(netuid),
                symbol,
                f"{price:.6f}" if price > 0 else "-",
                f"{emission:.4f}" if emission > 0 else "-",
            )
        except Exception:
            table.add_row(str(netuid), get_token_symbol(netuid), "-", "-")

    console.print(table)

    if ctx.obj.get('output_format') == 'json':
        from .valhopper_logging import format_json_output
        data = {"subnets": []}
        for netuid in sorted(all_netuids):
            try:
                meta = client.get_metagraph(netuid)
                data["subnets"].append({
                    "netuid": netuid,
                    "symbol": get_token_symbol(netuid),
                    "price": float(meta.pool.moving_price) if hasattr(meta, 'pool') else 0,
                })
            except Exception:
                data["subnets"].append({"netuid": netuid, "symbol": get_token_symbol(netuid), "price": 0})
        console.print(format_json_output("subnets", data))
```

- [ ] **Step 2: Run tests**
  Run: `pytest tests/ -v`
  Expected: All pass

- [ ] **Step 3: Commit**
  ```bash
  git add -A && git commit -m "feat: add subnets command"
  ```

---

### Task 12: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add documentation for all new features**

Add/update the following sections in README.md:

1. **Configuration** — Document `~/.valhopper/config.yaml`, the `--config` flag, and show a sample config file with all options including `discord_webhook_url`, `min_improvement`, and `format`.

2. **Automated Rebalancing** — Document the wrapper script pattern:
   ```bash
   #!/bin/bash
   # rebalance.sh — schedule this with cron, systemd timer, or run in tmux
   valhopper --coldkey YOUR_KEY optimize --dry-run --min-improvement 20
   ```

3. **New Commands** — Document each new command with usage examples:
   - `vh snapshot` — record yield data
   - `vh history <netuid>` — view yield trends
   - `vh portfolio` — cross-subnet overview
   - `vh diff <netuid>` — compare risk levels
   - `vh watch --once --discord` — one-shot monitoring with Discord alert
   - `vh rollback --last` — reverse recent moves
   - `vh subnets` — list all subnets

4. **Multi-Coldkey** — Document `--coldkey-file coldkeys.txt`

5. **JSON Output** — Document `--format json` with example

6. **Optimize Options** — Document `--min-improvement`, `--split N`, fee estimates, slippage warnings

7. **Discord Notifications** — Document `discord_webhook_url` in config + `--discord` flag on watch

8. **Changelog** — Add v0.2.0 entry listing all new features

- [ ] **Step 2: Commit**
  ```bash
  git add -A && git commit -m "docs: update README for v0.2.0 features"
  ```

"""Transaction execution for ValHopper."""

import os
import time

import click
import bittensor

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]


def load_wallet(wallet_name, wallet_hotkey, wallet_path):
    """Load bittensor wallet with hotkey.

    Args:
        wallet_name: Name of the wallet directory
        wallet_hotkey: Name of the hotkey (usually 'default')
        wallet_path: Base path to wallet directory

    Returns:
        Wallet instance

    Raises:
        UsageError: If wallet_name is not provided
        BadParameter: If wallet or hotkey not found on disk
    """
    if not wallet_name:
        raise click.UsageError(
            "--wallet-name required for live execution. "
            "Use --dry-run to preview."
        )

    # Expand ~ in path before validation
    expanded_path = os.path.expanduser(wallet_path)
    wallet_dir = os.path.join(expanded_path, wallet_name)

    # Pre-flight: verify wallet directory exists before calling SDK
    if not os.path.isdir(wallet_dir):
        raise click.BadParameter(
            f"Wallet directory not found: {wallet_dir}\n"
            f"Check --wallet-name and --wallet-path. "
            f"Path defaults to ~/.bittensor/wallets/"
        )

    coldkey_path = os.path.join(wallet_dir, "coldkey")
    if not os.path.isfile(coldkey_path) and not os.path.isfile(coldkey_path + ".json"):
        raise click.BadParameter(
            f"coldkey file not found in {wallet_dir}\n"
            f"Expected: {coldkey_path}"
        )

    hotkey_dir = os.path.join(wallet_dir, "hotkeys")
    hotkey_path = os.path.join(hotkey_dir, wallet_hotkey)
    if not os.path.isfile(hotkey_path) and not os.path.isfile(hotkey_path + ".json"):
        # Try listing available hotkeys to help the user
        available = []
        if os.path.isdir(hotkey_dir):
            available = [f for f in os.listdir(hotkey_dir)
                         if not f.startswith('.') and os.path.isfile(os.path.join(hotkey_dir, f))]
        hint = f"Available hotkeys: {', '.join(available)}" if available else "No hotkeys found in wallet."
        raise click.BadParameter(
            f"Hotkey '{wallet_hotkey}' not found in {wallet_dir}/hotkeys/\n"
            f"{hint}"
        )

    # Now safely create the Wallet object
    try:
        wallet = bittensor.Wallet(
            name=wallet_name,
            hotkey=wallet_hotkey,
            path=wallet_path,
        )
    except TypeError as e:
        raise click.BadParameter(
            f"Failed to create wallet object: {e}\n"
            f"This may be a bittensor SDK version mismatch. "
            f"Check your bittensor installation with: pip show bittensor"
        )

    return wallet


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
                if hasattr(response, 'transaction_tao_fee') and response.transaction_tao_fee:
                    details['tao_fee'] = response.transaction_tao_fee
                if hasattr(response, 'transaction_alpha_fee') and response.transaction_alpha_fee:
                    details['alpha_fee'] = response.transaction_alpha_fee
                if hasattr(response, 'data') and response.data:
                    details.update(response.data)
                parts = []
                if hasattr(response, 'extrinsic_receipt') and response.extrinsic_receipt:
                    receipt = response.extrinsic_receipt
                    if hasattr(receipt, 'block_hash'):
                        parts.append(f"block: {str(receipt.block_hash)[:16]}...")
                    if hasattr(receipt, 'block_number'):
                        parts.append(f"height: {receipt.block_number}")
                msg = "Success"
                if parts:
                    msg += f" ({', '.join(parts)})"
                if details.get('tao_fee'):
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
    retryable_patterns = [
        "rate limit", "timeout", "connection", "network",
        "busy", "temporarily", "503", "429", "too many", "pool",
    ]
    lower = error_msg.lower()
    return any(p in lower for p in retryable_patterns)


def estimate_stake_move_fee(subtensor, position) -> dict:
    try:
        if hasattr(subtensor, "get_transfer_fee"):
            fee = subtensor.get_transfer_fee()
            return {"estimated_tao_fee": float(fee)}
    except Exception:
        pass
    return {"estimated_tao_fee": 0.001}


def format_transaction_results(results, console):
    """Format transaction results for display.

    Args:
        results: List of (position, success, message, details) tuples
        console: Rich console instance
    """
    from rich.table import Table

    table = Table(title="Transaction Results")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Subnet", justify="right")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("From", style="dim")
    table.add_column("To", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    for i, (pos, success, msg, details) in enumerate(results, 1):
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        from_addr = pos.hotkey[:12] + "..."
        to_addr = pos.best_validator_hotkey[:12] + "..."
        # Truncate long error messages for the table
        detail_text = msg if len(msg) <= 60 else msg[:57] + "..."
        table.add_row(
            str(i),
            str(pos.netuid),
            f"{pos.stake_tao:.4f} {pos.token_symbol}",
            from_addr,
            to_addr,
            status,
            detail_text,
        )

    console.print(table)

    success_count = sum(1 for _, s, _, _ in results if s)
    fail_count = len(results) - success_count

    if fail_count == 0:
        console.print(f"\n[bold green]All {success_count} transaction(s) succeeded[/bold green]")
        # Show total fees if available
        total_tao_fee = sum(
            float(details.get('tao_fee', 0))
            for _, s, _, details in results if s and 'tao_fee' in details
        )
        if total_tao_fee > 0:
            console.print(f"[dim]Total TAO fees: {total_tao_fee:.6f}[/dim]")
    else:
        console.print(f"\n[bold]{success_count} succeeded, {fail_count} failed[/bold]")
        # Print full error messages for failed transactions
        for pos, success, msg, details in results:
            if not success:
                console.print(f"  [red]Subnet {pos.netuid}:[/red] {msg}")

    return success_count == len(results)

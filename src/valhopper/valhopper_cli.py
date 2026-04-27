#!/usr/bin/env python3
"""ValHopper - Bittensor Alpha Token Stake Optimizer

A CLI tool to help Alpha token holders maximize their yields by
moving stakes to the most profitable validators.
"""

import os
import json as json_lib
import logging

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
from .valhopper_logging import write_transaction_log, format_json_output

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('valhopper')

console = Console()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
@click.option('--network', default='finney', help='Bittensor network')
@click.option('--coldkey', help='Coldkey SS58 address')
@click.option('--wallet-name', default=None, help='Wallet name for transactions')
@click.option('--wallet-hotkey', default='default', help='Hotkey name in wallet')
@click.option('--wallet-path', default='~/.bittensor/wallets', help='Wallet path')
@click.option('--risk-level',
    type=click.Choice(['conservative', 'moderate', 'aggressive']),
    default='moderate',
    help='Risk level for validator selection (default: moderate)')
@click.option('--format', 'output_format',
    type=click.Choice(['table', 'json']),
    default='table',
    help='Output format (default: table)')
@click.pass_context
def cli(ctx, network, coldkey, wallet_name, wallet_hotkey, wallet_path, risk_level, output_format):
    """ValHopper - Optimize your Bittensor Alpha token stakes."""
    os.environ['BT_NO_PARSE_CLI_ARGS'] = '1'
    ctx.ensure_object(dict)
    ctx.obj['network'] = network
    ctx.obj['coldkey'] = coldkey
    ctx.obj['wallet_name'] = wallet_name
    ctx.obj['wallet_hotkey'] = wallet_hotkey
    ctx.obj['wallet_path'] = wallet_path
    ctx.obj['risk_level'] = risk_level
    ctx.obj['output_format'] = output_format


# ---------------------------------------------------------------------------
# list-stakes
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def list_stakes(ctx):
    """List all stakes with return rates and best validator info."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    client = BittensorClient(network=ctx.obj['network'])
    risk_level = ctx.obj.get('risk_level', 'moderate')

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Fetching stakes...", total=None)
        positions = client.get_stakes(coldkey, risk_level)

    if not positions:
        if ctx.obj.get('output_format') == 'json':
            console.print(format_json_output("list-stakes", {
                "coldkey": coldkey, "risk_level": risk_level, "positions": [],
            }))
        else:
            console.print(Panel(
                f"[yellow]No stakes found for coldkey:[/yellow]\n[cyan]{coldkey}[/cyan]"
            ))
        return

    if ctx.obj.get('output_format') == 'json':
        console.print(format_json_output("list-stakes", {
            "coldkey": coldkey,
            "risk_level": risk_level,
            "positions": [p.to_dict() for p in positions],
        }))
        return

    table = Table(title=f"Stakes for {coldkey[:16]}...", show_lines=True)
    table.add_column("Subnet", justify="right", style="cyan")
    table.add_column("Stake", justify="right", style="green")
    table.add_column("Current\nDaily α", justify="right")
    table.add_column("Best\nDaily α", justify="right", style="yellow")
    table.add_column("Δ Daily α", justify="right", style="magenta")
    table.add_column("Best Validator", style="dim")
    table.add_column("Cur\nTrust", justify="right")
    table.add_column("Best\nTrust", justify="right")
    table.add_column("Val Age", justify="right")

    for p in sorted(positions, key=lambda x: x.stake_tao, reverse=True):
        best_validator = (client.get_validator_identity(p.best_validator_hotkey)
                          if p.best_validator_hotkey else "-")

        best_daily_str = fmt_ret(p.new_daily_earn)
        if p.best_validator_return <= p.current_validator_return:
            best_daily_str = f"[dim]{best_daily_str}[/dim]"

        delta = p.new_daily_earn - p.current_daily_earn
        if delta > 0:
            delta_str = f"[green]+{fmt_ret(delta)}[/green]"
        elif delta < 0:
            delta_str = f"[red]{fmt_ret(delta)}[/red]"
        else:
            delta_str = "-"

        table.add_row(
            str(p.netuid),
            f"{p.stake_tao:.4f} {p.token_symbol}",
            fmt_ret(p.current_daily_earn),
            best_daily_str,
            delta_str,
            f"[dim]{best_validator}[/dim]" if best_validator != "-" else "-",
            color_trust(p.current_validator_trust),
            color_trust(p.best_validator_trust),
            color_age(p.best_validator_age_days),
        )

    console.print(table)
    console.print(f"[dim]Risk level: {risk_level}[/dim]")
    console.print("[dim]Daily α = your wallet's daily earnings (after validator take)[/dim]")


# ---------------------------------------------------------------------------
# optimize
# ---------------------------------------------------------------------------

@cli.command()
@click.option('--dry-run', is_flag=True, default=False,
              help='Simulate without executing (default: live execution)')
@click.option('--risk-level',
              type=click.Choice(['conservative', 'moderate', 'aggressive']),
              default=None,
              help='Override risk level for validator selection')
@click.option('--max-stake-per-move', type=float, default=None,
              help='Maximum stake amount per move (optional filter)')
@click.pass_context
def optimize(ctx, dry_run, risk_level, max_stake_per_move):
    """Move all stakes to the most profitable validators."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    # Command-level risk_level overrides global, fallback to global
    effective_risk = risk_level or ctx.obj.get('risk_level', 'moderate')

    client = BittensorClient(network=ctx.obj['network'])

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Analyzing stakes...", total=None)
        positions = client.get_stakes(coldkey, effective_risk)

    if not positions:
        console.print(Panel(
            f"[yellow]No stakes found for coldkey:[/yellow]\n[cyan]{coldkey}[/cyan]"
        ))
        return

    console.print(
        f"Found [cyan]{len(positions)}[/cyan] stake position(s) "
        f"[dim](risk level: {effective_risk})[/dim]"
    )

    movable_positions = [
        p for p in positions
        if p.best_validator_hotkey
        and p.hotkey != p.best_validator_hotkey
        and p.return_delta > 0
    ]

    if not movable_positions:
        if ctx.obj.get('output_format') == 'json':
            console.print(format_json_output("optimize", {
                "coldkey": coldkey, "risk_level": effective_risk,
                "dry_run": dry_run, "positions_to_move": [],
                "total_stake_to_move": 0, "total_daily_gain": 0,
            }))
        else:
            console.print(Panel(
                f"[green]All {len(positions)} stake(s) are already "
                f"with the best validators![/green]"
            ))
        return

    # Apply max stake filter if specified
    if max_stake_per_move is not None:
        movable_positions = [
            p for p in movable_positions
            if p.stake_tao <= max_stake_per_move
        ]
        if not movable_positions:
            console.print(f"[yellow]No positions under {max_stake_per_move} TAO stake[/yellow]")
            return

    total_stake_to_move = 0
    total_daily_gain = 0

    for p in movable_positions:
        total_stake_to_move += p.stake_tao
        total_daily_gain += p.potential_additional_daily

    if ctx.obj.get('output_format') == 'json':
        console.print(format_json_output("optimize", {
            "coldkey": coldkey,
            "risk_level": effective_risk,
            "dry_run": dry_run,
            "positions_to_move": [p.to_dict() for p in movable_positions],
            "total_stake_to_move": total_stake_to_move,
            "total_daily_gain": total_daily_gain,
        }))
        if dry_run:
            return
        # If not dry_run, continue to live execution
    else:
        table = Table(title="Planned Stake Moves")
        table.add_column("Subnet", justify="right", style="cyan")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("From Validator", style="red")
        table.add_column("To Validator", style="green")
        table.add_column("Current\nDaily α", justify="right")
        table.add_column("Best\nDaily α", justify="right", style="yellow")
        table.add_column("Δ Daily α", justify="right", style="magenta")
        table.add_column("Cur\nTrust", justify="right")
        table.add_column("Best\nTrust", justify="right")
        table.add_column("Val Age", justify="right")
        table.add_column("Noms", justify="right")
        table.add_column("Val Take", justify="right")

        for p in movable_positions:
            from_val = client.get_validator_identity(p.hotkey)
            to_val = client.get_validator_identity(p.best_validator_hotkey)

            delta = p.new_daily_earn - p.current_daily_earn
            if delta >= 0:
                delta_str = f"[green]+{fmt_ret(delta)}[/green]"
            else:
                delta_str = f"[red]{fmt_ret(delta)}[/red]"

            table.add_row(
                str(p.netuid),
                f"{p.stake_tao:.4f} {p.token_symbol}",
                f"[red]{from_val}[/red]",
                f"[green]{to_val}[/green]",
                fmt_ret(p.current_daily_earn),
                f"[yellow]{fmt_ret(p.new_daily_earn)}[/yellow]",
                delta_str,
                color_trust(p.current_validator_trust),
                color_trust(p.best_validator_trust),
                color_age(p.best_validator_age_days),
                str(p.best_validator_nominators),
                f"{p.best_validator_take*100:.2f}%",
            )

        console.print(table)

        avg_daily_gain = total_daily_gain / len(movable_positions)

        console.print(Panel(
            f"[bold]Total Stake to Move:[/bold] {total_stake_to_move:.4f} worth of tokens\n"
            f"[bold]Avg Daily Improvement:[/bold] +{fmt_ret(avg_daily_gain)} α/day\n"
            f"[bold]Additional Daily Yield:[/bold] +{total_daily_gain:.4f} alpha\n"
            f"[bold]Additional Monthly Yield:[/bold] +{total_daily_gain * 30:.2f} alpha",
            title="[bold]Optimization Summary[/bold]",
            border_style="green"
        ))
        console.print("[dim]Daily α = your wallet's daily earnings (after validator take)[/dim]")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No actual transactions will be made.[/yellow]")
            console.print("[dim]Remove --dry-run flag to execute actual transactions.[/dim]")
            return

    # Live execution
    wallet_name = ctx.obj.get('wallet_name')
    wallet_hotkey = ctx.obj.get('wallet_hotkey', 'default')
    wallet_path = ctx.obj.get('wallet_path', '~/.bittensor/wallets')

    if not wallet_name:
        console.print("[red]Error:[/red] --wallet-name required for live execution")
        console.print("[dim]Example: --wallet-name mywallet --wallet-hotkey default[/dim]")
        return

    console.print("\n[bold red]SECURITY WARNING[/bold red]")
    console.print("This will move actual stake between validators.")
    console.print("Transactions are IRREVERSIBLE.\n")

    if not click.confirm("Proceed?"):
        console.print("[yellow]Cancelled.[/yellow]")
        return

    try:
        wallet = load_wallet(wallet_name, wallet_hotkey, wallet_path)
    except Exception as e:
        console.print(f"[red]Wallet error:[/red] {e}")
        return

    # CRITICAL: Verify wallet coldkey matches --coldkey
    # move_stake always uses wallet.coldkeypub as origin/destination coldkey.
    # If they mismatch, the displayed positions (from --coldkey) would not match
    # the actual positions being moved (from wallet), causing wrong stake to move.
    wallet_coldkey = wallet.coldkeypub.ss58_address
    if coldkey != wallet_coldkey:
        console.print("[bold red]SECURITY: Coldkey mismatch![/bold red]")
        console.print(f"  --coldkey:          {coldkey}")
        console.print(f"  Wallet coldkey:     {wallet_coldkey}")
        console.print("The wallet's coldkey must match --coldkey.")
        console.print("move_stake uses the wallet coldkey, so a mismatch would move")
        console.print("different stake than what was shown in the preview.")
        return

    console.print(f"\n[bold]Refreshing data before execution...[/bold]")
    client.refresh_caches()

    # Re-validate validators still active (race condition protection)
    validated_positions = []
    skipped = 0
    for pos in movable_positions:
        meta = client.get_metagraph(pos.netuid)
        if pos.best_validator_hotkey not in meta.hotkeys:
            console.print(
                f"[yellow]⚠ Skipping subnet {pos.netuid}: "
                f"best validator deregistered since analysis[/yellow]"
            )
            skipped += 1
            continue
        validated_positions.append(pos)

    if not validated_positions:
        console.print("[red]No validators valid for stake moves after re-validation.[/red]")
        return

    if skipped > 0:
        console.print(f"[dim]Skipped {skipped} position(s) due to validator changes[/dim]")

    console.print(f"\nExecuting {len(validated_positions)} stake moves...")

    results = []
    for pos in validated_positions:
        console.print(
            f"  Subnet {pos.netuid}: {pos.hotkey[:8]}... → "
            f"{pos.best_validator_hotkey[:8]}...",
            end=" "
        )
        success, msg, details = execute_stake_move(client.subtensor, wallet, pos)
        status = "[green]OK[/green]" if success else f"[red]{msg[:80]}[/red]"
        console.print(status)
        results.append((pos, success, msg, details))

        format_transaction_results(results, console)

        log_path = write_transaction_log(results)
        if log_path:
            console.print(f"[dim]Transaction log: {log_path}[/dim]")


# ---------------------------------------------------------------------------
# top-validators
# ---------------------------------------------------------------------------

@cli.command()
@click.argument('netuid', type=int)
@click.option('--risk-level',
              type=click.Choice(['conservative', 'moderate', 'aggressive']),
              default=None,
              help='Filter validators by risk level')
@click.pass_context
def top_validators(ctx, netuid, risk_level):
    """Show top validators for a subnet by return rate, filtered by risk level."""
    effective_risk = risk_level or ctx.obj.get('risk_level', 'moderate')

    client = BittensorClient(network=ctx.obj['network'])

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Fetching validators...", total=None)
        delegates = client.get_delegates()
        subnet_delegates = [
            d for d in delegates
            if netuid in d.registrations
        ]
        # Apply risk filters
        filtered = client._apply_risk_filters(subnet_delegates, netuid, effective_risk)

        # Compute per-subnet returns
        scored = []
        for d, risk in filtered:
            ret = client._compute_return_per_1k(d.hotkey_ss58, netuid)
            if ret > 0:
                scored.append((d, risk, ret))

        scored.sort(key=lambda x: x[2], reverse=True)

    if not scored:
        if ctx.obj.get('output_format') == 'json':
            console.print(format_json_output("top-validators", {
                "netuid": netuid, "risk_level": effective_risk, "validators": [],
            }))
        else:
            console.print(
                f"[yellow]No validators found for subnet {netuid} "
                f"at {effective_risk} risk level[/yellow]"
            )
        return

    if ctx.obj.get('output_format') == 'json':
        console.print(format_json_output("top-validators", {
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
        }))
        return

        symbol = get_token_symbol(netuid)
        table = Table(title=f"Top Validators on Subnet {netuid} [{effective_risk}]")
        table.add_column("Rank", justify="right", style="cyan")
        table.add_column("Hotkey", style="blue")
        table.add_column(f"Ret/1K {symbol}", justify="right", style="green")
        table.add_column("Trust", justify="right")
        table.add_column("Val Age", justify="right")
        table.add_column("Noms", justify="right")
        table.add_column("Val Take", justify="right")

        for i, (d, risk, ret) in enumerate(scored[:20], 1):
            table.add_row(
                str(i),
                f"{d.hotkey_ss58[:20]}...",
                fmt_ret(ret),
        color_trust(risk['trust']),
        color_age(risk['age_days']),
                str(risk['nominators']),
                f"{d.take*100:.2f}%",
            )

    console.print(table)
    console.print(f"[dim]Ret/1K = native tokens earned per 1000 staked per day (τ for root, α for alpha subnets)[/dim]")


if __name__ == '__main__':
    cli(obj={})

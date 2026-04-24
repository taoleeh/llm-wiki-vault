#!/usr/bin/env python3
"""
ValHopper - Bittensor Alpha Token Stake Optimizer
A CLI tool to help Alpha token holders maximize their yields by moving stakes to the most profitable validators.
"""

import os
os.environ['BT_NO_PARSE_CLI_ARGS'] = '1'

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional
import bittensor
from bittensor import Balance

console = Console()


def get_token_symbol(netuid: int) -> str:
    """Get the token symbol for a subnet."""
    symbols = {0: "τ", 1: "α", 2: "β", 3: "γ", 4: "δ", 5: "ε"}
    return symbols.get(netuid, f"S{netuid}")


class StakePosition:
    """Represents a stake position with percentage-based returns calculation."""

    def __init__(self, hotkey: str, netuid: int, stake: Balance, 
                 current_validator_return: float = 0.0, 
                 best_validator_return: float = 0.0,
                 best_validator_hotkey: str = ""):
        self.hotkey = hotkey
        self.netuid = netuid
        self.stake = stake
        self.current_validator_return = current_validator_return
        self.best_validator_return = best_validator_return
        self.best_validator_hotkey = best_validator_hotkey

    @property
    def token_symbol(self) -> str:
        return get_token_symbol(self.netuid)

    @property
    def current_daily_yield_percent(self) -> float:
        """Current daily yield as percentage."""
        return (self.current_validator_return / 1000) * 100

    @property
    def best_daily_yield_percent(self) -> float:
        """Best validator daily yield as percentage."""
        return (self.best_validator_return / 1000) * 100

    @property
    def current_apy_percent(self) -> float:
        """Current APY (daily × 365)."""
        return self.current_daily_yield_percent * 365

    @property
    def best_apy_percent(self) -> float:
        """Best validator APY."""
        return self.best_daily_yield_percent * 365

    @property
    def apy_gain_percent(self) -> float:
        """APY improvement percentage points."""
        return self.best_apy_percent - self.current_apy_percent

    @property
    def potential_additional_daily(self) -> float:
        """Potential additional daily returns in TAO if moved to best validator."""
        return (self.stake.tao / 1000) * (self.best_validator_return - self.current_validator_return)


class BittensorClient:
    """Client for interacting with the Bittensor blockchain."""

    def __init__(self, network: str = "finney"):
        self.network = network
        self.subtensor = bittensor.Subtensor(network=network)

    def get_delegates(self) -> list:
        return self.subtensor.get_delegates()

    def get_validator_identity(self, hotkey: str) -> str:
        try:
            identity = self.subtensor.get_identity(hotkey_ss58=hotkey)
            if identity and identity.name:
                return f"{identity.name.strip()} ({hotkey[:8]}...)"
        except Exception:
            pass
        return f"{hotkey[:16]}..."

    def get_best_validator_for_subnet(self, netuid: int) -> Optional[dict]:
        """Find the validator with highest return_per_1000 for a subnet."""
        delegates = self.get_delegates()
        subnet_delegates = [d for d in delegates if netuid in d.registrations and d.return_per_1000.tao > 0]
        if not subnet_delegates:
            return None
        best = max(subnet_delegates, key=lambda x: x.return_per_1000.tao)
        return {
            'hotkey': best.hotkey_ss58,
            'return_per_1000': best.return_per_1000.tao,
            'take': best.take
        }

    def get_validator_return(self, hotkey: str, netuid: int) -> float:
        """Get return_per_1000 for a specific validator on a subnet."""
        for d in self.get_delegates():
            if d.hotkey_ss58 == hotkey and netuid in d.registrations:
                return d.return_per_1000.tao
        return 0.0

    def get_stakes(self, coldkey_ss58: str) -> list[StakePosition]:
        """Get all stake positions for a coldkey."""
        try:
            stake_infos = self.subtensor.get_stake_info_for_coldkey(coldkey_ss58)
        except Exception as e:
            console.print(f"[red]Error fetching stakes: {e}[/red]")
            return []
            
        positions = []
        for si in stake_infos:
            if si.stake.tao > 0:
                current_return = self.get_validator_return(si.hotkey_ss58, si.netuid)
                best_validator = self.get_best_validator_for_subnet(si.netuid)
                position = StakePosition(
                    hotkey=si.hotkey_ss58,
                    netuid=si.netuid,
                    stake=si.stake,
                    current_validator_return=current_return,
                    best_validator_return=best_validator['return_per_1000'] if best_validator else 0,
                    best_validator_hotkey=best_validator['hotkey'] if best_validator else ""
                )
                positions.append(position)
        return positions


@click.group()
@click.option('--network', default='finney', help='Bittensor network')
@click.option('--coldkey', help='Coldkey SS58 address')
def cli(ctx, network, coldkey):
    """ValHopper - Optimize your Bittensor Alpha token stakes."""
    ctx.ensure_object(dict)
    ctx.obj['network'] = network
    ctx.obj['coldkey'] = coldkey


@cli.command()
@click.pass_context
def list_stakes(ctx):
    """List all stakes with percentage returns and APY."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    client = BittensorClient(network=ctx.obj['network'])

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Fetching stakes...", total=None)
        positions = client.get_stakes(coldkey)

    if not positions:
        console.print(Panel(f"[yellow]No stakes found for coldkey:[/yellow]\n[cyan]{coldkey}[/cyan]"))
        return

    table = Table(title=f"Stakes for {coldkey[:16]}...", show_lines=True)
    table.add_column("Subnet", justify="right", style="cyan")
    table.add_column("Stake", justify="right", style="green")
    table.add_column("Current\nDaily %", justify="right")
    table.add_column("Best\nDaily %", justify="right", style="yellow")
    table.add_column("Current\nAPY %", justify="right")
    table.add_column("Best\nAPY %", justify="right", style="yellow")
    table.add_column("APY\nGain %", justify="right", style="magenta")
    table.add_column("Best Validator", style="dim")

    for p in sorted(positions, key=lambda x: x.stake.tao, reverse=True):
        best_validator = client.get_validator_identity(p.best_validator_hotkey) if p.best_validator_hotkey else "-"
        def fmt_pct(val):
            return f"{val:.4f}%" if val else "[dim]N/A[/dim]"
        
        best_daily_str = fmt_pct(p.best_daily_yield_percent)
        if p.best_validator_return <= p.current_validator_return:
            best_daily_str = f"[dim]{best_daily_str}[/dim]"
        
        best_apy_str = fmt_pct(p.best_apy_percent)
        if p.best_apy_percent <= p.current_apy_percent:
            best_apy_str = f"[dim]{best_apy_str}[/dim]"
        
        apy_gain_str = f"[bold magenta]+{p.apy_gain_percent:.4f}%[/bold magenta]" if p.apy_gain_percent > 0 else "-"

        table.add_row(
            str(p.netuid),
            f"{p.stake.tao:.4f} {p.token_symbol}",
            fmt_pct(p.current_daily_yield_percent),
            best_daily_str,
            fmt_pct(p.current_apy_percent),
            best_apy_str,
            apy_gain_str,
            f"[dim]{best_validator}[/dim]" if best_validator != "-" else "-"
        )

    console.print(table)


@cli.command()
@click.option('--dry-run', is_flag=True, default=True, help='Simulate without executing')
@click.pass_context
def optimize(ctx, dry_run):
    """Move all stakes to the most profitable validators."""
    coldkey = ctx.obj.get('coldkey')
    if not coldkey:
        console.print("[red]Please provide --coldkey[/red]")
        return

    client = BittensorClient(network=ctx.obj['network'])

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Analyzing stakes...", total=None)
        positions = client.get_stakes(coldkey)

    if not positions:
        console.print(Panel(f"[yellow]No stakes found for coldkey:[/yellow]\n[cyan]{coldkey}[/cyan]"))
        return

    console.print(f"Found [cyan]{len(positions)}[/cyan] stake position(s)")

    movable_positions = [p for p in positions if p.best_validator_hotkey and p.hotkey != p.best_validator_hotkey]

    if not movable_positions:
        console.print(Panel(f"[green]All {len(positions)} stake(s) are already with the best validators![/green]"))
        return

    def fmt_pct_opt(val):
        return f"{val:.4f}%" if val else "[dim]N/A[/dim]"

    table = Table(title="Planned Stake Moves")
    table.add_column("Subnet", justify="right", style="cyan")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("From Validator", style="red")
    table.add_column("To Validator", style="green")
    table.add_column("Current APY %", justify="right")
    table.add_column("New APY %", justify="right", style="yellow")
    table.add_column("APY Δ %", justify="right", style="magenta")

    total_stake_to_move = 0
    total_daily_gain = 0
    total_apy_improvement = 0

    for p in movable_positions:
        total_stake_to_move += p.stake.tao
        total_daily_gain += p.potential_additional_daily
        total_apy_improvement += p.apy_gain_percent

        from_val = client.get_validator_identity(p.hotkey)
        to_val = client.get_validator_identity(p.best_validator_hotkey)
        table.add_row(
            str(p.netuid),
            f"{p.stake.tao:.4f} {p.token_symbol}",
            f"[red]{from_val}[/red]",
            f"[green]{to_val}[/green]",
            fmt_pct_opt(p.current_apy_percent),
            f"[yellow]{fmt_pct_opt(p.best_apy_percent)}[/yellow]",
            f"[magenta]+{p.apy_gain_percent:.4f}%[/magenta]"
        )

    console.print(table)
    
    avg_apy_improvement = total_apy_improvement / len(movable_positions)
    console.print(Panel(
        f"[bold]Total Stake to Move:[/bold] {total_stake_to_move:.4f} worth of tokens\n"
        f"[bold]Average APY Improvement:[/bold] +{avg_apy_improvement:.2f}%\n"
        f"[bold]Additional Daily Yield:[/bold] +{total_daily_gain:.4f} τ (TAO equiv)\n"
        f"[bold]Additional Monthly Yield:[/bold] +{total_daily_gain * 30:.2f} τ (TAO equiv)",
        title="[bold]Optimization Summary[/bold]",
        border_style="yellow"
    ))

    if dry_run:
        console.print("\n[yellow]DRY RUN - No actual transactions will be made.[/yellow]")
        console.print("[dim]Remove --dry-run flag to execute actual transactions.[/dim]")
        return

    console.print("\n[yellow]Live transactions require wallet configuration (not implemented in this version).[/yellow]")


@cli.command()
@click.argument('netuid', type=int)
@click.pass_context
def top_validators(ctx, netuid):
    """Show top validators for a subnet by APY."""
    client = BittensorClient(network=ctx.obj['network'])
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Fetching validators...", total=None)
        delegates = client.get_delegates()
        subnet_delegates = [d for d in delegates if netuid in d.registrations and d.return_per_1000.tao > 0]
        subnet_delegates.sort(key=lambda x: x.return_per_1000.tao, reverse=True)

    if not subnet_delegates:
        console.print(f"[yellow]No validators found for subnet {netuid}[/yellow]")
        return

    symbol = get_token_symbol(netuid)
    table = Table(title=f"Top Validators on Subnet {netuid}")
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Hotkey", style="blue")
    table.add_column(f"Return/1000 {symbol}", justify="right", style="green")
    table.add_column("Daily %", justify="right")
    table.add_column("APY %", justify="right", style="yellow")

    for i, d in enumerate(subnet_delegates[:20], 1):
        daily_pct = (d.return_per_1000.tao / 1000) * 100
        apy_pct = daily_pct * 365
        table.add_row(
            str(i),
            f"{d.hotkey_ss58[:20]}...",
            f"{d.return_per_1000.tao:.2f} {symbol}",
            f"{daily_pct:.4f}%",
            f"{apy_pct:.2f}%"
        )

    console.print(table)


if __name__ == '__main__':
    cli(obj={})

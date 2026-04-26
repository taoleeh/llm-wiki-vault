#!/usr/bin/env python3
"""ValHopper - Bittensor Alpha Token Stake Optimizer

A CLI tool to help Alpha token holders maximize their yields by
moving stakes to the most profitable validators.
"""

import os
import time
import logging
import enum
os.environ['BT_NO_PARSE_CLI_ARGS'] = '1'

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional

import bittensor
from bittensor import Balance
from .valhopper_transactions import load_wallet, execute_stake_move, format_transaction_results
from .valhopper_logging import write_transaction_log

# Configure structured logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('valhopper')


# --- Error types ---
class ReturnError(enum.Enum):
    """Reasons return computation returns 0."""
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

console = Console()


# ---------------------------------------------------------------------------
# Risk level filter thresholds
# ---------------------------------------------------------------------------

RISK_LEVELS = {
    'conservative': {
        'min_trust': 0.95,
        'min_age_days': 90,
        'min_validator_permits': 1,
        'min_nominators': 100,
        'fallback_min_trust': 0.80,
        'fallback_min_age_days': 30,
    },
    'moderate': {
        'min_trust': 0.80,
        'min_age_days': 30,
        'min_validator_permits': 1,  # OR min_nominators
        'min_nominators': 10,
        'fallback_min_trust': 0.50,
        'fallback_min_age_days': 7,
    },
    'aggressive': {
        'min_trust': 0.50,
        'min_age_days': 7,
        'min_validator_permits': 0,
        'min_nominators': 0,
        'fallback_min_trust': 0.0,
        'fallback_min_age_days': 0,
    },
}

SECONDS_PER_BLOCK = 12
BLOCKS_PER_DAY = 86400 // SECONDS_PER_BLOCK  # 7200


def get_token_symbol(netuid: int) -> str:
    """Get the token symbol for a subnet."""
    symbols = {0: "τ", 1: "α", 2: "β", 3: "γ", 4: "δ", 5: "ε"}
    return symbols.get(netuid, f"S{netuid}")


def fmt_ret(val: float) -> str:
    """Format a return_per_1000 value for display."""
    if val == 0:
        return "[dim]0[/dim]"
    if val < 0.01:
        return f"{val:.6f}"
    if val < 1:
        return f"{val:.4f}"
    if val < 100:
        return f"{val:.2f}"
    return f"{val:.1f}"


# ---------------------------------------------------------------------------
# StakePosition
# ---------------------------------------------------------------------------

class StakePosition:
    """Represents a stake position with return-per-1000 calculations."""

    def __init__(self, hotkey: str, netuid: int, stake: Balance,
                 current_validator_return: float = 0.0,
                 best_validator_return: float = 0.0,
                 best_validator_hotkey: str = "",
                 best_validator_trust: float = 0.0,
                 best_validator_age_days: float = 0.0,
                 best_validator_nominators: int = 0,
                 best_validator_permits: int = 0,
                 best_validator_take: float = 0.0,
                 current_validator_trust: float = 0.0):
        self.hotkey = hotkey
        self.netuid = netuid
        self.stake = stake
        self.current_validator_return = current_validator_return
        self.best_validator_return = best_validator_return
        self.best_validator_hotkey = best_validator_hotkey
        self.best_validator_trust = best_validator_trust
        self.best_validator_age_days = best_validator_age_days
        self.best_validator_nominators = best_validator_nominators
        self.best_validator_permits = best_validator_permits
        self.best_validator_take = best_validator_take
        self.current_validator_trust = current_validator_trust

    @property
    def token_symbol(self) -> str:
        return get_token_symbol(self.netuid)

    @property
    def current_return_per_1000(self) -> float:
        """Current validator: alpha earned per 1000 alpha staked per day."""
        return self.current_validator_return

    @property
    def best_return_per_1000(self) -> float:
        """Best validator: alpha earned per 1000 alpha staked per day."""
        return self.best_validator_return

    @property
    def return_delta(self) -> float:
        """Improvement in return_per_1000 if moved to best validator."""
        return self.best_validator_return - self.current_validator_return

    @property
    def current_daily_earn(self) -> float:
        """Daily alpha earned with current validator (post-take)."""
        return (self.stake.tao / 1000) * self.current_validator_return

    @property
    def new_daily_earn(self) -> float:
        """Daily alpha earned if moved to best validator (post-take)."""
        return (self.stake.tao / 1000) * self.best_validator_return

    @property
    def potential_additional_daily(self) -> float:
        """Additional daily alpha earned if moved to best validator."""
        return self.new_daily_earn - self.current_daily_earn


# ---------------------------------------------------------------------------
# Helper: colour-code risk signals for Rich tables
# ---------------------------------------------------------------------------

def _color_trust(trust: float) -> str:
    s = f"{trust:.4f}"
    if trust >= 0.95:
        return f"[green]{s}[/green]"
    if trust >= 0.80:
        return f"[yellow]{s}[/yellow]"
    if trust > 0:
        return f"[red]{s}[/red]"
    return "-"


def _color_age(age_days: float) -> str:
    if age_days <= 0:
        return "-"
    s = f"{age_days:.0f}d"
    if age_days >= 90:
        return f"[green]{s}[/green]"
    if age_days >= 30:
        return f"[yellow]{s}[/yellow]"
    return f"[red]{s}[/red]"


# ---------------------------------------------------------------------------
# BittensorClient
# ---------------------------------------------------------------------------

class BittensorClient:
    """Client for interacting with the Bittensor blockchain."""

    def __init__(self, network: str = "finney"):
        self.network = network
        self.subtensor = bittensor.Subtensor(network=network)
        self._delegates_cache = None  # (data, timestamp)
        self._metagraph_cache = {}    # netuid -> (data, timestamp)
        self._current_block = None
        self._tempo_cache = {}        # netuid -> (tempo, timestamp)
        self.CACHE_TTL = 300  # 5 minutes

    def _cache_is_valid(self, cached):
        """Check if cache entry is still valid."""
        if cached is None:
            return False
        data, timestamp = cached
        return time.time() - timestamp < self.CACHE_TTL

    def refresh_caches(self):
        """Force refresh all caches before live execution."""
        self._delegates_cache = None
        self._metagraph_cache = {}
        self._current_block = None
        self._tempo_cache = {}

    # -- caching data fetchers -----------------------------------------------

    def get_delegates(self) -> list:
        if not self._cache_is_valid(self._delegates_cache):
            self._delegates_cache = (self.subtensor.get_delegates(), time.time())
        return self._delegates_cache[0]

    def _get_take(self, hotkey: str) -> float:
        """Get delegate take for a hotkey."""
        for d in self.get_delegates():
            if d.hotkey_ss58 == hotkey:
                return d.take
        return 0.18  # default take

    def _get_subnet_tempo(self, netuid: int) -> int:
        """Get tempo for a subnet, with caching."""
        if netuid not in self._tempo_cache or not self._cache_is_valid(self._tempo_cache[netuid]):
            hp = self.subtensor.get_subnet_hyperparameters(netuid)
            self._tempo_cache[netuid] = (hp.tempo, time.time())
        return self._tempo_cache[netuid][0]

    def get_metagraph(self, netuid: int):
        """Get and cache metagraph for a subnet."""
        if netuid not in self._metagraph_cache or not self._cache_is_valid(self._metagraph_cache[netuid]):
            self._metagraph_cache[netuid] = (self.subtensor.metagraph(netuid), time.time())
            time.sleep(0.1)  # Rate limit RPC calls
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
        """Get risk signals for a validator from metagraph + delegates."""
        info = {
            'trust': 0.0,
            'age_days': 0.0,
            'validator_permits': 0,
            'nominators': 0,
            'take': 0.0,
            'in_metagraph': False,
        }

        # From metagraph: trust, age
        try:
            meta = self.get_metagraph(netuid)
            cur_block = self.get_current_block()
            uid = None
            for i, hk in enumerate(meta.hotkeys):
                if hk == hotkey:
                    uid = i
                    break
            if uid is not None:
                info['in_metagraph'] = True
            if uid is not None and uid < len(meta.Tv):
                info['trust'] = float(meta.Tv[uid])
                reg_block = (
                    meta.block_at_registration[uid]
                    if uid < len(meta.block_at_registration) else 0
                )
                if reg_block > 0:
                    info['age_days'] = (cur_block - reg_block) * SECONDS_PER_BLOCK / 86400
        except Exception:
            pass

        # From delegates: permits, nominators, take
        for d in self.get_delegates():
            if d.hotkey_ss58 == hotkey:
                info['validator_permits'] = len(d.validator_permits)
                info['nominators'] = len(d.nominators)
                info['take'] = d.take
                break

        return info

    def _apply_risk_filters(self, delegates: list, netuid: int,
                            risk_level: str = 'moderate') -> list:
        """Filter delegates by risk level thresholds.

        Returns list of (delegate, risk_info) tuples that pass the filters.
        Uses primary thresholds first, falls back to relaxed if none pass.
        """
        config = RISK_LEVELS.get(risk_level, RISK_LEVELS['moderate'])

        candidates = []
        for d in delegates:
            risk = self._get_validator_risk_info(d.hotkey_ss58, netuid)
            # Skip deregistered validators (not in metagraph)
            if not risk['in_metagraph']:
                continue
            candidates.append((d, risk))

        # --- primary filter ---
        primary = []
        for d, risk in candidates:
            if risk['trust'] < config['min_trust']:
                continue
            if risk['age_days'] < config['min_age_days']:
                continue
            # moderate: permits OR nominators
            if risk_level == 'moderate':
                if risk['validator_permits'] < 1 and risk['nominators'] < config['min_nominators']:
                    continue
            else:
                if risk['validator_permits'] < config['min_validator_permits']:
                    continue
                if risk['nominators'] < config['min_nominators']:
                    continue
            primary.append((d, risk))

        if primary:
            return primary

        # --- fallback filter ---
        console.print(
            f"[dim]  Subnet {netuid}: No validators pass {risk_level} "
            f"primary filters, using fallback thresholds[/dim]"
        )
        fallback = []
        for d, risk in candidates:
            if risk['trust'] < config['fallback_min_trust']:
                continue
            if risk['age_days'] < config['fallback_min_age_days']:
                continue
            fallback.append((d, risk))
        return fallback

    # -- per-subnet return computation -----------------------------------------
    def _compute_return_per_1k(self, hotkey: str, netuid: int) -> float:
        """Compute per-subnet return per 1000 staked per day."""
        result = self._compute_return_per_1k_with_status(hotkey, netuid)
        logger.debug(f"Return {result.value:.6f} for {hotkey[:12]} on subnet {netuid}: {result.error.value}")
        return result.value

    def _compute_return_per_1k_with_status(self, hotkey: str, netuid: int) -> ReturnResult:
        """Compute per-subnet return per 1000 staked per day with status info."""
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
                tempo = 360  # Default tempo fallback
            tempos_per_day = BLOCKS_PER_DAY / tempo
            stake = float(meta.S[uid])
            if stake <= 0:
                return ReturnResult(0.0, ReturnError.NO_STAKE, "Validator has no stake")

            if netuid == 0:
                # Root subnet: use tao_dividends_per_hotkey
                tao_div = meta.tao_dividends_per_hotkey[uid]
                if isinstance(tao_div, tuple):
                    tao_div = tao_div[1]
                tao_div = float(tao_div)
                if tao_div <= 0:
                    # Fallback to emission-based for roots without direct tao_div
                    emission = float(meta.emission[uid])
                    if emission <= 0:
                        return ReturnResult(0.0, ReturnError.NO_EMISSION, "No root emission")
                    daily_tao = emission * tempos_per_day * (1 - take)
                    return ReturnResult(daily_tao / stake * 1000, ReturnError.NO_ERROR, "")
                daily_tao = tao_div * tempos_per_day * (1 - take)
                return ReturnResult(daily_tao / stake * 1000, ReturnError.NO_ERROR, "")
            else:
                # Alpha subnets: use alpha_dividends + tao_dividends/price
                alpha_div = meta.alpha_dividends_per_hotkey[uid]
                tao_div = meta.tao_dividends_per_hotkey[uid]
                if isinstance(alpha_div, tuple):
                    alpha_div = alpha_div[1]
                if isinstance(tao_div, tuple):
                    tao_div = tao_div[1]
                alpha_div = float(alpha_div)
                tao_div = float(tao_div)

                # Combine alpha and tao (converted to alpha)
                price = meta.pool.moving_price
                total_alpha = alpha_div
                if price > 0:
                    total_alpha += tao_div / price

                if total_alpha <= 0:
                    return ReturnResult(0.0, ReturnError.NO_EMISSION, "No alpha subnet emission")

                # Nominator gets (1 - take) share
                daily_alpha = total_alpha * tempos_per_day * (1 - take)
                return ReturnResult(daily_alpha / stake * 1000, ReturnError.NO_ERROR, "")
        except Exception as e:
            logger.warning(f"Network error for {hotkey[:12]}... on subnet {netuid}: {e}")
            return ReturnResult(0.0, ReturnError.NETWORK_ERROR, str(e))

    # -- best validator -----------------------------------------------------
    def get_best_validator_for_subnet(self, netuid: int,
                                     risk_level: str = 'moderate') -> Optional[dict]:
        """Find the best validator for a subnet, filtered by risk level.

        Computes per-subnet return from metagraph emission data instead
        of the broken aggregate return_per_1000 from get_delegates().
        """
        delegates = self.get_delegates()
        subnet_delegates = [
            d for d in delegates
            if netuid in d.registrations
        ]
        if not subnet_delegates:
            return None

        filtered = self._apply_risk_filters(subnet_delegates, netuid, risk_level)
        if not filtered:
            return None

        # Compute per-subnet return and sort
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
            'hotkey': best.hotkey_ss58,
            'return_per_1000': ret,
            'take': best.take,
            'trust': risk['trust'],
            'age_days': risk['age_days'],
            'nominators': risk['nominators'],
            'validator_permits': risk['validator_permits'],
        }

    # -- validator return ---------------------------------------------------
    def get_validator_return(self, hotkey: str, netuid: int) -> float:
        """Compute per-subnet return_per_1000 from metagraph emission data.

        Does NOT use get_delegates().return_per_1000 which is a broken
        aggregate across all subnets in mixed alpha/tao units.
        """
        return self._compute_return_per_1k(hotkey, netuid)

    # -- stakes -------------------------------------------------------------

    def get_stakes(self, coldkey_ss58: str,
                   risk_level: str = 'moderate') -> list[StakePosition]:
        """Get all stake positions for a coldkey, filtered by risk level."""
        try:
            stake_infos = self.subtensor.get_stake_info_for_coldkey(coldkey_ss58)
        except Exception as e:
            console.print(f"[red]Error fetching stakes: {e}[/red]")
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
                    stake=si.stake,
                    current_validator_return=current_return,
                    best_validator_return=best_validator['return_per_1000'] if best_validator else 0,
                    best_validator_hotkey=best_validator['hotkey'] if best_validator else "",
                    best_validator_trust=best_validator.get('trust', 0.0) if best_validator else 0.0,
                    best_validator_age_days=best_validator.get('age_days', 0.0) if best_validator else 0.0,
                    best_validator_nominators=best_validator.get('nominators', 0) if best_validator else 0,
                    best_validator_permits=best_validator.get('validator_permits', 0) if best_validator else 0,
                    best_validator_take=best_validator.get('take', 0.0) if best_validator else 0.0,
                    current_validator_trust=current_risk['trust'],
                )
                positions.append(position)

        return positions


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
@click.pass_context
def cli(ctx, network, coldkey, wallet_name, wallet_hotkey, wallet_path, risk_level):
    """ValHopper - Optimize your Bittensor Alpha token stakes."""
    ctx.ensure_object(dict)
    ctx.obj['network'] = network
    ctx.obj['coldkey'] = coldkey
    ctx.obj['wallet_name'] = wallet_name
    ctx.obj['wallet_hotkey'] = wallet_hotkey
    ctx.obj['wallet_path'] = wallet_path
    ctx.obj['risk_level'] = risk_level


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
        console.print(Panel(
            f"[yellow]No stakes found for coldkey:[/yellow]\n[cyan]{coldkey}[/cyan]"
        ))
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

    for p in sorted(positions, key=lambda x: x.stake.tao, reverse=True):
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
            f"{p.stake.tao:.4f} {p.token_symbol}",
            fmt_ret(p.current_daily_earn),
            best_daily_str,
            delta_str,
            f"[dim]{best_validator}[/dim]" if best_validator != "-" else "-",
            _color_trust(p.current_validator_trust),
            _color_trust(p.best_validator_trust),
            _color_age(p.best_validator_age_days),
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
        console.print(Panel(
            f"[green]All {len(positions)} stake(s) are already "
            f"with the best validators![/green]"
        ))
        return

    # Apply max stake filter if specified
    if max_stake_per_move is not None:
        movable_positions = [
            p for p in movable_positions
            if p.stake.tao <= max_stake_per_move
        ]
        if not movable_positions:
            console.print(f"[yellow]No positions under {max_stake_per_move} TAO stake[/yellow]")
            return

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

    total_stake_to_move = 0
    total_daily_gain = 0

    for p in movable_positions:
        total_stake_to_move += p.stake.tao
        total_daily_gain += p.potential_additional_daily

        from_val = client.get_validator_identity(p.hotkey)
        to_val = client.get_validator_identity(p.best_validator_hotkey)

        delta = p.new_daily_earn - p.current_daily_earn
        if delta >= 0:
            delta_str = f"[green]+{fmt_ret(delta)}[/green]"
        else:
            delta_str = f"[red]{fmt_ret(delta)}[/red]"

        table.add_row(
            str(p.netuid),
            f"{p.stake.tao:.4f} {p.token_symbol}",
            f"[red]{from_val}[/red]",
            f"[green]{to_val}[/green]",
            fmt_ret(p.current_daily_earn),
            f"[yellow]{fmt_ret(p.new_daily_earn)}[/yellow]",
            delta_str,
            _color_trust(p.current_validator_trust),
            _color_trust(p.best_validator_trust),
            _color_age(p.best_validator_age_days),
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
            console.print(
                f"[yellow]No validators found for subnet {netuid} "
                f"at {effective_risk} risk level[/yellow]"
            )
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
                _color_trust(risk['trust']),
                _color_age(risk['age_days']),
                str(risk['nominators']),
                f"{d.take*100:.2f}%",
            )

    console.print(table)
    console.print(f"[dim]Ret/1K = native tokens earned per 1000 staked per day (τ for root, α for alpha subnets)[/dim]")


if __name__ == '__main__':
    cli(obj={})

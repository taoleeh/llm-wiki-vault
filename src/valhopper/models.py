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

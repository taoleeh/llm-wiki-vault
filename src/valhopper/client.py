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
        timestamp = cached[-1]
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

"""SQLite yield history storage for ValHopper.

Stores daily snapshots of validator return_per_1000 per subnet
so users can track yield trends over time.
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

DB_DIR = Path.home() / ".valhopper"
DB_PATH = DB_DIR / "history.db"


def _get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS yield_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_date TEXT NOT NULL,
        netuid INTEGER NOT NULL,
        hotkey TEXT NOT NULL,
        return_per_1000 REAL NOT NULL,
        trust REAL NOT NULL DEFAULT 0.0,
        stake REAL NOT NULL DEFAULT 0.0,
        nominators INTEGER NOT NULL DEFAULT 0,
        take REAL NOT NULL DEFAULT 0.0,
        UNIQUE(snapshot_date, netuid, hotkey)
    );

    CREATE INDEX IF NOT EXISTS idx_snapshots_netuid
    ON yield_snapshots(netuid, snapshot_date DESC);

    CREATE INDEX IF NOT EXISTS idx_snapshots_hotkey
    ON yield_snapshots(hotkey, snapshot_date DESC);

    CREATE TABLE IF NOT EXISTS position_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_date TEXT NOT NULL,
        coldkey TEXT NOT NULL,
        netuid INTEGER NOT NULL,
        hotkey TEXT NOT NULL,
        stake_tao REAL NOT NULL,
        return_per_1000 REAL NOT NULL,
        daily_earn REAL NOT NULL,
        UNIQUE(snapshot_date, coldkey, netuid, hotkey)
    );

    CREATE INDEX IF NOT EXISTS idx_positions_coldkey
    ON position_snapshots(coldkey, snapshot_date DESC);
    """)
    conn.commit()


def record_validator_snapshot(
    conn: sqlite3.Connection,
    snapshot_date: str,
    netuid: int,
    hotkey: str,
    return_per_1000: float,
    trust: float = 0.0,
    stake: float = 0.0,
    nominators: int = 0,
    take: float = 0.0,
):
    conn.execute(
        """INSERT OR REPLACE INTO yield_snapshots
        (snapshot_date, netuid, hotkey, return_per_1000, trust, stake, nominators, take)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_date, netuid, hotkey, return_per_1000, trust, stake, nominators, take),
    )
    conn.commit()


def record_position_snapshot(
    conn: sqlite3.Connection,
    snapshot_date: str,
    coldkey: str,
    netuid: int,
    hotkey: str,
    stake_tao: float,
    return_per_1000: float,
    daily_earn: float,
):
    conn.execute(
        """INSERT OR REPLACE INTO position_snapshots
        (snapshot_date, coldkey, netuid, hotkey, stake_tao, return_per_1000, daily_earn)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_date, coldkey, netuid, hotkey, stake_tao, return_per_1000, daily_earn),
    )
    conn.commit()


def get_validator_history(
    conn: sqlite3.Connection,
    netuid: int,
    hotkey: str,
    days: int = 30,
) -> list[dict]:
    rows = conn.execute(
        """SELECT snapshot_date, return_per_1000, trust, stake, nominators, take
        FROM yield_snapshots
        WHERE netuid = ? AND hotkey = ?
        ORDER BY snapshot_date DESC
        LIMIT ?""",
        (netuid, hotkey, days),
    ).fetchall()
    return [dict(r) for r in rows]


def get_subnet_history(
    conn: sqlite3.Connection,
    netuid: int,
    days: int = 30,
) -> list[dict]:
    rows = conn.execute(
        """SELECT y.hotkey, y.snapshot_date, y.return_per_1000, y.trust, y.stake, y.nominators, y.take
        FROM yield_snapshots y
        INNER JOIN (
            SELECT hotkey, MAX(snapshot_date) as max_date
            FROM yield_snapshots
            WHERE netuid = ?
            GROUP BY hotkey
        ) latest ON y.hotkey = latest.hotkey AND y.snapshot_date = latest.max_date
        WHERE y.netuid = ?
        ORDER BY y.return_per_1000 DESC""",
        (netuid, netuid),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position_history(
    conn: sqlite3.Connection,
    coldkey: str,
    days: int = 30,
) -> list[dict]:
    rows = conn.execute(
        """SELECT snapshot_date, netuid, hotkey, stake_tao, return_per_1000, daily_earn
        FROM position_snapshots
        WHERE coldkey = ?
        ORDER BY snapshot_date DESC
        LIMIT ?""",
        (coldkey, days),
    ).fetchall()
    return [dict(r) for r in rows]


def detect_declining_validators(
    conn: sqlite3.Connection,
    netuid: int,
    min_days: int = 7,
    decline_threshold: float = 0.5,
) -> list[dict]:
    rows = conn.execute(
        """WITH recent AS (
            SELECT hotkey, snapshot_date, return_per_1000 as recent_ret
            FROM yield_snapshots
            WHERE netuid = ?
            GROUP BY hotkey
            HAVING snapshot_date = MAX(snapshot_date)
        ),
        older AS (
            SELECT y.hotkey, y.return_per_1000 as older_ret
            FROM yield_snapshots y
            INNER JOIN recent r ON y.hotkey = r.hotkey
            WHERE y.netuid = ?
            AND y.snapshot_date = (
                SELECT MAX(y2.snapshot_date)
                FROM yield_snapshots y2
                WHERE y2.netuid = y.netuid
                AND y2.hotkey = y.hotkey
                AND julianday(r.snapshot_date) - julianday(y2.snapshot_date) >= ?
            )
        )
        SELECT r.hotkey, o.older_ret as old_return, r.recent_ret as new_return,
        CASE WHEN o.older_ret > 0 THEN (o.older_ret - r.recent_ret) / o.older_ret
        ELSE 0 END as decline_pct
        FROM recent r
        JOIN older o ON r.hotkey = o.hotkey
        WHERE o.older_ret > 0
        AND (o.older_ret - r.recent_ret) / o.older_ret > ?""",
        (netuid, netuid, min_days, decline_threshold),
    ).fetchall()
    return [dict(r) for r in rows]


def snapshot_today(
    client,
    conn: sqlite3.Connection,
    coldkey: Optional[str] = None,
):
    today = date.today().isoformat()
    delegates = client.get_delegates()

    for d in delegates:
        for netuid in d.registrations:
            ret = client._compute_return_per_1k_with_status(d.hotkey_ss58, netuid)
            if ret.is_error:
                continue
            risk = client._get_validator_risk_info(d.hotkey_ss58, netuid)
            record_validator_snapshot(
                conn,
                today,
                netuid,
                d.hotkey_ss58,
                ret.value,
                trust=risk["trust"],
                stake=0.0,
                nominators=risk["nominators"],
                take=d.take,
            )

    if coldkey:
        positions = client.get_stakes(coldkey)
        for p in positions:
            record_position_snapshot(
                conn,
                today,
                coldkey,
                p.netuid,
                p.hotkey,
                p.stake_tao,
                p.current_return_per_1000,
                p.current_daily_earn,
            )

    conn.commit()

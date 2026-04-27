"""Transaction logging for ValHopper.

Writes transaction results to timestamped log files under
~/.valhopper/logs/ with one file per execution run.
Filename format: YYYY-MM-DD_HH-MM-SS.log
"""

import json as json_lib
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".valhopper" / "logs"


def _ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def _format_detail_value(key, value):
    if hasattr(value, 'tao'):
        return f"{value.tao:.6f}"
    if isinstance(value, int) or key in ('block_number', 'height'):
        return str(int(value))
    if isinstance(value, str) and len(value) > 20:
        return value
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def write_transaction_log(results):
    """Write transaction results to a timestamped log file.

    Args:
        results: List of (position, success, message, details) tuples
        as returned by execute_stake_move / format_transaction_results.

    Returns:
        Path to the written log file, or None if no results to log.
    """
    if not results:
        return None

    _ensure_log_dir()
    timestamp = datetime.now()
    filename = timestamp.strftime("%Y-%m-%d_%H-%M-%S") + ".log"
    filepath = LOG_DIR / filename

    lines = []
    lines.append(f"ValHopper Transaction Log")
    lines.append(f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'=' * 72}")
    lines.append("")

    success_count = 0
    fail_count = 0

    for i, (pos, success, msg, details) in enumerate(results, 1):
        status_str = "SUCCESS" if success else "FAILED"
        if success:
            success_count += 1
        else:
            fail_count += 1

        lines.append(f"Transaction #{i}")
        lines.append(f"  Subnet: {pos.netuid}")
        lines.append(f"  Amount: {pos.stake_tao:.4f} {pos.token_symbol}")
        lines.append(f"  From: {pos.hotkey}")
        lines.append(f"  To: {pos.best_validator_hotkey}")
        lines.append(f"  Status: {status_str}")
        lines.append(f"  Details: {msg}")

        if details:
            lines.append(f"  Block Info:")
            for key, value in details.items():
                label = key.replace('_', ' ').title()
                lines.append(f"    {label}: {_format_detail_value(key, value)}")

        lines.append("")

    lines.append(f"{'=' * 72}")
    lines.append(f"Summary: {success_count} succeeded, {fail_count} failed")

    total_tao_fee = sum(
        float(details.get('tao_fee', 0))
        for _, s, _, details in results if s and 'tao_fee' in details
    )
    total_alpha_fee = sum(
        float(details.get('alpha_fee', 0))
        for _, s, _, details in results if s and 'alpha_fee' in details
    )
    if total_tao_fee > 0:
        lines.append(f"Total TAO fees: {total_tao_fee:.6f}")
    if total_alpha_fee > 0:
        lines.append(f"Total Alpha fees: {total_alpha_fee:.6f}")

    if fail_count > 0:
        lines.append("")
        lines.append("Errors:")
        for pos, success, msg, details in results:
            if not success:
                lines.append(f"  Subnet {pos.netuid}: {msg}")

    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return filepath


def format_json_output(command: str, data: dict) -> str:
    """Format command output as JSON string.

    Args:
        command: The CLI command name (e.g. 'list-stakes', 'optimize')
        data: Dict of output data

    Returns:
        JSON string
    """
    output = {"command": command, **data}
    return json_lib.dumps(output, indent=2, default=str)

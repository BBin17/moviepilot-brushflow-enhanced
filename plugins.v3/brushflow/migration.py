"""BrushFlow 8.0 可重复执行的任务配置迁移。"""

from __future__ import annotations

import time
import uuid
from typing import Any, Mapping, Sequence


BALANCED_PRESET = {
    "smart_selection_max_add_per_run": 5,
    "smart_selection_min_score": 30,
    "smart_cold_inactive_minutes": 360,
    "smart_candidate_confirmations": 3,
    "smart_candidate_confirmation_minutes": 30,
    "smart_score_threshold": 40,
    "smart_max_delete_capacity_percent_day": 8,
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def migrate_task_rows_v8(
    rows: Sequence[Mapping[str, Any]],
    backups: Mapping[str, Any] | None = None,
    *,
    now: float | None = None,
) -> tuple[list[dict], dict, bool]:
    """迁移 7.x 任务；已经标记为 8 的行原样返回且不会覆盖备份。"""
    timestamp = float(now or time.time())
    saved_backups = dict(backups or {})
    normalized: list[dict] = []
    changed = False
    for source in rows:
        row = dict(source)
        if int(_number(row.get("smart_migration_version"))) >= 8:
            normalized.append(row)
            continue
        task_id = str(row.get("id") or uuid.uuid4().hex)
        row["id"] = task_id
        saved_backups.setdefault(task_id, {"saved_at": timestamp, "config": dict(source)})
        smart_was_enabled = bool(row.get("smart_enabled", False))
        ratio_weight = min(_number(row.get("smart_ratio_weight"), 5.0), 5.0)
        row.update(BALANCED_PRESET)
        row.update(
            {
                "smart_profile": "balanced",
                "smart_engine": "v8",
                "smart_ratio_weight": ratio_weight,
                "smart_demand_confirmations": 2,
                "smart_capacity_trigger_percent": 90,
                "smart_capacity_target_percent": 85,
                "smart_max_delete_per_run": 3,
                "smart_max_delete_percent_day": 5,
                "smart_max_delete_capacity_percent_run": 4,
                "smart_allow_proactive_delete": False,
                "smart_delete_paused": False,
                "smart_auto_activate": True,
                "smart_shadow_started_at": timestamp if smart_was_enabled else None,
                "smart_shadow_until": timestamp + 48 * 3600 if smart_was_enabled else None,
                "smart_shadow_extensions": 0,
                "smart_migration_version": 8,
                "site_ratio_reached_behavior": "continue",
                "delete_files": bool(row.get("delete_files", True)),
            }
        )
        # smart_enabled 本身从未被覆盖：关闭任务只预填均衡参数。
        normalized.append(row)
        changed = True
    return normalized, saved_backups, changed

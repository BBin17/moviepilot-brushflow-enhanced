"""下载健康判断：区分真正卡住和仍在缓慢推进的未完成种子。

这里只做观测和解释，不参与智能删种的硬安全线。下载字节增量是主判据，
qBittorrent 的瞬时 dlspeed 只作为辅助展示，避免一次短暂的 0 速被误判。
"""

from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Optional


HEALTH_COMPLETED = "completed"
HEALTH_DOWNLOADING = "downloading"
HEALTH_UNKNOWN = "unknown"
HEALTH_STALLED = "stalled"
HEALTH_SLOW = "slow"
HEALTH_PAUSED = "paused"
HEALTH_QUEUED = "queued"
HEALTH_CHECKING = "checking"
HEALTH_ERROR = "error"


@dataclass(frozen=True)
class DownloadHealthPolicy:
    """下载健康的任务级默认策略。"""

    stalled_confirmations: int = 3
    stalled_window_minutes: float = 30.0
    slow_after_hours: float = 6.0
    slow_speed_kbps: float = 128.0
    history_days: float = 7.0
    max_samples: int = 200
    max_sample_gap_minutes: float = 60.0


def policy_for_profile(profile: str) -> DownloadHealthPolicy:
    """按智能预设给出观测灵敏度，保守只影响提示频率，不改变删种安全线。"""
    values = {
        "conservative": {
            "stalled_confirmations": 4,
            "slow_after_hours": 12.0,
            "slow_speed_kbps": 64.0,
        },
        "aggressive": {
            "stalled_confirmations": 2,
            "slow_after_hours": 3.0,
            "slow_speed_kbps": 256.0,
        },
    }.get(profile, {})
    return DownloadHealthPolicy(**values)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _timestamp(row: Dict[str, Any]) -> float:
    return _number(row.get("at"))


def _suspended(row: Dict[str, Any]) -> bool:
    state = str(row.get("downloader_state") or "").lower()
    return bool(row.get("is_paused")) or state.startswith(("checking", "paused", "stopped")) or state in {
        "queuedl", "queueddl", "queuedup", "error", "missingfiles",
    }


def _sample(current: Dict[str, Any], now: float = 0) -> Dict[str, Any]:
    downloaded = _number(current.get("downloaded"), -1)
    return {
        "at": _number(current.get("at"), now),
        "downloaded": max(downloaded, 0),
        "measurement_valid": downloaded >= 0 and current.get("measurement_valid", True),
        "total_size": max(_number(current.get("total_size")), 0),
        "download_speed": max(_number(current.get("download_speed")), 0),
        "active_peers": current.get("active_peers"),
        "availability": current.get("availability"),
        "is_paused": bool(current.get("is_paused")),
        "downloader_state": str(current.get("downloader_state") or ""),
    }


def _annotate_sample(row: Dict[str, Any], previous: Optional[Dict[str, Any]], policy: DownloadHealthPolicy) -> dict:
    """Retain continuity evidence independently of the bounded display samples."""
    row = dict(row)
    at = _timestamp(row)
    continuous = bool(
        previous
        and row.get("measurement_valid", True)
        and previous.get("measurement_valid", True)
        and not _suspended(row)
        and not _suspended(previous)
        and 0 < at - _timestamp(previous) <= policy.max_sample_gap_minutes * 60
        and row["downloaded"] >= _number(previous.get("downloaded"))
        and row["total_size"] == _number(previous.get("total_size"))
    )
    progressed = continuous and row["downloaded"] > _number(previous.get("downloaded"))
    row["segment_since"] = previous.get("segment_since", _timestamp(previous)) if continuous else at
    row["no_progress_since"] = previous.get("no_progress_since", _timestamp(previous)) if continuous and not progressed else at
    row["no_progress_count"] = int(previous.get("no_progress_count", 1)) + 1 if continuous and not progressed else 1
    row["last_progress_at"] = at if progressed else previous.get("last_progress_at") if continuous else None
    return row


def _history(samples: Iterable[Dict[str, Any]], policy: DownloadHealthPolicy) -> List[dict]:
    rows = []
    for raw in sorted((r for r in samples if isinstance(r, dict) and _timestamp(r) > 0), key=_timestamp):
        row = _sample(raw)
        if rows and _timestamp(row) <= _timestamp(rows[-1]):
            continue
        # New records already carry continuity across compacted samples. Legacy
        # records are conservatively reconstructed from actual observations.
        if all(key in raw for key in ("segment_since", "no_progress_since", "no_progress_count")):
            row.update({key: raw.get(key) for key in ("segment_since", "no_progress_since", "no_progress_count", "last_progress_at")})
        else:
            row = _annotate_sample(row, rows[-1] if rows else None, policy)
        rows.append(row)
    return rows


def append_download_sample(
    samples: Iterable[Dict[str, Any]],
    current: Dict[str, Any],
    now: Optional[float] = None,
    policy: Optional[DownloadHealthPolicy] = None,
) -> List[Dict[str, Any]]:
    """Append distinct observations, retaining a time-window anchor when compacting.

    The last three raw checks and durable continuity counters are retained. Older
    observations are thinned in time rather than dropping the six-hour baseline
    after 200 one-minute checks. A preview must never call this function to save
    new evidence.
    """
    policy = policy or DownloadHealthPolicy()
    current_row = _sample(current, now or 0)
    rows = _history(samples, policy)
    if current_row["at"] <= 0:
        return rows
    if rows and current_row["at"] < _timestamp(rows[-1]):
        return rows  # Out-of-order responses cannot rewrite newer evidence.
    if rows and current_row["at"] - _timestamp(rows[-1]) <= 10:
        rows.pop()  # Polling/repeated checks are not independent confirmations.
    rows.append(_annotate_sample(current_row, rows[-1] if rows else None, policy))
    horizon = max(policy.slow_after_hours * 3600, policy.stalled_window_minutes * 60)
    cutoff = current_row["at"] - min(horizon, max(policy.history_days, 1) * 86400)
    before = [row for row in rows if _timestamp(row) <= cutoff]
    rows = before[-1:] + [row for row in rows if _timestamp(row) > cutoff]
    limit = max(int(policy.max_samples), int(policy.stalled_confirmations) + 2, 6)
    while len(rows) > limit:
        # Preserve the boundary anchor and recent raw checks. Cumulative bytes
        # retain their exact values; rates use the actual observed duration.
        index = min(range(1, len(rows) - 3), key=lambda i: _timestamp(rows[i + 1]) - _timestamp(rows[i - 1]))
        rows.pop(index)
    return rows


def _rate_kbps(downloaded_delta: float, elapsed: float) -> float:
    if elapsed <= 0:
        return 0.0
    return max(downloaded_delta, 0.0) / elapsed / 1024


def assess_download_health(
    samples: Iterable[Dict[str, Any]],
    current: Dict[str, Any],
    policy: Optional[DownloadHealthPolicy] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """返回可持久化的下载健康结果。

    卡住要求连续无增量的时长和独立检查次数同时达到阈值。低速使用
    窗口边界之前的一次真实累积值，避免非整点检查永远凑不齐六小时。
    """
    policy = policy or DownloadHealthPolicy()
    downloaded = max(_number(current.get("downloaded")), 0)
    total_size = max(_number(current.get("total_size")), 0)
    completed = bool(current.get("completed")) or (total_size > 0 and downloaded >= total_size)
    base = {
        "state": HEALTH_COMPLETED if completed else HEALTH_UNKNOWN,
        "reason": "completed" if completed else "insufficient_history",
        "avg_download_speed_kbps": 0.0,
        "progress_delta": 0.0,
        "observed_seconds": 0.0,
        "sample_count": 0,
    }
    if completed:
        return base
    downloader_state = str(current.get("downloader_state") or "").lower()
    if bool(current.get("is_paused")) or downloader_state.startswith(("paused", "stopped")):
        base.update({"state": HEALTH_PAUSED, "reason": "downloader_paused"})
        return base
    if downloader_state in {"queuedl", "queueddl", "queuedup"}:
        base.update({"state": HEALTH_QUEUED, "reason": "downloader_queue"})
        return base
    if downloader_state.startswith("checking"):
        base.update({"state": HEALTH_CHECKING, "reason": "downloader_checking"})
        return base
    if downloader_state in {"error", "missingfiles"}:
        base.update({"state": HEALTH_ERROR, "reason": "downloader_error"})
        return base

    rows = append_download_sample(samples, current, now=now, policy=policy)
    if not rows or not rows[-1].get("measurement_valid", True):
        return base | {"reason": "missing_download_measurement"}
    last = rows[-1]
    rows = [row for row in rows if _timestamp(row) >= _number(last.get("segment_since"))]
    confirmations = max(int(policy.stalled_confirmations), 2)
    if len(rows) < confirmations:
        return base | {"sample_count": len(rows)}

    stalled_elapsed = max(_timestamp(last) - _number(last.get("no_progress_since")), 0.0)
    stalled_count = int(last.get("no_progress_count", 1))
    if stalled_elapsed >= max(policy.stalled_window_minutes, 0) * 60 and stalled_count >= confirmations:
        reason = "no_download_progress"
        if current.get("active_peers") is not None and _number(current.get("active_peers")) > 0:
            reason = "no_download_progress_with_connection"
        base.update(
            {
                "state": HEALTH_STALLED,
                "reason": reason,
                "avg_download_speed_kbps": 0.0,
                "progress_delta": 0,
                "observed_seconds": stalled_elapsed,
                "sample_count": len(rows),
            }
        )
        return base

    slow_cutoff = _timestamp(rows[-1]) - max(policy.slow_after_hours, 0) * 3600
    anchor = [row for row in rows if _timestamp(row) <= slow_cutoff]
    slow_rows = anchor[-1:] + [row for row in rows if _timestamp(row) > slow_cutoff]
    if len(slow_rows) >= 2:
        slow_elapsed = max(_timestamp(slow_rows[-1]) - _timestamp(slow_rows[0]), 0.0)
        slow_delta = max(_number(slow_rows[-1].get("downloaded")) - _number(slow_rows[0].get("downloaded")), 0.0)
        avg_speed = _rate_kbps(slow_delta, slow_elapsed)
        if slow_elapsed >= max(policy.slow_after_hours, 0) * 3600 and slow_delta > 0 and avg_speed < max(policy.slow_speed_kbps, 0):
            base.update(
                {
                    "state": HEALTH_SLOW,
                    "reason": "low_effective_download_speed",
                    "avg_download_speed_kbps": round(avg_speed, 3),
                    "progress_delta": slow_delta,
                    "observed_seconds": slow_elapsed,
                    "sample_count": len(rows),
                }
            )
            return base

    observed = max(_timestamp(rows[-1]) - _timestamp(rows[0]), 0.0) if len(rows) >= 2 else 0.0
    delta = max(_number(rows[-1].get("downloaded")) - _number(rows[0].get("downloaded")), 0.0) if rows else 0.0
    base.update(
        {
            "state": HEALTH_DOWNLOADING if delta > 0 else HEALTH_UNKNOWN,
            "reason": "progressing" if delta > 0 else "confirming_no_progress",
            "avg_download_speed_kbps": round(_rate_kbps(delta, observed), 3),
            "progress_delta": delta,
            "observed_seconds": observed,
            "sample_count": len(rows),
        }
    )
    return base


def health_label(state: str) -> str:
    return {
        HEALTH_COMPLETED: "已完成",
        HEALTH_DOWNLOADING: "正常推进",
        HEALTH_UNKNOWN: "观察中",
        HEALTH_STALLED: "长时间无进度",
        HEALTH_SLOW: "异常低速",
        HEALTH_PAUSED: "下载器已暂停",
        HEALTH_QUEUED: "下载器排队中",
        HEALTH_CHECKING: "下载器检查中",
        HEALTH_ERROR: "下载器报错",
    }.get(state, "观察中")


def next_health_action(
    state: str,
    progress_delta: float,
    *,
    repair_at: Optional[float],
    paused_at: Optional[float],
    now: float,
    policy: Optional[DownloadHealthPolicy] = None,
    post_repair_confirmed: bool = False,
) -> Dict[str, Any]:
    """返回下载健康状态机的下一步；动作只包含修复或暂停，永不删除。"""
    policy = policy or DownloadHealthPolicy()
    if state == HEALTH_COMPLETED or (state == HEALTH_DOWNLOADING and progress_delta > 0):
        return {"action": None, "repair_at": None, "paused_at": None}
    if state not in {HEALTH_STALLED, HEALTH_SLOW}:
        return {"action": None, "repair_at": repair_at, "paused_at": paused_at}
    # 卡住状态出现真实增量即恢复；低速状态按完整观察窗的有效均速判断，
    # 否则每次极小增量都会让“连续低速 6 小时”永远无法进入修复闭环。
    if state == HEALTH_STALLED and _number(progress_delta) > 0:
        return {"action": None, "repair_at": None, "paused_at": None}
    if not repair_at:
        return {"action": "repair", "repair_at": now, "paused_at": None}
    required = policy.stalled_window_minutes * 60 if state == HEALTH_STALLED else policy.slow_after_hours * 3600
    if not paused_at and post_repair_confirmed and now - float(repair_at) >= required:
        return {"action": "pause", "repair_at": repair_at, "paused_at": now}
    return {"action": None, "repair_at": repair_at, "paused_at": paused_at}


def observe_download(
    record: Dict[str, Any], current: Dict[str, Any], *, policy: Optional[DownloadHealthPolicy] = None,
) -> tuple[dict, dict, Optional[str]]:
    """Observe without assuming an external repair/pause request succeeded.

    The returned record can be saved before attempting an action. Commit action
    results separately with ``record_health_action_result`` after adapter I/O.
    """
    policy = policy or DownloadHealthPolicy()
    now = _timestamp(current)
    previous_sample = record.get("samples", [])[-1] if record.get("samples") else None
    latest_delta = (
        max(_number(current.get("downloaded")) - _number(previous_sample.get("downloaded")), 0)
        if previous_sample and previous_sample.get("measurement_valid", True) else 0
    )
    samples = append_download_sample(record.get("samples", []), current, policy=policy)
    health = assess_download_health(samples, current, policy=policy)
    post_repair_confirmed = False
    if record.get("repair_at"):
        # Strip continuity annotations: this is a *new* evidence window, not
        # permission to reuse confirmations from before the repair.
        after = [_sample(row) for row in samples if _timestamp(row) >= float(record["repair_at"])]
        baseline = record.get("repair_baseline")
        if isinstance(baseline, dict) and (not after or _timestamp(after[0]) > _timestamp(baseline)):
            after.insert(0, _sample(baseline))
        post_health = assess_download_health(after, current, policy=policy)
        post_repair_confirmed = post_health["state"] in {HEALTH_STALLED, HEALTH_SLOW}
    transition = next_health_action(
        health["state"], latest_delta, repair_at=record.get("repair_at"),
        paused_at=record.get("paused_at"), now=now, policy=policy,
        post_repair_confirmed=post_repair_confirmed,
    )
    result = {
        **record,
        "state": health["state"], "reason": health["reason"], "updated_at": now,
        "state_since": record.get("state_since", now) if record.get("state") == health["state"] else now,
        "samples": samples,
    }
    action = transition["action"]
    if not action:
        result.update({"repair_at": transition["repair_at"], "paused_at": transition["paused_at"]})
        if not result.get("repair_at"):
            result.pop("repair_baseline", None)
    # Failed adapter attempts are visible, but not retried on every UI/check tick.
    if result.get("action_error") and now - _number(result.get("action_attempted_at")) < 300:
        action = None
    return result, health, action


def record_health_action_result(
    record: Dict[str, Any], action: str, *, now: float, success: bool, error: Optional[str] = None,
) -> dict:
    """Only an acknowledged adapter action starts the post-repair window."""
    if action not in {"repair", "pause"}:
        raise ValueError("Unknown download-health action")
    result = {**record, "action_attempted_at": now, "last_action": action}
    if not success:
        return {**result, "action_error": error or "下载器未确认操作成功"}
    result.pop("action_error", None)
    if action == "repair":
        result.update({"repair_at": now, "paused_at": None})
        if record.get("samples"):
            result["repair_baseline"] = {**_sample(record["samples"][-1]), "at": now}
    else:
        result["paused_at"] = now
    return result

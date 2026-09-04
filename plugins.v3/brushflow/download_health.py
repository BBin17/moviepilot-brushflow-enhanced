"""下载健康判断：区分真正卡住和仍在缓慢推进的未完成种子。

这里只做观测和解释，不参与智能删种的硬安全线。下载字节增量是主判据，
qBittorrent 的瞬时 dlspeed 只作为辅助展示，避免一次短暂的 0 速被误判。
"""

from dataclasses import dataclass
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
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _timestamp(row: Dict[str, Any]) -> float:
    return _number(row.get("at"))


def append_download_sample(
    samples: Iterable[Dict[str, Any]],
    current: Dict[str, Any],
    now: Optional[float] = None,
    policy: Optional[DownloadHealthPolicy] = None,
) -> List[Dict[str, Any]]:
    """追加一个采样并去除同一检查周期的重复记录。"""
    policy = policy or DownloadHealthPolicy()
    current_row = {
        "at": _number(current.get("at"), now or 0),
        "downloaded": max(_number(current.get("downloaded")), 0),
        "total_size": max(_number(current.get("total_size")), 0),
        "download_speed": max(_number(current.get("download_speed")), 0),
        "active_peers": current.get("active_peers"),
        "availability": current.get("availability"),
        "is_paused": bool(current.get("is_paused")),
        "downloader_state": str(current.get("downloader_state") or ""),
    }
    rows = [dict(row) for row in samples if isinstance(row, dict) and _timestamp(row) > 0]
    if current_row["at"] <= 0:
        return rows[-policy.max_samples :]
    if rows and current_row["at"] - _timestamp(rows[-1]) <= 10:
        rows[-1] = current_row
    else:
        rows.append(current_row)
    cutoff = current_row["at"] - max(policy.history_days, 1) * 86400
    rows = [row for row in rows if _timestamp(row) >= cutoff]
    return rows[-max(policy.max_samples, 1) :]


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

    卡住要求最近 N 次检查全部没有完成字节增量且跨度达到窗口；低速要求
    在更长观察窗口内有增量但有效平均速度低于阈值。这样“单次陈旧连接”
    不会永久保护或立即触发处理。
    """
    policy = policy or DownloadHealthPolicy()
    current_at = _number(current.get("at"), now or 0)
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
    if bool(current.get("is_paused")):
        base.update({"state": HEALTH_PAUSED, "reason": "downloader_paused"})
        return base
    downloader_state = str(current.get("downloader_state") or "").lower()
    if downloader_state in {"queuedl", "queuedup"}:
        base.update({"state": HEALTH_QUEUED, "reason": "downloader_queue"})
        return base
    if downloader_state.startswith("checking"):
        base.update({"state": HEALTH_CHECKING, "reason": "downloader_checking"})
        return base
    if downloader_state in {"error", "missingfiles"}:
        base.update({"state": HEALTH_ERROR, "reason": "downloader_error"})
        return base

    rows = [dict(row) for row in samples if isinstance(row, dict) and _timestamp(row) > 0]
    current_row = {
        "at": current_at,
        "downloaded": downloaded,
        "total_size": total_size,
        "download_speed": max(_number(current.get("download_speed")), 0),
        "active_peers": current.get("active_peers"),
        "availability": current.get("availability"),
        "is_paused": bool(current.get("is_paused")),
        "downloader_state": str(current.get("downloader_state") or ""),
    }
    if current_at > 0 and (not rows or abs(_timestamp(rows[-1]) - current_at) > 10):
        rows.append(current_row)
    elif rows:
        rows[-1] = current_row
    rows.sort(key=_timestamp)
    confirmations = max(int(policy.stalled_confirmations), 2)
    recent = rows[-confirmations:]
    if len(recent) < confirmations:
        return base | {"sample_count": len(rows)}

    stalled_elapsed = max(_timestamp(recent[-1]) - _timestamp(recent[0]), 0.0)
    stalled_delta = max(_number(recent[-1].get("downloaded")) - _number(recent[0].get("downloaded")), 0.0)
    if stalled_elapsed >= max(policy.stalled_window_minutes, 0) * 60 and stalled_delta < 1024:
        reason = "no_download_progress"
        if current.get("active_peers") is not None and _number(current.get("active_peers")) > 0:
            reason = "no_download_progress_with_connection"
        base.update(
            {
                "state": HEALTH_STALLED,
                "reason": reason,
                "avg_download_speed_kbps": 0.0,
                "progress_delta": stalled_delta,
                "observed_seconds": stalled_elapsed,
                "sample_count": len(rows),
            }
        )
        return base

    slow_cutoff = _timestamp(rows[-1]) - max(policy.slow_after_hours, 0) * 3600
    slow_rows = [row for row in rows if _timestamp(row) >= slow_cutoff]
    if len(slow_rows) >= 2:
        slow_elapsed = max(_timestamp(slow_rows[-1]) - _timestamp(slow_rows[0]), 0.0)
        slow_delta = max(_number(slow_rows[-1].get("downloaded")) - _number(slow_rows[0].get("downloaded")), 0.0)
        avg_speed = _rate_kbps(slow_delta, slow_elapsed)
        if slow_elapsed >= max(policy.slow_after_hours, 0) * 3600 and slow_delta >= 1024 and avg_speed < max(policy.slow_speed_kbps, 0):
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
            "state": HEALTH_DOWNLOADING,
            "reason": "progressing",
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
) -> Dict[str, Any]:
    """返回下载健康状态机的下一步；动作只包含修复或暂停，永不删除。"""
    policy = policy or DownloadHealthPolicy()
    if state not in {HEALTH_STALLED, HEALTH_SLOW}:
        return {"action": None, "repair_at": None, "paused_at": None}
    # 卡住状态出现真实增量即恢复；低速状态按完整观察窗的有效均速判断，
    # 否则每次极小增量都会让“连续低速 6 小时”永远无法进入修复闭环。
    if state == HEALTH_STALLED and _number(progress_delta) > 0:
        return {"action": None, "repair_at": None, "paused_at": None}
    if not repair_at:
        return {"action": "repair", "repair_at": now, "paused_at": None}
    required = policy.stalled_window_minutes * 60 if state == HEALTH_STALLED else policy.slow_after_hours * 3600
    if not paused_at and now - float(repair_at) >= required:
        return {"action": "pause", "repair_at": repair_at, "paused_at": now}
    return {"action": None, "repair_at": repair_at, "paused_at": paused_at}

"""SmartBrushFlow 1.0 本地收益学习。

模块只处理 JSON 可序列化数据，不访问网络或 MoviePilot 服务。原始小时快照
保留 30 天，长期状态仅保存分桶 EWMA 与有限的截尾样本。
"""

from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence


GIB = 1024**3
RETENTION_SECONDS = 30 * 86400
MIN_SNAPSHOT_INTERVAL = 55 * 60
MAX_BUCKET_SAMPLES = 100


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _read(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def learning_confidence(sample_count: int) -> float:
    """少于 20 个样本不启用学习，20–100 线性升权。"""
    return round(max(0.0, min((int(sample_count or 0) - 20) / 80.0, 1.0)), 4)


def size_bucket(size_bytes: Any) -> str:
    size_gb = max(_number(size_bytes), 0.0) / GIB
    if size_gb < 5:
        return "lt5"
    if size_gb < 20:
        return "5_20"
    if size_gb <= 50:
        return "20_50"
    return "gt50"


def promotion_bucket(item: Any) -> str:
    download_factor = _number(_read(item, "downloadvolumefactor", 1), 1.0)
    upload_factor = _number(_read(item, "uploadvolumefactor", 1), 1.0)
    if download_factor == 0 and upload_factor >= 2:
        return "2xfree"
    if download_factor == 0:
        return "free"
    if upload_factor >= 2:
        return "2x"
    return "normal"


def count_bucket(value: Any, *, unknown: str = "unknown") -> str:
    if value is None or _number(value, -1.0) < 0:
        return unknown
    count = _number(value)
    if count == 0:
        return "0"
    if count <= 3:
        return "1_3"
    if count <= 10:
        return "4_10"
    if count <= 30:
        return "11_30"
    return "gt30"


def age_bucket(age_minutes: Any) -> str:
    minutes = max(_number(age_minutes), 0.0)
    if minutes <= 60:
        return "lt1h"
    if minutes <= 6 * 60:
        return "1_6h"
    if minutes <= 24 * 60:
        return "6_24h"
    if minutes <= 7 * 24 * 60:
        return "1_7d"
    return "gt7d"


def feature_key(item: Any, *, joined_at: Optional[float] = None) -> str:
    """按任务内稳定特征构造学习桶键。"""
    age = _read(item, "age_minutes", _read(item, "date_elapsed", 0))
    hour_source = joined_at or _number(_read(item, "joined_at", _read(item, "time", 0)))
    hour = datetime.fromtimestamp(hour_source).hour if hour_source > 0 else datetime.now().hour
    seeders = _read(item, "join_seeders", _read(item, "seeders", _read(item, "num_seeds")))
    leechers = _read(item, "join_leechers", _read(item, "leechers", _read(item, "num_leechs")))
    return "|".join(
        (
            size_bucket(_read(item, "size", _read(item, "total_size", 0))),
            promotion_bucket(item),
            f"s:{count_bucket(seeders)}",
            f"l:{count_bucket(leechers)}",
            f"a:{age_bucket(age)}",
            f"h:{hour // 6}",
        )
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    rows = sorted(float(value) for value in values)
    position = (len(rows) - 1) * max(0.0, min(percentile, 1.0))
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return rows[lower]
    return rows[lower] + (rows[upper] - rows[lower]) * (position - lower)


def winsorize(value: float, samples: Sequence[float]) -> float:
    """正收益按95分位截尾；零收益保持为零，也不会锁死后续增长。"""
    clean = [_number(item) for item in samples if _number(item) > 0]
    if _number(value) <= 0:
        return 0.0
    if len(clean) < 5:
        return max(_number(value), 0.0)
    return min(_number(value), _percentile(clean, 0.95))


def _update_bucket(bucket: Mapping[str, Any] | None, value: float, elapsed_hours: float, now: float) -> dict:
    row = dict(bucket or {})
    recent = [max(_number(item), 0.0) for item in row.get("recent", [])][-MAX_BUCKET_SAMPLES:]
    clipped = winsorize(value, recent)
    previous = _number(row.get("ewma"), clipped)
    # 30 天时间常数；早期至少给 5% 权重，使冷启动后能在合理时间内收敛。
    alpha = max(0.05, 1.0 - math.exp(-max(elapsed_hours, 1.0) / (30 * 24)))
    row.update(
        {
            "count": int(row.get("count") or 0) + 1,
            "ewma": round(previous + alpha * (clipped - previous), 10),
            "updated_at": now,
            "recent": (recent + [round(clipped, 10)])[-MAX_BUCKET_SAMPLES:],
        }
    )
    return row


def update_learning_state(
    state: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
    *,
    now: Optional[float] = None,
) -> dict:
    """追加一轮小时快照，并用真实累计上传增量更新任务内 EWMA。"""
    timestamp = float(now or time.time())
    current = dict(state or {})
    original_snapshots = current.get("snapshots", [])
    if not isinstance(original_snapshots, list):
        original_snapshots = []
    snapshots = [
        dict(row)
        for row in original_snapshots
        if timestamp - _number(row.get("at")) <= RETENTION_SECONDS
    ]
    changed = len(snapshots) != len(original_snapshots)
    features = {str(key): dict(value) for key, value in (current.get("features") or {}).items()}
    latest = {}
    for row in snapshots:
        torrent_hash = str(row.get("hash") or "")
        if torrent_hash and _number(row.get("at")) > _number(latest.get(torrent_hash, {}).get("at")):
            latest[torrent_hash] = row

    sample_count = int(current.get("sample_count") or 0)
    for observation in observations:
        torrent_hash = str(observation.get("hash") or observation.get("torrent_hash") or "")
        if not torrent_hash:
            continue
        previous = latest.get(torrent_hash)
        if previous and timestamp - _number(previous.get("at")) < MIN_SNAPSHOT_INTERVAL:
            continue
        size = max(_number(observation.get("size", observation.get("total_size"))), 0.0)
        uploaded = max(_number(observation.get("uploaded")), 0.0)
        key = str(observation.get("feature_key") or feature_key(observation, joined_at=observation.get("joined_at")))
        snapshot = {
            "at": timestamp,
            "hash": torrent_hash,
            "uploaded": uploaded,
            "size": size,
            "feature_key": key,
            "seeders": observation.get("seeders"),
            "leechers": observation.get("leechers"),
        }
        snapshots.append(snapshot)
        changed = True
        latest[torrent_hash] = snapshot
        if not previous:
            continue
        elapsed_hours = (timestamp - _number(previous.get("at"))) / 3600.0
        delta = uploaded - _number(previous.get("uploaded"))
        size_gb = size / GIB
        if elapsed_hours <= 0 or delta < 0 or size_gb <= 0:
            continue
        yield_gb_per_gb_hour = (delta / GIB) / size_gb / elapsed_hours
        features[key] = _update_bucket(features.get(key), yield_gb_per_gb_hour, elapsed_hours, timestamp)
        features["__all__"] = _update_bucket(features.get("__all__"), yield_gb_per_gb_hour, elapsed_hours, timestamp)
        sample_count += 1

    if current and not changed:
        return current
    return {
        "version": 1,
        "snapshots": snapshots,
        "features": features,
        "sample_count": sample_count,
        "confidence": learning_confidence(sample_count),
        "updated_at": timestamp,
    }


def recent_yield_metrics(
    state: Mapping[str, Any] | None,
    torrent_hash: str,
    *,
    uploaded: float,
    size: float,
    now: Optional[float] = None,
    snapshots_by_hash: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
) -> dict:
    """从累计上传量推导 1/6/24 小时真实增量和单位容量收益。"""
    timestamp = float(now or time.time())
    rows = [
        row for row in (snapshots_by_hash.get(str(torrent_hash), []) if snapshots_by_hash is not None else (state or {}).get("snapshots", []))
        if str(row.get("hash") or "") == str(torrent_hash)
        and _number(row.get("at")) <= timestamp
    ]
    result = {}
    for hours in (1, 6, 24):
        measured = measure_upload_window(rows, uploaded=uploaded, now=timestamp, hours=hours)
        result[f"upload_delta_{hours}h"] = measured["delta"]
        elapsed = measured["coverage_hours"]
        result[f"yield_per_gb_{hours}h"] = measured["delta"] / max(size, 1) / elapsed if size > 0 and elapsed > 0 else 0.0
        result[f"upload_window_observed_{hours}h"] = measured["complete"]
        result[f"upload_coverage_hours_{hours}h"] = elapsed
    return result


def measure_upload_window(rows, *, uploaded: float, now: float, hours: float = 24) -> dict:
    """Measured deltas with explicit coverage; missing history is never zero income."""
    start = now - hours * 3600
    points = {_number(row.get("at")): _number(row.get("uploaded"), -1)
              for row in rows if 0 < _number(row.get("at")) <= now and _number(row.get("uploaded"), -1) >= 0}
    points[now] = max(_number(uploaded), 0)
    ordered = sorted(points.items())
    before = [point for point in ordered if point[0] <= start]
    after = [point for point in ordered if point[0] > start]
    if not after:
        return {"delta": 0.0, "coverage_hours": 0.0, "complete": False}
    full = bool(before)
    if before:
        left, right = before[-1], after[0]
        if right[0] - left[0] > 2 * 3600 or right[1] < left[1]:
            full = False
            window = after
        else:
            fraction = (start - left[0]) / max(right[0] - left[0], 1)
            window = [(start, left[1] + fraction * (right[1] - left[1]))] + after
    else:
        window = after
    delta = 0.0
    for left, right in zip(window, window[1:]):
        if right[1] < left[1] or right[0] - left[0] > 2 * 3600:
            full = False
        delta += max(right[1] - left[1], 0)
    elapsed = max(now - window[0][0], 0) / 3600
    return {"delta": delta, "coverage_hours": min(elapsed, hours), "complete": full and elapsed >= hours}


def predict_yield(state: Mapping[str, Any] | None, item: Any) -> dict:
    """返回候选的任务内预期收益、0–25 分及当前学习置信度。"""
    current = state or {}
    features = current.get("features") or {}
    exact = features.get(feature_key(item)) or {}
    global_row = features.get("__all__") or {}
    bucket_samples = int(exact.get("count") or 0)
    bucket_confidence = min(bucket_samples / 20, 1.0)
    global_expected = _number(global_row.get("ewma"), 0.0)
    expected = _number(exact.get("ewma"), global_expected) * bucket_confidence + global_expected * (1 - bucket_confidence)
    global_recent = global_row.get("recent") or []
    median = _percentile(global_recent, 0.5) if global_recent else _number(global_row.get("ewma"), 0.0)
    if expected <= 0 and median <= 0:
        score = 0.0
    else:
        reference = max(median, 1e-9)
        score = max(0.0, min(25.0, 12.5 + math.log2(max(expected, 1e-9) / reference) * 5.0))
    return {
        "expected": expected,
        "median": median,
        "score": round(score, 2),
        "confidence": learning_confidence(int(current.get("sample_count") or 0)) * bucket_confidence,
        "bucket_samples": bucket_samples,
    }


def learning_summary(state: Mapping[str, Any] | None) -> dict:
    current = state or {}
    sample_count = int(current.get("sample_count") or 0)
    return {
        "sample_count": sample_count,
        "confidence": learning_confidence(sample_count),
        "feature_buckets": max(len(current.get("features") or {}) - 1, 0),
        "snapshot_count": len(current.get("snapshots") or []),
        "updated_at": current.get("updated_at"),
    }

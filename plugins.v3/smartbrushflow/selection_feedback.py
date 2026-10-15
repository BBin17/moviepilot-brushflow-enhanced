"""Task-local, distinct-torrent outcomes; repeated checks never add samples.

Only continuous measured windows are training labels. Historical counters without
an observed baseline, resets and long sampling gaps are not zero-yield examples.
No model or raw data is sent off the NAS.
"""

from collections import defaultdict
from copy import deepcopy
import math

from .learning import RETENTION_SECONDS, age_bucket, promotion_bucket, size_bucket


def number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def read(item, name, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def selection_features(item):
    seeds = number(read(item, "join_seeders", read(item, "seeders")), -1)
    peers = number(read(item, "join_leechers", read(item, "leechers")), -1)
    competition = "unknown" if seeds < 0 or peers < 0 else "high" if seeds > max(peers, 1) * 10 else "low"
    age = read(item, "age_minutes")
    if age is None:
        age = read(item, "date_elapsed")
    return [size_bucket(read(item, "size", 0)), promotion_bucket(item), competition,
            age_bucket(age) if number(age, -1) >= 0 else "unknown"]


def _window(points, start, hours):
    end = start + hours * 3600
    points = sorted(points.items())
    def boundary(at):
        left = [p for p in points if p[0] <= at]
        right = [p for p in points if p[0] >= at]
        if not left or not right:
            return None
        a, b = left[-1], right[0]
        if b[0] - a[0] > 2 * 3600 or b[1] < a[1]:
            return None
        return a[1] if a[0] == b[0] else a[1] + (b[1] - a[1]) * (at - a[0]) / (b[0] - a[0])
    first, last = boundary(start), boundary(end)
    if first is None or last is None:
        return None
    inner = [(start, first)] + [p for p in points if start < p[0] < end] + [(end, last)]
    if any(b[0] - a[0] > 2 * 3600 or b[1] < a[1] for a, b in zip(inner, inner[1:])):
        return None
    return max(last - first, 0)


def update_feedback(state, records, learning, *, now):
    """Freeze measured 6/24/72h labels once, and keep only 30 days/1000 torrents."""
    outcomes = deepcopy((state or {}).get("outcomes") or {})
    snapshots = defaultdict(dict)
    for point in (learning or {}).get("snapshots", []):
        at, uploaded = number(point.get("at")), number(point.get("uploaded"), -1)
        if now - RETENTION_SECONDS <= at <= now and uploaded >= 0:
            snapshots[str(point.get("hash") or "")][at] = uploaded
    for key, record in records.items():
        joined = number(record.get("time"))
        size = number(record.get("size"))
        if not (now - RETENTION_SECONDS <= joined <= now) or size <= 0:
            continue
        row = outcomes.get(str(key), {"joined_at": joined, "size": size,
                                     "features": selection_features(record), "windows": {}})
        points = snapshots[str(key)]
        context = record.get("selection_context") or {}
        # Baseline is only known for downloads actually added by this engine.
        if number(context.get("at")) == joined and context.get("baseline_uploaded") is not None:
            points[joined] = number(context["baseline_uploaded"])
        measured = number(record.get("download_health_checked_at"))
        if joined <= measured <= now and record.get("uploaded") is not None:
            points[measured] = number(record["uploaded"])
        for hours in (6, 24, 72):
            if str(hours) in row["windows"] or now < joined + hours * 3600:
                continue
            delta = _window(points, joined, hours)
            if delta is not None:
                row["windows"][str(hours)] = {"uploaded": delta, "yield": delta / size,
                                               "at": joined + hours * 3600}
        row["completed"] = bool(number(record.get("download_completed_bytes")) >= size)
        row["download_issue"] = bool(record.get("download_overdue") or record.get("download_health_auto_paused")
                                     or record.get("download_health") in {"stalled", "slow", "error"})
        row["predicted_yield_24h"] = context.get("predicted_yield_24h")
        outcomes[str(key)] = row
    outcomes = {key: row for key, row in outcomes.items() if now - RETENTION_SECONDS <= number(row.get("joined_at")) <= now}
    outcomes = dict(sorted(outcomes.items(), key=lambda item: number(item[1]["joined_at"]), reverse=True)[:1000])
    return {"version": 1, "outcomes": outcomes, "updated_at": now}


def _estimate(rows, hours, now):
    values = []
    for row in rows:
        sample = row.get("windows", {}).get(str(hours))
        if sample:
            values.append((number(sample["yield"]), math.exp(-(now - number(row["joined_at"])) / (14 * 86400))))
    if not values:
        return None
    positive = sorted(value for value, _ in values if value > 0)
    cap = positive[min(int((len(positive) - 1) * .95), len(positive) - 1)] if len(positive) >= 5 else float("inf")
    return sum(min(value, cap) * weight for value, weight in values) / sum(weight for _, weight in values)


def predict_selection(state, candidate, *, now, hours=24):
    features = selection_features(candidate)
    rows = [row for row in ((state or {}).get("outcomes") or {}).values()
            if now - RETENTION_SECONDS <= number(row.get("joined_at")) <= now and str(hours) in row.get("windows", {})]
    global_expected = _estimate(rows, hours, now)
    expected, matched, level = global_expected, rows, "task"
    # Hierarchical shrinkage prevents a sparse 6-way exact bucket claiming certainty.
    for width, name in ((1, "size"), (2, "size_promotion"), (4, "similar")):
        group = [row for row in rows if row.get("features", [])[:width] == features[:width]]
        if len(group) < 5:
            continue
        weight = len(group) / (len(group) + 20)
        expected = _estimate(group, hours, now) * weight + (expected or 0) * (1 - weight)
        matched, level = group, name
    confidence = max(0, min((len(rows) - 20) / 80, 1)) * min(len(matched) / 20, 1)
    score = 0.0
    if expected is not None:
        if global_expected and expected > 0:
            score = max(0, min(25, 12.5 + math.log2(expected / global_expected) * 5))
        elif expected > 0:
            score = 12.5
    return {"expected": expected, "reference": global_expected, "score": round(score, 2), "confidence": round(confidence, 4),
            "sample_count": len(rows), "matched_count": len(matched), "level": level, "hours": hours,
            "productive_rate": sum(row["windows"][str(hours)]["uploaded"] > 0 for row in matched) / len(matched) if matched else None}


def feedback_summary(state, *, now):
    rows = [row for row in ((state or {}).get("outcomes") or {}).values()
            if now - RETENTION_SECONDS <= number(row.get("joined_at")) <= now]
    measured = [row for row in rows if "24" in row.get("windows", {})]
    calibrated = [row for row in measured if row.get("predicted_yield_24h") is not None]
    return {"tracked_torrents": len(rows), "sample_count": len(measured),
            "confidence": round(max(0, min((len(measured) - 20) / 80, 1)), 4),
            "productive_count": sum(row["windows"]["24"]["uploaded"] > 0 for row in measured),
            "zero_upload_count": sum(row["windows"]["24"]["uploaded"] == 0 for row in measured),
            "uploaded_bytes_24h": sum(row["windows"]["24"]["uploaded"] for row in measured),
            "window_counts": {str(h): sum(str(h) in row.get("windows", {}) for row in rows) for h in (6, 24, 72)},
            "prediction_error": (sum(abs(number(row["predicted_yield_24h"]) - row["windows"]["24"]["yield"])
                                     for row in calibrated) / len(calibrated)) if calibrated else None}

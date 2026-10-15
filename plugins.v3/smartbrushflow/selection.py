"""Opportunity-aware selection. Pure functions; no network or downloader writes."""

from datetime import datetime
import hashlib
import statistics

from .decision import candidate_score
from .learning import GIB
from .selection_feedback import number, read, predict_selection


MAX_HISTORY_CANDIDATES = 1000
HISTORY_SECONDS = 6 * 3600


def candidate_key(candidate):
    # Never persist URLs/passkeys in the candidate-observation store.
    identity = read(candidate, "page_url") or read(candidate, "enclosure") or read(candidate, "title", "")
    return hashlib.sha256(str(identity).encode()).hexdigest()


def candidate_data(candidate):
    return {key: read(candidate, key) for key in (
        "title", "size", "seeders", "leechers", "downloadvolumefactor", "uploadvolumefactor",
        "age_minutes", "date_elapsed", "freedate",
        "demand_trusted",
    )}


def observe_candidates(state, candidates, *, now):
    history = {}
    for key, points in ((state or {}).get("candidates") or {}).items():
        recent = [dict(p) for p in points if now - HISTORY_SECONDS <= number(p.get("at")) <= now]
        if recent:
            history[key] = recent[-12:]
    for candidate in candidates:
        key = candidate_key(candidate)
        points = history.setdefault(key, [])
        # Manual refresh spam cannot manufacture confirmation or stall evidence.
        if points and now - number(points[-1].get("at")) < 120:
            continue
        points.append({"at": now, "seeders": read(candidate, "seeders"), "leechers": read(candidate, "leechers")})
        history[key] = points[-12:]
    keys = sorted(history, key=lambda key: number(history[key][-1]["at"]), reverse=True)[:MAX_HISTORY_CANDIDATES]
    return {"version": 1, "candidates": {key: history[key] for key in keys}}


def demand_signal(points, *, now):
    recent = [p for p in points if 0 <= now - number(p.get("at")) <= 2 * 3600
              and number(p.get("leechers"), -1) >= 0 and number(p.get("seeders"), -1) >= 0]
    if len(recent) < 2 or now - number(recent[-1]["at"]) > 120 or recent[-1]["at"] - recent[0]["at"] < 300:
        return {"state": "unknown", "adjustment": 0, "observations": len(recent), "span_minutes": 0}
    # Do not join disjoint observations into a trend.
    while len(recent) > 1 and any(b["at"] - a["at"] > 3600 for a, b in zip(recent, recent[1:])):
        recent.pop(0)
    first, last = recent[0], recent[-1]
    if last["at"] - first["at"] < 300:
        return {"state": "unknown", "adjustment": 0, "observations": len(recent), "span_minutes": 0}
    delta = number(last["leechers"]) - number(first["leechers"])
    seed_delta = number(last["seeders"]) - number(first["seeders"])
    ratio = delta / max(number(first["leechers"]), 1)
    state, adjustment = "stable", 0
    if delta >= 2 and ratio >= .15:
        state, adjustment = "rising", min(12, 5 + ratio * 10)
    elif delta <= -2 and ratio <= -.2:
        state, adjustment = "falling", -min(18, 8 + abs(ratio) * 12)
    if seed_delta >= 5 and seed_delta > max(delta, 0) * 2:
        adjustment -= min(10, seed_delta / max(number(first["seeders"]), 1) * 5)
        if state != "falling":
            state = "competition_rising"
    return {"state": state, "adjustment": round(adjustment, 2), "observations": len(recent),
            "span_minutes": round((last["at"] - first["at"]) / 60, 1),
            "leecher_change": delta, "seeder_change": seed_delta}


def download_context(records, *, now, base_count, download_limit_kbps=0, torrent_limit_kbps=0):
    active, issues, speeds = [], [], []
    for row in records.values():
        if row.get("deleted"):
            continue
        size = number(row.get("size"))
        if size <= 0 or number(row.get("download_completed_bytes")) >= size:
            continue
        active.append(row)
        fresh = 0 <= now - number(row.get("download_health_checked_at")) <= 1800
        if fresh and (row.get("download_overdue") or row.get("download_health_auto_paused")
                      or row.get("download_health") in {"stalled", "slow", "error"}):
            issues.append(row)
        speed = number(row.get("download_health_avg_kbps")) * 1024
        if fresh and speed > 0 and number(row.get("download_health_progress_delta")) > 0:
            speeds.append(speed)
    # A previous completion provides wall-clock throughput, including queue time.
    historical = []
    for row in records.values():
        completed_at, joined = number(row.get("download_first_completed_at")), number(row.get("time"))
        elapsed = completed_at - joined
        if (now - 30 * 86400 <= completed_at <= now and 180 <= elapsed <= 48 * 3600
                and number(row.get("download_seen_incomplete_at")) > 0):
            historical.append((completed_at, number(row.get("size")) / elapsed))
    historical.sort(reverse=True)
    source = "active" if len(speeds) >= 3 else "completed" if len(historical) >= 3 else "unknown"
    pool = speeds if source == "active" else [s for _, s in historical[:30]] if source == "completed" else []
    speed = statistics.median_low(sorted(pool)) if pool else None
    count = max(int(base_count), 1)
    reason = None
    if len(active) >= 3 and len(issues) / len(active) >= .5:
        count, reason = 0, "download_backlog_unhealthy"
    elif issues:
        count, reason = min(count, 1), "download_backlog_limited"
    if speed:
        if download_limit_kbps > 0:
            speed = min(speed, download_limit_kbps * 1024 / max(len(active) + count, 1))
        if torrent_limit_kbps > 0:
            speed = min(speed, torrent_limit_kbps * 1024)
    return {"max_add": count, "reason": reason, "active_count": len(active), "issue_count": len(issues),
            "speed_bytes_second": speed, "speed_source": source, "speed_samples": len(pool)}


def promotion_remaining(candidate, *, now):
    raw = read(candidate, "freedate")
    if not raw:
        return None
    try:
        if isinstance(raw, (float, int)) and raw > 1_000_000_000:
            return (raw - now) / 3600
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        # Site-local dates with no known timezone cannot support a hard veto.
        return (parsed.timestamp() - now) / 3600 if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def evaluate_opportunities(candidates, history, feedback, records, *, now, min_score=30,
                           max_count=5, occupancy_ratio=0, profile="balanced", task_capacity_bytes=0,
                           min_seed_hours=0, download_limit_kbps=0, torrent_limit_kbps=0, require_free=True):
    context = download_context(records, now=now, base_count=max_count,
                               download_limit_kbps=download_limit_kbps, torrent_limit_kbps=torrent_limit_kbps)
    evaluated = []
    for candidate in candidates:
        data, key = candidate_data(candidate), candidate_key(candidate)
        age = number(data.get("age_minutes"), number(data.get("date_elapsed"), -1))
        # Unknown publication time must not earn the full freshness bonus.
        data["age_minutes"] = age if age >= 0 else 7 * 24 * 60
        learned = predict_selection(feedback, data, now=now)
        base = candidate_score(data, occupancy_ratio=occupancy_ratio, profile=profile, normal_threshold=min_score,
                               learned_yield_score=learned["score"], learned_expected_yield=learned["expected"],
                               learned_median_yield=learned["reference"],
                               learning_confidence=learned["confidence"], task_capacity_bytes=task_capacity_bytes)
        trend = demand_signal(((history or {}).get("candidates") or {}).get(key, []), now=now)
        reasons, parts = list(base.reason_codes), dict(base.contributions)
        parts["demand_trend"] = trend["adjustment"]
        if learned["confidence"] >= .5 and learned["productive_rate"] is not None and learned["productive_rate"] < .2:
            parts["historical_failure_risk"] = -15 * learned["confidence"]
            reasons.append("similar_torrents_unproductive")
        reasons.append("demand_" + trend["state"])
        size = number(data.get("size"))
        eta = size / context["speed_bytes_second"] / 3600 if context["speed_bytes_second"] else None
        parts["completion_risk"] = 0
        if eta is not None and eta > 2:
            penalty = min(15, (eta - 2) * 1.5)
            if trend["state"] in {"falling", "competition_rising"}:
                penalty = min(25, penalty * 1.5)
            parts["completion_risk"] = -round(penalty, 2)
            reasons.append("completion_window_risk")
        elif eta is None:
            reasons.append("completion_time_unknown")
        commitment = size / GIB * max(min_seed_hours, 0)
        parts["minimum_seed_cost"] = -round(min(10, commitment / max(task_capacity_bytes / GIB * 24, 1) * 10), 2) if task_capacity_bytes > 0 else 0
        if min_seed_hours > 0:
            reasons.append("minimum_seed_commitment")
        remaining = promotion_remaining(candidate, now=now)
        accepted = base.accepted
        if require_free and number(data.get("downloadvolumefactor"), 1) == 0 and remaining is not None:
            if remaining <= 0 or (eta is not None and eta * 1.25 >= remaining):
                accepted = False
                reasons.append("promotion_finishes_too_soon")
        peers, seeds = number(data.get("leechers"), -1), number(data.get("seeders"), -1)
        if peers == 0:
            parts["no_demand_risk"] = -12
            reasons.append("no_observed_demand")
        if seeds == 0:
            parts["source_risk"] = -15
            reasons.append("full_source_unconfirmed")
        score = round(max(0, min(100, sum(parts.values()))), 2)
        if score < min_score:
            accepted = False
            reasons.append("below_selection_threshold")
        # Unknown/no demand is a small, explicitly bounded exploration, not filler.
        explore = peers <= 0
        if explore and (size > 10 * GIB or (age >= 0 and age > 24 * 60) or seeds == 0):
            accepted = False
            reasons.append("exploration_not_suitable")
        if context["reason"]:
            reasons.append(context["reason"])
        evaluated.append({"key": key, "candidate": candidate, "score": score, "eligible": accepted,
                          "selected": False, "status": "rejected" if not accepted else "qualified",
                          "reasons": list(dict.fromkeys(reasons)), "contributions": parts,
                          "confidence": learned["confidence"], "learning": learned, "trend": trend,
                          "eta_hours": round(eta, 2) if eta is not None else None,
                          "promotion_hours": round(remaining, 2) if remaining is not None else None,
                          "minimum_seed_gb_hours": round(commitment, 1), "exploratory": explore})
    ranked = sorted([row for row in evaluated if row["eligible"]],
                    key=lambda row: (not row["exploratory"], row["score"], -number(read(row["candidate"], "size"))), reverse=True)
    chosen, explored = [], False
    for row in ranked:
        if len(chosen) >= context["max_add"]:
            row["status"] = "waiting"
            row["reasons"].append("round_selection_limit")
        elif row["exploratory"] and explored:
            row["status"] = "waiting"
            row["reasons"].append("exploration_limit")
        else:
            row["status"] = "planned"
            chosen.append(row)
            explored |= row["exploratory"]
    return {"evaluated": evaluated, "ranked": ranked, "planned": chosen, "context": context}


def public_decision(row):
    return {key: value for key, value in row.items() if key not in {"candidate", "eligible"}} | {
        "title": read(row["candidate"], "title", "未知候选"), "size": number(read(row["candidate"], "size"))}

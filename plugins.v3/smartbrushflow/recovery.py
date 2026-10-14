"""Read-only rolling quota forecasts; never grants extra deletion authority."""
from .decision import deletion_budget


def recovery_summary(*, policy, active_count, capacity, current, target, ledger, candidates, now):
    recent = [row for row in ledger if row.get("status") not in {"failed", "skipped"}
              and 0 <= now - float(row.get("at") or 0) < 86400]

    def budget_at(at):
        rows = [row for row in recent if at < float(row.get("at") or 0) + 86400]
        return deletion_budget(policy, active_count=active_count, capacity=capacity,
                               deleted_count=len(rows), deleted_bytes=sum(float(row.get("size") or 0) for row in rows))

    budget = budget_at(now)
    sizes = [float(row.get("size") or 0) for row in candidates if float(row.get("size") or 0) > 0]
    fits_run = [size for size in sizes if budget["run_byte_cap"] <= 0 or size <= budget["run_byte_cap"]]

    def available(quotas):
        return (quotas["run_count_cap"] > 0 and quotas["remaining_daily_count"] > 0
                and any(quotas["daily_byte_cap"] <= 0 or size <= quotas["remaining_daily_bytes"] for size in fits_run))

    next_at = None
    if fits_run and not available(budget):
        for at in sorted({float(row.get("at") or 0) + 86400 for row in recent}):
            if available(budget_at(at)):
                next_at = at
                break
    return {
        **budget, "deleted_count_24h": len(recent),
        "deleted_bytes_24h": sum(float(row.get("size") or 0) for row in recent),
        "debt_bytes": max(current - target, 0), "next_quota_at": next_at,
        "wait_seconds": max(next_at - now, 0) if next_at else None,
        "oversized_count": len(sizes) - len(fits_run),
        "candidate_min_bytes": min(sizes) if sizes else 0,
        "forecast_note": "按已有删除记录估算；新删除、候选变化和最终安全复核会影响结果。",
    }

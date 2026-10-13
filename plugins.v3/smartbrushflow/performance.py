"""Task-local upload and space diagnostics from measured hourly counters."""

from collections import defaultdict
import time

from .learning import recent_yield_metrics


def performance_rows(torrents, learning, *, min_seed_hours=0, now=None):
    timestamp = time.time() if now is None else now
    snapshots = defaultdict(list)
    for row in (learning or {}).get("snapshots", []):
        snapshots[str(row.get("hash") or "")].append(row)
    result = {}
    for torrent_hash, raw in torrents.items():
        row = dict(raw)
        size = float(row.get("total_size") or row.get("size") or 0)
        measured_at = float(row.get("deleted_time") or row.get("manual_removed_at") or row.get("download_health_checked_at") or 0)
        if measured_at > 0 and measured_at <= timestamp and row.get("uploaded") is not None:
            snapshots[str(torrent_hash)].append({"hash": str(torrent_hash), "at": measured_at, "uploaded": row["uploaded"]})
        measured = recent_yield_metrics(learning, str(torrent_hash), uploaded=float(row.get("uploaded") or 0),
                                        size=size, now=timestamp, snapshots_by_hash=snapshots)
        completed = size > 0 and float(row.get("download_completed_bytes") or 0) >= size
        seed_seconds = row.get("seeding_time")
        minimum_met = bool(completed and min_seed_hours > 0 and seed_seconds is not None
                           and float(seed_seconds) >= min_seed_hours * 3600)
        zero_upload = bool(minimum_met and row.get("uploaded") is not None and measured["upload_window_observed_24h"]
                           and measured["upload_delta_24h"] == 0)
        row.update(measured)
        row["removed_at"] = float(row.get("deleted_time") or row.get("manual_removed_at") or 0)
        row["measured_at"] = timestamp
        row.update({"hash": str(torrent_hash), "size": size, "completed": completed,
                    "min_seed_met": minimum_met, "min_seed_hours": min_seed_hours,
                    "seeding_hours": round(float(seed_seconds or 0) / 3600, 1) if seed_seconds is not None else None,
                    "minimum_remaining_hours": max(min_seed_hours - float(seed_seconds or 0) / 3600, 0),
                    "mature_zero_upload": zero_upload,
                    "age_hours": max(timestamp - float(row.get("add_on") or row.get("time") or timestamp), 0) / 3600})
        result[str(torrent_hash)] = row
    return result


def summarize_performance(rows):
    active = [row for row in rows.values() if not row.get("deleted")]
    zero = [row for row in active if row["mature_zero_upload"]]
    total_upload = sum(row["upload_delta_24h"] for row in rows.values()
                       if not row.get("deleted") or row["removed_at"] > row["measured_at"] - 24 * 3600)
    complete_windows = sum(bool(row["upload_window_observed_24h"]) for row in active)
    size = sum(row["size"] for row in active)
    return {
        "uploaded_bytes_24h": total_upload,
        "unit_yield_24h": total_upload / size if size else 0,
        "active_count": len(active),
        "completed_count": sum(row["completed"] for row in active),
        "minimum_met_count": sum(row["min_seed_met"] for row in active),
        "minimum_pending_count": sum(row["completed"] and not row["min_seed_met"] for row in active),
        "productive_count": sum(row["upload_delta_24h"] > 0 for row in active),
        "connected_count": sum(float(row.get("active_peers") or 0) > 0 for row in active),
        "uploading_count": sum(float(row.get("upload_speed") or 0) > 0 for row in active),
        "tracker_demand_count": sum(float(row.get("leechers") or 0) > 0 for row in active),
        "zero_upload_count": len(zero),
        "zero_upload_bytes": sum(row["size"] for row in zero),
        "complete_window_count": complete_windows,
        "partial_window_count": len(active) - complete_windows,
        "observation_complete": bool(active) and complete_windows == len(active),
        "low_yield_items": [{key: row.get(key) for key in ("hash", "title", "size", "seeding_hours", "min_seed_met", "upload_delta_24h")}
                            for row in sorted(zero, key=lambda row: -row["size"])[:10]],
    }

from dataclasses import replace

import pytest

from app.plugins.smartbrushflow.decision import SmartPolicy, select_deletions
from app.plugins.smartbrushflow.recovery import recovery_summary


GIB = 1024 ** 3
NOW = 2_000_000


def seed(name, size, **overrides):
    return {"hash": name, "total_size": size * GIB, "progress": 100, "seeding_time": 200 * 3600,
            "inactive_time": 48 * 3600, "active_peers": 0, "upload_speed": 0,
            "low_value_confirmations": 3, "low_value_span_minutes": 60,
            "upload_window_observed_24h": True, **overrides}


def policy(**overrides):
    return replace(SmartPolicy(min_seed_time_hours=48, max_delete_per_run=3, max_delete_percent_day=100,
                               max_delete_capacity_percent_run=8, max_delete_capacity_percent_day=15), **overrides)


def test_recovery_uses_one_slot_to_clear_debt_with_minimal_overshoot():
    result = select_deletions([seed("tiny", 1), seed("fitting", 24), seed("larger", 38), seed("too-big", 210)],
                             policy(max_delete_per_run=1), current_size=703*GIB, disk_limit=800*GIB,
                             recovery_active=True)
    assert [row.torrent_hash for row in result.selected] == ["fitting"]
    assert result.estimated_freed_bytes == 24*GIB


@pytest.mark.parametrize("guard", [{"hit_and_run": True}, {"progress": 50}, {"upload_speed": 1},
                                    {"active_peers": 1}, {"seeding_time": 1}, {"upload_delta_since_check": 1}])
def test_recovery_preference_never_bypasses_protection(guard):
    result = select_deletions([seed("protected", 24, **guard), seed("safe", 1)], policy(),
                             current_size=703*GIB, disk_limit=800*GIB, recovery_active=True)
    assert "protected" not in {row.torrent_hash for row in result.selected}


def test_recovery_does_not_grant_additional_count_or_bytes():
    result = select_deletions([seed("fitting", 24)], policy(max_delete_percent_day=10),
                             current_size=703*GIB, disk_limit=800*GIB, recovery_active=True,
                             deleted_today=1)
    assert not result.selected
    assert "daily_count_cap" in result.reason_codes
    result = select_deletions([seed("fitting", 24)], policy(max_delete_gb_per_run=2),
                             current_size=703*GIB, disk_limit=800*GIB, recovery_active=True)
    assert not result.selected


def test_partial_window_keeps_original_score_order():
    result = select_deletions([seed("big", 38, upload_window_observed_24h=False),
                              seed("fit", 24, upload_window_observed_24h=False)],
                             policy(max_delete_per_run=1), current_size=703*GIB, disk_limit=800*GIB,
                             recovery_active=True)
    assert result.selected[0].torrent_hash == "big"


def forecast(ledger, candidates=None, **overrides):
    return recovery_summary(policy=policy(max_delete_percent_day=10, **overrides), active_count=59,
                            capacity=800*GIB, current=703*GIB, target=680*GIB, ledger=ledger,
                            candidates=candidates if candidates is not None else [{"size":24*GIB}], now=NOW)


def test_quota_forecast_accounts_for_rolling_denominator_and_does_not_modify_ledger():
    ledger = [{"at": NOW-1000-i, "size":GIB, "status":"confirmed_removed"} for i in range(6)]
    result = forecast(ledger)
    assert result["daily_count_cap"] == 6
    assert result["remaining_daily_count"] == 0
    assert result["next_quota_at"] == NOW-1005+86400
    assert result["debt_bytes"] == 23*GIB
    assert len(ledger) == 6


def test_failed_future_and_expired_rows_do_not_consume_quota():
    result = forecast([{"at":NOW-90000}, {"at":NOW+10}, {"at":NOW-100,"status":"failed"},
                       {"at":NOW-100,"status":"skipped"}])
    assert result["deleted_count_24h"] == 0
    assert result["remaining_daily_count"] == 5
    assert result["next_quota_at"] is None


def test_unconfirmed_request_still_consumes_quota():
    ledger = [{"at":NOW-100, "size":GIB, "status":"pending_confirmation"} for _ in range(6)]
    assert forecast(ledger)["remaining_daily_count"] == 0


def test_oversized_seed_cannot_be_fixed_by_waiting():
    result = forecast([{"at":NOW-100,"size":GIB}], candidates=[{"size":210*GIB}])
    assert result["oversized_count"] == 1
    assert result["next_quota_at"] is None


def test_capacity_quota_forecast_waits_for_enough_bytes_not_first_expiry():
    ledger = [{"at":NOW-1000,"size":GIB}, {"at":NOW-100,"size":100*GIB}]
    result = forecast(ledger, max_delete_gb_per_day=24)
    assert result["next_quota_at"] == NOW-100+86400


def test_task_status_exposes_live_quota_and_preview_not_delete(monkeypatch):
    import sys
    from app.plugins.smartbrushflow import SmartBrushFlow, BrushTaskConfig
    from app.plugins.smartbrushflow.v9 import TaskConfigV9

    document = TaskConfigV9.model_validate({
        "id":"task", "identity":{"name":"test", "site_id":1, "downloader":"qb"},
        "capacity":{"limit_gb":800}, "deletion":{"enabled":True,"min_seed_hours":48},
    })
    plugin = SmartBrushFlow()
    plugin._task_documents = {"task":document}
    plugin._task_configs = {"task":BrushTaskConfig(document.to_runtime())}
    plugin._runtime = {}
    data = {
        "torrents":{"a":{"size":703*GIB, "title":"seed", "uploaded":0}},
        "capacity_recovery":{"active":True},
        "current_deletion_plan":{"evaluated":[{"hash":"a","size":703*GIB,"action":"candidate"}],
                                 "reason_codes":["daily_count_cap"]},
        "smart_deletions":[{"at":NOW-100,"size":GIB,"status":"confirmed_removed"}],
    }
    monkeypatch.setattr(plugin, "_get_task_data", lambda task_id, key: data.get(key))
    monkeypatch.setattr(sys.modules["app.plugins.smartbrushflow"].time, "time", lambda: NOW)
    summary = plugin._build_strategy_status("task")["ui_summary"]
    assert summary["capacity"]["debt_bytes"] == 0  # Capacity is now only an admission ceiling.
    assert summary["deletion"]["performance_driven"] is True
    assert "quota" not in summary["deletion"]
    assert "preview_cleanup" in [action["code"] for action in summary["recommended_actions"]]
    document.deletion.observation_until = NOW+3600
    plugin._task_configs["task"] = BrushTaskConfig(document.to_runtime())
    assert "preview_cleanup" not in [action["code"] for action in plugin._build_strategy_status("task")["ui_summary"]["recommended_actions"]]

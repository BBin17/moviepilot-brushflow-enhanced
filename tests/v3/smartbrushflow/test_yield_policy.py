from copy import deepcopy

import pytest

from app.plugins.smartbrushflow import SmartBrushFlow, BrushTaskConfig
from app.plugins.smartbrushflow.deletion_service import DeletionService, hard_safety_reasons
from app.plugins.smartbrushflow.decision import candidate_score
from app.plugins.smartbrushflow.learning import measure_upload_window, winsorize, predict_yield, feature_key
from app.plugins.smartbrushflow.operations import TaskService
from app.plugins.smartbrushflow.performance import performance_rows, summarize_performance
from app.plugins.smartbrushflow.repository import TaskRepository
from app.plugins.smartbrushflow.v9 import TaskConfigV9, migrate_yield_policy
from app.plugins.smartbrushflow.health_service import DownloadHealthService
from app.plugins.smartbrushflow.download_health import DownloadHealthPolicy


GIB = 1024 ** 3
NOW = 1_000_000.0


class Storage:
    def __init__(self):
        self.data = {}

    def get_data(self, key):
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        self.data[key] = deepcopy(value)


class Adapter:
    def __init__(self, rows):
        self.rows = rows
        self.removals = []

    def snapshot(self):
        return deepcopy(self.rows)

    def remove(self, torrent_hash, *, delete_data):
        self.removals.append((torrent_hash, delete_data))
        self.rows.pop(torrent_hash)
        return "accepted"


def setup_service(*, shadow=False):
    doc = TaskConfigV9.model_validate({
        "id": "task", "identity": {"name": "测试", "site_id": 1, "downloader": "qb", "tag": "tag"},
        "capacity": {"limit_gb": 100},
        "deletion": {"enabled": True, "min_seed_hours": 24, "observation_until": NOW + 48 * 3600 if shadow else None},
    })
    rows = {
        "quiet": {"hash": "quiet", "total_size": 2 * GIB, "completed": 2 * GIB,
                  "uploaded": 100, "upload_speed": 0, "active_peers": 0, "leechers": 5,
                  "seeders": 50, "seeding_time": 72 * 3600, "iatime": 48 * 3600, "tags": "tag"},
        "protected": {"hash": "protected", "total_size": 99 * GIB, "completed": 99 * GIB,
                      "uploaded": 100, "upload_speed": 0, "active_peers": 0, "leechers": 0,
                      "seeders": 50, "seeding_time": 72 * 3600, "iatime": 48 * 3600, "tags": "tag"},
    }
    records = {key: {"size": row["total_size"], "uploaded": 100, "hit_and_run": key == "protected"} for key, row in rows.items()}
    repository = TaskRepository(Storage())
    repository.save("task", "torrents", records)
    repository.save("task", "learning_state", {"snapshots": [
        {"hash": key, "at": NOW - hour * 3600, "uploaded": 100, "size": row["total_size"]}
        for key, row in rows.items() for hour in range(26)
    ]})
    repository.save("task", "smart_history", [
        {"hash": key, "at": NOW - minutes * 60, "uploaded": 100, "leechers": row["leechers"], "low_value": True}
        for key, row in rows.items() for minutes in (45, 30, 15)
    ])
    adapter = Adapter(rows)
    service = DeletionService(repository=repository, operations=TaskService(repository, clock=lambda: NOW),
                              adapter=adapter, document=doc, managed_tag="tag", clock=lambda: NOW, sleep=lambda _: None)
    return service, adapter


def test_tracker_only_demand_expires_after_a_complete_zero_upload_window():
    service, _ = setup_service()
    plan = service.plan()
    quiet = next(row for row in plan["observations"] if row["hash"] == "quiet")
    assert quiet["tracker_demand_stale"] is True
    assert hard_safety_reasons(quiet, service.policy) == []
    assert [row["hash"] for row in plan["items"]] == ["quiet"]


@pytest.mark.parametrize("field,value,reason", [
    ("uploaded", 101, "real_upload"), ("upload_speed", 1, "real_upload"),
    ("active_peers", 1, "active_connection"), ("active_peers", None, "safety_data_unknown"),
    ("seeding_time", 1, "min_seed_time"), ("completed", 100, "incomplete"),
])
def test_actual_activity_and_permanent_safety_override_stale_tracker(field, value, reason):
    service, adapter = setup_service()
    adapter.rows["quiet"][field] = value
    quiet = next(row for row in service.plan()["observations"] if row["hash"] == "quiet")
    assert reason in hard_safety_reasons(quiet, service.policy)


def test_partial_or_interrupted_history_cannot_expire_tracker_protection():
    service, _ = setup_service()
    learning = service.read("learning_state")
    learning["snapshots"] = [row for row in learning["snapshots"] if row["at"] >= NOW - 6 * 3600]
    service.write("learning_state", learning)
    plan = service.plan()
    quiet = next(row for row in plan["observations"] if row["hash"] == "quiet")
    assert quiet["tracker_demand_stale"] is False
    assert "trusted_active_demand" in hard_safety_reasons(quiet, service.policy)


def test_upgraded_shadow_plan_does_not_call_downloader_remove():
    service, adapter = setup_service(shadow=True)
    plan = service.sample_and_plan()
    assert plan["items"]
    result = service.operations.submit("task", "check", lambda operation_id: service.execute(operation_id, plan["items"]))
    assert result["deleted_count"] == 0
    assert adapter.removals == []


def test_frozen_candidate_gets_final_upload_recheck():
    service, adapter = setup_service()
    items = service.plan()["items"]
    adapter.rows["quiet"]["uploaded"] += 1
    result = service.operations.submit("task", "check", lambda operation_id: service.execute(operation_id, items))
    assert result["deleted_count"] == 0
    assert adapter.removals == []


def test_measurement_retains_partial_upload_without_claiming_a_complete_window():
    rows = [{"at": NOW - 6 * 3600, "uploaded": 0}]
    value = measure_upload_window(rows, uploaded=GIB, now=NOW)
    assert value["delta"] == GIB
    assert value["coverage_hours"] == 6
    assert value["complete"] is False


def test_counter_reset_or_large_gap_is_not_proof_of_zero_upload():
    rows = [{"at": NOW - hour * 3600, "uploaded": 100} for hour in range(26)]
    assert measure_upload_window(rows, uploaded=100, now=NOW)["complete"]
    assert not measure_upload_window(rows, uploaded=0, now=NOW)["complete"]
    assert not measure_upload_window(rows[::4], uploaded=100, now=NOW)["complete"]


def test_zero_history_can_learn_again_and_sparse_feature_bucket_is_not_fully_confident():
    assert winsorize(1.0, [0] * 100) == 1.0
    assert winsorize(0.0, [1] * 100) == 0.0
    candidate = {"size": GIB, "joined_at": NOW}
    state = {"sample_count": 100000, "features": {feature_key(candidate): {"count": 1, "ewma": 1}, "__all__": {"ewma": .1}}}
    assert predict_yield(state, candidate)["confidence"] == .05


def test_aggressive_selection_does_not_fill_space_with_big_competed_seeds():
    candidate = {"size": 80 * GIB, "seeders": 1000, "leechers": 1, "downloadvolumefactor": 0}
    assert not candidate_score(candidate, profile="aggressive").accepted
    candidate.update(size=210 * GIB, leechers=1000)
    assert not candidate_score(candidate, profile="aggressive", task_capacity_bytes=800 * GIB).accepted
    candidate.update(size=5 * GIB)
    heavily_competed = candidate_score(candidate)
    candidate.update(seeders=10)
    assert candidate_score(candidate).score > heavily_competed.score


def test_policy_migration_preserves_settings_backup_and_only_observes_once():
    original = TaskConfigV9.model_validate({"id": "one", "identity": {"name": "任务", "site_id": 1, "downloader": "qb"},
        "capacity": {"limit_gb": 800}, "deletion": {"enabled": True, "min_seed_hours": 72, "delete_data": False},
        "selection": {"size_min_gb": .5, "size_max_gb": 60}}).model_dump(mode="json")
    original["strategy"]["overrides"].pop("tracker_demand_grace_hours")
    rows, backups, changed = migrate_yield_policy([original], now=NOW)
    assert changed and backups["one"]["config"] == original
    assert rows[0]["deletion"]["min_seed_hours"] == 72
    assert rows[0]["deletion"]["delete_data"] is False
    assert rows[0]["selection"] == original["selection"]
    assert rows[0]["deletion"]["observation_until"] == NOW + 48 * 3600
    assert migrate_yield_policy(rows, backups, now=NOW + 100) == (rows, backups, False)
    original["deletion"]["enabled"] = False
    rows, _, _ = migrate_yield_policy([original], now=NOW)
    assert rows[0]["deletion"]["enabled"] is False
    assert rows[0]["deletion"]["observation_until"] is None


def test_income_statistics_and_filtering_preserve_hashes_and_minimum_seed_time():
    rows = {"real-hash": {"title": "old", "time": NOW - 100000, "size": GIB, "uploaded": 100,
                         "seeding_time": 72 * 3600, "download_completed_bytes": GIB},
            "new-hash": {"title": "new", "time": NOW, "size": GIB, "uploaded": 0,
                        "seeding_time": 1, "download_completed_bytes": GIB}}
    learning = {"snapshots": [{"hash": "real-hash", "at": NOW - hour * 3600, "uploaded": 100} for hour in range(26)]}
    diagnostics = summarize_performance(performance_rows(rows, learning, min_seed_hours=72, now=NOW))
    assert diagnostics["zero_upload_count"] == 1
    assert diagnostics["minimum_pending_count"] == 1
    plugin = object.__new__(SmartBrushFlow)
    plugin._task_configs = {"task": BrushTaskConfig({"id": "task", "min_seed_time": 72})}
    plugin._get_task_data = lambda task_id, name: rows if name == "torrents" else learning if name == "learning_state" else {}
    # Use a recent real-time dataset for the actual API paginator's clock.
    import time
    offset = time.time() - NOW
    for row in learning["snapshots"]:
        row["at"] += offset
    result = plugin._paginate_task_torrents("task", filter="zero_upload", sort="size")
    assert result["total"] == 1
    assert result["items"][0]["hash"] == "real-hash"


def test_overdue_and_auto_paused_downloads_are_visible_in_health_summary():
    data = {}
    rows = {"x": {"time": NOW - 72 * 3600}}
    service = DownloadHealthService(downloader=None, read=lambda key, default=None: data.get(key, default),
        write=lambda key, value: data.__setitem__(key, value), identify=lambda row: row["hash"], normalize=dict,
        notify=lambda *_: None, policy=DownloadHealthPolicy(max_download_hours=48), clock=lambda: NOW)
    service.observe([{"hash": "x", "total_size": 1000, "completed": 500, "downloaded": 500}], rows)
    summary = service.summarize(rows)
    assert rows["x"]["download_overdue"]
    assert summary["overdue_count"] == 1 and summary["issue_count"] == 1
    rows["x"].update(download_health="paused", download_health_auto_paused=True)
    assert service.summarize(rows)["issue_count"] == 1

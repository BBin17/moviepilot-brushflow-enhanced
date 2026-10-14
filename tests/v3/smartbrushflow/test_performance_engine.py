from copy import deepcopy
from dataclasses import replace

import pytest

from app.plugins.smartbrushflow.decision import SmartPolicy, evaluate_candidate, select_deletions
from app.plugins.smartbrushflow.deletion_service import DeletionService, policy_for_document
from app.plugins.smartbrushflow.operations import TaskService
from app.plugins.smartbrushflow.repository import TaskRepository
from app.plugins.smartbrushflow.v9 import TaskConfigV9, migrate_performance_policy


GIB = 1024**3
NOW = 2_000_000.0


def seed(**changes):
    return {"hash":"idle", "total_size":210*GIB, "progress":100, "seeding_time":100*3600,
            "inactive_time":96*3600, "active_peers":0, "upload_speed":0,
            "upload_window_observed_24h":True, "idle_zero_upload":True,
            "low_value_confirmations":3, "low_value_span_minutes":60, **changes}


def performance_policy(**changes):
    return replace(SmartPolicy(min_seed_time_hours=48, performance_driven=True, max_delete_percent_day=0,
                               max_delete_capacity_percent_run=0, max_delete_capacity_percent_day=0), **changes)


def test_idle_seed_is_pruned_below_capacity_target_without_gb_or_day_caps():
    result = select_deletions([seed()], performance_policy(), current_size=210*GIB, disk_limit=800*GIB,
                             deleted_today=100, deleted_today_bytes=10000*GIB)
    assert not result.pressure
    assert result.selected[0].torrent_hash == "idle"
    assert result.selected[0].reason_codes == ("long_zero_upload",)
    assert result.run_byte_cap == result.daily_byte_cap == 0


@pytest.mark.parametrize("changes,reason", [
    ({"seeding_time":47*3600}, "min_seed_time"), ({"hit_and_run":True}, "hit_and_run"),
    ({"progress":50}, "incomplete"), ({"upload_speed":1}, "real_upload"),
    ({"upload_delta_since_check":1}, "real_upload"), ({"active_peers":1}, "active_connection"),
    ({"tags":["keep"]}, "excluded_tag"),
])
def test_no_performance_rule_can_override_minimum_seeding_or_other_guards(changes, reason):
    result = evaluate_candidate(seed(**changes), performance_policy(excluded_tags=("keep",)))
    assert result.action == "blocked" and reason in result.reason_codes


def test_minimum_seeding_longer_than_idle_threshold_still_wins():
    assert evaluate_candidate(seed(), performance_policy(min_seed_time_hours=168)).reason_codes == ("min_seed_time",)


def test_zero_upload_does_not_skip_required_72_hour_window_or_confirmation():
    assert evaluate_candidate(seed(idle_zero_upload=False), performance_policy()).action == "keep"
    assert evaluate_candidate(seed(seeding_time=71*3600), performance_policy()).action == "keep"
    assert evaluate_candidate(seed(low_value_confirmations=1), performance_policy()).action == "watch"
    assert evaluate_candidate(seed(upload_window_observed_24h=False), performance_policy()).action == "keep"


def test_idle_rule_uses_real_evidence_not_predicted_potential():
    assert evaluate_candidate(seed(seeders=0, learned_potential=15), performance_policy(score_threshold=1)).eligible


class Storage:
    def __init__(self):
        self.data = {}
    def get_data(self, key):
        return deepcopy(self.data.get(key))
    def save_data(self, key, value):
        self.data[key] = deepcopy(value)


class Adapter:
    def __init__(self, repository):
        self.repository = repository
        self.removals = []
        self.rows = {"idle":{"hash":"idle", "total_size":210*GIB, "completed":210*GIB, "uploaded":100,
                             "upload_speed":0, "active_peers":0, "leechers":0, "seeders":40,
                             "seeding_time":100*3600, "iatime":96*3600, "tags":"managed"}}
    def snapshot(self):
        return deepcopy(self.rows)
    def remove(self, torrent_hash, *, delete_data):
        assert any(row.get("kind") == "deletion_request" for row in self.repository.get("task", "decision_audit", []))
        self.removals.append((torrent_hash, delete_data))
        self.rows.pop(torrent_hash)
        return "accepted"


def service(*, shadow=False, minimum=48):
    document = TaskConfigV9.model_validate({"id":"task", "identity":{"name":"test","site_id":1,"downloader":"qb"},
        "capacity":{"limit_gb":800}, "deletion":{"enabled":True,"min_seed_hours":minimum,
        "observation_until":NOW+3600 if shadow else None},
        "strategy":{"profile":"custom","overrides":{"max_release_gb_run":1,"max_release_gb_day":1}}})
    repository = TaskRepository(Storage())
    repository.save("task", "torrents", {"idle":{"size":210*GIB,"uploaded":100}})
    repository.save("task", "learning_state", {"snapshots":[{"hash":"idle","at":NOW-h*3600,"uploaded":100} for h in range(74)]})
    repository.save("task", "smart_history", [{"hash":"idle","at":NOW-m*60,"uploaded":100,"leechers":0,"low_value":True} for m in (60,45,30)])
    adapter = Adapter(repository)
    return DeletionService(repository=repository, operations=TaskService(repository, clock=lambda:NOW),
                           adapter=adapter, document=document, managed_tag="managed", clock=lambda:NOW, sleep=lambda _:None), adapter


def test_service_can_execute_after_capacity_target_with_audit_first():
    worker, adapter = service()
    plan = worker.plan()
    assert not plan["recovery"]["active"] and len(plan["items"]) == 1
    worker.operations.submit("task","check",lambda operation_id:worker.execute(operation_id,plan["items"]))
    assert adapter.removals == [("idle",True)]


@pytest.mark.parametrize("change", ["upload", "connection", "short-seeding", "gap", "reset", "unknown"])
def test_service_rechecks_idle_evidence_before_actual_removal(change):
    worker, adapter = service()
    items = worker.plan()["items"]
    if change == "upload":
        adapter.rows["idle"]["uploaded"] += 1
    elif change == "connection":
        adapter.rows["idle"]["active_peers"] = 1
    elif change == "short-seeding":
        adapter.rows["idle"]["seeding_time"] = 1
    elif change == "unknown":
        adapter.rows["idle"]["seeding_time"] = None
    elif change == "reset":
        adapter.rows["idle"]["uploaded"] = 0
    else:
        learning = worker.read("learning_state")
        learning["snapshots"] = learning["snapshots"][::4]
        worker.write("learning_state",learning)
    worker.operations.submit("task","check",lambda operation_id:worker.execute(operation_id,items))
    assert adapter.removals == []


def test_observation_still_prevents_real_deletion():
    worker, adapter = service(shadow=True)
    plan = worker.plan()
    worker.operations.submit("task","check",lambda operation_id:worker.execute(operation_id,plan["items"]))
    assert adapter.removals == []


def test_factory_ignores_old_capacity_release_settings():
    worker, _ = service()
    policy = policy_for_document(worker.document)
    assert policy.performance_driven and policy.max_delete_percent_day == 0
    assert policy.max_delete_gb_per_run == policy.max_delete_gb_per_day == 0


def test_migration_preserves_closed_tasks_and_safety_with_idempotent_backup():
    row = {"id":"a","identity":{"name":"test","site_id":1,"downloader":"qb"},
           "deletion":{"enabled":False,"min_seed_hours":168,"delete_data":False,"paused":True}}
    rows, backups, changed = migrate_performance_policy([row],now=NOW)
    assert changed and backups["a"]["config"] == row
    assert rows[0]["deletion"]["enabled"] is False
    assert rows[0]["deletion"]["min_seed_hours"] == 168
    assert rows[0]["deletion"]["delete_data"] is False
    assert migrate_performance_policy(rows,backups,now=NOW+100) == (rows,backups,False)

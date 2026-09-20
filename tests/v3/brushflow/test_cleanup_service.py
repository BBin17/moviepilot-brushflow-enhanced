from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.plugins.brushflow.deletion_service import DeletionService, GIB
from app.plugins.brushflow.downloaders import DownloaderAdapter
from app.plugins.brushflow.operations import OperationError, TaskService
from app.plugins.brushflow.repository import TaskRepository
from app.plugins.brushflow.v9 import TaskConfigV9
from support.downloaders import FakeDownloader, FakeQbClient
from test_operations import MemoryStorage


def setup(*, count=20, observation_until=None, delete_data=True):
    now = [10000.0]
    document = TaskConfigV9.model_validate({
        "id": "one", "revision": 3, "identity": {"name": "Test", "site_id": 1, "downloader": "qb"},
        "capacity": {"limit_gb": 100},
        "deletion": {"enabled": True, "min_seed_hours": 24, "delete_data": delete_data, "observation_until": observation_until},
    })
    records = {}
    snapshot = []
    for index in range(count + 1):
        size = 80 * GIB if index == count else 2 * GIB
        key = f"seed-{index}"
        records[key] = {"hash": key, "title": key, "size": size, "time": 100, "hit_and_run": index == count}
        snapshot.append({"hash": key, "title": key, "total_size": size, "completed": size, "downloaded": size,
                         "seeding_time": 72 * 3600, "iatime": 12 * 3600, "upload_speed": 0, "uploaded": 0,
                         "active_peers": 0, "leechers": 0, "seeders": 50, "tags": "brush-test"})
    storage = MemoryStorage()
    repository = TaskRepository(storage)
    repository.save("one", "torrents", records)
    repository.save("one", "smart_history", [{"hash": key, "at": at, "uploaded": 0, "leechers": 0, "low_value": True}
                                              for key in records for at in (8000, 9000, 9900)])
    operations = TaskService(repository, clock=lambda: now[0])
    downloader = FakeDownloader(snapshot, client=FakeQbClient())
    adapter = DownloaderAdapter(downloader, normalize=dict, identify=lambda row: row["hash"])
    cleanup = DeletionService(repository=repository, operations=operations, adapter=adapter, document=document,
                              clock=lambda: now[0], sleep=lambda _: None)
    return cleanup, storage, downloader, now


def run(cleanup, preview):
    return cleanup.operations.submit(cleanup.task_id, "cleanup",
        lambda operation_id: cleanup.execute(operation_id, preview["items"], relax_limits=preview["relax_limits"], manual=True))


def test_preview_only_stores_token_and_never_changes_evidence():
    cleanup, storage, downloader, _ = setup()
    before = deepcopy(storage.data)
    storage.writes.clear()
    preview = cleanup.preview()
    assert preview["allowed"]
    assert storage.writes == ["task.one.cleanup_previews"]
    for key, value in before.items():
        assert storage.data[key] == value
    assert downloader.qbc.calls == []
    assert all(row[0] == "get_torrents" for row in downloader.calls)


def test_scheduled_plan_persists_full_evaluation_for_protection_summary():
    cleanup, _, _, _ = setup()
    cleanup.sample_and_plan()
    plan = cleanup.read("current_deletion_plan")
    assert plan["aggregate"]["candidate_count"] + plan["aggregate"]["protected_count"] == 21
    assert len(plan["evaluated"]) == 21
    assert any(row["action"] == "blocked" and "hit_and_run" in row["reason_codes"] for row in plan["evaluated"])
    assert all("size" in row and "contributions" in row for row in plan["evaluated"])
    audit = cleanup.read("decision_audit")[-1]
    assert audit["kind"] == "deletion"
    assert len(audit["evaluated"]) == 21


def test_preview_does_not_supply_a_third_confirmation():
    cleanup, _, _, _ = setup()
    rows = cleanup.read("smart_history")
    cleanup.write("smart_history", [row for row in rows if row["at"] != 9000])
    assert not cleanup.preview()["items"]
    cleanup.sample_and_plan()
    assert cleanup.preview()["items"]


def test_minutely_checks_reach_span_after_compaction_but_protection_resets_it():
    cleanup, _, downloader, now = setup()
    cleanup.document.schedule.check_interval = 1
    cleanup.write("smart_history", [])
    for minute in range(41):
        now[0] = 10000 + minute * 60
        cleanup.sample_and_plan()
        if minute < 30:
            assert not cleanup.preview()["items"]
    assert cleanup.preview()["items"]
    assert len(cleanup.read("smart_history")) <= 12 * 21
    key = "seed-0"
    downloader.torrents[key]["upload_speed"] = 1
    now[0] += 60
    cleanup.sample_and_plan()
    downloader.torrents[key]["upload_speed"] = 0
    now[0] += 60
    cleanup.sample_and_plan()
    observation = next(row for row in cleanup.plan()["observations"] if row["hash"] == key)
    assert observation["low_value_confirmations"] == 1
    assert observation["low_value_span_minutes"] == 0


def test_long_gap_breaks_compacted_confirmation_run():
    cleanup, _, _, now = setup()
    cleanup.sample_and_plan()
    now[0] += 3601
    cleanup.sample_and_plan()
    assert not cleanup.preview()["items"]


def test_audit_failure_stops_before_any_downloader_mutation(monkeypatch):
    cleanup, _, downloader, _ = setup()
    preview = cleanup.preview()
    def fail(_):
        raise OSError("audit disk unavailable")
    monkeypatch.setattr(cleanup, "audit", fail)
    result = run(cleanup, preview)
    assert result["state"] != "completed"
    assert not any(call[0] == "delete_torrents" for call in downloader.calls)


def test_preview_observation_bypass_requires_explicit_choice_and_is_bounded():
    cleanup, _, _, _ = setup(observation_until=20000)
    standard = cleanup.preview()
    assert not standard["allowed"]
    assert "observation" in standard["blocked_reasons"]
    override = cleanup.preview(relax_limits=True)
    assert override["allowed"]
    assert len(override["items"]) <= 10
    assert sum(row["size"] for row in override["items"]) <= 25 * GIB
    assert all(row["hash"] != "seed-20" for row in override["items"])


def test_expiry_revision_and_confirmation_are_validated():
    cleanup, _, _, now = setup()
    preview = cleanup.preview()
    payload = SimpleNamespace(preview_id=preview["preview_id"], revision=3, confirm=True, relax_limits=False)
    assert cleanup.validate_preview(payload)["allowed"]
    payload.revision = 2
    with pytest.raises(OperationError, match="改变"):
        cleanup.validate_preview(payload)
    payload.revision = 3
    payload.relax_limits = True
    with pytest.raises(OperationError, match="确认"):
        cleanup.validate_preview(payload)
    payload.relax_limits = False
    now[0] += 301
    with pytest.raises(OperationError, match="过期"):
        cleanup.validate_preview(payload)


def test_execution_is_audited_before_delete_and_confirms_real_removal():
    cleanup, storage, downloader, _ = setup()
    preview = cleanup.preview(relax_limits=True)
    original_remove = downloader.delete_torrents
    def remove(*, ids, delete_file):
        audit = storage.get_data("task.one.decision_audit")
        assert audit[-1]["kind"] == "deletion_request"
        assert audit[-1]["item"]["hash"] == ids[0]
        ledger = cleanup.read("smart_deletions")
        assert any(row["hash"] == ids[0] and row["status"] == "submitting" for row in ledger)
        return original_remove(ids=ids, delete_file=delete_file)
    downloader.delete_torrents = remove
    result = run(cleanup, preview)
    assert result["state"] == "completed"
    assert result["deleted_count"] == len(preview["items"])
    assert result["actual_released_bytes"] is None
    assert result["estimated_released_bytes"] == 20 * GIB
    assert result["display_until"] == 10008
    assert all(row["deleted"] for row in cleanup.read("torrents").values() if row["hash"] in {item["hash"] for item in preview["items"]})


def test_fresh_upload_protects_frozen_candidate_without_replacement():
    cleanup, _, downloader, _ = setup()
    preview = cleanup.preview()
    key = preview["items"][0]["hash"]
    downloader.torrents[key]["uploaded"] = 1
    result = run(cleanup, preview)
    assert result["skipped_count"] == 1
    assert result["deleted_count"] == 0
    assert "real_upload" in result["items"][0]["reason_codes"]
    assert all(row[0] != "delete_torrents" for row in downloader.calls)


def test_missing_activity_is_protected():
    cleanup, _, downloader, _ = setup()
    for row in downloader.torrents.values():
        row["active_peers"] = None
    preview = cleanup.preview(relax_limits=True)
    assert preview["items"] == []
    assert preview["aggregate"]["protected_count"] == 21


def test_retained_data_is_not_counted_as_freed_disk():
    cleanup, _, _, _ = setup(delete_data=False)
    result = run(cleanup, cleanup.preview())
    assert result["deleted_count"] == 1
    assert result["task_bytes_removed"] == 2 * GIB
    assert result["estimated_released_bytes"] == 0
    assert result["actual_released_bytes"] is None


def test_accepted_but_still_present_is_not_completed_and_not_resent():
    cleanup, _, downloader, _ = setup()
    calls = []
    downloader.delete_torrents = lambda **kwargs: calls.append(kwargs) or True
    result = run(cleanup, cleanup.preview())
    assert result["state"] == "pending_confirmation"
    assert result["deleted_count"] == 0
    assert result["display_until"] is None
    preview = cleanup.preview()
    assert result["items"][0]["hash"] not in {row["hash"] for row in preview["items"]}
    cleanup.reconcile()
    assert len(calls) == 1
    downloader.torrents.pop(result["items"][0]["hash"])
    cleanup.reconcile()
    resolved = cleanup.operations.get("one", result["operation_id"])
    assert resolved["deleted_count"] == 1
    assert resolved["display_until"] == 10008
    assert len(calls) == 1


def test_timeout_after_server_removal_is_confirmed_by_readback_once():
    cleanup, _, downloader, _ = setup()
    calls = []
    def timeout(*, ids, delete_file):
        calls.append(ids)
        downloader.torrents.pop(ids[0])
        raise TimeoutError("response lost")
    downloader.delete_torrents = timeout
    result = run(cleanup, cleanup.preview())
    assert result["state"] == "completed"
    assert result["deleted_count"] == 1
    assert len(calls) == 1


def test_host_false_may_be_a_swallowed_timeout_and_is_not_retried():
    cleanup, _, downloader, _ = setup()
    calls = []
    downloader.delete_torrents = lambda **kwargs: calls.append(kwargs) or False
    result = run(cleanup, cleanup.preview())
    assert result["state"] == "pending_confirmation"
    assert result["deleted_count"] == 0
    cleanup.reconcile()
    assert len(calls) == 1


def test_management_tag_removed_after_preview_is_protected():
    cleanup, _, downloader, _ = setup()
    cleanup.managed_tag = "brush-test"
    preview = cleanup.preview()
    downloader.torrents[preview["items"][0]["hash"]]["tags"] = "user-removed"
    result = run(cleanup, preview)
    assert result["deleted_count"] == 0
    assert "management_tag_removed" in result["items"][0]["reason_codes"]


def test_invalid_tracker_cleanup_retains_data_and_cannot_bypass_completion():
    cleanup, _, downloader, _ = setup()
    preview = cleanup.preview()
    item = {**preview["items"][0], "kind": "invalid_tracker", "delete_data": False}
    downloader.torrents[item["hash"]]["completed"] = 1
    result = cleanup.operations.submit("one", "check", lambda operation_id: cleanup.execute(operation_id, [item], invalid_revalidator=lambda _: True))
    assert result["deleted_count"] == 0
    assert "incomplete" in result["items"][0]["reason_codes"]
    assert all(row[0] != "delete_torrents" for row in downloader.calls)


def test_progress_is_running_until_all_frozen_items_are_processed():
    cleanup, _, downloader, _ = setup()
    preview = cleanup.preview(relax_limits=True)
    original = downloader.delete_torrents
    def remove(**kwargs):
        current = cleanup.operations.latest("one")
        assert current["state"] == "running"
        return original(**kwargs)
    downloader.delete_torrents = remove
    result = run(cleanup, preview)
    assert result["state"] == "completed"

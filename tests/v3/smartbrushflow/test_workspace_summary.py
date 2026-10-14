from copy import deepcopy

from app.plugins.smartbrushflow import BrushTaskConfig, SmartBrushFlow
from app.plugins.smartbrushflow.v9 import TaskConfigV9

GIB = 1024**3


def workspace(monkeypatch):
    document = TaskConfigV9.model_validate({
        "id": "task", "identity": {"name": "test", "site_id": 1, "downloader": "qb"},
        "capacity": {"limit_gb": 800}, "deletion": {"enabled": True, "min_seed_hours": 72},
    })
    plugin = SmartBrushFlow()
    plugin._task_documents = {"task": document}
    plugin._task_configs = {"task": BrushTaskConfig(document.to_runtime())}
    plugin._runtime = {}
    data = {
        "torrents": {
            "a": {"title": "candidate a", "size": 10*GIB},
            "c": {"title": "candidate c", "size": 20*GIB},
            "b": {"title": "protected b", "size": 8*GIB},
            "gone": {"size": 50*GIB, "deleted": True},
        },
        "current_deletion_plan": {
            "engine_mode": "performance", "at": 1800000000,
            "evaluated": [
                {"hash": "a", "action": "candidate", "size": 10*GIB},
                {"hash": "c", "action": "candidate", "size": 20*GIB},
                {"hash": "b", "action": "keep", "reason_codes": ["min_seed_time"]},
                {"hash": "b", "action": "keep", "reason_codes": ["min_seed_time"]},
                {"hash": "gone", "action": "candidate", "size": 50*GIB},
                {"hash": "missing", "action": "keep", "size": 100*GIB},
            ],
            "items": [{"hash": "a", "size": 10*GIB, "delete_data": True},
                      {"hash": "gone", "size": 50*GIB, "delete_data": True}],
            "estimated_freed_bytes": 60*GIB,
        },
    }
    monkeypatch.setattr(plugin, "_get_task_data", lambda task_id, key: data.get(key))
    return plugin, data


def test_current_workspace_excludes_removed_seeds_and_exposes_unique_protection(monkeypatch):
    plugin, data = workspace(monkeypatch)
    original = deepcopy(data)
    strategy = plugin._build_strategy_status("task")
    deletion = strategy["ui_summary"]["deletion"]
    assert deletion["candidate_count"] == 2
    assert deletion["candidate_bytes"] == 30*GIB
    assert deletion["next_batch_bytes"] == 10*GIB
    assert deletion["next_batch_count"] == 1
    assert deletion["protected_count"] == 1
    assert deletion["protected_bytes"] == 8*GIB
    assert strategy["protected_items"] == [{
        "hash": "b", "title": "protected b", "size": 8*GIB, "reasons": ["min_seed_time"],
    }]
    assert strategy["evaluation_at"] == 1800000000
    assert {item["hash"] for item in strategy["pending_candidates"]} == {"a", "c"}
    assert data == original  # Display generation never edits historical evidence.


def test_run_history_pages_without_changing_data_or_task_config(monkeypatch):
    plugin, data = workspace(monkeypatch)
    data["runs"] = [{"id": str(index)} for index in range(62)]
    original = deepcopy(data)
    page = plugin.get_task_events("task", page=2, page_size=20).data
    assert page["total"] == 62
    assert page["page"] == 2
    assert [row["id"] for row in page["items"]] == [str(index) for index in range(20, 40)]
    assert data == original
    assert plugin._task_documents["task"].deletion.min_seed_hours == 72


def test_protected_and_candidate_seed_filters_use_current_plan_only(monkeypatch):
    plugin, data = workspace(monkeypatch)
    protected = plugin._paginate_task_torrents("task", filter="protected")
    assert protected["total"] == 1
    assert protected["items"][0]["hash"] == "b"
    assert protected["items"][0]["retention_reasons"] == ["min_seed_time"]
    assert protected["items"][0]["retention_labels"]
    candidates = plugin._paginate_task_torrents("task", filter="candidates")
    assert {row["hash"] for row in candidates["items"]} == {"a", "c"}
    assert plugin._paginate_task_torrents("task", state="deleted", filter="candidates")["total"] == 0
    data["current_deletion_plan"]["engine_mode"] = "legacy"
    assert plugin._paginate_task_torrents("task", filter="protected")["total"] == 0

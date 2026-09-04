"""需要 MoviePilot 测试环境的 9.0 统一 API 与守门测试。"""

import threading
import time
from types import SimpleNamespace

from app.plugins.brushflow import BrushFlow, BrushTaskConfig
from app.plugins.brushflow.v9 import migrate_v8_task


def make_plugin(task):
    plugin = object.__new__(BrushFlow)
    plugin._task_configs = {task.id: task}
    plugin._task_documents = {task.id: migrate_v8_task(task.to_dict())}
    plugin._task_locks = {task.id: threading.Lock()}
    plugin._runtime_lock = threading.Lock()
    plugin._runtime = {task.id: {"state": "idle", "operation": None, "last_error": None}}
    plugin._save_config = lambda: None
    plugin._append_decision_audit = lambda *_: None
    plugin._build_task_overview = lambda task_id: {"task": plugin._task_configs[task_id].to_dict()}
    return plugin


def smart_task(**overrides):
    return BrushTaskConfig(
        {
            "id": "smart-api",
            "name": "Coffee",
            "site_id": 1,
            "downloader": "qb",
            "min_seed_time": 48,
            "smart_enabled": True,
            "smart_shadow_until": time.time() + 48 * 3600,
            **overrides,
        }
    )


def test_strategy_api_routes_are_registered():
    paths = {row["path"] for row in object.__new__(BrushFlow).get_api()}
    assert "/tasks/{task_id}/actions/{action}" in paths
    assert "/tasks/{task_id}/strategy/rollback" not in paths
    assert "/tasks/{task_id}/run" not in paths
    assert "/tasks/{task_id}/check" not in paths


def test_strategy_operation_respects_task_lock():
    task = smart_task()
    plugin = make_plugin(task)
    plugin._task_locks[task.id].acquire()
    try:
        response = plugin.run_task_action(task.id, "activate_deletion")
    finally:
        plugin._task_locks[task.id].release()
    assert response.success is False
    assert "执行" in response.message


def test_false_positive_gate_auto_extends_shadow():
    task = smart_task(smart_shadow_until=time.time() - 1)
    plugin = make_plugin(task)
    candidates = {
        str(index): {
            "hash": str(index),
            "planned_at": time.time() - 25 * 3600,
            "uploaded": 0,
            "recovered": index < 2,
        }
        for index in range(10)
    }
    store = {
        "smart_candidates": candidates,
        "strategy_state": {"hard_safety_violations": 0},
    }
    plugin._get_task_data = lambda task_id, name: store.get(name)
    plugin._save_task_data = lambda task_id, name, value: store.__setitem__(name, value)
    selection = SimpleNamespace(selected=(), estimated_freed_bytes=0)
    state = plugin._update_smart_strategy_state(
        task,
        [],
        [],
        selection,
        {"confidence": 0, "sample_count": 0},
        {},
    )
    assert state["mode"] == "shadow"
    assert task.smart_shadow_until > time.time()
    assert task.smart_shadow_extensions == 1


def test_strategy_status_summarizes_capacity_and_protection():
    gib = 1024**3
    task = smart_task(disksize=100, smart_shadow_until=None)
    plugin = make_plugin(task)
    store = {
        "strategy_state": {},
        "learning_state": {},
        "smart_candidates": {},
        "smart_deletions": [],
        "decision_audit": [
            {
                "kind": "deletion",
                "evaluated": [
                    {
                        "hash": "protected",
                        "size": 10 * gib,
                        "action": "keep",
                        "reasons": ["min_seed_time"],
                    }
                ],
                "selected": [],
                "reason_codes": ["no_low_value_candidate"],
            }
        ],
        "torrents": {
            "protected": {"size": 10 * gib},
            "other": {"size": 120 * gib},
        },
    }
    plugin._get_task_data = lambda task_id, name: store.get(name)

    strategy = plugin._build_strategy_status(task.id)

    assert strategy["capacity_bytes"] == 100 * gib
    assert strategy["capacity_debt_bytes"] == 45 * gib
    assert strategy["deletion_readiness"]["state"] == "blocked"
    assert strategy["deletion_blockers"] == [
        {
            "code": "min_seed_time",
            "label": "尚未达到站点最低保种时长",
            "count": 1,
            "bytes": 10 * gib,
        }
    ]

"""BrushFlow 9.0嵌套任务模型与迁移测试。"""

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "brushflow" / "v9.py"
SPEC = importlib.util.spec_from_file_location("brushflow_v9_migration", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)
TaskConfigV9 = module.TaskConfigV9
migrate_task_rows_v9 = module.migrate_task_rows_v9
migrate_v8_task = module.migrate_v8_task


def legacy_task(**overrides):
    return {
        "id": "coffee",
        "name": "咖啡",
        "site_id": 1,
        "downloader": "qb",
        "enabled": True,
        "smart_enabled": True,
        "disksize": 200,
        "min_seed_time": 72,
        "size": "0.5-80",
        "freeleech": "free",
        "delete_files": True,
        **overrides,
    }


def test_migration_preserves_safety_and_enters_observation():
    task = migrate_v8_task(legacy_task(), now=1000)
    assert task.schema_version == 9
    assert task.selection.size_min_gb == 0.5
    assert task.selection.size_max_gb == 80
    assert task.deletion.enabled is True
    assert task.deletion.min_seed_hours == 72
    assert task.deletion.observation_until == 1000 + 48 * 3600
    assert task.strategy.profile == "balanced"
    runtime = task.to_runtime()
    assert runtime["smart_enabled"] is True
    assert "proxy_delete" not in runtime
    assert runtime["delete_files"] is True


def test_missing_capacity_disables_deletion_instead_of_guessing():
    task = migrate_v8_task(legacy_task(disksize=None), now=1000)
    assert task.deletion.enabled is False
    assert task.deletion.paused is True


def test_dynamic_or_condition_delete_maps_to_unified_observation():
    dynamic = migrate_v8_task(legacy_task(smart_enabled=False, proxy_delete=True), now=1000)
    conditional = migrate_v8_task(legacy_task(smart_enabled=False, seed_time=72), now=1000)
    assert dynamic.deletion.enabled is True
    assert conditional.deletion.enabled is True
    assert dynamic.deletion.observation_until == 1000 + 48 * 3600


def test_disabled_delete_stays_disabled_and_explicit_data_choice_is_preserved():
    task = migrate_v8_task(
        legacy_task(smart_enabled=False, proxy_delete=False, delete_files=False),
        now=1000,
    )
    assert task.deletion.enabled is False
    assert task.deletion.delete_data is False
    assert task.deletion.observation_until is None


def test_migration_is_idempotent_and_backup_is_immutable():
    rows, backups, changed = migrate_task_rows_v9([legacy_task()], {}, now=1000)
    assert changed is True
    assert backups["coffee"]["config"]["name"] == "咖啡"
    second_rows, second_backups, second_changed = migrate_task_rows_v9(rows, backups, now=2000)
    assert second_changed is False
    assert TaskConfigV9.model_validate(second_rows[0]).revision == 1
    assert second_backups == backups


def test_preset_mismatch_is_normalized_to_custom_without_touching_safety():
    task = migrate_v8_task(legacy_task(), now=1000)
    payload = task.model_dump(mode="json")
    payload["strategy"]["profile"] = "balanced"
    payload["strategy"]["overrides"]["max_add_per_run"] = 99
    normalized = TaskConfigV9.model_validate(payload)
    assert normalized.strategy.profile == "custom"
    assert normalized.deletion.min_seed_hours == 72
    assert normalized.deletion.delete_data is True

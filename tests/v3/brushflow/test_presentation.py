"""BrushFlow 9.0 健康状态优先级测试。"""

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "brushflow" / "presentation.py"
SPEC = importlib.util.spec_from_file_location("brushflow_presentation", MODULE_PATH)
presentation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = presentation
SPEC.loader.exec_module(presentation)


def _summary(**overrides):
    values = {
        "runtime_error": None, "configuration_issue": False, "severe_capacity": False, "capacity_percent": 80,
        "download": {}, "mode": "active", "shadow_remaining_seconds": 0,
        "capacity_pressure": False, "readiness_message": "无需清理", "task_enabled": True,
    }
    values.update(overrides)
    return presentation.build_health_summary(**values)


def test_runtime_error_wins_over_every_other_state():
    result = _summary(runtime_error="boom", severe_capacity=True, download={"stalled_count": 2}, mode="shadow")
    assert result["health"]["status"] == "runtime_error"


def test_capacity_wins_over_download_and_observation():
    result = _summary(severe_capacity=True, download={"stalled_count": 2}, mode="shadow")
    assert result["health"]["status"] == "severe_capacity"


def test_missing_safety_config_is_visible_before_normal_state():
    result = _summary(configuration_issue=True)
    assert result["health"]["status"] == "configuration_required"
    assert result["recommended_actions"][0]["code"] == "open_editor"


def test_download_wins_over_observation_and_uses_safe_retry():
    result = _summary(download={"slow_count": 1}, mode="shadow")
    assert result["health"]["status"] == "download_issue"
    assert result["recommended_actions"][0]["code"] == "retry_stalled"


def test_observation_wins_over_normal_capacity_pressure():
    result = _summary(mode="shadow", capacity_pressure=True)
    assert result["health"]["status"] == "observation"


def test_paused_and_healthy_are_distinct():
    assert _summary(task_enabled=False)["health"]["status"] == "task_paused"
    assert _summary()["health"]["status"] == "healthy"

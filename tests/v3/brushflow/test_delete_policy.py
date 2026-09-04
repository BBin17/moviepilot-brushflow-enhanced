"""BrushFlow 9.0 统一删种策略回归测试。"""

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "brushflow" / "decision.py"
SPEC = importlib.util.spec_from_file_location("brushflow_decision_delete_policy", MODULE_PATH)
decision = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = decision
SPEC.loader.exec_module(decision)


def _seed(**overrides):
    row = {
        "hash": "seed", "total_size": 20 * 1024**3, "downloaded": 20 * 1024**3,
        "progress": 100, "seeding_time": 80 * 3600, "iatime": 12 * 3600,
        "upspeed": 0, "avg_upspeed": 0, "uploaded": 0,
        "active_peers": 0, "num_leechs": 0, "hit_and_run": False,
    }
    row.update(overrides)
    return row


def _policy(**overrides):
    values = {
        "min_seed_time_hours": 72, "score_threshold": 40,
        "low_value_confirmations": 3, "low_value_span_minutes": 30,
        "max_delete_percent_day": 100, "max_delete_capacity_percent_run": 100,
        "max_delete_capacity_percent_day": 100,
    }
    values.update(overrides)
    return decision.SmartPolicy(**values)


def test_unfinished_and_hr_are_permanently_protected():
    unfinished = decision.evaluate_candidate(_seed(downloaded=1, progress=5), _policy())
    hit_and_run = decision.evaluate_candidate(_seed(hit_and_run=True), _policy())
    assert unfinished.action == "blocked"
    assert hit_and_run.action == "blocked"


def test_minimum_site_seed_time_is_a_hard_floor():
    result = decision.evaluate_candidate(_seed(seeding_time=24 * 3600), _policy())
    assert result.action == "blocked"
    assert "min_seed_time" in result.reason_codes


def test_equal_value_prefers_larger_capacity_release():
    history = []
    for at in (0, 1800, 3600):
        history.extend([{ "at": at, "hash": key, "low_value": True, "uploaded": 0 } for key in ("small", "large")])
    result = decision.select_deletions(
        [_seed(hash="small", total_size=5 * 1024**3), _seed(hash="large", total_size=50 * 1024**3)],
        _policy(max_delete_per_run=1), current_size=100 * 1024**3,
        min_size=40 * 1024**3, max_size=90 * 1024**3, history=history,
    )
    assert [item.torrent_hash for item in result.selected] == ["large"]

"""BrushFlow 智能决策引擎测试。"""

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "brushflow" / "decision.py"
SPEC = importlib.util.spec_from_file_location("brushflow_decision_full", MODULE_PATH)
decision = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = decision
SPEC.loader.exec_module(decision)

SmartPolicy = decision.SmartPolicy
TorrentObservation = decision.TorrentObservation
candidate_score = decision.candidate_score
evaluate_candidate = decision.evaluate_candidate
rank_selection_candidates = decision.rank_selection_candidates
select_deletions = decision.select_deletions


def _seed(**overrides):
    data = {
        "hash": overrides.pop("hash", "hash-1"),
        "total_size": overrides.pop("total_size", 10 * 1024**3),
        "downloaded": overrides.pop("downloaded", 10 * 1024**3),
        "uploaded": overrides.pop("uploaded", 6 * 1024**3),
        "ratio": overrides.pop("ratio", 0.6),
        "progress": overrides.pop("progress", 100),
        "seeding_time": overrides.pop("seeding_time", 96 * 3600),
        "iatime": overrides.pop("iatime", 48 * 3600),
        "avg_upspeed": overrides.pop("avg_upspeed", 0),
        "upspeed": overrides.pop("upspeed", 0),
        "num_seeds": overrides.pop("num_seeds", 20),
        "num_leechs": overrides.pop("num_leechs", 0),
        "active_peers": overrides.pop("active_peers", 0),
        "low_value_confirmations": overrides.pop("low_value_confirmations", 3),
        "low_value_span_minutes": overrides.pop("low_value_span_minutes", 30),
    }
    data.update(overrides)
    return data


def _policy(**overrides):
    values = {
        "min_seed_time_hours": 72,
        "min_ratio": 0,
        "score_threshold": 40,
        "score_margin": 0,
        "max_delete_per_run": 3,
        "max_delete_percent_day": 100,
        "allow_proactive_delete": False,
        "max_delete_capacity_percent_run": 100,
        "max_delete_capacity_percent_day": 100,
    }
    values.update(overrides)
    return SmartPolicy(**values)


def test_minimum_site_seed_time_is_a_hard_floor():
    result = evaluate_candidate(_seed(seeding_time=24 * 3600), _policy())
    assert result.action == "blocked"
    assert result.reason_codes == ("min_seed_time",)


def test_hr_and_incomplete_are_never_candidates():
    assert evaluate_candidate(_seed(progress=80, downloaded=8 * 1024**3), _policy()).reason_codes == ("incomplete",)
    assert evaluate_candidate(_seed(hit_and_run=True), _policy()).reason_codes == ("hit_and_run",)


def test_low_demand_seed_can_be_removed_after_site_floor():
    result = evaluate_candidate(
        _seed(
            ratio=0,
            uploaded=0,
            avg_upspeed=0,
            num_seeds=30,
            num_leechs=0,
            iatime=14 * 24 * 3600,
        ),
        _policy(),
    )
    assert result.action == "candidate"
    assert "low_retention_value" in result.reason_codes


def test_hot_seed_is_kept_even_when_capacity_is_under_pressure():
    result = evaluate_candidate(
        _seed(
            avg_upspeed=800 * 1024,
            upspeed=2 * 1024 * 1024,
            num_seeds=2,
            num_leechs=8,
            ratio=2.0,
            iatime=10 * 60,
        ),
        _policy(),
    )
    assert result.action == "blocked"
    assert result.reason_codes == ("real_upload",)


def test_no_pressure_means_no_deletion_by_default():
    result = select_deletions(
        [_seed()],
        _policy(),
        current_size=30 * 1024**3,
        min_size=20 * 1024**3,
        max_size=50 * 1024**3,
    )
    assert result.selected == ()
    assert result.reason_codes == ("no_pressure",)


def test_proactive_mode_cleans_cold_seed_without_capacity_threshold():
    cold = _seed(uploaded=0, ratio=0, num_seeds=30, iatime=14 * 86400)
    result = select_deletions(
        [cold],
        _policy(allow_proactive_delete=True),
        current_size=10 * 1024**3,
        disk_limit=500 * 1024**3,
    )
    assert [item.torrent_hash for item in result.selected] == ["hash-1"]


def test_pressure_selects_low_value_and_respects_run_cap():
    seeds = [
        _seed(hash="low-1", uploaded=0, ratio=0, num_seeds=30, iatime=14 * 86400),
        _seed(hash="low-2", uploaded=0, ratio=0, num_seeds=30, iatime=14 * 86400),
        _seed(hash="low-3", uploaded=0, ratio=0, num_seeds=30, iatime=14 * 86400),
        _seed(hash="hot", avg_upspeed=2 * 1024 * 1024, upspeed=2 * 1024 * 1024, num_seeds=1, num_leechs=10),
    ]
    result = select_deletions(
        seeds,
        _policy(max_delete_per_run=2),
        current_size=100 * 1024**3,
        min_size=50 * 1024**3,
        max_size=90 * 1024**3,
    )
    assert [item.torrent_hash for item in result.selected] == ["low-1", "low-2"]
    assert "run_cap" in result.reason_codes


def test_minimum_ratio_can_be_enabled_per_site():
    result = evaluate_candidate(_seed(ratio=0.2), _policy(min_ratio=0.5))
    assert result.action == "blocked"
    assert result.reason_codes == ("min_ratio",)


def test_smart_selection_prefers_promotion_demand_and_scarcity():
    cold = {
        "title": "普通大盘种",
        "size": 80 * 1024**3,
        "seeders": 50,
        "leechers": 0,
        "downloadvolumefactor": 1,
        "uploadvolumefactor": 1,
        "age_minutes": 7 * 24 * 60,
    }
    valuable = {
        "title": "免费热门种",
        "size": 10 * 1024**3,
        "seeders": 2,
        "leechers": 12,
        "downloadvolumefactor": 0,
        "uploadvolumefactor": 2,
        "age_minutes": 30,
    }
    assert candidate_score(valuable).score > candidate_score(cold).score
    ranked = rank_selection_candidates([cold, valuable], min_score=25, max_count=1)
    assert ranked[0].candidate["title"] == "免费热门种"


def test_default_selection_threshold_rejects_large_stale_candidate():
    stale = {
        "title": "超大冷种",
        "size": 200 * 1024**3,
        "seeders": 80,
        "leechers": 0,
        "downloadvolumefactor": 0,
        "uploadvolumefactor": 1,
        "age_minutes": 7 * 24 * 60,
    }
    assert candidate_score(stale).score < 25
    assert rank_selection_candidates([stale], min_score=25) == ()


def test_deletion_prefers_larger_seed_when_retention_value_is_equal():
    small = _seed(hash="small", total_size=5 * 1024**3)
    large = _seed(hash="large", total_size=50 * 1024**3)
    result = select_deletions(
        [small, large],
        _policy(max_delete_per_run=1),
        current_size=100 * 1024**3,
        min_size=40 * 1024**3,
        max_size=90 * 1024**3,
    )
    assert [item.torrent_hash for item in result.selected] == ["large"]

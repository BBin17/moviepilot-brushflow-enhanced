"""BrushFlow 9.0 统一收益引擎与本地学习测试。"""

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[3]


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "plugins.v3" / "brushflow" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


decision = load_module("brushflow_v9_decision", "decision.py")
learning = load_module("brushflow_v9_learning", "learning.py")
GIB = 1024**3


def cold_seed(torrent_hash, size_gb=3, **overrides):
    row = {
        "hash": torrent_hash,
        "size": size_gb * GIB,
        "downloaded": size_gb * GIB,
        "progress": 100,
        "seeding_time": 72 * 3600,
        "inactive_time": 12 * 3600,
        "seeders": 30,
        "leechers": 0,
        "active_peers": 0,
        "low_value_confirmations": 3,
        "low_value_span_minutes": 30,
    }
    row.update(overrides)
    return row


def balanced_policy(**overrides):
    values = {
        "min_seed_time_hours": 48,
        "smart_cold_inactive_minutes": 360,
        "score_threshold": 40,
        "max_delete_per_run": 3,
        "max_delete_percent_day": 100,
        "max_delete_capacity_percent_run": 100,
        "max_delete_capacity_percent_day": 100,
    }
    values.update(overrides)
    return decision.SmartPolicy(**values)


class SelectionTests(unittest.TestCase):
    def test_explicit_minimum_size_is_always_enforced(self):
        self.assertFalse(decision.size_range_matches(0.49 * GIB, "0.5"))
        self.assertTrue(decision.size_range_matches(0.5 * GIB, "0.5"))
        self.assertTrue(decision.size_range_matches(1 * GIB, "0.5"))

    def test_explicit_size_range_is_closed_interval(self):
        self.assertFalse(decision.size_range_matches(0.49 * GIB, "0.5-2"))
        self.assertTrue(decision.size_range_matches(0.5 * GIB, "0.5-2"))
        self.assertTrue(decision.size_range_matches(2 * GIB, "0.5-2"))
        self.assertFalse(decision.size_range_matches(2.01 * GIB, "0.5-2"))

    def test_80gb_free_without_demand_is_rejected(self):
        item = {
            "size": 80 * GIB,
            "downloadvolumefactor": 0,
            "uploadvolumefactor": 2,
            "seeders": 10,
            "leechers": 0,
            "age_minutes": 10,
        }
        result = decision.candidate_score(item, profile="balanced")
        self.assertFalse(result.accepted)
        self.assertIn("large_without_trusted_demand", result.reason_codes)

    def test_unknown_tracker_counts_are_neutral(self):
        unknown = decision.candidate_score({"size": 5 * GIB, "age_minutes": 60})
        known_zero = decision.candidate_score(
            {"size": 5 * GIB, "age_minutes": 60, "seeders": 0, "leechers": 0}
        )
        self.assertEqual(unknown.contributions["scarcity"], 0)
        self.assertGreater(known_zero.contributions["scarcity"], 0)
        self.assertIn("tracker_seeders_unknown", unknown.reason_codes)

    def test_ratio_target_reached_keeps_normal_policy(self):
        self.assertEqual(
            decision.adaptive_selection_policy(5, 30, 2.1, 2.0),
            (5, 30.0, 0.0),
        )

    def test_balanced_capacity_tiers(self):
        self.assertEqual(decision.capacity_selection_policy("balanced", 0.69, 9, 10)[:2], (5, 30.0))
        self.assertEqual(decision.capacity_selection_policy("balanced", 0.80, 9, 10)[:2], (3, 35.0))
        self.assertEqual(decision.capacity_selection_policy("balanced", 0.88, 9, 10)[:2], (2, 42.0))
        self.assertEqual(decision.capacity_selection_policy("balanced", 0.91, 9, 10)[:2], (1, 50.0))


class DeletionTests(unittest.TestCase):
    def test_single_stale_leecher_does_not_permanently_protect(self):
        seed = cold_seed("stale", leechers=1)
        result = decision.evaluate_candidate(
            seed,
            balanced_policy(),
            history=[{"hash": "stale", "at": 1, "leechers": 0}],
        )
        self.assertNotEqual(result.reason_codes, ("trusted_active_demand",))

    def test_two_of_three_demand_checks_protect(self):
        seed = cold_seed("demand", leechers=1)
        result = decision.evaluate_candidate(
            seed,
            balanced_policy(),
            history=[{"hash": "demand", "at": 2, "leechers": 1}],
        )
        self.assertEqual(result.reason_codes, ("trusted_active_demand",))

    def test_real_upload_delta_immediately_protects(self):
        result = decision.evaluate_candidate(
            cold_seed("upload", upload_delta_since_check=1),
            balanced_policy(),
        )
        self.assertEqual(result.reason_codes, ("real_upload",))

    def test_ratio_contributes_at_most_five_only_with_recent_yield(self):
        without_yield = decision.evaluate_candidate(
            cold_seed("ratio-a", ratio=5),
            balanced_policy(ratio_weight=20),
        )
        with_yield = decision.evaluate_candidate(
            cold_seed("ratio-b", ratio=5, yield_per_gb_24h=0.001),
            balanced_policy(ratio_weight=20),
        )
        self.assertEqual(without_yield.contributions["ratio"], 0)
        self.assertEqual(with_yield.contributions["ratio"], 5)

    def test_near_scores_prefer_larger_release(self):
        result = decision.select_deletions(
            [cold_seed("small", 5), cold_seed("large", 20)],
            balanced_policy(max_delete_per_run=1),
            current_size=95 * GIB,
            disk_limit=100 * GIB,
        )
        self.assertEqual([row.torrent_hash for row in result.selected], ["large"])

    def test_capacity_closes_toward_85_percent(self):
        result = decision.select_deletions(
            [cold_seed("a"), cold_seed("b"), cold_seed("c")],
            balanced_policy(max_delete_per_run=3),
            current_size=92 * GIB,
            disk_limit=100 * GIB,
        )
        self.assertEqual(result.target_size, 85 * GIB)
        self.assertGreaterEqual(result.estimated_freed_bytes, 7 * GIB)

    def test_count_and_gb_limits_both_apply(self):
        result = decision.select_deletions(
            [cold_seed(str(index), 3) for index in range(5)],
            balanced_policy(
                max_delete_per_run=3,
                max_delete_capacity_percent_run=4,
                max_delete_capacity_percent_day=8,
            ),
            current_size=95 * GIB,
            disk_limit=100 * GIB,
        )
        self.assertEqual(len(result.selected), 1)
        self.assertLessEqual(result.estimated_freed_bytes, 4 * GIB)

    def test_severe_over_capacity_still_respects_normal_capacity_cap(self):
        result = decision.select_deletions(
            [cold_seed(str(index), 3) for index in range(3)],
            balanced_policy(
                max_delete_per_run=3,
                max_delete_percent_day=5,
                max_delete_capacity_percent_run=4,
                max_delete_capacity_percent_day=8,
            ),
            current_size=130 * GIB,
            disk_limit=100 * GIB,
        )
        self.assertTrue(result.recovery_active)
        self.assertEqual(len(result.selected), 1)
        self.assertLessEqual(result.estimated_freed_bytes, 4 * GIB)

    def test_capacity_cost_keeps_rising_beyond_trigger(self):
        seed = cold_seed("capacity", 20)
        normal = decision.select_deletions(
            [seed],
            balanced_policy(),
            current_size=95 * GIB,
            disk_limit=100 * GIB,
        )
        overloaded = decision.select_deletions(
            [seed],
            balanced_policy(),
            current_size=150 * GIB,
            disk_limit=100 * GIB,
        )
        self.assertLess(
            overloaded.evaluated[0].contributions["capacity_cost"],
            normal.evaluated[0].contributions["capacity_cost"],
        )

    def test_unified_engine_always_requires_confirmation(self):
        result = decision.evaluate_candidate(
            cold_seed("legacy", low_value_confirmations=0, low_value_span_minutes=0),
            balanced_policy(ratio_weight=18),
        )
        self.assertEqual(result.action, "watch")


class LearningTests(unittest.TestCase):
    def test_cold_start_and_confidence_growth(self):
        self.assertEqual(learning.learning_confidence(19), 0)
        self.assertEqual(learning.learning_confidence(60), 0.5)
        self.assertEqual(learning.learning_confidence(100), 1)

    def test_outlier_is_winsorized(self):
        samples = [1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
        self.assertLessEqual(learning.winsorize(1000, samples), 2)

    def test_30_day_expiry_and_task_isolation(self):
        old = {"snapshots": [{"at": 1, "hash": "old", "uploaded": 0, "size": GIB}], "sample_count": 0}
        state_a = learning.update_learning_state(old, [{"hash": "a", "uploaded": 0, "size": GIB}], now=31 * 86400 + 2)
        state_b = learning.update_learning_state({}, [{"hash": "b", "uploaded": 0, "size": GIB}], now=31 * 86400 + 2)
        self.assertNotIn("old", [row["hash"] for row in state_a["snapshots"]])
        self.assertEqual({row["hash"] for row in state_a["snapshots"]}, {"a"})
        self.assertEqual({row["hash"] for row in state_b["snapshots"]}, {"b"})

    def test_hourly_delta_updates_ewma(self):
        first = learning.update_learning_state({}, [{"hash": "a", "uploaded": 0, "size": 10 * GIB}], now=1000)
        second = learning.update_learning_state(first, [{"hash": "a", "uploaded": GIB, "size": 10 * GIB}], now=4600)
        self.assertEqual(second["sample_count"], 1)
        self.assertGreater(second["features"]["__all__"]["ewma"], 0)


if __name__ == "__main__":
    unittest.main()

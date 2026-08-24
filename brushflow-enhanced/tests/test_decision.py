import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "plugins.v3" / "brushflow" / "decision.py"
SPEC = importlib.util.spec_from_file_location("brushflow_decision", MODULE_PATH)
decision = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = decision
SPEC.loader.exec_module(decision)


class DecisionEngineTests(unittest.TestCase):
    def test_adaptive_selection_scales_with_ratio_gap(self):
        self.assertEqual(decision.adaptive_selection_policy(5, 30, 0.4, 2.0), (5, 25.0, 1.6))
        self.assertEqual(decision.adaptive_selection_policy(5, 30, 1.29, 2.0), (3, 30.0, 0.71))
        count, score, gap = decision.adaptive_selection_policy(5, 30, 1.85, 2.0)
        self.assertEqual((count, score), (1, 40.0))
        self.assertAlmostEqual(gap, 0.15)

    def test_candidate_scoring_prefers_demand_and_efficiency(self):
        small_demand = {
            "size": 2 * 1024**3,
            "seeders": 2,
            "leechers": 8,
            "downloadvolumefactor": 0,
            "uploadvolumefactor": 2,
            "date_elapsed": 30,
        }
        large_cold = {
            "size": 90 * 1024**3,
            "seeders": 40,
            "leechers": 0,
            "downloadvolumefactor": 1,
            "uploadvolumefactor": 1,
            "date_elapsed": 30,
        }
        ranked = decision.rank_selection_candidates(
            [large_cold, small_demand],
            min_score=0,
            max_count=2,
            share_ratio_gap=1.0,
            share_ratio_target=2.0,
        )
        self.assertIs(ranked[0].candidate, small_demand)
        self.assertGreater(ranked[0].decision.contributions["size_efficiency"], 0)

    def test_active_demand_and_cold_cooldown_are_hard_protection(self):
        policy = decision.SmartPolicy(
            min_seed_time_hours=24,
            smart_cold_inactive_minutes=360,
            protect_active_demand=True,
        )
        active = decision.evaluate_candidate(
            {
                "hash": "active",
                "size": 10 * 1024**3,
                "downloaded": 10 * 1024**3,
                "seeding_time": 48 * 3600,
                "inactive_time": 48 * 3600,
                "leechers": 1,
            },
            policy,
        )
        recent = decision.evaluate_candidate(
            {
                "hash": "recent",
                "size": 10 * 1024**3,
                "downloaded": 10 * 1024**3,
                "seeding_time": 48 * 3600,
                "inactive_time": 60,
            },
            policy,
        )
        self.assertEqual(active.reason_codes, ("active_demand",))
        self.assertEqual(recent.reason_codes, ("smart_cold_cooldown",))

    def test_ratio_weight_keeps_high_ratio_seed_when_capacity_is_full(self):
        policy = decision.SmartPolicy(
            min_seed_time_hours=24,
            smart_cold_inactive_minutes=0,
            ratio_target=2.0,
            ratio_weight=18.0,
            max_delete_per_run=1,
            max_delete_percent_day=100,
        )
        low = {
            "hash": "low",
            "size": 10 * 1024**3,
            "downloaded": 10 * 1024**3,
            "uploaded": 0,
            "ratio": 0.05,
            "seeding_time": 48 * 3600,
            "inactive_time": 48 * 3600,
            "seeders": 30,
        }
        high = {**low, "hash": "high", "ratio": 2.0, "uploaded": 20 * 1024**3}
        result = decision.select_deletions(
            [low, high],
            policy,
            current_size=20 * 1024**3,
            min_size=10 * 1024**3,
            max_size=20 * 1024**3,
        )
        self.assertEqual([item.torrent_hash for item in result.selected], ["low"])


if __name__ == "__main__":
    unittest.main()

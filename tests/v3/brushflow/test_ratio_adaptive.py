import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "brushflow" / "decision.py"
SPEC = importlib.util.spec_from_file_location("brushflow_decision", MODULE_PATH)
decision = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = decision
SPEC.loader.exec_module(decision)


class DecisionEngineTests(unittest.TestCase):
    def test_adaptive_selection_scales_with_ratio_gap(self):
        self.assertEqual(decision.adaptive_selection_policy(5, 30, 0.4, 2.0), (5, 26.0, 1.6))
        self.assertEqual(decision.adaptive_selection_policy(5, 30, 1.2, 2.0), (5, 28.0, 0.8))
        count, score, gap = decision.adaptive_selection_policy(5, 30, 1.85, 2.0)
        self.assertEqual(count, 5)
        self.assertAlmostEqual(score, 29.625)
        self.assertAlmostEqual(gap, 0.15)
        self.assertEqual(decision.adaptive_selection_policy(5, 30, 2.1, 2.0), (5, 30.0, 0.0))

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

    def test_trusted_demand_and_cold_cooldown_are_hard_protection(self):
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
            history=[{"hash": "active", "at": 1, "leechers": 1}],
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
        self.assertEqual(active.reason_codes, ("trusted_active_demand",))
        self.assertEqual(recent.reason_codes, ("smart_cold_cooldown",))

    def test_ratio_is_neutral_without_recent_upload(self):
        policy = decision.SmartPolicy(
            min_seed_time_hours=24,
            smart_cold_inactive_minutes=0,
            ratio_target=2.0,
            ratio_weight=18.0,
            max_delete_per_run=1,
            max_delete_percent_day=100,
            max_delete_capacity_percent_run=100,
            max_delete_capacity_percent_day=100,
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
            "active_peers": 0,
            "low_value_confirmations": 3,
            "low_value_span_minutes": 30,
        }
        high = {**low, "hash": "high", "ratio": 2.0, "uploaded": 20 * 1024**3}
        low_result = decision.evaluate_candidate(low, policy)
        high_result = decision.evaluate_candidate(high, policy)
        self.assertEqual(low_result.score, high_result.score)
        self.assertEqual(low_result.contributions["ratio"], 0)

    def test_invalid_seed_requires_explicit_error_and_working_tracker(self):
        invalid = decision.detect_invalid_seed(
            [{
                "status": 4,
                "url": "https://tracker.example/announce",
                "msg": "Torrent not registered with this tracker",
            }],
            working_domains={"tracker.example"},
        )
        self.assertTrue(invalid.invalid)
        self.assertEqual(invalid.domains, ("tracker.example",))

        transient = decision.detect_invalid_seed(
            [{
                "status": 4,
                "url": "https://tracker.example/announce",
                "msg": "Request too frequent(h)",
            }],
            working_domains={"tracker.example"},
        )
        self.assertFalse(transient.invalid)

        outage = decision.detect_invalid_seed(
            [{
                "status": 4,
                "url": "https://tracker.example/announce",
                "msg": "Torrent banned",
            }],
            working_domains=set(),
        )
        self.assertFalse(outage.invalid)


if __name__ == "__main__":
    unittest.main()

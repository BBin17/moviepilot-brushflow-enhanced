import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[3]
MODULE_PATH = ROOT / "plugins.v3" / "brushflow" / "download_health.py"
SPEC = importlib.util.spec_from_file_location("brushflow_download_health", MODULE_PATH)
health = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = health
SPEC.loader.exec_module(health)


class DownloadHealthTests(unittest.TestCase):
    def sample(self, at, downloaded, **overrides):
        row = {
            "at": at,
            "downloaded": downloaded,
            "total_size": 100 * 1024**3,
            "download_speed": 0,
            "active_peers": 0,
            "availability": 1,
            "is_paused": False,
        }
        row.update(overrides)
        return row

    def test_cold_start_waits_for_history(self):
        result = health.assess_download_health(
            [],
            self.sample(1000, 0),
            now=1000,
        )
        self.assertEqual(result["state"], health.HEALTH_UNKNOWN)

    def test_three_checks_without_progress_is_stalled(self):
        samples = [
            self.sample(100, 0),
            self.sample(1000, 0),
        ]
        result = health.assess_download_health(
            samples,
            self.sample(1900, 0),
            now=1900,
        )
        self.assertEqual(result["state"], health.HEALTH_STALLED)
        self.assertEqual(result["reason"], "no_download_progress")

    def test_one_old_stale_sample_does_not_mark_stalled(self):
        result = health.assess_download_health(
            [self.sample(100, 0)],
            self.sample(1900, 1024 * 1024),
            now=1900,
        )
        self.assertEqual(result["state"], health.HEALTH_UNKNOWN)

    def test_progressing_but_slow_is_slow_not_stalled(self):
        policy = health.DownloadHealthPolicy(slow_after_hours=1, slow_speed_kbps=128)
        samples = [
            self.sample(100, 0),
            self.sample(1900, 100 * 1024**2),
            self.sample(3700, 200 * 1024**2),
        ]
        result = health.assess_download_health(
            samples,
            self.sample(3700, 200 * 1024**2),
            policy=policy,
            now=3700,
        )
        self.assertEqual(result["state"], health.HEALTH_SLOW)
        self.assertGreater(result["progress_delta"], 0)
        self.assertGreater(result["avg_download_speed_kbps"], 0)

    def test_any_new_progress_resets_stalled_window(self):
        samples = [
            self.sample(100, 0),
            self.sample(1000, 0),
        ]
        result = health.assess_download_health(
            samples,
            self.sample(1900, 1024 * 1024),
            now=1900,
        )
        self.assertNotEqual(result["state"], health.HEALTH_STALLED)

    def test_paused_and_completed_are_not_download_failures(self):
        paused = health.assess_download_health(
            [self.sample(100, 0), self.sample(1000, 0)],
            self.sample(1900, 0, is_paused=True),
            now=1900,
        )
        completed = health.assess_download_health(
            [],
            self.sample(1000, 100 * 1024**3),
            now=1000,
        )
        self.assertEqual(paused["state"], health.HEALTH_PAUSED)
        self.assertEqual(completed["state"], health.HEALTH_COMPLETED)


if __name__ == "__main__":
    unittest.main()

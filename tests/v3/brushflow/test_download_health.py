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

    def test_unhealthy_download_repairs_once_then_pauses(self):
        policy = health.DownloadHealthPolicy(stalled_window_minutes=30)
        first = health.next_health_action(
            health.HEALTH_STALLED, 0, repair_at=None, paused_at=None, now=1000, policy=policy
        )
        self.assertEqual(first["action"], "repair")
        second = health.next_health_action(
            health.HEALTH_STALLED, 0, repair_at=1000, paused_at=None, now=2800,
            policy=policy, post_repair_confirmed=True,
        )
        self.assertEqual(second["action"], "pause")

    def test_real_progress_clears_repair_state_and_never_deletes(self):
        result = health.next_health_action(
            health.HEALTH_STALLED, 1024, repair_at=1000, paused_at=2000, now=3000
        )
        self.assertIsNone(result["action"])
        self.assertIsNone(result["repair_at"])

    def test_sustained_slow_speed_enters_repair_even_with_small_progress(self):
        result = health.next_health_action(
            health.HEALTH_SLOW, 1024, repair_at=None, paused_at=None, now=3000
        )
        self.assertEqual(result["action"], "repair")

    def test_five_minute_checks_accumulate_a_full_stalled_window(self):
        record = {}
        for minutes in range(0, 121, 5):
            record, result, _ = health.observe_download(record, self.sample(100 + minutes * 60, 0))
            if minutes < 30:
                self.assertNotEqual(result["state"], health.HEALTH_STALLED)
            else:
                self.assertEqual(result["state"], health.HEALTH_STALLED)
        self.assertEqual(result["observed_seconds"], 7200)

    def test_single_byte_progress_clears_stalled(self):
        rows = [self.sample(at, 0) for at in range(100, 1901, 300)]
        result = health.assess_download_health(rows, self.sample(2200, 1))
        self.assertEqual(result["state"], health.HEALTH_DOWNLOADING)

    def test_slow_window_survives_more_than_200_minute_samples(self):
        record = {}
        policy = health.DownloadHealthPolicy()
        for minutes in range(0, 421):
            # Larger total keeps this slow torrent incomplete after seven hours.
            record, result, _ = health.observe_download(record, self.sample(100 + minutes * 60, minutes * 60 * 1024), policy=policy)
        self.assertEqual(result["state"], health.HEALTH_SLOW)
        self.assertAlmostEqual(result["avg_download_speed_kbps"], 1)
        self.assertLessEqual(len(record["samples"]), policy.max_samples)

    def test_slow_window_need_not_land_on_exact_boundary(self):
        rows = [self.sample(100 + i * 401, i * 401 * 1024) for i in range(56)]
        result = health.assess_download_health(rows, rows[-1])
        self.assertEqual(result["state"], health.HEALTH_SLOW)
        self.assertGreaterEqual(result["observed_seconds"], 6 * 3600)

    def test_missing_data_counter_reset_and_gap_start_new_evidence(self):
        rows = [self.sample(at, 1000) for at in range(100, 1901, 300)]
        for current in (self.sample(2200, None), self.sample(2200, 0), self.sample(10000, 1000)):
            result = health.assess_download_health(rows, current)
            self.assertEqual(result["state"], health.HEALTH_UNKNOWN)

    def test_queue_pause_and_checking_break_continuous_window(self):
        for state in ("queuedDL", "pausedDL", "stoppedDL", "checkingDL", "error"):
            rows = [self.sample(at, 0) for at in range(100, 1901, 300)]
            rows.append(self.sample(2200, 0, downloader_state=state))
            result = health.assess_download_health(rows, self.sample(2500, 0))
            self.assertEqual(result["state"], health.HEALTH_UNKNOWN)

    def test_duplicate_checks_do_not_count_as_confirmations(self):
        rows = []
        for at in (100, 101, 102, 103):
            rows = health.append_download_sample(rows, self.sample(at, 0))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["no_progress_count"], 1)

    def test_repair_needs_new_confirmations_not_just_elapsed_time(self):
        result = health.next_health_action(health.HEALTH_STALLED, 0, repair_at=100,
                                           paused_at=None, now=10000)
        self.assertIsNone(result["action"])

    def test_repair_is_committed_only_after_downloader_acknowledgement(self):
        record = {}
        for at in range(100, 1901, 300):
            record, _, action = health.observe_download(record, self.sample(at, 0))
        self.assertEqual(action, "repair")
        self.assertIsNone(record.get("repair_at"))
        failed = health.record_health_action_result(record, action, now=1900, success=False, error="not supported")
        self.assertIsNone(failed.get("repair_at"))
        self.assertEqual(failed["action_error"], "not supported")
        record = health.record_health_action_result(record, action, now=1900, success=True)
        for at in range(2200, 3701, 300):
            record, _, action = health.observe_download(record, self.sample(at, 0))
            self.assertEqual(action, "pause" if at == 3700 else None)

    def test_postrepair_data_gap_does_not_pause(self):
        record = {"repair_at": 100, "repair_baseline": self.sample(100, 0)}
        record, _, action = health.observe_download(record, self.sample(10000, 0))
        self.assertIsNone(action)
        self.assertEqual(record["repair_at"], 100)

    def test_historical_progress_does_not_clear_current_repair(self):
        record = {}
        for at, downloaded in ((100, 0), (400, 1024), (1000, 1024), (1600, 1024), (2200, 1024)):
            record, _, _ = health.observe_download(record, self.sample(at, downloaded))
        record = health.record_health_action_result(record, "repair", now=2200, success=True)
        record, _, action = health.observe_download(record, self.sample(2500, 1024))
        self.assertEqual(record["repair_at"], 2200)
        self.assertIsNone(action)
        record, _, action = health.observe_download(record, self.sample(2800, 1025))
        self.assertIsNone(record.get("repair_at"))
        self.assertIsNone(action)

    def test_user_pause_keeps_history_and_does_not_resume(self):
        record = {"repair_at": 100, "paused_at": 200}
        record, result, action = health.observe_download(record, self.sample(300, 0, is_paused=True))
        self.assertEqual(result["state"], health.HEALTH_PAUSED)
        self.assertIsNone(action)
        self.assertEqual(record["paused_at"], 200)


if __name__ == "__main__":
    unittest.main()

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "smartbrushflow" / "manual_download_deletion.py"
SPEC = importlib.util.spec_from_file_location("smartbrushflow_manual_download_deletion", MODULE_PATH)
manual_delete = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manual_delete)


HASH = "a" * 40


class MemoryData:
    def __init__(self, health="stalled", progress=500):
        self.rows = {
            "torrents": {
                HASH: {
                    "title": "Stalled download",
                    "size": 1000,
                    "download_health": health,
                    "download_completed_bytes": progress,
                }
            },
            "download_health": {},
            "manual_download_deletions": [],
        }

    def read(self, name):
        return self.rows.get(name)

    def write(self, name, value):
        self.rows[name] = value


class FakeAdapter:
    def __init__(self, data, *, completed=500, present=True, remove_result=True, remove_works=True):
        self.data = data
        self.completed = completed
        self.present = present
        self.remove_result = remove_result
        self.remove_works = remove_works
        self.delete_data = None
        self.audit_was_saved_before_remove = False
        self.remove_calls = 0

    def snapshot(self):
        if not self.present:
            return {}
        return {
            HASH: {
                "hash": HASH,
                "title": "Stalled download",
                "total_size": 1000,
                "completed": self.completed,
                "downloaded": self.completed,
                "downloader_state": "downloading",
            }
        }

    def remove(self, torrent_hash, *, delete_data):
        self.remove_calls += 1
        self.audit_was_saved_before_remove = bool(self.data.read("manual_download_deletions"))
        self.delete_data = delete_data
        if self.remove_works:
            self.present = False
        return "accepted" if self.remove_result else "uncertain"


def service(data, adapter, clock=lambda: 1234.0):
    return manual_delete.ManualDownloadDeletionService(
        adapter=adapter, read_data=data.read, write_data=data.write, clock=clock,
    )


def delete(service_, **overrides):
    payload = {
        "torrent_hash": HASH,
        "request_id": "manual-test-0001",
        "confirm": True,
        "delete_data": False,
    }
    payload.update(overrides)
    return service_.delete(**payload)


class ManualDownloadDeletionTests(unittest.TestCase):
    def test_manual_delete_is_single_torrent_audited_first_and_keeps_data_by_default(self):
        data = MemoryData()
        adapter = FakeAdapter(data)

        result = delete(service(data, adapter))

        self.assertEqual(result["state"], "completed")
        self.assertTrue(adapter.audit_was_saved_before_remove)
        self.assertFalse(adapter.delete_data)
        self.assertTrue(data.read("torrents")[HASH]["deleted"])
        self.assertFalse(data.read("manual_download_deletions")[0]["delete_data"])

    def test_manual_delete_can_remove_data_only_after_explicit_choice(self):
        data = MemoryData(health="slow")
        adapter = FakeAdapter(data)

        result = delete(service(data, adapter), delete_data=True)

        self.assertEqual(result["state"], "completed")
        self.assertTrue(adapter.delete_data)

    def test_slow_download_can_be_manually_removed_while_still_slow(self):
        data = MemoryData(health="slow")
        adapter = FakeAdapter(data, completed=501)
        original = adapter.snapshot
        def snapshot():
            rows = original()
            if HASH in rows:
                rows[HASH]["download_speed"] = 1024
            return rows
        adapter.snapshot = snapshot
        self.assertEqual(delete(service(data, adapter))["state"], "completed")

    def test_recovered_slow_download_is_not_removed(self):
        data = MemoryData(health="slow")
        adapter = FakeAdapter(data, completed=501)
        original = adapter.snapshot
        adapter.snapshot = lambda: {key: {**row, "download_speed": 1024 * 1024} for key, row in original().items()}
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "已有下载进度"):
            delete(service(data, adapter))
        self.assertEqual(adapter.remove_calls, 0)

    def test_automatic_health_pause_can_be_removed_after_confirmation(self):
        data = MemoryData(health="paused")
        data.read("torrents")[HASH]["download_health_auto_paused"] = True
        adapter = FakeAdapter(data)
        self.assertEqual(delete(service(data, adapter))["state"], "completed")

    def test_reusing_request_id_for_another_file_choice_is_rejected(self):
        data = MemoryData()
        adapter = FakeAdapter(data)
        deletion = service(data, adapter)
        delete(deletion)
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "请求编号已用于另一项"):
            delete(deletion, delete_data=True)

    def test_only_current_stalled_or_slow_downloads_are_eligible(self):
        for health in ("completed", "downloading", "queued", "error", "paused"):
            with self.subTest(health=health):
                data = MemoryData(health=health)
                adapter = FakeAdapter(data)

                with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "不再属于卡住或低速"):
                    delete(service(data, adapter))

                self.assertIsNone(adapter.delete_data)
                self.assertEqual(data.read("manual_download_deletions"), [])

    def test_fresh_progress_or_completion_cancels_removal(self):
        data = MemoryData()
        adapter = FakeAdapter(data, completed=501)
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "已有下载进度"):
            delete(service(data, adapter))

        adapter.completed = 1000
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "已经完成下载"):
            delete(service(data, adapter), request_id="manual-test-0002")
        self.assertIsNone(adapter.delete_data)

    def test_unknown_completion_or_progress_baseline_fails_closed(self):
        data = MemoryData()
        adapter = FakeAdapter(data)
        adapter.snapshot = lambda: {HASH: {"total_size": 1000, "completed": None, "downloaded": None}}
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "无法确认种子是否仍未完成"):
            delete(service(data, adapter))

        adapter.snapshot = lambda: {HASH: {"total_size": 1000, "completed": 500, "downloaded": 500}}
        data.read("torrents")[HASH].pop("download_completed_bytes")
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "缺少最近一次下载进度记录"):
            delete(service(data, adapter), request_id="manual-test-0002")
        self.assertEqual(data.read("manual_download_deletions"), [])

    def test_uncertain_removal_is_audited_and_never_automatically_retried(self):
        data = MemoryData()
        adapter = FakeAdapter(data, remove_works=False, remove_result=False)
        deletion = service(data, adapter)

        result = delete(deletion)
        self.assertEqual(result["state"], "pending_confirmation")
        self.assertEqual(data.read("manual_download_deletions")[0]["state"], "pending_confirmation")
        with self.assertRaisesRegex(manual_delete.ManualDownloadDeleteError, "仍在核对中"):
            delete(deletion, request_id="manual-test-0002")

    def test_request_retry_returns_existing_audit_without_second_downloader_call(self):
        data = MemoryData()
        adapter = FakeAdapter(data)
        deletion = service(data, adapter)

        first = delete(deletion)
        retry = delete(deletion)

        self.assertEqual(first["state"], "completed")
        self.assertTrue(retry["duplicate"])
        self.assertEqual(len(data.read("manual_download_deletions")), 1)

    def test_pending_removal_can_be_reconciled_without_resubmitting(self):
        data = MemoryData()
        adapter = FakeAdapter(data, remove_works=False, remove_result=False)
        deletion = service(data, adapter)
        first = delete(deletion)
        adapter.present = False

        reconciled = delete(deletion, request_id="manual-test-0002")

        self.assertEqual(first["state"], "pending_confirmation")
        self.assertEqual(reconciled["state"], "completed")
        self.assertTrue(reconciled["reconciled"])
        self.assertEqual(adapter.remove_calls, 1)
        self.assertTrue(data.read("torrents")[HASH]["deleted"])

    def test_old_pending_request_requires_fresh_confirmation_before_retry(self):
        data = MemoryData()
        adapter = FakeAdapter(data, remove_works=False, remove_result=False)
        clock = [1234.0]
        deletion = service(data, adapter, clock=lambda: clock[0])
        delete(deletion)
        clock[0] += manual_delete.PENDING_CONFIRMATION_GRACE_SECONDS + 1

        result = delete(deletion, request_id="manual-test-0002")

        self.assertEqual(result["state"], "pending_confirmation")
        self.assertEqual(adapter.remove_calls, 2)
        states = [row["state"] for row in data.read("manual_download_deletions")]
        self.assertEqual(states, ["not_removed", "pending_confirmation"])

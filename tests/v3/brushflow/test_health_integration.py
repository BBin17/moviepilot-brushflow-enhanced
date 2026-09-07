from unittest.mock import PropertyMock, patch

from app.plugins.brushflow import BrushFlow, BrushTaskConfig
from support.downloaders import FakeDownloader, FakeQbClient


def seed(**overrides):
    return {"hash": "seed", "total_size": 1024**3, "completed": 0, "downloaded": 0,
            "downloader_state": "stalledDL", **overrides}


def exercise(rows, *, outcomes=None, health_record=None, repair=True, supported=True, error=None):
    plugin = object.__new__(BrushFlow)
    plugin._get_task_config = lambda: None
    store = {"download_health": {"seed": health_record or {}}}
    plugin._current_task_data = lambda key, default=None: store.get(key, default)
    plugin._save_current_task_data = lambda key, value: store.__setitem__(key, value)
    plugin._BrushFlow__get_hash = lambda row: row["hash"]
    plugin._BrushFlow__get_torrent_info = dict
    notifications = []
    plugin._BrushFlow__send_message = lambda *args: notifications.append(args)
    client = FakeQbClient(outcomes) if supported else None
    downloader = FakeDownloader(rows, client=client, error=error)
    with patch.object(BrushFlow, "downloader", new_callable=PropertyMock, return_value=downloader):
        result = plugin._BrushFlow__apply_download_health_actions(["seed"] if repair else [], [] if repair else ["seed"])
    return result["seed"], store["download_health"]["seed"], downloader, notifications


def test_successful_repair_is_persisted_after_client_calls():
    result, record, downloader, _ = exercise([seed()])
    assert result["success"]
    assert record["repair_at"] > 0
    assert downloader.calls[0] == ("get_torrents",)
    assert downloader.qbc.calls == [("reannounce", "seed"), ("start", "seed")]


def test_failed_repair_is_not_recorded_as_success():
    result, record, downloader, _ = exercise([seed()], outcomes={"start": RuntimeError("offline")})
    assert not result["success"]
    assert record.get("repair_at") is None
    assert record["action_error"]
    assert not any(call[0] == "delete_torrents" for call in downloader.calls)


def test_completed_missing_and_user_paused_torrents_are_not_resumed():
    for rows in ([], [seed(completed=1024**3)], [seed(is_paused=True)], [seed(downloader_state="queuedDL")]):
        result, _, downloader, _ = exercise(rows)
        assert not result["success"]
        assert not downloader.qbc.calls


def test_plugin_paused_torrent_can_be_explicitly_retried():
    result, record, _, _ = exercise([seed(is_paused=True)], health_record={"paused_at": 100})
    assert result["success"]
    assert record["paused_at"] is None


def test_unsupported_adapter_is_visible_and_does_not_start_window():
    result, record, _, _ = exercise([seed()], supported=False)
    assert not result["success"]
    assert "不支持" in result["error"]
    assert record.get("repair_at") is None


def test_pause_failure_is_not_announced_as_success():
    result, record, _, notifications = exercise([seed()], repair=False, outcomes={"stop": False})
    assert not result["success"]
    assert record.get("paused_at") is None
    assert notifications == []


def test_stale_snapshot_failure_blocks_all_actions():
    result, _, downloader, _ = exercise([seed()], error="unavailable")
    assert not result["success"]
    assert not downloader.qbc.calls


def test_real_progress_during_final_recheck_skips_pause():
    record = {"state": "stalled", "repair_at": 100, "samples": [{"downloaded": 0}]}
    result, _, downloader, notifications = exercise([seed(completed=1)], repair=False, health_record=record)
    assert not result["success"]
    assert "恢复推进" in result["error"]
    assert not downloader.qbc.calls
    assert not notifications


def test_selection_waits_for_task_recovery_below_trigger():
    plugin = object.__new__(BrushFlow)
    task = BrushTaskConfig({"id": "one", "name": "test", "site_id": 1, "downloader": "qb", "disksize": 100})
    plugin._get_task_config = lambda: task
    plugin._get_task_data = lambda task_id, name: {"active": True}
    allowed, reason = plugin._BrushFlow__evaluate_size_condition_for_brush(89 * 1024**3)
    assert not allowed
    assert "空间恢复中" in reason
    allowed, _ = plugin._BrushFlow__evaluate_size_condition_for_brush(85 * 1024**3)
    assert allowed

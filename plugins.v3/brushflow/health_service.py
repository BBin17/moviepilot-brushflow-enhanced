"""Download-health service with injected storage, downloader, clock and notifications."""

from typing import Any, Dict, List
import time

from .download_health import (
    DownloadHealthPolicy, observe_download, record_health_action_result, health_label,
    HEALTH_UNKNOWN, HEALTH_DOWNLOADING, HEALTH_STALLED, HEALTH_SLOW, HEALTH_QUEUED,
    HEALTH_ERROR, HEALTH_PAUSED, HEALTH_CHECKING,
)


class DownloadHealthService:
    def __init__(self, *, downloader, read, write, identify, normalize, notify,
                 policy=None, auto_repair=False, pause_after_failed_repair=False, clock=time.time):
        self.downloader = downloader
        self.read = read
        self.write = write
        self.identify = identify
        self.normalize = normalize
        self.notify = notify
        self.policy = policy or DownloadHealthPolicy()
        self.auto_repair = auto_repair
        self.pause_after_failed_repair = pause_after_failed_repair
        self.clock = clock

    def observe(self, torrents: List[Any], torrent_tasks: Dict[str, dict]) -> None:
        """更新当前任务种子的上下传、分享率、做种时间和下载健康"""
        health_policy = self.policy
        health_store = self.read("download_health", {})
        if not isinstance(health_store, dict):
            health_store = {}
        now = self.clock()
        repair_hashes: List[str] = []
        pause_hashes: List[str] = []
        for torrent in torrents:
            torrent_hash = self.identify(torrent)
            torrent_task = torrent_tasks.get(torrent_hash)
            if not torrent_task:
                continue
            torrent_info = self.normalize(torrent)
            total_size = float(torrent_info.get("total_size") or 0)
            completed_measurement = torrent_info.get("completed")
            if completed_measurement is None:
                completed_measurement = torrent_info.get("downloaded")
            completed_bytes = float(completed_measurement or 0)
            is_completed = bool(total_size > 0 and completed_bytes >= total_size)
            current_sample = {
                "at": now,
                "downloaded": completed_bytes,
                "total_size": total_size,
                "download_speed": torrent_info.get("download_speed", 0),
                "active_peers": torrent_info.get("active_peers"),
                "availability": torrent_info.get("availability"),
                "is_paused": torrent_info.get("is_paused", False),
                "downloader_state": torrent_info.get("downloader_state", ""),
                "completed": is_completed,
                "measurement_valid": completed_measurement is not None,
            }
            health_record = health_store.get(torrent_hash)
            if not isinstance(health_record, dict):
                health_record = {}
            record, health, action = observe_download(health_record, current_sample, policy=health_policy)
            if self.auto_repair and action == "repair":
                repair_hashes.append(torrent_hash)
            if self.pause_after_failed_repair and action == "pause":
                pause_hashes.append(torrent_hash)
            health_store[torrent_hash] = {**record, "hash": torrent_hash}
            torrent_task.update(
                {
                    "downloaded": torrent_info.get("downloaded"),
                    "uploaded": torrent_info.get("uploaded"),
                    "ratio": torrent_info.get("ratio"),
                    "seeding_time": torrent_info.get("seeding_time"),
                    "download_speed": torrent_info.get("download_speed", 0),
                    "download_completed_bytes": completed_bytes,
                    "download_health": health.get("state", HEALTH_UNKNOWN),
                    "download_health_label": health_label(health.get("state", HEALTH_UNKNOWN)),
                    "download_health_reason": health.get("reason", "insufficient_history"),
                    "download_health_since": record["state_since"],
                    "download_health_action_error": record.get("action_error"),
                    "download_health_avg_kbps": health.get("avg_download_speed_kbps", 0),
                    "download_health_progress_delta": health.get("progress_delta", 0),
                    "download_health_checked_at": now,
                }
            )
        self.write("download_health", health_store)
        outcomes = self.apply(repair_hashes, pause_hashes)
        for torrent_hash, result in outcomes.items():
            if torrent_hash in torrent_tasks:
                torrent_tasks[torrent_hash]["download_health_action_error"] = result["error"]

    def apply(self, repair_hashes: List[str], pause_hashes: List[str]) -> dict:
        """Freshly recheck incomplete state and commit only acknowledged actions."""
        actions = dict.fromkeys(repair_hashes, "repair") | dict.fromkeys(pause_hashes, "pause")
        if not actions:
            return {}
        downloader = self.downloader
        qbc = getattr(downloader, "qbc", None) if downloader else None
        starter = (getattr(qbc, "torrents_start", None) or getattr(qbc, "torrents_resume", None)) if qbc else None
        stopper = (getattr(qbc, "torrents_stop", None) or getattr(qbc, "torrents_pause", None)) if qbc else None
        reannounce = getattr(qbc, "torrents_reannounce", None) if qbc else None
        store = self.read("download_health", {}) or {}
        try:
            torrents, error = downloader.get_torrents() if downloader else (None, "下载器不可用")
            fresh = {self.identify(torrent): self.normalize(torrent) for torrent in torrents or []}
        except Exception:
            fresh, error = {}, "无法复核下载器状态"
        outcomes = {}
        for torrent_hash, action in actions.items():
            record = store.get(torrent_hash, {})
            info = fresh.get(torrent_hash)
            success, message = False, None
            try:
                if error or info is None:
                    raise ValueError("无法复核种子，未执行操作")
                total = float(info.get("total_size") or 0)
                completed = info.get("completed", info.get("downloaded"))
                state = str(info.get("downloader_state") or "").lower()
                if total <= 0 or completed is None or float(completed) >= total:
                    raise ValueError("种子已完成或完成度未知，未执行下载修复")
                baseline = record.get("samples", [])[-1] if record.get("samples") else None
                if record.get("state") == HEALTH_STALLED and baseline and float(completed) > float(baseline["downloaded"]):
                    raise ValueError("复核时下载已恢复推进，本次无需修复或暂停")
                if state.startswith("checking") or state in {"queuedl", "queueddl", "queuedup"}:
                    raise ValueError("种子正在排队或校验，未执行操作")
                if (info.get("is_paused") or state.startswith(("paused", "stopped"))) and not record.get("paused_at"):
                    raise ValueError("种子由用户暂停，不自动恢复或接管")
                if action == "repair":
                    if not callable(starter) or not callable(reannounce):
                        raise ValueError("当前下载器不支持自动重新汇报并恢复")
                    if reannounce(torrent_hashes=torrent_hash) is False or starter(torrent_hashes=torrent_hash) is False:
                        raise ValueError("下载器未确认修复成功")
                else:
                    if not callable(stopper):
                        raise ValueError("当前下载器不支持自动暂停")
                    if stopper(torrent_hashes=torrent_hash) is False:
                        raise ValueError("下载器未确认暂停成功")
                success = True
            except ValueError as err:
                message = str(err)
            except Exception:
                message = "下载器请求失败；保留数据，请检查下载器连接"
            store[torrent_hash] = record_health_action_result(record, action, now=self.clock(), success=success, error=message)
            outcomes[torrent_hash] = {"action": action, "success": success, "error": message}
        self.write("download_health", store)
        paused_count = sum(row["success"] and row["action"] == "pause" for row in outcomes.values())
        if paused_count:
            self.notify("【刷流任务下载异常】", f"{paused_count} 个未完成任务修复后仍无进展，已暂停；下载数据完整保留。")
        return outcomes

    @staticmethod
    def summarize(torrent_tasks: Dict[str, dict]) -> Dict[str, Any]:
        """从任务记录汇总卡住、低速和观察中的未完成下载。"""
        active_rows = [
            (str(torrent_hash), row)
            for torrent_hash, row in torrent_tasks.items()
            if isinstance(row, dict) and not row.get("deleted")
        ]
        stalled = [row for _, row in active_rows if row.get("download_health") == HEALTH_STALLED]
        slow = [row for _, row in active_rows if row.get("download_health") == HEALTH_SLOW]
        items = sorted(
            [
                (torrent_hash, row)
                for torrent_hash, row in active_rows
                if row.get("download_health") in {
                    HEALTH_STALLED,
                    HEALTH_SLOW,
                    HEALTH_QUEUED,
                    HEALTH_ERROR,
                }
            ],
            key=lambda item: (
                {
                    HEALTH_STALLED: 0,
                    HEALTH_SLOW: 1,
                    HEALTH_ERROR: 2,
                    HEALTH_QUEUED: 3,
                }.get(item[1].get("download_health"), 4),
                -float(item[1].get("download_health_since") or 0),
            ),
        )
        return {
            "stalled_count": len(stalled),
            "slow_count": len(slow),
            "queued_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_QUEUED),
            "checking_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_CHECKING),
            "error_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_ERROR),
            "paused_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_PAUSED),
            "observed_count": sum(
                1
                for _, row in active_rows
                if row.get("download_health") in {
                    HEALTH_UNKNOWN,
                    HEALTH_DOWNLOADING,
                    HEALTH_PAUSED,
                    HEALTH_QUEUED,
                    HEALTH_CHECKING,
                    HEALTH_ERROR,
                }
            ),
            "items": [
                {
                    "hash": torrent_hash,
                    "title": row.get("title"),
                    "state": row.get("download_health"),
                    "label": row.get("download_health_label") or health_label(row.get("download_health", HEALTH_UNKNOWN)),
                    "reason": row.get("download_health_reason"),
                    "action_error": row.get("download_health_action_error"),
                    "since": row.get("download_health_since"),
                    "avg_kbps": row.get("download_health_avg_kbps", 0),
                    "progress_delta": row.get("download_health_progress_delta", 0),
                    "size": row.get("size", 0),
                }
                for torrent_hash, row in items[:20]
            ],
        }

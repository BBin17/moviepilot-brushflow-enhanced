"""Explicit, audited removal of a stalled or slow incomplete download."""

from __future__ import annotations

from copy import deepcopy
import time
import math
from typing import Any, Callable


ELIGIBLE_HEALTH_STATES = frozenset({"stalled", "slow"})
UNRESOLVED_STATES = frozenset({"submitting", "pending_confirmation"})
PENDING_CONFIRMATION_GRACE_SECONDS = 60


class ManualDownloadDeleteError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ManualDownloadDeletionService:
    """Remove one user-selected torrent, never an entire health category."""

    def __init__(
        self,
        *,
        adapter: Any,
        read_data: Callable[[str], Any],
        write_data: Callable[[str, Any], None],
        clock: Callable[[], float] = time.time,
        slow_speed_kbps: float = 128,
    ):
        self.adapter = adapter
        self.read_data = read_data
        self.write_data = write_data
        self.clock = clock
        self.slow_speed_kbps = slow_speed_kbps

    def delete(
        self,
        *,
        torrent_hash: str,
        request_id: str,
        confirm: bool,
        delete_data: bool,
    ) -> dict:
        torrent_hash = str(torrent_hash or "").strip()
        request_id = str(request_id or "").strip()
        if not confirm:
            raise ManualDownloadDeleteError("confirmation_required", "请先确认单个种子的移除操作")
        if not torrent_hash or not request_id:
            raise ManualDownloadDeleteError("invalid_request", "缺少种子标识或请求编号")

        audit = self._audit_rows()
        previous = next((row for row in audit if row.get("request_id") == request_id), None)
        if previous:
            if previous.get("hash") != torrent_hash or bool(previous.get("delete_data")) != bool(delete_data):
                raise ManualDownloadDeleteError("request_conflict", "请求编号已用于另一项移除操作")
            # An HTTP retry must never submit a second destructive request.
            return {**deepcopy(previous), "duplicate": True}
        pending = next((row for row in reversed(audit)
                        if row.get("hash") == torrent_hash and row.get("state") in UNRESOLVED_STATES), None)
        if pending:
            try:
                still_present = torrent_hash in self.adapter.snapshot()
            except Exception as exc:
                raise ManualDownloadDeleteError(
                    "removal_pending", "这个种子的上一次移除结果仍在核对中，暂时无法读取下载器；请稍后刷新。"
                ) from exc
            if not still_present:
                self._mark_managed_removed(torrent_hash)
                pending.update({"state": "completed", "updated_at": self.clock(),
                                "message": "重新核对后确认：种子已从下载器移除"})
                self._store_audit(audit, pending)
                return {**deepcopy(pending), "reconciled": True}
            pending_age = self.clock() - self._number(pending.get("updated_at"), default=self.clock())
            if pending_age < PENDING_CONFIRMATION_GRACE_SECONDS:
                raise ManualDownloadDeleteError(
                    "removal_pending", "这个种子的上一次移除结果仍在核对中，请稍后刷新；暂不重复提交。"
                )
            pending.update({"state": "not_removed", "updated_at": self.clock(),
                            "message": "核对后下载器仍保留该种子；如仍需移除，请再次确认。"})
            self._store_audit(audit, pending)
            audit = self._audit_rows()

        managed = self.read_data("torrents") or {}
        managed_row = managed.get(torrent_hash) if isinstance(managed, dict) else None
        if not isinstance(managed_row, dict) or managed_row.get("deleted"):
            raise ManualDownloadDeleteError("torrent_not_managed", "该种子已不在当前任务管理中，请刷新列表")
        health_state = str(managed_row.get("download_health") or "")
        auto_paused = health_state == "paused" and bool(managed_row.get("download_health_auto_paused"))
        if health_state not in ELIGIBLE_HEALTH_STATES and not auto_paused:
            raise ManualDownloadDeleteError("health_changed", "该种子已不再属于卡住或低速状态，请刷新后确认")

        try:
            current = self.adapter.snapshot().get(torrent_hash)
        except Exception as exc:
            raise ManualDownloadDeleteError("downloader_unavailable", "无法重新读取下载器状态，本次没有提交移除") from exc
        if not current:
            raise ManualDownloadDeleteError("torrent_missing", "下载器中已找不到这个种子，请刷新状态")

        total_size = self._number(current.get("total_size"))
        completed = current.get("completed")
        if completed is None:
            completed = current.get("downloaded")
        if total_size <= 0 or completed is None:
            raise ManualDownloadDeleteError("progress_unknown", "无法确认种子是否仍未完成，为保护数据，本次不执行移除")
        completed = self._number(completed, default=-1)
        if completed < 0:
            raise ManualDownloadDeleteError("progress_unknown", "下载器返回的进度无效，本次不执行移除")
        if completed >= total_size:
            raise ManualDownloadDeleteError("torrent_completed", "种子已经完成下载，不会按卡住下载移除")

        health_store = self.read_data("download_health") or {}
        health_row = health_store.get(torrent_hash, {}) if isinstance(health_store, dict) else {}
        baseline = managed_row.get("download_completed_bytes")
        if baseline is None and isinstance(health_row, dict):
            samples = health_row.get("samples") or []
            if samples and isinstance(samples[-1], dict):
                baseline = samples[-1].get("downloaded")
        if baseline is None:
            raise ManualDownloadDeleteError("progress_baseline_missing", "缺少最近一次下载进度记录，请先重新检查种子")
        resumed = health_state != "slow" and completed > self._number(baseline, default=-1)
        recovered_speed = health_state == "slow" and self._number(current.get("download_speed")) >= self.slow_speed_kbps * 1024
        if resumed or recovered_speed:
            raise ManualDownloadDeleteError("download_resumed", "种子最近已有下载进度，已取消移除；请重新检查状态")

        now = self.clock()
        row = {
            "request_id": request_id,
            "hash": torrent_hash,
            "title": str(current.get("title") or managed_row.get("title") or torrent_hash),
            "size_bytes": total_size,
            "health_state": health_state,
            "completed_bytes": completed,
            "delete_data": bool(delete_data),
            "requested_at": now,
            "updated_at": now,
            "state": "submitting",
            "message": "正在向下载器提交单种移除请求",
        }
        self._store_audit(audit, row)  # Durable audit precedes the downloader mutation.

        try:
            result = self.adapter.remove(torrent_hash, delete_data=bool(delete_data))
        except Exception:
            # A transport error can happen after the downloader received the command.
            result = "uncertain"
        try:
            still_present = torrent_hash in self.adapter.snapshot()
        except Exception:
            still_present = True

        if not still_present:
            self._mark_managed_removed(torrent_hash, at=now)
            row.update({"state": "completed", "updated_at": self.clock(), "message": "已从下载器移除所选种子"})
        else:
            row.update({
                "state": "pending_confirmation",
                "updated_at": self.clock(),
                "downloader_result": result,
                "message": "移除请求已提交，但下载器仍显示该种子；为避免重复操作，结果待核对。",
            })
        self._store_audit(self._audit_rows(), row)
        return deepcopy(row)

    def _audit_rows(self) -> list[dict]:
        rows = self.read_data("manual_download_deletions") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def _store_audit(self, rows: list[dict], updated: dict) -> None:
        result = list(rows)
        found = False
        for index, row in enumerate(result):
            if row.get("request_id") == updated.get("request_id"):
                result[index] = dict(updated)
                found = True
                break
        if not found:
            result.append(dict(updated))
        unresolved = [row for row in result if row.get("state") in UNRESOLVED_STATES]
        settled = [row for row in result if row.get("state") not in UNRESOLVED_STATES]
        self.write_data("manual_download_deletions", sorted(unresolved + settled[-500:], key=lambda row: row.get("requested_at", 0)))

    def _mark_managed_removed(self, torrent_hash: str, *, at: float | None = None) -> None:
        managed = self.read_data("torrents") or {}
        row = managed.get(torrent_hash) if isinstance(managed, dict) else None
        if not isinstance(row, dict):
            return
        row.update({"deleted": True, "download_health": "manually_removed", "manual_removed_at": at or self.clock(), "deleted_time": at or self.clock()})
        self.write_data("torrents", managed)

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

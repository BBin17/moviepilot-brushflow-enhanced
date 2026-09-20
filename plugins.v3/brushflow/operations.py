"""Durable operation journal and task-local exclusion, independent of MoviePilot.

The lock is reserved before scheduling a worker; the same lock guards config
mutations. A persisted in-flight operation is interrupted on process restart,
never resumed as a destructive request. Reads never contact a downloader.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import threading
import time
from typing import Any, Callable
import uuid


TERMINAL_STATES = frozenset({"completed", "partial", "failed", "interrupted", "pending_confirmation"})
UNRESOLVED_ITEMS = frozenset({"submitting", "accepted", "pending_confirmation"})


class OperationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TaskService:
    def __init__(self, repository, *, locks=None, runtime=None, runtime_lock=None, clock=time.time):
        self.repository = repository
        self.locks = locks if locks is not None else {}
        self.runtime = runtime if runtime is not None else {}
        self.runtime_lock = runtime_lock or threading.RLock()
        self.clock = clock
        self._journal = {}
        self._by_id = {}
        self._by_request = {}

    def _load(self, task_id: str) -> list[dict]:
        if task_id not in self._journal:
            self._index(task_id, deepcopy(self.repository.get(task_id, "operations", []) or []))
        return self._journal[task_id]

    def _index(self, task_id: str, rows: list[dict]) -> None:
        self._journal[task_id] = rows
        self._by_id[task_id] = {row["operation_id"]: row for row in rows}
        self._by_request[task_id] = {row.get("request_id"): row for row in rows}

    def _rows(self, task_id: str) -> list[dict]:
        return deepcopy(self._load(task_id))

    def _save_rows(self, task_id: str, rows: list[dict]) -> None:
        # Never discard unconfirmed destructive requests to make room in a UI
        # history limit. They are required for reconciliation and duplicate guard.
        unresolved = [row for row in rows if any(item.get("state") in UNRESOLVED_ITEMS for item in row.get("items", []))]
        unresolved_ids = {row["operation_id"] for row in unresolved}
        terminal = [row for row in rows if row["operation_id"] not in unresolved_ids]
        retained = sorted(unresolved + terminal[-500:], key=lambda row: row["created_at"])
        self.repository.save(task_id, "operations", retained)
        self._index(task_id, retained)

    @contextmanager
    def guard(self, task_id: str, *, wait: bool = False):
        with self.runtime_lock:
            lock = self.locks.setdefault(task_id, threading.Lock())
        if not lock.acquire(blocking=wait):
            raise OperationError("task_busy", "任务已有操作正在执行，请稍后重试")
        try:
            yield
        finally:
            lock.release()

    def find_request(self, task_id: str, request_id: str) -> dict | None:
        with self.runtime_lock:
            self._load(task_id)
            return deepcopy(self._by_request[task_id].get(request_id))

    def get(self, task_id: str, operation_id: str) -> dict | None:
        with self.runtime_lock:
            self._load(task_id)
            return deepcopy(self._by_id[task_id].get(operation_id))

    def latest(self, task_id: str, kind: str | None = None) -> dict | None:
        with self.runtime_lock:
            return deepcopy(next((row for row in reversed(self._load(task_id)) if kind is None or row["kind"] == kind), None))

    def pending_hashes(self, task_id: str) -> set[str]:
        with self.runtime_lock:
            return {item["hash"] for row in self._load(task_id) for item in row.get("items", [])
                    if item.get("state") in UNRESOLVED_ITEMS}

    def update(self, task_id: str, operation_id: str, **updates: Any) -> dict:
        with self.runtime_lock:
            rows = self._rows(task_id)
            row = next((row for row in rows if row["operation_id"] == operation_id), None)
            if row is None:
                raise OperationError("operation_missing", "操作记录不存在")
            if "percent" in updates:
                updates["percent"] = max(float(row.get("percent") or 0), float(updates["percent"]))
            if updates.get("state") == "completed" and row.get("state") != "completed":
                updates.setdefault("display_until", self.clock() + 8)
                updates.setdefault("finished_at", self.clock())
            row.update(deepcopy(updates))
            row.update({"updated_at": self.clock(), "revision": row["revision"] + 1})
            self._save_rows(task_id, rows)
            current = self.runtime.setdefault(task_id, {})
            if current.get("operation_id") in (None, operation_id):
                current["operation_id"] = operation_id
                if row["kind"] == "cleanup":
                    current["cleanup_progress"] = deepcopy(row)
            return deepcopy(row)

    def recover_interrupted(self, task_id: str) -> None:
        with self.runtime_lock:
            rows = self._rows(task_id)
            changed = False
            for row in rows:
                if row.get("state") in {"queued", "running"}:
                    row.update({"state": "interrupted", "phase": "上次操作被中断，等待核对", "updated_at": self.clock(),
                                "finished_at": self.clock(), "display_until": None, "revision": row["revision"] + 1})
                    for item in row.get("items", []):
                        if item.get("state") in UNRESOLVED_ITEMS:
                            item["state"] = "pending_confirmation"
                        elif item.get("state") in {"pending", "reviewing"}:
                            item.update({"state": "skipped", "reason": "operation_interrupted"})
                    changed = True
            if changed:
                self._save_rows(task_id, rows)

    def submit(
        self, task_id: str, kind: str, worker: Callable[[str], dict | None], *,
        dispatch: Callable[[Callable], Any] | None = None, request_id: str | None = None,
        request_fingerprint: str | None = None, validate: Callable[[], None] | None = None,
    ) -> dict:
        request_id = request_id or uuid.uuid4().hex
        with self.runtime_lock:
            self._load(task_id)
            previous = self._by_request[task_id].get(request_id)
            if previous:
                if previous.get("request_fingerprint") != request_fingerprint or previous["kind"] != kind:
                    raise OperationError("request_conflict", "请求编号已用于另一项操作")
                return deepcopy(previous)
            lock = self.locks.setdefault(task_id, threading.Lock())
            if not lock.acquire(blocking=False):
                raise OperationError("task_busy", "任务已有操作正在执行")
            try:
                if validate:
                    validate()
                now = self.clock()
                row = {
                    "operation_id": uuid.uuid4().hex, "task_id": task_id, "kind": kind,
                    "request_id": request_id, "request_fingerprint": request_fingerprint,
                    "state": "queued", "phase": "待执行", "percent": 0, "revision": 1,
                    "created_at": now, "started_at": None, "updated_at": now, "finished_at": None,
                    "items": [], "display_until": None,
                }
                self._save_rows(task_id, self._rows(task_id) + [row])
                self.runtime.setdefault(task_id, {}).update({"state": "queued", "operation": kind,
                                                           "operation_id": row["operation_id"], "last_error": None})
            except BaseException:
                lock.release()
                raise

        dispatch_guard = threading.Lock()
        claimed, cancelled = False, False

        def run():
            nonlocal claimed
            with dispatch_guard:
                if claimed or cancelled:
                    return
                claimed = True
            try:
                self.update(task_id, row["operation_id"], state="running", phase="执行中", started_at=self.clock())
                with self.runtime_lock:
                    self.runtime[task_id]["state"] = "running"
                result = worker(row["operation_id"]) or {}
                final = self.get(task_id, row["operation_id"])
                state = result.pop("state", final["state"] if final["state"] in TERMINAL_STATES else "completed")
                self.update(task_id, row["operation_id"], **result, state=state, percent=100,
                            finished_at=self.clock(), display_until=self.clock() + 8 if state == "completed" else None)
            except Exception:
                # Exceptions may contain tracker passkeys; external-facing error
                # text is deliberately stable and details stay in per-item audit.
                current = self.get(task_id, row["operation_id"])
                for item in current.get("items", []):
                    if item.get("state") in UNRESOLVED_ITEMS:
                        item["state"] = "pending_confirmation"
                    elif item.get("state") in {"pending", "reviewing"}:
                        item.update({"state": "skipped", "reason_codes": ["operation_failed"]})
                uncertain = any(item.get("state") in UNRESOLVED_ITEMS for item in current.get("items", []))
                self.update(task_id, row["operation_id"], state="pending_confirmation" if uncertain else "failed",
                            phase="等待核对" if uncertain else "操作未完成", percent=100, items=current.get("items", []),
                            error="操作未完成；已提交的请求仅核对结果，不自动重发", finished_at=self.clock(), display_until=None)
            finally:
                try:
                    finished = self.get(task_id, row["operation_id"])
                    with self.runtime_lock:
                        self.runtime[task_id].update({"state": "idle", "operation": None})
                        self.runtime[task_id]["last_error"] = finished.get("error") if finished["state"] == "failed" else None
                finally:
                    lock.release()

        try:
            if dispatch is None:
                run()
            else:
                dispatch(run)
        except Exception:
            with dispatch_guard:
                cancelled = not claimed
            # A dispatcher may invoke the callback then fail, or enqueue then
            # fail. Only the party that owns execution may release its lock.
            if cancelled:
                try:
                    self.update(task_id, row["operation_id"], state="failed", phase="提交失败", percent=100,
                                error="后台执行器未接受操作", finished_at=self.clock())
                    with self.runtime_lock:
                        self.runtime[task_id].update({"state": "idle", "operation": None})
                finally:
                    lock.release()
        return self.get(task_id, row["operation_id"])

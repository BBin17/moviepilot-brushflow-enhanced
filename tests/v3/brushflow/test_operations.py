from copy import deepcopy
import threading

import pytest

from app.plugins.brushflow.operations import OperationError, TaskService
from app.plugins.brushflow.repository import TaskRepository


class MemoryStorage:
    def __init__(self):
        self.data = {}
        self.writes = []

    def get_data(self, key):
        return deepcopy(self.data.get(key))

    def save_data(self, key, value):
        self.writes.append(key)
        self.data[key] = deepcopy(value)


def service():
    return TaskService(TaskRepository(MemoryStorage()), clock=lambda: 1000)


def test_reservation_blocks_scheduler_and_configuration_until_worker_finishes():
    tasks = service()
    queue = []
    operation = tasks.submit("a", "check", lambda _: {"message": "done"}, dispatch=queue.append)
    assert operation["state"] == "queued"
    with pytest.raises(OperationError, match="执行"):
        with tasks.guard("a"):
            pytest.fail("busy task was allowed to mutate")
    with tasks.guard("b"):
        pass
    queue.pop()()
    assert tasks.get("a", operation["operation_id"])["state"] == "completed"
    with tasks.guard("a"):
        pass


def test_same_request_runs_once_and_conflicting_reuse_is_rejected():
    tasks = service()
    calls = []
    first = tasks.submit("a", "cleanup", lambda _: calls.append(1), request_id="request-1", request_fingerprint="preview-a")
    second = tasks.submit("a", "cleanup", lambda _: calls.append(2), request_id="request-1", request_fingerprint="preview-a")
    assert first["operation_id"] == second["operation_id"]
    assert calls == [1]
    with pytest.raises(OperationError, match="另一项"):
        tasks.submit("a", "cleanup", lambda _: None, request_id="request-1", request_fingerprint="preview-b")


def test_progress_is_monotonic_and_records_are_detached():
    tasks = service()
    queued = []
    row = tasks.submit("a", "cleanup", lambda _: None, dispatch=queued.append)
    tasks.update("a", row["operation_id"], percent=30)
    read = tasks.update("a", row["operation_id"], percent=10)
    assert read["percent"] == 30
    read["items"].append({"hash": "not-persisted"})
    assert not tasks.get("a", row["operation_id"])["items"]
    queued[0]()


def test_dispatch_failure_releases_lock_and_is_not_success():
    tasks = service()
    def reject(_):
        raise RuntimeError("queue down")
    row = tasks.submit("a", "cleanup", lambda _: None, dispatch=reject)
    assert row["state"] == "failed"
    assert row["display_until"] is None
    with tasks.guard("a"):
        pass


def test_restart_interrupts_without_resending_and_preserves_uncertain_hashes():
    tasks = service()
    row = tasks.submit("a", "cleanup", lambda _: None, dispatch=lambda _: None)
    tasks.update("a", row["operation_id"], items=[{"hash": "sent", "state": "submitting"}, {"hash": "unstarted", "state": "pending"}])
    restarted = TaskService(tasks.repository)
    restarted.recover_interrupted("a")
    result = restarted.get("a", row["operation_id"])
    assert result["state"] == "interrupted"
    assert result["items"][0]["state"] == "pending_confirmation"
    assert result["items"][1]["state"] == "skipped"
    assert restarted.pending_hashes("a") == {"sent"}


def test_simultaneous_submits_only_reserve_once():
    tasks = service()
    barrier = threading.Barrier(2)
    queued = []
    outcomes = []
    def submit():
        barrier.wait()
        try:
            outcomes.append(tasks.submit("a", "check", lambda _: None, dispatch=queued.append))
        except OperationError as error:
            outcomes.append(error.code)
    threads = [threading.Thread(target=submit) for _ in range(2)]
    for worker in threads:
        worker.start()
    for worker in threads:
        worker.join(timeout=3)
        assert not worker.is_alive()
    assert len(queued) == 1
    assert "task_busy" in outcomes
    queued[0]()


def test_dispatch_invokes_twice_then_raises_does_not_rerun_or_release_twice():
    tasks = service()
    calls = []
    def dispatch(worker):
        worker()
        worker()
        raise RuntimeError("dispatcher failed after delivery")
    row = tasks.submit("a", "cleanup", lambda _: calls.append(1), dispatch=dispatch)
    assert row["state"] == "completed"
    assert calls == [1]
    with tasks.guard("a"):
        pass


def test_dispatch_queues_then_rejects_cancels_late_callback():
    tasks = service()
    calls, queue = [], []
    def dispatch(worker):
        queue.append(worker)
        raise RuntimeError("rejected")
    row = tasks.submit("a", "cleanup", lambda _: calls.append(1), dispatch=dispatch)
    queue[0]()
    assert calls == []
    assert tasks.get("a", row["operation_id"])["state"] == "failed"


def test_polling_uses_an_index_and_never_reloads_full_journal(monkeypatch):
    tasks = service()
    row = tasks.submit("a", "cleanup", lambda _: {})
    monkeypatch.setattr(tasks.repository, "get", lambda *_: pytest.fail("poll read entire journal"))
    for _ in range(20):
        assert tasks.get("a", row["operation_id"])["state"] == "completed"


def test_non_reentrant_runtime_lock_does_not_deadlock_worker_completion():
    tasks = TaskService(TaskRepository(MemoryStorage()), runtime_lock=threading.Lock())
    worker = threading.Thread(target=lambda: tasks.submit("a", "check", lambda _: {}), daemon=True)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive()

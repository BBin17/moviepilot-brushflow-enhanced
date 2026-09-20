import threading
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.plugins.brushflow import BrushFlow, BrushTaskConfig
from app.plugins.brushflow.deletion_service import DeletionService
from test_cleanup_service import setup


def client_setup():
    cleanup, storage, downloader, now = setup()
    plugin = object.__new__(BrushFlow)
    plugin._enabled = True
    plugin._task_context = threading.local()
    plugin._task_configs = {"one": BrushTaskConfig(cleanup.document.to_runtime())}
    plugin._task_documents = {"one": cleanup.document}
    plugin._repository = cleanup.repository
    plugin._task_service = cleanup.operations
    plugin._task_locks = cleanup.operations.locks
    plugin._runtime = cleanup.operations.runtime
    plugin._runtime_lock = cleanup.operations.runtime_lock
    plugin._deletion_service = lambda task_id: DeletionService(
        repository=cleanup.repository, operations=cleanup.operations, adapter=cleanup.adapter,
        document=plugin._task_documents[task_id], clock=lambda: now[0], sleep=lambda _: None,
    )
    plugin._recalculate_statistics = lambda *_: None
    plugin._save_config = lambda: None
    plugin._refresh_scheduler = lambda: None
    plugin._validate_task_reference = lambda *_: True
    plugin._build_task_overview = lambda task_id: {"config": plugin._task_documents[task_id].model_dump(mode="json")}
    app = FastAPI()
    for route in plugin.get_api():
        app.add_api_route(route["path"], route["endpoint"], methods=route["methods"])
    return TestClient(app), plugin, downloader, now, storage


def test_http_cleanup_preview_confirm_progress_and_idempotent_retry():
    client, plugin, downloader, now, _ = client_setup()
    preview = client.post("/tasks/one/cleanup/preview", json={"revision": 3}).json()["data"]
    payload = {"preview_id": preview["preview_id"], "revision": 3, "request_id": "cleanup-request-1", "confirm": True}
    queued = []
    with patch("app.plugins.brushflow.ThreadHelper") as threads:
        threads.return_value.submit.side_effect = queued.append
        response = client.post("/tasks/one/actions/force_cleanup", json=payload).json()
        assert response["success"]
        operation_id = response["data"]["operation_id"]
        assert response["data"]["state"] == "queued"
        before = len(downloader.calls)
        status = client.get(f"/tasks/one/operations/{operation_id}").json()["data"]
        assert status["state"] == "queued"
        assert len(downloader.calls) == before  # Polling never reads qB.
        draft = plugin._task_documents["one"].model_dump(mode="json")
        draft["identity"]["name"] = "Cannot overwrite running task"
        refused = client.put("/tasks/one", json=draft).json()
        assert not refused["success"]
        assert refused["data"]["code"] == "task_busy"
        queued.pop()()
        finished = client.get(f"/tasks/one/operations/{operation_id}").json()["data"]
        assert finished["state"] == "completed"
        assert finished["deleted_count"] == 1
        now[0] += 400
        retry = client.post("/tasks/one/actions/force_cleanup", json=payload).json()
        assert retry["data"]["operation_id"] == operation_id
        assert queued == []


def test_old_client_cannot_execute_without_preview_or_confirmation():
    client, _, downloader, _, _ = client_setup()
    for body in (None, {}, {"confirm": True}):
        response = client.post("/tasks/one/actions/force_cleanup", json=body).json()
        assert not response["success"]
        assert response["data"]["code"] == "needs_preview"
    assert downloader.calls == []


def test_preview_revision_conflict_and_unknown_operation():
    client, _, downloader, _, _ = client_setup()
    response = client.post("/tasks/one/cleanup/preview", json={"revision": 2}).json()
    assert response["data"]["code"] == "revision_conflict"
    assert not response["success"]
    assert not downloader.calls
    response = client.get("/tasks/one/operations/unknown").json()
    assert response["data"]["code"] == "operation_missing"


def test_model_rejects_injected_candidate_list_and_invalid_token():
    client, _, _, _, _ = client_setup()
    response = client.post("/tasks/one/actions/force_cleanup", json={"items": [{"hash": "arbitrary"}]})
    assert response.status_code == 422
    response = client.post("/tasks/one/actions/force_cleanup", json={"preview_id": "not-a-token"})
    assert response.status_code == 422

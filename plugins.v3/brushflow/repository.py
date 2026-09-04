"""BrushFlow 9.0 任务仓库：集中管理任务历史、快照、审计和迁移备份。"""

from __future__ import annotations

from typing import Any, Iterable


class TaskRepository:
    def __init__(self, storage: Any):
        self._storage = storage

    @staticmethod
    def task_key(task_id: str, name: str) -> str:
        return f"task.{task_id}.{name}"

    def get(self, task_id: str, name: str, default: Any = None) -> Any:
        value = self._storage.get_data(self.task_key(task_id, name))
        return default if value is None else value

    def save(self, task_id: str, name: str, value: Any) -> None:
        self._storage.save_data(self.task_key(task_id, name), value)

    def delete_task(self, task_id: str, names: Iterable[str]) -> None:
        for name in names:
            self._storage.del_data(self.task_key(task_id, name))

    def append_bounded(self, task_id: str, name: str, row: dict, limit: int) -> list:
        rows = self.get(task_id, name, [])
        if not isinstance(rows, list):
            rows = []
        rows.append(dict(row))
        rows = rows[-max(int(limit), 1) :]
        self.save(task_id, name, rows)
        return rows

    def prepend_bounded(self, task_id: str, name: str, row: dict, limit: int) -> list:
        rows = self.get(task_id, name, [])
        if not isinstance(rows, list):
            rows = []
        rows.insert(0, dict(row))
        rows = rows[: max(int(limit), 1)]
        self.save(task_id, name, rows)
        return rows

    def get_global(self, key: str, default: Any = None) -> Any:
        value = self._storage.get_data(key)
        return default if value is None else value

    def save_global(self, key: str, value: Any) -> None:
        self._storage.save_data(key, value)

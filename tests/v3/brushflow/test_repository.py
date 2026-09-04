"""BrushFlow 9.0 任务仓库测试。"""

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[3] / "plugins.v3" / "brushflow" / "repository.py"
SPEC = importlib.util.spec_from_file_location("brushflow_repository", MODULE_PATH)
repository_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = repository_module
SPEC.loader.exec_module(repository_module)


class Storage:
    def __init__(self):
        self.rows = {}

    def get_data(self, key):
        return self.rows.get(key)

    def save_data(self, key, value):
        self.rows[key] = value

    def del_data(self, key):
        self.rows.pop(key, None)


def test_task_data_is_isolated_and_bounded():
    storage = Storage()
    repo = repository_module.TaskRepository(storage)
    for index in range(5):
        repo.append_bounded("coffee", "audit", {"index": index}, 3)
    repo.save("mteam", "audit", [{"index": 99}])
    assert [row["index"] for row in repo.get("coffee", "audit")] == [2, 3, 4]
    assert repo.get("mteam", "audit")[0]["index"] == 99


def test_delete_task_only_removes_requested_task_names():
    storage = Storage()
    repo = repository_module.TaskRepository(storage)
    repo.save("coffee", "runs", [1])
    repo.save("coffee", "audit", [2])
    repo.save("mteam", "runs", [3])
    repo.delete_task("coffee", ["runs", "audit"])
    assert repo.get("coffee", "runs") is None
    assert repo.get("mteam", "runs") == [3]

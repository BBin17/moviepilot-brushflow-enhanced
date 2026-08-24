"""BrushFlow 6.2.0 增强删种策略测试。"""

import threading

from app.plugins.brushflow import BrushFlow, BrushTaskConfig


def _make_plugin(task: BrushTaskConfig) -> BrushFlow:
    """构造仅包含删种策略上下文的插件实例。"""
    plugin = object.__new__(BrushFlow)
    plugin._task_configs = {task.id: task}
    plugin._task_context = threading.local()
    plugin._task_context.task_id = task.id
    return plugin


def _completed_info(seed_hours: float, inactive_minutes: float) -> dict:
    """返回完成种子的最小实时状态。"""
    return {
        "total_size": 100,
        "downloaded": 100,
        "uploaded": 20,
        "ratio": 0.2,
        "avg_upspeed": 0,
        "seeding_time": seed_hours * 3600,
        "iatime": inactive_minutes * 60,
    }


class TestDeleteSafety:
    """硬安全线优先于任一/全部条件和动态兜底。"""

    def setup_method(self):
        self.task = BrushTaskConfig(
            {
                "id": "safe-task",
                "name": "咖啡",
                "site_id": 1,
                "downloader": "qb",
                "min_seed_time": 72,
                "min_inactivetime": 360,
                "seed_time": 72,
                "seed_inactivetime": 360,
                "delete_condition_mode": "all",
            }
        )
        self.plugin = _make_plugin(self.task)

    def evaluate(self, info):
        return self.plugin._BrushFlow__evaluate_conditions_for_delete(info, {})

    def test_minimum_seed_time_blocks_delete(self):
        should_delete, reason = self.evaluate(_completed_info(24, 400))
        assert should_delete is False
        assert "最少保种时长" in reason

    def test_minimum_inactive_time_protects_active_seed(self):
        should_delete, reason = self.evaluate(_completed_info(72, 120))
        assert should_delete is False
        assert "最少未活动时间" in reason

    def test_all_conditions_delete_only_after_both_match(self):
        should_delete, reason = self.evaluate(_completed_info(72, 360))
        assert should_delete is True
        assert " 且 " in reason


class TestDynamicPriority:
    """智能淘汰优先选择闲置更久且上传更慢的种子。"""

    def test_smart_sort_prefers_idle_slow_seed(self):
        idle_slow = {
            "iatime": 12 * 3600,
            "avg_upspeed": 0,
            "seeding_time": 80 * 3600,
            "total_size": 10,
        }
        active_fast = {
            "iatime": 30 * 60,
            "avg_upspeed": 2 * 1024 * 1024,
            "seeding_time": 100 * 3600,
            "total_size": 50,
        }
        assert BrushFlow._dynamic_sort_key(idle_slow, "smart") > BrushFlow._dynamic_sort_key(
            active_fast,
            "smart",
        )

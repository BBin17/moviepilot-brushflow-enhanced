import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugins.v3" / "smartbrushflow"


def test_smartbrushflow_is_a_distinct_v3_plugin() -> None:
    """新插件必须拥有独立类名、配置前缀、事件和 qB 标签命名空间。"""
    source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    plugin_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SmartBrushFlow"
    )
    assert plugin_class.name == "SmartBrushFlow"
    assert 'plugin_config_prefix = "smartbrushflow_"' in source
    assert 'GLOBAL_BRUSH_TAG = "智能刷流"' in source
    assert 'startswith("智能刷流-")' in source
    assert "from app.sdk.plugin import _PluginBase" in (PLUGIN / "host.py").read_text(encoding="utf-8")

    metadata = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
    assert metadata["SmartBrushFlow"]["name"] == "智能刷流"
    assert metadata["SmartBrushFlow"]["version"] == "1.1.1"
    assert metadata["SmartBrushFlow"]["release"] is True


def test_old_and_new_plugin_sources_are_not_the_same_directory() -> None:
    assert (ROOT / "plugins.v3" / "brushflow").resolve() != PLUGIN.resolve()
    assert (PLUGIN / "__init__.py").exists()
    assert (PLUGIN / "src" / "components" / "SmartBrushFlow.vue").exists()

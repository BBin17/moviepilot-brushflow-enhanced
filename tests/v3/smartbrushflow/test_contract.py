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
    assert metadata["SmartBrushFlow"]["version"] == "1.1.5"
    assert metadata["SmartBrushFlow"]["release"] is True


def test_old_and_new_plugin_sources_are_not_the_same_directory() -> None:
    assert (ROOT / "plugins.v3" / "brushflow").resolve() != PLUGIN.resolve()
    assert (PLUGIN / "__init__.py").exists()
    assert (PLUGIN / "src" / "components" / "SmartBrushFlow.vue").exists()


def test_qb_temporary_add_tags_are_removed_after_hash_lookup() -> None:
    """临时定位标签不能和任务管理标签一起长期写入 qBittorrent。"""
    source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    assert "_TEMPORARY_QB_TAG_RE = re.compile(r\"^[A-Za-z0-9]{10}$\")" in source
    assert "torrents_remove_tags(tags=[tag], torrent_hashes=[torrent_hash])" in source
    assert "self._cleanup_temporary_qb_tags(task, seeding_torrents)" in source
    assert "self._remove_qbittorrent_torrent_tag(service, torrent_hash, random_tag)" in source


def test_save_path_is_normalized_to_a_string() -> None:
    source = (PLUGIN / "src" / "v9-ui.js").read_text(encoding="utf-8")
    wizard = (PLUGIN / "src" / "components" / "TaskWizardV9.vue").read_text(encoding="utf-8")
    assert "[savePath.value, savePath.path, savePath.title]" in source
    assert "typeof item !== 'function'" in source
    assert "not callable(candidate)" in (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    assert "normalizePathValue(value)" in wizard
    assert ':return-object="false"' in wizard

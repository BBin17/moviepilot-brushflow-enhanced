"""验证智能刷流的 V3 发布元数据、目录和独立插件身份。"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v3" / "smartbrushflow"
PLUGIN_ID = "SmartBrushFlow"
VERSION = "1.1.4"


def python_version() -> str:
    tree = ast.parse((PLUGIN / "version.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            return str(ast.literal_eval(node.value))
    raise RuntimeError("version.py 缺少 __version__")


def main() -> None:
    root_index = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
    package = json.loads((PLUGIN / "package.json").read_text(encoding="utf-8"))
    versions = {
        "plugins.v3/smartbrushflow/version.py": python_version(),
        "plugins.v3/smartbrushflow/package.json": package["version"],
        "package.v3.json": root_index[PLUGIN_ID]["version"],
    }
    if set(versions.values()) != {VERSION}:
        raise SystemExit(f"SmartBrushFlow 版本不一致：{versions}")
    entry = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
    host = (PLUGIN / "host.py").read_text(encoding="utf-8")
    required = (
        "class SmartBrushFlow(",
        'plugin_name = "智能刷流"',
        'plugin_config_prefix = "smartbrushflow_"',
    )
    missing = [item for item in required if item not in entry]
    missing.extend(
        item
        for item in (
            "from app.sdk.plugin import _PluginBase",
            "from app.schemas.types import EventType, MessageType as NotificationType",
        )
        if item not in host
    )
    if missing:
        raise SystemExit(f"SmartBrushFlow V3 契约缺失：{missing}")
    if (ROOT / "plugins.v3" / "brushflow").resolve() == PLUGIN.resolve():
        raise SystemExit("新插件目录不能与旧 BrushFlow 目录相同")
    duplicate = ROOT / "smartbrushflow-enhanced" / "plugins.v3" / "smartbrushflow"
    if duplicate.exists():
        raise SystemExit(f"发现重复插件源码副本：{duplicate}")
    print(f"SmartBrushFlow release metadata OK: {VERSION}")


if __name__ == "__main__":
    main()

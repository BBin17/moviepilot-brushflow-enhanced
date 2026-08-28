"""验证 BrushFlow 三处宿主可见版本与唯一版本源完全一致。"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v3" / "brushflow"


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
    expected = python_version()
    package_version = json.loads((PLUGIN / "package.json").read_text(encoding="utf-8"))["version"]
    market_version = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))["BrushFlow"]["version"]
    versions = {
        "plugins.v3/brushflow/version.py": expected,
        "plugins.v3/brushflow/package.json": package_version,
        "package.v3.json": market_version,
    }
    if len(set(versions.values())) != 1:
        raise SystemExit(f"BrushFlow 版本不一致：{versions}")
    duplicate = ROOT / "brushflow-enhanced" / "plugins.v3" / "brushflow"
    if duplicate.exists():
        raise SystemExit(f"发现重复插件源码副本：{duplicate}")
    print(f"BrushFlow release metadata OK: {expected}")


if __name__ == "__main__":
    main()

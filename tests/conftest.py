"""Load the repository plugin through an explicit, isolated host boundary.

Set BRUSHFLOW_HOST_TEST=1 and PYTHONPATH to the pinned MoviePilot checkout for
real-host contract runs. Import failure in that mode is a failure, not a skip.
"""

import importlib
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType

from support.host_stub import make_host_module


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "plugins.v3" / "brushflow"

if os.environ.get("BRUSHFLOW_HOST_TEST") == "1":
    importlib.import_module("app.plugins")
else:
    for name in ("app", "app.plugins"):
        module = ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    sys.modules["app"].plugins = sys.modules["app.plugins"]
    sys.modules["app.plugins.brushflow.host"] = make_host_module("app.plugins.brushflow.host")

spec = importlib.util.spec_from_file_location(
    "app.plugins.brushflow", PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)],
)
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
sys.modules["app.plugins"].brushflow = plugin
spec.loader.exec_module(plugin)

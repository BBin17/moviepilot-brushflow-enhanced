"""Load the independent SmartBrushFlow package against the explicit host stub."""
import importlib.util
from pathlib import Path
import sys

from support.host_stub import make_host_module


PACKAGE = Path(__file__).resolve().parents[3] / "plugins.v3" / "smartbrushflow"
NAME = "app.plugins.smartbrushflow"
sys.modules[f"{NAME}.host"] = make_host_module(f"{NAME}.host")
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)

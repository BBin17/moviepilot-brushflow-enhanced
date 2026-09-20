"""SmartBrushFlow historical takeover tests."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

from support.host_stub import make_host_module


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "plugins.v3" / "smartbrushflow"
sys.modules["app.plugins.smartbrushflow.host"] = make_host_module("app.plugins.smartbrushflow.host")
spec = importlib.util.spec_from_file_location(
    "app.plugins.smartbrushflow",
    PACKAGE / "__init__.py",
    submodule_search_locations=[str(PACKAGE)],
)
smartbrushflow = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = smartbrushflow
spec.loader.exec_module(smartbrushflow)
SmartBrushFlow = smartbrushflow.SmartBrushFlow


class FakeQbClient:
    def __init__(self):
        self.calls = []

    def torrents_add_tags(self, *, torrent_hashes, tags):
        self.calls.append((torrent_hashes, tags))


def test_historical_takeover_adds_the_current_management_tag_without_touching_data():
    client = FakeQbClient()
    service = SimpleNamespace(instance=SimpleNamespace(qbc=client))

    tagged = SmartBrushFlow._add_qbittorrent_tag(
        service,
        ["hash-a", "hash-b", "hash-a"],
        "智能刷流-咖啡",
    )

    assert tagged == 2
    assert client.calls == [("hash-a|hash-b", "智能刷流-咖啡")]

"""Explicit offline host boundary, never imported by production code.

Only declarations needed to load the plugin are supplied. Network, downloader,
scheduler and database services fail loudly unless a test injects its own fake.
This is NOT proof of compatibility with the actual MoviePilot SDK.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from types import ModuleType, SimpleNamespace
from typing import Any


@dataclass
class Response:
    success: bool = False
    message: str | None = None
    data: Any = None


class PluginBase:
    def get_data(self, key):
        return getattr(self, "_offline_data", {}).get(key)

    def save_data(self, key, value):
        if not hasattr(self, "_offline_data"):
            self._offline_data = {}
        self._offline_data[key] = value

    def del_data(self, key):
        getattr(self, "_offline_data", {}).pop(key, None)

    def update_config(self, config):
        self._offline_config = config

    def post_message(self, **kwargs):
        raise AssertionError("A test must inject its notification sink")


class UnavailableService:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        raise AssertionError(f"Offline tests must explicitly fake host service method: {name}")


class EventTypes(str, Enum):
    PluginReload = "PluginReload"
    PluginTriggered = "PluginTriggered"


class EventManager:
    def register(self, event_type):
        return lambda callback: callback


class StringUtilities:
    @staticmethod
    def generate_random_str(length):
        return "test-tag-"[:length].ljust(length, "x")

    @staticmethod
    def str_filesize(size):
        return f"{size} bytes"


def make_host_module(name):
    module = ModuleType(name)
    module.schemas = SimpleNamespace(Response=Response, DownloaderInfo=UnavailableService)
    module._PluginBase = PluginBase
    module.settings = SimpleNamespace(TZ="UTC", PROXY=None, PROXY_SERVER=None)
    module.logger = logging.getLogger("brushflow.offline")
    module.eventmanager = EventManager()
    module.EventType = EventTypes
    module.NotificationType = SimpleNamespace(SiteMessage="SiteMessage")
    module.MediaType = SimpleNamespace(TV="TV", MOVIE="MOVIE")
    for service in (
        "register_plugin_api", "TorrentsChain", "MediaInfo", "MetaInfo", "Event", "SiteOper", "SubscribeOper",
        "DownloaderHelper", "SitesHelper", "RequestUtils", "ThreadHelper", "Qbittorrent", "Transmission",
        "Scheduler", "ServiceInfo", "TorrentInfo",
    ):
        setattr(module, service, type(service, (UnavailableService,), {}))
    module.StringUtils = StringUtilities
    return module

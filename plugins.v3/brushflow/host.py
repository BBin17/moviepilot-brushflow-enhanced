"""MoviePilot V3 integration boundary.

Production always imports the actual host SDK. Offline tests replace *this
module* explicitly; there is no silent stub fallback in the shipped plugin.
Host contract CI must import this module against a pinned MoviePilot checkout.
"""

from app import schemas
from app.api.endpoints.plugin import register_plugin_api
from app.chain.torrents import TorrentsChain
from app.sdk.config import settings
from app.sdk.media import MediaInfo, MetaInfo
from app.sdk.events import Event, eventmanager
from app.db.oper.site import SiteOper
from app.db.oper.subscribe import SubscribeOper
from app.sdk.services import DownloaderHelper
from app.sdk.network import SitesHelper, RequestUtils
from app.runtime.thread import ThreadHelper
from app.sdk.logging import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.scheduler import Scheduler
from app.schemas import MediaType, NotificationType, ServiceInfo, TorrentInfo
from app.schemas.types import EventType
from app.sdk.utilities import StringUtils

__all__ = [
    "schemas", "register_plugin_api", "TorrentsChain", "settings", "MediaInfo", "MetaInfo",
    "Event", "eventmanager", "SiteOper", "SubscribeOper", "DownloaderHelper", "SitesHelper",
    "RequestUtils", "ThreadHelper", "logger", "Qbittorrent", "Transmission", "_PluginBase",
    "Scheduler", "MediaType", "NotificationType", "ServiceInfo", "TorrentInfo", "EventType", "StringUtils",
]

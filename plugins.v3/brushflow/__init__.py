import base64
import json
import re
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse

from apscheduler.triggers.cron import CronTrigger
from fastapi import Query

from app import schemas
from app.api.endpoints.plugin import register_plugin_api
from app.chain.torrents import TorrentsChain
from app.sdk.config import settings
from app.sdk.media import MediaInfo
from app.sdk.events import Event, eventmanager
from app.sdk.media import MetaInfo
from app.db.oper.site import SiteOper
from app.db.oper.subscribe import SubscribeOper
from app.sdk.services import DownloaderHelper
from app.sdk.network import SitesHelper
from app.runtime.thread import ThreadHelper
from app.sdk.logging import logger
from app.modules.qbittorrent import Qbittorrent
from app.modules.transmission import Transmission
from app.plugins import _PluginBase
from app.scheduler import Scheduler
from app.schemas import MediaType, NotificationType, ServiceInfo, TorrentInfo
from app.schemas.types import EventType
from app.sdk.network import RequestUtils
from app.sdk.utilities import StringUtils

from .models import BrushFlowSettingsPayload
from .signin import signin_site, success_message
from .version import __version__
from .decision import (
    SmartPolicy,
    TorrentObservation,
    adaptive_selection_policy,
    candidate_score,
    capacity_selection_policy,
    detect_invalid_seed,
    manual_cleanup_policy,
    rank_selection_candidates,
    select_deletions,
    size_range_matches,
    tracker_endpoint_domain,
)
from .learning import (
    feature_key,
    learning_summary,
    predict_yield,
    recent_yield_metrics,
    update_learning_state,
)
from .download_health import (
    DownloadHealthPolicy,
    HEALTH_COMPLETED,
    HEALTH_CHECKING,
    HEALTH_DOWNLOADING,
    HEALTH_ERROR,
    HEALTH_PAUSED,
    HEALTH_QUEUED,
    HEALTH_SLOW,
    HEALTH_STALLED,
    HEALTH_UNKNOWN,
    append_download_sample,
    assess_download_health,
    health_label,
    next_health_action,
    policy_for_profile,
)
from .v9 import TaskConfigV9, migrate_task_rows_v9
from .presentation import build_health_summary, deletion_quota_message
from .repository import TaskRepository


TASK_CONFIG_FIELDS = (
    "enabled",
    "notify",
    "site_id",
    "downloader",
    "brush_interval",
    "check_interval",
    "cron",
    "active_time_range",
    "site_ratio_control",
    "site_ratio_target",
    "site_ratio_reached_behavior",
    "disksize",
    "maxupspeed",
    "maxdlspeed",
    "maxdlcount",
    "freeleech",
    "hr",
    "include",
    "exclude",
    "size",
    "seeder",
    "timezone_offset",
    "pubtime",
    "min_seed_time",
    "smart_enabled",
    "smart_profile",
    "smart_selection_enabled",
    "smart_adaptive_enabled",
    "smart_selection_relax_filters",
    "smart_selection_min_score",
    "smart_selection_max_add_per_run",
    "smart_ratio_weight",
    "smart_cold_inactive_minutes",
    "smart_protect_active_demand",
    "smart_demand_confirmations",
    "smart_candidate_confirmations",
    "smart_candidate_confirmation_minutes",
    "smart_capacity_trigger_percent",
    "smart_capacity_target_percent",
    "invalid_seed_cleanup_enabled",
    "invalid_seed_confirmations",
    "smart_score_threshold",
    "smart_score_margin",
    "smart_max_delete_per_run",
    "smart_max_delete_percent_day",
    "smart_max_delete_capacity_percent_run",
    "smart_max_delete_capacity_percent_day",
    "smart_max_delete_gb_per_run",
    "smart_max_delete_gb_per_day",
    "smart_shadow_until",
    "smart_shadow_started_at",
    "smart_shadow_extensions",
    "smart_delete_paused",
    "smart_auto_activate",
    "delete_files",
    "up_speed",
    "dl_speed",
    "auto_archive_days",
    "save_path",
    "delete_except_tags",
    "except_subscribe",
    "qb_category",
    "site_hr_active",
    "site_skip_tips",
    "rss_support",
    "tag",
)

LEGACY_SITE_OVERRIDE_FIELDS = {
    "freeleech",
    "hr",
    "include",
    "exclude",
    "size",
    "seeder",
    "timezone_offset",
    "pubtime",
    "seed_time",
    "hr_seed_time",
    "seed_ratio",
    "seed_size",
    "download_time",
    "seed_avgspeed",
    "seed_inactivetime",
    "save_path",
    "qb_category",
    "site_hr_active",
    "site_skip_tips",
    "del_no_free",
    "rss_support",
}

GLOBAL_LIMIT_FIELDS = (
    "global_disksize",
    "global_maxdlcount",
    "global_maxupspeed",
    "global_maxdlspeed",
)

class BrushTaskConfig:
    """
    单个站点刷流任务的运行配置
    """

    def __init__(self, config: dict):
        """读取并标准化一项刷流任务配置"""
        self.id = str(config.get("id") or uuid.uuid4().hex)
        self.name = str(config.get("name") or "刷流任务").strip()
        self.enabled = bool(config.get("enabled", True))
        self.notify = bool(config.get("notify", True))
        self.site_id = int(config.get("site_id") or 0)
        self.downloader = str(config.get("downloader") or "").strip()
        self.brush_interval = max(int(self._parse_number(config.get("brush_interval")) or 10), 1)
        self.check_interval = max(int(self._parse_number(config.get("check_interval")) or 5), 1)
        self.cron = self._clean_text(config.get("cron"))
        self.active_time_range = self._clean_text(config.get("active_time_range"))
        self.site_ratio_control = bool(config.get("site_ratio_control", False))
        self.site_ratio_target = self._parse_number(config.get("site_ratio_target"))
        self.site_ratio_reached_behavior = str(
            config.get("site_ratio_reached_behavior") or "continue"
        )
        self.disksize = self._parse_number(config.get("disksize"))
        self.maxupspeed = self._parse_number(config.get("maxupspeed"))
        self.maxdlspeed = self._parse_number(config.get("maxdlspeed"))
        self.maxdlcount = self._parse_number(config.get("maxdlcount"))
        self.freeleech = config.get("freeleech", "free")
        self.hr = config.get("hr", "yes")
        self.include = self._clean_text(config.get("include"))
        self.exclude = self._clean_text(config.get("exclude"))
        self.size = self._clean_text(config.get("size"))
        self.seeder = self._clean_text(config.get("seeder"))
        self.timezone_offset = float(self._parse_number(config.get("timezone_offset")) or 0)
        self.pubtime = self._clean_text(config.get("pubtime"))
        self.min_seed_time = self._parse_number(config.get("min_seed_time"))
        self.smart_enabled = bool(config.get("smart_enabled", False))
        self.smart_profile = str(config.get("smart_profile") or "balanced")
        self.smart_selection_enabled = bool(
            config.get("smart_selection_enabled", self.smart_enabled)
        )
        self.smart_adaptive_enabled = bool(config.get("smart_adaptive_enabled", True))
        self.smart_selection_relax_filters = bool(
            config.get("smart_selection_relax_filters", True)
        )
        smart_selection_min_score = self._parse_number(
            config.get("smart_selection_min_score", 30)
        )
        self.smart_selection_min_score = (
            30 if smart_selection_min_score is None else smart_selection_min_score
        )
        self.smart_selection_max_add_per_run = int(
            self._parse_number(config.get("smart_selection_max_add_per_run", 5)) or 5
        )
        smart_ratio_weight = self._parse_number(config.get("smart_ratio_weight", 5))
        self.smart_ratio_weight = 5 if smart_ratio_weight is None else min(smart_ratio_weight, 5)
        smart_cold_inactive_minutes = self._parse_number(
            config.get("smart_cold_inactive_minutes", 360)
        )
        self.smart_cold_inactive_minutes = (
            360 if smart_cold_inactive_minutes is None else smart_cold_inactive_minutes
        )
        self.smart_protect_active_demand = bool(
            config.get("smart_protect_active_demand", True)
        )
        self.smart_demand_confirmations = max(
            1,
            min(int(self._parse_number(config.get("smart_demand_confirmations", 2)) or 2), 3),
        )
        self.smart_candidate_confirmations = max(
            1,
            int(self._parse_number(config.get("smart_candidate_confirmations", 3)) or 3),
        )
        self.smart_candidate_confirmation_minutes = float(
            self._parse_number(config.get("smart_candidate_confirmation_minutes", 30)) or 0
        )
        self.smart_capacity_trigger_percent = float(
            self._parse_number(config.get("smart_capacity_trigger_percent", 90)) or 90
        )
        self.smart_capacity_target_percent = float(
            self._parse_number(config.get("smart_capacity_target_percent", 85)) or 85
        )
        self.invalid_seed_cleanup_enabled = bool(
            config.get("invalid_seed_cleanup_enabled", False)
        )
        invalid_seed_confirmations = self._parse_number(
            config.get("invalid_seed_confirmations", 2)
        )
        self.invalid_seed_confirmations = max(
            1,
            min(int(invalid_seed_confirmations or 2), 5),
        )
        smart_score_threshold = self._parse_number(config.get("smart_score_threshold", 40))
        self.smart_score_threshold = 40 if smart_score_threshold is None else smart_score_threshold
        self.smart_score_margin = self._parse_number(config.get("smart_score_margin", 0)) or 0
        self.smart_max_delete_per_run = int(
            self._parse_number(config.get("smart_max_delete_per_run", 3)) or 3
        )
        self.smart_max_delete_percent_day = self._parse_number(
            config.get("smart_max_delete_percent_day", 5)
        )
        if self.smart_max_delete_percent_day is None:
            self.smart_max_delete_percent_day = 5
        self.smart_max_delete_capacity_percent_run = float(
            self._parse_number(config.get("smart_max_delete_capacity_percent_run", 4)) or 0
        )
        self.smart_max_delete_capacity_percent_day = float(
            self._parse_number(config.get("smart_max_delete_capacity_percent_day", 8)) or 0
        )
        self.smart_max_delete_gb_per_run = self._parse_number(
            config.get("smart_max_delete_gb_per_run")
        )
        self.smart_max_delete_gb_per_day = self._parse_number(
            config.get("smart_max_delete_gb_per_day")
        )
        self.smart_shadow_until = self._parse_number(config.get("smart_shadow_until"))
        self.smart_shadow_started_at = self._parse_number(config.get("smart_shadow_started_at"))
        self.smart_shadow_extensions = int(
            self._parse_number(config.get("smart_shadow_extensions", 0)) or 0
        )
        self.smart_delete_paused = bool(config.get("smart_delete_paused", False))
        self.smart_auto_activate = bool(config.get("smart_auto_activate", True))
        self.delete_files = bool(config.get("delete_files", True))
        self.up_speed = self._parse_number(config.get("up_speed"))
        self.dl_speed = self._parse_number(config.get("dl_speed"))
        self.auto_archive_days = self._parse_number(config.get("auto_archive_days"))
        self.save_path = self._clean_text(config.get("save_path"))
        self.delete_except_tags = self._clean_text(config.get("delete_except_tags"))
        self.except_subscribe = bool(config.get("except_subscribe", True))
        self.qb_category = self._clean_text(config.get("qb_category"))
        self.site_hr_active = bool(config.get("site_hr_active", False))
        self.site_skip_tips = bool(config.get("site_skip_tips", False))
        self.rss_support = bool(config.get("rss_support", False))
        self.tag = self._clean_text(config.get("tag"))

    @property
    def brush_tag(self) -> str:
        """返回当前任务在下载器中使用的标签（默认按站点名称生成，保证可读性）"""
        if self.tag:
            return self.tag
        site_name = BrushFlow._get_site_name(self.site_id) if self.site_id else None
        return f"刷流-{site_name}" if site_name else f"刷流-{self.id[:8]}"

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        """把空白文本标准化为 None"""
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _parse_number(value: Any) -> Optional[Union[int, float]]:
        """兼容解析历史配置中的整数、浮点数和空值"""
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return int(number) if number.is_integer() else number

    def to_dict(self) -> Dict[str, Any]:
        """返回可持久化和供前端编辑的任务配置"""
        data = {"id": self.id, "name": self.name}
        data.update({field: getattr(self, field) for field in TASK_CONFIG_FIELDS})
        return data


class BrushFlow(_PluginBase):
    """
    多站点独立任务刷流插件
    """

    plugin_name = "站点刷流增强版"
    plugin_desc = "本地 30 天收益学习、硬安全线、容量闭环与可解释智能选删种。"
    plugin_icon = "brush-flow.png"
    plugin_version = __version__
    plugin_author = "jxxghp,InfinityPacer,Seed680"
    author_url = "https://github.com/InfinityPacer"
    plugin_config_prefix = "brushflow_"
    plugin_order = 21
    auth_level = 2

    DATA_SCHEMA_VERSION = 9
    MAX_RUN_HISTORY = 50
    GLOBAL_BRUSH_TAG = "刷流"
    SIGNIN_DATA_KEY = "signin_history"
    TASK_DATA_NAMES = (
        "torrents",
        "archived",
        "unmanaged",
        "statistic",
        "runs",
        "smart_history",
        "smart_deletions",
        "smart_plan",
        "smart_candidates",
        "learning_state",
        "decision_audit",
        "strategy_state",
        "download_health",
        "invalid_seed_history",
        "invalid_seed_plan",
    )

    def init_plugin(self, config: dict = None) -> None:
        """初始化全局开关、任务配置、运行锁和历史数据迁移"""
        raw_config = config or {}
        self._repository = TaskRepository(self)
        self._task_context = threading.local()
        self._task_locks: Dict[str, threading.Lock] = {}
        self._brush_lock = threading.Lock()
        self._runtime_lock = threading.Lock()
        self._runtime: Dict[str, dict] = {}
        self._subscribe_infos: Dict[str, List[str]] = {}
        self._enabled = bool(raw_config.get("enabled", False))
        self._show_sidebar_nav = bool(raw_config.get("show_sidebar_nav", True))
        self._signin_enabled = bool(raw_config.get("signin_enabled", False))
        self._signin_notify = bool(raw_config.get("signin_notify", True))
        self._signin_cron = str(raw_config.get("signin_cron") or "17 7 * * *").strip()
        self._signin_sites = self._normalize_site_ids(raw_config.get("signin_sites"))
        self._signin_lock = threading.Lock()

        legacy_config = not isinstance(raw_config.get("tasks"), list) and bool(raw_config.get("brushsites"))
        for field in GLOBAL_LIMIT_FIELDS:
            value = raw_config.get(field)
            if value is None and legacy_config:
                value = raw_config.get(field.removeprefix("global_"))
            parsed_value = BrushTaskConfig._parse_number(value)
            setattr(self, f"_{field}", parsed_value if parsed_value and parsed_value > 0 else None)
        task_rows = raw_config.get("tasks") if isinstance(raw_config.get("tasks"), list) else None
        migrated = task_rows is None and bool(raw_config.get("brushsites"))
        if migrated:
            task_rows = self._migrate_legacy_config(raw_config)
        task_rows = task_rows or []
        v9_backups = self._repository.get_global("v9_task_config_backups", {}) or {}
        task_rows, v9_backups, migrated_v9 = migrate_task_rows_v9(task_rows, v9_backups)
        if migrated_v9:
            self._repository.save_global("v9_task_config_backups", v9_backups)

        self._task_configs: Dict[str, BrushTaskConfig] = {}
        self._task_documents: Dict[str, TaskConfigV9] = {}
        for row in task_rows:
            if not isinstance(row, dict):
                continue
            document = TaskConfigV9.model_validate(row)
            task = BrushTaskConfig(document.to_runtime())
            if not self._validate_task_reference(task, notify=False):
                task.enabled = False
            self._task_configs[task.id] = task
            self._task_documents[task.id] = document
            self._task_locks[task.id] = threading.Lock()
            self._runtime[task.id] = {"state": "idle", "operation": None, "last_error": None}

        normalized = self._current_config()
        if migrated or migrated_v9 or raw_config != normalized:
            self.update_config(normalized)
        self._migrate_legacy_data()
        self._migrate_torrent_identity_data()

        # V5 为任务增加了唯一标签；启动时回收升级前已经失去任务配置的孤立标签。
        if self._enabled:
            try:
                ThreadHelper().submit(self._cleanup_unused_task_tags)
            except Exception as err:
                logger.warning(f"提交刷流标签清理任务失败：{str(err)}")

        if migrated and raw_config.get("onlyonce") and self._enabled:
            for task in self._task_configs.values():
                if task.enabled:
                    ThreadHelper().submit(self.brush, task.id)
                    ThreadHelper().submit(self.check, task.id)

    def get_state(self) -> bool:
        """返回插件全局启用状态"""
        return bool(getattr(self, "_enabled", False))

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """当前插件不注册远程命令"""
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦组件渲染插件界面"""
        return "vue", "dist/assets"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """向主界面整理分组注册刷流任务入口"""
        if not self.get_state() or not getattr(self, "_show_sidebar_nav", True):
            return []
        return [
            {
                "nav_key": "main",
                "title": "站点刷流",
                "icon": "mdi-sync",
                "section": "organize",
                "permission": "manage",
                "order": 45,
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """注册 Vue 工作台使用的刷流任务 API"""
        return [
            {
                "path": "/status",
                "endpoint": self.get_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取刷流任务总览",
            },
            {
                "path": "/settings",
                "endpoint": self.update_settings,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "更新刷流插件设置",
            },
            {
                "path": "/tasks",
                "endpoint": self.create_task,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "创建刷流任务",
            },
            {
                "path": "/tasks/{task_id}",
                "endpoint": self.get_task_detail,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取刷流任务详情",
            },
            {
                "path": "/tasks/{task_id}/torrents",
                "endpoint": self.get_task_torrents,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "分页获取任务种子",
            },
            {
                "path": "/tasks/{task_id}/events",
                "endpoint": self.get_task_events,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "分页获取任务事件",
            },
            {
                "path": "/tasks/{task_id}",
                "endpoint": self.update_task,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "更新刷流任务",
            },
            {
                "path": "/tasks/{task_id}",
                "endpoint": self.delete_task,
                "methods": ["DELETE"],
                "auth": "bear",
                "summary": "删除刷流任务",
            },
            {
                "path": "/tasks/{task_id}/actions/{action}",
                "endpoint": self.run_task_action,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "执行统一任务操作",
            },
            {
                "path": "/signin/run",
                "endpoint": self.run_signin,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即执行站点签到",
            },
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """Vue 配置组件只需要接收当前配置模型"""
        return [], self._current_config()

    def get_page(self) -> List[dict]:
        """Vue 详情组件自行通过插件 API 获取页面数据"""
        return []

    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], None]]:
        """保留原有仪表板入口并改由 Vue 组件渲染"""
        if not self.get_state():
            return None
        return (
            {"cols": 12, "sm": 6, "md": 6},
            {
                "title": "站点刷流",
                "subtitle": "多任务运行概览",
                "refresh": 30,
                "border": True,
            },
            None,
        )

    def get_service(self) -> List[Dict[str, Any]]:
        """为刷流、检查、促销和站点签到注册宿主公共服务"""
        if not self.get_state():
            return []
        services: List[Dict[str, Any]] = []
        for task in self._task_configs.values():
            if not task.enabled:
                continue
            if task.cron:
                try:
                    brush_trigger: Union[str, CronTrigger] = CronTrigger.from_crontab(task.cron)
                    brush_kwargs: Dict[str, Any] = {}
                except ValueError as err:
                    logger.error(f"刷流任务 [{task.name}] CRON 表达式无效：{str(err)}")
                    brush_trigger = "interval"
                    brush_kwargs = {"minutes": task.brush_interval}
            else:
                brush_trigger = "interval"
                brush_kwargs = {"minutes": task.brush_interval}
            services.append(
                {
                    "id": f"Task_{task.id}_Brush",
                    "name": f"刷流刷新 - {task.name}",
                    "trigger": brush_trigger,
                    "func": self.brush,
                    "kwargs": brush_kwargs,
                    "func_kwargs": {"task_id": task.id},
                }
            )
            services.append(
                {
                    "id": f"Task_{task.id}_Check",
                    "name": f"刷流检查 - {task.name}",
                    "trigger": "interval",
                    "func": self.check,
                    "kwargs": {"minutes": task.check_interval},
                    "func_kwargs": {"task_id": task.id},
                }
            )
        if self._signin_enabled:
            try:
                signin_trigger: Union[str, CronTrigger] = CronTrigger.from_crontab(
                    self._signin_cron,
                    timezone=settings.TZ,
                )
                services.append(
                    {
                        "id": "BrushFlow_SignIn",
                        "name": "站点自动签到",
                        "trigger": signin_trigger,
                        "func": self.sign_in,
                        "kwargs": {},
                    }
                )
            except (TypeError, ValueError) as err:
                logger.error(f"站点自动签到 CRON 表达式无效：{str(err)}")
        return services

    def stop_service(self) -> None:
        """插件不再维护私有调度器，公共服务由宿主统一停止"""
        with getattr(self, "_runtime_lock", threading.Lock()):
            for runtime in getattr(self, "_runtime", {}).values():
                runtime.update({"state": "idle", "operation": None})

    @property
    def service_info(self) -> Optional[ServiceInfo]:
        """获取当前任务绑定的下载器服务"""
        task = self._get_task_config()
        if not task or not task.downloader:
            return None
        service = DownloaderHelper().get_service(name=task.downloader)
        if not service:
            self._log_and_notify_error(f"刷流任务 [{task.name}] 获取下载器实例失败，请检查配置")
            return None
        if service.instance.is_inactive():
            self._log_and_notify_error(f"刷流任务 [{task.name}] 下载器未连接")
            return None
        return service

    @property
    def downloader(self) -> Optional[Union[Qbittorrent, Transmission]]:
        """返回当前任务绑定的下载器实例"""
        service = self.service_info
        return service.instance if service else None

    def get_status(self) -> schemas.Response:
        """返回全局设置、任务摘要和前端可选项"""
        return schemas.Response(success=True, data=self._build_status_data())

    def update_settings(self, payload: BrushFlowSettingsPayload) -> schemas.Response:
        """更新插件全局开关、自动签到配置并刷新宿主任务调度"""
        signin_cron = str(payload.signin_cron or "17 7 * * *").strip()
        try:
            CronTrigger.from_crontab(signin_cron, timezone=settings.TZ)
        except (TypeError, ValueError) as err:
            return schemas.Response(success=False, message=f"站点签到 CRON 无效：{str(err)}")
        self._enabled = payload.enabled
        self._show_sidebar_nav = payload.show_sidebar_nav
        self._signin_enabled = payload.signin_enabled
        self._signin_notify = payload.signin_notify
        self._signin_cron = signin_cron
        self._signin_sites = self._normalize_site_ids(payload.signin_sites)
        for field in GLOBAL_LIMIT_FIELDS:
            setattr(self, f"_{field}", getattr(payload, field))
        self._save_config()
        self._refresh_scheduler()
        return schemas.Response(success=True, data=self._build_status_data())

    def create_task(self, payload: TaskConfigV9) -> schemas.Response:
        """创建一个站点与下载器均独立的刷流任务"""
        document = payload.model_copy(deep=True)
        document.id = uuid.uuid4().hex
        document.revision = 1
        if document.deletion.enabled:
            now = time.time()
            document.deletion.observation_started_at = now
            document.deletion.observation_until = now + 48 * 3600
        task = BrushTaskConfig(document.to_runtime())
        if not self._validate_task_reference(task):
            return schemas.Response(success=False, message="站点或下载器配置无效")
        self._task_configs[task.id] = task
        self._task_documents[task.id] = document
        self._task_locks[task.id] = threading.Lock()
        self._runtime[task.id] = {"state": "idle", "operation": None, "last_error": None}
        self._save_config()
        self._refresh_scheduler()
        return schemas.Response(success=True, data=self._build_task_overview(task.id))

    def get_task_detail(self, task_id: str) -> schemas.Response:
        """返回任务配置、统计和统一展示摘要；种子与事件使用独立分页接口。"""
        if task_id not in self._task_configs:
            return schemas.Response(success=False, message="刷流任务不存在")
        return schemas.Response(
            success=True,
            data=self._build_task_overview(task_id),
        )

    def update_task(self, task_id: str, payload: TaskConfigV9) -> schemas.Response:
        """更新任务配置并保持原任务 ID 与历史数据关联"""
        if task_id not in self._task_configs:
            return schemas.Response(success=False, message="刷流任务不存在")
        if self._is_task_busy(task_id):
            return schemas.Response(success=False, message="任务正在执行，请稍后再修改")
        previous_document = self._task_documents[task_id]
        if payload.revision != previous_document.revision:
            return schemas.Response(success=False, message="任务配置已被更新，请刷新后重试")
        document = payload.model_copy(deep=True)
        document.id = task_id
        document.revision = previous_document.revision + 1
        previous = self._task_configs[task_id]
        newly_enabled = document.deletion.enabled and not previous.smart_enabled
        risk_increased = bool(
            document.deletion.enabled
            and (
                document.strategy.overrides.deletion_score_threshold > previous.smart_score_threshold
                or document.strategy.overrides.candidate_confirmations < previous.smart_candidate_confirmations
                or document.strategy.overrides.confirmation_minutes < previous.smart_candidate_confirmation_minutes
            )
        )
        if newly_enabled or risk_increased:
            now = time.time()
            document.deletion.observation_started_at = now
            document.deletion.observation_until = now + (48 if newly_enabled else 24) * 3600
        task = BrushTaskConfig(document.to_runtime())
        if not self._validate_task_reference(task):
            return schemas.Response(success=False, message="站点或下载器配置无效")
        self._task_configs[task_id] = task
        self._task_documents[task_id] = document
        self._save_config()
        self._refresh_scheduler()
        return schemas.Response(success=True, data=self._build_task_overview(task_id))

    def get_task_torrents(
        self,
        task_id: str,
        state: str = Query("active", pattern="^(active|deleted|all)$"),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=10, le=200),
    ) -> schemas.Response:
        if task_id not in self._task_configs:
            return schemas.Response(success=False, message="刷流任务不存在")
        return schemas.Response(
            success=True,
            data=self._paginate_task_torrents(task_id, state=state, page=page, page_size=page_size),
        )

    def get_task_events(
        self,
        task_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=10, le=100),
    ) -> schemas.Response:
        if task_id not in self._task_configs:
            return schemas.Response(success=False, message="刷流任务不存在")
        rows = self._get_task_data(task_id, "runs") or []
        start = (page - 1) * page_size
        return schemas.Response(
            success=True,
            data={"items": rows[start : start + page_size], "total": len(rows), "page": page, "page_size": page_size},
        )

    def delete_task(self, task_id: str) -> schemas.Response:
        """删除没有活跃种子的任务及其独立历史数据"""
        task = self._task_configs.get(task_id)
        if not task:
            return schemas.Response(success=False, message="刷流任务不存在")
        if self._is_task_busy(task_id):
            return schemas.Response(success=False, message="任务正在执行，请稍后再删除")
        torrents = self._get_task_data(task_id, "torrents") or {}
        active_count = sum(1 for item in torrents.values() if not item.get("deleted"))
        if active_count:
            return schemas.Response(success=False, message="任务仍有活跃种子，请先处理后再删除")
        self._task_configs.pop(task_id, None)
        self._task_documents.pop(task_id, None)
        self._task_locks.pop(task_id, None)
        self._runtime.pop(task_id, None)
        self._repository.delete_task(task_id, self.TASK_DATA_NAMES)
        self._save_config()
        self._refresh_scheduler()
        try:
            # 删除接口不应被下载器网络请求阻塞，标签清理由后台线程完成。
            ThreadHelper().submit(self._cleanup_unused_task_tag, task)
        except Exception as err:
            logger.warning(f"提交刷流任务标签清理失败：{str(err)}")
        return schemas.Response(success=True, data=self._build_status_data())

    def run_task(self, task_id: str) -> schemas.Response:
        """异步提交单个任务的立即刷流刷新"""
        return self._submit_task_operation(task_id, "brush")

    def check_task(self, task_id: str) -> schemas.Response:
        """异步提交单个任务的立即状态检查"""
        return self._submit_task_operation(task_id, "check")

    def run_task_action(self, task_id: str, action: str) -> schemas.Response:
        """9.0 单一交互入口；旧版策略路由不再注册。"""
        task = self._task_configs.get(task_id)
        document = self._task_documents.get(task_id)
        if not task or not document:
            return schemas.Response(success=False, message="刷流任务不存在")
        if action == "run_selection":
            return self.run_task(task_id)
        if action == "run_check":
            return self.check_task(task_id)
        if action == "force_cleanup":
            if not document.deletion.enabled:
                return schemas.Response(success=False, message="当前任务未启用自动删种")
            return self._submit_task_operation(task_id, "force_cleanup")
        if self._is_task_busy(task_id):
            return schemas.Response(success=False, message="任务正在执行，请稍后再操作")
        if action in {"retry_stalled", "pause_stalled"}:
            torrents = self._get_task_data(task_id, "torrents") or {}
            hashes = [
                str(torrent_hash)
                for torrent_hash, row in torrents.items()
                if isinstance(row, dict)
                and not row.get("deleted")
                and row.get("download_health") in {HEALTH_STALLED, HEALTH_SLOW, HEALTH_PAUSED}
            ]
            if not hashes:
                return schemas.Response(success=True, message="当前没有需要处理的异常下载", data=self._build_task_overview(task_id))
            with self._task_scope(task_id):
                self.__apply_download_health_actions(
                    hashes if action == "retry_stalled" else [],
                    hashes if action == "pause_stalled" else [],
                )
            health_store = self._get_task_data(task_id, "download_health") or {}
            now = time.time()
            for torrent_hash in hashes:
                record = health_store.get(torrent_hash)
                if not isinstance(record, dict):
                    continue
                if action == "retry_stalled":
                    record.update({"repair_at": now, "paused_at": None})
                else:
                    record["paused_at"] = now
            self._save_task_data(task_id, "download_health", health_store)
            self._append_decision_audit(task_id, {"at": now, "kind": "task_action", "action": action, "hashes": hashes})
            return schemas.Response(
                success=True,
                message="异常下载已重新汇报并恢复" if action == "retry_stalled" else "异常下载已暂停并保留数据",
                data=self._build_task_overview(task_id),
            )
        now = time.time()
        messages = {
            "pause_task": "任务已暂停",
            "resume_task": "任务已恢复",
            "activate_deletion": "已结束观察并启用自动删种",
            "extend_observation": "安全观察已延长24小时",
            "pause_deletion": "自动删种已暂停",
            "resume_deletion": "自动删种已恢复",
        }
        if action not in messages:
            return schemas.Response(success=False, message="未知任务操作")
        if action in {"activate_deletion", "extend_observation", "pause_deletion", "resume_deletion"} and not document.deletion.enabled:
            return schemas.Response(success=False, message="当前任务未启用自动删种")
        if action in {"pause_task", "resume_task"}:
            task.enabled = action == "resume_task"
            document.identity.enabled = task.enabled
        elif action == "activate_deletion":
            task.smart_shadow_until = None
            task.smart_delete_paused = False
            document.deletion.observation_until = None
            document.deletion.paused = False
        elif action == "extend_observation":
            until = max(float(task.smart_shadow_until or 0), now) + 24 * 3600
            task.smart_shadow_until = until
            task.smart_shadow_extensions += 1
            document.deletion.observation_until = until
            document.deletion.observation_extensions += 1
        elif action in {"pause_deletion", "resume_deletion"}:
            paused = action == "pause_deletion"
            task.smart_delete_paused = paused
            document.deletion.paused = paused
        document.revision += 1
        self._append_decision_audit(task_id, {"at": now, "kind": "task_action", "action": action})
        self._save_config()
        self._refresh_scheduler()
        return schemas.Response(success=True, message=messages[action], data=self._build_task_overview(task_id))

    def run_signin(self) -> schemas.Response:
        """异步执行一次站点签到；手动执行不要求自动签到开关已打开。"""
        try:
            ThreadHelper().submit(self.sign_in, True)
            return schemas.Response(success=True, message="站点签到已提交")
        except Exception as err:
            logger.error(f"提交站点签到失败：{str(err)}")
            return schemas.Response(success=False, message=f"提交站点签到失败：{str(err)}")

    def _append_decision_audit(self, task_id: str, row: dict) -> None:
        """保存最近 500 条完整决策，实际调用下载器前也必须先写入。"""
        self._repository.append_bounded(task_id, "decision_audit", row, 500)

    @eventmanager.register(EventType.PluginReload)
    def reload(self, event: Event) -> None:
        """插件重载后重新注册动态 API 和任务调度"""
        if event and event.event_data.get("plugin_id") == self.__class__.__name__:
            register_plugin_api(plugin_id=self.__class__.__name__)
            Scheduler().update_plugin_job(self.__class__.__name__)

    def _current_config(self) -> Dict[str, Any]:
        """返回插件当前可持久化配置快照"""
        config = {
            "schema_version": self.DATA_SCHEMA_VERSION,
            "enabled": bool(getattr(self, "_enabled", False)),
            "show_sidebar_nav": bool(getattr(self, "_show_sidebar_nav", True)),
            "signin_enabled": bool(getattr(self, "_signin_enabled", False)),
            "signin_notify": bool(getattr(self, "_signin_notify", True)),
            "signin_cron": getattr(self, "_signin_cron", "17 7 * * *"),
            "signin_sites": list(getattr(self, "_signin_sites", [])),
            "tasks": [
                self._serialize_task_document(task_id)
                for task_id in getattr(self, "_task_configs", {})
            ],
        }
        config.update({field: getattr(self, f"_{field}", None) for field in GLOBAL_LIMIT_FIELDS})
        return config

    def _serialize_task_document(self, task_id: str) -> dict:
        """把运行期允许变化的状态同步回9.0任务文档。"""
        task = self._task_configs[task_id]
        document = self._task_documents[task_id].model_copy(deep=True)
        document.identity.enabled = task.enabled
        document.deletion.paused = task.smart_delete_paused
        document.deletion.observation_started_at = task.smart_shadow_started_at
        document.deletion.observation_until = task.smart_shadow_until
        document.deletion.observation_extensions = task.smart_shadow_extensions
        self._task_documents[task_id] = document
        return document.model_dump(mode="json")

    def _save_config(self) -> None:
        """保存全局设置和全部任务配置"""
        self.update_config(self._current_config())

    def _refresh_scheduler(self) -> None:
        """通知宿主按最新任务列表重建插件服务"""
        try:
            Scheduler().update_plugin_job(self.__class__.__name__)
        except Exception as err:
            logger.error(f"更新站点刷流调度失败：{str(err)}")

    @staticmethod
    def _normalize_site_ids(value: Any) -> List[int]:
        """标准化签到站点 ID，并去重、忽略无效值。"""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if not isinstance(value, (list, tuple, set)):
            return []
        site_ids: List[int] = []
        for item in value:
            try:
                site_id = int(item)
            except (TypeError, ValueError):
                continue
            if site_id > 0 and site_id not in site_ids:
                site_ids.append(site_id)
        return site_ids

    def _signin_site_rows(self) -> List[dict]:
        """返回当前配置可用的私有站点信息；空选择时仅使用刷流任务站点。"""
        indexers = [
            item
            for item in SitesHelper().get_indexers()
            if isinstance(item, dict) and not item.get("public")
        ]
        by_id = {int(item.get("id")): item for item in indexers if item.get("id")}
        selected_ids = list(self._signin_sites)
        if not selected_ids:
            selected_ids = list(
                dict.fromkeys(
                    task.site_id
                    for task in self._task_configs.values()
                    if task.enabled and task.site_id
                )
            )
        rows: List[dict] = []
        for site_id in selected_ids:
            site = by_id.get(int(site_id))
            if not site:
                continue
            row = dict(site)
            if not row.get("url") and row.get("domain"):
                row["url"] = f"https://{str(row['domain']).strip('/') }"
            rows.append(row)
        return rows

    @staticmethod
    def _signin_success(message: str) -> bool:
        """把签到模块结果统一判定为当天完成。"""
        return success_message(message)

    def _signin_history(self) -> Dict[str, dict]:
        """读取签到历史，并兼容早期空值或损坏数据。"""
        history = self.get_data(self.SIGNIN_DATA_KEY) or {}
        return history if isinstance(history, dict) else {}

    def _build_signin_status(self) -> Dict[str, Any]:
        """构造自动签到配置和最近结果，供工作台展示。"""
        history = self._signin_history()
        today_key = datetime.now().strftime("%Y-%m-%d")
        today = history.get(today_key) or {}
        rows = self._signin_site_rows()
        return {
            "enabled": bool(getattr(self, "_signin_enabled", False)),
            "notify": bool(getattr(self, "_signin_notify", True)),
            "cron": getattr(self, "_signin_cron", "17 7 * * *"),
            "site_ids": list(getattr(self, "_signin_sites", [])),
            "site_names": [row.get("name") for row in rows],
            "today": today.get("results") or [],
            "last_run_at": today.get("run_at"),
            "last_results": today.get("results") or [],
        }

    def sign_in(self, force: bool = False) -> None:
        """串行执行站点签到；成功站点当天跳过，失败站点下次自动重试。"""
        if not force and not getattr(self, "_signin_enabled", False):
            return
        signin_lock = getattr(self, "_signin_lock", None)
        if signin_lock is None:
            self._signin_lock = threading.Lock()
            signin_lock = self._signin_lock
        if not signin_lock.acquire(blocking=False):
            logger.info("站点自动签到已有任务执行中，本轮跳过")
            return
        try:
            sites = self._signin_site_rows()
            if not sites:
                logger.info("站点自动签到没有可执行的私有站点")
                return
            today_key = datetime.now().strftime("%Y-%m-%d")
            history = self._signin_history()
            day_record = history.get(today_key) or {"run_at": None, "results": []}
            previous = {
                str(item.get("site_id")): item
                for item in day_record.get("results") or []
                if isinstance(item, dict)
            }
            results: List[dict] = []
            for site in sites:
                site_id = int(site.get("id"))
                old = previous.get(str(site_id))
                if old and old.get("success"):
                    results.append({**old, "skipped": True})
                    continue
                success, message = signin_site(site)
                results.append(
                    {
                        "site_id": site_id,
                        "site_name": site.get("name") or str(site_id),
                        "success": bool(success),
                        "message": message,
                        "checked_at": self._now_iso(),
                        "skipped": False,
                    }
                )
            day_record = {"run_at": self._now_iso(), "results": results}
            history[today_key] = day_record
            for key in sorted(history)[:-31]:
                history.pop(key, None)
            self.save_data(self.SIGNIN_DATA_KEY, history)
            logger.info(
                f"站点自动签到完成：成功 "
                f"{sum(1 for item in results if item.get('success'))}/{len(results)}"
            )
            if self._signin_notify:
                message = "\n".join(
                    f"{item.get('site_name')}: {item.get('message')}"
                    for item in results
                )
                self.post_message(
                    mtype=NotificationType.SiteMessage,
                    title="【站点自动签到】",
                    text=message or "没有需要签到的站点",
                )
        except Exception as err:
            logger.error(f"站点自动签到执行失败：{str(err)}")
        finally:
            signin_lock.release()

    def _validate_task_reference(self, task: BrushTaskConfig, notify: bool = True) -> bool:
        """校验任务引用的私有站点和下载器是否仍然存在。"""
        site = SiteOper().get(task.site_id)
        downloader_configs = DownloaderHelper().get_configs()
        valid = bool(
            site
            and not getattr(site, "public", False)
            and task.downloader
            and task.downloader in downloader_configs
        )
        if notify and not valid:
            self._log_and_notify_error(f"刷流任务 [{task.name}] 引用的站点或下载器不存在")
        return valid

    @staticmethod
    def _torrent_has_tag(torrent: Any, tag: str) -> bool:
        """判断 qBittorrent 种子是否仍绑定指定标签。"""
        if not isinstance(torrent, dict):
            return False
        tags = {
            item.strip()
            for item in str(torrent.get("tags") or "").split(",")
            if item.strip()
        }
        return tag in tags

    @staticmethod
    def _delete_qbittorrent_tags(service: Any, tags: Union[str, List[str]]) -> bool:
        """删除 qBittorrent 全局标签定义，不调用需要种子 Hash 的 removeTags。"""
        client = getattr(getattr(service, "instance", None), "qbc", None)
        if not client or not tags:
            return False
        client.torrents_delete_tags(tags=tags)
        return True

    def _cleanup_unused_task_tag(
        self,
        task: BrushTaskConfig,
        torrents: Optional[List[Any]] = None,
    ) -> None:
        """仅删除不再被任何 qBittorrent 种子使用的任务唯一标签"""
        if not task or not task.downloader:
            return
        try:
            helper = DownloaderHelper()
            service = helper.get_service(name=task.downloader)
            if not service or not service.instance or not helper.is_downloader("qbittorrent", service=service):
                return
            if torrents is None:
                torrents, error = service.instance.get_torrents()
                if error:
                    logger.warning(f"清理刷流任务 [{task.name}] 标签时获取下载器种子失败")
                    return
            if any(self._torrent_has_tag(torrent, task.brush_tag) for torrent in torrents or []):
                return
            if self._delete_qbittorrent_tags(service, task.brush_tag):
                logger.info(f"清理刷流任务 [{task.name}] 未使用标签：{task.brush_tag}")
        except Exception as err:
            # 标签清理失败不应影响刷流检查或任务删除主流程。
            logger.warning(f"清理刷流任务 [{task.name}] 标签失败：{str(err)}")

    def _cleanup_unused_task_tags(self) -> None:
        """扫描全部 qBittorrent 下载器，清理历史遗留的刷流唯一标签"""
        try:
            helper = DownloaderHelper()
            downloader_names = set(helper.get_configs().keys())
            for downloader_name in downloader_names:
                service = helper.get_service(name=downloader_name)
                if not service or not service.instance or not helper.is_downloader("qbittorrent", service=service):
                    continue
                client = getattr(service.instance, "qbc", None)
                if not client:
                    continue
                all_tags = [str(tag).strip() for tag in client.torrents_tags() or [] if str(tag).strip()]
                task_tags = [tag for tag in all_tags if tag.startswith("刷流-")]
                if not task_tags:
                    continue
                torrents, error = service.instance.get_torrents()
                if error:
                    logger.warning(f"扫描下载器 [{downloader_name}] 刷流标签时获取种子失败")
                    continue
                used_tags = {
                    tag
                    for torrent in torrents or []
                    for tag in {
                        item.strip()
                        for item in str(torrent.get("tags") or "").split(",")
                        if item.strip()
                    }
                }
                unused_tags = [tag for tag in task_tags if tag not in used_tags]
                if unused_tags and self._delete_qbittorrent_tags(service, unused_tags):
                    logger.info(f"清理下载器 [{downloader_name}] 未使用刷流标签：{','.join(unused_tags)}")
        except Exception as err:
            logger.warning(f"扫描清理历史刷流标签失败：{str(err)}")

    def _migrate_legacy_config(self, config: dict) -> List[dict]:
        """把旧全局配置和站点覆盖 JSON 拆分为一站点一任务"""
        overrides = self._parse_legacy_site_overrides(config)
        tasks: List[dict] = []
        for site_id in config.get("brushsites") or []:
            site = SiteOper().get(site_id)
            if not site or getattr(site, "public", False):
                continue
            migration_fields = set(TASK_CONFIG_FIELDS).union(LEGACY_SITE_OVERRIDE_FIELDS)
            task_data = {field: config.get(field) for field in migration_fields if field in config}
            site_override = overrides.get(site.name, {})
            task_data.update(site_override)
            # 旧版会把全局时区小时数转换成分钟后再次持久化，站点覆盖 JSON 则始终保留小时数。
            if "timezone_offset" not in site_override:
                timezone_offset = BrushTaskConfig._parse_number(config.get("timezone_offset")) or 0
                task_data["timezone_offset"] = float(timezone_offset) / 60
            task_data.update(
                {
                    "id": uuid.uuid4().hex,
                    "name": site.name,
                    "site_id": site.id,
                    "enabled": True,
                    "brush_interval": 10,
                    "check_interval": 5,
                }
            )
            tasks.append(task_data)
        return tasks

    @staticmethod
    def _parse_legacy_site_overrides(config: dict) -> Dict[str, dict]:
        """解析旧版允许注释的站点覆盖 JSON"""
        if not config.get("enable_site_config") or not config.get("site_config"):
            return {}
        try:
            content = re.sub(r"//.*?(?:\n|$)", "", str(config.get("site_config"))).strip()
            rows = json.loads(content)
        except (TypeError, ValueError) as err:
            logger.error(f"解析旧版站点独立配置失败：{str(err)}")
            return {}
        overrides: Dict[str, dict] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or not row.get("sitename"):
                continue
            overrides[str(row["sitename"])] = {
                key: row[key] for key in LEGACY_SITE_OVERRIDE_FIELDS if key in row
            }
        return overrides

    def _migrate_legacy_data(self) -> None:
        """按站点把旧全局种子、归档和未托管记录迁移到任务命名空间"""
        if (self.get_data("task_data_schema_version") or 0) >= self.DATA_SCHEMA_VERSION:
            return
        tasks = list(self._task_configs.values())
        by_site_id = {str(task.site_id): task for task in tasks}
        by_site_name = {
            self._get_site_name(task.site_id): task for task in tasks if self._get_site_name(task.site_id)
        }
        for data_name in ("torrents", "archived", "unmanaged"):
            legacy_rows = self.get_data(data_name) or {}
            buckets: Dict[str, dict] = {task.id: {} for task in tasks}
            for item_id, item in legacy_rows.items() if isinstance(legacy_rows, dict) else []:
                task = by_site_id.get(str(item.get("site"))) or by_site_name.get(item.get("site_name"))
                if not task and len(tasks) == 1:
                    task = tasks[0]
                if not task:
                    continue
                migrated_item = dict(item)
                migrated_item.update({"task_id": task.id, "task_name": task.name})
                buckets[task.id][item_id] = migrated_item
            for task_id, rows in buckets.items():
                current = self._get_task_data(task_id, data_name)
                if not current and rows:
                    self._save_task_data(task_id, data_name, rows)
        for task in tasks:
            self._recalculate_statistics(task.id)
        self.save_data("task_data_schema_version", self.DATA_SCHEMA_VERSION)

    def _migrate_torrent_identity_data(self) -> None:
        """移除任务记录中未参与业务判断的旧 IMDb ID 字段。"""
        for task in self._task_configs.values():
            for data_name in ("torrents", "archived", "unmanaged"):
                rows = self._get_task_data(task.id, data_name)
                if not isinstance(rows, dict):
                    continue
                changed = False
                for item in rows.values():
                    if isinstance(item, dict) and "imdbid" in item:
                        item.pop("imdbid", None)
                        changed = True
                if changed:
                    self._save_task_data(task.id, data_name, rows)

    @staticmethod
    def _get_site_name(site_id: int) -> Optional[str]:
        """按站点 ID 获取名称并兼容已删除站点"""
        site = SiteOper().get(site_id)
        return site.name if site else None

    @contextmanager
    def _task_scope(self, task_id: str) -> Iterator[BrushTaskConfig]:
        """在当前线程中绑定任务上下文，供深层核心逻辑读取"""
        previous = getattr(self._task_context, "task_id", None)
        self._task_context.task_id = task_id
        try:
            task = self._task_configs.get(task_id)
            if not task:
                raise KeyError(f"刷流任务不存在：{task_id}")
            yield task
        finally:
            if previous is None:
                if hasattr(self._task_context, "task_id"):
                    delattr(self._task_context, "task_id")
            else:
                self._task_context.task_id = previous

    def _get_task_config(self, task_id: Optional[str] = None) -> Optional[BrushTaskConfig]:
        """获取显式任务或当前线程绑定的任务配置"""
        resolved_id = task_id or getattr(self._task_context, "task_id", None)
        return self._task_configs.get(resolved_id) if resolved_id else None

    @staticmethod
    def _task_data_key(task_id: str, data_name: str) -> str:
        """生成任务独立的插件数据键"""
        return TaskRepository.task_key(task_id, data_name)

    def _get_task_data(self, task_id: str, data_name: str) -> Any:
        """读取指定任务的独立持久化数据"""
        return self._repository.get(task_id, data_name)

    def _save_task_data(self, task_id: str, data_name: str, value: Any) -> None:
        """保存指定任务的独立持久化数据"""
        self._repository.save(task_id, data_name, value)

    def _current_task_data(self, data_name: str, default: Any = None) -> Any:
        """读取当前线程任务的数据并提供缺省值"""
        task = self._get_task_config()
        if not task:
            return default
        value = self._get_task_data(task.id, data_name)
        return default if value is None else value

    def _save_current_task_data(self, data_name: str, value: Any) -> None:
        """保存当前线程任务的数据"""
        task = self._get_task_config()
        if task:
            self._save_task_data(task.id, data_name, value)

    def _submit_task_operation(self, task_id: str, operation: str) -> schemas.Response:
        """校验运行条件后把手动操作提交到宿主线程池"""
        task = self._task_configs.get(task_id)
        if not task:
            return schemas.Response(success=False, message="刷流任务不存在")
        if not self.get_state() or not task.enabled:
            return schemas.Response(success=False, message="插件或任务未启用")
        if not self._mark_task_queued(task_id, operation):
            return schemas.Response(success=False, message="任务已有操作正在执行")
        target = self.brush if operation == "brush" else self.check
        args = (task_id, False, True) if operation == "force_cleanup" else (task_id,)
        try:
            ThreadHelper().submit(target, *args)
        except Exception as err:
            self._set_runtime(task_id, state="idle", operation=None, last_error=str(err))
            logger.error(f"提交刷流任务 [{task.name}] 失败：{str(err)}")
            return schemas.Response(success=False, message="任务提交失败")
        return schemas.Response(success=True, message="任务已提交", data=self._task_summary(task_id))

    def _is_task_busy(self, task_id: str) -> bool:
        """判断任务是否已经排队或正在执行，保护运行中的配置与数据"""
        task_lock = self._task_locks.get(task_id)
        with self._runtime_lock:
            runtime = self._runtime.get(task_id, {})
            return bool(
                runtime.get("state") in {"queued", "running"}
                or (task_lock and task_lock.locked())
            )

    def _mark_task_queued(self, task_id: str, operation: str) -> bool:
        """以原子方式把空闲任务标记为排队，避免重复提交手动操作"""
        with self._runtime_lock:
            runtime = self._runtime.setdefault(
                task_id,
                {"state": "idle", "operation": None, "last_error": None},
            )
            if runtime.get("state") in {"queued", "running"}:
                return False
            runtime.update({"state": "queued", "operation": operation, "last_error": None})
            if operation == "force_cleanup":
                now = time.time()
                runtime["cleanup_progress"] = {
                    "state": "queued",
                    "phase": "已提交，等待任务锁",
                    "percent": 2,
                    "candidate_count": 0,
                    "selected_count": 0,
                    "deleted_count": 0,
                    "freed_bytes": 0.0,
                    "protected_count": 0,
                    "started_at": now,
                    "updated_at": now,
                }
            return True

    def _set_runtime(self, task_id: str, **updates: Any) -> None:
        """线程安全地更新任务瞬时运行状态"""
        with self._runtime_lock:
            runtime = self._runtime.setdefault(task_id, {"state": "idle", "operation": None, "last_error": None})
            runtime.update(updates)

    def _update_cleanup_progress(self, task_id: str, **updates: Any) -> None:
        """更新手动安全清理的瞬时进度，供前端短轮询展示。"""
        with self._runtime_lock:
            runtime = self._runtime.setdefault(task_id, {"state": "idle", "operation": None, "last_error": None})
            progress = dict(runtime.get("cleanup_progress") or {})
            progress.update(updates)
            progress["updated_at"] = time.time()
            runtime["cleanup_progress"] = progress

    def _append_run(self, task_id: str, report: dict) -> None:
        """保存最近的刷流或检查诊断记录"""
        stored_report = {
            **report,
            "reason_counts": dict(report.get("reason_counts") or {}),
        }
        self._repository.prepend_bounded(task_id, "runs", stored_report, self.MAX_RUN_HISTORY)

    def _build_status_data(self) -> Dict[str, Any]:
        """组装工作台总览、任务摘要和可选站点下载器"""
        site_user_data = (
            self._latest_site_user_data_by_domain()
            if any(task.site_ratio_control for task in self._task_configs.values())
            else {}
        )
        task_rows = [
            self._task_summary(task_id, site_user_data_by_domain=site_user_data)
            for task_id in self._task_configs
        ]
        aggregate = {
            "task_count": len(task_rows),
            "enabled_count": sum(1 for row in task_rows if row.get("enabled")),
            "running_count": sum(
                1 for row in task_rows if row.get("state") in {"running", "brush", "check"}
            ),
            "active_count": sum(row.get("statistic", {}).get("active", 0) for row in task_rows),
            "uploaded": sum(row.get("statistic", {}).get("uploaded", 0) for row in task_rows),
            "downloaded": sum(row.get("statistic", {}).get("downloaded", 0) for row in task_rows),
            "seeding_size": sum(row.get("seeding_size", 0) for row in task_rows),
        }
        site_options = [
            {"title": site.get("name"), "value": site.get("id")}
            for site in SitesHelper().get_indexers()
            if not site.get("public")
        ]
        downloader_options = [
            {"title": item.name, "value": item.name}
            for item in DownloaderHelper().get_configs().values()
        ]
        return {
            "enabled": self.get_state(),
            "show_sidebar_nav": self._show_sidebar_nav,
            "signin": self._build_signin_status(),
            **{field: getattr(self, f"_{field}", None) for field in GLOBAL_LIMIT_FIELDS},
            "summary": aggregate,
            "tasks": task_rows,
            "options": {"sites": site_options, "downloaders": downloader_options},
        }

    def _task_summary(
        self,
        task_id: str,
        site_user_data_by_domain: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """组装单个任务在左侧任务列表和仪表板中的摘要"""
        task = self._task_configs.get(task_id)
        if not task:
            return {}
        statistic = self._get_statistic_info(task_id)
        torrents = self._get_task_data(task_id, "torrents") or {}
        history = self._get_task_data(task_id, "runs") or []
        runtime = dict(self._runtime.get(task_id, {}))
        cleanup_progress = runtime.get("cleanup_progress")
        if (
            cleanup_progress
            and cleanup_progress.get("state") in {"completed", "failed"}
            and float(cleanup_progress.get("display_until") or 0) <= time.time()
        ):
            cleanup_progress = None
        site_ratio = self._build_site_ratio_status(task, site_user_data_by_domain)
        if not self.get_state():
            display_state = "disabled"
        elif not task.enabled:
            display_state = "paused"
        elif runtime.get("state") in {"queued", "running"}:
            display_state = runtime.get("operation") or "running"
        elif site_ratio["enabled"] and not site_ratio["available"]:
            display_state = "ratio_unavailable"
        elif site_ratio["reached"] and task.site_ratio_reached_behavior == "pause":
            display_state = "waiting_ratio"
        elif not self._is_current_time_in_range(task):
            display_state = "waiting"
        elif runtime.get("last_error"):
            display_state = "error"
        else:
            display_state = "running"
        return {
            "id": task.id,
            "name": task.name,
            "enabled": task.enabled,
            "site_id": task.site_id,
            "site_name": self._get_site_name(task.site_id) or "站点已删除",
            "downloader": task.downloader,
            "brush_interval": task.brush_interval,
            "check_interval": task.check_interval,
            "cron": task.cron,
            "active_time_range": task.active_time_range,
            "state": display_state,
            "operation": runtime.get("operation"),
            "last_error": runtime.get("last_error"),
            "cleanup_progress": cleanup_progress,
            "next_run_at": self._next_run_at(task, history),
            "last_run": history[0] if history else None,
            "statistic": statistic,
            "seeding_size": self.__calculate_seeding_torrents_size(torrents),
            "site_ratio": site_ratio,
            "strategy": self._build_strategy_status(task_id),
        }

    @staticmethod
    def _latest_site_user_data_by_domain() -> Dict[str, Any]:
        """按标准化域名索引各站点最新一条有效用户统计。"""
        result: Dict[str, Any] = {}
        for row in SiteOper().get_userdata_latest() or []:
            domain = StringUtils.get_url_domain(getattr(row, "domain", None))
            if domain and domain not in result:
                result[domain] = row
        return result

    def _build_site_ratio_status(
        self,
        task: BrushTaskConfig,
        site_user_data_by_domain: Optional[Dict[str, Any]] = None,
        site: Any = None,
    ) -> Dict[str, Any]:
        """组装任务绑定站点的当前分享率、目标值和控制状态。"""
        status = {
            "enabled": bool(task.site_ratio_control),
            "target": task.site_ratio_target,
            "current": None,
            "gap": None,
            "progress": None,
            "available": False,
            "unlimited": False,
            "reached": False,
            "updated_at": None,
        }
        if not task.site_ratio_control or not task.site_ratio_target:
            return status
        site = site or SiteOper().get(task.site_id)
        if not site:
            return status
        if site_user_data_by_domain is None:
            site_user_data_by_domain = self._latest_site_user_data_by_domain()
        domain = StringUtils.get_url_domain(getattr(site, "domain", None))
        user_data = site_user_data_by_domain.get(domain)
        if not user_data:
            return status
        ratio = BrushTaskConfig._parse_number(getattr(user_data, "ratio", None))
        if ratio is None:
            return status
        upload = BrushTaskConfig._parse_number(getattr(user_data, "upload", None)) or 0
        download = BrushTaskConfig._parse_number(getattr(user_data, "download", None)) or 0
        unlimited = float(ratio) == 0 and float(upload) > 0 and float(download) <= 0
        updated_day = getattr(user_data, "updated_day", None)
        updated_time = getattr(user_data, "updated_time", None)
        status.update(
            {
                "current": None if unlimited else float(ratio),
                "available": True,
                "unlimited": unlimited,
                "reached": unlimited or float(ratio) >= float(task.site_ratio_target),
                "updated_at": " ".join(value for value in (updated_day, updated_time) if value) or None,
            }
        )
        if not unlimited:
            status["gap"] = max(float(task.site_ratio_target) - float(ratio), 0.0)
            status["progress"] = min(float(ratio) / float(task.site_ratio_target), 1.0)
        else:
            status["gap"] = 0.0
            status["progress"] = 1.0
        return status

    def _evaluate_site_ratio_control(
        self,
        task: BrushTaskConfig,
        site: Any = None,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """判断站点分享率是否允许当前任务继续新增种子。"""
        status = self._build_site_ratio_status(task, site=site)
        if not status["enabled"]:
            return True, None, status
        if not status["available"]:
            return False, "暂无站点分享率统计，等待数据更新", status
        if status["reached"] and task.site_ratio_reached_behavior == "pause":
            current = "无限" if status["unlimited"] else f"{status['current']:.2f}"
            return (
                False,
                f"站点分享率 {current}，已达到目标 {float(status['target']):.2f}",
                status,
            )
        if status["reached"]:
            return True, "目标已达成，按普通均衡门槛继续运行", status
        return True, None, status

    def _build_task_overview(self, task_id: str) -> Dict[str, Any]:
        """组装任务状态页所需的轻量数据，不夹带种子和运行记录。"""
        task = self._task_configs[task_id]
        return {
            "task": self._serialize_task_document(task_id),
            "runtime_config": task.to_dict(),
            "summary": self._task_summary(task_id),
            "strategy": self._build_strategy_status(task_id),
        }

    def _paginate_task_torrents(
        self,
        task_id: str,
        state: str = "active",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按任务和状态分页读取托管种子。"""
        torrents = self._get_task_data(task_id, "torrents") or {}
        archived = self._get_task_data(task_id, "archived") or {}
        rows = list(torrents.values())
        if state == "active":
            rows = [row for row in rows if not row.get("deleted")]
        elif state == "deleted":
            rows = [row for row in rows if row.get("deleted")] + list(archived.values())
        else:
            rows.extend(archived.values())
        rows.sort(key=lambda item: item.get("time") or 0, reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        selected_rows = rows[start : start + page_size]
        return {
            "items": selected_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "state": state,
        }

    def _build_strategy_status(self, task_id: str) -> Dict[str, Any]:
        """组装策略概览、学习置信度和最近选删种解释。"""
        task = self._task_configs[task_id]
        document = self._task_documents.get(task_id)
        now = time.time()
        state = dict(self._get_task_data(task_id, "strategy_state") or {})
        learning_state = self._get_task_data(task_id, "learning_state") or {}
        learning = learning_summary(learning_state)
        candidates = self._get_task_data(task_id, "smart_candidates") or {}
        if not isinstance(candidates, dict):
            candidates = {}
        audit = self._get_task_data(task_id, "decision_audit") or []
        if not isinstance(audit, list):
            audit = []
        latest_selection = next((row for row in reversed(audit) if row.get("kind") == "selection"), None)
        latest_deletion = next((row for row in reversed(audit) if row.get("kind") == "deletion"), None)
        torrents = self._get_task_data(task_id, "torrents") or {}
        current_size = self.__calculate_seeding_torrents_size(torrents)
        download_health = self._build_download_health_summary(torrents)
        uploaded_24h = 0.0
        snapshots = learning_state.get("snapshots", []) if isinstance(learning_state, dict) else []
        previous_by_hash: Dict[str, dict] = {}
        for row in snapshots:
            if float(row.get("at") or 0) > now - 24 * 3600:
                continue
            torrent_hash = str(row.get("hash") or "")
            if torrent_hash and float(row.get("at") or 0) > float(
                previous_by_hash.get(torrent_hash, {}).get("at") or 0
            ):
                previous_by_hash[torrent_hash] = row
        for torrent_hash, torrent in torrents.items():
            if torrent.get("deleted"):
                continue
            previous = previous_by_hash.get(str(torrent_hash))
            if previous:
                uploaded_24h += max(
                    float(torrent.get("uploaded") or 0) - float(previous.get("uploaded") or 0),
                    0.0,
                )
        deleted_rows = self._get_task_data(task_id, "smart_deletions") or []
        actual_freed_24h = sum(
            float(row.get("size") or 0)
            for row in deleted_rows
            if now - float(row.get("at") or 0) <= 24 * 3600
        )
        capacity = float(task.disksize or 0) * 1024**3
        capacity_target = capacity * task.smart_capacity_target_percent / 100 if capacity else None
        capacity_ratio = current_size / capacity if capacity else 0.0
        recovery_active = bool(capacity and capacity_ratio > 1.0)
        torrent_sizes = {
            str(torrent_hash): float(
                torrent.get("size") or torrent.get("total_size") or 0
            )
            for torrent_hash, torrent in torrents.items()
            if not torrent.get("deleted")
        }
        blocker_counts: Dict[str, int] = {}
        blocker_bytes: Dict[str, float] = {}
        protected_hashes: set[str] = set()
        protected_bytes_by_hash: Dict[str, float] = {}
        eligible_count = 0
        eligible_bytes = 0.0
        for row in (latest_deletion or {}).get("evaluated", []):
            torrent_hash = str(row.get("hash") or "")
            torrent_size = float(row.get("size") or torrent_sizes.get(torrent_hash) or 0)
            if row.get("action") == "candidate":
                eligible_count += 1
                eligible_bytes += torrent_size
                continue
            if torrent_hash:
                protected_hashes.add(torrent_hash)
                protected_bytes_by_hash[torrent_hash] = torrent_size
            for code in row.get("reasons") or []:
                blocker_counts[code] = blocker_counts.get(code, 0) + 1
                blocker_bytes[code] = blocker_bytes.get(code, 0.0) + torrent_size
        deletion_blockers = [
            {
                "code": code,
                "label": self._smart_reason_label(code),
                "count": count,
                "bytes": blocker_bytes.get(code, 0.0),
            }
            for code, count in sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        shadow_remaining = max(float(task.smart_shadow_until or 0) - now, 0.0)
        if not task.smart_enabled:
            mode, mode_label = "disabled", "智能删种未启用"
        elif task.smart_delete_paused:
            mode, mode_label = "paused", "自动删除已暂停"
        elif shadow_remaining > 0:
            mode, mode_label = "shadow", "影子观察中"
        else:
            mode, mode_label = "active", "自动删除已启用"
        candidate_rows = sorted(
            candidates.values(),
            key=lambda row: float(row.get("planned_at") or 0),
            reverse=True,
        )
        false_positive_count = sum(1 for row in candidate_rows if row.get("recovered"))
        deletion_reason_codes = list((latest_deletion or {}).get("reason_codes") or [])
        planned_count = len((latest_deletion or {}).get("selected") or [])
        planned_bytes = float((latest_deletion or {}).get("estimated_freed_bytes") or 0)
        if not task.smart_enabled:
            readiness = {
                "state": "disabled",
                "message": "自动删种未启用，当前只做选种、下载健康检查和统计。",
            }
        elif not capacity:
            readiness = {
                "state": "capacity_unset",
                "message": "未设置任务容量，智能删种不会因空间压力自动清理。",
            }
        elif current_size <= (capacity_target or current_size):
            readiness = {
                "state": "at_target",
                "message": "容量已在目标范围内，当前无需删种。",
            }
        elif planned_count:
            if mode == "shadow":
                plan_outcome = "影子期仅观察，不会实际删除。"
            elif mode == "paused":
                plan_outcome = "自动删除已暂停。"
            else:
                plan_outcome = "将按硬安全线复核后执行。"
            readiness = {
                "state": "shadow" if mode == "shadow" else "paused" if mode == "paused" else "planned",
                "message": (
                    f"已找到 {planned_count} 个低价值候选，预计释放 {self.__bytes_to_gb(planned_bytes):.1f} GB；"
                    f"{plan_outcome}"
                ),
                "candidate_count": planned_count,
                "candidate_bytes": planned_bytes,
            }
        elif eligible_count and any(
            code in deletion_reason_codes
            for code in ("byte_cap", "daily_count_cap", "run_count_cap")
        ):
            quota_message = deletion_quota_message(deletion_reason_codes)
            readiness = {
                "state": "quota",
                "message": f"已有低价值候选，但{quota_message}；策略会在额度恢复后继续处理。",
                "candidate_count": eligible_count,
                "candidate_bytes": eligible_bytes,
            }
        elif eligible_count:
            readiness = {
                "state": "waiting",
                "message": "已有低价值候选，正在等待下一次连续确认或容量额度。",
                "candidate_count": eligible_count,
                "candidate_bytes": eligible_bytes,
            }
        else:
            main_blocker = deletion_blockers[0]["label"] if deletion_blockers else "安全线和连续确认"
            readiness = {
                "state": "blocked",
                "message": f"暂时没有可安全删除的种子，主要受“{main_blocker}”保护。",
            }
        protected_count = len(protected_hashes)
        protected_bytes = sum(protected_bytes_by_hash.values())
        runs = self._get_task_data(task_id, "runs") or []
        latest_brush = next((row for row in runs if row.get("kind") == "brush"), {})
        selection_summary = {
            "candidate_count": int(latest_brush.get("source_count") or 0),
            "added_count": int(latest_brush.get("added_count") or 0),
            "filtered_count": int(latest_brush.get("filtered_count") or 0),
            "main_reason": next(
                iter(
                    sorted(
                        (latest_brush.get("reason_counts") or {}).items(),
                        key=lambda item: (-int(item[1] or 0), str(item[0])),
                    )
                ),
                (None, 0),
            )[0],
        }
        capacity_percent = round(capacity_ratio * 100, 1) if capacity else None
        presentation = build_health_summary(
            runtime_error=self._runtime.get(task_id, {}).get("last_error"),
            configuration_issue=bool(
                document
                and not document.deletion.enabled
                and document.deletion.paused
                and (
                    document.capacity.limit_gb is None
                    or document.deletion.min_seed_hours is None
                )
            ),
            severe_capacity=bool(
                capacity
                and capacity_ratio > 1.0
            ),
            capacity_percent=capacity_percent,
            download=download_health,
            mode=mode,
            shadow_remaining_seconds=shadow_remaining,
            capacity_pressure=bool(capacity and current_size > (capacity_target or current_size)),
            readiness_message=str(readiness.get("message") or "容量高于目标，等待安全候选。"),
            task_enabled=task.enabled,
        )
        health = presentation["health"]
        recommended_actions = presentation["recommended_actions"]
        download_issue_count = presentation["download_issue_count"]
        download_issues = [
            {
                "hash": str(torrent_hash),
                "title": row.get("title") or str(torrent_hash),
                "size": float(row.get("size") or row.get("total_size") or 0),
                "state": row.get("download_health") or HEALTH_UNKNOWN,
                "label": row.get("download_health_label") or health_label(row.get("download_health")),
                "reason": row.get("download_health_reason"),
            }
            for torrent_hash, row in torrents.items()
            if not row.get("deleted")
            and row.get("download_health") in {HEALTH_STALLED, HEALTH_SLOW, HEALTH_QUEUED, HEALTH_ERROR, HEALTH_PAUSED}
        ][:50]
        ui_summary = {
            "health": health,
            "capacity": {
                "current_bytes": current_size,
                "limit_bytes": capacity,
                "percent": capacity_percent,
                "trigger_bytes": capacity * task.smart_capacity_trigger_percent / 100 if capacity else None,
                "target_bytes": capacity_target,
                "recovery_active": recovery_active,
            },
            "selection": selection_summary,
            "deletion": {
                "state": readiness.get("state"),
                "candidate_count": int(readiness.get("candidate_count") or planned_count or eligible_count),
                "candidate_bytes": float(readiness.get("candidate_bytes") or planned_bytes or eligible_bytes),
                "protected_count": protected_count,
                "protected_bytes": protected_bytes,
                "message": readiness.get("message"),
            },
            "download": {
                "state": "attention" if download_issue_count else "healthy",
                "stalled_count": int(download_health.get("stalled_count") or 0),
                "slow_count": int(download_health.get("slow_count") or 0),
                "queued_count": int(download_health.get("queued_count") or 0),
                "error_count": int(download_health.get("error_count") or 0),
                "paused_count": int(download_health.get("paused_count") or 0),
                "issues": download_issues,
            },
            "recommended_actions": recommended_actions,
        }
        state.update(
            {
                "engine_version": __version__,
                "profile": task.smart_profile,
                "mode": mode,
                "mode_label": mode_label,
                "shadow_until": task.smart_shadow_until,
                "shadow_remaining_seconds": shadow_remaining,
                "learning_confidence": learning["confidence"],
                "learning_sample_count": learning["sample_count"],
                "learning": learning,
                "candidate_count": len(candidate_rows),
                "false_positive_count": false_positive_count,
                "false_positive_rate": round(false_positive_count / len(candidate_rows), 4) if candidate_rows else 0.0,
                "capacity_bytes": capacity,
                "current_size_bytes": current_size,
                "capacity_trigger_bytes": capacity * task.smart_capacity_trigger_percent / 100 if capacity else None,
                "capacity_target_bytes": capacity_target,
                "capacity_debt_bytes": max(current_size - (capacity_target or current_size), 0.0),
                "capacity_ratio": round(capacity_ratio, 4),
                "capacity_trigger_percent": task.smart_capacity_trigger_percent,
                "capacity_target_percent": task.smart_capacity_target_percent,
                "recovery_active": recovery_active,
                "estimated_freed_bytes": (latest_deletion or {}).get("estimated_freed_bytes", 0),
                "deletion_readiness": readiness,
                "eligible_candidate_count": eligible_count,
                "eligible_candidate_bytes": eligible_bytes,
                "uploaded_gb_per_day": round(uploaded_24h / 1024**3, 3),
                "unit_capacity_yield_per_day": round(uploaded_24h / current_size, 6) if current_size else 0.0,
                "actual_freed_bytes_24h": actual_freed_24h,
                "download_health": download_health,
                "selection_explanations": (latest_selection or {}).get("decisions", []),
                "deletion_explanations": (latest_deletion or {}).get("selected", []),
                "deletion_blockers": deletion_blockers,
                "deletion_reason_codes": deletion_reason_codes,
                "pending_candidates": candidate_rows[:50],
                "audit_count": len(audit),
                "ui_summary": ui_summary,
            }
        )
        return state

    @staticmethod
    def _next_run_at(task: BrushTaskConfig, history: List[dict]) -> Optional[str]:
        """按 CRON 或固定间隔估算任务下一次刷新时间"""
        now = datetime.now().astimezone()
        try:
            if task.cron:
                next_time = CronTrigger.from_crontab(task.cron, timezone=settings.TZ).get_next_fire_time(None, now)
            else:
                last_brush = next((item for item in history if item.get("kind") == "brush"), None)
                if last_brush and last_brush.get("started_at"):
                    base = datetime.fromisoformat(last_brush["started_at"])
                    next_time = max(base + timedelta(minutes=task.brush_interval), now)
                else:
                    next_time = now + timedelta(minutes=task.brush_interval)
            return next_time.isoformat(timespec="minutes") if next_time else None
        except (TypeError, ValueError):
            return None

    def brush(self, task_id: Optional[str] = None) -> None:
        """执行单个任务的站点刷新、选种和下载流程"""
        task = self._get_task_config(task_id)
        if not task or not self.get_state() or not task.enabled:
            return
        task_lock = self._task_locks.setdefault(task.id, threading.Lock())
        if not task_lock.acquire(blocking=False):
            logger.info(f"刷流任务 [{task.name}] 已有操作执行中，本轮跳过")
            return
        report = self._new_run_report("brush")
        self._set_runtime(task.id, state="running", operation="brush", last_error=None)
        try:
            with self._brush_lock, self._task_scope(task.id):
                self._run_brush(task, report)
            report["success"] = report.get("result") not in {"downloader_unavailable", "site_missing"}
        except Exception as err:
            report.update({"success": False, "error": str(err)})
            self._set_runtime(task.id, last_error=str(err))
            logger.error(f"刷流任务 [{task.name}] 执行失败：{str(err)}")
        finally:
            report["finished_at"] = self._now_iso()
            self._append_run(task.id, report)
            self._set_runtime(task.id, state="idle", operation=None)
            task_lock.release()
            if report.get("added_count"):
                self._refresh_scheduler()

    def _run_brush(self, task: BrushTaskConfig, report: dict) -> None:
        """在已绑定任务上下文中执行刷流核心流程"""
        if not self._validate_task_reference(task) or not self.downloader:
            report["result"] = "downloader_unavailable"
            return
        if not self._is_current_time_in_range(task):
            report["result"] = "outside_active_time"
            report["reason_counts"]["不在开启时间段"] = 1
            return
        site = SiteOper().get(task.site_id)
        if not site:
            report["result"] = "site_missing"
            return
        ratio_passed, ratio_reason, ratio_status = self._evaluate_site_ratio_control(task, site=site)
        if ratio_status["enabled"]:
            report["site_ratio"] = ratio_status
        if not ratio_passed:
            report["result"] = "site_ratio_blocked"
            report["reason_counts"][ratio_reason] = 1
            return
        torrent_tasks: Dict[str, dict] = self._current_task_data("torrents", {})
        seeding_size = self.__calculate_seeding_torrents_size(torrent_tasks)
        global_seeding_size = self._calculate_global_seeding_size(task.id, torrent_tasks)
        passed, reason = self.__evaluate_size_condition_for_brush(
            seeding_size,
            global_torrents_size=global_seeding_size,
        )
        if not passed:
            report["result"] = "precondition_blocked"
            report["reason_counts"][reason] = 1
            return
        passed, reason = self.__evaluate_pre_conditions_for_brush()
        if not passed:
            report["result"] = "precondition_blocked"
            report["reason_counts"][reason] = 1
            return
        all_torrent_tasks = self._load_all_torrent_tasks()
        subscribe_titles = self.__get_subscribe_titles()
        self.__brush_site_torrents(
            site=site,
            torrent_tasks=torrent_tasks,
            all_torrent_tasks=all_torrent_tasks,
            subscribe_titles=subscribe_titles,
            report=report,
            global_seeding_size=global_seeding_size,
            ratio_status=ratio_status,
        )
        self._save_current_task_data("torrents", torrent_tasks)
        self._recalculate_statistics(task.id)

    def _load_all_torrent_tasks(self) -> Dict[str, dict]:
        """聚合所有任务的当前记录以保持跨站点重复种子保护"""
        rows: Dict[str, dict] = {}
        for task_id in self._task_configs:
            task_rows = self._get_task_data(task_id, "torrents") or {}
            rows.update(task_rows)
        return rows

    def _calculate_global_seeding_size(
        self,
        current_task_id: Optional[str] = None,
        current_torrent_tasks: Optional[Dict[str, dict]] = None,
    ) -> float:
        """汇总所有任务未删除种子的体积，并允许使用当前任务的内存快照。"""
        total_size = 0.0
        for task_id in self._task_configs:
            if task_id == current_task_id and current_torrent_tasks is not None:
                task_rows = current_torrent_tasks
            else:
                task_rows = self._get_task_data(task_id, "torrents") or {}
            total_size += self.__calculate_seeding_torrents_size(task_rows)
        return total_size

    def __brush_site_torrents(
        self,
        site: Any,
        torrent_tasks: Dict[str, dict],
        all_torrent_tasks: Dict[str, dict],
        subscribe_titles: Set[str],
        report: dict,
        global_seeding_size: float,
        ratio_status: Optional[Dict[str, Any]] = None,
    ) -> None:
        """获取当前任务站点候选并逐项执行保留的选种规则"""
        task = self._get_task_config()
        logger.info(f"刷流任务 [{task.name}] 开始获取站点 {site.name} 的新种子")
        torrents = TorrentsChain().rss(domain=site.domain) if task.rss_support else TorrentsChain().browse(domain=site.domain)
        if not torrents:
            report["result"] = "no_candidates"
            return
        report["source_count"] = len(torrents)
        if task.except_subscribe:
            before_count = len(torrents)
            torrents = self.__filter_torrents_contains_subscribe(torrents, subscribe_titles)
            report["subscription_excluded"] = before_count - len(torrents)
            if report["subscription_excluded"]:
                report["reason_counts"]["命中订阅内容"] = report["subscription_excluded"]
        report["candidate_count"] = len(torrents)

        # 先过滤现有任务、跨站未完成、促销、H&R、包含/排除规则等硬条件，
        # 再做智能评分。旧顺序是先取评分前 N 名再过滤，容易让前 N 名
        # 恰好都是重复种子，导致没有候选补位。
        eligible_torrents = []
        for torrent in torrents:
            passed, reason = self.__evaluate_conditions_for_brush(torrent, all_torrent_tasks)
            if not passed:
                report["reason_counts"][reason] += 1
                continue
            eligible_torrents.append(torrent)
        report["eligible_count"] = len(eligible_torrents)
        torrents = eligible_torrents

        selection_limit = None
        if task.smart_selection_enabled or task.smart_enabled:
            ratio_current = (ratio_status or {}).get("current")
            ratio_target = (ratio_status or {}).get("target") or task.site_ratio_target or 2.0
            capacity_limit = float(task.disksize or 0) * 1024**3
            task_size = self.__calculate_seeding_torrents_size(torrent_tasks)
            occupancy_ratio = task_size / capacity_limit if capacity_limit > 0 else 0.0
            selection_limit, selection_min_score, capacity_tier = capacity_selection_policy(
                task.smart_profile,
                occupancy_ratio,
                int(task.smart_selection_max_add_per_run or 5),
                float(task.smart_selection_min_score or 30),
            )
            ratio_gap = 0.0
            if task.smart_adaptive_enabled and ratio_status and ratio_status.get("available"):
                selection_limit, selection_min_score, ratio_gap = adaptive_selection_policy(
                    selection_limit,
                    selection_min_score,
                    ratio_current,
                    ratio_target,
                )
            learning_state = self._get_task_data(task.id, "learning_state") or {}
            learned_by_candidate: Dict[str, dict] = {}
            learned_median = 0.0
            for candidate in torrents:
                candidate_key = str(
                    getattr(candidate, "enclosure", "")
                    or getattr(candidate, "page_url", "")
                    or getattr(candidate, "title", "")
                    or (candidate.get("title") if isinstance(candidate, dict) else "")
                )
                learned = predict_yield(learning_state, candidate)
                learned_by_candidate[candidate_key] = learned
                learned_median = float(learned.get("median") or learned_median)
            learning_info = learning_summary(learning_state)
            report["smart_selection_policy"] = {
                "current_ratio": ratio_current,
                "target_ratio": ratio_target,
                "gap": ratio_gap,
                "max_add": selection_limit,
                "min_score": selection_min_score,
                "adaptive": bool(task.smart_adaptive_enabled),
                "profile": task.smart_profile,
                "capacity_tier": capacity_tier,
                "occupancy_percent": round(occupancy_ratio * 100, 2),
                "learning_confidence": learning_info["confidence"],
                "learning_samples": learning_info["sample_count"],
            }
            report["smart_selection_input_count"] = len(torrents)
            ranked_candidates = rank_selection_candidates(
                torrents,
                min_score=selection_min_score,
                # 评分阶段保留完整候选池，下载阶段再按上限停止，
                # 这样前面的候选被动态条件拦截时可以继续补位。
                max_count=max(selection_limit, len(torrents), 1),
                share_ratio_gap=ratio_gap,
                share_ratio_target=ratio_target,
                occupancy_ratio=occupancy_ratio,
                profile=task.smart_profile,
                learning=learned_by_candidate,
                learning_confidence=learning_info["confidence"],
                learned_median_yield=learned_median,
            )
            report["smart_selection_count"] = len(ranked_candidates)
            if torrents and not ranked_candidates:
                report["reason_counts"]["低于智能评分阈值"] += len(torrents)
            report["smart_selection_scores"] = [
                {
                    "title": getattr(item.candidate, "title", None)
                    or (item.candidate.get("title") if isinstance(item.candidate, dict) else ""),
                    "score": item.decision.score,
                    "reasons": list(item.decision.reason_codes),
                }
                for item in ranked_candidates
            ]
            selected_keys = {id(item.candidate) for item in ranked_candidates}
            report["smart_selection_explanations"] = []
            for candidate in torrents:
                candidate_key = str(
                    getattr(candidate, "enclosure", "")
                    or getattr(candidate, "page_url", "")
                    or getattr(candidate, "title", "")
                    or (candidate.get("title") if isinstance(candidate, dict) else "")
                )
                learned = learned_by_candidate.get(candidate_key) or {}
                decision = candidate_score(
                    candidate,
                    occupancy_ratio=occupancy_ratio,
                    profile=task.smart_profile,
                    normal_threshold=selection_min_score,
                    learned_yield_score=learned.get("score"),
                    learned_expected_yield=learned.get("expected"),
                    learned_median_yield=learned_median,
                    learning_confidence=learning_info["confidence"],
                )
                accepted = id(candidate) in selected_keys and decision.score >= selection_min_score
                reasons = list(decision.reason_codes)
                if decision.score < selection_min_score:
                    reasons.append("below_selection_threshold")
                report["smart_selection_explanations"].append(
                    {
                        "title": getattr(candidate, "title", "") or candidate_key,
                        "selected": accepted,
                        "score": decision.score,
                        "reasons": reasons,
                        "contributions": dict(decision.contributions),
                        "confidence": decision.confidence,
                    }
                )
            self._append_decision_audit(
                task.id,
                {
                    "at": time.time(),
                    "kind": "selection",
                    "policy": dict(report["smart_selection_policy"]),
                    "decisions": report["smart_selection_explanations"][:50],
                },
            )
            torrents = [item.candidate for item in ranked_candidates]
        else:
            torrents.sort(key=lambda item: item.pubdate or "", reverse=True)
        seeding_size = self.__calculate_seeding_torrents_size(torrent_tasks)
        for torrent in torrents:
            passed, reason = self.__evaluate_pre_conditions_for_brush(include_network_conditions=False)
            if not passed:
                report["reason_counts"][reason] += 1
                report["result"] = "precondition_blocked"
                break
            passed, reason = self.__evaluate_size_condition_for_brush(
                seeding_size,
                torrent.size,
                global_torrents_size=global_seeding_size,
            )
            if not passed:
                report["reason_counts"][reason] += 1
                continue
            passed, reason = self.__evaluate_conditions_for_brush(torrent, all_torrent_tasks)
            if not passed:
                report["reason_counts"][reason] += 1
                continue
            hash_string = self.__download(torrent)
            if not hash_string:
                report["reason_counts"]["下载器添加失败"] += 1
                continue
            torrent_task = self._torrent_to_task_record(torrent, site, task)
            torrent_tasks[hash_string] = torrent_task
            all_torrent_tasks[hash_string] = torrent_task
            seeding_size += torrent.size
            global_seeding_size += torrent.size
            report["added_count"] += 1
            report["added_titles"].append(torrent.title)
            self.eventmanager.send_event(
                etype=EventType.PluginTriggered,
                data={
                    "plugin_id": self.__class__.__name__,
                    "event_name": "brushflow_download_added",
                    "hash": hash_string,
                    "data": torrent_task,
                    "downloader": self.service_info.name,
                },
            )
            logger.info(f"刷流任务 [{task.name}] 新增种子：{torrent.title}|{torrent.description}")
            self.__send_add_message(torrent)
            if selection_limit is not None and report["added_count"] >= selection_limit:
                break
        report["filtered_count"] = max(report["candidate_count"] - report["added_count"], 0)
        report["result"] = "completed"

    @staticmethod
    def _torrent_to_task_record(torrent: TorrentInfo, site: Any, task: BrushTaskConfig) -> dict:
        """把站点候选种子转换为可持久化的任务记录"""
        return {
            "task_id": task.id,
            "task_name": task.name,
            "site": site.id,
            "site_name": site.name,
            "title": torrent.title,
            "size": torrent.size,
            "pubdate": torrent.pubdate,
            "description": torrent.description,
            "page_url": torrent.page_url,
            "date_elapsed": torrent.date_elapsed,
            "freedate": torrent.freedate,
            "uploadvolumefactor": torrent.uploadvolumefactor,
            "downloadvolumefactor": torrent.downloadvolumefactor,
            "join_seeders": getattr(torrent, "seeders", None),
            "join_leechers": getattr(torrent, "leechers", None),
            "hit_and_run": torrent.hit_and_run or task.site_hr_active,
            "volume_factor": torrent.volume_factor,
            "freedate_diff": torrent.freedate_diff,
            "ratio": 0,
            "downloaded": 0,
            "uploaded": 0,
            "seeding_time": 0,
            "deleted": False,
            "time": time.time(),
        }

    @staticmethod
    def _new_run_report(kind: str) -> dict:
        """创建一条结构稳定的运行诊断记录"""
        return {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "started_at": BrushFlow._now_iso(),
            "finished_at": None,
            "success": None,
            "result": None,
            "error": None,
            "source_count": 0,
            "subscription_excluded": 0,
            "candidate_count": 0,
            "eligible_count": 0,
            "filtered_count": 0,
            "added_count": 0,
            "deleted_count": 0,
            "active_count": 0,
            "reason_counts": Counter(),
            "added_titles": [],
            "smart_selection_policy": None,
            "smart_selection_input_count": 0,
            "smart_selection_count": 0,
        }

    @staticmethod
    def _now_iso() -> str:
        """返回带本地时区且精确到秒的时间文本"""
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def __evaluate_size_condition_for_brush(
        self,
        torrents_size: float,
        add_torrent_size: float = 0.0,
        global_torrents_size: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """校验当前任务及所有任务新增种子后是否超过保种体积。"""
        task = self._get_task_config()
        if not task:
            return False, "任务配置不存在"
        estimated_size = torrents_size + (add_torrent_size or 0)
        if task.disksize:
            limit_size = float(task.disksize) * 1024 ** 3
            if estimated_size > limit_size:
                reason = (
                    f"预计做种体积 {self.__bytes_to_gb(estimated_size):.1f} GB，"
                    f"超过任务保种上限 {task.disksize} GB"
                )
                return False, reason
        global_disksize = getattr(self, "_global_disksize", None)
        if global_disksize:
            if global_torrents_size is None:
                global_torrents_size = self._calculate_global_seeding_size()
            estimated_global_size = global_torrents_size + (add_torrent_size or 0)
            if estimated_global_size > float(global_disksize) * 1024 ** 3:
                reason = (
                    f"预计全局做种体积 {self.__bytes_to_gb(estimated_global_size):.1f} GB，"
                    f"超过全局保种上限 {global_disksize} GB"
                )
                return False, reason
        return True, None

    def __evaluate_pre_conditions_for_brush(
        self,
        include_network_conditions: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """校验单任务与全局下载并发及上传下载带宽。"""
        task = self._get_task_config()
        if not task:
            return False, "任务配置不存在"
        global_maxdlcount = getattr(self, "_global_maxdlcount", None)
        if global_maxdlcount and self.__get_global_downloading_count() >= int(global_maxdlcount):
            return False, f"全局同时下载任务数达到上限 {global_maxdlcount}"
        if task.maxdlcount and self.__get_downloading_count() >= int(task.maxdlcount):
            return False, f"同时下载任务数达到上限 {task.maxdlcount}"
        if not include_network_conditions:
            return True, None
        avg_upload_speed, avg_download_speed = self.__get_average_bandwidth()
        if avg_upload_speed is None or avg_download_speed is None:
            return True, None
        global_maxupspeed = getattr(self, "_global_maxupspeed", None)
        global_maxdlspeed = getattr(self, "_global_maxdlspeed", None)
        if global_maxupspeed and avg_upload_speed >= float(global_maxupspeed) * 1024:
            return False, f"全局总上传带宽达到上限 {global_maxupspeed} KB/s"
        if global_maxdlspeed and avg_download_speed >= float(global_maxdlspeed) * 1024:
            return False, f"全局总下载带宽达到上限 {global_maxdlspeed} KB/s"
        if task.maxupspeed and avg_upload_speed >= float(task.maxupspeed) * 1024:
            return False, f"总上传带宽达到上限 {task.maxupspeed} KB/s"
        if task.maxdlspeed and avg_download_speed >= float(task.maxdlspeed) * 1024:
            return False, f"总下载带宽达到上限 {task.maxdlspeed} KB/s"
        return True, None

    def __evaluate_conditions_for_brush(
        self,
        torrent: TorrentInfo,
        torrent_tasks: Dict[str, dict],
    ) -> Tuple[bool, Optional[str]]:
        """按原有促销、H&R、规则、体积、人数和发布时间筛选候选"""
        task = self._get_task_config()
        if not task:
            return False, "任务配置不存在"
        task_key = f"{torrent.site_name}{torrent.title}"
        if any(task_key == f"{item.get('site_name')}{item.get('title')}" for item in torrent_tasks.values()):
            return False, "重复种子"
        if torrent.page_url:
            page_key = f"{torrent.site_name}{torrent.page_url}"
            if any(page_key == f"{item.get('site_name')}{item.get('page_url')}" for item in torrent_tasks.values()):
                return False, "重复种子"
        if torrent.title and any(
            torrent.site_name != item.get("site_name")
            and torrent.title == item.get("title")
            and not item.get("deleted")
            and (item.get("downloaded") or 0) < (item.get("size") or 0)
            for item in torrent_tasks.values()
        ):
            return False, "其他站点存在尚未下载完成的相同种子"
        if task.freeleech and torrent.downloadvolumefactor != 0:
            return False, "非免费种子"
        if task.freeleech == "2xfree" and torrent.uploadvolumefactor != 2:
            return False, "非双倍上传种子"
        if task.hr == "yes" and torrent.hit_and_run:
            return False, "存在 H&R"
        if task.include:
            include_match = bool(
                (torrent.title and re.search(task.include, torrent.title, re.I))
                or (torrent.description and re.search(task.include, torrent.description, re.I))
            )
            if not include_match:
                return False, "不符合包含规则"
        if task.exclude:
            exclude_match = bool(
                (torrent.title and re.search(task.exclude, torrent.title, re.I))
                or (torrent.description and re.search(task.exclude, torrent.description, re.I))
            )
            if exclude_match:
                return False, "符合排除规则"
        smart_relaxed = task.smart_selection_enabled and task.smart_selection_relax_filters
        # 用户明确填写的大小是硬过滤，不能被“放宽大小/做种人数”开关绕过。
        # 否则填写 0.5 GB 时，智能选种仍可能加入更小的候选。
        if task.size and not size_range_matches(torrent.size, task.size):
            return False, "种子大小低于下限" if "-" not in task.size else "种子大小不在范围内"
        if task.seeder and not smart_relaxed:
            seeder_range = [float(value) for value in task.seeder.split("-")]
            seeders = torrent.seeders or 0
            if len(seeder_range) == 1 and seeders > seeder_range[0]:
                return False, "做种人数超过上限"
            if len(seeder_range) > 1 and not seeder_range[0] <= seeders <= seeder_range[1]:
                return False, "做种人数不在范围内"
        if task.pubtime:
            pubdate_minutes = self.__get_pubminutes(torrent.pubdate) - task.timezone_offset * 60
            pubtime_range = [float(value) for value in task.pubtime.split("-")]
            if len(pubtime_range) == 1 and pubdate_minutes > pubtime_range[0]:
                return False, "发布时间超过上限"
            if len(pubtime_range) > 1 and not pubtime_range[0] <= pubdate_minutes <= pubtime_range[1]:
                return False, "发布时间不在范围内"
        return True, None

    def check(
        self,
        task_id: Optional[str] = None,
        wait_for_lock: bool = False,
        force_cleanup: bool = False,
    ) -> None:
        """执行状态同步、删种和归档，到期检查可等待同任务的当前操作"""
        task = self._get_task_config(task_id)
        if not task or not self.get_state() or not task.enabled:
            return
        task_lock = self._task_locks.setdefault(task.id, threading.Lock())
        if not task_lock.acquire(blocking=wait_for_lock):
            logger.info(f"刷流任务 [{task.name}] 已有操作执行中，本轮检查跳过")
            return
        report = self._new_run_report("check")
        self._set_runtime(
            task.id,
            state="running",
            operation="force_cleanup" if force_cleanup else "check",
            last_error=None,
        )
        if force_cleanup:
            self._update_cleanup_progress(
                task.id,
                state="running",
                phase="正在读取下载器任务",
                percent=10,
            )
        try:
            with self._task_scope(task.id):
                self._run_check(task, report, force_cleanup=force_cleanup)
            report["success"] = report.get("result") not in {"downloader_unavailable", "downloader_error"}
        except Exception as err:
            report.update({"success": False, "error": str(err)})
            self._set_runtime(task.id, last_error=str(err))
            if force_cleanup:
                self._update_cleanup_progress(
                    task.id,
                    state="failed",
                    phase="清理失败",
                    percent=100,
                    error=str(err),
                    finished_at=time.time(),
                    display_until=time.time() + 8,
                )
            logger.error(f"刷流任务 [{task.name}] 检查失败：{str(err)}")
        finally:
            task_lock.release()
        report["finished_at"] = self._now_iso()
        self._append_run(task.id, report)
        if force_cleanup:
            if report.get("success"):
                deleted_count = int(report.get("deleted_count") or 0)
                freed_bytes = float(report.get("freed_bytes") or 0)
                self._update_cleanup_progress(
                    task.id,
                    state="completed",
                    phase="安全清理完成",
                    percent=100,
                    candidate_count=int(report.get("deletion_candidate_count") or report.get("planned_delete_count") or 0),
                    selected_count=int(report.get("selected_delete_count") or 0),
                    deleted_count=deleted_count,
                    freed_bytes=freed_bytes,
                    protected_count=int(report.get("protected_count") or 0),
                    message=(
                        f"已删除 {deleted_count} 个，释放 {self.__bytes_to_gb(freed_bytes):.1f} GB"
                        if deleted_count
                        else str(report.get("deletion_message") or "本轮没有种子通过最终安全复核")
                    ),
                    finished_at=time.time(),
                    display_until=time.time() + 8,
                )
            elif (self._runtime.get(task.id, {}).get("cleanup_progress") or {}).get("state") != "failed":
                self._update_cleanup_progress(
                    task.id,
                    state="failed",
                    phase="清理未完成",
                    percent=100,
                    error=str(report.get("error") or "下载器不可用，请检查连接后重试"),
                    finished_at=time.time(),
                    display_until=time.time() + 8,
                )
        self._set_runtime(task.id, state="idle", operation=None)

    def __get_tracker_items(self, torrent: Any) -> List[dict]:
        """获取 qBittorrent 的逐种子 Tracker 状态，兼容不同适配器字段。"""
        if isinstance(torrent, dict):
            trackers = torrent.get("trackers") or torrent.get("tracker_stats")
        else:
            trackers = getattr(torrent, "trackers", None) or getattr(torrent, "tracker_stats", None)
        if trackers:
            return list(trackers) if isinstance(trackers, (list, tuple)) else []

        downloader = self.downloader
        qbc = getattr(downloader, "qbc", None) if downloader else None
        torrent_hash = self.__get_hash(torrent)
        if not qbc or not torrent_hash:
            return []
        for method_name in ("torrents_trackers", "get_torrent_trackers"):
            method = getattr(qbc, method_name, None)
            if not method:
                continue
            try:
                try:
                    result = method(torrent_hash=torrent_hash)
                except TypeError:
                    result = method(torrent_hash)
                if isinstance(result, dict):
                    result = result.get("data", result.get("trackers", []))
                return list(result or []) if isinstance(result, (list, tuple)) else []
            except Exception as err:
                logger.debug(f"获取种子 [{torrent_hash}] Tracker 状态失败：{str(err)}")
        return []

    def __collect_invalid_tracker_states(
        self,
        torrents: List[Any],
    ) -> Tuple[Dict[str, List[dict]], Set[str]]:
        """扫描当前下载器 Tracker 状态，并收集仍然工作的 Tracker 域名。"""
        states: Dict[str, List[dict]] = {}
        working_domains: Set[str] = set()
        for torrent in torrents:
            torrent_hash = self.__get_hash(torrent)
            if not torrent_hash:
                continue
            trackers = self.__get_tracker_items(torrent)
            states[torrent_hash] = trackers
            for tracker in trackers:
                try:
                    status = int(tracker.get("status", -1))
                except (AttributeError, TypeError, ValueError):
                    status = -1
                if status not in (2, 3):
                    continue
                domain = tracker_endpoint_domain(
                    tracker.get("url", tracker.get("announce", tracker.get("tracker")))
                )
                if domain:
                    working_domains.add(domain)
        return states, working_domains

    def __plan_invalid_seed_deletions(
        self,
        torrents: List[Any],
        torrent_tasks: Dict[str, dict],
        tracker_states: Dict[str, List[dict]],
        working_domains: Set[str],
    ) -> Tuple[List[str], Dict[str, str]]:
        """按明确 Tracker 拒绝、跨种子故障确认和连续次数生成无效做种计划。"""
        task = self._get_task_config()
        if not task or not task.invalid_seed_cleanup_enabled:
            self._save_current_task_data("invalid_seed_plan", {})
            return [], {}

        now = time.time()
        history = self._current_task_data("invalid_seed_history", [])
        history = [
            row for row in history
            if now - float(row.get("at") or 0) <= 24 * 3600
        ]
        history_by_key = {
            (str(row.get("hash") or ""), str(row.get("signature") or "")): row
            for row in history
        }
        plan: Dict[str, str] = {}
        delete_hashes: List[str] = []
        active_keys: Set[Tuple[str, str]] = set()
        confirmations = max(int(task.invalid_seed_confirmations or 2), 1)

        for torrent in torrents:
            torrent_hash = self.__get_hash(torrent)
            torrent_task = torrent_tasks.get(torrent_hash)
            if not torrent_hash or not torrent_task or torrent_task.get("deleted"):
                continue
            if torrent_task.get("hit_and_run"):
                continue
            decision = detect_invalid_seed(
                tracker_states.get(torrent_hash, []),
                working_domains=working_domains,
            )
            if not decision.invalid:
                continue
            signature = "|".join(
                (*decision.domains, *decision.messages)
            )
            key = (torrent_hash, signature)
            active_keys.add(key)
            previous = history_by_key.get(key)
            previous_at = float(previous.get("at") or 0) if previous else 0
            count = int(previous.get("count") or 0) + 1 if now - previous_at <= 12 * 3600 else 1
            history_by_key[key] = {
                "hash": torrent_hash,
                "signature": signature,
                "count": count,
                "at": now,
                "domains": list(decision.domains),
                "messages": list(decision.messages),
            }
            if count < confirmations:
                continue
            reason = (
                f"Tracker 明确拒绝（{', '.join(decision.messages) or '无效做种'}），"
                f"已连续确认 {count} 次；仅移除 qB 任务，不删除下载数据"
            )
            delete_hashes.append(torrent_hash)
            plan[torrent_hash] = reason

        self._save_current_task_data(
            "invalid_seed_history",
            [row for key, row in history_by_key.items() if key in active_keys][-2000:],
        )
        self._save_current_task_data("invalid_seed_plan", plan)
        return list(dict.fromkeys(delete_hashes)), plan

    def _run_check(self, task: BrushTaskConfig, report: dict, force_cleanup: bool = False) -> None:
        """在已绑定任务上下文中执行刷流种子检查"""
        if force_cleanup:
            self._update_cleanup_progress(task.id, state="running", phase="正在连接下载器", percent=8)
        if not self._validate_task_reference(task) or not self.downloader:
            report["result"] = "downloader_unavailable"
            return
        torrent_tasks: Dict[str, dict] = self._current_task_data("torrents", {})
        unmanaged_tasks: Dict[str, dict] = self._current_task_data("unmanaged", {})
        downloader = self.downloader
        seeding_torrents, error = downloader.get_torrents()
        if error:
            report["result"] = "downloader_error"
            raise RuntimeError("连接下载器出错")
        seeding_torrents_dict = {self.__get_hash(torrent): torrent for torrent in seeding_torrents}
        self.__update_seeding_tasks_based_on_tags(torrent_tasks, unmanaged_tasks, seeding_torrents_dict)
        check_hashes = list(torrent_tasks.keys())
        if not check_hashes:
            self._cleanup_unused_task_tag(task, torrents=seeding_torrents)
            report.update({"result": "no_managed_torrents", "active_count": 0})
            self._recalculate_statistics(task.id)
            return
        check_torrents = [seeding_torrents_dict[item] for item in check_hashes if item in seeding_torrents_dict]
        if force_cleanup:
            self._update_cleanup_progress(
                task.id,
                phase=f"正在复核 {len(check_torrents)} 个托管种子",
                percent=30,
                candidate_count=len(check_torrents),
            )
        self.__update_torrent_tasks_state(check_torrents, torrent_tasks)
        health_summary = self._build_download_health_summary(torrent_tasks)
        report["download_health"] = health_summary
        if health_summary["stalled_count"] or health_summary["slow_count"]:
            logger.warning(
                f"刷流任务 [{task.name}] 下载健康："
                f"{health_summary['stalled_count']} 个长时间无进度，"
                f"{health_summary['slow_count']} 个异常低速；未完成种子仍受硬保护"
            )
        self.__update_undeleted_torrents_missing_in_downloader(torrent_tasks, check_hashes, seeding_torrents)
        filtered_torrents = self.__filter_torrents_by_tag(check_torrents, task.delete_except_tags)
        invalid_delete_hashes: List[str] = []
        invalid_seed_plan: Dict[str, str] = {}
        if task.invalid_seed_cleanup_enabled:
            tracker_states, working_domains = self.__collect_invalid_tracker_states(seeding_torrents)
            invalid_delete_hashes, invalid_seed_plan = self.__plan_invalid_seed_deletions(
                filtered_torrents,
                torrent_tasks,
                tracker_states,
                working_domains,
            )
        report["invalid_seed_plan_count"] = len(invalid_delete_hashes)
        report["invalid_seed_plan_reasons"] = list(invalid_seed_plan.values())
        smart_shadow_only = False
        if task.smart_enabled:
            regular_delete_hashes = self.__delete_torrent_for_smart(
                filtered_torrents,
                torrent_tasks,
                force_cleanup=force_cleanup,
            )
            smart_plan = self._current_task_data("smart_plan", {})
            report["smart_plan_count"] = len(smart_plan)
            report["smart_execute_count"] = len(regular_delete_hashes)
            report["smart_plan_reasons"] = list(smart_plan.values())
            smart_shadow_only = self._build_strategy_status(task.id).get("mode") in {"shadow", "paused"}
        else:
            # 9.0 只保留统一收益引擎；关闭自动删种时不会退回旧条件或动态路径。
            regular_delete_hashes = []
        invalid_delete_hashes = list(dict.fromkeys(invalid_delete_hashes or []))
        regular_delete_hashes = [
            torrent_hash
            for torrent_hash in dict.fromkeys(regular_delete_hashes or [])
            if torrent_hash not in invalid_delete_hashes
        ]
        planned_delete_count = len(invalid_delete_hashes) + int(report.get("smart_plan_count") or len(regular_delete_hashes))
        selected_delete_count = len(invalid_delete_hashes) + len(regular_delete_hashes)
        report["selected_delete_count"] = selected_delete_count
        if force_cleanup:
            self._update_cleanup_progress(
                task.id,
                phase=(
                    f"安全复核完成，{selected_delete_count} 个准备清理"
                    if selected_delete_count
                    else "安全复核完成，没有种子可删除"
                ),
                percent=60,
                candidate_count=planned_delete_count,
                selected_count=selected_delete_count,
            )
        deleted_from_downloader = False
        actual_invalid_hashes: List[str] = []
        actual_regular_hashes: List[str] = []
        if invalid_delete_hashes:
            if smart_shadow_only:
                logger.info(
                    f"[影子观察] 任务 [{task.name}] 本轮记录 {len(invalid_delete_hashes)} 个无效做种计划，未调用下载器"
                )
            else:
                self._append_decision_audit(
                    task.id,
                    {
                        "at": time.time(),
                        "kind": "invalid_tracker_deletion",
                        "hashes": list(invalid_delete_hashes),
                        "delete_files": False,
                        "reasons": dict(invalid_seed_plan),
                    },
                )
                if downloader.delete_torrents(ids=invalid_delete_hashes, delete_file=False):
                    deleted_from_downloader = True
                    actual_invalid_hashes = invalid_delete_hashes
                    for torrent_hash in actual_invalid_hashes:
                        if torrent_hash in torrent_tasks:
                            torrent_tasks[torrent_hash]["deleted"] = True
                            torrent_tasks[torrent_hash]["deleted_time"] = time.time()
                        torrent_task = torrent_tasks.get(torrent_hash)
                        if torrent_task:
                            self.__send_delete_message(
                                torrent_task,
                                invalid_seed_plan.get(torrent_hash, "Tracker 明确拒绝，清理无效做种"),
                            )
                    self._save_current_task_data("invalid_seed_plan", {})
                else:
                    logger.warning(f"刷流任务 [{task.name}] 清理无效做种失败，本轮保留任务")
        if regular_delete_hashes:
            if force_cleanup:
                self._update_cleanup_progress(
                    task.id,
                    phase=f"正在调用下载器删除 {len(regular_delete_hashes)} 个种子",
                    percent=75,
                )
            if DownloaderHelper().is_downloader("qbittorrent", service=self.service_info):
                self.__qb_torrents_reannounce(regular_delete_hashes)
            if downloader.delete_torrents(ids=regular_delete_hashes, delete_file=task.delete_files):
                deleted_from_downloader = True
                actual_regular_hashes = regular_delete_hashes
                for torrent_hash in actual_regular_hashes:
                    if torrent_hash in torrent_tasks:
                        torrent_tasks[torrent_hash]["deleted"] = True
                        torrent_tasks[torrent_hash]["deleted_time"] = time.time()
                if task.smart_enabled:
                    smart_plan = self._current_task_data("smart_plan", {})
                    for torrent_hash in actual_regular_hashes:
                        torrent_task = torrent_tasks.get(torrent_hash)
                        if torrent_task:
                            self.__send_delete_message(
                                torrent_task,
                                smart_plan.get(torrent_hash, "智能策略已确认删除"),
                            )
                    self._save_current_task_data("smart_plan", {})
                    self.__record_smart_deletions(actual_regular_hashes, torrent_tasks)
                    self._append_decision_audit(
                        task.id,
                        {
                            "at": time.time(),
                            "kind": "deletion_outcome",
                            "success": True,
                            "delete_files": bool(task.delete_files),
                            "hashes": list(actual_regular_hashes),
                        },
                    )
            else:
                logger.warning(f"刷流任务 [{task.name}] 普通删种执行失败，本轮保留任务")
                if task.smart_enabled:
                    self._append_decision_audit(
                        task.id,
                        {
                            "at": time.time(),
                            "kind": "deletion_outcome",
                            "success": False,
                            "hashes": list(regular_delete_hashes),
                        },
                    )
        need_delete_hashes = list(dict.fromkeys(actual_invalid_hashes + actual_regular_hashes))
        freed_bytes = sum(
            float((torrent_tasks.get(torrent_hash) or {}).get("size") or (torrent_tasks.get(torrent_hash) or {}).get("total_size") or 0)
            for torrent_hash in need_delete_hashes
        )
        report["freed_bytes"] = freed_bytes
        if force_cleanup:
            self._update_cleanup_progress(
                task.id,
                phase="下载器操作完成，正在整理结果",
                percent=90,
                deleted_count=len(need_delete_hashes),
                freed_bytes=freed_bytes,
            )
        self.__auto_archive_tasks(torrent_tasks)
        self._cleanup_unused_task_tag(
            task,
            torrents=None if deleted_from_downloader else seeding_torrents,
        )
        self._save_current_task_data("torrents", torrent_tasks)
        self._recalculate_statistics(task.id)
        report.update(
            {
                "result": "completed",
                "deleted_count": len(need_delete_hashes),
                "planned_delete_count": planned_delete_count,
                "dry_run": False,
                "active_count": sum(1 for item in torrent_tasks.values() if not item.get("deleted")),
                "force_cleanup": bool(force_cleanup),
            }
        )
        strategy_status = self._build_strategy_status(task.id)
        deletion_summary = (strategy_status.get("ui_summary") or {}).get("deletion") or {}
        report.update(
            {
                "deletion_state": deletion_summary.get("state"),
                "deletion_message": deletion_summary.get("message"),
                "deletion_candidate_count": int(deletion_summary.get("candidate_count") or 0),
                "deletion_candidate_bytes": float(deletion_summary.get("candidate_bytes") or 0),
                "protected_count": int(deletion_summary.get("protected_count") or 0),
                "protected_bytes": float(deletion_summary.get("protected_bytes") or 0),
            }
        )

    def __update_torrent_tasks_state(self, torrents: List[Any], torrent_tasks: Dict[str, dict]) -> None:
        """更新当前任务种子的上下传、分享率、做种时间和下载健康"""
        task = self._get_task_config()
        document = self._task_documents.get(task.id) if task else None
        if document:
            health_policy = DownloadHealthPolicy(
                stalled_confirmations=document.health.stalled_confirmations,
                stalled_window_minutes=document.health.stalled_window_minutes,
                slow_after_hours=document.health.slow_after_hours,
                slow_speed_kbps=document.health.slow_speed_kbps,
            )
        else:
            health_policy = policy_for_profile(task.smart_profile if task else "balanced")
        health_store = self._current_task_data("download_health", {})
        if not isinstance(health_store, dict):
            health_store = {}
        now = time.time()
        repair_hashes: List[str] = []
        pause_hashes: List[str] = []
        for torrent in torrents:
            torrent_hash = self.__get_hash(torrent)
            torrent_task = torrent_tasks.get(torrent_hash)
            if not torrent_task:
                continue
            torrent_info = self.__get_torrent_info(torrent)
            total_size = float(torrent_info.get("total_size") or 0)
            completed_bytes = float(
                torrent_info.get("completed")
                if torrent_info.get("completed") is not None
                else torrent_info.get("downloaded") or 0
            )
            is_completed = bool(total_size > 0 and completed_bytes >= total_size)
            current_sample = {
                "at": now,
                "downloaded": completed_bytes,
                "total_size": total_size,
                "download_speed": torrent_info.get("download_speed", 0),
                "active_peers": torrent_info.get("active_peers"),
                "availability": torrent_info.get("availability"),
                "is_paused": torrent_info.get("is_paused", False),
                "downloader_state": torrent_info.get("downloader_state", ""),
                "completed": is_completed,
            }
            health_record = health_store.get(torrent_hash)
            if not isinstance(health_record, dict):
                health_record = {}
            samples = append_download_sample(
                health_record.get("samples", []),
                current_sample,
                now=now,
                policy=health_policy,
            )
            health = assess_download_health(samples, current_sample, policy=health_policy, now=now)
            previous_state = health_record.get("state")
            state_since = (
                float(health_record.get("state_since") or now)
                if previous_state == health.get("state")
                else now
            )
            transition = next_health_action(
                health.get("state", HEALTH_UNKNOWN),
                health.get("progress_delta", 0),
                repair_at=health_record.get("repair_at"),
                paused_at=health_record.get("paused_at"),
                now=now,
                policy=health_policy,
            )
            if transition["action"] == "repair" and document and not document.health.auto_repair:
                transition = {
                    "action": None,
                    "repair_at": health_record.get("repair_at"),
                    "paused_at": health_record.get("paused_at"),
                }
            if transition["action"] == "pause" and document and not document.health.pause_after_failed_repair:
                transition = {
                    "action": None,
                    "repair_at": health_record.get("repair_at"),
                    "paused_at": health_record.get("paused_at"),
                }
            repair_at = transition["repair_at"]
            paused_at = transition["paused_at"]
            if document and document.health.auto_repair and transition["action"] == "repair":
                repair_hashes.append(torrent_hash)
            if document and document.health.pause_after_failed_repair and transition["action"] == "pause":
                pause_hashes.append(torrent_hash)
            health_store[torrent_hash] = {
                "hash": torrent_hash,
                "state": health.get("state", HEALTH_UNKNOWN),
                "reason": health.get("reason", "insufficient_history"),
                "state_since": state_since,
                "updated_at": now,
                "samples": samples,
                "repair_at": repair_at,
                "paused_at": paused_at,
            }
            torrent_task.update(
                {
                    "downloaded": torrent_info.get("downloaded"),
                    "uploaded": torrent_info.get("uploaded"),
                    "ratio": torrent_info.get("ratio"),
                    "seeding_time": torrent_info.get("seeding_time"),
                    "download_speed": torrent_info.get("download_speed", 0),
                    "download_completed_bytes": completed_bytes,
                    "download_health": health.get("state", HEALTH_UNKNOWN),
                    "download_health_label": health_label(health.get("state", HEALTH_UNKNOWN)),
                    "download_health_reason": health.get("reason", "insufficient_history"),
                    "download_health_since": state_since,
                    "download_health_avg_kbps": health.get("avg_download_speed_kbps", 0),
                    "download_health_progress_delta": health.get("progress_delta", 0),
                    "download_health_checked_at": now,
                }
            )
        self._save_current_task_data("download_health", health_store)
        self.__apply_download_health_actions(repair_hashes, pause_hashes)

    def __apply_download_health_actions(self, repair_hashes: List[str], pause_hashes: List[str]) -> None:
        """对异常未完成任务修复一次，持续失败后暂停；绝不删除数据。"""
        downloader = self.downloader
        qbc = getattr(downloader, "qbc", None) if downloader else None
        if not qbc:
            return
        if repair_hashes:
            hashes = "|".join(repair_hashes)
            try:
                qbc.torrents_reannounce(torrent_hashes=hashes)
                starter = getattr(qbc, "torrents_start", None) or getattr(qbc, "torrents_resume", None)
                if starter:
                    starter(torrent_hashes=hashes)
                logger.info(f"下载健康自动修复：已重新汇报并恢复 {len(repair_hashes)} 个未完成任务")
            except Exception as err:
                logger.warning(f"下载健康自动修复失败：{str(err)}")
        if pause_hashes:
            hashes = "|".join(pause_hashes)
            try:
                stopper = getattr(qbc, "torrents_stop", None) or getattr(qbc, "torrents_pause", None)
                if stopper:
                    stopper(torrent_hashes=hashes)
                logger.warning(f"下载健康：{len(pause_hashes)} 个任务修复后仍无进展，已暂停并保留数据")
                self.__send_message(
                    "【刷流任务下载异常】",
                    f"{len(pause_hashes)} 个未完成任务自动修复后仍无进展，已暂停；下载数据完整保留。",
                )
            except Exception as err:
                logger.warning(f"暂停异常下载失败：{str(err)}")

    @staticmethod
    def _build_download_health_summary(torrent_tasks: Dict[str, dict]) -> Dict[str, Any]:
        """从任务记录汇总卡住、低速和观察中的未完成下载。"""
        active_rows = [
            (str(torrent_hash), row)
            for torrent_hash, row in torrent_tasks.items()
            if isinstance(row, dict) and not row.get("deleted")
        ]
        stalled = [row for _, row in active_rows if row.get("download_health") == HEALTH_STALLED]
        slow = [row for _, row in active_rows if row.get("download_health") == HEALTH_SLOW]
        items = sorted(
            [
                (torrent_hash, row)
                for torrent_hash, row in active_rows
                if row.get("download_health") in {
                    HEALTH_STALLED,
                    HEALTH_SLOW,
                    HEALTH_QUEUED,
                    HEALTH_ERROR,
                }
            ],
            key=lambda item: (
                {
                    HEALTH_STALLED: 0,
                    HEALTH_SLOW: 1,
                    HEALTH_ERROR: 2,
                    HEALTH_QUEUED: 3,
                }.get(item[1].get("download_health"), 4),
                -float(item[1].get("download_health_since") or 0),
            ),
        )
        return {
            "stalled_count": len(stalled),
            "slow_count": len(slow),
            "queued_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_QUEUED),
            "checking_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_CHECKING),
            "error_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_ERROR),
            "paused_count": sum(1 for _, row in active_rows if row.get("download_health") == HEALTH_PAUSED),
            "observed_count": sum(
                1
                for _, row in active_rows
                if row.get("download_health") in {
                    HEALTH_UNKNOWN,
                    HEALTH_DOWNLOADING,
                    HEALTH_PAUSED,
                    HEALTH_QUEUED,
                    HEALTH_CHECKING,
                    HEALTH_ERROR,
                }
            ),
            "items": [
                {
                    "hash": torrent_hash,
                    "title": row.get("title"),
                    "state": row.get("download_health"),
                    "label": row.get("download_health_label") or health_label(row.get("download_health", HEALTH_UNKNOWN)),
                    "reason": row.get("download_health_reason"),
                    "since": row.get("download_health_since"),
                    "avg_kbps": row.get("download_health_avg_kbps", 0),
                    "progress_delta": row.get("download_health_progress_delta", 0),
                    "size": row.get("size", 0),
                }
                for torrent_hash, row in items[:20]
            ],
        }

    def __update_seeding_tasks_based_on_tags(
        self,
        torrent_tasks: Dict[str, dict],
        unmanaged_tasks: Dict[str, dict],
        seeding_torrents_dict: Dict[str, Any],
    ) -> None:
        """按任务唯一标签同步 qBittorrent 中的纳管和移除状态"""
        task = self._get_task_config()
        if not task or not DownloaderHelper().is_downloader("qbittorrent", service=self.service_info):
            return
        added_tasks: List[dict] = []
        removed_tasks: List[dict] = []
        reset_tasks: List[dict] = []
        for torrent_hash, torrent in seeding_torrents_dict.items():
            tags = self.__get_label(torrent)
            has_unique_tag = task.brush_tag in tags
            has_global_tag = self.GLOBAL_BRUSH_TAG in tags
            existing = torrent_hash in torrent_tasks
            adopt_legacy = (
                has_global_tag
                and not existing
                and self._is_primary_task_for_torrent(task, torrent)
            )
            managed = has_unique_tag or (has_global_tag and existing) or adopt_legacy
            if managed:
                if not existing:
                    torrent_task = unmanaged_tasks.pop(torrent_hash, None) or self.__convert_torrent_info_to_task(torrent)
                    torrent_task.update({"task_id": task.id, "task_name": task.name})
                    torrent_tasks[torrent_hash] = torrent_task
                    added_tasks.append(torrent_task)
                elif torrent_tasks[torrent_hash].get("deleted"):
                    torrent_tasks[torrent_hash]["deleted"] = False
                    torrent_tasks[torrent_hash].pop("deleted_time", None)
                    reset_tasks.append(torrent_tasks[torrent_hash])
            elif existing:
                unmanaged_tasks[torrent_hash] = torrent_tasks.pop(torrent_hash)
                removed_tasks.append(unmanaged_tasks[torrent_hash])
        self._save_current_task_data("torrents", torrent_tasks)
        self._save_current_task_data("unmanaged", unmanaged_tasks)
        if added_tasks:
            self.__log_and_send_torrent_task_update_message(
                "【刷流任务种子加入】", "纳入刷流管理", "刷流任务标签匹配", added_tasks
            )
        if removed_tasks:
            self.__log_and_send_torrent_task_update_message(
                "【刷流任务种子移除】", "移除刷流管理", "刷流任务标签移除", removed_tasks
            )
        if reset_tasks:
            self.__log_and_send_torrent_task_update_message(
                "【刷流任务状态更新】", "恢复为正常", "下载器中仍存在对应种子", reset_tasks
            )

    def _is_primary_task_for_torrent(self, task: BrushTaskConfig, torrent: Any) -> bool:
        """仅让同站点第一项任务接管没有唯一标签的旧版刷流种子"""
        site_id, _ = self.__get_site_by_torrent(torrent)
        if site_id != task.site_id:
            return False
        site_tasks = [item for item in self._task_configs.values() if item.site_id == site_id]
        return bool(site_tasks and site_tasks[0].id == task.id)

    @staticmethod
    def _smart_reason_label(code: str) -> str:
        """把单个引擎原因码翻译成通知、日志和界面可读的文本。"""
        labels = {
            "incomplete": "未完成下载",
            "hit_and_run": "H&R 保护",
            "missing_min_seed_time": "未配置站点最低保种时长",
            "min_seed_time": "尚未达到站点最低保种时长",
            "active_demand": "当前存在下载需求",
            "trusted_active_demand": "最近 3 次中至少 2 次存在真实下载需求",
            "real_upload": "最近出现真实上传增量或正在上传",
            "active_connection": "下载器仍有有效活动连接",
            "smart_cold_cooldown": "尚未达到智能冷种保护时间",
            "min_inactive_time": "尚未达到最低未活动时间",
            "excluded_tag": "命中删除排除标签",
            "low_retention_value": "长期低需求、低上传或资源不稀缺",
            "low_value_unconfirmed": "低价值信号尚未连续确认",
            "valuable_seed": "存在上传需求或资源稀缺，继续保留",
            "no_low_value_candidate": "没有通过安全线和连续确认的低价值候选",
            "byte_cap": "删除容量配额已用尽",
            "daily_count_cap": "每日删除数量配额已用尽",
            "run_count_cap": "单轮删除数量配额已用尽",
        }
        return labels.get(code, code)

    @classmethod
    def _smart_reason_text(cls, result: Any) -> str:
        """把引擎原因码翻译成通知和日志可读的文本。"""
        codes = getattr(result, "reason_codes", ()) or ()
        return "、".join(cls._smart_reason_label(code) for code in codes) or "智能策略"

    def _smart_policy(self, task: BrushTaskConfig) -> SmartPolicy:
        """从任务配置构造站点级智能策略；最低时长来自该任务绑定站点。"""
        excluded_tags = tuple(
            item.strip()
            for item in (task.delete_except_tags or "").split(",")
            if item.strip()
        )
        return SmartPolicy(
            profile=task.smart_profile,
            min_seed_time_hours=float(task.min_seed_time or 0),
            min_inactive_minutes=0.0,
            smart_cold_inactive_minutes=float(task.smart_cold_inactive_minutes or 0),
            protect_active_demand=bool(task.smart_protect_active_demand),
            demand_confirmations=int(task.smart_demand_confirmations or 2),
            low_value_confirmations=int(task.smart_candidate_confirmations or 3),
            low_value_span_minutes=float(task.smart_candidate_confirmation_minutes or 0),
            ratio_target=float(task.site_ratio_target or 2.0),
            ratio_weight=min(float(task.smart_ratio_weight or 5), 5),
            score_threshold=float(task.smart_score_threshold or 40),
            score_margin=float(task.smart_score_margin or 0),
            capacity_trigger_percent=float(task.smart_capacity_trigger_percent or 90),
            capacity_target_percent=float(task.smart_capacity_target_percent or 85),
            max_delete_per_run=int(task.smart_max_delete_per_run or 3),
            max_delete_percent_day=float(task.smart_max_delete_percent_day or 0),
            max_delete_capacity_percent_run=float(task.smart_max_delete_capacity_percent_run or 0),
            max_delete_capacity_percent_day=float(task.smart_max_delete_capacity_percent_day or 0),
            max_delete_gb_per_run=float(task.smart_max_delete_gb_per_run or 0),
            max_delete_gb_per_day=float(task.smart_max_delete_gb_per_day or 0),
            excluded_tags=excluded_tags,
        )

    def __record_smart_deletions(
        self,
        hashes: List[str],
        torrent_tasks: Dict[str, dict],
    ) -> None:
        """记录实际成功删除的智能候选，供每日删除上限使用。"""
        task = self._get_task_config()
        if not task or not hashes:
            return
        rows = self._get_task_data(task.id, "smart_deletions") or []
        now = time.time()
        rows = [row for row in rows if now - float(row.get("at") or 0) <= 31 * 86400]
        rows.extend(
            {
                "at": now,
                "hash": torrent_hash,
                "size": float(torrent_tasks.get(torrent_hash, {}).get("size") or 0),
            }
            for torrent_hash in hashes
        )
        self._save_task_data(task.id, "smart_deletions", rows[-500:])

    def __delete_torrent_for_smart(
        self,
        torrents: List[Any],
        torrent_tasks: Dict[str, dict],
        force_cleanup: bool = False,
    ) -> List[str]:
        """生成 9.0 统一删种计划；影子期和暂停期只记录、不执行。"""
        task = self._get_task_config()
        if not task or not task.smart_enabled:
            return []
        self._save_current_task_data("smart_plan", {})
        now = time.time()
        history = self._current_task_data("smart_history", [])
        if not isinstance(history, list):
            history = []
        history = [
            row for row in history
            if now - float(row.get("at") or 0) <= 30 * 86400
        ]
        observations: List[dict] = []
        learning_observations: List[dict] = []
        history_before_current = list(history)
        for torrent in torrents:
            torrent_hash = self.__get_hash(torrent)
            torrent_task = torrent_tasks.get(torrent_hash)
            if not torrent_task or torrent_task.get("deleted"):
                continue
            info = self.__get_torrent_info(torrent)
            info.update(
                {
                    "hash": torrent_hash,
                    "title": torrent_task.get("title") or info.get("title"),
                    "hit_and_run": bool(torrent_task.get("hit_and_run")),
                    "tags": info.get("tags") or self.__get_label(torrent),
                    "size": info.get("total_size") or torrent_task.get("size") or 0,
                }
            )
            observations.append(info)
            learning_row = {
                **torrent_task,
                **info,
                "hash": torrent_hash,
                "joined_at": torrent_task.get("time"),
                "feature_key": feature_key(torrent_task, joined_at=torrent_task.get("time")),
            }
            learning_observations.append(learning_row)
        if not observations:
            return []

        previous_learning_state = self._current_task_data("learning_state", {}) or {}
        learning_state = update_learning_state(
            previous_learning_state,
            learning_observations,
            now=now,
        )
        if learning_state.get("updated_at") != previous_learning_state.get("updated_at"):
            self._save_current_task_data("learning_state", learning_state)
        learning_info = learning_summary(learning_state)
        task_records = {
            str(item.get("hash")): item for item in learning_observations
        }
        enriched_observations: List[dict] = []
        for info in observations:
            torrent_hash = str(info.get("hash") or "")
            learned = predict_yield(learning_state, task_records.get(torrent_hash, info))
            metrics = recent_yield_metrics(
                learning_state,
                torrent_hash,
                uploaded=float(info.get("uploaded") or 0),
                size=float(info.get("size") or info.get("total_size") or 0),
                now=now,
            )
            previous_upload = next(
                (
                    float(row.get("uploaded") or 0)
                    for row in sorted(
                        (
                            item
                            for item in history_before_current
                            if str(item.get("hash") or "") == torrent_hash
                        ),
                        key=lambda item: float(item.get("at") or 0),
                        reverse=True,
                    )
                    if row.get("uploaded") is not None
                ),
                None,
            )
            if previous_upload is not None:
                immediate_delta = max(float(info.get("uploaded") or 0) - previous_upload, 0.0)
                metrics["upload_delta_since_check"] = immediate_delta
                for window in (1, 6, 24):
                    metrics[f"upload_delta_{window}h"] = max(
                        float(metrics.get(f"upload_delta_{window}h") or 0),
                        immediate_delta,
                    )
            enriched_observations.append(
                {
                    **info,
                    **metrics,
                    "learned_potential": (
                        float(learned.get("score") or 0)
                        / 25.0
                        * 15.0
                        * float(learned.get("confidence") or 0)
                    ),
                }
            )

        min_size = None
        max_size = None
        disk_limit = float(task.disksize) * 1024**3 if task.disksize else None
        deleted_rows = self._get_task_data(task.id, "smart_deletions") or []
        deleted_today = sum(
            1
            for row in deleted_rows
            if now - float(row.get("at") or 0) < 86400
        )
        deleted_today_bytes = sum(
            float(row.get("size") or 0)
            for row in deleted_rows
            if now - float(row.get("at") or 0) < 86400
        )
        current_size = self.__calculate_seeding_torrents_size(torrent_tasks)
        policy = self._smart_policy(task)
        if force_cleanup:
            policy = manual_cleanup_policy(policy)
        selection = select_deletions(
            enriched_observations,
            policy,
            current_size=current_size,
            min_size=min_size,
            max_size=max_size,
            disk_limit=disk_limit,
            history=history_before_current,
            deleted_today=0 if force_cleanup else deleted_today,
            deleted_today_bytes=0.0 if force_cleanup else deleted_today_bytes,
        )

        evaluated_by_hash = {result.torrent_hash: result for result in selection.evaluated}
        for info in enriched_observations:
            torrent_hash = str(info.get("hash") or "")
            result = evaluated_by_hash.get(torrent_hash)
            history.append(
                {
                    "at": now,
                    "hash": torrent_hash,
                    "uploaded": info.get("uploaded", 0),
                    "upload_speed": info.get("upload_speed", 0),
                    "avg_upload_speed": info.get("avg_upspeed", 0),
                    "active_peers": info.get("active_peers"),
                    "seeders": info.get("seeders"),
                    "leechers": info.get("leechers"),
                    "low_value": bool(result and result.action in {"watch", "candidate"}),
                    "score": result.score if result else None,
                }
            )
        self._save_current_task_data("smart_history", history[-5000:])

        results = {result.torrent_hash: result for result in selection.selected}
        delete_hashes: List[str] = []
        smart_plan: Dict[str, str] = {}
        for torrent_hash, result in results.items():
            torrent_task = torrent_tasks.get(torrent_hash)
            if not torrent_task:
                continue
            observation = next(
                (row for row in enriched_observations if str(row.get("hash") or "") == torrent_hash),
                {},
            )
            hard_reasons = self._smart_runtime_safety_reasons(task, observation)
            if hard_reasons:
                logger.error(
                    f"智能删种任务 [{task.name}] 守门拦截候选 {torrent_hash}："
                    f"{','.join(hard_reasons)}"
                )
                continue
            reason = (
                f"智能决策保留价值 {result.score:.1f} 分，"
                f"{self._smart_reason_text(result)}"
            )
            delete_hashes.append(torrent_hash)
            smart_plan[torrent_hash] = reason
        self._save_current_task_data("smart_plan", smart_plan)
        strategy = self._update_smart_strategy_state(
            task,
            enriched_observations,
            history_before_current,
            selection,
            learning_info,
            torrent_tasks,
        )
        self._append_decision_audit(
            task.id,
            {
                "at": now,
                "kind": "deletion",
                "engine": strategy.get("engine_version"),
                "mode": strategy.get("mode"),
                "force_cleanup": bool(force_cleanup),
                "pressure": selection.pressure,
                "current_size": current_size,
                "target_size": selection.target_size,
                "estimated_freed_bytes": selection.estimated_freed_bytes,
                "capacity_ratio": selection.capacity_ratio,
                "capacity_debt_bytes": selection.capacity_debt_bytes,
                "recovery_active": selection.recovery_active,
                "run_byte_cap": selection.run_byte_cap,
                "daily_byte_cap": selection.daily_byte_cap,
                "reason_codes": list(selection.reason_codes),
                "selected": [
                    {
                        "hash": result.torrent_hash,
                        "title": torrent_tasks.get(result.torrent_hash, {}).get("title"),
                        "size": torrent_tasks.get(result.torrent_hash, {}).get("size"),
                        "score": result.score,
                        "reasons": list(result.reason_codes),
                        "contributions": dict(result.contributions),
                    }
                    for result in selection.selected
                ],
                "evaluated": [
                    {
                        "hash": result.torrent_hash,
                        "title": torrent_tasks.get(result.torrent_hash, {}).get("title"),
                        "size": torrent_tasks.get(result.torrent_hash, {}).get("size"),
                        "action": result.action,
                        "score": result.score,
                        "reasons": list(result.reason_codes),
                    }
                    for result in selection.evaluated[:200]
                ],
            },
        )
        if not selection.selected:
            logger.info(
                f"智能删种任务 [{task.name}] 本轮不删："
                f"{','.join(selection.reason_codes) or '候选尚在连续确认或受硬安全线保护'}"
            )
            return []
        if strategy.get("mode") != "active" and not force_cleanup:
            logger.info(
                f"智能删种任务 [{task.name}] {strategy.get('mode_label')}："
                f"仅记录 {len(delete_hashes)} 个计划，不调用下载器"
            )
            return []
        if force_cleanup:
            logger.warning(
                f"刷流任务 [{task.name}] 执行手动安全清理：仅绕过观察期与删除额度，"
                "全部硬安全线仍然生效"
            )
        for torrent_hash in delete_hashes:
            logger.info(
                f"智能删种任务 [{task.name}] 已通过 9.0 守门，准备删除："
                f"{torrent_tasks.get(torrent_hash, {}).get('title')}"
            )
        return delete_hashes

    @staticmethod
    def _smart_runtime_safety_reasons(task: BrushTaskConfig, observation: dict) -> List[str]:
        """在调用下载器前独立复核硬安全线，防止评分回归导致误删。"""
        reasons: List[str] = []
        total_size = float(observation.get("total_size") or observation.get("size") or 0)
        downloaded = float(observation.get("downloaded") or 0)
        if total_size <= 0 or downloaded < total_size:
            reasons.append("incomplete")
        if observation.get("hit_and_run"):
            reasons.append("hit_and_run")
        if float(observation.get("seeding_time") or 0) < float(task.min_seed_time or 0) * 3600:
            reasons.append("min_seed_time")
        tags = {
            item.strip()
            for item in (
                observation.get("tags")
                if isinstance(observation.get("tags"), list)
                else str(observation.get("tags") or "").split(",")
            )
            if str(item).strip()
        }
        excluded = {item.strip() for item in str(task.delete_except_tags or "").split(",") if item.strip()}
        if tags.intersection(excluded):
            reasons.append("excluded_tag")
        if float(observation.get("upload_speed") or 0) > 0 or float(
            observation.get("upload_delta_since_check") or 0
        ) > 0:
            reasons.append("real_upload")
        if observation.get("active_peers") is not None and float(observation.get("active_peers") or 0) > 0:
            reasons.append("active_connection")
        return reasons

    def _update_smart_strategy_state(
        self,
        task: BrushTaskConfig,
        observations: List[dict],
        history: List[dict],
        selection: Any,
        learning_info: dict,
        torrent_tasks: Dict[str, dict],
    ) -> dict:
        """更新影子候选恢复情况，并在到期时执行自动守门。"""
        now = time.time()
        candidates = self._get_task_data(task.id, "smart_candidates") or {}
        if not isinstance(candidates, dict):
            candidates = {}
        observations_by_hash = {str(row.get("hash") or ""): row for row in observations}
        for torrent_hash, candidate in list(candidates.items()):
            if candidate.get("recovered") or now - float(candidate.get("planned_at") or 0) > 30 * 86400:
                continue
            observation = observations_by_hash.get(torrent_hash)
            if not observation or now - float(candidate.get("planned_at") or 0) > 24 * 3600:
                continue
            if float(observation.get("uploaded") or 0) > float(candidate.get("uploaded") or 0):
                candidate.update({"recovered": True, "recovered_at": now, "recovery_reason": "upload_delta"})
                continue
            demand_values: List[bool] = []
            if observation.get("leechers") is not None:
                demand_values.append(float(observation.get("leechers") or 0) > 0)
            for row in sorted(
                (item for item in history if str(item.get("hash") or "") == torrent_hash),
                key=lambda item: float(item.get("at") or 0),
                reverse=True,
            ):
                if len(demand_values) >= 3:
                    break
                if row.get("leechers") is not None:
                    demand_values.append(float(row.get("leechers") or 0) > 0)
            if sum(demand_values[:3]) >= int(task.smart_demand_confirmations or 2):
                candidate.update({"recovered": True, "recovered_at": now, "recovery_reason": "trusted_demand"})

        for result in selection.selected:
            if result.torrent_hash not in candidates:
                observation = observations_by_hash.get(result.torrent_hash, {})
                candidates[result.torrent_hash] = {
                    "hash": result.torrent_hash,
                    "title": torrent_tasks.get(result.torrent_hash, {}).get("title"),
                    "planned_at": now,
                    "uploaded": float(observation.get("uploaded") or 0),
                    "size": float(observation.get("size") or observation.get("total_size") or 0),
                    "score": result.score,
                    "recovered": False,
                }
        candidates = {
            key: value
            for key, value in candidates.items()
            if now - float(value.get("planned_at") or 0) <= 30 * 86400
        }
        self._save_task_data(task.id, "smart_candidates", candidates)
        candidate_count = len(candidates)
        false_positive_count = sum(1 for row in candidates.values() if row.get("recovered"))
        false_positive_rate = false_positive_count / candidate_count if candidate_count else 0.0
        previous = self._get_task_data(task.id, "strategy_state") or {}
        new_safety_violations = sum(
            1
            for result in selection.selected
            if self._smart_runtime_safety_reasons(
                task,
                observations_by_hash.get(result.torrent_hash, {}),
            )
        )
        safety_violations = int(previous.get("hard_safety_violations") or 0) + new_safety_violations

        alert = None
        if new_safety_violations:
            task.smart_shadow_until = max(float(task.smart_shadow_until or 0), now) + 24 * 3600
            task.smart_shadow_extensions += 1
            alert = f"检测到 {new_safety_violations} 个硬安全违规，已阻止执行并延长 24 小时"
            logger.error(
                f"智能删种任务 [{task.name}] 检测到 {new_safety_violations} 个硬安全违规，"
                "已阻止执行并延长影子观察 24 小时"
            )
            self._save_config()

        if task.smart_shadow_until is not None and float(task.smart_shadow_until) <= now:
            should_extend = safety_violations > 0 or (
                candidate_count >= 10 and false_positive_rate > 0.15
            )
            if should_extend and task.smart_auto_activate:
                task.smart_shadow_until = now + 24 * 3600
                task.smart_shadow_extensions += 1
                alert = (
                    f"影子观察自动延长 24 小时：误判率 {false_positive_rate:.1%}，"
                    f"硬安全违规 {safety_violations}"
                )
                logger.warning(f"智能删种任务 [{task.name}] {alert}")
                self._save_config()
            else:
                task.smart_shadow_until = None
                self._save_config()

        shadow_remaining = max(float(task.smart_shadow_until or 0) - now, 0.0)
        if task.smart_delete_paused:
            mode, mode_label = "paused", "自动删除已暂停"
        elif shadow_remaining > 0:
            mode, mode_label = "shadow", "影子观察中"
        else:
            mode, mode_label = "active", "自动删除已启用"
        state = {
            "engine_version": __version__,
            "profile": task.smart_profile,
            "mode": mode,
            "mode_label": mode_label,
            "shadow_until": task.smart_shadow_until,
            "shadow_remaining_seconds": shadow_remaining,
            "shadow_extensions": task.smart_shadow_extensions,
            "learning_confidence": learning_info.get("confidence", 0),
            "learning_sample_count": learning_info.get("sample_count", 0),
            "false_positive_count": false_positive_count,
            "candidate_count": candidate_count,
            "false_positive_rate": round(false_positive_rate, 4),
            "hard_safety_violations": safety_violations,
            "capacity_trigger_percent": task.smart_capacity_trigger_percent,
            "capacity_target_percent": task.smart_capacity_target_percent,
            "estimated_freed_bytes": selection.estimated_freed_bytes,
            "capacity_ratio": getattr(selection, "capacity_ratio", 0.0),
            "capacity_debt_bytes": getattr(selection, "capacity_debt_bytes", 0.0),
            "recovery_active": bool(getattr(selection, "recovery_active", False)),
            "recovery_run_byte_cap": getattr(selection, "run_byte_cap", 0.0),
            "recovery_daily_byte_cap": getattr(selection, "daily_byte_cap", 0.0),
            "pending_delete_count": len(selection.selected),
            "alert": alert,
            "updated_at": now,
        }
        self._save_task_data(task.id, "strategy_state", state)
        return state

    def __update_undeleted_torrents_missing_in_downloader(
        self,
        torrent_tasks: Dict[str, dict],
        torrent_check_hashes: List[str],
        torrents: List[Any],
    ) -> None:
        """把下载器中已不存在但仍标记正常的记录更新为已删除"""
        existing_hashes = set(self.__get_all_hashes(torrents))
        missing_hashes = [
            item for item in torrent_check_hashes
            if item not in existing_hashes and not torrent_tasks[item].get("deleted")
        ]
        deleted_tasks: List[dict] = []
        for torrent_hash in missing_hashes:
            torrent_task = torrent_tasks[torrent_hash]
            torrent_task.update({"deleted": True, "deleted_time": time.time()})
            deleted_tasks.append(torrent_task)
        if deleted_tasks:
            self.__log_and_send_torrent_task_update_message(
                "【刷流任务状态更新】", "更新为已删除", "下载器中找不到对应种子", deleted_tasks
            )

    def __convert_torrent_info_to_task(self, torrent: Any) -> dict:
        """把下载器种子转换为当前任务的托管记录"""
        torrent_info = self.__get_torrent_info(torrent)
        site_id, site_name = self.__get_site_by_torrent(torrent)
        task = self._get_task_config()
        return {
            "task_id": task.id if task else None,
            "task_name": task.name if task else None,
            "site": site_id,
            "site_name": site_name,
            "title": torrent_info.get("title", ""),
            "size": torrent_info.get("total_size", 0),
            "pubdate": None,
            "description": None,
            "page_url": None,
            "date_elapsed": None,
            "freedate": None,
            "uploadvolumefactor": None,
            "downloadvolumefactor": None,
            "hit_and_run": False,
            "volume_factor": None,
            "freedate_diff": None,
            "ratio": torrent_info.get("ratio", 0),
            "downloaded": torrent_info.get("downloaded", 0),
            "uploaded": torrent_info.get("uploaded", 0),
            "seeding_time": torrent_info.get("seeding_time", 0),
            "deleted": False,
            "time": torrent_info.get("add_on", time.time()),
        }

    @staticmethod
    def __get_redict_url(
        url: str,
        proxies: str = None,
        ua: str = None,
        cookie: str = None,
    ) -> Optional[str]:
        """解析带请求参数的跳转下载链接并返回真实地址"""
        match = re.search(r"\[(.*)](.*)", url)
        if not match:
            return None
        base64_str, request_url = match.group(1), match.group(2)
        if not base64_str:
            return request_url
        try:
            request_text = base64.b64decode(base64_str.encode("utf-8")).decode("utf-8")
            request_params: Dict[str, dict] = json.loads(request_text)
        except (ValueError, UnicodeDecodeError) as err:
            logger.error(f"解析种子跳转下载参数失败：{str(err)}")
            return None
        if not request_params.get("cookie"):
            cookie = None
        headers = request_params.get("header") or None
        request = RequestUtils(ua=ua, proxies=proxies, cookies=cookie, headers=headers)
        if request_params.get("method") == "get":
            response = request.get_res(request_url, params=request_params.get("params"))
        else:
            response = request.post_res(request_url, params=request_params.get("params"))
        if not response:
            return None
        result_path = request_params.get("result")
        if not result_path:
            return response.text
        data = response.json()
        success_key = request_params.get("success")
        if success_key and not data.get(success_key):
            return None
        for key in str(result_path).split("."):
            if not isinstance(data, dict):
                return None
            data = data.get(key)
            if data is None:
                return None
        result_url_path = request_params.get("result_path")
        result_query_param = request_params.get("result_query_param")
        if result_url_path and result_query_param:
            result_url = urljoin(
                f"{str(request_params.get('result_base_url')).rstrip('/')}/",
                str(result_url_path).lstrip("/"),
            )
            return f"{result_url}?{urlencode({result_query_param: data})}"
        return str(data)

    @staticmethod
    def __reset_download_url(torrent_url: str, site_id: int) -> str:
        """为支持的 NexusPHP 站点追加跳过下载提示参数"""
        try:
            if not torrent_url or torrent_url.startswith("magnet"):
                return torrent_url
            site = next(
                (item for item in SitesHelper().get_indexers() if item.get("id") == site_id),
                None,
            )
            if not site or site.get("name") in {"天空"} or not site.get("schema", "").startswith("Nexus"):
                return torrent_url
            parsed_url = urlparse(torrent_url)
            query_params = dict(parse_qsl(parsed_url.query))
            query_params["letdown"] = "1"
            return str(urlunparse(parsed_url._replace(query=urlencode(query_params))))
        except Exception as err:
            logger.error(f"处理种子下载提示地址失败：{str(err)}")
            return torrent_url

    def __download(self, torrent: TorrentInfo) -> Optional[str]:
        """按当前任务配置向 qBittorrent 或 Transmission 添加种子"""
        task = self._get_task_config()
        if not task or not torrent.enclosure:
            logger.error(f"获取种子下载链接失败：{torrent.title}")
            return None
        up_speed = int(task.up_speed) if task.up_speed else None
        down_speed = int(task.dl_speed) if task.dl_speed else None
        torrent_content: Union[str, bytes] = torrent.enclosure
        proxies = settings.PROXY if torrent.site_proxy else None
        cookies = torrent.site_cookie
        if isinstance(torrent_content, str) and torrent_content.startswith("["):
            torrent_content = self.__get_redict_url(
                torrent_content,
                proxies=proxies,
                ua=torrent.site_ua,
                cookie=cookies,
            )
            cookies = None
        if not torrent_content:
            return None
        if task.site_skip_tips and isinstance(torrent_content, str):
            torrent_content = self.__reset_download_url(torrent_content, torrent.site)
        downloader = self.downloader
        service = self.service_info
        if not downloader or not service:
            return None
        downloader_helper = DownloaderHelper()
        if downloader_helper.is_downloader("qbittorrent", service=service):
            up_limit = up_speed * 1024 if up_speed else None
            down_limit = down_speed * 1024 if down_speed else None
            random_tag = StringUtils.generate_random_str(10)
            if isinstance(torrent_content, str) and not torrent_content.startswith("magnet"):
                response = RequestUtils(cookies=cookies, proxies=proxies, ua=torrent.site_ua).get_res(
                    url=torrent_content
                )
                if response and response.ok:
                    torrent_content = response.content
            if not downloader.add_torrent(
                content=torrent_content,
                download_dir=task.save_path,
                cookie=cookies,
                category=task.qb_category,
                tag=[task.brush_tag, random_tag],
                upload_limit=up_limit,
                download_limit=down_limit,
            ):
                return None
            torrent_hash = downloader.get_torrent_id_by_tag(tags=random_tag)
            if not torrent_hash:
                logger.error(f"刷流任务 [{task.name}] 获取种子 Hash 失败")
            return torrent_hash
        if downloader_helper.is_downloader("transmission", service=service):
            if isinstance(torrent_content, str) and not torrent_content.startswith("magnet"):
                response = RequestUtils(cookies=cookies, proxies=proxies, ua=torrent.site_ua).get_res(
                    url=torrent_content
                )
                if response and response.ok:
                    torrent_content = response.content
            added_torrent = downloader.add_torrent(
                content=torrent_content,
                download_dir=task.save_path,
                cookie=cookies,
                labels=[task.brush_tag],
            )
            if not added_torrent:
                return None
            if task.up_speed or task.dl_speed:
                downloader.change_torrent(
                    hash_string=added_torrent.hashString,
                    upload_limit=up_speed,
                    download_limit=down_speed,
                )
            return added_torrent.hashString
        return None

    def __qb_torrents_reannounce(self, torrent_hashes: List[str]) -> None:
        """删除 qBittorrent 种子前强制重新汇报 Tracker"""
        downloader = self.downloader
        if not downloader or not getattr(downloader, "qbc", None) or not torrent_hashes:
            return
        try:
            downloader.qbc.torrents_reannounce(torrent_hashes=torrent_hashes)
        except Exception as err:
            logger.error(f"强制重新汇报 Tracker 失败：{str(err)}")

    def __get_hash(self, torrent: Any) -> str:
        """兼容获取 qBittorrent 与 Transmission 种子 Hash"""
        try:
            service = self.service_info
            if service and DownloaderHelper().is_downloader("qbittorrent", service=service):
                return torrent.get("hash") or ""
            return getattr(torrent, "hashString", "") or ""
        except Exception as err:
            logger.error(f"获取种子 Hash 失败：{str(err)}")
            return ""

    def __get_all_hashes(self, torrents: List[Any]) -> List[str]:
        """提取下载器种子列表中的全部有效 Hash"""
        return [torrent_hash for torrent in torrents if (torrent_hash := self.__get_hash(torrent))]

    def __get_label(self, torrent: Any) -> List[str]:
        """兼容获取 qBittorrent 标签和 Transmission Labels"""
        try:
            service = self.service_info
            if service and DownloaderHelper().is_downloader("qbittorrent", service=service):
                return [item.strip() for item in str(torrent.get("tags") or "").split(",") if item.strip()]
            return [str(item).strip() for item in getattr(torrent, "labels", None) or [] if str(item).strip()]
        except Exception as err:
            logger.error(f"获取种子标签失败：{str(err)}")
            return []

    def __get_torrent_info(self, torrent: Any) -> dict:
        """统一提取 qBittorrent 与 transmission-rpc v7 种子状态"""
        now_timestamp = int(time.time())
        service = self.service_info
        if service and DownloaderHelper().is_downloader("qbittorrent", service=service):
            torrent_id = torrent.get("hash")
            title = torrent.get("name")
            added_on = torrent.get("added_on") or 0
            completion_on = torrent.get("completion_on") or 0
            last_activity = torrent.get("last_activity") or 0
            dltime = now_timestamp - added_on if added_on > 0 else 0
            seeding_time = now_timestamp - completion_on if completion_on > 0 else 0
            iatime = now_timestamp - last_activity if last_activity > 0 else 0
            ratio = torrent.get("ratio") or 0
            uploaded = torrent.get("uploaded") or 0
            downloaded = torrent.get("downloaded") or 0
            total_size = torrent.get("total_size") or torrent.get("size") or 0
            completed = torrent.get("completed")
            if completed is None:
                progress = torrent.get("progress")
                completed = (
                    float(total_size) * float(progress)
                    if progress is not None and float(progress) <= 1
                    else downloaded
                )
            upload_speed = torrent.get("upspeed") or torrent.get("upload_speed") or 0
            download_speed = torrent.get("dlspeed") or torrent.get("download_speed") or 0
            downloader_state = str(torrent.get("state") or "").lower()
            is_paused = (
                downloader_state in {"paused", "pauseddl", "pausedup", "stopped"}
                or downloader_state.startswith("paused")
                or downloader_state.startswith("stopped")
            )
            tracker_seeders = torrent.get("num_complete")
            if tracker_seeders is None or float(tracker_seeders) < 0:
                tracker_seeders = torrent.get("seeders")
            tracker_leechers = torrent.get("num_incomplete")
            if tracker_leechers is None or float(tracker_leechers) < 0:
                tracker_leechers = torrent.get("leechers")
            seeders = tracker_seeders if tracker_seeders is not None and float(tracker_seeders) >= 0 else None
            leechers = tracker_leechers if tracker_leechers is not None and float(tracker_leechers) >= 0 else None
            active_peers = torrent.get("num_leechs")
            active_peers = active_peers if active_peers is not None and float(active_peers) >= 0 else None
            availability = torrent.get("availability") or 0
            tags = torrent.get("tags") or ""
            tracker = torrent.get("tracker") or ""
        else:
            torrent_id = getattr(torrent, "hashString", "")
            title = getattr(torrent, "name", "")
            done_date = getattr(torrent, "done_date", None) or getattr(torrent, "date_done", None)
            added_date = getattr(torrent, "added_date", None) or getattr(torrent, "date_added", None)
            activity_date = getattr(torrent, "activity_date", None) or getattr(torrent, "date_active", None)
            done_timestamp = int(done_date.timestamp()) if done_date and done_date.timestamp() > 0 else 0
            added_on = int(added_date.timestamp()) if added_date and added_date.timestamp() > 0 else 0
            activity_timestamp = int(activity_date.timestamp()) if activity_date and activity_date.timestamp() > 0 else 0
            seeding_time = now_timestamp - done_timestamp if done_timestamp else 0
            dltime = now_timestamp - added_on if added_on else 0
            iatime = now_timestamp - activity_timestamp if activity_timestamp else 0
            total_size = getattr(torrent, "total_size", 0) or 0
            progress = getattr(torrent, "progress", 0) or 0
            downloaded = int(total_size * progress / 100)
            ratio = getattr(torrent, "ratio", 0) or 0
            uploaded = int(downloaded * ratio)
            upload_speed = getattr(torrent, "upload_speed", 0) or getattr(torrent, "upspeed", 0) or 0
            download_speed = getattr(torrent, "download_speed", 0) or getattr(torrent, "dlspeed", 0) or 0
            completed = downloaded
            transmission_status = int(getattr(torrent, "status", 1) or 1)
            is_paused = transmission_status == 0
            downloader_state = str(transmission_status)
            seeders = getattr(torrent, "seeders", None)
            leechers = getattr(torrent, "leechers", None)
            active_peers = getattr(torrent, "peers_connected", None)
            availability = getattr(torrent, "availability", 0) or 0
            tags = getattr(torrent, "labels", None) or ""
            tracker_list = getattr(torrent, "tracker_list", None)
            tracker = tracker_list[0] if tracker_list else ""
        avg_upspeed = int(uploaded / dltime) if dltime else uploaded
        return {
            "hash": torrent_id,
            "title": title,
            "seeding_time": seeding_time,
            "ratio": ratio,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "completed": completed,
            "avg_upspeed": avg_upspeed,
            "upload_speed": upload_speed,
            "download_speed": download_speed,
            "seeders": seeders,
            "leechers": leechers,
            "active_peers": active_peers,
            "availability": availability,
            "iatime": iatime,
            "dltime": dltime,
            "total_size": total_size,
            "add_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(added_on)),
            "add_on": added_on,
            "tags": tags,
            "tracker": tracker,
            "is_paused": is_paused,
            "downloader_state": downloader_state,
        }

    def __get_average_bandwidth(
        self,
        sample_count: int = 5,
        interval: float = 3.0,
    ) -> Tuple[Optional[float], Optional[float]]:
        """多次采样所有下载器带宽并返回平均值"""
        upload_speeds: List[float] = []
        download_speeds: List[float] = []
        for index in range(sample_count):
            downloader_info = self.__get_downloader_info()
            if downloader_info:
                upload_speeds.append(downloader_info.upload_speed or 0)
                download_speeds.append(downloader_info.download_speed or 0)
            if index < sample_count - 1:
                time.sleep(interval)
        if not upload_speeds or not download_speeds:
            return None, None
        return sum(upload_speeds) / len(upload_speeds), sum(download_speeds) / len(download_speeds)

    def __get_downloader_info(self) -> schemas.DownloaderInfo:
        """通过插件链汇总当前所有下载器的实时传输信息"""
        result = schemas.DownloaderInfo()
        transfer_infos = self.chain.run_module("downloader_info")
        for transfer_info in transfer_infos or []:
            result.download_speed += transfer_info.download_speed
            result.upload_speed += transfer_info.upload_speed
            result.download_size += transfer_info.download_size
            result.upload_size += transfer_info.upload_size
        return result

    def __get_downloading_count(self) -> int:
        """获取带当前任务唯一标签的下载中种子数量"""
        task = self._get_task_config()
        downloader = self.downloader
        if not task or not downloader:
            return 0
        try:
            torrents = downloader.get_downloading_torrents(tags=task.brush_tag)
            return len(torrents or [])
        except Exception as err:
            logger.error(f"获取任务 [{task.name}] 下载数量失败：{str(err)}")
            return 0

    def __get_global_downloading_count(self) -> int:
        """按下载器去重汇总带全局刷流标签或任务标签的下载中种子数量。"""
        total_count = 0
        downloader_names = {task.downloader for task in self._task_configs.values() if task.downloader}
        downloader_helper = DownloaderHelper()
        for downloader_name in downloader_names:
            try:
                service = downloader_helper.get_service(name=downloader_name)
                if not service or not service.instance:
                    continue
                task_tags = {
                    task.brush_tag for task in self._task_configs.values() if task.downloader == downloader_name
                } | {self.GLOBAL_BRUSH_TAG}
                torrents = service.instance.get_downloading_torrents()
                total_count += sum(
                    1 for torrent in torrents or [] if task_tags.intersection(self.__get_label(torrent))
                )
            except Exception as err:
                logger.error(f"获取下载器 [{downloader_name}] 全局刷流下载数量失败：{str(err)}")
        return total_count

    @staticmethod
    def __get_pubminutes(pubdate: str) -> float:
        """计算站点发布时间距当前时间的分钟数"""
        if not pubdate:
            return 0
        try:
            publish_time = datetime.strptime(pubdate.replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - publish_time).total_seconds() / 60
        except (TypeError, ValueError) as err:
            logger.error(f"解析发布时间 {pubdate} 失败：{str(err)}")
            return 0

    def __filter_torrents_by_tag(self, torrents: List[Any], exclude_tag: Optional[str]) -> List[Any]:
        """过滤包含任一删除排除标签的种子"""
        if not exclude_tag:
            return torrents
        excluded_tags = {item.strip() for item in exclude_tag.split(",") if item.strip()}
        return [
            torrent for torrent in torrents
            if not excluded_tags.intersection(self.__get_label(torrent))
        ]

    def __get_subscribe_titles(self) -> Set[str]:
        """识别并缓存当前订阅可用于排除匹配的标题集合"""
        task = self._get_task_config()
        if not task or not task.except_subscribe:
            return set()
        subscribes = SubscribeOper().list() or []
        for subscribe in subscribes:
            cache_key = f"{subscribe.id}_{subscribe.name}"
            if cache_key in self._subscribe_infos:
                continue
            titles = [subscribe.name]
            try:
                meta = MetaInfo(subscribe.name)
                meta.year = subscribe.year
                meta.begin_season = subscribe.season or None
                meta.type = MediaType(subscribe.type)
                mediainfo: MediaInfo = self.chain.recognize_media(
                    meta=meta,
                    mtype=meta.type,
                    media_source=subscribe.media_source,
                    media_id=subscribe.media_id,
                    cache=True,
                )
                if mediainfo:
                    titles.extend(mediainfo.names)
            except Exception as err:
                logger.error(f"识别订阅 {subscribe.name} 失败：{str(err)}")
            self._subscribe_infos[cache_key] = [item.strip() for item in titles if item and item.strip()]
        current_keys = {f"{subscribe.id}_{subscribe.name}" for subscribe in subscribes}
        for cache_key in set(self._subscribe_infos) - current_keys:
            self._subscribe_infos.pop(cache_key, None)
        return {title for titles in self._subscribe_infos.values() for title in titles}

    @staticmethod
    def __filter_torrents_contains_subscribe(
        torrents: List[TorrentInfo],
        subscribe_titles: Set[str],
    ) -> List[TorrentInfo]:
        """排除标题或描述命中任一订阅名称的候选种子"""
        if not subscribe_titles:
            return torrents
        included: List[TorrentInfo] = []
        for torrent in torrents:
            title = torrent.title or ""
            description = torrent.description or ""
            if any(item in title or item in description for item in subscribe_titles):
                logger.info(f"命中订阅内容，排除种子：{title}|{description}")
                continue
            included.append(torrent)
        return included

    @staticmethod
    def __bytes_to_gb(size_in_bytes: float) -> float:
        """把字节数转换为 GB"""
        return float(size_in_bytes or 0) / 1024 ** 3

    @staticmethod
    def __calculate_seeding_torrents_size(torrent_tasks: Dict[str, dict]) -> float:
        """计算未删除托管种子的总做种体积"""
        return sum(
            item.get("size", 0) or 0
            for item in torrent_tasks.values()
            if not item.get("deleted")
        )

    def __auto_archive_tasks(self, torrent_tasks: Dict[str, dict]) -> None:
        """按当前任务保留天数归档已删除种子记录"""
        task = self._get_task_config()
        if not task or not task.auto_archive_days or task.auto_archive_days <= 0:
            return
        archived_tasks: Dict[str, dict] = self._current_task_data("archived", {})
        threshold = float(task.auto_archive_days) * 86400
        now_timestamp = time.time()
        archive_hashes = []
        for torrent_hash, item in torrent_tasks.items():
            if not item.get("deleted"):
                continue
            deleted_time = item.get("deleted_time")
            if deleted_time is None or (
                isinstance(deleted_time, (int, float))
                and now_timestamp - deleted_time > threshold
            ):
                archive_hashes.append(torrent_hash)
        for torrent_hash in archive_hashes:
            archived_tasks[torrent_hash] = torrent_tasks.pop(torrent_hash)
        self._save_current_task_data("archived", archived_tasks)

    def _recalculate_statistics(self, task_id: str) -> Dict[str, int]:
        """从当前和归档记录重新计算单任务统计"""
        torrents = self._get_task_data(task_id, "torrents") or {}
        archived = self._get_task_data(task_id, "archived") or {}
        combined = {**archived, **torrents}
        statistic = {
            "count": len(combined),
            "deleted": sum(1 for item in combined.values() if item.get("deleted")),
            "uploaded": sum(item.get("uploaded", 0) or 0 for item in combined.values()),
            "downloaded": sum(item.get("downloaded", 0) or 0 for item in combined.values()),
            "unarchived": sum(1 for item in torrents.values() if item.get("deleted")),
            "active": sum(1 for item in torrents.values() if not item.get("deleted")),
            "active_uploaded": sum(
                item.get("uploaded", 0) or 0 for item in torrents.values() if not item.get("deleted")
            ),
            "active_downloaded": sum(
                item.get("downloaded", 0) or 0 for item in torrents.values() if not item.get("deleted")
            ),
        }
        self._save_task_data(task_id, "statistic", statistic)
        return statistic

    def _get_statistic_info(self, task_id: str) -> Dict[str, int]:
        """读取单任务统计并为历史空数据补齐字段"""
        defaults = {
            "count": 0,
            "deleted": 0,
            "uploaded": 0,
            "downloaded": 0,
            "unarchived": 0,
            "active": 0,
            "active_uploaded": 0,
            "active_downloaded": 0,
        }
        statistic = self._get_task_data(task_id, "statistic") or {}
        return {**defaults, **statistic}

    @staticmethod
    def _is_valid_time_range(time_range: Optional[str]) -> bool:
        """校验 HH:MM-HH:MM 格式的每日时间段"""
        if not time_range or not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", time_range):
            return False
        try:
            start, end = time_range.split("-", 1)
            datetime.strptime(start, "%H:%M")
            datetime.strptime(end, "%H:%M")
            return True
        except ValueError:
            return False

    def _is_current_time_in_range(self, task: Optional[BrushTaskConfig] = None) -> bool:
        """判断当前时间是否处于任务允许的每日开启区间"""
        task = task or self._get_task_config()
        if not task or not self._is_valid_time_range(task.active_time_range):
            return True
        start_text, end_text = task.active_time_range.split("-", 1)
        start_time = datetime.strptime(start_text, "%H:%M").time()
        end_time = datetime.strptime(end_text, "%H:%M").time()
        current_time = datetime.now().time()
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        return current_time >= start_time or current_time <= end_time

    @staticmethod
    def __get_site_by_torrent(torrent: Any) -> Tuple[int, str]:
        """根据 Tracker 或磁力链接识别种子所属站点"""
        trackers: List[str] = []
        last_domain = "未知"
        tracker_url = torrent.get("tracker") if isinstance(torrent, dict) else None
        if not tracker_url:
            tracker_list = getattr(torrent, "tracker_list", None)
            tracker_url = tracker_list[0] if tracker_list else None
        if tracker_url:
            trackers.append(tracker_url)
        magnet_link = torrent.get("magnet_uri") if isinstance(torrent, dict) else getattr(torrent, "magnet_link", None)
        if magnet_link:
            trackers.extend(unquote(item) for item in parse_qs(urlparse(magnet_link).query).get("tr", []))
        tracker_mappings = {
            "chdbits.xyz": "ptchdbits.co",
            "agsvpt.trackers.work": "agsvpt.com",
            "tracker.cinefiles.info": "audiences.me",
        }
        for tracker in trackers:
            if not tracker:
                continue
            domain = next(
                (mapped for keyword, mapped in tracker_mappings.items() if keyword in tracker),
                StringUtils.get_url_domain(tracker),
            )
            last_domain = domain or last_domain
            site = SitesHelper().get_indexer(domain)
            if site:
                return site.get("id"), site.get("name")
        return 0, last_domain

    def _log_and_notify_error(self, message: str) -> None:
        """记录错误并写入系统消息中心"""
        logger.error(message)
        self.systemmessage.put(message, title="站点刷流")

    def __send_delete_message(self, torrent_task: dict, reason: str) -> None:
        """发送包含任务、站点、种子和原因的删种通知"""
        task = self._get_task_config()
        if not task or not task.notify:
            return
        text = (
            f"任务：{task.name}\n"
            f"站点：{torrent_task.get('site_name') or '未知'}\n"
            f"标题：{torrent_task.get('title') or '未知'}\n"
            f"原因：{reason}"
        )
        self.post_message(mtype=NotificationType.SiteMessage, title="【刷流任务种子删除】", text=text)

    @staticmethod
    def __build_add_message_text(torrent: Union[TorrentInfo, dict], task_name: str) -> str:
        """兼容候选对象和任务字典构建新增通知文本"""
        def read_value(key: str, default: Any = None) -> Any:
            """统一读取候选对象或字典字段"""
            return torrent.get(key, default) if isinstance(torrent, dict) else getattr(torrent, key, default)

        lines = [f"任务：{task_name}"]
        labels = {
            "site_name": "站点",
            "title": "标题",
            "description": "内容",
            "size": "大小",
            "pubdate": "发布时间",
            "seeders": "做种数",
            "volume_factor": "促销",
            "hit_and_run": "Hit&Run",
        }
        for key, label in labels.items():
            value = read_value(key)
            if key == "size" and value:
                value = StringUtils.str_filesize(value)
            if value not in (None, "", False):
                lines.append(f"{label}：{'是' if key == 'hit_and_run' else value}")
        return "\n".join(lines)

    def __send_add_message(self, torrent: Union[TorrentInfo, dict]) -> None:
        """发送当前任务新增刷流种子的通知"""
        task = self._get_task_config()
        if not task or not task.notify:
            return
        self.post_message(
            mtype=NotificationType.SiteMessage,
            title="【刷流任务种子下载】",
            text=self.__build_add_message_text(torrent, task.name),
        )

    def __send_message(self, title: str, text: str) -> None:
        """按当前任务通知开关发送通用站点消息"""
        task = self._get_task_config()
        if task and task.notify:
            self.post_message(mtype=NotificationType.SiteMessage, title=title, text=text)

    def __log_and_send_torrent_task_update_message(
        self,
        title: str,
        status: str,
        reason: str,
        torrent_tasks: List[dict],
    ) -> None:
        """记录并汇总发送标签同步导致的任务状态变更"""
        if not torrent_tasks:
            return
        task = self._get_task_config()
        first_title = torrent_tasks[0].get("title") or "未知种子"
        text = (
            f"任务：{task.name if task else '未知'}\n"
            f"内容：{first_title} 等 {len(torrent_tasks)} 个种子已{status}\n"
            f"原因：{reason}"
        )
        logger.info(f"{title}，{text}")
        self.__send_message(title, text)

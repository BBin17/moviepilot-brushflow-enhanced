"""BrushFlow 9.0 单一任务模型与可重复迁移。"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


Profile = Literal["conservative", "balanced", "aggressive", "custom"]


class IdentityConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    site_id: int = Field(..., gt=0)
    downloader: str = Field(..., min_length=1, max_length=80)
    save_path: Optional[str] = None
    tag: Optional[str] = None
    enabled: bool = True
    notify: bool = True


class ScheduleConfig(BaseModel):
    brush_interval: int = Field(10, ge=1, le=1440)
    check_interval: int = Field(5, ge=1, le=1440)
    cron: Optional[str] = None
    active_time_range: Optional[str] = None


class GoalConfig(BaseModel):
    enabled: bool = False
    ratio_target: Optional[float] = Field(None, gt=0)
    reached_behavior: Literal["continue", "pause"] = "continue"

    @model_validator(mode="after")
    def require_target(self):
        if self.enabled and self.ratio_target is None:
            raise ValueError("启用分享率目标时必须填写目标值")
        return self


class CapacityConfig(BaseModel):
    limit_gb: Optional[float] = Field(None, gt=0)
    max_downloads: Optional[int] = Field(None, gt=0)
    upload_limit_kbps: Optional[float] = Field(None, gt=0)
    download_limit_kbps: Optional[float] = Field(None, gt=0)
    torrent_upload_limit_kbps: Optional[float] = Field(None, gt=0)
    torrent_download_limit_kbps: Optional[float] = Field(None, gt=0)


class SelectionConfig(BaseModel):
    enabled: bool = True
    source: Literal["page", "rss"] = "page"
    promotion: Literal["all", "free", "2xfree"] = "free"
    exclude_hr: bool = True
    site_hr_active: bool = False
    exclude_subscriptions: bool = True
    size_min_gb: Optional[float] = Field(None, ge=0)
    size_max_gb: Optional[float] = Field(None, gt=0)
    seeder_range: Optional[str] = None
    published_min_minutes: Optional[float] = Field(None, ge=0)
    published_max_minutes: Optional[float] = Field(None, gt=0)
    timezone_offset: float = 0
    include: Optional[str] = None
    exclude: Optional[str] = None

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.size_min_gb is not None and self.size_max_gb is not None:
            if self.size_min_gb > self.size_max_gb:
                raise ValueError("种子最小体积不能大于最大体积")
        if self.published_min_minutes is not None and self.published_max_minutes is not None:
            if self.published_min_minutes > self.published_max_minutes:
                raise ValueError("发布时间最小值不能大于最大值")
        for pattern in (self.include, self.exclude):
            if pattern:
                re.compile(pattern)
        return self


class DeletionConfig(BaseModel):
    enabled: bool = False
    min_seed_hours: Optional[float] = Field(None, gt=0)
    exclude_tags: Optional[str] = None
    delete_data: bool = True
    invalid_tracker_cleanup: bool = False
    invalid_tracker_confirmations: int = Field(2, ge=1, le=5)
    paused: bool = False
    observation_started_at: Optional[float] = None
    observation_until: Optional[float] = None
    observation_extensions: int = Field(0, ge=0)


class StrategyOverrides(BaseModel):
    selection_min_score: float = Field(30, ge=0, le=100)
    max_add_per_run: int = Field(5, ge=1, le=100)
    deletion_score_threshold: float = Field(40, ge=0, le=100)
    candidate_confirmations: int = Field(3, ge=2, le=6)
    confirmation_minutes: float = Field(30, ge=0, le=1440)
    capacity_trigger_percent: float = Field(90, gt=0, le=100)
    capacity_target_percent: float = Field(85, ge=0, lt=100)
    max_delete_per_run: int = Field(3, ge=1, le=100)
    max_delete_percent_day: float = Field(5, ge=0, le=100)
    max_release_percent_run: float = Field(4, ge=0, le=100)
    max_release_percent_day: float = Field(8, ge=0, le=100)
    max_release_gb_run: Optional[float] = Field(None, gt=0)
    max_release_gb_day: Optional[float] = Field(None, gt=0)
    cold_protection_minutes: float = Field(360, ge=0)
    demand_confirmations: int = Field(2, ge=1, le=3)

    @model_validator(mode="after")
    def validate_capacity_loop(self):
        if self.capacity_target_percent >= self.capacity_trigger_percent:
            raise ValueError("容量停止线必须低于触发线")
        return self


PROFILE_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "selection_min_score": 40, "max_add_per_run": 2, "deletion_score_threshold": 35,
        "candidate_confirmations": 4, "confirmation_minutes": 60,
        "capacity_trigger_percent": 90, "capacity_target_percent": 85,
        "max_delete_per_run": 2, "max_delete_percent_day": 3,
        "max_release_percent_run": 2, "max_release_percent_day": 4,
        "cold_protection_minutes": 720, "demand_confirmations": 2,
    },
    "balanced": {
        "selection_min_score": 30, "max_add_per_run": 5, "deletion_score_threshold": 40,
        "candidate_confirmations": 3, "confirmation_minutes": 30,
        "capacity_trigger_percent": 90, "capacity_target_percent": 85,
        "max_delete_per_run": 3, "max_delete_percent_day": 5,
        "max_release_percent_run": 4, "max_release_percent_day": 8,
        "cold_protection_minutes": 360, "demand_confirmations": 2,
    },
    "aggressive": {
        "selection_min_score": 22, "max_add_per_run": 8, "deletion_score_threshold": 48,
        "candidate_confirmations": 2, "confirmation_minutes": 15,
        "capacity_trigger_percent": 90, "capacity_target_percent": 85,
        "max_delete_per_run": 5, "max_delete_percent_day": 10,
        "max_release_percent_run": 8, "max_release_percent_day": 15,
        "cold_protection_minutes": 180, "demand_confirmations": 2,
    },
}


class StrategyConfig(BaseModel):
    profile: Profile = "balanced"
    overrides: StrategyOverrides = Field(default_factory=StrategyOverrides)

    @model_validator(mode="before")
    @classmethod
    def normalize_profile(cls, value):
        data = dict(value or {})
        profile = str(data.get("profile") or "balanced")
        expected = PROFILE_OVERRIDES.get(profile)
        supplied = data.get("overrides")
        if expected and supplied is None:
            data["overrides"] = expected
        elif expected:
            normalized = StrategyOverrides.model_validate(supplied).model_dump()
            expected_normalized = StrategyOverrides.model_validate(expected).model_dump()
            if normalized != expected_normalized:
                data["profile"] = "custom"
        return data


class HealthConfig(BaseModel):
    stalled_confirmations: int = Field(3, ge=2, le=10)
    stalled_window_minutes: float = Field(30, ge=10, le=1440)
    slow_after_hours: float = Field(6, ge=1, le=168)
    slow_speed_kbps: float = Field(128, ge=1)
    auto_repair: bool = True
    pause_after_failed_repair: bool = True


class TaskConfigV9(BaseModel):
    schema_version: Literal[9] = 9
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    revision: int = Field(1, ge=1)
    identity: IdentityConfig
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    goal: GoalConfig = Field(default_factory=GoalConfig)
    capacity: CapacityConfig = Field(default_factory=CapacityConfig)
    selection: SelectionConfig = Field(default_factory=SelectionConfig)
    deletion: DeletionConfig = Field(default_factory=DeletionConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)

    @model_validator(mode="after")
    def validate_deletion_safety(self):
        if self.deletion.enabled:
            if self.capacity.limit_gb is None:
                raise ValueError("启用自动删种时必须设置任务容量")
            if self.deletion.min_seed_hours is None:
                raise ValueError("启用自动删种时必须设置站点最低保种时间")
        return self

    def to_runtime(self) -> Dict[str, Any]:
        """转换为下载器执行层需要的扁平只读视图。"""
        override = self.strategy.overrides
        size = _join_range(self.selection.size_min_gb, self.selection.size_max_gb)
        pubtime = _join_range(self.selection.published_min_minutes, self.selection.published_max_minutes)
        return {
            "id": self.id,
            "name": self.identity.name,
            "enabled": self.identity.enabled,
            "notify": self.identity.notify,
            "site_id": self.identity.site_id,
            "downloader": self.identity.downloader,
            "save_path": self.identity.save_path,
            "tag": self.identity.tag,
            "brush_interval": self.schedule.brush_interval,
            "check_interval": self.schedule.check_interval,
            "cron": self.schedule.cron,
            "active_time_range": self.schedule.active_time_range,
            "site_ratio_control": self.goal.enabled,
            "site_ratio_target": self.goal.ratio_target,
            "site_ratio_reached_behavior": self.goal.reached_behavior,
            "disksize": self.capacity.limit_gb,
            "maxdlcount": self.capacity.max_downloads,
            "maxupspeed": self.capacity.upload_limit_kbps,
            "maxdlspeed": self.capacity.download_limit_kbps,
            "up_speed": self.capacity.torrent_upload_limit_kbps,
            "dl_speed": self.capacity.torrent_download_limit_kbps,
            "freeleech": "" if self.selection.promotion == "all" else self.selection.promotion,
            "hr": "yes" if self.selection.exclude_hr else "no",
            "site_hr_active": self.selection.site_hr_active,
            "except_subscribe": self.selection.exclude_subscriptions,
            "rss_support": self.selection.source == "rss",
            "size": size,
            "seeder": self.selection.seeder_range,
            "pubtime": pubtime,
            "timezone_offset": self.selection.timezone_offset,
            "include": self.selection.include,
            "exclude": self.selection.exclude,
            "smart_enabled": self.deletion.enabled,
            "smart_profile": self.strategy.profile,
            "smart_selection_enabled": self.selection.enabled,
            "smart_adaptive_enabled": True,
            "smart_selection_relax_filters": True,
            "smart_selection_min_score": override.selection_min_score,
            "smart_selection_max_add_per_run": override.max_add_per_run,
            "min_seed_time": self.deletion.min_seed_hours,
            "delete_except_tags": self.deletion.exclude_tags,
            "delete_files": self.deletion.delete_data,
            "invalid_seed_cleanup_enabled": self.deletion.invalid_tracker_cleanup,
            "invalid_seed_confirmations": self.deletion.invalid_tracker_confirmations,
            "smart_delete_paused": self.deletion.paused,
            "smart_shadow_started_at": self.deletion.observation_started_at,
            "smart_shadow_until": self.deletion.observation_until,
            "smart_shadow_extensions": self.deletion.observation_extensions,
            "smart_score_threshold": override.deletion_score_threshold,
            "smart_candidate_confirmations": override.candidate_confirmations,
            "smart_candidate_confirmation_minutes": override.confirmation_minutes,
            "smart_capacity_trigger_percent": override.capacity_trigger_percent,
            "smart_capacity_target_percent": override.capacity_target_percent,
            "smart_max_delete_per_run": override.max_delete_per_run,
            "smart_max_delete_percent_day": override.max_delete_percent_day,
            "smart_max_delete_capacity_percent_run": override.max_release_percent_run,
            "smart_max_delete_capacity_percent_day": override.max_release_percent_day,
            "smart_max_delete_gb_per_run": override.max_release_gb_run,
            "smart_max_delete_gb_per_day": override.max_release_gb_day,
            "smart_cold_inactive_minutes": override.cold_protection_minutes,
            "smart_demand_confirmations": override.demand_confirmations,
            "del_no_free": False,
        }


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _split_range(value: Any, *, single_is_min: bool = True) -> tuple[Optional[float], Optional[float]]:
    text = str(value or "").strip()
    if not text:
        return None, None
    parts = text.split("-", 1)
    first = _number(parts[0])
    if len(parts) == 1:
        return (first, None) if single_is_min else (None, first)
    return first, _number(parts[1])


def _join_range(minimum: Optional[float], maximum: Optional[float]) -> Optional[str]:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is None:
        return f"{minimum:g}"
    if minimum is None:
        return f"0-{maximum:g}"
    return f"{minimum:g}-{maximum:g}"


def migrate_v8_task(source: Mapping[str, Any], now: Optional[float] = None) -> TaskConfigV9:
    """把8.x扁平任务迁移为9.0模型；调用方负责保存不可变备份。"""
    if int(source.get("schema_version") or 0) == 9 and source.get("identity"):
        return TaskConfigV9.model_validate(source)
    timestamp = float(now or time.time())
    size_min, size_max = _split_range(source.get("size"), single_is_min=True)
    pub_min, pub_max = _split_range(source.get("pubtime"), single_is_min=True)
    legacy_condition_enabled = any(
        _number(source.get(key)) is not None
        for key in ("seed_time", "hr_seed_time", "seed_ratio", "seed_size", "download_time", "seed_avgspeed", "seed_inactivetime")
    )
    deletion_was_enabled = bool(source.get("smart_enabled") or source.get("proxy_delete") or legacy_condition_enabled)
    capacity = _number(source.get("disksize"))
    minimum_seed = _number(source.get("min_seed_time") or source.get("dynamic_min_seed_time"))
    deletion_enabled = bool(deletion_was_enabled and capacity and minimum_seed)
    return TaskConfigV9(
        id=str(source.get("id") or uuid.uuid4().hex),
        identity=IdentityConfig(
            name=str(source.get("name") or "刷流任务"),
            site_id=int(source.get("site_id") or 0),
            downloader=str(source.get("downloader") or ""),
            save_path=source.get("save_path"),
            tag=source.get("tag"),
            enabled=bool(source.get("enabled", True)),
            notify=bool(source.get("notify", True)),
        ),
        schedule=ScheduleConfig(
            brush_interval=int(source.get("brush_interval") or 10),
            check_interval=int(source.get("check_interval") or 5),
            cron=source.get("cron"),
            active_time_range=source.get("active_time_range"),
        ),
        goal=GoalConfig(
            enabled=bool(source.get("site_ratio_control", False)),
            ratio_target=_number(source.get("site_ratio_target")),
            reached_behavior=source.get("site_ratio_reached_behavior") or "continue",
        ),
        capacity=CapacityConfig(
            limit_gb=capacity,
            max_downloads=_number(source.get("maxdlcount")),
            upload_limit_kbps=_number(source.get("maxupspeed")),
            download_limit_kbps=_number(source.get("maxdlspeed")),
            torrent_upload_limit_kbps=_number(source.get("up_speed")),
            torrent_download_limit_kbps=_number(source.get("dl_speed")),
        ),
        selection=SelectionConfig(
            enabled=bool(source.get("smart_selection_enabled", True)),
            source="rss" if source.get("rss_support") else "page",
            promotion=source.get("freeleech") or "all",
            exclude_hr=source.get("hr", "yes") == "yes",
            site_hr_active=bool(source.get("site_hr_active", False)),
            exclude_subscriptions=bool(source.get("except_subscribe", True)),
            size_min_gb=size_min,
            size_max_gb=size_max,
            seeder_range=source.get("seeder"),
            published_min_minutes=pub_min,
            published_max_minutes=pub_max,
            timezone_offset=float(source.get("timezone_offset") or 0),
            include=source.get("include"),
            exclude=source.get("exclude"),
        ),
        deletion=DeletionConfig(
            enabled=deletion_enabled,
            min_seed_hours=minimum_seed,
            exclude_tags=source.get("delete_except_tags"),
            delete_data=bool(source.get("delete_files", True)),
            invalid_tracker_cleanup=bool(source.get("invalid_seed_cleanup_enabled", False)),
            invalid_tracker_confirmations=int(source.get("invalid_seed_confirmations") or 2),
            paused=bool(deletion_was_enabled and not deletion_enabled),
            observation_started_at=timestamp if deletion_enabled else None,
            observation_until=timestamp + 48 * 3600 if deletion_enabled else None,
        ),
        strategy=StrategyConfig(profile="balanced"),
    )


def migrate_task_rows_v9(
    rows: List[Mapping[str, Any]],
    backups: Optional[Mapping[str, Any]] = None,
    *,
    now: Optional[float] = None,
) -> tuple[List[dict], Dict[str, Any], bool]:
    timestamp = float(now or time.time())
    saved = dict(backups or {})
    result: List[dict] = []
    changed = False
    for source in rows:
        task = migrate_v8_task(source, now=timestamp)
        if int(source.get("schema_version") or 0) != 9:
            saved.setdefault(task.id, {"saved_at": timestamp, "config": dict(source)})
            changed = True
        result.append(task.model_dump(mode="json"))
    return result, saved, changed

import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_optional_positive_number(value):
    """把历史配置中的空值和 0 统一转换为未设置。"""
    if value is None or value == "":
        return None
    try:
        if float(value) == 0:
            return None
    except (TypeError, ValueError):
        return value
    return value


class BrushTaskPayload(BaseModel):
    """
    刷流任务新增与更新请求模型
    """

    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    notify: bool = True
    site_id: int = Field(..., gt=0)
    downloader: str = Field(..., min_length=1, max_length=80)
    brush_interval: int = Field(10, ge=1, le=1440)
    check_interval: int = Field(5, ge=1, le=1440)
    cron: Optional[str] = None
    active_time_range: Optional[str] = None
    site_ratio_control: bool = False
    site_ratio_target: Optional[float] = Field(None, gt=0)
    disksize: Optional[float] = Field(None, gt=0)
    maxupspeed: Optional[float] = Field(None, gt=0)
    maxdlspeed: Optional[float] = Field(None, gt=0)
    maxdlcount: Optional[int] = Field(None, gt=0)
    freeleech: Literal["", "free", "2xfree"] = "free"
    hr: Literal["yes", "no"] = "yes"
    include: Optional[str] = None
    exclude: Optional[str] = None
    size: Optional[str] = None
    seeder: Optional[str] = None
    timezone_offset: float = 0
    pubtime: Optional[str] = None
    seed_time: Optional[float] = Field(None, gt=0)
    hr_seed_time: Optional[float] = Field(None, gt=0)
    seed_ratio: Optional[float] = Field(None, gt=0)
    seed_size: Optional[float] = Field(None, gt=0)
    download_time: Optional[float] = Field(None, gt=0)
    seed_avgspeed: Optional[float] = Field(None, gt=0)
    seed_inactivetime: Optional[float] = Field(None, gt=0)
    min_seed_time: Optional[float] = Field(None, gt=0)
    min_inactivetime: Optional[float] = Field(None, gt=0)
    smart_enabled: bool = False
    smart_selection_enabled: bool = True
    smart_adaptive_enabled: bool = True
    smart_selection_relax_filters: bool = True
    smart_selection_min_score: float = Field(25, ge=0, le=100)
    smart_selection_max_add_per_run: int = Field(5, ge=1, le=100)
    smart_min_ratio: Optional[float] = Field(0, ge=0)
    smart_min_uploaded: Optional[float] = Field(None, ge=0)
    smart_ratio_weight: float = Field(18, ge=0, le=40)
    smart_cold_inactive_minutes: float = Field(360, ge=0)
    smart_protect_active_demand: bool = True
    invalid_seed_cleanup_enabled: bool = False
    invalid_seed_confirmations: int = Field(2, ge=1, le=5)
    smart_score_threshold: float = Field(40, ge=0, le=100)
    smart_score_margin: float = Field(0, ge=0, le=100)
    smart_max_delete_per_run: int = Field(3, ge=1, le=100)
    smart_max_delete_percent_day: float = Field(5, ge=0, le=100)
    smart_allow_proactive_delete: bool = False
    smart_required_conditions: bool = False
    delete_condition_mode: Literal["any", "all"] = "any"
    dynamic_require_conditions: bool = False
    dynamic_sort_mode: Literal["smart", "oldest", "inactive", "low_speed", "largest"] = "smart"
    delete_dry_run: bool = True
    delete_files: bool = True
    delete_min_size: Optional[float] = Field(None, gt=0)
    delete_max_size: Optional[float] = Field(None, gt=0)
    delete_size_range: Optional[str] = None
    up_speed: Optional[float] = Field(None, gt=0)
    dl_speed: Optional[float] = Field(None, gt=0)
    auto_archive_days: Optional[float] = Field(None, gt=0)
    save_path: Optional[str] = None
    delete_except_tags: Optional[str] = None
    except_subscribe: bool = True
    proxy_delete: bool = False
    del_no_free: bool = False
    qb_category: Optional[str] = None
    site_hr_active: bool = False
    site_skip_tips: bool = False
    rss_support: bool = False
    tag: Optional[str] = None

    @field_validator(
        "disksize",
        "maxupspeed",
        "maxdlspeed",
        "maxdlcount",
        "site_ratio_target",
        "seed_time",
        "hr_seed_time",
        "seed_ratio",
        "seed_size",
        "download_time",
        "seed_avgspeed",
        "seed_inactivetime",
        "min_seed_time",
        "min_inactivetime",
        "smart_min_uploaded",
        "delete_min_size",
        "delete_max_size",
        "up_speed",
        "dl_speed",
        "auto_archive_days",
        mode="before",
    )
    @classmethod
    def normalize_optional_positive_number(cls, value):
        """兼容旧版用 0 表示未配置的可选正数配置。"""
        return _normalize_optional_positive_number(value)

    @field_validator("name", "downloader")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """清理必填文本并拒绝纯空白内容"""
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("字段不能为空")
        return cleaned

    @field_validator(
        "cron",
        "active_time_range",
        "include",
        "exclude",
        "size",
        "seeder",
        "pubtime",
        "delete_size_range",
        "save_path",
        "delete_except_tags",
        "qb_category",
        "tag",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        """把空白可选文本统一转换为 None"""
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, value: Optional[str]) -> Optional[str]:
        """qBittorrent 标签不允许包含逗号"""
        if value and "," in value:
            raise ValueError("下载器标签不能包含逗号")
        return value

    @field_validator("size", "seeder", "pubtime", "delete_size_range")
    @classmethod
    def validate_number_range(cls, value: Optional[str]) -> Optional[str]:
        """校验单值或数字范围配置"""
        if value and not re.fullmatch(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?", value):
            raise ValueError("请输入数字或数字范围，例如 10 或 10-80")
        return value

    @field_validator("active_time_range")
    @classmethod
    def validate_active_time_range(cls, value: Optional[str]) -> Optional[str]:
        """校验每日开启时间段格式并允许跨越午夜"""
        if not value:
            return None
        if not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", value):
            raise ValueError("开启时间段格式应为 HH:MM-HH:MM")
        start, end = value.split("-", 1)
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
        return value

    @field_validator("include", "exclude")
    @classmethod
    def validate_regex(cls, value: Optional[str]) -> Optional[str]:
        """提前校验选种正则表达式"""
        if value:
            re.compile(value)
        return value

    @model_validator(mode="after")
    def validate_site_ratio_control(self):
        """启用站点分享率控制时要求同时配置有效目标值。"""
        if self.site_ratio_control and self.site_ratio_target is None:
            raise ValueError("启用站点分享率控制时必须设置目标分享率")
        return self

    @model_validator(mode="after")
    def validate_smart_policy(self):
        """智能删种必须明确填入当前站点的最低保种时长。"""
        if self.smart_enabled and self.min_seed_time is None:
            raise ValueError("启用智能删种时必须设置当前站点的最低保种时长")
        return self

    @model_validator(mode="after")
    def validate_dynamic_delete_limits(self):
        """动态删种使用明确的最低/最高容量，并兼容旧版区间字符串。"""
        if self.delete_size_range and (self.delete_min_size is None or self.delete_max_size is None):
            limits = [float(item) for item in self.delete_size_range.split("-")]
            self.delete_min_size = limits[0]
            self.delete_max_size = limits[1] if len(limits) > 1 else limits[0]
        if self.delete_min_size is not None or self.delete_max_size is not None:
            if self.delete_min_size is None or self.delete_max_size is None:
                raise ValueError("动态删种必须同时设置最低和最高阈值")
            if self.delete_min_size > self.delete_max_size:
                raise ValueError("动态删种最低阈值不能大于最高阈值")
            self.delete_size_range = f"{self.delete_min_size:g}-{self.delete_max_size:g}"
        if self.proxy_delete and not self.delete_size_range:
            raise ValueError("启用动态删种时必须设置最低和最高阈值")
        return self


class BrushTaskStatePayload(BaseModel):
    """
    刷流任务启停请求模型
    """

    enabled: bool


class BrushFlowSettingsPayload(BaseModel):
    """
    刷流插件全局设置请求模型
    """

    enabled: bool = True
    show_sidebar_nav: bool = True
    global_disksize: Optional[float] = Field(None, gt=0)
    global_maxdlcount: Optional[int] = Field(None, gt=0)
    global_maxupspeed: Optional[float] = Field(None, gt=0)
    global_maxdlspeed: Optional[float] = Field(None, gt=0)
    global_proxy_delete: bool = False
    global_delete_min_size: Optional[float] = Field(None, gt=0)
    global_delete_max_size: Optional[float] = Field(None, gt=0)
    global_delete_size_range: Optional[str] = None
    signin_enabled: bool = False
    signin_notify: bool = True
    signin_cron: Optional[str] = "17 7 * * *"
    signin_sites: List[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def clear_global_delete_size_range_when_disabled(cls, data):
        """关闭全局动态删种时忽略隐藏阈值，确保无效草稿不会阻止保存。"""
        if not isinstance(data, dict):
            return data
        enabled = data.get("global_proxy_delete", False)
        if enabled not in (False, None, 0, "", "0", "false", "False"):
            return data
        normalized = dict(data)
        normalized["global_delete_size_range"] = None
        normalized["global_delete_min_size"] = None
        normalized["global_delete_max_size"] = None
        return normalized

    @field_validator(
        "global_disksize",
        "global_maxdlcount",
        "global_maxupspeed",
        "global_maxdlspeed",
        "global_delete_min_size",
        "global_delete_max_size",
        mode="before",
    )
    @classmethod
    def normalize_optional_positive_number(cls, value):
        """兼容全局限额中用于表示不限的空值和 0。"""
        return _normalize_optional_positive_number(value)

    @field_validator("global_delete_size_range", mode="before")
    @classmethod
    def normalize_global_delete_size_range(cls, value):
        """清理全局动态删种阈值中的空白值。"""
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("signin_cron", mode="before")
    @classmethod
    def normalize_signin_cron(cls, value):
        """清理签到 CRON；留空时使用每天 07:17 的低频默认计划。"""
        if value is None:
            return "17 7 * * *"
        cleaned = str(value).strip()
        return cleaned or "17 7 * * *"

    @field_validator("signin_sites", mode="before")
    @classmethod
    def normalize_signin_sites(cls, value):
        """兼容旧配置中以字符串保存的站点 ID 列表。"""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if not isinstance(value, (list, tuple, set)):
            return []
        result = []
        for item in value:
            try:
                site_id = int(item)
            except (TypeError, ValueError):
                continue
            if site_id > 0 and site_id not in result:
                result.append(site_id)
        return result

    @field_validator("global_delete_size_range")
    @classmethod
    def validate_global_delete_size_range(cls, value: Optional[str]) -> Optional[str]:
        """校验全局动态删种的单值或区间阈值。"""
        if value and not re.fullmatch(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?", value):
            raise ValueError("请输入数字或数字范围，例如 100 或 50-100")
        if value:
            limits = [float(item) for item in value.split("-")]
            if any(item <= 0 for item in limits) or (len(limits) > 1 and limits[0] >= limits[1]):
                raise ValueError("动态删种区间下限必须小于上限")
        return value

    @model_validator(mode="after")
    def validate_global_dynamic_delete(self):
        """启用全局动态删种时要求配置有效体积阈值。"""
        if self.global_delete_size_range and (
            self.global_delete_min_size is None or self.global_delete_max_size is None
        ):
            limits = [float(item) for item in self.global_delete_size_range.split("-")]
            self.global_delete_min_size = limits[0]
            self.global_delete_max_size = limits[1] if len(limits) > 1 else limits[0]
        if self.global_delete_min_size is not None or self.global_delete_max_size is not None:
            if self.global_delete_min_size is None or self.global_delete_max_size is None:
                raise ValueError("全局动态删种必须同时设置最低和最高阈值")
            if self.global_delete_min_size > self.global_delete_max_size:
                raise ValueError("全局动态删种最低阈值不能大于最高阈值")
            self.global_delete_size_range = (
                f"{self.global_delete_min_size:g}-{self.global_delete_max_size:g}"
            )
        if self.global_proxy_delete and not self.global_delete_size_range:
            raise ValueError("启用全局动态删种时必须设置最低和最高阈值")
        return self

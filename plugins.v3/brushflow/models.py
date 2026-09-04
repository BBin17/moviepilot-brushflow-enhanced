"""BrushFlow 9.0 插件级请求模型。

任务配置由 ``TaskConfigV9`` 负责；这里不再保留旧条件、动态删种或兼容引擎字段。
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def _positive_or_none(value):
    return None if value in (None, "", 0, "0") else value


class BrushFlowSettingsPayload(BaseModel):
    enabled: bool = True
    show_sidebar_nav: bool = True
    global_disksize: Optional[float] = Field(None, gt=0)
    global_maxdlcount: Optional[int] = Field(None, gt=0)
    global_maxupspeed: Optional[float] = Field(None, gt=0)
    global_maxdlspeed: Optional[float] = Field(None, gt=0)
    signin_enabled: bool = False
    signin_notify: bool = True
    signin_cron: Optional[str] = "17 7 * * *"
    signin_sites: List[int] = Field(default_factory=list)

    @field_validator("global_disksize", "global_maxdlcount", "global_maxupspeed", "global_maxdlspeed", mode="before")
    @classmethod
    def normalize_limits(cls, value):
        return _positive_or_none(value)

    @field_validator("signin_cron", mode="before")
    @classmethod
    def normalize_signin_cron(cls, value):
        return str(value or "17 7 * * *").strip() or "17 7 * * *"

    @field_validator("signin_sites", mode="before")
    @classmethod
    def normalize_signin_sites(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = value.split(",")
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

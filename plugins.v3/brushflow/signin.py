"""站点自动签到的安全通用实现。

大多数 NexusPHP 站点访问 ``attendance.php`` 即可完成签到。本模块只负责
通用签到链路：读取 MoviePilot 已保存的 Cookie/UA，串行访问签到页，判断
登录状态和常见的“已签到”提示，并把失败留给下一次调度重试。需要验证码、
答题或专用 API 的站点不会被强行提交，避免误签到和错误消耗站点机会。
"""

import re
from typing import Any, Dict, Tuple
from urllib.parse import urljoin, urlparse

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import RequestUtils


SIGNED_MARKERS = (
    "已签到",
    "今日已签到",
    "今天已经签过",
    "签到已得",
    "签到成功",
    "already signed",
    "signed today",
)
LOGGED_IN_MARKERS = (
    "logout.php",
    "logout",
    "登出",
    "退出登录",
    "退出",
)
LOGIN_FORM_MARKERS = (
    'name="username"',
    "name='username'",
    "login.php?",
    "登录密码",
    "登入密码",
)
CHALLENGE_MARKERS = (
    "cloudflare",
    "cf-chl-",
    "just a moment",
    "验证您是真人",
    "checking your browser",
)


def _text(value: Any) -> str:
    return str(value or "")


def _looks_logged_out(page_source: str) -> bool:
    """只在登录表单特征明显且没有退出标志时判定 Cookie 失效。"""
    normalized = page_source.lower()
    if any(marker.lower() in normalized for marker in LOGGED_IN_MARKERS):
        return False
    return any(marker.lower() in normalized for marker in LOGIN_FORM_MARKERS)


def _is_signed(page_source: str) -> bool:
    normalized = page_source.lower()
    return any(marker.lower() in normalized for marker in SIGNED_MARKERS)


def _is_challenge(page_source: str) -> bool:
    normalized = page_source.lower()
    return any(marker.lower() in normalized for marker in CHALLENGE_MARKERS)


def _request_kwargs(site_info: Dict[str, Any]) -> Dict[str, Any]:
    """构造不包含敏感信息的请求参数。"""
    timeout = site_info.get("timeout")
    try:
        timeout = max(int(float(timeout)), 5) if timeout else 20
    except (TypeError, ValueError):
        timeout = 20
    return {
        "cookies": site_info.get("cookie"),
        "ua": site_info.get("ua"),
        "proxies": settings.PROXY if site_info.get("proxy") else None,
        "timeout": timeout,
    }


def _request_get(url: str, site_info: Dict[str, Any]):
    """兼容不同 MoviePilot V3 网络 SDK 的 timeout 参数。"""
    kwargs = _request_kwargs(site_info)
    try:
        return RequestUtils(**kwargs).get_res(url=url)
    except TypeError:
        kwargs.pop("timeout", None)
        return RequestUtils(**kwargs).get_res(url=url)


def _render_get(url: str, site_info: Dict[str, Any]) -> str:
    """按需使用宿主浏览器仿真，导入失败时返回空字符串。"""
    try:
        from app.helper.browser import PlaywrightHelper

        timeout = _request_kwargs(site_info)["timeout"]
        page_source = PlaywrightHelper().get_page_source(
            url=url,
            cookies=site_info.get("cookie"),
            ua=site_info.get("ua"),
            proxies=getattr(settings, "PROXY_SERVER", None) if site_info.get("proxy") else None,
            timeout=timeout,
        )
        return _text(page_source)
    except Exception as err:
        logger.warning(f"站点 [{site_info.get('name')}] 浏览器仿真签到不可用：{err}")
        return ""


def signin_site(site_info: Dict[str, Any]) -> Tuple[bool, str]:
    """对单个站点执行一次安全通用签到。"""
    site_name = _text(site_info.get("name")) or "未知站点"
    site_url = _text(site_info.get("url")).strip()
    cookie = _text(site_info.get("cookie")).strip()
    if not site_url:
        domain = _text(site_info.get("domain")).strip()
        site_url = f"https://{domain}" if domain else ""
    if not site_url:
        return False, "签到失败，站点地址为空"
    if not cookie:
        return False, "签到失败，站点 Cookie 为空"

    parsed = urlparse(site_url)
    if not parsed.scheme or not parsed.netloc:
        return False, "签到失败，站点地址无效"
    checkin_url = site_url if "attendance.php" in parsed.path.lower() else urljoin(
        site_url.rstrip("/") + "/", "attendance.php"
    )

    try:
        logger.info(f"开始站点签到：{site_name}")
        page_source = _render_get(checkin_url, site_info) if site_info.get("render") else ""
        response = None
        if not page_source:
            response = _request_get(checkin_url, site_info)
            if response is None:
                return False, "签到失败，无法访问签到页面"
            page_source = _text(getattr(response, "text", ""))

        if _is_challenge(page_source):
            return False, "签到失败，站点需要浏览器验证"
        if _looks_logged_out(page_source):
            return False, "签到失败，Cookie 已失效"
        if response is not None and getattr(response, "status_code", 200) in {401, 403}:
            return False, f"签到失败，站点返回状态码 {response.status_code}"
        if _is_signed(page_source):
            return True, "今日已签到"

        status_code = getattr(response, "status_code", 200) if response is not None else 200
        if 200 <= int(status_code) < 400:
            return True, "签到成功"
        return False, f"签到失败，站点返回状态码 {status_code}"
    except Exception as err:
        logger.warning(f"站点 [{site_name}] 签到失败：{err}")
        return False, f"签到失败：{err}"


def success_message(message: str) -> bool:
    """判断一条结果是否已经完成当天签到。"""
    normalized = _text(message).lower()
    return bool(
        re.search(r"签到成功|已签到|already signed|signed today", normalized, re.IGNORECASE)
    )

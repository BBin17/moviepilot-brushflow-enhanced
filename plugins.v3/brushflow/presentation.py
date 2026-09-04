"""BrushFlow 9.0 展示服务：统一健康结论与推荐操作。"""

from __future__ import annotations

from typing import Any, Mapping, Optional


QUOTA_REASON_LABELS = {
    "byte_cap": "本轮或每日释放容量额度已用尽",
    "daily_count_cap": "每日删除数量额度已用尽",
    "run_count_cap": "本轮删除数量额度已用尽",
}


def deletion_quota_message(reason_codes: list[str] | tuple[str, ...]) -> str:
    """把命中的删除额度守门原因转成可直接展示的精确说明。"""
    labels = [QUOTA_REASON_LABELS[code] for code in QUOTA_REASON_LABELS if code in reason_codes]
    if not labels:
        return ""
    return "、".join(labels)


def build_health_summary(
    *,
    runtime_error: Optional[str],
    configuration_issue: bool = False,
    severe_capacity: bool,
    capacity_percent: Optional[float],
    download: Mapping[str, Any],
    mode: str,
    shadow_remaining_seconds: float,
    capacity_pressure: bool,
    readiness_message: str,
    task_enabled: bool,
) -> dict:
    """按固定优先级返回白话结论和可执行动作。"""
    actions = []
    stalled_or_slow = int(download.get("stalled_count") or 0) + int(download.get("slow_count") or 0)
    download_issue_count = stalled_or_slow + int(download.get("queued_count") or 0) + int(download.get("error_count") or 0)
    if runtime_error:
        health = {"level": "error", "title": "任务运行异常", "message": str(runtime_error), "status": "runtime_error"}
        actions.append(_action("run_check", "重新检查", "error", "将立即检查下载器中的种子状态，确认继续吗？"))
    elif configuration_issue:
        health = {
            "level": "warning",
            "title": "需要完善删种设置",
            "status": "configuration_required",
            "message": "升级前曾启用删种，但任务容量或站点最低保种时间不完整；自动删种已安全暂停。",
        }
        actions.append(
            _action(
                "open_editor",
                "完善容量与保种时间",
                "warning",
                "将打开任务向导；填写容量和站点最低保种时间并保存后，任务会进入48小时安全观察。",
            )
        )
    elif severe_capacity:
        health = {
            "level": "error", "title": "容量严重超限", "status": "severe_capacity",
            "message": f"当前已使用任务上限的 {float(capacity_percent or 0):.0f}%，正在优先安全释放低价值空间。",
        }
        actions.append(_action("run_check", "立即检查可清理种子", "error", "将立即检查低价值候选；硬安全线仍然生效。确认继续吗？"))
    elif download_issue_count:
        health = {
            "level": "warning", "title": "部分下载需要关注", "status": "download_issue",
            "message": f"发现 {download_issue_count} 个卡住、低速、排队或报错的下载，未完成数据不会被自动删除。",
        }
        actions.append(
            _action(
                "retry_stalled" if stalled_or_slow else "run_check",
                "安全修复异常下载" if stalled_or_slow else "重新检查下载状态",
                "warning",
                "将重新汇报Tracker并恢复异常任务一次；不会删除未完成数据。确认继续吗？"
                if stalled_or_slow else "将立即刷新下载器中的排队和错误状态，确认继续吗？",
            )
        )
    elif mode == "shadow":
        hours = max(int(float(shadow_remaining_seconds or 0) // 3600), 1)
        health = {
            "level": "info", "title": "正在安全观察（影子期）", "status": "observation",
            "message": f"插件只记录删种计划，不会实际删除；剩余约 {hours} 小时。",
        }
        actions.extend(
            [
                _action("activate_deletion", "提前启用自动删种", "primary", "将提前结束安全观察并启用自动删种；所有硬安全线仍然生效。确认继续吗？"),
                _action("extend_observation", "再观察24小时", "secondary", "将安全观察期延长24小时，期间仍不会实际删种。确认继续吗？"),
            ]
        )
    elif capacity_pressure:
        health = {"level": "warning", "title": "容量高于目标", "message": readiness_message, "status": "capacity_pressure"}
        if mode == "paused":
            actions.append(_action("resume_deletion", "恢复自动清理", "warning", "将恢复自动删种；插件仍会先检查所有硬安全线。确认继续吗？"))
    elif not task_enabled:
        health = {
            "level": "info", "title": "任务已暂停", "status": "task_paused",
            "message": "自动选种和检查已停止，现有下载和数据不会被修改。",
        }
        actions.append(_action("resume_task", "恢复任务", "primary", "恢复后将重新注册自动选种和检查计划，确认继续吗？"))
    else:
        health = {
            "level": "success", "title": "运行正常", "status": "healthy",
            "message": "容量和下载状态正常，插件会按计划继续选种与检查。",
        }
    return {"health": health, "recommended_actions": actions, "download_issue_count": download_issue_count}


def _action(code: str, label: str, tone: str, confirm: str) -> dict:
    return {"code": code, "label": label, "tone": tone, "confirm": confirm, "enabled": True}

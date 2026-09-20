"""One explainable cleanup chain for automatic and explicitly previewed actions.

Planning consumes an immutable evidence snapshot. Only scheduled checks append
evidence; previews do not train, confirm, repair or activate an observation. The
executor revalidates the frozen set, journals each request and confirms removal.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
import math
import time
import uuid

from .decision import (
    DecisionResult, SmartPolicy, capacity_recovery_state, deletion_budget,
    manual_cleanup_policy, select_deletions,
)
from .downloaders import DownloaderUnavailable
from .learning import feature_key, learning_summary, predict_yield, recent_yield_metrics, update_learning_state
from .operations import OperationError, TaskService, UNRESOLVED_ITEMS


GIB = 1024**3
PREVIEW_TTL = 300


def number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def policy_for_document(document) -> SmartPolicy:
    overrides = document.strategy.overrides
    return SmartPolicy(
        profile=document.strategy.profile, min_seed_time_hours=document.deletion.min_seed_hours or 0,
        smart_cold_inactive_minutes=overrides.cold_protection_minutes,
        demand_confirmations=overrides.demand_confirmations,
        low_value_confirmations=overrides.candidate_confirmations,
        low_value_span_minutes=overrides.confirmation_minutes,
        score_threshold=overrides.deletion_score_threshold,
        ratio_target=document.goal.ratio_target or 2, ratio_weight=5,
        capacity_trigger_percent=overrides.capacity_trigger_percent,
        capacity_target_percent=overrides.capacity_target_percent,
        max_delete_per_run=overrides.max_delete_per_run,
        max_delete_percent_day=overrides.max_delete_percent_day,
        max_delete_capacity_percent_run=overrides.max_release_percent_run,
        max_delete_capacity_percent_day=overrides.max_release_percent_day,
        max_delete_gb_per_run=overrides.max_release_gb_run or 0,
        max_delete_gb_per_day=overrides.max_release_gb_day or 0,
        excluded_tags=tuple(tag.strip() for tag in (document.deletion.exclude_tags or "").split(",") if tag.strip()),
    )


def hard_safety_reasons(observation: dict, policy: SmartPolicy) -> list[str]:
    """Missing critical activity/completion data fails closed at the I/O boundary."""
    required = ("total_size", "completed", "uploaded", "upload_speed", "active_peers", "seeding_time")
    if any(number(observation.get(key), -1) < 0 for key in required):
        return ["safety_data_unknown"]
    reasons = []
    if str(observation.get("downloader_state") or "").lower().startswith("checking") or str(observation.get("downloader_state") or "").lower() in {"error", "missingfiles"}:
        reasons.append("downloader_not_ready")
    if number(observation["total_size"]) <= 0 or number(observation["completed"]) < number(observation["total_size"]):
        reasons.append("incomplete")
    if observation.get("hit_and_run"):
        reasons.append("hit_and_run")
    if policy.min_seed_time_hours <= 0:
        reasons.append("missing_min_seed_time")
    elif number(observation["seeding_time"]) < policy.min_seed_time_hours * 3600:
        reasons.append("min_seed_time")
    tags = observation.get("tags") or []
    tags = tags.split(",") if isinstance(tags, str) else tags
    if set(policy.excluded_tags).intersection(str(tag).strip() for tag in tags):
        reasons.append("excluded_tag")
    if number(observation["upload_speed"]) > 0 or number(observation.get("upload_delta_since_check")) > 0:
        reasons.append("real_upload")
    if number(observation["active_peers"]) > 0:
        reasons.append("active_connection")
    if number(observation.get("leechers")) > 0 and number(observation.get("demand_confirmations")) >= policy.demand_confirmations:
        reasons.append("trusted_active_demand")
    return reasons


def aggregate_decisions(evaluated, records) -> dict:
    """Compute unique totals on the complete set before trimming any UI page."""
    groups = {"candidate": {}, "protected": {}}
    blockers = defaultdict(dict)
    by_hash = {row.torrent_hash: row for row in evaluated}
    for torrent_hash, result in by_hash.items():
        record = records.get(torrent_hash, {})
        size = number(record.get("size", record.get("total_size")))
        groups["candidate" if result.eligible else "protected"][torrent_hash] = size
        if not result.eligible:
            for reason in result.reason_codes:
                blockers[reason][torrent_hash] = size
    return {
        **{f"{name}_count": len(rows) for name, rows in groups.items()},
        **{f"{name}_bytes": sum(rows.values()) for name, rows in groups.items()},
        "blockers": [{"code": code, "count": len(rows), "bytes": sum(rows.values())}
                     for code, rows in sorted(blockers.items(), key=lambda item: (-len(item[1]), item[0]))],
    }


class DeletionService:
    def __init__(self, *, repository, operations: TaskService, adapter, document, managed_tag=None, clock=time.time, sleep=time.sleep):
        self.repository = repository
        self.operations = operations
        self.adapter = adapter
        self.document = document
        self.task_id = document.id
        self.policy = policy_for_document(document)
        self.clock = clock
        self.sleep = sleep
        self.managed_tag = managed_tag or document.identity.tag

    def read(self, name, default=None):
        return deepcopy(self.repository.get(self.task_id, name, default))

    def write(self, name, value):
        self.repository.save(self.task_id, name, deepcopy(value))

    def audit(self, row):
        self.repository.append_bounded(self.task_id, "decision_audit", {"at": self.clock(), **row}, 500)

    def observations(self, records, snapshot, *, include_current=False):
        now = self.clock()
        history_by_hash = defaultdict(list)
        for row in self.read("smart_history", []):
            if 0 <= now - number(row.get("at")) <= 30 * 86400:
                history_by_hash[str(row.get("hash"))].append(row)
        snapshots_by_hash = defaultdict(list)
        learning = self.read("learning_state", {})
        for row in learning.get("snapshots", []):
            snapshots_by_hash[str(row.get("hash"))].append(row)
        pending = self.operations.pending_hashes(self.task_id)
        gap_limit = max(3600, self.document.schedule.check_interval * 120)
        result = []
        for torrent_hash, record in records.items():
            if record.get("deleted") or torrent_hash not in snapshot:
                continue
            info = deepcopy(snapshot[torrent_hash])
            history = sorted(history_by_hash[torrent_hash], key=lambda row: number(row.get("at")), reverse=True)
            previous = history[0] if history else {}
            info.update({"title": record.get("title") or info.get("title"), "size": info.get("total_size"),
                         "hit_and_run": bool(record.get("hit_and_run") or self.document.selection.site_hr_active),
                         "downloaded": info.get("completed"),
                         "progress": number(info.get("completed")) / number(info.get("total_size"), 1) * 100 if number(info.get("total_size")) > 0 else 0})
            info["upload_delta_since_check"] = max(number(info.get("uploaded")) - number(previous.get("uploaded"), number(info.get("uploaded"))), 0)
            demands = [number(info.get("leechers")) > 0] if info.get("leechers") is not None else []
            # Tracker evidence older than the continuity window is not reused.
            demands.extend(number(row.get("leechers")) > 0 for row in history
                           if row.get("leechers") is not None and now - number(row.get("at")) <= gap_limit)
            info["demand_confirmations"] = sum(demands[:3])
            lows, newer_at = [], now
            for row in history:
                at = number(row.get("at"))
                if not row.get("low_value") or newer_at - at > gap_limit:
                    break
                if lows and number(lows[-1].get("at")) - at < 10:
                    continue
                lows.append(row)
                newer_at = at
            add_current = include_current and (not history or now - number(previous.get("at")) >= 10)
            info["low_value_confirmations"] = len(lows) + int(add_current)
            newest = now if add_current else number(lows[0].get("at")) if lows else now
            since = number(lows[-1].get("at")) if lows else now
            # Preserve the continuous run anchor when compacting raw checks.
            # Keeping only N recent rows otherwise makes a 30-minute window
            # impossible to reach when users check every minute.
            if lows and previous.get("low_value_since") is not None:
                anchor = number(previous.get("low_value_since"), newest)
                if 0 <= anchor <= number(previous.get("at")):
                    since = anchor
                    info["low_value_confirmations"] = max(len(lows), int(number(previous.get("low_value_count")))) + int(add_current)
            info["low_value_span_minutes"] = max(newest - since, 0) / 60
            info.update(recent_yield_metrics(learning, torrent_hash, uploaded=number(info.get("uploaded")),
                        size=number(info.get("size")), now=now, snapshots_by_hash=snapshots_by_hash))
            learned = predict_yield(learning, record)
            info["learned_potential"] = learned["score"] / 25 * 15 * learned["confidence"]
            info["pending_confirmation"] = torrent_hash in pending
            tags = info.get("tags") or []
            tags = [tag.strip() for tag in tags.split(",")] if isinstance(tags, str) else tags
            info["management_tag_removed"] = bool(self.managed_tag and self.managed_tag not in tags and "刷流" not in tags)
            result.append(info)
        return result

    def plan(self, *, relax_limits=False, include_current=False, snapshot=None, manual=False):
        now = self.clock()
        records = self.read("torrents", {})
        snapshot = self.adapter.snapshot() if snapshot is None else snapshot
        observations = self.observations(records, snapshot, include_current=include_current)
        # Full logical task occupancy, including uncompleted commitments. Missing
        # downloader rows are retained until the normal reconciliation step.
        current = sum(number(row.get("size", row.get("total_size"))) for row in records.values() if not row.get("deleted"))
        capacity = number(self.document.capacity.limit_gb) * GIB
        recovery = capacity_recovery_state(current, capacity, self.policy, previous=self.read("capacity_recovery", {}), now=now)
        policy = manual_cleanup_policy(self.policy) if manual and relax_limits else self.policy
        if manual:
            policy = replace(policy, max_delete_per_run=min(10, policy.max_delete_per_run),
                             max_delete_capacity_percent_run=min(25, policy.max_delete_capacity_percent_run or 25))
        ledger = [row for row in self.read("smart_deletions", [])
                  if 0 <= now - number(row.get("at")) < 86400 and row.get("status") not in {"failed", "skipped"}]
        budget = deletion_budget(policy, active_count=len(observations), capacity=capacity or current,
                                 deleted_count=0 if relax_limits and manual else len(ledger),
                                 deleted_bytes=0 if relax_limits and manual else sum(number(row.get("size")) for row in ledger))
        blocked = []
        for observation in observations:
            reasons = hard_safety_reasons(observation, self.policy)
            if observation["pending_confirmation"]:
                reasons.append("previous_request_unconfirmed")
            if observation["management_tag_removed"]:
                reasons.append("management_tag_removed")
            if reasons:
                blocked.append(DecisionResult(observation["hash"], "blocked", 100, tuple(reasons)))
        # Blocked seeds still count toward the denominator. Their safety flags
        # keep them unselectable; insert placeholder H&R solely in this evaluation.
        blocked_hashes = {row.torrent_hash for row in blocked}
        guarded = [dict(row, hit_and_run=True) if row["hash"] in blocked_hashes else row for row in observations]
        selection = select_deletions(
            guarded, policy, current_size=current, disk_limit=capacity or None,
            deleted_today=0 if relax_limits and manual else len(ledger),
            deleted_today_bytes=0 if relax_limits and manual else sum(number(row.get("size")) for row in ledger),
            recovery_active=recovery["active"],
        )
        override = {row.torrent_hash: row for row in blocked}
        selection = replace(selection, evaluated=tuple(override.get(row.torrent_hash, row) for row in selection.evaluated))
        gating = []
        if not self.document.deletion.enabled:
            gating.append("deletion_disabled")
        if self.document.deletion.paused:
            gating.append("deletion_paused")
        if capacity <= 0 or self.policy.min_seed_time_hours <= 0:
            gating.append("configuration_required")
        if number(self.document.deletion.observation_until) > now and not (manual and relax_limits):
            gating.append("observation")
        observation_map = {row["hash"]: row for row in observations}
        items = [{"hash": row.torrent_hash, "title": observation_map[row.torrent_hash].get("title"),
                  "size": number(observation_map[row.torrent_hash].get("total_size")),
                  "uploaded": number(observation_map[row.torrent_hash].get("uploaded")),
                  "score": row.score, "reason_codes": list(row.reason_codes), "contributions": dict(row.contributions),
                  "delete_data": self.document.deletion.delete_data, "state": "pending"}
                 for row in selection.selected]
        return {"selection": selection, "observations": observations, "records": records, "recovery": recovery,
                "items": items, "gating": gating, "aggregate": aggregate_decisions(selection.evaluated, observation_map),
                "ledger": ledger, "budget": budget}

    def preview(self, *, relax_limits=False) -> dict:
        plan = self.plan(relax_limits=relax_limits, manual=True)
        now = self.clock()
        result = {
            "preview_id": uuid.uuid4().hex, "task_id": self.task_id, "revision": self.document.revision,
            "created_at": now, "expires_at": now + PREVIEW_TTL, "relax_limits": bool(relax_limits),
            "delete_data": self.document.deletion.delete_data,
            "items": plan["items"], "blocked_reasons": plan["gating"], "allowed": not plan["gating"] and bool(plan["items"]),
            "current_bytes": plan["recovery"]["current_bytes"], "target_bytes": plan["recovery"]["target_bytes"],
            "expected_task_bytes_removed": sum(row["size"] for row in plan["items"]),
            "estimated_released_bytes": sum(row["size"] for row in plan["items"] if row["delete_data"]),
            "aggregate": plan["aggregate"], "reason_codes": list(plan["selection"].reason_codes),
            "limits": {"max_count": min(10, plan["budget"]["run_count_cap"]),
                       "max_bytes": min(number(self.document.capacity.limit_gb) * GIB * .25, plan["budget"]["run_byte_cap"] or math.inf),
                       "remaining_24h_count": plan["budget"]["remaining_daily_count"],
                       "remaining_24h_bytes": plan["budget"]["remaining_daily_bytes"]},
        }
        previews = [row for row in self.read("cleanup_previews", []) if row["expires_at"] > now]
        # Storing this token is the only preview side effect. No training,
        # confirmation evidence, operation, downloader mutation or audit deletion.
        self.write("cleanup_previews", (previews + [result])[-20:])
        return result

    def validate_preview(self, payload) -> dict:
        preview = next((row for row in self.read("cleanup_previews", []) if row["preview_id"] == payload.preview_id), None)
        if preview is None or preview["expires_at"] <= self.clock():
            raise OperationError("preview_expired", "清理预览已过期，请重新预览")
        if preview["revision"] != self.document.revision or payload.revision != self.document.revision:
            raise OperationError("revision_conflict", "任务配置已改变，请重新预览")
        if not payload.confirm or payload.relax_limits != preview["relax_limits"]:
            raise OperationError("confirmation_required", "请确认本轮名单及放宽选项")
        if not preview["allowed"]:
            raise OperationError("cleanup_blocked", "本轮没有可执行的清理计划，请查看保护和限制说明")
        return preview

    def _settle(self, item, operation_id):
        ledger = self.read("smart_deletions", [])
        key = (operation_id, item["hash"])
        found = next((row for row in ledger if (row.get("operation_id"), row.get("hash")) == key), None)
        if found is None:
            found = {"operation_id": operation_id, "hash": item["hash"], "at": self.clock(), "size": item["size"]}
            ledger.append(found)
        found.update({"status": item["state"], "delete_data": item["delete_data"], "updated_at": self.clock()})
        if item["state"] == "confirmed_removed":
            found["at"] = self.clock()
            records = self.read("torrents", {})
            record = records.get(item["hash"])
            if record:
                record.update({"deleted": True, "deleted_time": self.clock(), "deletion_operation_id": operation_id,
                               "delete_data": item["delete_data"], "uploaded": max(number(record.get("uploaded")), number(item.get("uploaded")))})
                self.write("torrents", records)
        # Keep unresolved requests even past the accounting retention window.
        ledger = [row for row in ledger if self.clock() - number(row.get("at")) < 31 * 86400 or row.get("status") in UNRESOLVED_ITEMS]
        self.write("smart_deletions", ledger)

    def execute(self, operation_id: str, items: list[dict], *, relax_limits=False, manual=False, invalid_revalidator=None) -> dict:
        items = deepcopy(items)
        if manual and (len(items) > 10 or sum(number(row.get("size")) for row in items) > number(self.document.capacity.limit_gb) * GIB * .25):
            raise OperationError("manual_limit_exceeded", "本轮不能超过10个种子或任务容量的25%")
        submitted_count, submitted_bytes = 0, 0.0
        self.operations.update(self.task_id, operation_id, items=items, phase="安全复核", selected_count=len(items))
        for index, item in enumerate(items):
            item["state"] = "reviewing"
            self.operations.update(self.task_id, operation_id, items=items, phase=f"安全复核 {index + 1}/{len(items)}")
            try:
                latest = self.plan(relax_limits=relax_limits, manual=manual)
                observation = next((row for row in latest["observations"] if row["hash"] == item["hash"]), None)
                reasons = hard_safety_reasons(observation, self.policy) if observation else ["torrent_missing"]
                if observation and number(observation.get("uploaded")) > number(item.get("uploaded")):
                    reasons.append("real_upload")
                if observation and number(observation.get("total_size")) != item["size"]:
                    reasons.append("size_changed")
                result = next((row for row in latest["selection"].evaluated if row.torrent_hash == item["hash"]), None)
                invalid = item.get("kind") == "invalid_tracker"
                if invalid:
                    if manual or item["delete_data"] or not invalid_revalidator or not invalid_revalidator(item["hash"]):
                        reasons.append("invalid_tracker_not_confirmed")
                elif result is not None and not result.eligible:
                    reasons.extend(result.reason_codes)
                reasons.extend(latest["gating"])
                if observation and observation["pending_confirmation"]:
                    reasons.append("previous_request_unconfirmed")
                if observation and observation["management_tag_removed"]:
                    reasons.append("management_tag_removed")
                if not invalid and not latest["recovery"]["active"]:
                    reasons.append("capacity_target_reached")
                budget = latest["budget"]
                if submitted_count >= budget["run_count_cap"]:
                    reasons.append("run_count_cap")
                if budget["remaining_daily_count"] < 1:
                    reasons.append("daily_count_cap")
                if budget["run_byte_cap"] and item["size"] + submitted_bytes > budget["run_byte_cap"]:
                    reasons.append("run_byte_cap")
                if budget["daily_byte_cap"] and item["size"] > budget["remaining_daily_bytes"]:
                    reasons.append("daily_byte_cap")
                if reasons:
                    item.update({"state": "skipped", "reason_codes": list(dict.fromkeys(reasons))})
                else:
                    item["state"] = "submitting"
                    self.operations.update(self.task_id, operation_id, items=items, phase=f"提交删除 {index + 1}/{len(items)}")
                    self.audit({"kind": "deletion_request", "operation_id": operation_id, "item": deepcopy(item),
                                "observation": {key: value for key, value in observation.items() if key not in {"tracker", "trackers"}},
                                "manual": manual, "relax_limits": relax_limits})
                    self._settle(item, operation_id)  # Reserve quota before external I/O.
                    submitted_count += 1
                    submitted_bytes += item["size"]
                    acknowledgement = self.adapter.remove(item["hash"], delete_data=item["delete_data"])
                    item.update({"state": "accepted" if acknowledgement == "accepted" else "pending_confirmation", "acknowledgement": acknowledgement})
                    self.operations.update(self.task_id, operation_id, items=items, phase="确认下载器结果")
                    self._settle(item, operation_id)
                    for attempt in range(3):
                        try:
                            snapshot = self.adapter.snapshot()
                            if item["hash"] not in snapshot:
                                item["state"] = "confirmed_removed"
                                break
                            if acknowledgement == "rejected":
                                item["state"] = "failed"
                                break
                        except DownloaderUnavailable:
                            pass
                        if attempt < 2:
                            self.sleep(1)
                    if item["state"] == "accepted":
                        item["state"] = "pending_confirmation"
                    self._settle(item, operation_id)
                    self.audit({"kind": "deletion_outcome", "operation_id": operation_id, "item": deepcopy(item)})
            except DownloaderUnavailable:
                item.update({"state": "skipped", "reason_codes": ["downloader_unavailable"]})
            summary = self.result_summary(items)
            summary.update({"state": "running", "phase": f"已处理 {index + 1}/{len(items)}"})
            self.operations.update(self.task_id, operation_id, items=items,
                                   percent=(index + 1) / max(len(items), 1) * 100, **summary)
        return self.result_summary(items)

    @staticmethod
    def result_summary(items):
        removed = [row for row in items if row["state"] == "confirmed_removed"]
        failed = sum(row["state"] == "failed" for row in items)
        pending = sum(row["state"] in UNRESOLVED_ITEMS for row in items)
        skipped = sum(row["state"] == "skipped" for row in items)
        state = "pending_confirmation" if pending else "failed" if failed and not removed and not skipped else "partial" if failed or skipped else "completed"
        return {
            "state": state, "phase": "等待下载器确认" if pending else "部分完成" if failed or skipped else "安全清理完成",
            "deleted_count": len(removed), "failed_count": failed, "pending_count": pending, "skipped_count": skipped,
            "task_bytes_removed": sum(row["size"] for row in removed),
            "estimated_released_bytes": sum(row["size"] for row in removed if row["delete_data"]),
            "actual_released_bytes": None,
            "message": f"已确认移除 {len(removed)} 个，跳过 {skipped} 个，失败 {failed} 个，待确认 {pending} 个；空间为预计值",
        }

    def reconcile(self):
        """Readback only. A restart or timeout never resends deletion requests."""
        rows = self.read("operations", [])
        pending = [row for row in rows if any(item.get("state") in UNRESOLVED_ITEMS for item in row.get("items", []))]
        if not pending:
            return
        snapshot = self.adapter.snapshot()
        for operation in pending:
            changed = False
            for item in operation["items"]:
                if item.get("state") in UNRESOLVED_ITEMS and item["hash"] not in snapshot:
                    item["state"] = "confirmed_removed"
                    self._settle(item, operation["operation_id"])
                    self.audit({"kind": "deletion_reconciled", "operation_id": operation["operation_id"], "item": deepcopy(item)})
                    changed = True
            if changed:
                self.operations.update(self.task_id, operation["operation_id"], items=operation["items"], **self.result_summary(operation["items"]))

    def sample_and_plan(self, snapshot=None):
        plan = self.plan(include_current=True, snapshot=snapshot)
        now = self.clock()
        evaluated = {row.torrent_hash: row for row in plan["selection"].evaluated}
        history = self.read("smart_history", [])
        latest_at = {row["hash"]: number(row.get("at")) for row in sorted(history, key=lambda row: number(row.get("at")))}
        for row in plan["observations"]:
            if now - latest_at.get(row["hash"], 0) < 10:
                continue
            result = evaluated[row["hash"]]
            low_value = result.action in {"watch", "candidate"}
            history.append({"at": now, "hash": row["hash"], "uploaded": row.get("uploaded"),
                            "leechers": row.get("leechers"), "seeders": row.get("seeders"),
                            "low_value": low_value, "score": result.score,
                            "low_value_since": now - row["low_value_span_minutes"] * 60 if low_value else None,
                            "low_value_count": row["low_value_confirmations"] if low_value else 0})
        # Recent raw tracker/upload checks plus a continuous low-value anchor,
        # independently bounded per torrent. A protected check resets the anchor.
        per_hash = defaultdict(list)
        for row in history:
            if 0 <= now - number(row.get("at")) <= 30 * 86400:
                per_hash[row["hash"]].append(row)
        self.write("smart_history", [row for rows in per_hash.values() for row in rows[-max(12, self.policy.low_value_confirmations):]])
        observations = [{**plan["records"].get(row["hash"], {}), **row,
                         "feature_key": feature_key(plan["records"].get(row["hash"], {}))} for row in plan["observations"]]
        learning = update_learning_state(self.read("learning_state", {}), observations, now=now)
        self.write("learning_state", learning)
        self.write("capacity_recovery", plan["recovery"])
        self.write("current_deletion_plan", {"at": now, "aggregate": plan["aggregate"], "items": plan["items"],
                                           "evaluated": [{"hash": row.torrent_hash, "action": row.action, "score": row.score,
                                                          "reason_codes": list(row.reason_codes)} for row in plan["selection"].evaluated],
                                           "gating": plan["gating"], "reason_codes": list(plan["selection"].reason_codes)})
        self.audit({"kind": "deletion", "pressure": plan["selection"].pressure, "aggregate": plan["aggregate"],
                    "selected": plan["items"], "reason_codes": list(plan["selection"].reason_codes),
                    "estimated_freed_bytes": plan["selection"].estimated_freed_bytes,
                    "recovery_active": plan["recovery"]["active"]})
        plan["learning"] = learning_summary(learning)
        return plan

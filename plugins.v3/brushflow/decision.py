"""BrushFlow 的可解释智能删种决策引擎。

这个模块故意不依赖 MoviePilot、qBittorrent 或插件实例。它只接收一组
标准化的种子观测值和策略，输出带原因码的决策结果，便于单元测试、审计
和后续接入其他下载器。

设计原则：

* 任何硬安全线优先于评分；
* 没有容量压力时默认不删；
* 分数只是“保留价值”，不是单一分享率条件；
* 每轮和每天都有删除上限；
* 每个结果都带可读原因和贡献项，避免黑盒删种。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlparse


def _number(value: Any, default: float = 0.0) -> float:
    """安全转换 qBittorrent/历史 JSON 中可能出现的空值和脏值。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _positive(value: Any, default: float = 0.0) -> float:
    return max(_number(value, default), 0.0)


def _tags(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, Iterable):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


DEFAULT_INVALID_TRACKER_MESSAGES = (
    "torrent not registered",
    "torrent banned",
    "torrent not exists",
    "torrent does not exist",
    "torrent not found",
)


def tracker_endpoint_domain(value: Any) -> str:
    """提取 tracker 域名，供无效做种的跨种子故障保护使用。"""
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"//{text}")
    return (parsed.hostname or "").lower().strip(".")


def _tracker_message(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


@dataclass(frozen=True)
class InvalidSeedDecision:
    """Tracker 明确拒绝某个种子的可解释判定。"""

    invalid: bool
    domains: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()
    reason: str = ""


def detect_invalid_seed(
    trackers: Sequence[Mapping[str, Any]] | None,
    *,
    working_domains: Iterable[str] = (),
    invalid_messages: Sequence[str] = DEFAULT_INVALID_TRACKER_MESSAGES,
) -> InvalidSeedDecision:
    """只在 Tracker 明确拒绝且站点整体仍可用时判定无效做种。

    “Request too frequent”“unreachable”“skipping announce”等临时错误不在
    拒绝词表内；一个种子只要仍有任一正常或未知 Tracker，就不会被判为无效。
    working_domains 用于确认同一 Tracker 在下载器的其它种子上仍能正常工作，
    避免站点整体故障时批量误删。
    """
    rows = []
    for tracker in trackers or ():
        if not isinstance(tracker, Mapping):
            continue
        try:
            tier = int(_number(tracker.get("tier"), 0))
        except (TypeError, ValueError):
            tier = 0
        if tier == -1:
            continue
        status = int(_number(tracker.get("status"), -1))
        message = _tracker_message(
            tracker.get("msg", tracker.get("message", tracker.get("error")))
        )
        domain = tracker_endpoint_domain(
            tracker.get("url", tracker.get("announce", tracker.get("tracker")))
        )
        terminal = status == 4 and bool(message) and any(
            marker.lower() in message for marker in invalid_messages if str(marker).strip()
        )
        rows.append((terminal, domain, message))

    if not rows:
        return InvalidSeedDecision(False, reason="no_tracker_evidence")
    if not any(terminal for terminal, _, _ in rows):
        return InvalidSeedDecision(False, reason="no_explicit_invalid_error")
    if any(not terminal for terminal, _, _ in rows):
        return InvalidSeedDecision(False, reason="tracker_not_explicitly_invalid")

    domains = tuple(sorted({domain for _, domain, _ in rows if domain}))
    trusted_domains = {str(item).lower().strip(".") for item in working_domains if item}
    if not domains or not trusted_domains.intersection(domains):
        return InvalidSeedDecision(
            False,
            domains=domains,
            messages=tuple(sorted({message for _, _, message in rows if message})),
            reason="tracker_outage_not_confirmed",
        )
    return InvalidSeedDecision(
        True,
        domains=domains,
        messages=tuple(sorted({message for _, _, message in rows if message})),
        reason="explicit_invalid_tracker_error",
    )


def _optional_count(data: Mapping[str, Any], *names: str) -> Optional[float]:
    """读取 Tracker 人数；缺失、None 和负数均表示未知，而不是 0。"""
    for name in names:
        if name not in data or data.get(name) is None:
            continue
        value = _number(data.get(name), -1.0)
        return max(value, 0.0) if value >= 0 else None
    return None


@dataclass(frozen=True)
class TorrentObservation:
    """一次种子观测。人数为 ``None`` 时代表 Tracker 未提供数据。"""

    torrent_hash: str = ""
    title: str = ""
    total_size: float = 0.0
    downloaded: float = 0.0
    uploaded: float = 0.0
    ratio: float = 0.0
    progress: float = 0.0
    seeding_time: float = 0.0
    inactive_time: float = 0.0
    avg_upload_speed: float = 0.0
    upload_speed: float = 0.0
    seeders: Optional[float] = None
    leechers: Optional[float] = None
    active_peers: Optional[float] = None
    availability: float = 0.0
    hit_and_run: bool = False
    tags: tuple[str, ...] = ()
    upload_delta_1h: float = 0.0
    upload_delta_6h: float = 0.0
    upload_delta_24h: float = 0.0
    upload_delta_since_check: float = 0.0
    yield_per_gb_1h: float = 0.0
    yield_per_gb_6h: float = 0.0
    yield_per_gb_24h: float = 0.0
    learned_potential: float = 0.0
    demand_confirmations: int = 0
    low_value_confirmations: int = 0
    low_value_span_minutes: float = 0.0
    capacity_pressure: float = 0.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TorrentObservation":
        total_size = _positive(data.get("total_size", data.get("size")))
        downloaded = _positive(data.get("downloaded"))
        progress = _number(data.get("progress"), -1)
        if progress < 0:
            progress = (downloaded / total_size * 100) if total_size else 0.0
        return cls(
            torrent_hash=str(data.get("hash", data.get("torrent_hash", "")) or ""),
            title=str(data.get("title", data.get("name", "")) or ""),
            total_size=total_size,
            downloaded=downloaded,
            uploaded=_positive(data.get("uploaded")),
            ratio=_positive(data.get("ratio")),
            progress=max(min(progress, 100.0), 0.0),
            seeding_time=_positive(data.get("seeding_time")),
            inactive_time=_positive(data.get("inactive_time", data.get("iatime"))),
            avg_upload_speed=_positive(data.get("avg_upload_speed", data.get("avg_upspeed"))),
            upload_speed=_positive(data.get("upload_speed", data.get("upspeed"))),
            seeders=_optional_count(data, "seeders", "num_seeds"),
            leechers=_optional_count(data, "leechers", "num_leechs", "peers"),
            active_peers=_optional_count(data, "active_peers", "connected_peers"),
            availability=_positive(data.get("availability")),
            hit_and_run=bool(data.get("hit_and_run", False)),
            tags=_tags(data.get("tags")),
            upload_delta_1h=_positive(data.get("upload_delta_1h")),
            upload_delta_6h=_positive(data.get("upload_delta_6h")),
            upload_delta_24h=_positive(data.get("upload_delta_24h")),
            upload_delta_since_check=_positive(
                data.get("upload_delta_since_check", data.get("real_upload_delta"))
            ),
            yield_per_gb_1h=_positive(data.get("yield_per_gb_1h")),
            yield_per_gb_6h=_positive(data.get("yield_per_gb_6h")),
            yield_per_gb_24h=_positive(data.get("yield_per_gb_24h")),
            learned_potential=max(0.0, min(_number(data.get("learned_potential")), 15.0)),
            demand_confirmations=max(int(_number(data.get("demand_confirmations"))), 0),
            low_value_confirmations=max(int(_number(data.get("low_value_confirmations"))), 0),
            low_value_span_minutes=_positive(data.get("low_value_span_minutes")),
            # 容量压力允许超过 100%，供超额恢复模式区分“刚触发”与严重超额。
            capacity_pressure=max(0.0, min(_number(data.get("capacity_pressure")), 4.0)),
        )

    @property
    def completed(self) -> bool:
        return self.progress >= 99.999 or (
            self.total_size > 0 and self.downloaded >= self.total_size
        )

    @property
    def has_real_upload(self) -> bool:
        return self.upload_speed > 0 or self.upload_delta_since_check > 0


@dataclass(frozen=True)
class SmartPolicy:
    """9.0 统一收益策略。所有容量值使用字节。"""

    profile: str = "balanced"
    min_seed_time_hours: float = 0.0
    min_inactive_minutes: float = 0.0
    smart_cold_inactive_minutes: float = 360.0
    protect_active_demand: bool = True
    demand_confirmations: int = 2
    low_value_confirmations: int = 3
    low_value_span_minutes: float = 30.0
    ratio_target: float = 2.0
    ratio_weight: float = 5.0
    score_threshold: float = 40.0
    score_margin: float = 0.0
    capacity_trigger_percent: float = 90.0
    capacity_target_percent: float = 85.0
    max_delete_per_run: int = 3
    max_delete_percent_day: float = 5.0
    max_delete_capacity_percent_run: float = 4.0
    max_delete_capacity_percent_day: float = 8.0
    max_delete_gb_per_run: float = 0.0
    max_delete_gb_per_day: float = 0.0
    excluded_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionResult:
    torrent_hash: str
    action: str
    score: float
    reason_codes: tuple[str, ...] = ()
    contributions: Mapping[str, float] = field(default_factory=dict)

    @property
    def eligible(self) -> bool:
        return self.action == "candidate"


@dataclass(frozen=True)
class SelectionResult:
    selected: tuple[DecisionResult, ...] = ()
    evaluated: tuple[DecisionResult, ...] = ()
    reason_codes: tuple[str, ...] = ()
    pressure: bool = False
    target_size: Optional[float] = None
    estimated_freed_bytes: float = 0.0
    capacity_ratio: float = 0.0
    capacity_debt_bytes: float = 0.0
    recovery_active: bool = False
    run_byte_cap: float = 0.0
    daily_byte_cap: float = 0.0


@dataclass(frozen=True)
class CandidateDecision:
    score: float
    accepted: bool
    reason_codes: tuple[str, ...] = ()
    contributions: Mapping[str, float] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass(frozen=True)
class RankedCandidate:
    candidate: Any
    decision: CandidateDecision


def _read_candidate(candidate: Any, name: str, default: Any = None) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _candidate_optional_count(candidate: Any, *names: str) -> Optional[float]:
    marker = object()
    for name in names:
        value = _read_candidate(candidate, name, marker)
        if value is marker or value is None:
            continue
        number = _number(value, -1.0)
        return max(number, 0.0) if number >= 0 else None
    return None


def _candidate_age_minutes(candidate: Any) -> float:
    value = _number(_read_candidate(candidate, "age_minutes"), -1)
    if value >= 0:
        return value
    return max(_number(_read_candidate(candidate, "date_elapsed"), 0.0), 0.0)


def size_range_matches(size_bytes: Any, size_rule: Any) -> bool:
    """判断候选种子是否满足用户填写的 GB 大小范围。

    ``size`` 是显式过滤条件，即使智能选种开启了放宽模式也必须生效。
    单值沿用旧版语义，表示最低大小；两个值表示闭区间。
    """
    rule = str(size_rule or "").strip()
    if not rule:
        return True
    limits = [float(value) * 1024**3 for value in rule.split("-")]
    size = _positive(size_bytes)
    if len(limits) == 1:
        return size >= limits[0]
    return limits[0] <= size <= limits[1]


def capacity_selection_policy(
    profile: str,
    occupancy_ratio: float,
    base_count: int,
    base_min_score: float,
) -> tuple[int, float, str]:
    """按任务自身容量占用返回新增上限和门槛。"""
    occupancy = max(_number(occupancy_ratio), 0.0)
    tier = "under_70"
    balanced = (5, 30.0)
    if occupancy >= 0.90:
        tier, balanced = "over_90", (1, 50.0)
    elif occupancy >= 0.85:
        tier, balanced = "85_90", (2, 42.0)
    elif occupancy >= 0.70:
        tier, balanced = "70_85", (3, 35.0)
    profile = str(profile or "balanced").lower()
    if profile == "conservative":
        return min(balanced[0], 2), max(balanced[1], 40.0), tier
    if profile == "aggressive":
        counts = {"under_70": 8, "70_85": 5, "85_90": 3, "over_90": 1}
        floors = {"under_70": 22.0, "70_85": 30.0, "85_90": 37.0, "over_90": 45.0}
        return counts[tier], floors[tier], tier
    if profile == "custom":
        return min(max(int(base_count or 1), 1), balanced[0]), max(float(base_min_score), balanced[1]), tier
    return balanced[0], balanced[1], tier


def candidate_score(
    candidate: Any,
    *,
    share_ratio_gap: float = 0.0,
    share_ratio_target: float = 2.0,
    occupancy_ratio: float = 0.0,
    profile: str = "balanced",
    normal_threshold: float = 30.0,
    learned_yield_score: Optional[float] = None,
    learned_expected_yield: Optional[float] = None,
    learned_median_yield: Optional[float] = None,
    learning_confidence: float = 0.0,
) -> CandidateDecision:
    """计算 9.0 选种收益分，并保留未知 Tracker 人数的中性语义。"""
    download_factor = _number(_read_candidate(candidate, "downloadvolumefactor"), 1.0)
    upload_factor = _number(_read_candidate(candidate, "uploadvolumefactor"), 1.0)
    seeders = _candidate_optional_count(candidate, "seeders", "num_seeds")
    leechers = _candidate_optional_count(candidate, "leechers", "num_leechs", "peers")
    size = _positive(_read_candidate(candidate, "size"))
    size_gb = size / 1024**3 if size else 0.0
    confidence = max(0.0, min(_number(learning_confidence), 1.0))
    explicit_trust = _read_candidate(candidate, "demand_trusted", None)
    trusted_demand = bool(explicit_trust) if explicit_trust is not None else bool(leechers and leechers > 0)

    promotion = min((12.0 if download_factor == 0 else 0.0) + (8.0 if upload_factor >= 2 else 0.0), 20.0)
    demand = 0.0
    if trusted_demand and leechers is not None:
        demand = min(math.log1p(leechers) / math.log1p(50), 1.0) * 25.0
    scarcity = 0.0
    if seeders is not None:
        scarcity = max(0.0, 1.0 - min(seeders / 20.0, 1.0)) * 15.0
    age_minutes = _candidate_age_minutes(candidate)
    freshness = max(0.0, 1.0 - min(age_minutes / (7 * 24 * 60), 1.0)) * 10.0
    if learned_yield_score is None:
        learned_yield_score = _number(_read_candidate(candidate, "learned_yield_score"), 0.0)
    local_yield = max(0.0, min(_number(learned_yield_score), 25.0)) * confidence

    efficiency = 0.0
    if trusted_demand and size_gb > 0 and leechers is not None:
        efficiency += min(math.log1p(leechers) / math.log1p(max(size_gb, 1.0)), 1.0) * 10.0
    if confidence > 0 and local_yield > 0:
        efficiency += min(local_yield / 25.0, 1.0) * 5.0
    efficiency = min(efficiency, 15.0)

    occupancy = max(0.0, min(_number(occupancy_ratio), 1.5))
    size_factor = min(math.log1p(size_gb) / math.log1p(100), 1.0) if size_gb else 0.0
    pressure_factor = 0.35 + min(occupancy / 0.90, 1.0) * 0.65
    capacity_cost = min(size_factor * pressure_factor * 30.0 * (0.45 if trusted_demand else 1.0), 30.0)

    contributions = {
        "base": 10.0,
        "promotion": round(promotion, 2),
        "demand": round(demand, 2),
        "scarcity": round(scarcity, 2),
        "freshness": round(freshness, 2),
        "local_yield": round(local_yield, 2),
        "size_efficiency": round(efficiency, 2),
        "capacity_cost": round(-capacity_cost, 2),
    }
    score = max(0.0, min(100.0, sum(contributions.values())))
    reasons: list[str] = []
    accepted = True
    if leechers is None:
        reasons.append("tracker_demand_unknown")
    elif trusted_demand:
        reasons.append("trusted_download_demand")
    if seeders is None:
        reasons.append("tracker_seeders_unknown")
    elif scarcity > 0:
        reasons.append("trusted_scarcity")
    if promotion:
        reasons.append("promotion")
    if age_minutes <= 24 * 60:
        reasons.append("fresh")

    guarded_profile = str(profile or "balanced").lower() in {"balanced", "conservative", "custom"}
    if guarded_profile and size_gb > 50 and not trusted_demand:
        accepted = False
        reasons.append("large_without_trusted_demand")
    elif guarded_profile and 20 <= size_gb <= 50 and not trusted_demand:
        if not (download_factor == 0 and upload_factor >= 2):
            accepted = False
            reasons.append("medium_no_demand_requires_double_free")
        elif confidence <= 0:
            if score < normal_threshold + 15:
                accepted = False
                reasons.append("medium_no_demand_cold_start")
        elif learned_expected_yield is None or learned_median_yield is None or learned_expected_yield < learned_median_yield:
            accepted = False
            reasons.append("medium_no_demand_below_learned_median")

    return CandidateDecision(
        score=round(score, 2),
        accepted=accepted,
        reason_codes=tuple(reasons) or ("baseline",),
        contributions=contributions,
        confidence=round(confidence, 4),
    )


def rank_selection_candidates(
    candidates: Sequence[Any],
    *,
    min_score: float = 30.0,
    max_count: int = 5,
    share_ratio_gap: float = 0.0,
    share_ratio_target: float = 2.0,
    occupancy_ratio: float = 0.0,
    profile: str = "balanced",
    learning: Optional[Mapping[str, Mapping[str, float]]] = None,
    learning_confidence: float = 0.0,
    learned_median_yield: Optional[float] = None,
) -> tuple[RankedCandidate, ...]:
    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        candidate_key = str(
            _read_candidate(candidate, "enclosure", "")
            or _read_candidate(candidate, "page_url", "")
            or _read_candidate(candidate, "title", "")
        )
        learned = (learning or {}).get(candidate_key, {})
        decision = candidate_score(
            candidate,
            share_ratio_gap=share_ratio_gap,
            share_ratio_target=share_ratio_target,
            occupancy_ratio=occupancy_ratio,
            profile=profile,
            normal_threshold=min_score,
            learned_yield_score=learned.get("score"),
            learned_expected_yield=learned.get("expected"),
            learned_median_yield=learned_median_yield,
            learning_confidence=learning_confidence,
        )
        if decision.score < min_score:
            decision = CandidateDecision(
                decision.score,
                False,
                decision.reason_codes + ("below_selection_threshold",),
                decision.contributions,
                decision.confidence,
            )
        if decision.accepted:
            ranked.append(RankedCandidate(candidate, decision))
    ranked.sort(
        key=lambda item: (
            item.decision.score,
            _candidate_optional_count(item.candidate, "leechers", "num_leechs") or -1,
            -_positive(_read_candidate(item.candidate, "size")),
        ),
        reverse=True,
    )
    return tuple(ranked[: max(int(max_count), 1)])


def adaptive_selection_policy(
    base_count: int,
    base_min_score: float,
    current_ratio: Optional[float],
    target_ratio: Optional[float],
) -> tuple[int, float, float]:
    """目标未达时最多放宽 5 分；达标后恢复普通门槛且继续运行。"""
    count = max(int(base_count or 1), 1)
    minimum = max(float(base_min_score or 0.0), 0.0)
    target = _positive(target_ratio)
    current = _number(current_ratio, -1.0)
    if target <= 0 or current < 0:
        return count, minimum, 0.0
    gap = max(target - current, 0.0)
    if gap <= 0:
        return count, minimum, 0.0
    relaxation = min(gap / target, 1.0) * 5.0
    return count, max(0.0, minimum - relaxation), gap


def _history_for(torrent_hash: str, history: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    rows = [row for row in history if str(row.get("hash", "")) == torrent_hash]
    rows.sort(key=lambda row: _number(row.get("at")), reverse=True)
    return rows


def _demand_confirmations(
    observation: TorrentObservation,
    history: Sequence[Mapping[str, Any]],
) -> int:
    if observation.demand_confirmations > 0:
        return observation.demand_confirmations
    values: list[bool] = []
    if observation.leechers is not None:
        values.append(observation.leechers > 0)
    for row in _history_for(observation.torrent_hash, history):
        if len(values) >= 3:
            break
        count = _optional_count(row, "leechers", "num_leechs")
        if count is not None:
            values.append(count > 0)
    return sum(values[:3])


def _confirmation_state(
    observation: TorrentObservation,
    history: Sequence[Mapping[str, Any]],
    required: int,
) -> tuple[int, float]:
    if observation.low_value_confirmations > 0:
        return observation.low_value_confirmations, observation.low_value_span_minutes
    now = time.time()
    low_rows = []
    for row in _history_for(observation.torrent_hash, history):
        if not bool(row.get("low_value")):
            break
        low_rows.append(row)
    confirmations = 1 + len(low_rows)
    if not low_rows:
        return confirmations, 0.0
    earliest = min(_number(row.get("at"), now) for row in low_rows)
    return confirmations, max((now - earliest) / 60.0, 0.0)


def retention_score(
    observation: TorrentObservation,
    history: Sequence[Mapping[str, Any]] = (),
    *,
    ratio_target: float = 2.0,
    ratio_weight: float = 5.0,
) -> tuple[float, dict[str, float]]:
    """计算保留价值；累计分享率仅在近期有上传时贡献最多 5 分。"""
    yields = (
        observation.yield_per_gb_1h,
        observation.yield_per_gb_6h,
        observation.yield_per_gb_24h,
    )
    yield_signal = (
        min(math.log1p(yields[0]) / math.log1p(0.05), 1.0) * 12.0
        + min(math.log1p(yields[1]) / math.log1p(0.03), 1.0) * 8.0
        + min(math.log1p(yields[2]) / math.log1p(0.02), 1.0) * 5.0
    )
    demand_confirmations = _demand_confirmations(observation, history)
    trusted_demand = bool(observation.leechers and demand_confirmations >= 2)
    activity_signal = 12.0 if trusted_demand else 0.0
    if observation.active_peers and observation.active_peers > 0:
        activity_signal = max(activity_signal, 18.0)

    scarcity_signal = 0.0
    if observation.seeders is not None:
        scarcity_signal = max(0.0, 1.0 - min(observation.seeders / 20.0, 1.0)) * 15.0
        if observation.availability and observation.availability < 1.0:
            scarcity_signal = min(15.0, scarcity_signal + 3.0)

    learned_signal = max(0.0, min(observation.learned_potential, 15.0))
    trend_signal = 0.0
    if yields[2] > 0:
        recent = yields[0] or yields[1]
        if recent > yields[2] * 1.25:
            trend_signal = 8.0
        elif recent < yields[2] * 0.5:
            trend_signal = -6.0
    ratio_signal = 0.0
    if max(yields) > 0 or observation.upload_delta_24h > 0:
        target = max(_positive(ratio_target, 2.0), 1.0)
        ratio_signal = min(observation.ratio / target, 1.0) * min(max(_number(ratio_weight), 0.0), 5.0)
    inactivity_penalty = min(observation.inactive_time / (7 * 86400), 1.0) * 10.0
    size_factor = min(observation.total_size / (100 * 1024**3), 1.0)
    # 常规容量压力在 100% 以内累计；超过任务硬容量后继续增加成本，
    # 避免 90% 和 350% 占用得到完全相同的删种排序。
    normal_pressure = min(max(observation.capacity_pressure, 0.0), 1.0)
    overload_pressure = min(max(observation.capacity_pressure - 1.0, 0.0), 3.0)
    capacity_cost = min(
        size_factor * (5.0 + 10.0 * normal_pressure + 15.0 * overload_pressure),
        30.0,
    )
    contributions = {
        "recent_yield": round(yield_signal, 2),
        "activity": round(activity_signal, 2),
        "scarcity": round(scarcity_signal, 2),
        "learned_potential": round(learned_signal, 2),
        "trend": round(trend_signal, 2),
        "ratio": round(ratio_signal, 2),
        "inactivity": round(-inactivity_penalty, 2),
        "capacity_cost": round(-capacity_cost, 2),
    }
    score = max(0.0, min(100.0, 20.0 + sum(contributions.values())))
    return round(score, 2), contributions


def evaluate_candidate(
    observation: TorrentObservation | Mapping[str, Any],
    policy: SmartPolicy,
    history: Sequence[Mapping[str, Any]] = (),
) -> DecisionResult:
    if not isinstance(observation, TorrentObservation):
        observation = TorrentObservation.from_mapping(observation)
    blocked = lambda code: DecisionResult(observation.torrent_hash, "blocked", 100.0, (code,))
    if not observation.completed:
        return blocked("incomplete")
    if observation.hit_and_run:
        return blocked("hit_and_run")
    if policy.min_seed_time_hours <= 0:
        return blocked("missing_min_seed_time")
    if observation.seeding_time < policy.min_seed_time_hours * 3600:
        return blocked("min_seed_time")
    if set(policy.excluded_tags).intersection(observation.tags):
        return blocked("excluded_tag")
    if observation.has_real_upload:
        return blocked("real_upload")
    if observation.active_peers is not None and observation.active_peers > 0:
        return blocked("active_connection")
    if policy.protect_active_demand and observation.leechers and (
        _demand_confirmations(observation, history) >= max(policy.demand_confirmations, 1)
    ):
        return blocked("trusted_active_demand")
    inactive_floor = max(policy.smart_cold_inactive_minutes, policy.min_inactive_minutes)
    if inactive_floor > 0 and observation.inactive_time < inactive_floor * 60:
        return blocked("smart_cold_cooldown")
    score, contributions = retention_score(
        observation,
        history,
        ratio_target=policy.ratio_target,
        ratio_weight=policy.ratio_weight,
    )
    cutoff = max(0.0, policy.score_threshold - max(policy.score_margin, 0.0))
    if score > cutoff:
        return DecisionResult(observation.torrent_hash, "keep", score, ("valuable_seed",), contributions)
    required = max(policy.low_value_confirmations, 1)
    confirmations, span = _confirmation_state(observation, history, required)
    required_span = max(policy.low_value_span_minutes, 0.0)
    if confirmations < required or span < required_span:
        details = dict(contributions)
        details.update({"confirmations": float(confirmations), "confirmation_span_minutes": round(span, 2)})
        return DecisionResult(observation.torrent_hash, "watch", score, ("low_value_unconfirmed",), details)
    return DecisionResult(observation.torrent_hash, "candidate", score, ("low_retention_value",), contributions)


def select_deletions(
    observations: Sequence[TorrentObservation | Mapping[str, Any]],
    policy: SmartPolicy,
    *,
    current_size: float,
    min_size: Optional[float] = None,
    max_size: Optional[float] = None,
    disk_limit: Optional[float] = None,
    history: Sequence[Mapping[str, Any]] = (),
    deleted_today: int = 0,
    deleted_today_bytes: float = 0.0,
) -> SelectionResult:
    normalized = [
        item if isinstance(item, TorrentObservation) else TorrentObservation.from_mapping(item)
        for item in observations
    ]
    trigger = max_size
    if trigger is None and disk_limit:
        trigger = disk_limit * max(min(policy.capacity_trigger_percent, 100.0), 0.0) / 100.0
    pressure = bool(trigger is not None and current_size >= trigger)
    capacity_base_for_pressure = disk_limit or trigger
    capacity_ratio = (
        max(current_size / capacity_base_for_pressure, 0.0)
        if capacity_base_for_pressure
        else (1.0 if pressure else 0.0)
    )
    capacity_pressure = min(capacity_ratio, 4.0)
    recovery_active = bool(disk_limit and capacity_ratio > 1.0)
    normalized = [
        TorrentObservation(**{**item.__dict__, "capacity_pressure": capacity_pressure})
        for item in normalized
    ]
    evaluated = tuple(
        evaluate_candidate(
            item,
            policy,
            history,
        )
        for item in normalized
    )
    if not pressure:
        return SelectionResult(
            evaluated=evaluated,
            reason_codes=("no_pressure",),
            pressure=False,
            capacity_ratio=capacity_ratio,
        )

    target_size = min_size
    if target_size is None and disk_limit:
        target_size = disk_limit * max(min(policy.capacity_target_percent, 100.0), 0.0) / 100.0
    if target_size is None:
        return SelectionResult(
            evaluated=evaluated,
            reason_codes=("missing_target_size",),
            pressure=True,
            capacity_ratio=capacity_ratio,
            recovery_active=recovery_active,
        )

    by_hash = {item.torrent_hash: item for item in normalized}
    eligible = [result for result in evaluated if result.eligible]
    eligible.sort(
        key=lambda result: (
            math.floor(result.score / 5.0),
            by_hash[result.torrent_hash].yield_per_gb_24h,
            -by_hash[result.torrent_hash].total_size,
        )
    )
    active_count = len(normalized)
    daily_count_cap = (
        max(1, math.floor(active_count * policy.max_delete_percent_day / 100.0))
        if policy.max_delete_percent_day > 0 else len(eligible)
    )
    remaining_count = max(daily_count_cap - max(deleted_today, 0), 0)
    run_count_cap = max(int(policy.max_delete_per_run), 0)

    capacity_base = disk_limit or current_size
    run_percent = policy.max_delete_capacity_percent_run
    day_percent = policy.max_delete_capacity_percent_day
    run_percent_cap = capacity_base * run_percent / 100.0
    day_percent_cap = capacity_base * day_percent / 100.0
    run_explicit_cap = policy.max_delete_gb_per_run * 1024**3
    day_explicit_cap = policy.max_delete_gb_per_day * 1024**3
    run_byte_cap = min(
        cap for cap in (run_percent_cap, run_explicit_cap) if cap > 0
    ) if run_percent_cap > 0 or run_explicit_cap > 0 else 0.0
    daily_byte_cap = min(
        cap for cap in (day_percent_cap, day_explicit_cap) if cap > 0
    ) if day_percent_cap > 0 or day_explicit_cap > 0 else 0.0
    remaining_daily_bytes = max(daily_byte_cap - max(deleted_today_bytes, 0.0), 0.0)
    selected: list[DecisionResult] = []
    freed = 0.0
    remaining_size = current_size
    for result in eligible:
        if len(selected) >= min(run_count_cap, remaining_count) or remaining_size <= target_size:
            break
        size = by_hash[result.torrent_hash].total_size
        if run_byte_cap > 0 and freed + size > run_byte_cap:
            continue
        if daily_byte_cap > 0 and freed + size > remaining_daily_bytes:
            continue
        selected.append(result)
        freed += size
        remaining_size = max(remaining_size - size, 0.0)

    reasons: list[str] = []
    if not selected:
        reasons.append("no_low_value_candidate")
    if run_count_cap and len(selected) >= run_count_cap and len(selected) < len(eligible):
        reasons.extend(("run_count_cap", "run_cap"))
    if remaining_count <= 0:
        reasons.append("daily_count_cap")
    if eligible and not selected and (run_byte_cap <= 0 or remaining_daily_bytes <= 0):
        reasons.append("byte_cap")
    return SelectionResult(
        selected=tuple(selected),
        evaluated=evaluated,
        reason_codes=tuple(reasons),
        pressure=True,
        target_size=target_size,
        estimated_freed_bytes=freed,
        capacity_ratio=capacity_ratio,
        capacity_debt_bytes=max(current_size - target_size, 0.0),
        recovery_active=recovery_active,
        run_byte_cap=run_byte_cap,
        daily_byte_cap=daily_byte_cap,
    )

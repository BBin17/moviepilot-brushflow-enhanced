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


@dataclass(frozen=True)
class TorrentObservation:
    """一次种子实时状态快照，单位统一为字节、秒和字节/秒。"""

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
    seeders: float = 0.0
    leechers: float = 0.0
    active_peers: float = 0.0
    availability: float = 0.0
    hit_and_run: bool = False
    tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TorrentObservation":
        """兼容 qB 字段、插件状态字段和测试简化字段。"""
        total_size = _positive(data.get("total_size", data.get("size")))
        downloaded = _positive(data.get("downloaded"))
        progress = _number(data.get("progress"), -1)
        if progress < 0:
            progress = (downloaded / total_size * 100) if total_size else 0.0
        # qB 的 leechers/seeders 通常叫 num_leechs/num_seeds；某些下载器
        # 适配层则已经转换为 peers/seeders，因此这里按多个别名读取。
        leechers = _positive(
            data.get("leechers", data.get("num_leechs", data.get("peers")))
        )
        seeders = _positive(data.get("seeders", data.get("num_seeds")))
        active_peers = _positive(data.get("active_peers", leechers))
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
            avg_upload_speed=_positive(
                data.get("avg_upload_speed", data.get("avg_upspeed"))
            ),
            upload_speed=_positive(data.get("upload_speed", data.get("upspeed"))),
            seeders=seeders,
            leechers=leechers,
            active_peers=active_peers,
            availability=_positive(data.get("availability")),
            hit_and_run=bool(data.get("hit_and_run", False)),
            tags=_tags(data.get("tags")),
        )

    @property
    def completed(self) -> bool:
        """只有明确完成的种子才允许进入智能删种候选。"""
        return self.progress >= 99.999 or (
            self.total_size > 0 and self.downloaded >= self.total_size
        )


@dataclass(frozen=True)
class SmartPolicy:
    """智能模式策略。所有数值都已经是运行单位。"""

    min_seed_time_hours: float = 0.0
    min_inactive_minutes: float = 0.0
    min_ratio: float = 0.0
    min_uploaded_gb: float = 0.0
    score_threshold: float = 40.0
    score_margin: float = 0.0
    max_delete_per_run: int = 3
    max_delete_percent_day: float = 5.0
    allow_proactive_delete: bool = True
    required_conditions: bool = False
    excluded_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionResult:
    """单个种子的可解释结果。"""

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
    """一轮删种计划及其限额原因。"""

    selected: tuple[DecisionResult, ...] = ()
    evaluated: tuple[DecisionResult, ...] = ()
    reason_codes: tuple[str, ...] = ()
    pressure: bool = False


@dataclass(frozen=True)
class CandidateDecision:
    """新增候选的可解释价值评分。"""

    score: float
    accepted: bool
    reason_codes: tuple[str, ...] = ()
    contributions: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RankedCandidate:
    """保留原始候选对象，方便插件把对象交回下载链路。"""

    candidate: Any
    decision: CandidateDecision


def _read_candidate(candidate: Any, name: str, default: Any = None) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _candidate_age_minutes(candidate: Any) -> float:
    value = _number(_read_candidate(candidate, "age_minutes"), -1)
    if value >= 0:
        return value
    elapsed = _number(_read_candidate(candidate, "date_elapsed"), -1)
    if elapsed >= 0:
        return elapsed
    return 0.0


def candidate_score(candidate: Any) -> CandidateDecision:
    """给站点候选种子打分，分数越高越值得优先新增。"""
    download_factor = _number(_read_candidate(candidate, "downloadvolumefactor"), 1)
    upload_factor = _number(_read_candidate(candidate, "uploadvolumefactor"), 1)
    seeders = _positive(_read_candidate(candidate, "seeders"))
    leechers = _positive(
        _read_candidate(candidate, "leechers", _read_candidate(candidate, "num_leechs"))
    )
    size = _positive(_read_candidate(candidate, "size"))
    hit_and_run = bool(_read_candidate(candidate, "hit_and_run", False))

    promotion = 0.0
    if download_factor == 0:
        promotion += 18.0
    if upload_factor >= 2:
        promotion += 8.0

    demand = min(math.log1p(leechers) / math.log1p(50), 1.0) * 28
    if seeders <= 0:
        scarcity = 8.0
    elif seeders <= 3:
        scarcity = 25.0
    elif seeders <= 10:
        scarcity = 18.0
    elif seeders <= 20:
        scarcity = 8.0
    else:
        scarcity = 0.0

    age_minutes = _candidate_age_minutes(candidate)
    freshness = max(0.0, 1.0 - min(age_minutes / (7 * 24 * 60), 1.0)) * 15
    size_penalty = min(size / (100 * 1024**3), 1.0) * 6
    hr_penalty = 20.0 if hit_and_run else 0.0
    contributions = {
        "promotion": round(promotion, 2),
        "demand": round(demand, 2),
        "scarcity": round(scarcity, 2),
        "freshness": round(freshness, 2),
        "size": round(-size_penalty, 2),
        "hr_risk": round(-hr_penalty, 2),
    }
    score = max(0.0, min(100.0, 25.0 + sum(contributions.values())))
    reasons = []
    if promotion:
        reasons.append("promotion")
    if leechers > 0:
        reasons.append("download_demand")
    if seeders <= 10:
        reasons.append("scarcity")
    if age_minutes <= 24 * 60:
        reasons.append("fresh")
    if hit_and_run:
        reasons.append("hr_risk")
    return CandidateDecision(
        score=round(score, 2),
        accepted=True,
        reason_codes=tuple(reasons) or ("baseline",),
        contributions=contributions,
    )


def rank_selection_candidates(
    candidates: Sequence[Any],
    *,
    min_score: float = 25.0,
    max_count: int = 5,
) -> tuple[RankedCandidate, ...]:
    """按智能选种分数排序并限制本轮新增数量。"""
    ranked = []
    for candidate in candidates:
        decision = candidate_score(candidate)
        if decision.score < min_score:
            decision = CandidateDecision(
                decision.score,
                False,
                decision.reason_codes + ("below_selection_threshold",),
                decision.contributions,
            )
        if decision.accepted:
            ranked.append(RankedCandidate(candidate, decision))
    ranked.sort(
        key=lambda item: (
            item.decision.score,
            _number(_read_candidate(item.candidate, "leechers")),
            -_positive(_read_candidate(item.candidate, "size")),
        ),
        reverse=True,
    )
    return tuple(ranked[: max(int(max_count), 1)])


def _history_for(torrent_hash: str, history: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    rows = [row for row in history if str(row.get("hash", "")) == torrent_hash]
    rows.sort(key=lambda row: _number(row.get("at")), reverse=True)
    return rows


def retention_score(
    observation: TorrentObservation,
    history: Sequence[Mapping[str, Any]] = (),
) -> tuple[float, dict[str, float]]:
    """计算 0-100 的保留价值分数，并返回各信号贡献。

    分数越高代表越值得继续做种：上传需求、当前下载者和稀缺性会提高
    分数；长期闲置、上传很低、做种资源充足和较大体积会降低分数。分享
    率只做弱信号，不能单独触发删除。
    """
    upload_rate = max(observation.upload_speed, observation.avg_upload_speed)
    upload_signal = min(math.log1p(upload_rate) / math.log1p(1024 * 1024), 1.0) * 25
    peer_signal = min(math.log1p(max(observation.active_peers, observation.leechers)) / math.log1p(20), 1.0) * 20

    # 做种越少越稀缺；availability 小于 1 表示可能无法组成完整副本，额外保护。
    scarcity_signal = max(0.0, 1.0 - min(observation.seeders / 20.0, 1.0)) * 22
    if observation.availability and observation.availability < 1.0:
        scarcity_signal = min(30.0, scarcity_signal + 8.0)

    ratio_signal = min(observation.ratio / 2.0, 1.0) * 8
    inactive_penalty = min(observation.inactive_time / (7 * 24 * 3600), 1.0) * 15
    age_penalty = min(observation.seeding_time / (30 * 24 * 3600), 1.0) * 5
    size_penalty = min(observation.total_size / (100 * 1024**3), 1.0) * 5

    trend_signal = 0.0
    previous = _history_for(observation.torrent_hash, history)
    if previous:
        previous_row = previous[0]
        previous_rate = _positive(
            previous_row.get("upload_speed", previous_row.get("avg_upload_speed"))
        )
        previous_peers = _positive(previous_row.get("active_peers", previous_row.get("leechers")))
        if upload_rate > previous_rate * 1.15 or observation.active_peers > previous_peers:
            trend_signal = 8.0
        elif upload_rate < previous_rate * 0.5 and observation.active_peers <= previous_peers:
            trend_signal = -5.0

    contributions = {
        "upload_demand": round(upload_signal, 2),
        "peer_demand": round(peer_signal, 2),
        "scarcity": round(scarcity_signal, 2),
        "ratio": round(ratio_signal, 2),
        "trend": round(trend_signal, 2),
        "inactivity": round(-inactive_penalty, 2),
        "age": round(-age_penalty, 2),
        "size": round(-size_penalty, 2),
    }
    score = max(0.0, min(100.0, 20.0 + sum(contributions.values())))
    return round(score, 2), contributions


def evaluate_candidate(
    observation: TorrentObservation | Mapping[str, Any],
    policy: SmartPolicy,
    history: Sequence[Mapping[str, Any]] = (),
    legacy_conditions_met: bool = True,
) -> DecisionResult:
    """对单个种子应用硬安全线和保留价值评分。"""
    if not isinstance(observation, TorrentObservation):
        observation = TorrentObservation.from_mapping(observation)
    if not observation.completed:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("incomplete",))
    if observation.hit_and_run:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("hit_and_run",))
    if policy.min_seed_time_hours <= 0:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("missing_min_seed_time",))
    if observation.seeding_time < policy.min_seed_time_hours * 3600:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("min_seed_time",))
    if policy.min_inactive_minutes > 0 and observation.inactive_time < policy.min_inactive_minutes * 60:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("min_inactive_time",))
    if policy.min_ratio > 0 and observation.ratio < policy.min_ratio:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("min_ratio",))
    if policy.min_uploaded_gb > 0 and observation.uploaded < policy.min_uploaded_gb * 1024**3:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("min_uploaded",))
    excluded = set(policy.excluded_tags)
    if excluded.intersection(observation.tags):
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("excluded_tag",))
    if policy.required_conditions and not legacy_conditions_met:
        return DecisionResult(observation.torrent_hash, "blocked", 100.0, ("required_condition",))

    score, contributions = retention_score(observation, history)
    cutoff = max(0.0, policy.score_threshold - max(policy.score_margin, 0.0))
    if score <= cutoff:
        return DecisionResult(observation.torrent_hash, "candidate", score, ("low_retention_value",), contributions)
    return DecisionResult(observation.torrent_hash, "keep", score, ("valuable_seed",), contributions)


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
    legacy_conditions: Optional[Mapping[str, bool]] = None,
) -> SelectionResult:
    """在容量压力和删除限额下生成一轮实际删种计划。"""
    normalized = [
        item if isinstance(item, TorrentObservation) else TorrentObservation.from_mapping(item)
        for item in observations
    ]
    evaluated = tuple(
        evaluate_candidate(
            item,
            policy,
            history,
            (legacy_conditions or {}).get(item.torrent_hash, True),
        )
        for item in normalized
    )

    pressure = False
    if max_size is not None and current_size >= max_size:
        pressure = True
    elif disk_limit and current_size >= disk_limit * 0.90:
        pressure = True
    elif policy.allow_proactive_delete:
        pressure = True
    if not pressure:
        return SelectionResult(evaluated=evaluated, reason_codes=("no_pressure",), pressure=False)

    target_size = min_size if min_size is not None else (disk_limit * 0.85 if disk_limit else None)
    if policy.allow_proactive_delete and min_size is None and max_size is None:
        target_size = 0.0
    if target_size is None and policy.allow_proactive_delete:
        target_size = 0.0
    if target_size is None:
        return SelectionResult(evaluated=evaluated, reason_codes=("missing_target_size",), pressure=True)

    eligible = [result for result in evaluated if result.eligible]
    eligible.sort(
        key=lambda result: (
            result.score,
            -next((item.total_size for item in normalized if item.torrent_hash == result.torrent_hash), 0),
        )
    )
    active_count = len(normalized)
    daily_cap = max(1, math.floor(active_count * policy.max_delete_percent_day / 100)) if policy.max_delete_percent_day > 0 else 0
    remaining_daily = max(daily_cap - max(deleted_today, 0), 0) if daily_cap else len(eligible)
    run_cap = max(int(policy.max_delete_per_run), 0) if policy.max_delete_per_run else len(eligible)
    cap = min(run_cap, remaining_daily)

    selected: list[DecisionResult] = []
    remaining_size = current_size
    for result in eligible:
        if len(selected) >= cap or remaining_size <= target_size:
            break
        selected.append(result)
        observation = next(item for item in normalized if item.torrent_hash == result.torrent_hash)
        remaining_size = max(remaining_size - observation.total_size, 0.0)

    reasons: list[str] = []
    if not selected:
        reasons.append("no_low_value_candidate")
    if len(selected) >= run_cap and run_cap < len(eligible):
        reasons.append("run_cap")
    if daily_cap and remaining_daily <= 0:
        reasons.append("daily_cap")
    return SelectionResult(tuple(selected), evaluated, tuple(reasons), True)

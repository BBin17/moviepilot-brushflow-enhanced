from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import pytest

from app.plugins.smartbrushflow import SmartBrushFlow, BrushTaskConfig
from app.plugins.smartbrushflow.selection import (
    candidate_key, demand_signal, download_context, evaluate_opportunities, observe_candidates, promotion_remaining,
)
from app.plugins.smartbrushflow.selection_feedback import (
    feedback_summary, predict_selection, selection_features, update_feedback,
)
from app.plugins.smartbrushflow.health_service import DownloadHealthService


GIB = 1024 ** 3
NOW = 1_800_000_000.0


def candidate(**changes):
    return {"title": "seed", "page_url": "https://example.invalid/details?id=123", "size": 5 * GIB,
            "seeders": 5, "leechers": 20, "date_elapsed": 30, "downloadvolumefactor": 0,
            "uploadvolumefactor": 1, **changes}


def evaluate(items=None, **kw):
    return evaluate_opportunities(items or [candidate()], kw.pop("history", {}), kw.pop("feedback", {}),
        kw.pop("records", {}), now=NOW, task_capacity_bytes=800 * GIB, **kw)


def hourly_dataset(*, hours=73, uploaded_per_hour=GIB, baseline=True):
    joined = NOW - hours * 3600
    records = {"hash": {**candidate(), "time": joined, "uploaded": hours * uploaded_per_hour,
                        "download_completed_bytes": 5 * GIB, "download_health_checked_at": NOW}}
    if baseline:
        records["hash"]["selection_context"] = {"at": joined, "baseline_uploaded": 0}
    learning = {"snapshots": [{"hash": "hash", "at": joined + h * 3600, "uploaded": h * uploaded_per_hour}
                               for h in range(1, hours + 1)]}
    return records, learning


def model(count, *, value=1, features=None):
    return {"outcomes": {str(i): {"joined_at": NOW - (i + 1) * 3600, "features": features or selection_features(candidate()),
                        "windows": {"24": {"yield": value, "uploaded": value * GIB}}} for i in range(count)}}


def test_candidate_history_is_bounded_redacted_and_manual_spam_does_not_confirm():
    item = candidate(page_url="https://private.invalid/details?id=1&passkey=secret")
    history = observe_candidates({}, [item], now=NOW)
    assert "secret" not in str(history) and "private.invalid" not in str(history)
    assert observe_candidates(history, [item], now=NOW + 10) == history
    assert demand_signal(history["candidates"][candidate_key(item)], now=NOW)["state"] == "unknown"
    assert observe_candidates(history, [], now=NOW + 7 * 3600)["candidates"] == {}
    many = observe_candidates({}, [candidate(page_url=f"/{i}") for i in range(1100)], now=NOW)
    assert len(many["candidates"]) == 1000


@pytest.mark.parametrize("initial,latest,state", [(10, 20, "rising"), (30, 10, "falling"), (10, 10, "stable")])
def test_observed_demand_direction_changes_opportunity(initial, latest, state):
    item = candidate(leechers=latest)
    history = observe_candidates({}, [candidate(leechers=initial)], now=NOW - 600)
    history = observe_candidates(history, [item], now=NOW)
    result = evaluate([item], history=history)["evaluated"][0]
    assert result["trend"]["state"] == state
    assert result["contributions"]["demand_trend"] == pytest.approx(result["trend"]["adjustment"])


def test_falling_demand_and_seed_competition_rank_below_growing_demand():
    rising, falling = candidate(page_url="/rise"), candidate(page_url="/fall")
    history = observe_candidates({}, [{**rising, "leechers": 10}, {**falling, "leechers": 40}], now=NOW - 600)
    history = observe_candidates(history, [rising, falling], now=NOW)
    rows = evaluate([falling, rising], history=history)["ranked"]
    assert rows[0]["key"] == candidate_key(rising)
    points = [{"at": NOW - 600, "seeders": 5, "leechers": 10}, {"at": NOW, "seeders": 50, "leechers": 10}]
    assert demand_signal(points, now=NOW)["state"] == "competition_rising"


def test_unknown_stale_or_disjoint_people_are_not_a_trend():
    for points in ([{"at": NOW - 600, "seeders": None, "leechers": 10}, {"at": NOW, "seeders": 5, "leechers": 20}],
                   [{"at": NOW - 7200, "seeders": 5, "leechers": 10}, {"at": NOW, "seeders": 5, "leechers": 20}],
                   [{"at": NOW - 1800, "seeders": 5, "leechers": 10}, {"at": NOW - 600, "seeders": 5, "leechers": 20}]):
        assert demand_signal(points, now=NOW)["state"] == "unknown"


def test_unknown_counts_do_not_earn_scarcity_and_unknown_age_is_not_fresh():
    result = evaluate([candidate(seeders=None, leechers=None, date_elapsed=None)])["evaluated"][0]
    assert result["contributions"]["scarcity"] == 0
    assert result["contributions"]["freshness"] == 0
    assert result["eta_hours"] is None


def test_uncertain_small_torrents_have_one_exploration_slot_and_not_fake_additions():
    items = [candidate(page_url=f"/{i}", seeders=1, leechers=None, size=GIB) for i in range(4)]
    result = evaluate(items, min_score=0)
    assert len(result["planned"]) == 1
    assert all(not row["selected"] for row in result["evaluated"])
    assert sum(row["status"] == "waiting" for row in result["evaluated"]) == 3
    assert not evaluate([candidate(size=19 * GIB, leechers=None)], min_score=0)["planned"]


def test_strong_new_demand_can_be_chosen_without_waiting_for_trend():
    row = evaluate()["planned"][0]
    assert row["trend"]["state"] == "unknown"
    assert not row["exploratory"]


def test_minimum_seed_commitment_cost_uses_user_setting_not_a_new_stop_line():
    low = evaluate(min_seed_hours=24)["evaluated"][0]
    high = evaluate(min_seed_hours=168)["evaluated"][0]
    assert high["score"] < low["score"]
    assert high["minimum_seed_gb_hours"] == 5 * 168
    assert evaluate(occupancy_ratio=.95, min_score=0)["planned"]


def test_distinct_continuous_windows_include_zero_and_never_count_checks_as_samples():
    records, learning = hourly_dataset(uploaded_per_hour=0)
    state = update_feedback({}, records, learning, now=NOW)
    assert state["outcomes"]["hash"]["windows"]["24"]["uploaded"] == 0
    assert set(state["outcomes"]["hash"]["windows"]) == {"6", "24", "72"}
    assert update_feedback(state, records, learning, now=NOW) == state
    summary = feedback_summary(state, now=NOW)
    assert summary["sample_count"] == 1 and summary["zero_upload_count"] == 1
    assert summary["confidence"] == 0


@pytest.mark.parametrize("damage", ["gap", "reset", "missing_baseline"])
def test_incomplete_or_reset_history_never_teaches_zero_upload(damage):
    records, learning = hourly_dataset(hours=25)
    if damage == "gap":
        learning["snapshots"] = [row for row in learning["snapshots"] if row["at"] > NOW - 20 * 3600]
    elif damage == "reset":
        learning["snapshots"][12]["uploaded"] = 0
    else:
        records["hash"].pop("selection_context")
    row = update_feedback({}, records, learning, now=NOW)["outcomes"]["hash"]
    assert "24" not in row["windows"]


def test_sampling_labels_are_frozen_and_expire_at_30_days():
    records, learning = hourly_dataset(hours=25)
    state = update_feedback({}, records, learning, now=NOW)
    records["hash"]["uploaded"] *= 1000
    updated = update_feedback(state, records, learning, now=NOW + 100)
    assert updated["outcomes"]["hash"]["windows"]["24"] == state["outcomes"]["hash"]["windows"]["24"]
    assert not update_feedback(state, {}, {}, now=NOW + 31 * 86400)["outcomes"]


def test_model_confidence_requires_distinct_torrents_and_is_task_local():
    assert predict_selection(model(1), candidate(), now=NOW)["confidence"] == 0
    assert predict_selection(model(20), candidate(), now=NOW)["confidence"] == 0
    assert 0 < predict_selection(model(60), candidate(), now=NOW)["confidence"] < 1
    assert predict_selection(model(100), candidate(), now=NOW)["confidence"] == 1
    assert predict_selection({}, candidate(), now=NOW)["expected"] is None


def test_outlier_is_clipped_and_sparse_bucket_backs_off():
    state = model(99)
    state["outcomes"]["spike"] = {"joined_at": NOW, "features": selection_features(candidate()),
                                     "windows": {"24": {"yield": 1_000_000, "uploaded": 1_000_000 * GIB}}}
    assert predict_selection(state, candidate(), now=NOW)["expected"] == pytest.approx(1)
    original = deepcopy(state)
    other = predict_selection(state, candidate(size=80 * GIB), now=NOW)
    assert other["level"] == "task" and other["matched_count"] == 100
    assert state == original


def test_persistent_low_yield_cohort_is_penalized():
    row = evaluate(feedback=model(100, value=0))["evaluated"][0]
    assert row["contributions"]["historical_failure_risk"] == -15
    assert "similar_torrents_unproductive" in row["reasons"]


def test_download_health_gates_new_additions_without_deleting_anything():
    records = {str(i): {"size": GIB, "download_completed_bytes": 0, "download_health": "stalled",
                       "download_health_checked_at": NOW} for i in range(4)}
    before = deepcopy(records)
    result = evaluate(records=records)
    assert result["context"]["max_add"] == 0 and result["planned"] == []
    assert records == before
    records["0"]["deleted"] = True
    for row in list(records.values())[1:]:
        row["download_health"] = "downloading"
    assert evaluate(records=records)["context"]["max_add"] == 5
    records["1"]["download_health"] = "stalled"
    assert evaluate(records=records)["context"]["max_add"] == 1


def test_sparse_or_stale_speed_is_unknown_and_limits_do_not_invent_throughput():
    assert download_context({}, now=NOW, base_count=5, download_limit_kbps=10240)["speed_bytes_second"] is None
    records = {str(i): {"size": GIB, "download_health_avg_kbps": 1000, "download_health_progress_delta": 1,
                       "download_health_checked_at": NOW - 3600} for i in range(3)}
    assert evaluate(records=records)["context"]["speed_bytes_second"] is None


def test_completion_time_respects_shared_bandwidth_and_promotion_deadline():
    records = {str(i): {"size": 10 * GIB, "download_completed_bytes": GIB, "download_health_avg_kbps": 1024,
                       "download_health_progress_delta": 1000, "download_health_checked_at": NOW} for i in range(3)}
    row = evaluate([candidate(freedate=NOW + 3600)], records=records, download_limit_kbps=512)["evaluated"][0]
    assert row["eta_hours"] > 2
    assert "promotion_finishes_too_soon" in row["reasons"] and not row["eligible"]
    assert promotion_remaining(candidate(freedate="2026-10-15 10:00:00"), now=NOW) is None
    assert promotion_remaining(candidate(freedate="not-a-time"), now=NOW) is None
    assert promotion_remaining(candidate(freedate=NOW + 7200), now=NOW) == 2
    assert "promotion_finishes_too_soon" not in evaluate([candidate(freedate=NOW + 1)], records=records, require_free=False)["evaluated"][0]["reasons"]


def test_completed_wall_clock_speed_requires_observed_incomplete_transition():
    rows = {str(i): {"size": GIB, "time": NOW - 3600, "download_first_completed_at": NOW} for i in range(3)}
    assert download_context(rows, now=NOW, base_count=5)["speed_bytes_second"] is None
    for row in rows.values():
        row["download_seen_incomplete_at"] = NOW - 3000
    assert download_context(rows, now=NOW, base_count=5)["speed_source"] == "completed"


def test_health_capture_does_not_fabricate_old_completed_download_times():
    store, clock = {}, [NOW]
    service = DownloadHealthService(downloader=None, read=lambda key, default: store.get(key, default),
        write=lambda key, value: store.__setitem__(key, value), identify=lambda row: row["hash"], normalize=dict,
        notify=lambda *args: None, clock=lambda: clock[0])
    records = {"old": {"time": NOW - 86400}, "new": {"time": NOW}}
    service.observe([{"hash": "old", "total_size": GIB, "completed": GIB},
                     {"hash": "new", "total_size": GIB, "completed": 1}], records)
    assert "download_first_completed_at" not in records["old"]
    clock[0] += 600
    service.observe([{"hash": "new", "total_size": GIB, "completed": GIB}], records)
    assert records["new"]["download_first_completed_at"] == NOW + 600


def run_selection(*, capacity=800, fail_first=False, backlog=False, occupied=0):
    plugin = object.__new__(SmartBrushFlow)
    task = BrushTaskConfig({"id": "task", "name": "task", "site_id": 1, "downloader": "qb", "disksize": capacity,
                            "min_seed_time": 72, "smart_selection_enabled": True})
    records = {str(i): {"size": GIB, "download_health": "stalled", "download_health_checked_at": NOW}
               for i in range(3)} if backlog else {}
    if occupied:
        records["existing"] = {"size": occupied * GIB, "download_completed_bytes": occupied * GIB}
    items = [SimpleNamespace(**{**candidate(title=f"seed{i}", page_url=f"/{i}"), "site_name": "test", "enclosure": f"/{i}",
              "description": "", "hit_and_run": False, "pubdate": None, "freedate": None,
              "volume_factor": "free", "freedate_diff": None}) for i in range(3)]
    store, audits, downloads = {}, [], []
    plugin._get_task_config = lambda *args: task
    plugin._get_task_data = lambda task_id, key: store.get(key)
    plugin._save_task_data = lambda task_id, key, value: store.__setitem__(key, deepcopy(value))
    plugin._append_decision_audit = lambda task_id, row: audits.append(deepcopy(row))
    plugin._SmartBrushFlow__evaluate_pre_conditions_for_brush = lambda **kwargs: (True, None)
    plugin._SmartBrushFlow__send_add_message = lambda *args: None
    plugin.eventmanager = SimpleNamespace(send_event=lambda **kwargs: None)
    def add(item):
        downloads.append(item.title)
        return None if fail_first and len(downloads) == 1 else item.title
    plugin._SmartBrushFlow__download = add
    report = plugin._new_run_report("brush")
    with patch("app.plugins.smartbrushflow.time.time", return_value=NOW), patch("app.plugins.smartbrushflow.TorrentsChain") as source, \
            patch.object(SmartBrushFlow, "service_info", new_callable=PropertyMock, return_value=SimpleNamespace(name="qb")):
        source.return_value.browse.return_value = items
        plugin._SmartBrushFlow__brush_site_torrents(site=SimpleNamespace(name="test", domain="test", id=1),
            torrent_tasks=records, all_torrent_tasks=dict(records), subscribe_titles=set(), report=report, global_seeding_size=0)
    return report, records, store, audits, downloads


def test_real_selection_records_only_acknowledged_adds_and_fills_failed_slot():
    report, records, store, audits, downloads = run_selection(fail_first=True)
    assert len(downloads) == 3 and report["added_count"] == 2
    assert len([row for row in audits[-1]["decisions"] if row["selected"]]) == 2
    assert next(row for row in audits[-1]["decisions"] if row["title"] == "seed0")["status"] == "add_failed"
    assert records["seed1"]["selection_context"]["baseline_uploaded"] == 0
    assert "selection_history" in store


def test_capacity_veto_and_unhealthy_backlog_cannot_be_bypassed_by_high_score():
    report, records, _, audits, downloads = run_selection(capacity=21, occupied=12)
    assert len(downloads) == 1 and report["added_count"] == 1
    assert sum(row["status"] == "blocked" for row in audits[-1]["decisions"]) == 2
    report, _, _, audits, downloads = run_selection(backlog=True)
    assert downloads == [] and report["added_count"] == 0
    assert all(not row["selected"] for row in audits[-1]["decisions"])


@pytest.mark.parametrize("changes,expected", [
    ({"size": .1 * GIB}, "大小"), ({"hit_and_run": True}, "H&R"),
    ({"downloadvolumefactor": 1}, "非免费"), ({"title": "excluded-title"}, "排除规则"),
])
def test_smart_opportunity_never_bypasses_explicit_hard_filters(changes, expected):
    plugin = object.__new__(SmartBrushFlow)
    task = BrushTaskConfig({"id": "one", "size": "0.5-50", "freeleech": "free", "hr": "yes",
                            "exclude": "excluded", "smart_selection_enabled": True})
    plugin._get_task_config = lambda: task
    item = SimpleNamespace(**{**candidate(), "hit_and_run": False, "description": "", "site_name": "test", **changes})
    passed, reason = plugin._SmartBrushFlow__evaluate_conditions_for_brush(item, {})
    assert not passed and expected in reason

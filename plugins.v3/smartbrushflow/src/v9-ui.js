export const profileDefaults = {
  conservative: { selection_min_score: 40, max_add_per_run: 2, deletion_score_threshold: 35, candidate_confirmations: 4, confirmation_minutes: 60, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 2, max_delete_percent_day: 3, max_release_percent_run: 2, max_release_percent_day: 4, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 720, demand_confirmations: 2 },
  balanced: { selection_min_score: 30, max_add_per_run: 5, deletion_score_threshold: 40, candidate_confirmations: 3, confirmation_minutes: 30, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 3, max_delete_percent_day: 5, max_release_percent_run: 4, max_release_percent_day: 8, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 360, demand_confirmations: 2 },
  aggressive: { selection_min_score: 22, max_add_per_run: 8, deletion_score_threshold: 48, candidate_confirmations: 2, confirmation_minutes: 15, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 5, max_delete_percent_day: 10, max_release_percent_run: 8, max_release_percent_day: 15, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 180, demand_confirmations: 2 },
}

export function newTaskV9() {
  return {
    schema_version: 9,
    id: '',
    revision: 1,
    identity: { name: '', site_id: null, downloader: '', save_path: null, tag: null, enabled: true, notify: true },
    schedule: { brush_interval: 10, check_interval: 5, cron: null, active_time_range: null },
    goal: { enabled: false, ratio_target: null, reached_behavior: 'continue' },
    capacity: { limit_gb: null, max_downloads: null, upload_limit_kbps: null, download_limit_kbps: null, torrent_upload_limit_kbps: null, torrent_download_limit_kbps: null },
    selection: { enabled: true, source: 'page', promotion: 'free', exclude_hr: true, site_hr_active: false, exclude_subscriptions: true, size_min_gb: 0.5, size_max_gb: null, seeder_range: null, published_min_minutes: null, published_max_minutes: null, timezone_offset: 0, include: null, exclude: null },
    deletion: { enabled: false, min_seed_hours: null, exclude_tags: null, delete_data: true, invalid_tracker_cleanup: false, invalid_tracker_confirmations: 2, paused: false, observation_started_at: null, observation_until: null, observation_extensions: 0 },
    strategy: { profile: 'balanced', overrides: { ...profileDefaults.balanced } },
    health: { stalled_confirmations: 3, stalled_window_minutes: 30, slow_after_hours: 6, slow_speed_kbps: 128, auto_repair: true, pause_after_failed_repair: true },
  }
}

export function cloneTaskV9(task) {
  const base = newTaskV9()
  if (!task?.identity) return structuredClone(base)
  return structuredClone({
    ...base,
    ...task,
    identity: { ...base.identity, ...task.identity }, schedule: { ...base.schedule, ...task.schedule },
    goal: { ...base.goal, ...task.goal }, capacity: { ...base.capacity, ...task.capacity },
    selection: { ...base.selection, ...task.selection }, deletion: { ...base.deletion, ...task.deletion },
    strategy: { ...base.strategy, ...task.strategy, overrides: { ...base.strategy.overrides, ...(task.strategy?.overrides || {}) } },
    health: { ...base.health, ...task.health },
  })
}

export function normalizeTaskV9(task) {
  const result = cloneTaskV9(task)
  const optionalNumbers = [
    ['goal','ratio_target'], ['capacity','limit_gb'], ['capacity','max_downloads'],
    ['capacity','upload_limit_kbps'], ['capacity','download_limit_kbps'],
    ['capacity','torrent_upload_limit_kbps'], ['capacity','torrent_download_limit_kbps'],
    ['selection','size_min_gb'], ['selection','size_max_gb'],
    ['selection','published_min_minutes'], ['selection','published_max_minutes'],
    ['deletion','min_seed_hours'], ['strategy','overrides','max_release_gb_run'],
    ['strategy','overrides','max_release_gb_day'],
  ]
  optionalNumbers.forEach(path => {
    const parent = path.slice(0, -1).reduce((value, key) => value[key], result)
    const key = path.at(-1)
    const value = parent[key]
    parent[key] = value === '' || value === undefined ? null : value === null ? null : Number(value)
  })
  ;[
    ['identity','save_path'], ['identity','tag'], ['schedule','cron'], ['schedule','active_time_range'],
    ['selection','seeder_range'], ['selection','include'], ['selection','exclude'], ['deletion','exclude_tags'],
  ].forEach(path => {
    const parent = path.slice(0, -1).reduce((value, key) => value[key], result)
    const key = path.at(-1)
    parent[key] = String(parent[key] || '').trim() || null
  })
  return result
}

export function applyProfile(task, profile) {
  if (!profileDefaults[profile]) return { ...task, strategy: { ...task.strategy, profile: 'custom' } }
  return { ...task, strategy: { profile, overrides: { ...profileDefaults[profile] } } }
}

export function profileLabel(profile) {
  return ({ conservative: '保守', balanced: '均衡', aggressive: '冲量', custom: '自定义' })[profile] || '均衡'
}

export function promotionLabel(value) {
  return ({ all: '全部种子', free: '免费种子', '2xfree': '2X免费种子' })[value] || '免费种子'
}

export function taskPreview(task, siteName = '当前站点') {
  const frequency = task.schedule.cron ? `按 ${task.schedule.cron} 计划` : `每${task.schedule.brush_interval}分钟`
  const selection = `${frequency}检查${siteName}${promotionLabel(task.selection.promotion)}，每轮最多新增${task.strategy.overrides.max_add_per_run}个`
  if (!task.deletion.enabled) return `${selection}；自动删种关闭，只监控种子状态。`
  const limit = Number(task.capacity.limit_gb || 0)
  const trigger = limit * Number(task.strategy.overrides.capacity_trigger_percent || 90) / 100
  const target = limit * Number(task.strategy.overrides.capacity_target_percent || 85) / 100
  return `${selection}；容量达到${trigger.toFixed(0)}GB开始安全清理，降到${target.toFixed(0)}GB停止；保种不足${task.deletion.min_seed_hours || 0}小时、正在上传、有真实需求或未完成的种子不会删除。`
}

export function healthTone(level) {
  return ({ error: 'error', warning: 'warning', info: 'info', success: 'success' })[level] || 'secondary'
}

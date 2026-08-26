export const taskDefaults = {
  id: '',
  name: '',
  enabled: true,
  notify: true,
  site_id: null,
  downloader: '',
  brush_interval: 10,
  check_interval: 5,
  cron: null,
  active_time_range: null,
  site_ratio_control: false,
  site_ratio_target: null,
  disksize: null,
  maxupspeed: null,
  maxdlspeed: null,
  maxdlcount: null,
  freeleech: 'free',
  hr: 'yes',
  include: null,
  exclude: null,
  size: null,
  seeder: null,
  timezone_offset: 0,
  pubtime: null,
  seed_time: null,
  hr_seed_time: null,
  seed_ratio: null,
  seed_size: null,
  download_time: null,
  seed_avgspeed: null,
  seed_inactivetime: null,
  min_seed_time: null,
  min_inactivetime: null,
  smart_enabled: false,
  smart_selection_enabled: true,
  smart_adaptive_enabled: true,
  smart_selection_relax_filters: true,
  smart_selection_min_score: 25,
  smart_selection_max_add_per_run: 5,
  smart_min_ratio: 0,
  smart_min_uploaded: null,
  smart_ratio_weight: 18,
  smart_cold_inactive_minutes: 360,
  smart_protect_active_demand: true,
  invalid_seed_cleanup_enabled: false,
  invalid_seed_confirmations: 2,
  smart_score_threshold: 40,
  smart_score_margin: 0,
  smart_max_delete_per_run: 3,
  smart_max_delete_percent_day: 5,
  smart_allow_proactive_delete: true,
  smart_required_conditions: false,
  delete_condition_mode: 'any',
  dynamic_require_conditions: false,
  dynamic_sort_mode: 'smart',
  delete_dry_run: true,
  delete_files: true,
  delete_min_size: null,
  delete_max_size: null,
  delete_size_range: null,
  up_speed: null,
  dl_speed: null,
  auto_archive_days: null,
  save_path: null,
  delete_except_tags: null,
  except_subscribe: true,
  proxy_delete: false,
  del_no_free: false,
  qb_category: null,
  site_hr_active: false,
  site_skip_tips: false,
  rss_support: false,
  tag: null,
}

/** 统一提取宿主 API 客户端与标准响应模型中的业务数据。 */
export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'success')) {
    if (response.success === false) throw new Error(response.message || '操作失败')
    return response.data
  }
  return response?.data ?? response
}

/** 基于完整默认值创建可安全编辑的任务深拷贝。 */
export function cloneTask(task = {}) {
  return JSON.parse(JSON.stringify({ ...taskDefaults, ...(task || {}) }))
}

/** 把表单空值和数字字段标准化为后端请求模型需要的类型。 */
export function normalizeTask(task) {
  const result = cloneTask(task)
  const nullableNumbers = [
    'disksize',
    'maxupspeed',
    'maxdlspeed',
    'maxdlcount',
    'site_ratio_target',
    'seed_time',
    'hr_seed_time',
    'seed_ratio',
    'seed_size',
    'download_time',
    'seed_avgspeed',
    'seed_inactivetime',
    'min_seed_time',
    'min_inactivetime',
    'smart_min_ratio',
    'smart_min_uploaded',
    'smart_selection_min_score',
    'invalid_seed_confirmations',
    'delete_min_size',
    'delete_max_size',
    'up_speed',
    'dl_speed',
    'auto_archive_days',
  ]
  const optionalText = [
    'cron',
    'active_time_range',
    'include',
    'exclude',
    'size',
    'seeder',
    'pubtime',
    'delete_size_range',
    'save_path',
    'delete_except_tags',
    'qb_category',
    'tag',
  ]
  nullableNumbers.forEach(key => {
    const value = result[key] === '' || result[key] === null ? null : Number(result[key])
    result[key] = value === 0 ? null : value
  })
  ;['smart_selection_max_add_per_run', 'smart_score_threshold', 'smart_score_margin', 'smart_max_delete_per_run', 'smart_max_delete_percent_day'].forEach(key => {
    const value = Number(result[key])
    if (Number.isFinite(value)) result[key] = value
  })
  optionalText.forEach(key => {
    result[key] = String(result[key] || '').trim() || null
  })
  if (result.delete_min_size && result.delete_max_size) {
    result.delete_size_range = `${result.delete_min_size}-${result.delete_max_size}`
  }
  result.site_id = Number(result.site_id)
  result.brush_interval = Number(result.brush_interval || 10)
  result.check_interval = Number(result.check_interval || 5)
  result.timezone_offset = Number(result.timezone_offset || 0)
  return result
}

/** 把全局设置中的空值、零值和正数标准化为后端请求类型。 */
export function normalizeSettings(settings = {}) {
  const result = { ...(settings || {}) }
  const limitFields = [
    'global_disksize',
    'global_maxdlcount',
    'global_maxupspeed',
    'global_maxdlspeed',
    'global_delete_min_size',
    'global_delete_max_size',
  ]
  limitFields.forEach(key => {
    const value = Number(result[key] || 0)
    result[key] = value > 0 ? value : null
  })
  result.global_proxy_delete = Boolean(result.global_proxy_delete)
  result.global_delete_size_range = result.global_proxy_delete
    && result.global_delete_min_size
    && result.global_delete_max_size
    ? `${result.global_delete_min_size}-${result.global_delete_max_size}`
    : null
  result.signin_enabled = Boolean(result.signin_enabled)
  result.signin_notify = result.signin_notify !== false
  result.signin_cron = String(result.signin_cron || '17 7 * * *').trim() || '17 7 * * *'
  result.signin_sites = Array.from(
    new Set(
      (Array.isArray(result.signin_sites) ? result.signin_sites : [])
        .map(value => Number(value))
        .filter(value => Number.isInteger(value) && value > 0),
    ),
  )
  return result
}

/** 将字节数格式化为适合紧凑界面展示的容量文本。 */
export function formatBytes(value) {
  const bytes = Number(value || 0)
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const number = bytes / 1024 ** index
  return `${number >= 100 ? number.toFixed(0) : number.toFixed(1)} ${units[index]}`
}

/** 将时间值格式化为当前界面使用的月日与时分。 */
export function formatDateTime(value) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** 计算一次运行记录的秒级耗时。 */
export function formatDuration(startedAt, finishedAt) {
  if (!startedAt || !finishedAt) return '-'
  const seconds = Math.max(Math.round((new Date(finishedAt) - new Date(startedAt)) / 1000), 0)
  return `${seconds} 秒`
}

/** 返回任务状态对应的中文文本、主题色和图标。 */
export function taskStateMeta(state) {
  const states = {
    running: { text: '运行中', color: 'success', icon: 'mdi-check-circle-outline' },
    brush: { text: '正在刷新', color: 'primary', icon: 'mdi-sync' },
    check: { text: '正在检查', color: 'info', icon: 'mdi-progress-check' },
    paused: { text: '已暂停', color: 'secondary', icon: 'mdi-pause-circle-outline' },
    waiting: { text: '等待时段', color: 'warning', icon: 'mdi-clock-outline' },
    waiting_ratio: { text: '待刷流', color: 'warning', icon: 'mdi-target' },
    ratio_unavailable: { text: '等待数据', color: 'info', icon: 'mdi-database-clock-outline' },
    disabled: { text: '插件停用', color: 'secondary', icon: 'mdi-stop-circle-outline' },
    error: { text: '运行异常', color: 'error', icon: 'mdi-alert-circle-outline' },
  }
  return states[state] || states.running
}

/** 根据已下载量和总大小计算种子完成百分比。 */
export function torrentProgress(item) {
  const size = Number(item?.size || 0)
  if (!size) return 0
  return Math.min(Math.round((Number(item.downloaded || 0) * 100) / size), 100)
}

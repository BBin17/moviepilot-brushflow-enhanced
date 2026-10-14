/** Compact task navigation: searching and switching never modify task settings. */
export function taskNavigationItems(tasks = []) {
  return tasks.filter(task => task?.id).map(task => {
    const summary = task.strategy?.ui_summary || {}
    const name = String(task.name || task.site_name || '未命名任务')
    const site = String(task.site_name || '站点未设置')
    const downloader = String(task.downloader || '')
    return {
      id: String(task.id), name, site, downloader,
      displayTitle: site === name ? name : `${name} · ${site}`,
      searchText: [name, site, downloader].join(' '),
      health: summary.health || {},
      needsAttention: ['error', 'warning'].includes(summary.health?.level) || Number(summary.download?.issue_count || 0) > 0,
      enabled: Boolean(task.enabled),
      size: task.seeding_size,
      uploaded: summary.performance?.uploaded_bytes_24h ?? null,
      partialUpload: summary.performance?.observation_complete === false,
    }
  })
}

export function filterTaskNavigation(value, query, item) {
  const text = String(item?.raw?.searchText || value || '').toLocaleLowerCase()
  return text.includes(String(query || '').trim().toLocaleLowerCase())
}

export function taskNavigationSummary(items = []) {
  return {
    total: items.length,
    enabled: items.filter(item => item.enabled).length,
    attention: items.filter(item => item.needsAttention).length,
  }
}

export function adjacentTaskId(items, selectedId, direction) {
  const index = items.findIndex(item => item.id === selectedId)
  const next = index + direction
  return index >= 0 && next >= 0 && next < items.length ? items[next].id : null
}

export function validTaskSelection(items, selectedId, nextId) {
  return typeof nextId === 'string' && nextId !== selectedId && items.some(item => item.id === nextId)
}

/** Workspace wording only; never mutates strategy or configuration. */
export function deletionView(summary = {}, strategy = {}) {
  const deletion = summary.deletion || {}
  const taskPaused = summary.health?.status === 'task_paused'
  const pending = deletion.state === 'pending_evaluation' || !deletion.state
  const title = taskPaused ? '任务暂停，暂不自动淘汰' : !deletion.enabled ? '自动淘汰未启用'
    : strategy.mode === 'shadow' ? '安全观察中，只记录计划'
    : strategy.mode === 'paused' ? '自动淘汰已暂停'
    : pending ? '等待检查种子表现'
    : Number(deletion.candidate_count || 0) > 0 ? '低收益种子等待安全复核' : '暂时没有需要淘汰的种子'
  return {
    title, pending,
    modeLabel: taskPaused ? '任务已暂停' : ({active:'自动淘汰开启',shadow:'安全观察中',paused:'自动淘汰暂停',disabled:'只选种，不淘汰'})[strategy.mode] || '等待检查',
    candidateLabel: pending ? '待检查' : String(deletion.candidate_count || 0),
    protectedLabel: pending ? '待检查' : String(deletion.protected_count || 0),
    rule: deletion.idle_zero_upload_hours
      ? '连续' + deletion.idle_zero_upload_hours + '小时零上传，满足保种和安全条件后主动淘汰。'
      : '长期零上传规则未启用；按近期真实收益和安全条件评估。',
    safety: deletion.min_seed_hours
      ? '最低保种' + deletion.min_seed_hours + '小时，未完成、H&R、正在上传和有效连接始终保护。'
      : '最低保种尚未设置，请完善安全设置；不会绕过保种保护。',
  }
}

export function runPresentation(run = {}) {
  const selection = run.kind === 'brush'
  const title = selection ? '选种' : run.force_cleanup ? '手动安全清理' : '种子检查'
  const failed = run.success === false
  const metrics = selection
    ? '新增 ' + (run.added_count || 0) + ' · 过滤 ' + (run.filtered_count || 0)
    : '活跃 ' + (run.active_count || 0) + ' · 候选 ' + (run.deletion_candidate_count || 0) + ' · 删除 ' + (run.deleted_count || 0)
  const deletionCompleted = Number(run.deleted_count || 0) > 0
  return {
    title, metrics,
    result: failed ? '失败' : run.success === true ? '完成' : '运行记录',
    tone: failed ? 'error' : 'success',
    explanation: deletionCompleted
      ? '本次已删除 ' + run.deleted_count + ' 个通过最终安全复核的种子。' + (failed ? '其余处理未完成，请查看错误提示。' : '完整执行结果保留在审计记录中。')
      : run.deletion_message || '',
    error: run.error || '',
  }
}

const reasons = {
  tracker_demand_unknown:'站点未提供下载人数',tracker_seeders_unknown:'站点未提供做种人数',
  trusted_download_demand:'当前有人下载',trusted_scarcity:'完整做种较少',promotion:'有促销',fresh:'发布较新',
  demand_unknown:'需求趋势尚未形成',demand_stable:'需求暂时稳定',demand_rising:'下载需求正在增长',
  demand_falling:'下载需求正在减少',demand_competition_rising:'做种竞争增长较快',
  completion_time_unknown:'下载速度样本不足，完成时间未知',completion_window_risk:'预计下载较久，可能错过需求',
  minimum_seed_commitment:'已考虑最低保种期间的空间占用',promotion_finishes_too_soon:'免费期已结束或预计来不及完成',
  no_observed_demand:'当前没有观察到下载需求',full_source_unconfirmed:'站点显示无完整做种，下载来源待确认',
  exploration_not_suitable:'不适合低风险试探',exploration_limit:'本轮最多试探1个无明确需求的小种',
  download_backlog_unhealthy:'已有下载多数异常，先处理后再新增',download_backlog_limited:'已有异常下载，本轮减少新增',
  round_selection_limit:'本轮名额留给更优候选',below_selection_threshold:'综合机会低于门槛',
  large_without_trusted_demand:'大种的相对需求不足',oversized_for_task:'单种占任务容量过大',
  medium_no_demand_requires_double_free:'中型无需求种需要免费双倍',medium_no_demand_cold_start:'中型无需求种缺少收益证据',
  medium_no_demand_below_learned_median:'同类历史收益未达到任务参考水平',baseline:'基础规则',
  similar_torrents_unproductive:'足量同类样本多数没有上传，降低优先级',
}
export const contributionLabels = {base:'基础',promotion:'促销',demand:'当前需求',competition:'做种竞争',scarcity:'稀缺性',freshness:'新鲜度',local_yield:'真实收益学习',size_efficiency:'体积效率',capacity_cost:'空间占用',demand_trend:'需求变化',completion_risk:'完成时间风险',minimum_seed_cost:'最低保种成本',no_demand_risk:'无需求风险',source_risk:'来源风险',historical_failure_risk:'同类低收益风险'}
export function selectionReasonText(codes){return (codes||[]).map(code=>reasons[code]||'其他策略条件').join('；')||'暂无补充原因'}
export function selectionStatus(item){
  return ({added:'已添加',add_failed:'添加失败',blocked:'执行时被拦截',waiting:'本轮等待',planned:'待添加',qualified:'评分通过',rejected:'暂不选择'})[item.status] || (item.selected?'评分通过（旧记录）':'未选择（旧记录）')
}
export function etaText(value){return value===null||value===undefined||!Number.isFinite(Number(value))?'待积累速度样本':Number(value)<1?`约 ${Math.max(1,Math.round(Number(value)*60))} 分钟`:`约 ${Number(value).toFixed(1)} 小时`}
export function feedbackText(feedback={}){
  const count=Number(feedback.sample_count||0)
  return count?`已完整验收 ${count} 个独立种子，其中 ${Number(feedback.productive_count||0)} 个在加入后24小时内有上传。`:'正在积累完整的加入后24小时观测，不把缺失数据当零收益。'
}

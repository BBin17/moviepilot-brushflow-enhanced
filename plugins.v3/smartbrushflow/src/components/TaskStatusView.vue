<script setup>
import { computed } from 'vue'
import TaskPerformance from './TaskPerformance.vue'
import { formatBytes } from '../utils'
import { healthTone } from '../v9-ui'
import { deletionView } from '../workspace-ui'
const props = defineProps({ summary: {type:Object,default:()=>({})}, strategy: {type:Object,default:()=>({})}, loading:Boolean, busy:Boolean })
defineEmits(['inspect','action'])
const decision = computed(() => deletionView(props.summary, props.strategy))
</script>

<template>
  <section class="status-view" aria-label="任务表现与淘汰决策" :aria-busy="loading">
    <header class="status-verdict">
      <div class="status-verdict__message"><VIcon :icon="({error:'mdi-alert-circle-outline',warning:'mdi-alert-circle-outline',info:'mdi-clock-outline',success:'mdi-check-circle-outline'})[summary.health?.level] || 'mdi-clock-outline'" :color="healthTone(summary.health?.level)" size="25"/>
        <div><span class="eyebrow">当前结论</span><h2>{{ summary.health?.title || '正在读取任务' }}</h2><p>{{ summary.health?.message || '检查后展示实际表现和下一步。' }}</p></div>
      </div>
      <div v-if="summary.recommended_actions?.length" class="status-verdict__actions">
        <VBtn v-for="action in summary.recommended_actions" :key="action.code" :color="action.tone || 'primary'" size="small" variant="tonal"
          :disabled="action.enabled === false || loading || busy" @click="$emit('action',action)">{{ action.label }}</VBtn>
      </div>
    </header>

    <section class="status-section status-section--performance"><div class="section-heading"><h3>上传与保种表现</h3><span>真实增量 · 最近24小时</span></div>
      <TaskPerformance :performance="summary.performance || {}" :loading="loading" @inspect="$emit('inspect','income')"/>
    </section>

    <div class="status-columns">
      <section class="status-section status-section--decisions">
        <div class="section-heading"><h3>留种与淘汰</h3><VChip size="x-small" variant="tonal">{{ decision.modeLabel }}</VChip></div>
        <h4>{{ decision.title }}</h4><p>{{ summary.deletion?.message || '获取实际上传和做种记录后判断，不会把未知数据当作零收益。' }}</p>
        <div class="decision-totals">
          <button type="button" :disabled="loading" @click="$emit('inspect','deletion')"><span>待淘汰</span><strong>{{ decision.candidateLabel }}<small v-if="!decision.pending"> 个</small></strong><small v-if="!decision.pending">任务体积 {{ formatBytes(summary.deletion?.candidate_bytes) }}</small><em>查看名单与原因 <VIcon icon="mdi-chevron-right" size="15"/></em></button>
          <button type="button" :disabled="loading" @click="$emit('inspect','protection')"><span>继续保留 / 受保护</span><strong>{{ decision.protectedLabel }}<small v-if="!decision.pending"> 个</small></strong><small v-if="!decision.pending">任务体积 {{ formatBytes(summary.deletion?.protected_bytes) }}</small><em>查看保护原因 <VIcon icon="mdi-chevron-right" size="15"/></em></button>
        </div>
        <p class="rule-note">{{ decision.rule }}空间充足也会处理，不等待GB释放额度。</p>
        <details v-if="strategy.deletion_blockers?.length" class="protection-details"><summary>主要保留原因 <span>{{ strategy.deletion_blockers.length }} 类</span></summary>
          <ul><li v-for="reason in strategy.deletion_blockers" :key="reason.code"><span>{{ reason.label }}</span><strong>{{ reason.count }} 个</strong></li></ul><small>同一种子可能命中多个原因，上方种子总数已去重。</small>
        </details>
        <div class="safety-note"><VIcon icon="mdi-shield-check-outline" size="18"/><span>{{ decision.safety }}排除标签同样有效。</span></div>
      </section>

      <aside class="status-section status-section--activity" aria-label="自动运行摘要">
        <div class="section-heading"><h3>自动运行</h3><span>点击查看详情</span></div>
        <button type="button" class="activity-row" :disabled="loading" @click="$emit('inspect','selection')"><VIcon icon="mdi-radar" size="22" color="primary"/><div><strong>选种 <span>最近新增 {{ summary.selection?.added_count || 0 }} 个</span></strong><p>{{ summary.selection?.source_checked ? '看到 ' + (summary.selection.candidate_count || 0) + ' 个候选，过滤 ' + (summary.selection.filtered_count || 0) + ' 个。' : '本轮尚未进入站点选种。' }}</p><small>{{ summary.selection?.version_note || summary.selection?.main_reason || '按需求、竞争和历史收益继续选种。' }}</small></div><VIcon icon="mdi-chevron-right" size="18"/></button>
        <button type="button" class="activity-row" :disabled="loading" @click="$emit('inspect','download')"><VIcon icon="mdi-download-outline" size="22" :color="summary.download?.issue_count ? 'warning' : 'success'"/><div><strong>下载 <span>{{ summary.download?.issue_count || 0 }} 个需关注</span></strong><p>超时 {{ summary.download?.overdue_count || 0 }} · 卡住 {{ summary.download?.stalled_count || 0 }} · 低速 {{ summary.download?.slow_count || 0 }}</p><small>未完成数据不会自动删除，异常可逐个处理。</small></div><VIcon icon="mdi-chevron-right" size="18"/></button>
        <div class="activity-row activity-row--space"><VIcon icon="mdi-harddisk" size="22" color="primary"/><div><strong>任务空间 <span>{{ summary.capacity?.percent === null || summary.capacity?.percent === undefined ? '未设上限' : summary.capacity.percent + '%' }}</span></strong><p>{{ formatBytes(summary.capacity?.current_bytes) }} / {{ summary.capacity?.limit_bytes ? formatBytes(summary.capacity.limit_bytes) : '未设置' }}</p><VProgressLinear :model-value="Math.min(summary.capacity?.percent || 0,100)" :color="(summary.capacity?.percent || 0)>100 ? 'error' : 'primary'" height="4" rounded/><small>只限制新增，不设清理停止线。</small></div></div>
        <p class="released-note">过去24h已释放 <strong>{{ formatBytes(strategy.actual_freed_bytes_24h) }}</strong><small>仅统计下载器已确认移除且删除数据的记录。</small></p>
      </aside>
    </div>

    <details class="strategy-details"><summary>策略与学习详情 <span>专业数据，按需展开</span></summary><div class="strategy-facts"><span>引擎 {{ strategy.engine_version || '—' }}</span><span>样本 {{ strategy.learning_sample_count || 0 }}</span><span>学习置信度 {{ ((strategy.learning_confidence || 0)*100).toFixed(0) }}%</span><span>误判率 {{ ((strategy.false_positive_rate || 0)*100).toFixed(1) }}%</span></div><p>近期单位容量上传收益决定保留价值；连续零上传仍需完整观测和连续确认。每个种子在真正删除前重新检查安全数据，先记录审计再执行。</p><p>每次检查逐个处理最多5个合格种子，剩余在后续检查继续；这是下载器请求批次，不是每日数量或GB释放限额。</p></details>
  </section>
</template>

<style scoped>
.status-view{color:rgb(var(--v-theme-on-surface))}.status-view h2,.status-view h3,.status-view h4,.status-view p{margin:0}.status-view p{font-size:.86rem;line-height:1.65;color:rgba(var(--v-theme-on-surface),.75)}.status-view h2{font-size:1.15rem;line-height:1.4}.status-view h3{font-size:.96rem}.status-view h4{font-size:.92rem;margin-bottom:6px}
.status-verdict{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:22px 24px;background:rgba(var(--v-theme-primary),.045)}.status-verdict__message{display:flex;align-items:flex-start;gap:12px;min-width:0}.status-verdict__message>.v-icon{margin-top:4px}.eyebrow{display:block;font-size:.72rem;color:rgba(var(--v-theme-on-surface),.6);margin-bottom:4px}.status-verdict__actions{display:flex;flex-wrap:wrap;gap:8px;flex-shrink:0;max-width:38%}.status-verdict p{margin-top:5px}
.status-section{padding:22px 24px}.status-section--performance{border-bottom:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:16px}.section-heading>span{font-size:.72rem;color:rgba(var(--v-theme-on-surface),.6)}
.status-columns{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr)}.status-section--activity{border-inline-start:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.decision-totals{display:grid;grid-template-columns:1fr 1fr;margin:18px 0}.decision-totals button{display:flex;flex-direction:column;align-items:flex-start;gap:5px;padding:8px 14px 8px 0;color:inherit;text-align:start;min-width:0;cursor:pointer}.decision-totals button+button{padding-inline-start:20px;border-inline-start:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.decision-totals span{font-size:.8rem;color:rgba(var(--v-theme-on-surface),.7)}.decision-totals strong{font-size:1.7rem;line-height:1.35}.decision-totals small{font-size:.73rem;font-weight:400;color:rgba(var(--v-theme-on-surface),.65)}.decision-totals em{font-style:normal;font-size:.76rem;color:rgb(var(--v-theme-primary))}.decision-totals button:hover em{text-decoration:underline}.decision-totals button:disabled,.activity-row:disabled{opacity:.5;cursor:wait}
.rule-note{font-size:.76rem!important}.safety-note{display:flex;align-items:flex-start;gap:7px;margin-top:16px;font-size:.76rem;line-height:1.6;color:rgba(var(--v-theme-on-surface),.68)}.safety-note>.v-icon{flex-shrink:0;color:rgb(var(--v-theme-success))}.protection-details{margin-top:16px}.protection-details summary,.strategy-details summary{cursor:pointer;font-size:.82rem;font-weight:500;line-height:1.5}.protection-details summary>span,.strategy-details summary>span{font-weight:400;font-size:.72rem;margin-inline-start:8px;color:rgba(var(--v-theme-on-surface),.55)}.protection-details ul{list-style:none;padding:8px 0;margin:0}.protection-details li{display:flex;justify-content:space-between;gap:12px;padding:4px 0;font-size:.78rem}.protection-details li strong{white-space:nowrap}.protection-details>small{font-size:.72rem;color:rgba(var(--v-theme-on-surface),.6)}
.activity-row{display:flex;align-items:flex-start;gap:12px;width:100%;text-align:start;padding:14px 0;color:inherit;border-bottom:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.activity-row:first-of-type{padding-top:0}.activity-row>div{flex:1;min-width:0}.activity-row strong{display:flex;justify-content:space-between;gap:12px;font-size:.85rem}.activity-row strong>span{font-size:.77rem;font-weight:400;color:rgba(var(--v-theme-on-surface),.7);text-align:end}.activity-row p{margin-top:5px;font-size:.8rem}.activity-row small{display:block;font-size:.73rem;line-height:1.6;color:rgba(var(--v-theme-on-surface),.6)}button.activity-row{cursor:pointer}button.activity-row:hover{color:rgb(var(--v-theme-primary))}.activity-row--space{border-bottom:0}.activity-row--space .v-progress-linear{margin:8px 0}.released-note{font-size:.76rem!important;margin-top:12px!important}.released-note>small{display:block;font-size:.7rem;color:rgba(var(--v-theme-on-surface),.55)}
.strategy-details{padding:18px 24px;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.strategy-details p{margin-top:10px;font-size:.78rem}.strategy-facts{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:14px;font-size:.78rem;color:rgba(var(--v-theme-on-surface),.7)}
@media(max-width:959px){.status-columns{grid-template-columns:1fr}.status-section--activity{border-inline-start:0;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.status-verdict{align-items:flex-start;flex-direction:column;gap:12px}.status-verdict__actions{max-width:none}.section-heading>span{max-width:55%;text-align:end}}
@media(max-width:599px){.status-section,.status-verdict{padding:18px 16px}.strategy-details{padding:16px}.status-verdict h2{font-size:1.05rem}.decision-totals button+button{padding-inline-start:12px}.decision-totals strong{font-size:1.5rem}.status-verdict__actions{width:100%}.status-verdict__actions>*{max-width:100%}.strategy-details summary>span{display:block;margin-inline-start:16px}.status-view button:focus-visible{outline:2px solid rgb(var(--v-theme-primary));outline-offset:3px}}
</style>

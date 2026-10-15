<script setup>
import { computed } from 'vue'
import { formatBytes } from '../utils'
import { contributionLabels, etaText, feedbackText, selectionReasonText, selectionStatus } from '../selection-ui'
const props=defineProps({items:{type:Array,default:()=>[]},policy:{type:Object,default:()=>({})},feedback:{type:Object,default:()=>({})}})
defineEmits(['download'])
const context=computed(()=>props.policy.download_context||{})
</script>
<template>
  <section class="selection-insight" aria-label="选种机会与收益验收">
    <p>先看真实需求与竞争变化，再考虑下载耗时、最低保种占用和同类实际收益。评分通过不代表已经添加。</p>
    <div class="feedback"><strong>选种后验收 · 最近30天加入</strong><p>{{ feedbackText(feedback) }}</p><small v-if="feedback.sample_count">首24小时零上传 {{ feedback.zero_upload_count||0 }} 个 · 同期上传合计 {{ formatBytes(feedback.uploaded_bytes_24h) }} · 学习权重 {{ ((feedback.confidence||0)*100).toFixed(0) }}%</small><small>样本按独立种子计算；重复检查不会增加样本。6 / 24 / 72小时窗口分别验收，观测断档不用于训练。</small></div>
    <div v-if="context.reason" class="backlog"><p>{{ selectionReasonText([context.reason]) }}。本轮最多新增 {{ context.max_add }} 个。</p><VBtn size="small" variant="tonal" @click="$emit('download')">查看下载健康</VBtn></div>
    <p class="subtle">完成时间只是本任务历史速度估算，不保证完成或上传；缺少可靠速度、促销时区或历史样本时明确按未知处理。</p>
    <div class="choices"><article v-for="item in items" :key="item.key||item.title">
      <header><strong>{{ item.title||'未知候选' }}</strong><VChip :color="item.status==='added'?'success':item.status==='add_failed'?'error':'default'" size="small" variant="tonal">{{ selectionStatus(item) }}</VChip></header>
      <p>{{ item.execution_reason || selectionReasonText(item.reasons) }}</p>
      <div class="facts"><span v-if="item.size">体积 {{ formatBytes(item.size) }}</span><span>预计下载 {{ etaText(item.eta_hours) }}</span><span v-if="item.minimum_seed_gb_hours">最低保种占用 {{ Number(item.minimum_seed_gb_hours).toFixed(0) }} GB·小时</span><span v-if="item.trend?.observations">趋势观测 {{ item.trend.observations }} 次 / {{ item.trend.span_minutes||0 }} 分钟</span><span v-if="item.exploratory">小规模试探</span></div>
      <details><summary>评分与依据 · {{ Number(item.score||0).toFixed(1) }} 分</summary><div class="scores"><span v-for="(value,key) in item.contributions" :key="key">{{ contributionLabels[key]||key }} <strong>{{ Number(value)>0?'+':'' }}{{ Number(value).toFixed(1) }}</strong></span></div><p v-if="item.learning">同类有效样本 {{ item.learning.matched_count||0 }} 个 · 当前学习权重 {{ ((item.confidence||0)*100).toFixed(0) }}%。样本少时以固定规则为主。</p></details>
    </article></div>
    <p v-if="!items.length" class="empty">最近没有可展示的评分候选；容量、硬过滤或下载健康也可能阻止进入选种，请结合概览的主要原因查看。</p>
  </section>
</template>
<style scoped>
.selection-insight{font-size:.85rem;line-height:1.7}.selection-insight p{margin:0}.feedback{margin:16px 0;padding:14px;background:rgba(var(--v-theme-primary),.06);border-radius:8px}.feedback strong{font-size:.88rem}.feedback p{margin-top:4px}.feedback small,.subtle{display:block;color:rgba(var(--v-theme-on-surface),.65);font-size:.75rem}.backlog{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.choices article{border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity));padding:16px 0}.choices header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.choices header strong{overflow-wrap:anywhere;min-width:0;font-size:.86rem}.choices header .v-chip{flex-shrink:0}.choices article>p{margin-top:5px;font-size:.78rem;color:rgba(var(--v-theme-on-surface),.75)}.facts{display:flex;gap:4px 18px;flex-wrap:wrap;margin-top:8px;color:rgba(var(--v-theme-on-surface),.65);font-size:.74rem}details{margin-top:10px;font-size:.76rem}summary{cursor:pointer;color:rgb(var(--v-theme-primary))}.scores{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;margin:10px 0}.scores span{display:flex;justify-content:space-between}.empty{padding:20px 0;color:rgba(var(--v-theme-on-surface),.65)}@media(max-width:599px){.choices header,.backlog{flex-direction:column;gap:8px}.facts{display:grid;grid-template-columns:1fr}.scores{gap:4px 12px}}
</style>

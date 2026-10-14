<script setup>
import { formatBytes } from '../utils'
defineProps({ performance: { type: Object, default: () => ({}) }, loading: Boolean })
defineEmits(['inspect'])
</script>

<template>
  <section class="performance" aria-label="上传收益和保种情况">
    <div><span>过去 24 小时上传</span><strong>{{ loading ? '—' : performance.uploaded_bytes_24h === undefined ? '待统计' : formatBytes(performance.uploaded_bytes_24h) }}</strong><small>{{ performance.observation_complete ? '完整观测窗口' : `部分观测 · ${performance.partial_window_count || 0} 个窗口尚不完整` }}</small></div>
    <div><span>有上传的种子</span><strong>{{ performance.productive_count || 0 }}<em> / {{ performance.active_count || 0 }}</em></strong><small>近期真正贡献上传</small></div>
    <div><span>已达到最低保种时长</span><strong>{{ performance.minimum_met_count || 0 }}<em> 个</em></strong><small>{{ performance.minimum_pending_count || 0 }} 个完成种子仍在保种</small></div>
    <button type="button" :disabled="loading" @click="$emit('inspect')"><span>已达保种 · 24 小时零上传</span><strong>{{ formatBytes(performance.zero_upload_bytes) }}</strong><small>{{ performance.zero_upload_count || 0 }} 个 · 查看原因 <VIcon icon="mdi-chevron-right" size="14"/></small></button>
    <p v-if="performance.observation_complete&&performance.tracker_demand_count>0&&performance.connected_count===0&&performance.productive_count===0" class="connection-note">Tracker 显示下载需求，但当前没有有效连接且近期零上传；若轮换种子后仍无改善，可核查下载器端口与 Tracker 连通性。</p>
  </section>
</template>

<style scoped>
.performance{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}.performance>div,.performance>button{display:flex;flex-direction:column;gap:6px;min-width:0;padding:4px 18px;border-inline-end:1px solid rgba(var(--v-border-color),var(--v-border-opacity));text-align:start;color:inherit}.performance>div:first-child{padding-inline-start:0}.performance>button{cursor:pointer;border-inline-end:0;padding-inline-end:0}.performance>button:hover small{color:rgb(var(--v-theme-primary))}.performance>button:disabled{opacity:.5;cursor:wait}.performance span,.performance small{color:rgba(var(--v-theme-on-surface),.67);font-size:.75rem;line-height:1.5}.performance strong{font-size:1.65rem;line-height:1.25;overflow-wrap:anywhere}.performance em{font-size:.9rem;font-style:normal;font-weight:400}.performance small{font-size:.72rem}.connection-note{grid-column:1/-1;margin:16px 0 0;padding:10px 12px;font-size:.76rem;line-height:1.6;border-inline-start:2px solid rgb(var(--v-theme-warning));color:rgba(var(--v-theme-on-surface),.75)}
@media(max-width:959px){.performance{grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 0}.performance>div,.performance>button{padding:2px 14px}.performance>div:nth-child(3){padding-inline-start:0}.performance>div:nth-child(2){border-inline-end:0}.connection-note{margin-top:0}}
@media(max-width:599px){.performance strong{font-size:1.35rem}.performance span{font-size:.73rem}.performance>div,.performance>button{gap:5px}.performance>button:focus-visible{outline:2px solid rgb(var(--v-theme-primary));outline-offset:3px}}
</style>

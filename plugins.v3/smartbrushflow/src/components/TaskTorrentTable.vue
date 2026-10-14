<script setup>
import { useDisplay } from 'vuetify'
import { formatBytes, torrentProgress } from '../utils'
defineProps({ torrents: { type: Object, default: () => ({items:[],total:0,page:1,page_size:50}) }, state: String, sort: String, filter: String, loading: Boolean })
defineEmits(['state','sort','filter','page','inspect'])
const display = useDisplay()
function seedTime(item) { return item.seeding_hours == null ? '未知' : item.seeding_hours + '小时' }
function upload(item) { return item.upload_coverage_hours_24h > 0 ? formatBytes(item.upload_delta_24h) : '待观测' }
function stateLabel(item) { return item.deleted ? '已移除' : item.download_overdue ? '下载超时' : item.download_health_label || (item.completed ? '已完成' : torrentProgress(item) + '%') }
function stateTone(item) { return item.download_overdue ? 'warning' : item.deleted ? 'secondary' : item.completed ? 'success' : 'default' }
</script>

<template>
  <section class="seed-panel" aria-label="托管种子表现" :aria-busy="loading">
    <header><div><h3>种子表现</h3><p>共 {{ torrents.total || 0 }} 个 · 保种按下载器实际时间计算</p></div><VBtnToggle :model-value="state" mandatory density="compact" @update:model-value="$emit('state',$event)"><VBtn value="active">当前</VBtn><VBtn value="deleted">已移除</VBtn><VBtn value="all">全部</VBtn></VBtnToggle></header>
    <div class="seed-filters">
      <div><span>筛选种子</span><VSelect :model-value="filter" aria-label="筛选种子" variant="outlined" density="compact" hide-details :items="[{title:'全部种子',value:'all'},{title:'已达保种 · 24h零上传',value:'zero_upload'},{title:'已满足最低保种',value:'min_seed_met'},{title:'下载需要处理',value:'download_issues'},{title:'待淘汰种子',value:'candidates'},{title:'受保护 / 继续保留',value:'protected'}]" @update:model-value="$emit('filter',$event)"/></div>
      <div><span>显示顺序</span><VSelect :model-value="sort" aria-label="种子排序" variant="outlined" density="compact" hide-details :items="[{title:'最近添加',value:'newest'},{title:'单位容量收益最低优先',value:'yield'},{title:'体积最大优先',value:'size'},{title:'保种时间最长优先',value:'seed_time'}]" @update:model-value="$emit('sort',$event)"/></div>
      <VBtn v-if="filter === 'download_issues'" variant="tonal" color="warning" :disabled="loading" @click="$emit('inspect','download')">处理下载异常</VBtn>
    </div>
    <VProgressLinear v-if="loading" indeterminate height="2" color="primary"/>
    <div class="seed-desktop"><table><thead><tr><th>种子 / 加入时间</th><th>体积</th><th>实际保种</th><th>24h上传</th><th>累计上传</th><th>分享率</th><th>下载状态</th></tr></thead><tbody><tr v-for="item in torrents.items" :key="item.hash"><td><strong :title="item.title">{{ item.title || item.hash }}</strong><small>已加入 {{ Number(item.age_hours || 0).toFixed(0) }} 小时</small><small v-if="item.retention_labels?.length" class="seed-retention">{{ item.retention_labels.join(' · ') }}</small></td><td>{{ formatBytes(item.size) }}</td><td><span :class="{met:item.min_seed_met}">{{ seedTime(item) }}</span><small>{{ item.min_seed_met ? '已满足保种' : '最低 ' + (item.min_seed_hours || '未设置') + ' 小时' }}</small></td><td>{{ upload(item) }}<small v-if="!item.upload_window_observed_24h">观测 {{ Number(item.upload_coverage_hours_24h || 0).toFixed(1) }}h</small></td><td>{{ item.uploaded == null ? '未知' : formatBytes(item.uploaded) }}</td><td>{{ item.ratio == null ? '—' : Number(item.ratio).toFixed(2) }}</td><td><VChip size="x-small" variant="tonal" :color="stateTone(item)">{{ stateLabel(item) }}</VChip></td></tr></tbody></table></div>
    <div class="seed-mobile"><article v-for="item in torrents.items" :key="item.hash"><header><strong>{{ item.title || item.hash }}</strong><VChip size="x-small" variant="tonal" :color="stateTone(item)">{{ stateLabel(item) }}</VChip></header>
      <dl class="seed-mobile__metrics"><div><dt>实际保种</dt><dd :class="{met:item.min_seed_met}">{{ seedTime(item) }}<small>{{ item.min_seed_met ? '已满足保种' : '最低 ' + (item.min_seed_hours || '未设置') + ' 小时' }}</small></dd></div><div><dt>24h上传</dt><dd>{{ upload(item) }}<small v-if="!item.upload_window_observed_24h">已观测 {{ Number(item.upload_coverage_hours_24h || 0).toFixed(1) }}h</small></dd></div><div><dt>体积</dt><dd>{{ formatBytes(item.size) }}</dd></div><div><dt>分享率</dt><dd>{{ item.ratio == null ? '—' : Number(item.ratio).toFixed(2) }}</dd></div></dl>
      <p v-if="item.retention_labels?.length" class="seed-retention">{{ item.retention_labels.join(' · ') }}</p>
      <details><summary>更多数据与完整名称</summary><p>{{ item.title || item.hash }}</p><small>累计上传 {{ item.uploaded == null ? '未知' : formatBytes(item.uploaded) }} · 已加入 {{ Number(item.age_hours || 0).toFixed(0) }} 小时</small></details>
    </article></div>
    <p v-if="!torrents.items?.length" class="seed-empty">{{ loading ? '正在读取种子…' : '当前筛选下没有种子' }}</p>
    <VPagination v-if="torrents.total > torrents.page_size" :model-value="torrents.page" :length="Math.ceil(torrents.total/torrents.page_size)" :total-visible="display.xs.value ? 3 : 5" @update:model-value="$emit('page',$event)"/>
  </section>
</template>

<style scoped>
.seed-panel{padding:22px 24px;min-width:0}.seed-panel>header{display:flex;align-items:center;justify-content:space-between;gap:12px}.seed-panel h3{margin:0;font-size:.98rem}.seed-panel p{margin:4px 0 0}.seed-panel>header p,.seed-panel small{display:block;font-size:.73rem;color:rgba(var(--v-theme-on-surface),.65);line-height:1.55}.seed-filters{display:flex;align-items:flex-end;gap:12px;margin:18px 0}.seed-filters>div{min-width:0;flex:1;max-width:330px}.seed-filters>div>span{display:block;font-size:.73rem;color:rgba(var(--v-theme-on-surface),.65);margin-bottom:5px}
.seed-desktop{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.8rem;white-space:nowrap}th,td{text-align:start;padding:13px 10px;border-bottom:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}th{font-weight:500;color:rgba(var(--v-theme-on-surface),.65)}td:first-child{min-width:200px;max-width:330px}td strong{display:block;overflow:hidden;text-overflow:ellipsis;max-width:330px}.met{color:rgb(var(--v-theme-success))}.seed-empty{padding:28px 0;text-align:center;font-size:.84rem;color:rgba(var(--v-theme-on-surface),.65)}.seed-mobile{display:none}.seed-retention{font-size:.74rem!important;color:rgba(var(--v-theme-on-surface),.7);line-height:1.6;margin:6px 0!important;white-space:normal}
@media(max-width:959px){.seed-panel{padding:18px 16px}.seed-panel>header{align-items:flex-start;flex-direction:column}.seed-desktop{display:none}.seed-mobile{display:block}.seed-mobile article{padding:18px 0;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.seed-mobile article>header{display:flex;align-items:flex-start;gap:10px;justify-content:space-between}.seed-mobile article>header>strong{font-size:.86rem;line-height:1.55;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-width:0}.seed-mobile article>header>.v-chip{flex-shrink:0}.seed-mobile__metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px 20px;margin:14px 0}.seed-mobile dt{font-size:.72rem;color:rgba(var(--v-theme-on-surface),.6)}.seed-mobile dd{font-size:.85rem;margin:3px 0 0}.seed-mobile details{font-size:.75rem}.seed-mobile summary{cursor:pointer;color:rgb(var(--v-theme-primary))}.seed-mobile details p{overflow-wrap:anywhere;font-size:.8rem;line-height:1.6;margin:8px 0}.seed-filters{flex-wrap:wrap}.seed-filters>div{max-width:none;flex-basis:calc(50% - 6px)}}
@media(max-width:599px){.seed-filters>div{flex-basis:100%}.seed-filters>button{width:100%}}
</style>

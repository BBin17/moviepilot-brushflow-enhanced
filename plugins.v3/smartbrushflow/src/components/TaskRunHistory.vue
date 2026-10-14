<script setup>
import { computed } from 'vue'
import { useDisplay } from 'vuetify'
import { formatBytes, formatDateTime } from '../utils'
import { runPresentation } from '../workspace-ui'
const props = defineProps({ events: {type:Object,default:()=>({items:[],total:0,page:1,page_size:20})}, loading:Boolean })
defineEmits(['page'])
const display = useDisplay()
const rows = computed(() => (props.events.items || []).map(run => ({...run,view:runPresentation(run)})))
</script>
<template>
  <section class="run-history" aria-label="任务运行记录" :aria-busy="loading">
    <header><div><h3>运行记录</h3><p>共 {{ events.total || 0 }} 条 · 查看每次选种和检查的实际结果</p></div><span v-if="events.total">第 {{ events.page || 1 }} 页</span></header>
    <VProgressLinear v-if="loading" indeterminate height="2" color="primary"/>
    <ol><li v-for="(run,index) in rows" :key="run.id || index"><VIcon :icon="run.view.tone === 'error' ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline'" :color="run.view.tone" size="20"/><div class="run-history__body"><div class="run-history__title"><strong>{{ run.view.title }}</strong><time>{{ formatDateTime(run.started_at) }}</time><VChip size="x-small" :color="run.view.tone" variant="tonal">{{ run.view.result }}</VChip></div><p>{{ run.view.metrics }}<span v-if="run.freed_bytes"> · 释放 {{ formatBytes(run.freed_bytes) }}</span></p><details v-if="run.view.explanation || run.view.error"><summary>查看本次说明</summary><p>{{ run.view.explanation }}</p><p v-if="run.view.error" class="run-history__error">{{ run.view.error }}</p></details></div></li></ol>
    <p v-if="!rows.length" class="run-history__empty">{{ loading ? '正在读取运行记录…' : '暂无运行记录，首次执行后会在这里显示。' }}</p>
    <VPagination v-if="events.total > events.page_size" :model-value="events.page" :length="Math.ceil(events.total/events.page_size)" :total-visible="display.xs.value ? 3 : 5" @update:model-value="$emit('page',$event)"/>
  </section>
</template>
<style scoped>
.run-history{padding:22px 24px}.run-history h3,.run-history p{margin:0}.run-history header{display:flex;justify-content:space-between;gap:14px;align-items:center}.run-history h3{font-size:.98rem}.run-history header p,.run-history header>span{font-size:.75rem;color:rgba(var(--v-theme-on-surface),.65);margin-top:4px}.run-history ol{list-style:none;padding:0;margin:18px 0 0}.run-history li{display:flex;gap:12px;padding:17px 0;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.run-history__body{flex:1;min-width:0}.run-history__title{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.run-history__title strong{font-size:.9rem}.run-history time{font-size:.76rem;color:rgba(var(--v-theme-on-surface),.65);margin-inline-start:auto}.run-history__body>p{font-size:.8rem;line-height:1.7;margin-top:6px}.run-history details{margin-top:7px;font-size:.76rem}.run-history summary{cursor:pointer;color:rgb(var(--v-theme-primary))}.run-history details p{margin-top:8px;line-height:1.65;color:rgba(var(--v-theme-on-surface),.7);overflow-wrap:anywhere}.run-history details p.run-history__error{color:rgb(var(--v-theme-error))}.run-history__empty{padding:28px 0;text-align:center;color:rgba(var(--v-theme-on-surface),.65);font-size:.85rem}@media(max-width:599px){.run-history{padding:18px 16px}.run-history li{gap:9px}.run-history__title{gap:6px}.run-history time{font-size:.7rem}.run-history header{align-items:flex-start}}
</style>

<script setup>
import { computed } from 'vue'
import { formatBytes } from '../utils'
import { healthTone } from '../v9-ui'
import { adjacentTaskId, filterTaskNavigation, taskNavigationItems, taskNavigationSummary, validTaskSelection } from '../task-navigation'

const props = defineProps({ tasks: { type: Array, default: () => [] }, selectedId: { type: String, default: '' } })
const emit = defineEmits(['select'])
const items = computed(() => taskNavigationItems(props.tasks))
const counts = computed(() => taskNavigationSummary(items.value))
const previous = computed(() => adjacentTaskId(items.value, props.selectedId, -1))
const next = computed(() => adjacentTaskId(items.value, props.selectedId, 1))
function select(id) {
  if (validTaskSelection(items.value, props.selectedId, id)) emit('select', id)
}
</script>

<template>
  <section v-if="items.length" class="task-navigator" aria-label="刷流任务切换">
    <div class="task-navigator__picker">
      <div class="task-navigator__control"><span class="task-navigator__caption">当前任务 · 点击切换或搜索</span>
      <VAutocomplete :model-value="selectedId" :items="items" item-title="displayTitle" item-value="id" :custom-filter="filterTaskNavigation"
        aria-label="切换刷流任务" placeholder="搜索任务、站点或下载器" variant="outlined" density="compact" hide-details
        :menu-props="{ maxHeight: 360 }" no-data-text="没有匹配的任务，试试站点或下载器名称"
        @update:model-value="select">
        <template #item="{ props: optionProps, item }">
          <VListItem v-bind="optionProps" role="option" :aria-selected="item.value === selectedId" class="task-navigator__option" :title="item.raw.name"
            :subtitle="[item.raw.site, item.raw.downloader].filter(Boolean).join(' · ')">
            <template #title>
              <div class="task-navigator__option-title"><strong :title="item.raw.name">{{ item.raw.name }}</strong>
                <VChip size="x-small" :color="healthTone(item.raw.health.level)" variant="tonal">{{ item.raw.health.title || '等待检查' }}</VChip>
              </div>
            </template>
            <template #subtitle>
              <div class="task-navigator__option-meta"><span>{{ item.raw.site }}<template v-if="item.raw.downloader"> · {{ item.raw.downloader }}</template></span>
                <span>{{ formatBytes(item.raw.size) }} · 24h上传 {{ item.raw.uploaded === null ? '待统计' : formatBytes(item.raw.uploaded) }}{{ item.raw.partialUpload ? '（部分）' : '' }}</span>
              </div>
            </template>
          </VListItem>
        </template>
      </VAutocomplete>
      </div>
      <div v-if="items.length > 1" class="task-navigator__arrows">
        <VBtn icon="mdi-chevron-left" aria-label="上一个任务" title="上一个任务" size="small" variant="text" :disabled="!previous" @click="select(previous)" />
        <VBtn icon="mdi-chevron-right" aria-label="下一个任务" title="下一个任务" size="small" variant="text" :disabled="!next" @click="select(next)" />
      </div>
    </div>
    <div class="task-navigator__counts" aria-label="全部任务概况">
      <span>共 <strong>{{ counts.total }}</strong> 个任务</span>
      <span>启用 <strong>{{ counts.enabled }}</strong></span>
      <span :class="{ 'task-navigator__attention': counts.attention }"><VIcon v-if="counts.attention" icon="mdi-alert-circle-outline" size="16" />需关注 <strong>{{ counts.attention }}</strong></span>
    </div>
  </section>
</template>

<style scoped>
.task-navigator{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));border-radius:14px;background:rgba(var(--v-theme-surface),.55)}
.task-navigator__picker{display:flex;align-items:center;gap:6px;flex:1;min-width:0;max-width:600px}
.task-navigator__picker>:first-child{flex:1;min-width:0}
.task-navigator__control{display:flex;flex-direction:column;gap:5px;min-width:0}
.task-navigator__caption{font-size:.74rem;color:rgba(var(--v-theme-on-surface),.65)}
.task-navigator__arrows{display:flex;flex-shrink:0}
.task-navigator__counts{display:flex;align-items:center;flex-wrap:wrap;gap:16px;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity));font-size:.8rem}
.task-navigator__counts>span{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.task-navigator__attention{color:rgb(var(--v-theme-warning))}
.task-navigator__option-title{display:flex;align-items:center;justify-content:space-between;gap:10px;min-width:0}
.task-navigator__option-title strong{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:.88rem}
.task-navigator__option-meta{display:flex;flex-direction:column;gap:3px;margin-top:3px;font-size:.75rem}
.task-navigator__option-meta span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
@media(max-width:959px){.task-navigator{align-items:stretch;flex-direction:column;gap:10px}.task-navigator__picker{max-width:none}.task-navigator__counts{gap:14px}}
@media(max-width:599px){.task-navigator{padding:12px}.task-navigator__option-title{align-items:flex-start;flex-direction:column;gap:4px}}
</style>

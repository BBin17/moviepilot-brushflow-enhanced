<script setup>
import { formatBytes } from '../utils'
import { healthTone } from '../v9-ui'

defineProps({ tasks: { type: Array, default: () => [] }, selectedId: { type: String, default: '' } })
defineEmits(['select', 'create'])
</script>

<template>
  <section class="task-health-grid" aria-label="刷流任务健康状态">
    <button v-for="task in tasks" :key="task.id" type="button" class="task-health-card"
      :class="{ selected: task.id === selectedId }" @click="$emit('select', task.id)">
      <div class="task-health-card__top">
        <div><strong>{{ task.name }}</strong><span>{{ task.site_name }} · {{ task.downloader }}</span></div>
        <VChip size="x-small" :color="healthTone(task.strategy?.ui_summary?.health?.level)" variant="tonal">
          {{ task.strategy?.ui_summary?.health?.title || '等待检查' }}
        </VChip>
      </div>
      <div class="task-health-card__capacity">
        <span>{{ formatBytes(task.seeding_size) }}</span>
        <small>{{ task.strategy?.ui_summary?.capacity?.limit_bytes ? `上限 ${formatBytes(task.strategy.ui_summary.capacity.limit_bytes)}` : '容量未设置' }}</small>
      </div>
      <VProgressLinear :model-value="Math.min(task.strategy?.ui_summary?.capacity?.percent || 0, 100)"
        :color="(task.strategy?.ui_summary?.capacity?.percent || 0) > 100 ? 'error' : healthTone(task.strategy?.ui_summary?.health?.level)" height="5" rounded />
      <div class="task-health-card__meta">
        <span>上传 {{ Number(task.strategy?.uploaded_gb_per_day || 0).toFixed(1) }} GB/天</span>
        <span>异常 {{ (task.strategy?.ui_summary?.download?.stalled_count || 0) + (task.strategy?.ui_summary?.download?.slow_count || 0) + (task.strategy?.ui_summary?.download?.queued_count || 0) + (task.strategy?.ui_summary?.download?.error_count || 0) }}</span>
      </div>
      <p>{{ task.strategy?.ui_summary?.health?.message || '首次检查后显示下一步。' }}</p>
    </button>
    <button v-if="!tasks.length" type="button" class="task-health-card task-health-card--create" @click="$emit('create')">
      <VIcon icon="mdi-plus-circle-outline" size="24" />
      <span><strong>新建刷流任务</strong><small>按四步向导完成设置</small></span>
    </button>
  </section>
</template>

<style scoped>
.task-health-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}.task-health-card{display:flex;flex-direction:column;gap:10px;min-width:0;padding:16px;border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));border-radius:16px;background:rgba(var(--v-theme-surface),.72);color:inherit;text-align:start;cursor:pointer;transition:.18s ease}.task-health-card:hover,.task-health-card.selected{border-color:rgb(var(--v-theme-primary));transform:translateY(-1px)}.task-health-card__top,.task-health-card__capacity,.task-health-card__meta{display:flex;justify-content:space-between;gap:10px}.task-health-card__top>div{display:flex;flex-direction:column}.task-health-card span,.task-health-card small,.task-health-card p{color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity));font-size:.8rem}.task-health-card p{margin:0;line-height:1.45}.task-health-card__capacity span{font-size:1.2rem;font-weight:700;color:inherit}.task-health-card--create{align-items:center;align-self:start;flex-direction:row;justify-content:center;min-height:88px;border-style:dashed;text-align:left;color:rgb(var(--v-theme-primary))}.task-health-card--create>span{display:flex;flex-direction:column;gap:2px}.task-health-card--create strong{font-size:.95rem}.task-health-card--create small{font-size:.76rem}@media(max-width:599px){.task-health-grid{grid-template-columns:1fr}}
</style>

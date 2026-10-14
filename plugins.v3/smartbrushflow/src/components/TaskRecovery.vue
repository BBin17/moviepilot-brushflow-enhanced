<script setup>
import { formatBytes, formatDateTime } from '../utils'
defineProps({ capacity: {type:Object,default:()=>({})}, quota: {type:Object,default:()=>({})} })
</script>
<template>
  <section v-if="capacity.recovery_active" class="recovery" aria-label="空间恢复与清理额度">
    <header><strong>空间恢复中 · 还需释放 {{ formatBytes(capacity.debt_bytes) }}</strong><span>达到目标后恢复新增；不会提前占满空间</span></header>
    <div class="recovery-facts">
      <div><span>过去24小时删除名额</span><strong>剩余 {{ quota.remaining_daily_count ?? '—' }} / {{ quota.daily_count_cap ?? '—' }} 个</strong><small>已使用 {{ quota.deleted_count_24h ?? 0 }} 个，按滚动24小时计算</small></div>
      <div><span>本轮释放容量上限</span><strong>{{ quota.run_byte_cap ? formatBytes(quota.run_byte_cap) : '未设置' }}</strong><small>同时受数量和每日容量限额约束</small></div>
      <div><span>过去24小时剩余容量额度</span><strong>{{ quota.daily_byte_cap ? formatBytes(quota.remaining_daily_bytes) : '未设置' }}</strong><small>本轮仍会先复核全部硬安全线</small></div>
    </div>
    <p v-if="quota.next_quota_at">最早 {{ formatDateTime(quota.next_quota_at * 1000) }} 恢复可用额度，之后按检查周期复核；这是估算，不保证届时一定删除。</p>
    <p v-if="quota.oversized_count">{{ quota.oversized_count }} 个候选超过本轮容量上限，等待时间不会解决这一限制；可预览手动安全清理或检查限额设置。</p>
    <p v-if="!quota.next_quota_at&&!quota.oversized_count">完整24小时零上传的合格候选优先按恢复空间效率排序，尽量减少消耗的删种名额。</p>
  </section>
</template>
<style scoped>
.recovery{border:1px solid rgba(var(--v-theme-warning),.3);border-radius:14px;padding:16px;margin:16px 0;background:rgba(var(--v-theme-warning),.04)}.recovery header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.recovery header span,.recovery-facts span,.recovery-facts small,.recovery p{font-size:.78rem;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.recovery-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:14px}.recovery-facts>div{display:flex;flex-direction:column;gap:5px}.recovery p{margin-top:12px}@media(max-width:599px){.recovery-facts{grid-template-columns:1fr}}
</style>

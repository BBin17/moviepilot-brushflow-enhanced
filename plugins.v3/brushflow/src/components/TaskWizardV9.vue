<script setup>
import { computed, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { applyProfile, cloneTaskV9, normalizeTaskV9, profileLabel, taskPreview } from '../v9-ui'

const props = defineProps({ modelValue: Boolean, task: Object, sites: { type: Array, default: () => [] }, downloaders: { type: Array, default: () => [] }, saving: Boolean })
const emit = defineEmits(['update:modelValue', 'save'])
const display = useDisplay()
const step = ref(1)
const draft = ref(cloneTaskV9())
const error = ref('')
const advanced = ref(false)
const saveConfirmOpen = ref(false)
const steps = ['站点与任务', '空间与速度', '选种方式', '删种与安全']
const siteName = computed(() => props.sites.find(item => Number(item.value) === Number(draft.value.identity.site_id))?.title || '当前站点')
const preview = computed(() => taskPreview(draft.value, siteName.value))

watch(() => props.modelValue, value => { if (value) { draft.value = cloneTaskV9(props.task); step.value = 1; error.value = ''; advanced.value = false } })

function close() { emit('update:modelValue', false) }
function chooseProfile(profile) { draft.value = applyProfile(draft.value, profile) }
function markCustom() { draft.value.strategy.profile = 'custom' }
function validateStep(target = step.value) {
  if (target === 1 && (!draft.value.identity.name.trim() || !draft.value.identity.site_id || !draft.value.identity.downloader)) return '请填写任务名称、站点和下载器'
  if (target === 2 && draft.value.deletion.enabled && !Number(draft.value.capacity.limit_gb || 0)) return '启用自动删种前必须设置任务容量'
  if (target === 4 && draft.value.deletion.enabled && !Number(draft.value.deletion.min_seed_hours || 0)) return '请填写当前站点最低保种时间'
  return ''
}
function next() { const message = validateStep(); if (message) { error.value = message; return } error.value = ''; step.value = Math.min(step.value + 1, 4) }
function previous() { error.value = ''; step.value = Math.max(step.value - 1, 1) }
function save() {
  for (const target of [1, 2, 4]) { const message = validateStep(target); if (message) { step.value = target; error.value = message; return } }
  saveConfirmOpen.value = true
}
function confirmSave() {
  saveConfirmOpen.value = false
  emit('save', normalizeTaskV9(draft.value))
}
</script>

<template>
  <VDialog :model-value="modelValue" :fullscreen="display.smAndDown.value" max-width="72rem" scrollable @update:model-value="value => emit('update:modelValue', value)">
    <VCard class="wizard">
      <VToolbar color="transparent"><VToolbarTitle>{{ draft.id ? '编辑任务' : '新建任务' }}</VToolbarTitle><VSpacer/><VBtn icon="mdi-close" @click="close"/></VToolbar>
      <VDivider/>
      <VCardText class="wizard__body">
        <nav class="wizard__steps">
          <button v-for="(label,index) in steps" :key="label" type="button" :class="{active:step===index+1,done:step>index+1}" @click="step=index+1"><span>{{ index+1 }}</span>{{ label }}</button>
        </nav>
        <main class="wizard__content">
          <VAlert v-if="error" type="error" variant="tonal" density="compact">{{ error }}</VAlert>
          <section v-if="step===1" class="wizard-section">
            <div><h3>这个任务刷哪个站？</h3><p>站点和下载器保存后仍可修改，历史数据会继续关联。</p></div>
            <VRow><VCol cols="12" md="6"><VTextField v-model="draft.identity.name" label="任务名称"/></VCol><VCol cols="12" md="6"><VSelect v-model="draft.identity.site_id" :items="sites" label="站点"/></VCol><VCol cols="12" md="6"><VSelect v-model="draft.identity.downloader" :items="downloaders" label="下载器"/></VCol><VCol cols="12" md="6"><VTextField v-model="draft.identity.save_path" label="保存目录" placeholder="留空使用下载器默认目录"/></VCol></VRow>
            <VRow><VCol cols="12" md="4"><VTextField v-model.number="draft.schedule.brush_interval" type="number" min="1" label="选种周期（分钟）"/></VCol><VCol cols="12" md="4"><VTextField v-model.number="draft.schedule.check_interval" type="number" min="1" label="检查周期（分钟）"/></VCol><VCol cols="12" md="4"><VTextField v-model="draft.schedule.active_time_range" label="运行时段" placeholder="全天或 00:00-08:00"/></VCol></VRow>
            <div class="switches"><VSwitch v-model="draft.identity.enabled" label="启用任务" hide-details/><VSwitch v-model="draft.identity.notify" label="发送通知" hide-details/><VSwitch v-model="draft.goal.enabled" label="设置分享率目标" hide-details/></div>
            <VRow v-if="draft.goal.enabled"><VCol cols="12" md="6"><VTextField v-model.number="draft.goal.ratio_target" type="number" step="0.01" label="目标分享率"/></VCol><VCol cols="12" md="6"><VSelect v-model="draft.goal.reached_behavior" label="达到目标后" :items="[{title:'继续正常运行',value:'continue'},{title:'暂停新增',value:'pause'}]"/></VCol></VRow>
          </section>
          <section v-if="step===2" class="wizard-section">
            <div><h3>给任务多少空间和带宽？</h3><p>任务容量独立计算；全局限制只负责阻止继续新增。</p></div>
            <VRow><VCol cols="12" md="6"><VTextField v-model.number="draft.capacity.limit_gb" type="number" min="0" label="任务容量上限（GB）" hint="自动删种按90%开始、85%停止" persistent-hint/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.capacity.max_downloads" type="number" min="1" label="同时下载数"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.capacity.upload_limit_kbps" type="number" label="总上传限速（KB/s）"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.capacity.download_limit_kbps" type="number" label="总下载限速（KB/s）"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.selection.size_min_gb" type="number" step="0.1" min="0" label="最小种子体积（GB）"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.selection.size_max_gb" type="number" step="0.1" min="0" label="最大种子体积（GB，可选）"/></VCol></VRow>
          </section>
          <section v-if="step===3" class="wizard-section">
            <div><h3>优先选择什么种子？</h3><p>明确的体积、H&R和文本规则始终是硬过滤。</p></div>
            <div class="profile-grid"><button v-for="profile in ['conservative','balanced','aggressive']" :key="profile" type="button" :class="{active:draft.strategy.profile===profile}" @click="chooseProfile(profile)"><strong>{{ profileLabel(profile) }}</strong><span>{{ profile==='conservative'?'更少新增，适合空间紧张':profile==='balanced'?'收益与稳定性平衡':'更积极抢新种' }}</span></button></div>
            <VRow><VCol cols="12" md="4"><VSelect v-model="draft.selection.promotion" label="促销要求" :items="[{title:'全部',value:'all'},{title:'免费',value:'free'},{title:'2X免费',value:'2xfree'}]"/></VCol><VCol cols="12" md="4"><VSelect v-model="draft.selection.source" label="种子来源" :items="[{title:'站点列表页',value:'page'},{title:'RSS',value:'rss'}]"/></VCol><VCol cols="12" md="4"><VTextField v-model.number="draft.strategy.overrides.max_add_per_run" type="number" min="1" max="100" label="每轮最多新增" @update:model-value="markCustom"/></VCol></VRow>
            <div class="switches"><VSwitch v-model="draft.selection.enabled" label="启用智能选种" hide-details/><VSwitch v-model="draft.selection.exclude_hr" label="排除H&R" hide-details/><VSwitch v-model="draft.selection.exclude_subscriptions" label="排除订阅内容" hide-details/></div>
            <VRow><VCol cols="12" md="6"><VTextField v-model="draft.selection.include" label="必须包含（正则，可选）"/></VCol><VCol cols="12" md="6"><VTextField v-model="draft.selection.exclude" label="必须排除（正则，可选）"/></VCol></VRow>
          </section>
          <section v-if="step===4" class="wizard-section">
            <div><h3>如何安全释放空间？</h3><p>新启用或风险扩大后先观察，不会立即删除。</p></div>
            <VSwitch v-model="draft.deletion.enabled" color="error" label="启用统一智能删种"/>
            <VAlert v-if="draft.deletion.enabled" type="info" variant="tonal">前48小时只记录候选，不会实际删除；未完成、H&R、未到最低保种、正在上传或有真实需求的种子永久保护。</VAlert>
            <VRow><VCol cols="12" md="6"><VTextField v-model.number="draft.deletion.min_seed_hours" type="number" min="1" label="站点最低保种时间（小时）"/></VCol><VCol cols="12" md="6"><VTextField v-model="draft.deletion.exclude_tags" label="永不删除的标签"/></VCol></VRow>
            <div class="switches"><VSwitch v-model="draft.deletion.delete_data" color="error" label="清理时同时删除下载数据" hide-details/><VSwitch v-model="draft.deletion.invalid_tracker_cleanup" label="清理Tracker明确拒绝的任务（保留数据）" hide-details/></div>
            <VExpansionPanels v-model="advanced" class="mt-4"><VExpansionPanel :value="true"><VExpansionPanelTitle>高级设置（安全参数组）</VExpansionPanelTitle><VExpansionPanelText>
              <h4>评分</h4><VRow><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.selection_min_score" type="number" min="0" max="100" label="选种最低分" hint="越高越谨慎" persistent-hint @update:model-value="markCustom"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.deletion_score_threshold" type="number" min="0" max="100" label="低价值阈值" hint="只处理低于该分且通过安全线的种子" persistent-hint @update:model-value="markCustom"/></VCol></VRow>
              <h4>容量控制</h4><VRow><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.capacity_trigger_percent" type="number" min="1" max="100" label="容量触发线（%）" hint="默认90%开始清理" persistent-hint @update:model-value="markCustom"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.capacity_target_percent" type="number" min="0" max="99" label="容量停止线（%）" hint="默认降到85%停止" persistent-hint @update:model-value="markCustom"/></VCol></VRow>
              <h4>候选确认</h4><VRow><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.candidate_confirmations" type="number" min="2" max="6" label="连续确认次数" @update:model-value="markCustom"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.confirmation_minutes" type="number" min="0" label="确认跨度（分钟）" @update:model-value="markCustom"/></VCol></VRow>
              <h4>删除限额</h4><VRow><VCol cols="12" md="4"><VTextField v-model.number="draft.strategy.overrides.max_delete_per_run" type="number" min="1" label="每轮最多删除（个）" @update:model-value="markCustom"/></VCol><VCol cols="12" md="4"><VTextField v-model.number="draft.strategy.overrides.max_release_percent_run" type="number" min="0" max="100" label="每轮最多释放（容量%）" @update:model-value="markCustom"/></VCol><VCol cols="12" md="4"><VTextField v-model.number="draft.strategy.overrides.max_release_percent_day" type="number" min="0" max="100" label="每天最多释放（容量%）" @update:model-value="markCustom"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.max_release_gb_run" type="number" min="0" label="每轮GB上限（可选）" clearable @update:model-value="markCustom"/></VCol><VCol cols="12" md="6"><VTextField v-model.number="draft.strategy.overrides.max_release_gb_day" type="number" min="0" label="每天GB上限（可选）" clearable @update:model-value="markCustom"/></VCol></VRow>
              <h4>下载健康</h4><VRow><VCol cols="12" md="3"><VTextField v-model.number="draft.health.stalled_confirmations" type="number" min="2" max="10" label="卡住确认次数"/></VCol><VCol cols="12" md="3"><VTextField v-model.number="draft.health.stalled_window_minutes" type="number" min="10" label="卡住观察分钟"/></VCol><VCol cols="12" md="3"><VTextField v-model.number="draft.health.slow_after_hours" type="number" min="1" label="低速观察小时"/></VCol><VCol cols="12" md="3"><VTextField v-model.number="draft.health.slow_speed_kbps" type="number" min="1" label="低速阈值KB/s"/></VCol></VRow>
              <VBtn variant="tonal" @click="chooseProfile(draft.strategy.profile==='custom'?'balanced':draft.strategy.profile)">恢复当前预设</VBtn>
            </VExpansionPanelText></VExpansionPanel></VExpansionPanels>
          </section>
        </main>
        <aside class="wizard__summary"><VIcon icon="mdi-text-box-check-outline" color="primary" size="28"/><h3>保存后会这样运行</h3><p>{{ preview }}</p><VChip variant="tonal">{{ profileLabel(draft.strategy.profile) }}</VChip></aside>
      </VCardText>
      <VDivider/><VCardActions><VBtn v-if="step>1" variant="text" @click="previous">上一步</VBtn><VSpacer/><VBtn variant="text" @click="close">取消</VBtn><VBtn v-if="step<4" color="primary" variant="flat" @click="next">下一步</VBtn><VBtn v-else color="primary" variant="flat" :loading="saving" @click="save">保存任务</VBtn></VCardActions>
    </VCard>
    <VDialog v-model="saveConfirmOpen" max-width="32rem">
      <VCard>
        <VCardTitle>确认保存这套规则</VCardTitle>
        <VCardText>
          <p>{{ preview }}</p>
          <VAlert v-if="draft.deletion.enabled" type="warning" variant="tonal" class="mt-4">
            自动删种将{{ draft.deletion.delete_data ? '删除下载器任务和对应数据' : '只移除下载器任务并保留数据' }}；新启用或放宽安全参数后会先进入观察期，硬安全线始终有效。
          </VAlert>
        </VCardText>
        <VCardActions><VSpacer/><VBtn variant="text" @click="saveConfirmOpen=false">返回修改</VBtn><VBtn color="primary" variant="flat" :loading="saving" @click="confirmSave">确认保存</VBtn></VCardActions>
      </VCard>
    </VDialog>
  </VDialog>
</template>

<style scoped>
.wizard{max-height:min(92dvh,62rem)}.wizard__body{display:grid;grid-template-columns:11rem minmax(0,1fr)18rem;padding:0}.wizard__steps{display:flex;flex-direction:column;padding:18px 10px;border-inline-end:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.wizard__steps button{display:flex;align-items:center;gap:9px;padding:11px;border:0;border-radius:10px;background:transparent;color:inherit;text-align:start}.wizard__steps button span{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:rgba(var(--v-theme-on-surface),.08)}.wizard__steps button.active{background:rgba(var(--v-theme-primary),.12);color:rgb(var(--v-theme-primary))}.wizard__content{padding:22px;min-width:0}.wizard-section{display:flex;flex-direction:column;gap:18px}.wizard-section h3,.wizard__summary h3{margin:0}.wizard-section p,.wizard__summary p{margin:4px 0 0;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity));line-height:1.6}.wizard__summary{padding:22px 18px;border-inline-start:1px solid rgba(var(--v-border-color),var(--v-border-opacity));background:rgba(var(--v-theme-primary),.04)}.profile-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.profile-grid button{display:flex;flex-direction:column;gap:4px;padding:14px;border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));border-radius:12px;background:transparent;color:inherit;text-align:start}.profile-grid button.active{border-color:rgb(var(--v-theme-primary));background:rgba(var(--v-theme-primary),.08)}.profile-grid span{font-size:.78rem;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.switches{display:flex;flex-wrap:wrap;gap:8px 24px}@media(max-width:959px){.wizard__body{grid-template-columns:1fr}.wizard__steps{flex-direction:row;overflow:auto;border-inline-end:0;border-block-end:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.wizard__summary{border-inline-start:0;border-block-start:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}}@media(max-width:599px){.wizard__steps button{font-size:0}.wizard__steps button span{font-size:.8rem}.profile-grid{grid-template-columns:1fr}.wizard__content{padding:16px}}
</style>

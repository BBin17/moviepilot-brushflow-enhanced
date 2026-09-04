<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useDisplay } from 'vuetify'
import { applySmartProfile, cloneTask, normalizeTask } from '../utils'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  task: { type: Object, default: () => ({}) },
  sites: { type: Array, default: () => [] },
  downloaders: { type: Array, default: () => [] },
  globalDynamicDelete: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save'])
const display = useDisplay()
const formRef = ref(null)
const activeTab = ref('base')
const localTask = ref(cloneTask())
const syncingProfile = ref(false)
const presetFields = [
  'smart_selection_max_add_per_run',
  'smart_selection_min_score',
  'smart_ratio_weight',
  'smart_cold_inactive_minutes',
  'smart_demand_confirmations',
  'smart_candidate_confirmations',
  'smart_candidate_confirmation_minutes',
  'smart_capacity_trigger_percent',
  'smart_capacity_target_percent',
  'smart_score_threshold',
  'smart_score_margin',
  'smart_max_delete_per_run',
  'smart_max_delete_percent_day',
  'smart_max_delete_capacity_percent_run',
  'smart_max_delete_capacity_percent_day',
  'smart_max_delete_gb_per_run',
  'smart_max_delete_gb_per_day',
  'smart_recovery_enabled',
  'smart_recovery_trigger_percent',
  'smart_recovery_max_delete_percent_day',
  'smart_recovery_max_delete_capacity_percent_run',
  'smart_recovery_max_delete_capacity_percent_day',
  'smart_allow_proactive_delete',
  'smart_required_conditions',
]

const dialogTitle = computed(() => (localTask.value.id ? '编辑刷流任务' : '新建刷流任务'))
const siteName = computed(() => props.sites.find(item => item.value === Number(localTask.value.site_id))?.title || '未选择')
const scheduleText = computed(() => localTask.value.cron || `每 ${localTask.value.brush_interval || 10} 分钟`)

// 每次打开弹窗都从服务端任务快照重新创建本地草稿。
watch(
  () => props.modelValue,
  visible => {
    if (!visible) return
    syncingProfile.value = true
    localTask.value = cloneTask(props.task)
    activeTab.value = 'base'
    nextTick(() => { syncingProfile.value = false })
  },
)

watch(
  () => presetFields.map(key => localTask.value[key]),
  (values, previous) => {
    if (!previous || syncingProfile.value || localTask.value.smart_profile === 'custom') return
    if (values.some((value, index) => value !== previous[index])) localTask.value.smart_profile = 'custom'
  },
)

// 关闭编辑器并丢弃尚未保存的草稿。
function closeDialog() {
  emit('update:modelValue', false)
}

function setSmartProfile(profile) {
  syncingProfile.value = true
  localTask.value = applySmartProfile(localTask.value, profile)
  nextTick(() => { syncingProfile.value = false })
}

// 校验必填项后提交标准化任务数据。
async function saveTask() {
  const result = await formRef.value?.validate()
  if (result && !result.valid) return
  emit('save', normalizeTask(localTask.value))
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    scrollable
    :fullscreen="display.smAndDown.value"
    max-width="74rem"
    @update:model-value="value => emit('update:modelValue', value)"
  >
    <VCard class="brushflow-editor">
      <VToolbar color="transparent" density="comfortable" class="brushflow-editor__toolbar">
        <VToolbarTitle>{{ dialogTitle }}</VToolbarTitle>
        <VSpacer />
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save" :loading="saving" @click="saveTask">
          保存任务
        </VBtn>
        <VBtn icon="mdi-close" variant="text" aria-label="关闭" @click="closeDialog" />
      </VToolbar>
      <VDivider />

      <VCardText class="brushflow-editor__body">
        <VForm ref="formRef" class="brushflow-editor__form" @submit.prevent="saveTask">
          <VTabs
            v-model="activeTab"
            :direction="display.mdAndUp.value ? 'vertical' : 'horizontal'"
            color="primary"
            class="brushflow-editor__tabs"
          >
            <VTab value="base" prepend-icon="mdi-calendar-clock">基础与调度</VTab>
            <VTab value="selection" prepend-icon="mdi-filter-cog-outline">选种规则</VTab>
            <VTab value="limits" prepend-icon="mdi-gauge">运行限额</VTab>
            <VTab value="delete" prepend-icon="mdi-delete-clock-outline">删种规则</VTab>
            <VTab value="advanced" prepend-icon="mdi-tune-variant">高级</VTab>
          </VTabs>

          <VDivider :vertical="display.mdAndUp.value" />

          <VWindow v-model="activeTab" :touch="false" class="brushflow-editor__window">
            <VWindowItem value="base">
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">任务身份</div>
                    <div class="text-body-2 text-medium-emphasis">每个任务绑定一个站点和下载器</div>
                  </div>
                  <VChip size="small" color="primary" variant="tonal">必填</VChip>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model="localTask.name"
                      label="任务名称"
                      :rules="[value => !!String(value || '').trim() || '请输入任务名称']"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VSelect
                      v-model="localTask.site_id"
                      :items="sites"
                      label="站点"
                      :rules="[value => !!value || '请选择站点']"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VSelect
                      v-model="localTask.downloader"
                      :items="downloaders"
                      label="下载器"
                      :rules="[value => !!value || '请选择下载器']"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model="localTask.save_path" label="保存目录" placeholder="留空使用下载器默认目录" />
                  </VCol>
                </VRow>
                <div class="editor-switches">
                  <VSwitch v-model="localTask.enabled" label="启用任务" color="primary" hide-details inset />
                  <VSwitch v-model="localTask.notify" label="发送通知" color="primary" hide-details inset />
                </div>
              </section>

              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">刷新计划</div>
                    <div class="text-body-2 text-medium-emphasis">刷流刷新和下载状态检查分别调度</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.brush_interval"
                      type="number"
                      min="1"
                      max="1440"
                      label="刷流刷新周期（分钟）"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.check_interval"
                      type="number"
                      min="1"
                      max="1440"
                      label="状态检查周期（分钟）"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model="localTask.cron" label="CRON 表达式" placeholder="留空使用固定刷新周期" />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model="localTask.active_time_range"
                      label="开启时间段"
                      placeholder="如 00:00-08:00"
                    />
                  </VCol>
                </VRow>
              </section>

              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">站点分享率控制</div>
                    <div class="text-body-2 text-medium-emphasis">根据最新站点统计自动等待或恢复刷流</div>
                  </div>
                </header>
                <VSwitch
                  v-model="localTask.site_ratio_control"
                  label="启用站点分享率控制"
                  color="primary"
                  hide-details
                  inset
                />
                <VRow v-if="localTask.site_ratio_control">
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.site_ratio_target"
                      type="number"
                      min="0.01"
                      step="0.01"
                      label="目标分享率"
                      :rules="[value => Number(value) > 0 || '请输入大于 0 的目标分享率']"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VSelect
                      v-model="localTask.site_ratio_reached_behavior"
                      label="目标达成后"
                      :items="[
                        { title: '继续按普通均衡门槛运行', value: 'continue' },
                        { title: '暂停新增（兼容行为）', value: 'pause' },
                      ]"
                    />
                  </VCol>
                </VRow>
              </section>
            </VWindowItem>

            <VWindowItem value="selection">
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">来源与促销</div>
                    <div class="text-body-2 text-medium-emphasis">沿用站点列表页或 RSS 获取链路</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VSelect
                      v-model="localTask.freeleech"
                      label="促销"
                      :items="[
                        { title: '全部（包括普通）', value: '' },
                        { title: '免费', value: 'free' },
                        { title: '2X 免费', value: '2xfree' },
                      ]"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VSelect
                      v-model="localTask.hr"
                      label="排除 H&R"
                      :items="[
                        { title: '是', value: 'yes' },
                        { title: '否', value: 'no' },
                      ]"
                    />
                  </VCol>
                </VRow>
                <div class="editor-switches">
                  <VSwitch v-model="localTask.rss_support" label="使用 RSS" color="primary" hide-details inset />
                  <VSwitch v-model="localTask.except_subscribe" label="排除订阅" color="primary" hide-details inset />
                  <VSwitch v-model="localTask.site_hr_active" label="全站 H&R" color="primary" hide-details inset />
                  <VSwitch v-model="localTask.smart_selection_enabled" label="启用智能选种" color="primary" hide-details inset />
                </div>
                <VAlert v-if="localTask.smart_selection_enabled" type="info" variant="tonal" density="compact">
                  新增候选会优先选择免费/双倍、下载者更多、做种更稀缺、发布时间更新且 H&R 风险更低的种子；分享率接近目标时会自动收紧新增数量和评分门槛。
                </VAlert>
                <div v-if="localTask.smart_selection_enabled" class="editor-switches">
                  <VSwitch
                    v-model="localTask.smart_adaptive_enabled"
                    label="按分享率缺口自适应选种"
                    color="primary"
                    hide-details
                    inset
                  />
                  <VSwitch
                    v-model="localTask.smart_selection_relax_filters"
                    label="做种人数交给智能评分"
                    color="primary"
                    hide-details
                    inset
                  />
                  <div class="text-body-2 text-medium-emphasis">
                    已填写的种子大小始终作为硬过滤；此开关只影响做种人数范围。
                  </div>
                </div>
                <VRow v-if="localTask.smart_selection_enabled">
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.smart_selection_min_score"
                      type="number"
                      min="0"
                      max="100"
                      label="智能选种最低分"
                      hint="低于此分数的候选跳过，建议 20-35"
                      persistent-hint
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.smart_selection_max_add_per_run"
                      type="number"
                      min="1"
                      max="100"
                      label="每轮智能选种最多新增数"
                    />
                  </VCol>
                </VRow>
              </section>

              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">候选过滤</div>
                    <div class="text-body-2 text-medium-emphasis">范围字段支持单值或“最小值-最大值”</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="4">
                    <VTextField v-model="localTask.size" label="种子大小（GB）" placeholder="10-80" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model="localTask.seeder" label="做种人数" placeholder="1-10" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model="localTask.pubtime" label="发布时间（分钟）" placeholder="5-120" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.timezone_offset" type="number" label="站点时区偏移（小时）" />
                  </VCol>
                  <VCol cols="12" md="8">
                    <VTextField v-model="localTask.include" label="包含规则" placeholder="支持正则表达式" />
                  </VCol>
                  <VCol cols="12">
                    <VTextField v-model="localTask.exclude" label="排除规则" placeholder="支持正则表达式" />
                  </VCol>
                </VRow>
              </section>
            </VWindowItem>

            <VWindowItem value="limits">
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">新增任务上限</div>
                    <div class="text-body-2 text-medium-emphasis">达到任一上限后停止为当前任务新增种子</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.disksize" type="number" min="0" label="保种体积（GB）" />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.maxdlcount" type="number" min="0" label="同时下载任务数" />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.maxupspeed" type="number" min="0" label="总上传带宽（KB/s）" />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.maxdlspeed" type="number" min="0" label="总下载带宽（KB/s）" />
                  </VCol>
                </VRow>
              </section>
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">单种限速</div>
                    <div class="text-body-2 text-medium-emphasis">只作用于当前任务新添加的种子</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.up_speed" type="number" min="0" label="上传限速（KB/s）" />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.dl_speed" type="number" min="0" label="下载限速（KB/s）" />
                  </VCol>
                </VRow>
              </section>
            </VWindowItem>

            <VWindowItem value="delete">
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">
                      {{ globalDynamicDelete ? '全局删种托管' : '删除模式' }}
                    </div>
                    <div class="text-body-2 text-medium-emphasis">
                      {{ globalDynamicDelete ? '选择此任务是否参加全局阈值兜底淘汰' : '动态模式会在超过体积阈值后按现有算法托管删种' }}
                    </div>
                  </div>
                </header>
                <VBtnToggle v-model="localTask.proxy_delete" mandatory color="primary" divided>
                  <VBtn :value="false">{{ globalDynamicDelete ? '不参与托管' : '按条件删除' }}</VBtn>
                  <VBtn :value="true">{{ globalDynamicDelete ? '参与全局托管' : '动态删种' }}</VBtn>
                </VBtnToggle>
                <VSelect
                  :model-value="localTask.smart_profile"
                  label="智能策略预设"
                  :items="[
                    { title: '保守', value: 'conservative' },
                    { title: '均衡（推荐）', value: 'balanced' },
                    { title: '冲量', value: 'aggressive' },
                    { title: '自定义', value: 'custom' },
                  ]"
                  @update:model-value="setSmartProfile"
                />
                <VSwitch
                  v-model="localTask.smart_enabled"
                  label="启用 8.0 智能收益删种"
                  color="error"
                  hide-details
                  inset
                />
                <VAlert v-if="localTask.smart_enabled" type="info" variant="tonal" density="compact">
                  首次启用先进入 48 小时影子观察，只生成计划、不删除。正式启用后仍强制保护未完成、H&amp;R、最低保种、排除标签、真实上传和有效连接；正常淘汰默认删除任务及数据。
                </VAlert>
                <VRow v-if="localTask.proxy_delete && !globalDynamicDelete">
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.delete_min_size"
                      type="number"
                      min="0"
                      label="最低停止阈值（GB）"
                      hint="触发后删到此容量停止"
                      persistent-hint
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.delete_max_size"
                      type="number"
                      min="0"
                      label="最高触发阈值（GB）"
                      hint="达到此容量才开始删种"
                      persistent-hint
                    />
                  </VCol>
                </VRow>
              </section>
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">硬安全线</div>
                    <div class="text-body-2 text-medium-emphasis">任何完成种子都必须先满足；动态兜底也不能绕过</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.min_seed_time"
                      type="number"
                      min="0"
                      label="站点最低保种时长（小时）"
                      hint="按当前站点规则填写，不固定为 72 小时"
                      persistent-hint
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.min_inactivetime" type="number" min="0" label="最少未活动时间（分钟）" />
                  </VCol>
                </VRow>
                <VRow v-if="localTask.smart_enabled">
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_min_ratio" type="number" min="0" step="0.01" label="最低分享率（可选）" hint="留空或 0 不按分享率硬拦截" persistent-hint />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_min_uploaded" type="number" min="0" step="0.1" label="最低上传量（GB，可选）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_score_threshold" type="number" min="0" max="100" label="低价值分数阈值" hint="越高越容易淘汰，建议 35-45" persistent-hint />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_score_margin" type="number" min="0" max="100" label="安全余量" hint="从阈值再减去的分数，建议 0-5" persistent-hint />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_max_delete_per_run" type="number" min="1" max="100" label="每轮最多删除数" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_max_delete_percent_day" type="number" min="0" max="100" label="每日最多删除比例（%）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField
                      v-model.number="localTask.smart_ratio_weight"
                      type="number"
                      min="0"
                      max="5"
                      label="分享率保留权重"
                      hint="仅近期仍有上传时生效，最多 5 分"
                      persistent-hint
                    />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField
                      v-model.number="localTask.smart_cold_inactive_minutes"
                      type="number"
                      min="0"
                      label="智能冷种保护时间（分钟）"
                      hint="达到最低保种后，近期有活动的种子暂不淘汰"
                      persistent-hint
                    />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_demand_confirmations" type="number" min="1" max="3" label="需求可信次数（最近 3 次）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_candidate_confirmations" type="number" min="1" max="6" label="低价值连续确认次数" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_candidate_confirmation_minutes" type="number" min="0" label="候选确认最短跨度（分钟）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_capacity_trigger_percent" type="number" min="1" max="100" label="容量触发线（%）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_capacity_target_percent" type="number" min="0" max="99" label="容量停止线（%）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_max_delete_capacity_percent_run" type="number" min="0" max="100" label="每轮最多释放容量（%）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_max_delete_capacity_percent_day" type="number" min="0" max="100" label="每日最多释放容量（%）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_max_delete_gb_per_run" type="number" min="0" label="每轮删除 GB 上限（可选）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.smart_max_delete_gb_per_day" type="number" min="0" label="每日删除 GB 上限（可选）" />
                  </VCol>
                  <VCol cols="12" md="4" v-if="localTask.smart_recovery_enabled">
                    <VTextField
                      v-model.number="localTask.smart_recovery_trigger_percent"
                      type="number"
                      min="100"
                      max="500"
                      label="超额恢复触发线（%）"
                      hint="超过任务容量后才加速，默认 125%"
                      persistent-hint
                    />
                  </VCol>
                  <VCol cols="12" md="4" v-if="localTask.smart_recovery_enabled">
                    <VTextField
                      v-model.number="localTask.smart_recovery_max_delete_capacity_percent_run"
                      type="number"
                      min="0"
                      max="100"
                      label="恢复期每轮释放上限（%）"
                    />
                  </VCol>
                  <VCol cols="12" md="4" v-if="localTask.smart_recovery_enabled">
                    <VTextField
                      v-model.number="localTask.smart_recovery_max_delete_capacity_percent_day"
                      type="number"
                      min="0"
                      max="100"
                      label="恢复期每日释放上限（%）"
                    />
                  </VCol>
                  <VCol cols="12" md="4" v-if="localTask.smart_recovery_enabled">
                    <VTextField
                      v-model.number="localTask.smart_recovery_max_delete_percent_day"
                      type="number"
                      min="0"
                      max="100"
                      label="恢复期每日删除比例（%）"
                    />
                  </VCol>
                </VRow>
                <div v-if="localTask.smart_enabled" class="editor-switches">
                  <VSwitch
                    v-model="localTask.smart_protect_active_demand"
                    label="有下载需求时禁止删种"
                    color="primary"
                    hide-details
                    inset
                  />
                  <VSwitch
                    v-model="localTask.smart_required_conditions"
                    label="同时满足旧版删除条件才允许删除"
                    color="primary"
                    hide-details
                    inset
                  />
                  <VSwitch
                    v-model="localTask.smart_recovery_enabled"
                    label="超额容量自动恢复（仅超过任务上限 125% 后加速，硬安全线不变）"
                    color="primary"
                    hide-details
                    inset
                  />
                  <VSwitch
                    v-model="localTask.smart_allow_proactive_delete"
                    label="无容量压力也主动清理（默认禁止）"
                    color="warning"
                    hide-details
                    inset
                  />
                </div>
                <VSwitch
                  v-model="localTask.invalid_seed_cleanup_enabled"
                  label="自动清理无效做种"
                  color="error"
                  hide-details
                  inset
                />
                <VAlert v-if="localTask.invalid_seed_cleanup_enabled" type="info" variant="tonal" density="compact">
                  参考“清理无效做种”插件：只认 Tracker 明确返回未注册、已封禁或不存在，并确认同一 Tracker 在其它种子上仍正常；连续确认后仅移除 qB 任务，不删除下载数据。
                </VAlert>
                <VRow v-if="localTask.invalid_seed_cleanup_enabled">
                  <VCol cols="12" md="6">
                    <VTextField
                      v-model.number="localTask.invalid_seed_confirmations"
                      type="number"
                      min="1"
                      max="5"
                      label="无效做种连续确认次数"
                      hint="默认 2 次，避免站点临时故障误清理"
                      persistent-hint
                    />
                  </VCol>
                </VRow>
              </section>
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">触发条件</div>
                    <div class="text-body-2 text-medium-emphasis">可选择满足任一条件或全部条件后删除</div>
                  </div>
                </header>
                <VBtnToggle v-model="localTask.delete_condition_mode" mandatory color="primary" divided>
                  <VBtn value="any">任一条件</VBtn>
                  <VBtn value="all">全部条件</VBtn>
                </VBtnToggle>
                <VRow>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.seed_time" type="number" min="0" label="做种时间（小时）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.hr_seed_time" type="number" min="0" label="H&R 做种时间（小时）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.seed_ratio" type="number" min="0" label="分享率" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.seed_size" type="number" min="0" label="上传量（GB）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.download_time" type="number" min="0" label="下载超时（小时）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.seed_inactivetime" type="number" min="0" label="未活动时间（分钟）" />
                  </VCol>
                  <VCol cols="12" md="4">
                    <VTextField v-model.number="localTask.seed_avgspeed" type="number" min="0" label="平均上传速度（KB/s）" />
                  </VCol>
                  <VCol cols="12" md="8">
                    <VTextField v-model="localTask.delete_except_tags" label="删除排除标签" />
                  </VCol>
                </VRow>
                <VRow v-if="localTask.proxy_delete">
                  <VCol cols="12" md="6">
                    <VSelect
                      v-model="localTask.dynamic_sort_mode"
                      label="动态淘汰顺序"
                      :items="[
                        { title: '智能：闲置优先、低速优先', value: 'smart' },
                        { title: '做种最久优先', value: 'oldest' },
                        { title: '未活动最久优先', value: 'inactive' },
                        { title: '平均上传最低优先', value: 'low_speed' },
                        { title: '体积最大优先', value: 'largest' },
                      ]"
                    />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VSwitch
                      v-model="localTask.dynamic_require_conditions"
                      label="动态兜底也必须满足删除条件"
                      color="primary"
                      hide-details
                      inset
                    />
                  </VCol>
                </VRow>
                <VSwitch
                  v-model="localTask.del_no_free"
                  label="删除促销过期的未完成下载"
                  color="primary"
                  hide-details
                  inset
                />
                <VSwitch
                  v-if="!localTask.smart_enabled"
                  v-model="localTask.delete_dry_run"
                  label="模拟运行（只记录计划，不实际删除）"
                  color="warning"
                  hide-details
                  inset
                />
                <VSwitch
                  v-model="localTask.delete_files"
                  label="删除任务时同时删除下载数据"
                  color="error"
                  hide-details
                  inset
                />
              </section>
            </VWindowItem>

            <VWindowItem value="advanced">
              <section class="editor-section">
                <header class="editor-section__head">
                  <div>
                    <div class="text-subtitle-1 font-weight-medium">下载器适配</div>
                    <div class="text-body-2 text-medium-emphasis">保留原有分类、提示跳过和自动归档能力</div>
                  </div>
                </header>
                <VRow>
                  <VCol cols="12" md="6">
                    <VTextField v-model="localTask.qb_category" label="qBittorrent 分类" />
                  </VCol>
                  <VCol cols="12" md="6">
                    <VTextField v-model.number="localTask.auto_archive_days" type="number" min="0" label="自动归档天数" />
                  </VCol>
                  <VCol cols="12">
                    <VTextField
                      v-model="localTask.tag"
                      label="下载器标签（可选）"
                      placeholder="默认：刷流-站点名"
                      hint="下载器中的种子标签，留空自动使用「刷流-站点名」；同一站点存在多个任务时请设置为不同标签"
                      persistent-hint
                    />
                  </VCol>
                </VRow>
                <div class="editor-switches">
                  <VSwitch v-model="localTask.site_skip_tips" label="自动跳过下载提示" color="primary" hide-details inset />
                </div>
              </section>
            </VWindowItem>
          </VWindow>

          <VSheet tag="aside" class="brushflow-editor__summary">
            <div class="text-subtitle-1 font-weight-medium">配置摘要</div>
            <dl>
              <div><dt>站点</dt><dd>{{ siteName }}</dd></div>
              <div><dt>下载器</dt><dd>{{ localTask.downloader || '未选择' }}</dd></div>
              <div><dt>刷新</dt><dd>{{ scheduleText }}</dd></div>
              <div><dt>检查</dt><dd>每 {{ localTask.check_interval || 5 }} 分钟</dd></div>
              <div><dt>时段</dt><dd>{{ localTask.active_time_range || '全天' }}</dd></div>
              <div><dt>目标分享率</dt><dd>{{ localTask.site_ratio_control ? localTask.site_ratio_target || '未设置' : '关闭' }}</dd></div>
              <div><dt>促销</dt><dd>{{ localTask.freeleech === '2xfree' ? '2X 免费' : localTask.freeleech === 'free' ? '免费' : '全部' }}</dd></div>
              <div><dt>保种上限</dt><dd>{{ localTask.disksize ? `${localTask.disksize} GB` : '不限' }}</dd></div>
              <div><dt>删除</dt><dd>{{ localTask.smart_enabled ? `8.0 智能 · ${localTask.smart_profile}` : localTask.proxy_delete ? '动态删种' : '按条件删除' }}</dd></div>
            </dl>
          </VSheet>
        </VForm>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.brushflow-editor {
  max-block-size: min(90dvh, 58rem);
}

.brushflow-editor__toolbar {
  flex: 0 0 auto;
  padding-inline: 8px;
  z-index: 4;
  backdrop-filter: blur(var(--transparent-blur, 0px));
  background-color: rgba(var(--v-theme-surface), var(--transparent-opacity-heavy, 1));
}

.brushflow-editor__body {
  padding: 0;
}

.brushflow-editor__form {
  display: grid;
  grid-template-columns: 12rem auto minmax(0, 1fr) minmax(12rem, 0.34fr);
  min-block-size: 34rem;
}

.brushflow-editor__tabs {
  padding: 12px 8px;
}

.brushflow-editor__window {
  min-inline-size: 0;
  padding: 20px;
}

.editor-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.editor-section + .editor-section {
  margin-block-start: 28px;
  padding-block-start: 24px;
  border-block-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.editor-section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.editor-switches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}

.brushflow-editor__summary {
  padding: 20px 16px;
  border-inline-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.brushflow-editor__summary dl {
  display: grid;
  gap: 12px;
  margin: 18px 0 0;
}

.brushflow-editor__summary dl > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.brushflow-editor__summary dt {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.brushflow-editor__summary dd {
  margin: 0;
  text-align: end;
  overflow-wrap: anywhere;
}

@media (max-width: 959px) {
  .brushflow-editor {
    max-block-size: none;
  }

  .brushflow-editor__form {
    grid-template-columns: 1fr;
    min-block-size: 0;
  }

  .brushflow-editor__tabs {
    max-inline-size: 100%;
    padding-block: 0;
    overflow-x: auto;
  }

  .brushflow-editor__window {
    padding: 16px;
  }

  .brushflow-editor__summary {
    border-inline-start: 0;
    border-block-start: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }
}

@media (max-width: 599px) {
  .brushflow-editor__toolbar :deep(.v-toolbar-title) {
    font-size: 1rem;
  }

  .brushflow-editor__toolbar :deep(.v-btn__content) {
    white-space: normal;
  }

}
</style>

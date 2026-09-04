<script setup>
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import TaskHealthCards from './TaskHealthCards.vue'
import TaskWizardV9 from './TaskWizardV9.vue'
import { cloneTaskV9, newTaskV9, profileLabel } from '../v9-ui'
import { formatBytes, formatDateTime, unwrapResponse } from '../utils'

const props = defineProps({ api: { type: Object, default: () => ({}) }, pluginId: { type: String, default: 'BrushFlow' }, showClose: Boolean })
const emit = defineEmits(['close','action'])
const toast = inject('moviepilot:toast', null)
const base = computed(() => `plugin/${props.pluginId}`)
const loading = ref(false), saving = ref(false), error = ref('')
const status = ref({ enabled:false, summary:{}, tasks:[], options:{sites:[],downloaders:[]} })
const selectedId = ref(''), detail = ref(null), tab = ref('status'), torrentState = ref('active'), page = ref(1)
const wizard = ref(false), wizardTask = ref(newTaskV9())
const confirmOpen = ref(false), confirmAction = ref(null)
const settingsOpen = ref(false), settingsDraft = ref({})
const changeNotice = ref('')
let timer
const tasks = computed(() => status.value.tasks || [])
const selected = computed(() => tasks.value.find(item => item.id === selectedId.value) || null)
const strategy = computed(() => detail.value?.strategy || selected.value?.strategy || {})
const summary = computed(() => strategy.value.ui_summary || {})
const task = computed(() => detail.value?.task || null)
const torrents = computed(() => detail.value?.torrents || {items:[],total:0,page:1,page_size:50})
const runs = computed(() => detail.value?.runs || [])

function notify(message, type='success'){ if(typeof toast?.[type]==='function') toast[type](message); else if(type==='error') error.value=message }
async function loadDetail(){ if(!selectedId.value)return; try{ const [baseDetail,torrentData,eventData]=await Promise.all([props.api.get(`${base.value}/tasks/${selectedId.value}`),props.api.get(`${base.value}/tasks/${selectedId.value}/torrents?state=${torrentState.value}&page=${page.value}&page_size=50`),props.api.get(`${base.value}/tasks/${selectedId.value}/events?page=1&page_size=20`)]); detail.value={...(unwrapResponse(baseDetail)||{}),torrents:unwrapResponse(torrentData),runs:unwrapResponse(eventData)?.items||[]} }catch(err){ error.value=err?.message||'加载任务失败' } }
async function load(){ loading.value=true; try{ status.value=unwrapResponse(await props.api.get(`${base.value}/status`))||status.value; if(!tasks.value.some(item=>item.id===selectedId.value)) selectedId.value=tasks.value[0]?.id||''; await loadDetail() }catch(err){ error.value=err?.message||'加载刷流状态失败' }finally{ loading.value=false } }
function openSettings(){ const signin=status.value.signin||{}; settingsDraft.value={enabled:!!status.value.enabled,show_sidebar_nav:status.value.show_sidebar_nav!==false,global_disksize:status.value.global_disksize??null,global_maxdlcount:status.value.global_maxdlcount??null,global_maxupspeed:status.value.global_maxupspeed??null,global_maxdlspeed:status.value.global_maxdlspeed??null,signin_enabled:!!signin.enabled,signin_notify:signin.notify!==false,signin_cron:signin.cron||'17 7 * * *',signin_sites:[...(signin.site_ids||[])]}; settingsOpen.value=true }
async function saveSettings(){ saving.value=true; try{ status.value=unwrapResponse(await props.api.post(`${base.value}/settings`,settingsDraft.value))||status.value; settingsOpen.value=false; await load(); notify('插件设置已保存') }catch(err){ notify(err?.message||'保存设置失败','error') }finally{ saving.value=false } }
async function runSignin(){ saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/signin/run`,{})); await load(); notify('站点签到已执行') }catch(err){ notify(err?.message||'签到失败','error') }finally{ saving.value=false } }
async function selectTask(id){ selectedId.value=id; page.value=1; torrentState.value='active'; tab.value='status'; await loadDetail() }
function createTask(){ wizardTask.value=newTaskV9(); wizard.value=true }
function editTask(){ if(!task.value)return; wizardTask.value=cloneTaskV9(task.value); wizard.value=true }
async function saveTask(payload){ saving.value=true; try{ const previous=task.value; const response=payload.id?await props.api.put(`${base.value}/tasks/${payload.id}`,payload):await props.api.post(`${base.value}/tasks`,payload); const data=unwrapResponse(response); selectedId.value=data?.task?.id||payload.id||selectedId.value; wizard.value=false; const effects=[]; if(!previous) effects.push('已建立新的选种与检查计划'); else{ if(JSON.stringify(previous.capacity)!==JSON.stringify(payload.capacity)) effects.push('容量或速度限制已更新'); if(JSON.stringify(previous.selection)!==JSON.stringify(payload.selection)) effects.push('选种硬过滤与评分入口已更新'); if(JSON.stringify(previous.deletion)!==JSON.stringify(payload.deletion)||JSON.stringify(previous.strategy)!==JSON.stringify(payload.strategy)) effects.push('删种安全策略已更新，风险扩大时重新进入观察') } changeNotice.value=effects.join('；')||'任务基础信息已更新'; await load(); notify(payload.id?'任务已更新':'任务已创建') }catch(err){ notify(err?.message||'保存任务失败','error') }finally{ saving.value=false } }
function askAction(action){ confirmAction.value=action; confirmOpen.value=true }
async function executeAction(){ const action=confirmAction.value; if(!action)return; confirmOpen.value=false; if(action.code==='open_editor'){ confirmAction.value=null; editTask(); return } saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/tasks/${selectedId.value}/actions/${action.code}`,{})); await load(); notify(action.success||'操作已提交') }catch(err){ notify(err?.message||'操作失败','error') }finally{ saving.value=false; confirmAction.value=null } }
function topAction(code,label,confirm,success){ askAction({code,label,confirm,success,tone:'primary'}) }
async function changeTorrentState(value){ torrentState.value=value; page.value=1; await loadDetail() }
async function changePage(value){ page.value=value; await loadDetail() }
onMounted(()=>{ load(); timer=window.setInterval(load,30000) }); onUnmounted(()=>window.clearInterval(timer))
</script>

<template>
  <div class="bf9">
    <header class="bf9__header"><div><div class="bf9__brand"><VIcon icon="mdi-sync-circle" color="primary" size="34"/><div><h1>站点刷流</h1><p>看结论、处理异常，其余交给统一策略</p></div></div></div><div class="bf9__header-actions"><VBtn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">刷新</VBtn><VBtn variant="text" prepend-icon="mdi-tune" @click="openSettings">工具与设置</VBtn><VBtn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="createTask">新建任务</VBtn><VBtn v-if="showClose" icon="mdi-close" variant="text" @click="emit('close')"/></div></header>
    <VAlert v-if="error" type="error" variant="tonal" closable @click:close="error=''">{{ error }}</VAlert>
    <VAlert v-if="!status.enabled" type="warning" variant="tonal">插件当前未启用；任务和历史可以查看，但不会自动运行。</VAlert>
    <TaskHealthCards :tasks="tasks" :selected-id="selectedId" @select="selectTask" @create="createTask"/>
    <div v-if="!tasks.length&&!loading" class="bf9__empty"><VIcon icon="mdi-radar" size="52"/><h2>还没有刷流任务</h2><p>四步完成站点、容量、选种和安全规则。</p><VBtn color="primary" @click="createTask">创建第一个任务</VBtn></div>
    <template v-if="selected">
      <section class="bf9__taskbar"><div><h2>{{ selected.name }}</h2><p>{{ selected.site_name }} · 最近 {{ selected.last_run?formatDateTime(selected.last_run.started_at):'尚未运行' }} · 下次 {{ selected.next_run_at?formatDateTime(selected.next_run_at):'暂无计划' }}</p></div><div><VBtn variant="tonal" prepend-icon="mdi-radar" @click="topAction('run_selection','立即选种','将立即访问站点并可能添加符合条件的下载，确认继续吗？','选种任务已提交')">立即选种</VBtn><VBtn variant="tonal" prepend-icon="mdi-progress-check" @click="topAction('run_check','检查种子','将立即检查下载、上传和删种候选，确认继续吗？','种子检查已提交')">检查种子</VBtn><VBtn variant="text" prepend-icon="mdi-pencil" @click="editTask">编辑任务</VBtn><VBtn variant="text" :prepend-icon="selected.enabled?'mdi-pause':'mdi-play'" @click="topAction(selected.enabled?'pause_task':'resume_task',selected.enabled?'暂停任务':'恢复任务',selected.enabled?'暂停后将停止自动选种和检查，确认吗？':'恢复后将重新注册自动调度，确认吗？',selected.enabled?'任务已暂停':'任务已恢复')">{{ selected.enabled?'暂停':'恢复' }}</VBtn></div></section>
      <VAlert v-if="changeNotice" type="info" variant="tonal" closable @click:close="changeNotice=''">本次修改影响：{{ changeNotice }}</VAlert>
      <VTabs v-model="tab" color="primary"><VTab value="status">状态</VTab><VTab value="torrents">种子</VTab><VTab value="history">记录</VTab></VTabs><VDivider/>
      <VWindow v-model="tab" :touch="false">
        <VWindowItem value="status">
          <section class="bf9__conclusion" :class="`tone-${summary.health?.level||'info'}`"><VIcon :icon="summary.health?.level==='success'?'mdi-check-circle':summary.health?.level==='error'?'mdi-alert-circle':'mdi-information'" size="36"/><div><span>当前结论</span><h2>{{ summary.health?.title||'等待首次检查' }}</h2><p>{{ summary.health?.message||'插件完成第一次检查后会告诉你下一步。' }}</p></div></section>
          <section v-if="summary.recommended_actions?.length" class="bf9__attention"><div><h3>需要处理</h3><p>这些操作都会先说明影响，再由你确认。</p></div><div><VBtn v-for="action in summary.recommended_actions" :key="action.code" :color="action.tone||'primary'" variant="tonal" @click="askAction(action)">{{ action.label }}</VBtn></div></section>
          <section class="bf9__capacity panel"><header><div><h3>容量</h3><p>{{ formatBytes(summary.capacity?.current_bytes||selected.seeding_size) }} / {{ summary.capacity?.limit_bytes?formatBytes(summary.capacity.limit_bytes):'未设置上限' }}</p></div><strong>{{ summary.capacity?.percent??0 }}%</strong></header><div class="capacity-track"><i class="target" :style="{left:`${strategy.capacity_target_percent||85}%`}"/><i class="trigger" :style="{left:`${strategy.capacity_trigger_percent||90}%`}"/><span :style="{width:`${Math.min(summary.capacity?.percent||0,100)}%`}"/></div><div class="capacity-labels"><span>目标 {{ strategy.capacity_target_percent||85 }}%</span><span>开始清理 {{ strategy.capacity_trigger_percent||90 }}%</span><span>上限 100%</span></div></section>
          <div class="bf9__summary-grid">
            <article class="panel"><VIcon icon="mdi-radar" color="primary"/><h3>选种</h3><strong>新增 {{ summary.selection?.added_count||0 }} 个</strong><p>本轮看到 {{ summary.selection?.candidate_count||0 }} 个，过滤 {{ summary.selection?.filtered_count||0 }} 个。</p><small v-if="summary.selection?.main_reason">主要原因：{{ summary.selection.main_reason }}</small></article>
            <article class="panel"><VIcon icon="mdi-shield-check" color="warning"/><h3>安全删种</h3><strong>{{ summary.deletion?.candidate_count||0 }} 个候选</strong><p>{{ summary.deletion?.message||'暂无删种计划。' }}</p><small>保护 {{ summary.deletion?.protected_count||0 }} 个 / {{ formatBytes(summary.deletion?.protected_bytes||0) }}</small></article>
            <article class="panel"><VIcon icon="mdi-download-circle" :color="summary.download?.state==='healthy'?'success':'warning'"/><h3>下载健康</h3><strong>{{ summary.download?.state==='healthy'?'正常':'需要关注' }}</strong><p>卡住 {{ summary.download?.stalled_count||0 }} · 低速 {{ summary.download?.slow_count||0 }} · 排队 {{ summary.download?.queued_count||0 }} · 报错 {{ summary.download?.error_count||0 }}</p><small>未完成数据绝不自动删除</small></article>
          </div>
          <VExpansionPanels class="mt-4"><VExpansionPanel><VExpansionPanelTitle>策略详情（专业信息）</VExpansionPanelTitle><VExpansionPanelText><div class="bf9__facts"><div><span>策略预设</span><strong>{{ profileLabel(task?.strategy?.profile) }}</strong></div><div><span>安全观察（影子期）</span><strong>{{ strategy.mode_label||'未启用' }}</strong></div><div><span>学习置信度</span><strong>{{ Math.round((strategy.learning_confidence||0)*100) }}%</strong></div><div><span>有效样本</span><strong>{{ strategy.learning_sample_count||0 }}</strong></div><div><span>误判率</span><strong>{{ ((strategy.false_positive_rate||0)*100).toFixed(1) }}%</strong></div><div><span>单位容量收益</span><strong>{{ ((strategy.unit_capacity_yield_per_day||0)*100).toFixed(3) }}%/天</strong></div></div></VExpansionPanelText></VExpansionPanel></VExpansionPanels>
        </VWindowItem>
        <VWindowItem value="torrents"><section class="panel mt-4"><header class="bf9__list-head"><div><h3>托管种子</h3><p>共 {{ torrents.total }} 个</p></div><VBtnToggle :model-value="torrentState" mandatory density="compact" @update:model-value="changeTorrentState"><VBtn value="active">活跃</VBtn><VBtn value="deleted">已删除</VBtn><VBtn value="all">全部</VBtn></VBtnToggle></header><div class="torrent-list"><article v-for="item in torrents.items" :key="item.hash||item.title"><div><strong>{{ item.title||item.hash }}</strong><span>{{ item.download_health_label|| (item.deleted?'已删除':'正常') }}</span></div><span>{{ formatBytes(item.size||item.total_size) }}</span><span>上传 {{ formatBytes(item.uploaded) }}</span><VChip size="x-small" variant="tonal">{{ Number(item.ratio||0).toFixed(2) }}</VChip></article><div v-if="!torrents.items?.length" class="bf9__empty small">暂无种子</div></div><VPagination v-if="torrents.total>torrents.page_size" :model-value="page" :length="Math.ceil(torrents.total/torrents.page_size)" @update:model-value="changePage"/></section></VWindowItem>
        <VWindowItem value="history"><section class="panel mt-4"><h3>最近运行</h3><div class="event-list"><article v-for="run in runs" :key="run.id"><VIcon :icon="run.success===false?'mdi-alert-circle':'mdi-check-circle'" :color="run.success===false?'error':'success'"/><div><strong>{{ run.kind==='brush'?'选种刷新':'种子检查' }}</strong><span>{{ formatDateTime(run.started_at) }} · {{ run.kind==='brush'?`新增 ${run.added_count||0}，过滤 ${run.filtered_count||0}`:`活跃 ${run.active_count||0}，删除 ${run.deleted_count||0}` }}</span><small v-if="run.error">{{ run.error }}</small></div></article><div v-if="!runs.length" class="bf9__empty small">暂无运行记录</div></div></section></VWindowItem>
      </VWindow>
    </template>
    <TaskWizardV9 v-model="wizard" :task="wizardTask" :sites="status.options.sites" :downloaders="status.options.downloaders" :saving="saving" @save="saveTask"/>
    <VDialog v-model="settingsOpen" max-width="46rem" scrollable>
      <VCard>
        <VCardTitle><VIcon icon="mdi-tune" class="mr-2"/>工具与设置</VCardTitle>
        <VCardText class="bf9__settings">
          <section>
            <h3>插件运行</h3><p>这里只管理插件总开关和全局硬上限；每个任务仍独立管理自己的容量。</p>
            <VSwitch v-model="settingsDraft.enabled" label="启用站点刷流" color="primary" hide-details/>
            <VSwitch v-model="settingsDraft.show_sidebar_nav" label="显示侧边栏入口" color="primary" hide-details/>
            <div class="settings-grid">
              <VTextField v-model.number="settingsDraft.global_disksize" type="number" min="1" label="全局做种硬上限（GB）" hint="达到后只阻止新增，不跨任务删种" persistent-hint clearable/>
              <VTextField v-model.number="settingsDraft.global_maxdlcount" type="number" min="1" label="全局下载并发硬上限" clearable/>
              <VTextField v-model.number="settingsDraft.global_maxupspeed" type="number" min="1" label="全局上传限速（KB/s）" clearable/>
              <VTextField v-model.number="settingsDraft.global_maxdlspeed" type="number" min="1" label="全局下载限速（KB/s）" clearable/>
            </div>
          </section>
          <VDivider/>
          <section>
            <div class="settings-title"><div><h3>站点签到</h3><p>签到是独立工具，不参与选种、下载健康或删种决策。</p></div><VBtn variant="tonal" prepend-icon="mdi-login" :loading="saving" @click="runSignin">立即签到</VBtn></div>
            <VSwitch v-model="settingsDraft.signin_enabled" label="启用自动签到" color="primary" hide-details/>
            <VSwitch v-model="settingsDraft.signin_notify" label="发送签到结果通知" color="primary" hide-details/>
            <VTextField v-model="settingsDraft.signin_cron" label="签到 CRON" hint="默认每天 07:17：17 7 * * *" persistent-hint/>
            <VSelect v-model="settingsDraft.signin_sites" :items="status.options.sites" multiple chips closable-chips label="签到站点" hint="留空时使用已启用刷流任务的站点" persistent-hint/>
            <VAlert v-if="status.signin?.last_run_at" type="info" variant="tonal" density="compact">最近签到：{{ formatDateTime(status.signin.last_run_at) }}，成功 {{ (status.signin.last_results||[]).filter(item=>item.success).length }}/{{ (status.signin.last_results||[]).length }}</VAlert>
          </section>
        </VCardText>
        <VCardActions><VSpacer/><VBtn variant="text" @click="settingsOpen=false">取消</VBtn><VBtn color="primary" variant="flat" :loading="saving" @click="saveSettings">保存设置</VBtn></VCardActions>
      </VCard>
    </VDialog>
    <VDialog v-model="confirmOpen" max-width="30rem"><VCard><VCardTitle>{{ confirmAction?.label||'确认操作' }}</VCardTitle><VCardText>{{ confirmAction?.confirm||'确认执行这个操作吗？' }}</VCardText><VCardActions><VSpacer/><VBtn variant="text" @click="confirmOpen=false">取消</VBtn><VBtn :color="confirmAction?.tone||'primary'" variant="flat" :loading="saving" @click="executeAction">确认执行</VBtn></VCardActions></VCard></VDialog>
  </div>
</template>

<style scoped>
.bf9{display:flex;flex-direction:column;gap:18px;max-width:1500px;margin:auto;padding:20px}.bf9__header,.bf9__taskbar,.bf9__attention,.panel header,.bf9__list-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.bf9__brand{display:flex;align-items:center;gap:12px}.bf9 h1,.bf9 h2,.bf9 h3,.bf9 p{margin:0}.bf9__brand p,.bf9__taskbar p,.bf9__attention p,.panel p,.panel small,.event-list span,.torrent-list span{color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.bf9__header-actions,.bf9__taskbar>div:last-child,.bf9__attention>div:last-child{display:flex;flex-wrap:wrap;gap:8px}.bf9__taskbar{padding-top:6px}.bf9__conclusion{display:flex;align-items:flex-start;gap:16px;margin-top:18px;padding:22px;border-radius:18px;background:rgba(var(--v-theme-primary),.09)}.bf9__conclusion.tone-success{background:rgba(var(--v-theme-success),.1)}.bf9__conclusion.tone-warning{background:rgba(var(--v-theme-warning),.12)}.bf9__conclusion.tone-error{background:rgba(var(--v-theme-error),.12)}.bf9__conclusion span{font-size:.78rem;text-transform:uppercase}.bf9__conclusion p{margin-top:5px}.bf9__attention{padding:16px 18px;border:1px solid rgba(var(--v-theme-warning),.35);border-radius:14px}.panel{padding:18px;border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));border-radius:16px;background:rgba(var(--v-theme-surface),.62)}.bf9__capacity header strong{font-size:1.5rem}.capacity-track{position:relative;height:10px;margin-top:18px;border-radius:10px;background:rgba(var(--v-theme-on-surface),.08)}.capacity-track span{display:block;height:100%;border-radius:inherit;background:rgb(var(--v-theme-primary))}.capacity-track i{position:absolute;top:-5px;width:2px;height:20px;background:rgb(var(--v-theme-on-surface));opacity:.55}.capacity-labels{display:flex;justify-content:space-between;margin-top:7px;font-size:.72rem;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.bf9__summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.bf9__summary-grid article{display:flex;flex-direction:column;gap:8px}.bf9__summary-grid article>strong{font-size:1.18rem}.bf9__facts{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.bf9__facts>div{display:flex;flex-direction:column}.torrent-list,.event-list{display:flex;flex-direction:column;margin-top:12px}.torrent-list article{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;align-items:center;gap:14px;padding:12px 4px;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.torrent-list article>div,.event-list article>div{display:flex;flex-direction:column;min-width:0}.torrent-list strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.event-list article{display:flex;gap:12px;padding:13px 4px;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.event-list small{color:rgb(var(--v-theme-error))}.bf9__empty{display:flex;flex-direction:column;align-items:center;gap:8px;padding:60px 20px;text-align:center;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.bf9__empty.small{padding:28px}.mt-4{margin-top:18px}@media(max-width:959px){.bf9__summary-grid{grid-template-columns:1fr}.bf9__facts{grid-template-columns:repeat(2,1fr)}.bf9__taskbar{align-items:flex-start;flex-direction:column}.torrent-list article{grid-template-columns:minmax(0,1fr) auto}.torrent-list article>span:nth-of-type(2){display:none}}@media(max-width:599px){.bf9{padding:12px}.bf9__header{align-items:flex-start}.bf9__header-actions .v-btn:not(:last-child){display:none}.bf9__attention{align-items:flex-start;flex-direction:column}.bf9__facts{grid-template-columns:1fr}.capacity-labels span:nth-child(2){display:none}}
.bf9__settings{display:flex;flex-direction:column;gap:22px}.bf9__settings section{display:flex;flex-direction:column;gap:12px}.bf9__settings p{margin:0;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.settings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.settings-title{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}@media(max-width:599px){.bf9__header{flex-direction:column}.bf9__header-actions .v-btn:not(:last-child){display:inline-flex}.settings-grid{grid-template-columns:1fr}.settings-title{flex-direction:column}}
</style>

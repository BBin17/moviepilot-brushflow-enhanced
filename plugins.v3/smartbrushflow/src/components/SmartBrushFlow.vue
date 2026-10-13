<script setup>
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import TaskHealthCards from './TaskHealthCards.vue'
import TaskWizardV9 from './TaskWizardV9.vue'
import TaskPerformance from './TaskPerformance.vue'
import TaskTorrentTable from './TaskTorrentTable.vue'
import { createLatestRequest } from '../latest-request'
import { cloneTaskV9, newTaskV9, profileLabel } from '../v9-ui'
import { formatBytes, formatDateTime, unwrapResponse } from '../utils'

const props = defineProps({ api: { type: Object, default: () => ({}) }, pluginId: { type: String, default: 'SmartBrushFlow' }, showClose: Boolean })
const emit = defineEmits(['close','action'])
const toast = inject('moviepilot:toast', null)
const base = computed(() => `plugin/${props.pluginId}`)
const loading = ref(false), saving = ref(false), error = ref('')
const detailLoading = ref(false), detailRequests = createLatestRequest()
const status = ref({ enabled:false, summary:{}, tasks:[], options:{sites:[],downloaders:[]} })
const selectedId = ref(''), detail = ref(null), tab = ref('status'), torrentState = ref('active'), page = ref(1)
const torrentSort = ref('newest'), torrentFilter = ref('all')
const wizard = ref(false), wizardTask = ref(newTaskV9())
const confirmOpen = ref(false), confirmAction = ref(null)
const deleteConfirmOpen = ref(false), deleteTarget = ref(null), deleteData = ref(false)
const cleanupPreviewOpen = ref(false), cleanupPreview = ref(null)
const settingsOpen = ref(false), settingsDraft = ref({})
const changeNotice = ref('')
const insightOpen = ref(false), insightKind = ref('selection')
let timer, cleanupTimer
const tasks = computed(() => status.value.tasks || [])
const selected = computed(() => tasks.value.find(item => item.id === selectedId.value) || null)
const strategy = computed(() => detail.value?.strategy || selected.value?.strategy || {})
const summary = computed(() => strategy.value.ui_summary || {})
const task = computed(() => detail.value?.task?.id === selectedId.value ? detail.value.task : null)
const torrents = computed(() => detail.value?.torrents || {items:[],total:0,page:1,page_size:50})
const runs = computed(() => detail.value?.runs || [])
const insightTitle = computed(() => ({selection:'选种详情',deletion:'安全删种详情',download:'下载健康详情',income:'长期零上传占用'}[insightKind.value]||'策略详情'))
const selectionDetails = computed(() => strategy.value.selection_explanations || [])
const deletionDetails = computed(() => strategy.value.pending_candidates || strategy.value.deletion_explanations || [])
const downloadDetails = computed(() => summary.value.download?.issues || [])
const cleanupProgress = computed(() => detail.value?.summary?.cleanup_progress || selected.value?.cleanup_progress || null)
const cleanupActive = computed(() => ['queued','running'].includes(cleanupProgress.value?.state))

function notify(message, type='success'){ if(typeof toast?.[type]==='function') toast[type](message); else if(type==='error') error.value=message }
async function loadDetail(){
  const id=selectedId.value, section=tab.value
  if(!id)return
  detailLoading.value=true
  await detailRequests.run(async()=>{
    const requests=[props.api.get(`${base.value}/tasks/${id}`)]
    if(section==='torrents')requests.push(props.api.get(`${base.value}/tasks/${id}/torrents?state=${torrentState.value}&page=${page.value}&page_size=50&sort=${torrentSort.value}&filter=${torrentFilter.value}`))
    if(section==='history')requests.push(props.api.get(`${base.value}/tasks/${id}/events?page=1&page_size=20`))
    const responses=await Promise.all(requests)
    const data=unwrapResponse(responses[0])||{}
    if(data.task?.id!==id)throw new Error('任务详情不匹配，请刷新后重试')
    if(section==='torrents')data.torrents=unwrapResponse(responses[1])
    if(section==='history')data.runs=unwrapResponse(responses[1])?.items||[]
    return data
  },{commit(data){if(id===selectedId.value)detail.value={...(detail.value||{}),...data}},error(err){error.value=err?.message||'加载任务失败'},settled(){detailLoading.value=false}})
}
async function load(){ loading.value=true; try{ status.value=unwrapResponse(await props.api.get(`${base.value}/status`))||status.value; if(!tasks.value.some(item=>item.id===selectedId.value)) selectedId.value=tasks.value[0]?.id||''; await loadDetail(); scheduleCleanupDismiss(cleanupProgress.value) }catch(err){ error.value=err?.message||'加载刷流状态失败' }finally{ loading.value=false } }
function openSettings(){ const signin=status.value.signin||{}; settingsDraft.value={enabled:!!status.value.enabled,show_sidebar_nav:status.value.show_sidebar_nav!==false,global_disksize:status.value.global_disksize??null,global_maxdlcount:status.value.global_maxdlcount??null,global_maxupspeed:status.value.global_maxupspeed??null,global_maxdlspeed:status.value.global_maxdlspeed??null,signin_enabled:!!signin.enabled,signin_notify:signin.notify!==false,signin_cron:signin.cron||'17 7 * * *',signin_sites:[...(signin.site_ids||[])]}; settingsOpen.value=true }
async function saveSettings(){ saving.value=true; try{ status.value=unwrapResponse(await props.api.post(`${base.value}/settings`,settingsDraft.value))||status.value; settingsOpen.value=false; await load(); notify('插件设置已保存') }catch(err){ notify(err?.message||'保存设置失败','error') }finally{ saving.value=false } }
async function runSignin(){ saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/signin/run`,{})); await load(); notify('站点签到已执行') }catch(err){ notify(err?.message||'签到失败','error') }finally{ saving.value=false } }
async function selectTask(id){ detailRequests.invalidate(); detail.value=null; selectedId.value=id; page.value=1; torrentState.value='active'; torrentFilter.value='all'; torrentSort.value='newest'; tab.value='status'; insightOpen.value=false; await loadDetail() }
function createTask(){ wizardTask.value=newTaskV9(); wizard.value=true }
function editTask(){ if(!task.value)return; wizardTask.value=cloneTaskV9(task.value); wizard.value=true }
async function saveTask(payload){ saving.value=true; try{ const previous=task.value; const response=payload.id?await props.api.put(`${base.value}/tasks/${payload.id}`,payload):await props.api.post(`${base.value}/tasks`,payload); const data=unwrapResponse(response); selectedId.value=data?.task?.id||payload.id||selectedId.value; wizard.value=false; const effects=[]; if(!previous) effects.push('已建立新的选种与检查计划'); else{ if(JSON.stringify(previous.capacity)!==JSON.stringify(payload.capacity)) effects.push('容量或速度限制已更新'); if(JSON.stringify(previous.selection)!==JSON.stringify(payload.selection)) effects.push('选种硬过滤与评分入口已更新'); if(JSON.stringify(previous.deletion)!==JSON.stringify(payload.deletion)||JSON.stringify(previous.strategy)!==JSON.stringify(payload.strategy)) effects.push('删种安全策略已更新，风险扩大时重新进入观察') } changeNotice.value=effects.join('；')||'任务基础信息已更新'; await load(); notify(payload.id?'任务已更新':'任务已创建') }catch(err){ notify(err?.message||'保存任务失败','error') }finally{ saving.value=false } }
function askAction(action){ confirmAction.value={...action,taskId:action.taskId||(action.code==='force_cleanup'?cleanupPreview.value?.task_id:selectedId.value)}; confirmOpen.value=true }
async function executeAction(){ const action=confirmAction.value; if(!action)return; confirmOpen.value=false; if(action.code==='open_editor'){ confirmAction.value=null; editTask(); return } saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/tasks/${action.taskId}/actions/${action.code}`,action.payload||{})); await load(); notify(action.success||'操作已提交'); if(action.code==='force_cleanup') startCleanupPolling() }catch(err){ notify(err?.message||'操作失败','error') }finally{ saving.value=false; confirmAction.value=null } }
function topAction(code,label,confirm,success){ askAction({code,label,confirm,success,tone:'primary'}) }
function openInsight(kind){ insightKind.value=kind; insightOpen.value=true }
function askDeleteUnhealthyDownload(item){ insightOpen.value=false; deleteTarget.value={...item,taskId:selectedId.value}; deleteData.value=false; deleteConfirmOpen.value=true }
async function confirmDeleteUnhealthyDownload(){
  const item=deleteTarget.value
  if(!item?.hash||!selectedId.value)return
  saving.value=true
  try{
    const requestId=`manual-${Date.now()}-${Math.random().toString(36).slice(2,10)}`
    const response=await props.api.post(`${base.value}/tasks/${item.taskId}/actions/delete_unhealthy_download`,{
      torrent_hash:item.hash, request_id:requestId, confirm:true, delete_data:deleteData.value,
    })
    unwrapResponse(response)
    deleteConfirmOpen.value=false
    await load()
    notify(response?.message||'已提交单种移除请求')
  }catch(err){ deleteConfirmOpen.value=false; await load(); notify(err?.message||'移除下载失败','error') }
  finally{ saving.value=false; deleteTarget.value=null }
}
async function askForceCleanup(){
  if(!task.value)return
  const id=selectedId.value, revision=task.value.revision
  try{
    const preview=unwrapResponse(await props.api.post(`${base.value}/tasks/${id}/cleanup/preview`,{revision,relax_limits:true}))
    if(id!==selectedId.value)return
    cleanupPreview.value=preview
    cleanupPreviewOpen.value=true
  }catch(err){ notify(err?.message||'生成清理预览失败','error') }
}
function confirmCleanupPreview(){
  const preview=cleanupPreview.value
  if(!preview?.allowed)return
  cleanupPreviewOpen.value=false
  const requestId=`cleanup-${Date.now()}-${Math.random().toString(36).slice(2,10)}`
  askAction({code:'force_cleanup',label:'确认手动安全清理',tone:'error',success:'手动安全清理已提交',payload:{preview_id:preview.preview_id,revision:preview.revision,request_id:requestId,confirm:true,relax_limits:!!preview.relax_limits},confirm:`名单已冻结，有效期约5分钟；预计从下载器移除 ${preview.items?.length||0} 个任务，预计释放数据空间 ${formatBytes(preview.estimated_released_bytes||0)}。执行前仍会重新检查未完成、H&R、保种时间、上传、连接和需求保护。${preview.delete_data?'符合条件的任务及数据会被删除。':'只移除下载器任务，保留本地数据。'}确认继续吗？`})
}
function startCleanupPolling(){ window.clearTimeout(cleanupTimer); cleanupTimer=window.setTimeout(pollCleanup,700) }
function scheduleCleanupDismiss(progress){ if(!progress||!['completed','failed'].includes(progress.state))return; const delay=Math.max(Number(progress.display_until||0)*1000-Date.now(),0)+150; window.clearTimeout(cleanupTimer); cleanupTimer=window.setTimeout(()=>load(),delay) }
async function pollCleanup(){ const id=selectedId.value; if(!id)return; try{ const data=unwrapResponse(await props.api.get(`${base.value}/tasks/${id}`))||{}; if(id!==selectedId.value||data.task?.id!==id)return; detail.value={...(detail.value||{}),...data}; const progress=data.summary?.cleanup_progress; if(['queued','running'].includes(progress?.state)){ cleanupTimer=window.setTimeout(pollCleanup,900); return } await load(); scheduleCleanupDismiss(progress); if(progress?.state==='completed') notify(progress.message||'手动安全清理完成'); else if(progress?.state==='failed') notify(progress.error||'手动安全清理失败','error') }catch(err){ cleanupTimer=window.setTimeout(pollCleanup,1600) } }
function reasonText(codes){ const labels={below_selection_threshold:'低于选种门槛',incomplete:'未完成下载',hit_and_run:'H&R保护',min_seed_time:'未达到最低保种时间',active_demand:'存在下载需求',trusted_active_demand:'Tracker需求仍在观察保护中',real_upload:'近期真实上传',active_connection:'存在活动连接',excluded_tag:'命中排除标签',low_value_unconfirmed:'低价值尚未连续确认',byte_cap:'容量额度已用尽',daily_count_cap:'每日数量额度已用尽',run_count_cap:'单轮数量额度已用尽',low_retention_value:'低收益，等待安全清理',smart_cold_cooldown:'仍在闲置保护时间内',valuable_seed:'仍有保留价值',safety_data_unknown:'下载器安全数据不完整',large_without_trusted_demand:'大种相对下载需求不足',oversized_for_task:'单种超过任务容量的25%',tracker_demand_unknown:'下载需求未知'}; return (codes||[]).map(code=>labels[code]||code).join(' · ')||'暂无补充原因' }
function downloadReason(item){ const labels={no_download_progress:'长时间没有下载进度',no_download_progress_with_connection:'有连接但长时间没有下载进度',low_effective_download_speed:'持续下载速度低于策略阈值',downloader_paused:'下载任务已暂停',downloader_queue:'下载器正在排队',downloader_checking:'下载器正在校验文件',downloader_error:'下载器报告任务错误',missing_download_measurement:'下载器未提供有效进度数据',insufficient_history:'观测记录不足，暂不能判断',confirming_no_progress:'正在确认是否停止下载',progressing:'下载仍有进度'}; return labels[item.reason]||item.reason||item.label||'需要检查下载状态' }
async function changeTorrentState(value){ torrentState.value=value; page.value=1; await loadDetail() }
async function changePage(value){ page.value=value; await loadDetail() }
async function changeTorrentSort(value){torrentSort.value=value;page.value=1;await loadDetail()}
async function changeTorrentFilter(value){torrentFilter.value=value;page.value=1;await loadDetail()}
function openZeroUploadList(){insightOpen.value=false;torrentFilter.value='zero_upload';torrentSort.value='size';page.value=1;tab.value='torrents'}
watch(tab,()=>loadDetail())
onMounted(()=>{ load(); timer=window.setInterval(load,30000) }); onUnmounted(()=>{ detailRequests.invalidate(); window.clearInterval(timer); window.clearTimeout(cleanupTimer) })
</script>

<template>
  <div class="bf9">
    <header class="bf9__header"><div><div class="bf9__brand"><VIcon icon="mdi-sync-circle" color="primary" size="34"/><div><h1>智能刷流</h1><p>看结论、处理异常，其余交给统一策略</p></div></div></div><div class="bf9__header-actions"><VBtn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">刷新</VBtn><VBtn variant="text" prepend-icon="mdi-tune" @click="openSettings">工具与设置</VBtn><VBtn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="createTask">新建任务</VBtn><VBtn v-if="showClose" icon="mdi-close" variant="text" @click="emit('close')"/></div></header>
    <VAlert v-if="error" type="error" variant="tonal" closable @click:close="error=''">{{ error }}</VAlert>
    <VAlert v-if="!status.enabled" type="warning" variant="tonal">插件当前未启用；任务和历史可以查看，但不会自动运行。</VAlert>
    <TaskHealthCards :tasks="tasks" :selected-id="selectedId" @select="selectTask" @create="createTask"/>
    <div v-if="!tasks.length&&!loading" class="bf9__empty"><VIcon icon="mdi-radar" size="52"/><h2>还没有刷流任务</h2><p>四步完成站点、容量、选种和安全规则。</p><VBtn color="primary" @click="createTask">创建第一个任务</VBtn></div>
    <template v-if="selected">
      <section class="bf9__taskbar"><div><h2>{{ selected.name }}</h2><p>{{ selected.site_name }} · 最近 {{ selected.last_run?formatDateTime(selected.last_run.started_at):'尚未运行' }} · 下次 {{ selected.next_run_at?formatDateTime(selected.next_run_at):'暂无计划' }}</p></div><div><VBtn variant="tonal" prepend-icon="mdi-radar" :disabled="!task||detailLoading||saving" @click="topAction('run_selection','立即选种','将立即访问站点并可能添加符合条件的下载，确认继续吗？','选种任务已提交')">立即选种</VBtn><VBtn variant="tonal" prepend-icon="mdi-progress-check" :disabled="!task||detailLoading||saving" @click="topAction('run_check','检查种子','将立即检查下载、上传和删种候选，确认继续吗？','种子检查已提交')">检查种子</VBtn><VBtn variant="text" prepend-icon="mdi-pencil" :disabled="!task||detailLoading||saving" @click="editTask">编辑任务</VBtn><VBtn variant="text" :prepend-icon="selected.enabled?'mdi-pause':'mdi-play'" :disabled="!task||detailLoading||saving" @click="topAction(selected.enabled?'pause_task':'resume_task',selected.enabled?'暂停任务':'恢复任务',selected.enabled?'暂停后将停止自动选种和检查，确认吗？':'恢复后将重新注册自动调度，确认吗？',selected.enabled?'任务已暂停':'任务已恢复')">{{ selected.enabled?'暂停':'恢复' }}</VBtn></div></section>
      <VAlert v-if="changeNotice" type="info" variant="tonal" closable @click:close="changeNotice=''">本次修改影响：{{ changeNotice }}</VAlert>
      <section v-if="cleanupProgress" class="bf9__cleanup-progress panel" :class="`state-${cleanupProgress.state}`"><div><VIcon :icon="cleanupActive?'mdi-delete-clock':cleanupProgress.state==='completed'?'mdi-check-circle':'mdi-alert-circle'" :color="cleanupActive?'warning':cleanupProgress.state==='completed'?'success':'error'"/><div><strong>{{ cleanupProgress.phase }}</strong><p>{{ cleanupProgress.state==='completed'?(cleanupProgress.message||`已删除 ${cleanupProgress.deleted_count||0} 个，释放 ${formatBytes(cleanupProgress.freed_bytes||0)}`):`候选 ${cleanupProgress.candidate_count||0} · 已选 ${cleanupProgress.selected_count||0} · 已删 ${cleanupProgress.deleted_count||0}` }}</p></div></div><strong>{{ cleanupProgress.percent||0 }}%</strong><VProgressLinear :model-value="cleanupProgress.percent||0" :indeterminate="cleanupProgress.state==='queued'" :color="cleanupProgress.state==='failed'?'error':cleanupProgress.state==='completed'?'success':'warning'" height="7" rounded/></section>
      <VTabs v-model="tab" color="primary"><VTab value="status">状态</VTab><VTab value="torrents">种子</VTab><VTab value="history">记录</VTab></VTabs><VDivider/>
      <VWindow v-model="tab" :touch="false">
        <VWindowItem value="status">
          <TaskPerformance :performance="summary.performance||{}" :loading="detailLoading&&!task" @inspect="openInsight('income')"/>
          <section class="bf9__conclusion" :class="`tone-${summary.health?.level||'info'}`"><VIcon :icon="summary.health?.level==='success'?'mdi-check-circle':summary.health?.level==='error'?'mdi-alert-circle':'mdi-information'" size="36"/><div><span>当前结论</span><h2>{{ summary.health?.title||'等待首次检查' }}</h2><p>{{ summary.health?.message||'插件完成第一次检查后会告诉你下一步。' }}</p></div></section>
          <section v-if="summary.recommended_actions?.length" class="bf9__attention"><div><h3>需要处理</h3><p>这些操作都会先说明影响，再由你确认。</p></div><div><VBtn v-for="action in summary.recommended_actions" :key="action.code" :color="action.tone||'primary'" variant="tonal" @click="askAction(action)">{{ action.label }}</VBtn></div></section>
          <section class="bf9__capacity panel"><header><div><h3>容量</h3><p>{{ formatBytes(summary.capacity?.current_bytes||selected.seeding_size) }} / {{ summary.capacity?.limit_bytes?formatBytes(summary.capacity.limit_bytes):'未设置上限' }}</p></div><strong>{{ summary.capacity?.percent??0 }}%</strong></header><div class="capacity-track"><i class="target" :style="{left:`${strategy.capacity_target_percent||85}%`}"/><i class="trigger" :style="{left:`${strategy.capacity_trigger_percent||90}%`}"/><span :style="{width:`${Math.min(summary.capacity?.percent||0,100)}%`}"/></div><div class="capacity-labels"><span>目标 {{ strategy.capacity_target_percent||85 }}%</span><span>开始清理 {{ strategy.capacity_trigger_percent||90 }}%</span><span>上限 100%</span></div></section>
          <div class="bf9__summary-grid">
            <article class="panel bf9__drill-card" role="button" tabindex="0" @click="openInsight('selection')" @keydown.enter="openInsight('selection')"><VIcon icon="mdi-radar" color="primary"/><h3>选种</h3><strong>新增 {{ summary.selection?.added_count||0 }} 个</strong><p v-if="summary.selection?.source_checked">本轮看到 {{ summary.selection?.candidate_count||0 }} 个，过滤 {{ summary.selection?.filtered_count||0 }} 个。</p><p v-else>本轮尚未进入站点选种，先处理当前限制。</p><small v-if="summary.selection?.main_reason">主要原因：{{ summary.selection.main_reason }}</small><span class="bf9__drill-link">查看评分与未选原因 <VIcon icon="mdi-chevron-right" size="16"/></span></article>
            <article class="panel bf9__drill-card" role="button" tabindex="0" @click="openInsight('deletion')" @keydown.enter="openInsight('deletion')"><VIcon icon="mdi-shield-check" color="warning"/><h3>安全删种</h3><strong>{{ summary.deletion?.candidate_count||0 }} 个候选</strong><p>{{ summary.deletion?.message||'暂无删种计划。' }}</p><small>保护 {{ summary.deletion?.protected_count||0 }} 个 / {{ formatBytes(summary.deletion?.protected_bytes||0) }}</small><span class="bf9__drill-link">查看候选与保护原因 <VIcon icon="mdi-chevron-right" size="16"/></span></article>
            <article class="panel bf9__drill-card" role="button" tabindex="0" @click="openInsight('download')" @keydown.enter="openInsight('download')"><VIcon icon="mdi-download-circle" :color="summary.download?.state==='healthy'?'success':'warning'"/><h3>下载健康</h3><strong>{{ summary.download?.state==='healthy'?'正常':'需要关注' }}</strong><p>超时 {{ summary.download?.overdue_count||0 }} · 卡住 {{ summary.download?.stalled_count||0 }} · 低速 {{ summary.download?.slow_count||0 }} · 自动暂停 {{ summary.download?.auto_paused_count||0 }}</p><small>未完成数据绝不自动删除</small><span class="bf9__drill-link">查看下载状态 <VIcon icon="mdi-chevron-right" size="16"/></span></article>
          </div>
          <VExpansionPanels class="mt-4"><VExpansionPanel><VExpansionPanelTitle>策略详情（专业信息）</VExpansionPanelTitle><VExpansionPanelText><div class="bf9__facts"><div><span>策略预设</span><strong>{{ profileLabel(task?.strategy?.profile) }}</strong></div><div><span>安全观察（影子期）</span><strong>{{ strategy.mode_label||'未启用' }}</strong></div><div><span>任务样本成熟度</span><strong>{{ Math.round((strategy.learning_confidence||0)*100) }}%</strong></div><div><span>有效小时样本</span><strong>{{ strategy.learning_sample_count||0 }}</strong></div><div><span>误判率</span><strong>{{ ((strategy.false_positive_rate||0)*100).toFixed(1) }}%</strong></div><div><span>单位容量收益</span><strong>{{ ((strategy.unit_capacity_yield_per_day||0)*100).toFixed(3) }}%/天</strong></div></div></VExpansionPanelText></VExpansionPanel></VExpansionPanels>
        </VWindowItem>
        <VWindowItem value="torrents"><TaskTorrentTable :torrents="torrents" :state="torrentState" :sort="torrentSort" :filter="torrentFilter" :loading="detailLoading" @state="changeTorrentState" @sort="changeTorrentSort" @filter="changeTorrentFilter" @page="changePage"/></VWindowItem>
        <VWindowItem value="history"><section class="panel mt-4"><h3>最近运行</h3><div class="event-list"><article v-for="run in runs" :key="run.id"><VIcon :icon="run.success===false?'mdi-alert-circle':'mdi-check-circle'" :color="run.success===false?'error':'success'"/><div><strong>{{ run.kind==='brush'?'选种刷新':run.force_cleanup?'手动安全清理':'种子检查' }}</strong><span>{{ formatDateTime(run.started_at) }} · {{ run.kind==='brush'?`新增 ${run.added_count||0}，过滤 ${run.filtered_count||0}`:`同步 ${run.managed_count ?? run.restored_count ?? 0}，活跃 ${run.active_count||0}，候选 ${run.deletion_candidate_count||0}，删除 ${run.deleted_count||0}${run.force_cleanup?`，释放 ${formatBytes(run.freed_bytes||0)}`:''}` }}</span><small v-if="run.deletion_message" class="reason">{{ run.deletion_message }}</small><small v-if="run.error" class="error">{{ run.error }}</small></div></article><div v-if="!runs.length" class="bf9__empty small">暂无运行记录</div></div></section></VWindowItem>
      </VWindow>
    </template>
    <TaskWizardV9 v-model="wizard" :task="wizardTask" :sites="status.options.sites" :downloaders="status.options.downloaders" :api="api" :plugin-base="base" :saving="saving" @save="saveTask"/>
    <VDialog v-model="insightOpen" max-width="58rem" scrollable>
      <VCard class="bf9__insight"><VCardTitle>{{ insightTitle }}</VCardTitle><VCardText>
        <template v-if="insightKind==='income'"><div class="insight-intro"><p>这些种子已达到最低保种时长，完整 24 小时没有上传。清理仍会复核 H&amp;R、连接和连续确认。</p><VBtn variant="tonal" @click="openZeroUploadList">查看全部零上传种子</VBtn></div><div class="insight-list"><article v-for="item in summary.performance?.low_yield_items||[]" :key="item.hash"><div><strong>{{ item.title||item.hash }}</strong><small>已保种 {{ item.seeding_hours }} 小时 · {{ reasonText(item.reasons) }}</small></div><span>{{ formatBytes(item.size) }}</span></article><div v-if="!summary.performance?.low_yield_items?.length" class="bf9__empty small">暂无符合完整观测条件的零上传种子。</div></div></template>
        <template v-else-if="insightKind==='selection'"><p class="mb-3">最近一次选种评分及结果，分数越高越优先。</p><div class="insight-list"><article v-for="item in selectionDetails" :key="item.title"><div><strong>{{ item.title||'未知候选' }}</strong><small>{{ reasonText(item.reasons) }}</small></div><VChip :color="item.selected?'success':'default'" size="small" variant="tonal">{{ Number(item.score||0).toFixed(1) }} 分 · {{ item.selected?'已选':'未选' }}</VChip></article><div v-if="!selectionDetails.length" class="bf9__empty small">最近没有可展示的站点候选，下一次看到候选后会记录评分。</div></div></template>
        <template v-else-if="insightKind==='deletion'"><div class="insight-intro"><p>候选仍会在真正删除前重新经过全部硬安全线。</p><VBtn v-if="deletionDetails.length" color="error" variant="tonal" prepend-icon="mdi-delete-sweep" :loading="cleanupActive" :disabled="cleanupActive" @click="insightOpen=false;askForceCleanup()">{{ cleanupActive?'正在安全清理':'手动安全清理' }}</VBtn></div><VAlert v-if="cleanupProgress" :type="cleanupProgress.state==='failed'?'error':cleanupProgress.state==='completed'?'success':'warning'" variant="tonal" density="compact" class="mt-4">{{ cleanupProgress.phase }} · 已删 {{ cleanupProgress.deleted_count||0 }} 个 · 释放 {{ formatBytes(cleanupProgress.freed_bytes||0) }}</VAlert><div class="insight-list"><article v-for="item in deletionDetails" :key="item.hash"><div><strong>{{ item.title||item.hash }}</strong><small>{{ item.recovered?'候选恢复上传或需求，已判为误判并保护':'低价值候选，等待额度与最终复核' }}</small></div><div class="insight-metric"><span>{{ formatBytes(item.size||0) }}</span><VChip size="small" :color="item.recovered?'success':'warning'" variant="tonal">{{ Number(item.score||0).toFixed(1) }} 分</VChip></div></article><div v-if="!deletionDetails.length" class="bf9__empty small">当前没有进入观察记录的删种候选。</div></div></template>
        <template v-else><p class="mb-3">仅列出需要关注的下载；未完成数据不会自动删除。卡住或低速的种子可单独手动移除。</p><div class="insight-list"><article v-for="item in downloadDetails" :key="item.hash"><div><strong>{{ item.title }}</strong><small>{{ downloadReason(item) }}</small><small v-if="item.age_hours!==null&&item.age_hours!==undefined">已下载 {{ Number(item.age_hours||0).toFixed(1) }} 小时<span v-if="item.overdue"> · 超过设定时限</span><span v-if="item.eta_hours"> · 预计还需 {{ Number(item.eta_hours).toFixed(1) }} 小时</span></small><small v-if="item.action_error">处理提示：{{ item.action_error }}</small></div><div class="insight-metric"><span>{{ formatBytes(item.size||0) }}</span><VChip size="small" color="warning" variant="tonal">{{ item.overdue?'下载超时':item.label }}</VChip></div><div class="download-issue-actions"><VChip v-if="item.delete_pending" size="small" color="info" variant="tonal">移除结果核对中</VChip><VBtn v-else-if="['stalled','slow'].includes(item.state)||(item.state==='paused'&&item.auto_paused)" size="small" color="error" variant="tonal" prepend-icon="mdi-delete-outline" :disabled="saving" @click="askDeleteUnhealthyDownload(item)">删除</VBtn></div></article><div v-if="!downloadDetails.length" class="bf9__empty small">当前没有卡住、低速、排队或报错的下载。</div></div></template>
      </VCardText><VCardActions><VSpacer/><VBtn variant="text" @click="insightOpen=false">关闭</VBtn></VCardActions></VCard>
    </VDialog>
    <VDialog v-model="settingsOpen" max-width="46rem" scrollable>
      <VCard>
        <VCardTitle><VIcon icon="mdi-tune" class="mr-2"/>工具与设置</VCardTitle>
        <VCardText class="bf9__settings">
          <section>
            <h3>插件运行</h3><p>这里只管理插件总开关和全局硬上限；每个任务仍独立管理自己的容量。</p>
            <VSwitch v-model="settingsDraft.enabled" label="启用智能刷流" color="primary" hide-details/>
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
    <VDialog v-model="cleanupPreviewOpen" max-width="48rem" scrollable><VCard><VCardTitle>清理预览（不会立即删除）</VCardTitle><VCardText><p>以下名单来自本次只读评估，确认后还会再次执行全部硬安全线。</p><div class="preview-metrics"><div><span>候选</span><strong>{{ cleanupPreview?.items?.length||0 }} 个</strong></div><div><span>预计移除任务体积</span><strong>{{ formatBytes(cleanupPreview?.expected_task_bytes_removed||0) }}</strong></div><div><span>预计释放数据</span><strong>{{ formatBytes(cleanupPreview?.estimated_released_bytes||0) }}</strong></div></div><VAlert v-if="!cleanupPreview?.allowed" type="warning" variant="tonal">当前没有可执行的名单：{{ cleanupPreview?.blocked_reasons?.join('、')||'候选已被安全线或额度拦截' }}</VAlert><div v-else class="preview-list"><div v-for="item in cleanupPreview.items" :key="item.hash"><strong>{{ item.title||item.hash }}</strong><span>{{ formatBytes(item.size||0) }} · {{ Number(item.score||0).toFixed(1) }} 分</span></div></div></VCardText><VCardActions><VSpacer/><VBtn variant="text" @click="cleanupPreviewOpen=false">取消</VBtn><VBtn color="error" variant="flat" :disabled="!cleanupPreview?.allowed" @click="confirmCleanupPreview">确认名单并继续</VBtn></VCardActions></VCard></VDialog>
    <VDialog v-model="deleteConfirmOpen" max-width="38rem"><VCard><VCardTitle>确认移除下载</VCardTitle><VCardText><p>将重新检查下载器中的进度。若种子已完成、卡住恢复推进或低速恢复正常，操作会被取消。</p><div class="manual-delete-target"><strong>{{ deleteTarget?.title }}</strong><span>{{ formatBytes(deleteTarget?.size||0) }} · {{ deleteTarget?.label }}</span></div><VCheckbox v-model="deleteData" color="error" label="同时删除本地下载数据" hint="默认仅移除下载器任务并保留文件；勾选后文件也会删除。" persistent-hint hide-details="auto"/><VAlert v-if="deleteData" class="mt-4" type="warning" variant="tonal" density="compact">这会删除未完成的数据文件，通常无法恢复。请确认该下载确实不需要。</VAlert></VCardText><VCardActions><VSpacer/><VBtn variant="text" :disabled="saving" @click="deleteConfirmOpen=false">取消</VBtn><VBtn color="error" variant="flat" :loading="saving" @click="confirmDeleteUnhealthyDownload">确认删除</VBtn></VCardActions></VCard></VDialog>
    <VDialog v-model="confirmOpen" max-width="30rem"><VCard><VCardTitle>{{ confirmAction?.label||'确认操作' }}</VCardTitle><VCardText>{{ confirmAction?.confirm||'确认执行这个操作吗？' }}</VCardText><VCardActions><VSpacer/><VBtn variant="text" @click="confirmOpen=false">取消</VBtn><VBtn :color="confirmAction?.tone||'primary'" variant="flat" :loading="saving" @click="executeAction">确认执行</VBtn></VCardActions></VCard></VDialog>
  </div>
</template>

<style scoped>
.bf9{display:flex;flex-direction:column;gap:18px;max-width:1500px;margin:auto;padding:20px}.bf9__header,.bf9__taskbar,.bf9__attention,.panel header,.bf9__list-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.bf9__brand{display:flex;align-items:center;gap:12px}.bf9 h1,.bf9 h2,.bf9 h3,.bf9 p{margin:0}.bf9__brand p,.bf9__taskbar p,.bf9__attention p,.panel p,.panel small,.event-list span,.torrent-list span{color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.bf9__header-actions,.bf9__taskbar>div:last-child,.bf9__attention>div:last-child{display:flex;flex-wrap:wrap;gap:8px}.bf9__taskbar{padding-top:6px}.bf9__conclusion{display:flex;align-items:flex-start;gap:16px;margin-top:18px;padding:22px;border-radius:18px;background:rgba(var(--v-theme-primary),.09)}.bf9__conclusion.tone-success{background:rgba(var(--v-theme-success),.1)}.bf9__conclusion.tone-warning{background:rgba(var(--v-theme-warning),.12)}.bf9__conclusion.tone-error{background:rgba(var(--v-theme-error),.12)}.bf9__conclusion span{font-size:.78rem;text-transform:uppercase}.bf9__conclusion p{margin-top:5px}.bf9__attention{padding:16px 18px;border:1px solid rgba(var(--v-theme-warning),.35);border-radius:14px}.panel{padding:18px;border:1px solid rgba(var(--v-border-color),var(--v-border-opacity));border-radius:16px;background:rgba(var(--v-theme-surface),.62)}.bf9__capacity header strong{font-size:1.5rem}.capacity-track{position:relative;height:10px;margin-top:18px;border-radius:10px;background:rgba(var(--v-theme-on-surface),.08)}.capacity-track span{display:block;height:100%;border-radius:inherit;background:rgb(var(--v-theme-primary))}.capacity-track i{position:absolute;top:-5px;width:2px;height:20px;background:rgb(var(--v-theme-on-surface));opacity:.55}.capacity-labels{display:flex;justify-content:space-between;margin-top:7px;font-size:.72rem;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.bf9__summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.bf9__summary-grid article{display:flex;flex-direction:column;gap:8px}.bf9__summary-grid article>strong{font-size:1.18rem}.bf9__drill-card{cursor:pointer;transition:.18s ease}.bf9__drill-card:hover,.bf9__drill-card:focus-visible{border-color:rgb(var(--v-theme-primary));transform:translateY(-1px);outline:none}.bf9__drill-link{display:flex;align-items:center;margin-top:auto;color:rgb(var(--v-theme-primary));font-size:.8rem}.bf9__facts{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.bf9__facts>div{display:flex;flex-direction:column}.torrent-list,.event-list,.insight-list{display:flex;flex-direction:column;margin-top:12px}.torrent-list article{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;align-items:center;gap:14px;padding:12px 4px;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.torrent-list article>div,.event-list article>div,.insight-list article>div:first-child{display:flex;flex-direction:column;min-width:0}.torrent-list strong,.insight-list strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.event-list article,.insight-list article{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 4px;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.insight-list small{color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.insight-metric{align-items:flex-end;flex-shrink:0}.event-list small.reason{color:rgb(var(--v-theme-warning))}.event-list small.error{color:rgb(var(--v-theme-error))}.bf9__empty{display:flex;flex-direction:column;align-items:center;gap:8px;padding:60px 20px;text-align:center;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.bf9__empty.small{padding:28px}.mb-3{margin-bottom:12px!important}.mt-4{margin-top:18px}@media(max-width:959px){.bf9__summary-grid{grid-template-columns:1fr}.bf9__facts{grid-template-columns:repeat(2,1fr)}.bf9__taskbar{align-items:flex-start;flex-direction:column}.torrent-list article{grid-template-columns:minmax(0,1fr) auto}.torrent-list article>span:nth-of-type(2){display:none}}@media(max-width:599px){.bf9{padding:12px}.bf9__header{align-items:flex-start}.bf9__header-actions .v-btn:not(:last-child){display:none}.bf9__attention{align-items:flex-start;flex-direction:column}.bf9__facts{grid-template-columns:1fr}.capacity-labels span:nth-child(2){display:none}.insight-list article{align-items:flex-start;flex-direction:column}.insight-metric{align-items:flex-start}}
.bf9__settings{display:flex;flex-direction:column;gap:22px}.bf9__settings section{display:flex;flex-direction:column;gap:12px}.bf9__settings p{margin:0;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.settings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.settings-title{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}@media(max-width:599px){.bf9__header{flex-direction:column}.bf9__header-actions .v-btn:not(:last-child){display:inline-flex}.settings-grid{grid-template-columns:1fr}.settings-title{flex-direction:column}}
</style>

<style scoped>
.bf9{gap:14px}.bf9__conclusion{margin-top:14px;padding:16px;border-radius:14px}.bf9__conclusion h2{font-size:1.1rem}.bf9__conclusion p{font-size:.88rem}.bf9__summary-grid article{gap:6px;padding:15px}.bf9__summary-grid p{font-size:.84rem;line-height:1.45}.bf9__summary-grid small{font-size:.75rem}.bf9__summary-grid h3{font-size:.92rem}.bf9__capacity{padding:14px 16px}.download-issue-actions{display:flex;align-items:center}.bf9__insight small{line-height:1.55}@media(max-width:599px){.download-issue-actions{margin-left:0}}
</style>

<style scoped>
.insight-intro{display:flex;align-items:center;justify-content:space-between;gap:16px}
.event-list article{align-items:flex-start;justify-content:flex-start}
.bf9__cleanup-progress{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px}.bf9__cleanup-progress>div{display:flex;align-items:center;gap:12px}.bf9__cleanup-progress .v-progress-linear{grid-column:1/-1}.bf9__cleanup-progress p{margin-top:3px!important}
.preview-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.preview-metrics>div{display:flex;flex-direction:column;padding:12px;border-radius:12px;background:rgba(var(--v-theme-primary),.08)}.preview-metrics span{font-size:.8rem;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}.preview-list{max-height:300px;overflow:auto;border-top:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.preview-list>div{display:flex;justify-content:space-between;gap:12px;padding:10px 2px;border-bottom:1px solid rgba(var(--v-border-color),var(--v-border-opacity))}.preview-list span{white-space:nowrap;color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}
.download-issue-actions{margin-left:auto;flex-shrink:0}.manual-delete-target{display:flex;flex-direction:column;gap:4px;margin:16px 0;padding:12px;border-radius:10px;background:rgba(var(--v-theme-error),.08)}.manual-delete-target strong{overflow-wrap:anywhere}.manual-delete-target span{color:rgba(var(--v-theme-on-surface),var(--v-medium-emphasis-opacity))}
@media(max-width:599px){.insight-intro{align-items:flex-start;flex-direction:column}}
</style>

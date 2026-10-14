import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, f as formatBytes, u as unwrapResponse, a as torrentProgress, b as formatDateTime } from './_plugin-vue_export-helper-zQLOLLGb.js';

const profileDefaults = {
  conservative: { selection_min_score: 40, max_add_per_run: 2, deletion_score_threshold: 35, candidate_confirmations: 4, confirmation_minutes: 60, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 2, max_delete_percent_day: 3, max_release_percent_run: 2, max_release_percent_day: 4, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 720, demand_confirmations: 2, tracker_demand_grace_hours: 24 },
  balanced: { selection_min_score: 30, max_add_per_run: 5, deletion_score_threshold: 40, candidate_confirmations: 3, confirmation_minutes: 30, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 3, max_delete_percent_day: 5, max_release_percent_run: 4, max_release_percent_day: 8, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 360, demand_confirmations: 2, tracker_demand_grace_hours: 24 },
  aggressive: { selection_min_score: 22, max_add_per_run: 8, deletion_score_threshold: 48, candidate_confirmations: 2, confirmation_minutes: 15, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 5, max_delete_percent_day: 10, max_release_percent_run: 8, max_release_percent_day: 15, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 180, demand_confirmations: 2, tracker_demand_grace_hours: 24 },
};

function newTaskV9() {
  return {
    schema_version: 9,
    engine_mode: 'performance',
    id: '',
    revision: 1,
    identity: { name: '', site_id: null, downloader: '', save_path: null, tag: null, enabled: true, notify: true },
    schedule: { brush_interval: 10, check_interval: 5, cron: null, active_time_range: null },
    goal: { enabled: false, ratio_target: null, reached_behavior: 'continue' },
    capacity: { limit_gb: null, max_downloads: null, upload_limit_kbps: null, download_limit_kbps: null, torrent_upload_limit_kbps: null, torrent_download_limit_kbps: null },
    selection: { enabled: true, source: 'page', promotion: 'free', exclude_hr: true, site_hr_active: false, exclude_subscriptions: true, size_min_gb: 0.5, size_max_gb: null, seeder_range: null, published_min_minutes: null, published_max_minutes: null, timezone_offset: 0, include: null, exclude: null },
    deletion: { enabled: false, min_seed_hours: null, exclude_tags: null, delete_data: true, invalid_tracker_cleanup: false, idle_zero_upload_hours: 72, invalid_tracker_confirmations: 2, paused: false, observation_started_at: null, observation_until: null, observation_extensions: 0 },
    strategy: { profile: 'balanced', overrides: { ...profileDefaults.balanced } },
    health: { stalled_confirmations: 3, stalled_window_minutes: 30, slow_after_hours: 6, slow_speed_kbps: 128, max_download_hours: 48, auto_repair: true, pause_after_failed_repair: true },
  }
}

function cloneTaskV9(task) {
  const base = newTaskV9();
  if (!task?.identity) return structuredClone(base)
  return structuredClone({
    ...base,
    ...task,
    identity: { ...base.identity, ...task.identity }, schedule: { ...base.schedule, ...task.schedule },
    goal: { ...base.goal, ...task.goal }, capacity: { ...base.capacity, ...task.capacity },
    selection: { ...base.selection, ...task.selection }, deletion: { ...base.deletion, ...task.deletion },
    strategy: { ...base.strategy, ...task.strategy, overrides: { ...base.strategy.overrides, ...(task.strategy?.overrides || {}) } },
    health: { ...base.health, ...task.health },
  })
}

function normalizeTaskV9(task) {
  const result = cloneTaskV9(task);
  const optionalNumbers = [
    ['goal','ratio_target'], ['capacity','limit_gb'], ['capacity','max_downloads'],
    ['capacity','upload_limit_kbps'], ['capacity','download_limit_kbps'],
    ['capacity','torrent_upload_limit_kbps'], ['capacity','torrent_download_limit_kbps'],
    ['selection','size_min_gb'], ['selection','size_max_gb'],
    ['selection','published_min_minutes'], ['selection','published_max_minutes'],
    ['deletion','min_seed_hours'], ['deletion','idle_zero_upload_hours'], ['strategy','overrides','max_release_gb_run'],
    ['strategy','overrides','max_release_gb_day'],
  ];
  optionalNumbers.forEach(path => {
    const parent = path.slice(0, -1).reduce((value, key) => value[key], result);
    const key = path.at(-1);
    const value = parent[key];
    parent[key] = value === '' || value === undefined ? null : value === null ? null : Number(value);
  })
  ;[
    ['identity','save_path'], ['identity','tag'], ['schedule','cron'], ['schedule','active_time_range'],
    ['selection','seeder_range'], ['selection','include'], ['selection','exclude'], ['deletion','exclude_tags'],
  ].forEach(path => {
    const parent = path.slice(0, -1).reduce((value, key) => value[key], result);
    const key = path.at(-1);
    parent[key] = String(parent[key] || '').trim() || null;
  });
  const savePath = result.identity.save_path;
  result.identity.save_path = savePath && typeof savePath === 'object'
    ? String([savePath.value, savePath.path, savePath.title].find(item => item !== null && item !== undefined && typeof item !== 'function') ?? '').trim() || null
    : String(savePath || '').trim() || null;
  return result
}

function applyProfile(task, profile) {
  if (!profileDefaults[profile]) return { ...task, strategy: { ...task.strategy, profile: 'custom' } }
  return { ...task, strategy: { profile, overrides: { ...profileDefaults[profile] } } }
}

function profileLabel(profile) {
  return ({ conservative: '保守', balanced: '均衡', aggressive: '冲量', custom: '自定义' })[profile] || '均衡'
}

function promotionLabel(value) {
  return ({ all: '全部种子', free: '免费种子', '2xfree': '2X免费种子' })[value] || '免费种子'
}

function taskPreview(task, siteName = '当前站点') {
  const frequency = task.schedule.cron ? `按 ${task.schedule.cron} 计划` : `每${task.schedule.brush_interval}分钟`;
  const selection = `${frequency}检查${siteName}${promotionLabel(task.selection.promotion)}，每轮最多新增${task.strategy.overrides.max_add_per_run}个`;
  if (!task.deletion.enabled) return `${selection}；自动删种关闭，只监控种子状态。`
  const limit = Number(task.capacity.limit_gb || 0);
  const idle = task.deletion.idle_zero_upload_hours ? `；完整连续${task.deletion.idle_zero_upload_hours}小时零上传且已满足保种的种子会主动淘汰，不等待空间满` : '';
  return `${selection}；最多使用${limit.toFixed(0)}GB，剩余空间足够就能继续新增${idle}；保种不足${task.deletion.min_seed_hours || 0}小时、正在上传、有活动连接或未完成的种子不会删除；低收益种子按实际表现淘汰，不使用容量停止线或GB释放额度。`
}

function healthTone(level) {
  return ({ error: 'error', warning: 'warning', info: 'info', success: 'success' })[level] || 'secondary'
}

/** Compact task navigation: searching and switching never modify task settings. */
function taskNavigationItems(tasks = []) {
  return tasks.filter(task => task?.id).map(task => {
    const summary = task.strategy?.ui_summary || {};
    const name = String(task.name || task.site_name || '未命名任务');
    const site = String(task.site_name || '站点未设置');
    const downloader = String(task.downloader || '');
    return {
      id: String(task.id), name, site, downloader,
      displayTitle: site === name ? name : `${name} · ${site}`,
      searchText: [name, site, downloader].join(' '),
      health: summary.health || {},
      needsAttention: ['error', 'warning'].includes(summary.health?.level) || Number(summary.download?.issue_count || 0) > 0,
      enabled: Boolean(task.enabled),
      size: task.seeding_size,
      uploaded: summary.performance?.uploaded_bytes_24h ?? null,
      partialUpload: summary.performance?.observation_complete === false,
    }
  })
}

function filterTaskNavigation(value, query, item) {
  const text = String(item?.raw?.searchText || value || '').toLocaleLowerCase();
  return text.includes(String(query || '').trim().toLocaleLowerCase())
}

function taskNavigationSummary(items = []) {
  return {
    total: items.length,
    enabled: items.filter(item => item.enabled).length,
    attention: items.filter(item => item.needsAttention).length,
  }
}

function adjacentTaskId(items, selectedId, direction) {
  const index = items.findIndex(item => item.id === selectedId);
  const next = index + direction;
  return index >= 0 && next >= 0 && next < items.length ? items[next].id : null
}

function validTaskSelection(items, selectedId, nextId) {
  return typeof nextId === 'string' && nextId !== selectedId && items.some(item => item.id === nextId)
}

const {createElementVNode:_createElementVNode$6,unref:_unref$6,toDisplayString:_toDisplayString$6,createTextVNode:_createTextVNode$6,resolveComponent:_resolveComponent$6,withCtx:_withCtx$5,createVNode:_createVNode$6,Fragment:_Fragment$5,openBlock:_openBlock$6,createElementBlock:_createElementBlock$6,createCommentVNode:_createCommentVNode$6,mergeProps:_mergeProps,createBlock:_createBlock$5,normalizeClass:_normalizeClass$3} = await importShared('vue');


const _hoisted_1$6 = {
  key: 0,
  class: "task-navigator",
  "aria-label": "刷流任务切换"
};
const _hoisted_2$6 = { class: "task-navigator__picker" };
const _hoisted_3$6 = { class: "task-navigator__control" };
const _hoisted_4$5 = { class: "task-navigator__option-title" };
const _hoisted_5$5 = ["title"];
const _hoisted_6$5 = { class: "task-navigator__option-meta" };
const _hoisted_7$5 = {
  key: 0,
  class: "task-navigator__arrows"
};
const _hoisted_8$5 = {
  class: "task-navigator__counts",
  "aria-label": "全部任务概况"
};

const {computed: computed$4} = await importShared('vue');


const _sfc_main$6 = {
  __name: 'TaskNavigator',
  props: { tasks: { type: Array, default: () => [] }, selectedId: { type: String, default: '' } },
  emits: ['select'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const items = computed$4(() => taskNavigationItems(props.tasks));
const counts = computed$4(() => taskNavigationSummary(items.value));
const previous = computed$4(() => adjacentTaskId(items.value, props.selectedId, -1));
const next = computed$4(() => adjacentTaskId(items.value, props.selectedId, 1));
function select(id) {
  if (validTaskSelection(items.value, props.selectedId, id)) emit('select', id);
}

return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$6("VChip");
  const _component_VListItem = _resolveComponent$6("VListItem");
  const _component_VAutocomplete = _resolveComponent$6("VAutocomplete");
  const _component_VBtn = _resolveComponent$6("VBtn");
  const _component_VIcon = _resolveComponent$6("VIcon");

  return (items.value.length)
    ? (_openBlock$6(), _createElementBlock$6("section", _hoisted_1$6, [
        _createElementVNode$6("div", _hoisted_2$6, [
          _createElementVNode$6("div", _hoisted_3$6, [
            _cache[2] || (_cache[2] = _createElementVNode$6("span", { class: "task-navigator__caption" }, "当前任务 · 点击切换或搜索", -1)),
            _createVNode$6(_component_VAutocomplete, {
              "model-value": __props.selectedId,
              items: items.value,
              "item-title": "displayTitle",
              "item-value": "id",
              "custom-filter": _unref$6(filterTaskNavigation),
              "aria-label": "切换刷流任务",
              placeholder: "搜索任务、站点或下载器",
              variant: "outlined",
              density: "compact",
              "hide-details": "",
              "menu-props": { maxHeight: 360 },
              "no-data-text": "没有匹配的任务，试试站点或下载器名称",
              "onUpdate:modelValue": select
            }, {
              item: _withCtx$5(({ props: optionProps, item }) => [
                _createVNode$6(_component_VListItem, _mergeProps(optionProps, {
                  role: "option",
                  "aria-selected": item.value === __props.selectedId,
                  class: "task-navigator__option",
                  title: item.raw.name,
                  subtitle: [item.raw.site, item.raw.downloader].filter(Boolean).join(' · ')
                }), {
                  title: _withCtx$5(() => [
                    _createElementVNode$6("div", _hoisted_4$5, [
                      _createElementVNode$6("strong", {
                        title: item.raw.name
                      }, _toDisplayString$6(item.raw.name), 9, _hoisted_5$5),
                      _createVNode$6(_component_VChip, {
                        size: "x-small",
                        color: _unref$6(healthTone)(item.raw.health.level),
                        variant: "tonal"
                      }, {
                        default: _withCtx$5(() => [
                          _createTextVNode$6(_toDisplayString$6(item.raw.health.title || '等待检查'), 1)
                        ]),
                        _: 2
                      }, 1032, ["color"])
                    ])
                  ]),
                  subtitle: _withCtx$5(() => [
                    _createElementVNode$6("div", _hoisted_6$5, [
                      _createElementVNode$6("span", null, [
                        _createTextVNode$6(_toDisplayString$6(item.raw.site), 1),
                        (item.raw.downloader)
                          ? (_openBlock$6(), _createElementBlock$6(_Fragment$5, { key: 0 }, [
                              _createTextVNode$6(" · " + _toDisplayString$6(item.raw.downloader), 1)
                            ], 64))
                          : _createCommentVNode$6("", true)
                      ]),
                      _createElementVNode$6("span", null, _toDisplayString$6(_unref$6(formatBytes)(item.raw.size)) + " · 24h上传 " + _toDisplayString$6(item.raw.uploaded === null ? '待统计' : _unref$6(formatBytes)(item.raw.uploaded)) + _toDisplayString$6(item.raw.partialUpload ? '（部分）' : ''), 1)
                    ])
                  ]),
                  _: 2
                }, 1040, ["aria-selected", "title", "subtitle"])
              ]),
              _: 1
            }, 8, ["model-value", "items", "custom-filter"])
          ]),
          (items.value.length > 1)
            ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_7$5, [
                _createVNode$6(_component_VBtn, {
                  icon: "mdi-chevron-left",
                  "aria-label": "上一个任务",
                  title: "上一个任务",
                  size: "small",
                  variant: "text",
                  disabled: !previous.value,
                  onClick: _cache[0] || (_cache[0] = $event => (select(previous.value)))
                }, null, 8, ["disabled"]),
                _createVNode$6(_component_VBtn, {
                  icon: "mdi-chevron-right",
                  "aria-label": "下一个任务",
                  title: "下一个任务",
                  size: "small",
                  variant: "text",
                  disabled: !next.value,
                  onClick: _cache[1] || (_cache[1] = $event => (select(next.value)))
                }, null, 8, ["disabled"])
              ]))
            : _createCommentVNode$6("", true)
        ]),
        _createElementVNode$6("div", _hoisted_8$5, [
          _createElementVNode$6("span", null, [
            _cache[3] || (_cache[3] = _createTextVNode$6("共 ", -1)),
            _createElementVNode$6("strong", null, _toDisplayString$6(counts.value.total), 1),
            _cache[4] || (_cache[4] = _createTextVNode$6(" 个任务", -1))
          ]),
          _createElementVNode$6("span", null, [
            _cache[5] || (_cache[5] = _createTextVNode$6("启用 ", -1)),
            _createElementVNode$6("strong", null, _toDisplayString$6(counts.value.enabled), 1)
          ]),
          _createElementVNode$6("span", {
            class: _normalizeClass$3({ 'task-navigator__attention': counts.value.attention })
          }, [
            (counts.value.attention)
              ? (_openBlock$6(), _createBlock$5(_component_VIcon, {
                  key: 0,
                  icon: "mdi-alert-circle-outline",
                  size: "16"
                }))
              : _createCommentVNode$6("", true),
            _cache[6] || (_cache[6] = _createTextVNode$6("需关注 ", -1)),
            _createElementVNode$6("strong", null, _toDisplayString$6(counts.value.attention), 1)
          ], 2)
        ])
      ]))
    : _createCommentVNode$6("", true)
}
}

};
const TaskNavigator = /*#__PURE__*/_export_sfc(_sfc_main$6, [['__scopeId',"data-v-8a2936b5"]]);

const {unref:_unref$5,toDisplayString:_toDisplayString$5,createTextVNode:_createTextVNode$5,resolveComponent:_resolveComponent$5,withCtx:_withCtx$4,createVNode:_createVNode$5,renderList:_renderList$4,Fragment:_Fragment$4,openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,createElementVNode:_createElementVNode$5,normalizeClass:_normalizeClass$2,createBlock:_createBlock$4,createCommentVNode:_createCommentVNode$5} = await importShared('vue');


const _hoisted_1$5 = { class: "wizard__steps" };
const _hoisted_2$5 = ["onClick"];
const _hoisted_3$5 = { class: "wizard__content" };
const _hoisted_4$4 = {
  key: 1,
  class: "wizard-section"
};
const _hoisted_5$4 = { class: "switches" };
const _hoisted_6$4 = {
  key: 2,
  class: "wizard-section"
};
const _hoisted_7$4 = {
  key: 3,
  class: "wizard-section"
};
const _hoisted_8$4 = { class: "profile-grid" };
const _hoisted_9$3 = ["onClick"];
const _hoisted_10$3 = { class: "switches" };
const _hoisted_11$3 = {
  key: 4,
  class: "wizard-section"
};
const _hoisted_12$2 = { class: "switches" };
const _hoisted_13$2 = { class: "wizard__summary" };

const {computed: computed$3,ref: ref$1,watch: watch$1} = await importShared('vue');

const {useDisplay: useDisplay$3} = await importShared('vuetify');


const _sfc_main$5 = {
  __name: 'TaskWizardV9',
  props: { modelValue: Boolean, task: Object, sites: { type: Array, default: () => [] }, downloaders: { type: Array, default: () => [] }, api: { type: Object, default: () => ({}) }, pluginBase: { type: String, default: 'plugin/SmartBrushFlow' }, saving: Boolean },
  emits: ['update:modelValue', 'save'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const display = useDisplay$3();
const step = ref$1(1);
const draft = ref$1(cloneTaskV9());
const error = ref$1('');
const pathOptions = ref$1([]);
const pathsLoading = ref$1(false);
const pathsError = ref$1('');
const advanced = ref$1(false);
const saveConfirmOpen = ref$1(false);
const steps = ['站点与任务', '空间与速度', '选种方式', '删种与安全'];
const siteName = computed$3(() => props.sites.find(item => Number(item.value) === Number(draft.value.identity.site_id))?.title || '当前站点');
const preview = computed$3(() => taskPreview(draft.value, siteName.value));
function normalizePathValue(value) {
  if (value && typeof value === 'object') {
    const candidate = [value.value, value.path, value.title].find(item => item !== null && item !== undefined && typeof item !== 'function');
    return String(candidate ?? '').trim() || null
  }
  return String(value ?? '').trim() || null
}
const directoryItems = computed$3(() => {
  const items = [{ title: '使用下载器默认目录', value: '' }];
  const current = normalizePathValue(draft.value.identity.save_path);
  if (draft.value.identity.save_path !== current) draft.value.identity.save_path = current;
  if (current && !pathOptions.value.some(item => item.value === current)) {
    items.push({ title: current, subtitle: '当前任务配置', value: current, source: '当前任务配置' });
  }
  return [...items, ...pathOptions.value]
});

let pathRequest = 0;
async function loadPaths(downloader = draft.value.identity.downloader) {
  const request = ++pathRequest;
  pathOptions.value = [];
  pathsError.value = '';
  if (!downloader || typeof props.api?.get !== 'function') return
  pathsLoading.value = true;
  try {
    const data = unwrapResponse(await props.api.get(`${props.pluginBase}/downloaders/${encodeURIComponent(downloader)}/paths`)) || {};
    if (request !== pathRequest) return
    pathOptions.value = (data.paths || []).map(item => {
      const value = normalizePathValue(item?.value ?? item);
      return {
      title: normalizePathValue(item?.title) || value,
      subtitle: item.source || '下载器返回',
      value,
      source: item.source,
      }
    }).filter(item => item.value);
    pathsError.value = data.warning || '';
  } catch (err) {
    if (request === pathRequest) pathsError.value = '暂时读不到下载器目录，仍可手动输入路径';
  } finally {
    if (request === pathRequest) pathsLoading.value = false;
  }
}

watch$1(() => props.modelValue, value => {
  if (value) {
    draft.value = cloneTaskV9(props.task);
    step.value = 1;
    error.value = '';
    pathsError.value = '';
    advanced.value = false;
    loadPaths();
  }
});
watch$1(() => draft.value.identity.downloader, (value, previous) => {
  if (!props.modelValue || !value || value === previous) return
  if (previous) draft.value.identity.save_path = null;
  loadPaths(value);
});

function close() { emit('update:modelValue', false); }
function chooseProfile(profile) { draft.value = applyProfile(draft.value, profile); }
function markCustom() { draft.value.strategy.profile = 'custom'; }
function validateStep(target = step.value) {
  if (target === 1 && (!draft.value.identity.name.trim() || !draft.value.identity.site_id || !draft.value.identity.downloader)) return '请填写任务名称、站点和下载器'
  if (target === 2 && draft.value.deletion.enabled && !Number(draft.value.capacity.limit_gb || 0)) return '启用自动删种前必须设置任务容量'
  if (target === 4 && draft.value.deletion.enabled && !Number(draft.value.deletion.min_seed_hours || 0)) return '请填写当前站点最低保种时间'
  return ''
}
function next() { const message = validateStep(); if (message) { error.value = message; return } error.value = ''; step.value = Math.min(step.value + 1, 4); }
function previous() { error.value = ''; step.value = Math.max(step.value - 1, 1); }
function save() {
  for (const target of [1, 2, 4]) { const message = validateStep(target); if (message) { step.value = target; error.value = message; return } }
  saveConfirmOpen.value = true;
}
function confirmSave() {
  saveConfirmOpen.value = false;
  draft.value.identity.save_path = normalizePathValue(draft.value.identity.save_path);
  emit('save', normalizeTaskV9(draft.value));
}

return (_ctx, _cache) => {
  const _component_VToolbarTitle = _resolveComponent$5("VToolbarTitle");
  const _component_VSpacer = _resolveComponent$5("VSpacer");
  const _component_VBtn = _resolveComponent$5("VBtn");
  const _component_VToolbar = _resolveComponent$5("VToolbar");
  const _component_VDivider = _resolveComponent$5("VDivider");
  const _component_VAlert = _resolveComponent$5("VAlert");
  const _component_VTextField = _resolveComponent$5("VTextField");
  const _component_VCol = _resolveComponent$5("VCol");
  const _component_VSelect = _resolveComponent$5("VSelect");
  const _component_VCombobox = _resolveComponent$5("VCombobox");
  const _component_VRow = _resolveComponent$5("VRow");
  const _component_VSwitch = _resolveComponent$5("VSwitch");
  const _component_VExpansionPanelTitle = _resolveComponent$5("VExpansionPanelTitle");
  const _component_VExpansionPanelText = _resolveComponent$5("VExpansionPanelText");
  const _component_VExpansionPanel = _resolveComponent$5("VExpansionPanel");
  const _component_VExpansionPanels = _resolveComponent$5("VExpansionPanels");
  const _component_VIcon = _resolveComponent$5("VIcon");
  const _component_VChip = _resolveComponent$5("VChip");
  const _component_VCardText = _resolveComponent$5("VCardText");
  const _component_VCardActions = _resolveComponent$5("VCardActions");
  const _component_VCard = _resolveComponent$5("VCard");
  const _component_VCardTitle = _resolveComponent$5("VCardTitle");
  const _component_VDialog = _resolveComponent$5("VDialog");

  return (_openBlock$5(), _createBlock$4(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$5(display).smAndDown.value,
    "max-width": "72rem",
    scrollable: "",
    "onUpdate:modelValue": _cache[47] || (_cache[47] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$4(() => [
      _createVNode$5(_component_VCard, { class: "wizard" }, {
        default: _withCtx$4(() => [
          _createVNode$5(_component_VToolbar, { color: "transparent" }, {
            default: _withCtx$4(() => [
              _createVNode$5(_component_VToolbarTitle, null, {
                default: _withCtx$4(() => [
                  _createTextVNode$5(_toDisplayString$5(draft.value.id ? '编辑任务' : '新建任务'), 1)
                ]),
                _: 1
              }),
              _createVNode$5(_component_VSpacer),
              _createVNode$5(_component_VBtn, {
                icon: "mdi-close",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$5(_component_VDivider),
          _createVNode$5(_component_VCardText, { class: "wizard__body" }, {
            default: _withCtx$4(() => [
              _createElementVNode$5("nav", _hoisted_1$5, [
                (_openBlock$5(), _createElementBlock$5(_Fragment$4, null, _renderList$4(steps, (label, index) => {
                  return _createElementVNode$5("button", {
                    key: label,
                    type: "button",
                    class: _normalizeClass$2({active:step.value===index+1,done:step.value>index+1}),
                    onClick: $event => (step.value=index+1)
                  }, [
                    _createElementVNode$5("span", null, _toDisplayString$5(index+1), 1),
                    _createTextVNode$5(_toDisplayString$5(label), 1)
                  ], 10, _hoisted_2$5)
                }), 64))
              ]),
              _createElementVNode$5("main", _hoisted_3$5, [
                (error.value)
                  ? (_openBlock$5(), _createBlock$4(_component_VAlert, {
                      key: 0,
                      type: "error",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx$4(() => [
                        _createTextVNode$5(_toDisplayString$5(error.value), 1)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode$5("", true),
                (step.value===1)
                  ? (_openBlock$5(), _createElementBlock$5("section", _hoisted_4$4, [
                      _cache[48] || (_cache[48] = _createElementVNode$5("div", null, [
                        _createElementVNode$5("h3", null, "这个任务刷哪个站？"),
                        _createElementVNode$5("p", null, "站点和下载器保存后仍可修改，历史数据会继续关联。")
                      ], -1)),
                      _createVNode$5(_component_VRow, null, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.identity.name,
                                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((draft.value.identity.name) = $event)),
                                label: "任务名称"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VSelect, {
                                modelValue: draft.value.identity.site_id,
                                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((draft.value.identity.site_id) = $event)),
                                items: __props.sites,
                                label: "站点"
                              }, null, 8, ["modelValue", "items"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VSelect, {
                                modelValue: draft.value.identity.downloader,
                                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((draft.value.identity.downloader) = $event)),
                                items: __props.downloaders,
                                label: "下载器"
                              }, null, 8, ["modelValue", "items"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VCombobox, {
                                modelValue: draft.value.identity.save_path,
                                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((draft.value.identity.save_path) = $event)),
                                items: directoryItems.value,
                                "item-title": "title",
                                "item-value": "value",
                                "return-object": false,
                                label: "保存目录",
                                placeholder: "选择下载器目录，或手动输入",
                                "prepend-inner-icon": "mdi-folder-search-outline",
                                clearable: "",
                                loading: pathsLoading.value,
                                hint: "目录来自所选下载器的实际配置和现有任务；留空使用默认目录",
                                "persistent-hint": ""
                              }, null, 8, ["modelValue", "items", "loading"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      (pathsError.value)
                        ? (_openBlock$5(), _createBlock$4(_component_VAlert, {
                            key: 0,
                            type: "info",
                            variant: "tonal",
                            density: "compact"
                          }, {
                            default: _withCtx$4(() => [
                              _createTextVNode$5(_toDisplayString$5(pathsError.value), 1)
                            ]),
                            _: 1
                          }))
                        : _createCommentVNode$5("", true),
                      _createVNode$5(_component_VRow, null, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.schedule.brush_interval,
                                "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((draft.value.schedule.brush_interval) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                label: "选种周期（分钟）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.schedule.check_interval,
                                "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((draft.value.schedule.check_interval) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                label: "检查周期（分钟）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.schedule.active_time_range,
                                "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((draft.value.schedule.active_time_range) = $event)),
                                label: "运行时段",
                                placeholder: "全天或 00:00-08:00"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createElementVNode$5("div", _hoisted_5$4, [
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.identity.enabled,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((draft.value.identity.enabled) = $event)),
                          label: "启用任务",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.identity.notify,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((draft.value.identity.notify) = $event)),
                          label: "发送通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.goal.enabled,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((draft.value.goal.enabled) = $event)),
                          label: "设置分享率目标",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      (draft.value.goal.enabled)
                        ? (_openBlock$5(), _createBlock$4(_component_VRow, { key: 1 }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VCol, {
                                cols: "12",
                                md: "6"
                              }, {
                                default: _withCtx$4(() => [
                                  _createVNode$5(_component_VTextField, {
                                    modelValue: draft.value.goal.ratio_target,
                                    "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((draft.value.goal.ratio_target) = $event)),
                                    modelModifiers: { number: true },
                                    type: "number",
                                    step: "0.01",
                                    label: "目标分享率"
                                  }, null, 8, ["modelValue"])
                                ]),
                                _: 1
                              }),
                              _createVNode$5(_component_VCol, {
                                cols: "12",
                                md: "6"
                              }, {
                                default: _withCtx$4(() => [
                                  _createVNode$5(_component_VSelect, {
                                    modelValue: draft.value.goal.reached_behavior,
                                    "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((draft.value.goal.reached_behavior) = $event)),
                                    label: "达到目标后",
                                    items: [{title:'继续正常运行',value:'continue'},{title:'暂停新增',value:'pause'}]
                                  }, null, 8, ["modelValue"])
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          }))
                        : _createCommentVNode$5("", true)
                    ]))
                  : _createCommentVNode$5("", true),
                (step.value===2)
                  ? (_openBlock$5(), _createElementBlock$5("section", _hoisted_6$4, [
                      _cache[49] || (_cache[49] = _createElementVNode$5("div", null, [
                        _createElementVNode$5("h3", null, "给任务多少空间和带宽？"),
                        _createElementVNode$5("p", null, "任务容量独立计算；全局限制只负责阻止继续新增。")
                      ], -1)),
                      _createVNode$5(_component_VRow, null, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.capacity.limit_gb,
                                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((draft.value.capacity.limit_gb) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "0",
                                label: "任务容量上限（GB）",
                                hint: "仅阻止超上限新增；淘汰按种子实际表现决定",
                                "persistent-hint": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.capacity.max_downloads,
                                "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((draft.value.capacity.max_downloads) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                label: "同时下载数"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.capacity.upload_limit_kbps,
                                "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((draft.value.capacity.upload_limit_kbps) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                label: "总上传限速（KB/s）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.capacity.download_limit_kbps,
                                "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((draft.value.capacity.download_limit_kbps) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                label: "总下载限速（KB/s）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.selection.size_min_gb,
                                "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((draft.value.selection.size_min_gb) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                step: "0.1",
                                min: "0",
                                label: "最小种子体积（GB）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.selection.size_max_gb,
                                "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((draft.value.selection.size_max_gb) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                step: "0.1",
                                min: "0",
                                label: "最大种子体积（GB，可选）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]))
                  : _createCommentVNode$5("", true),
                (step.value===3)
                  ? (_openBlock$5(), _createElementBlock$5("section", _hoisted_7$4, [
                      _cache[50] || (_cache[50] = _createElementVNode$5("div", null, [
                        _createElementVNode$5("h3", null, "优先选择什么种子？"),
                        _createElementVNode$5("p", null, "明确的体积、H&R和文本规则始终是硬过滤。")
                      ], -1)),
                      _createElementVNode$5("div", _hoisted_8$4, [
                        (_openBlock$5(), _createElementBlock$5(_Fragment$4, null, _renderList$4(['conservative','balanced','aggressive'], (profile) => {
                          return _createElementVNode$5("button", {
                            key: profile,
                            type: "button",
                            class: _normalizeClass$2({active:draft.value.strategy.profile===profile}),
                            onClick: $event => (chooseProfile(profile))
                          }, [
                            _createElementVNode$5("strong", null, _toDisplayString$5(_unref$5(profileLabel)(profile)), 1),
                            _createElementVNode$5("span", null, _toDisplayString$5(profile==='conservative'?'更少新增，适合空间紧张':profile==='balanced'?'收益与稳定性平衡':'更积极抢新种'), 1)
                          ], 10, _hoisted_9$3)
                        }), 64))
                      ]),
                      _createVNode$5(_component_VRow, null, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VSelect, {
                                modelValue: draft.value.selection.promotion,
                                "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((draft.value.selection.promotion) = $event)),
                                label: "促销要求",
                                items: [{title:'全部',value:'all'},{title:'免费',value:'free'},{title:'2X免费',value:'2xfree'}]
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VSelect, {
                                modelValue: draft.value.selection.source,
                                "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((draft.value.selection.source) = $event)),
                                label: "种子来源",
                                items: [{title:'站点列表页',value:'page'},{title:'RSS',value:'rss'}]
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.strategy.overrides.max_add_per_run,
                                "onUpdate:modelValue": [
                                  _cache[20] || (_cache[20] = $event => ((draft.value.strategy.overrides.max_add_per_run) = $event)),
                                  markCustom
                                ],
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                max: "100",
                                label: "每轮最多新增"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createElementVNode$5("div", _hoisted_10$3, [
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.selection.enabled,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((draft.value.selection.enabled) = $event)),
                          label: "启用智能选种",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.selection.exclude_hr,
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((draft.value.selection.exclude_hr) = $event)),
                          label: "排除H&R",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.selection.exclude_subscriptions,
                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((draft.value.selection.exclude_subscriptions) = $event)),
                          label: "排除订阅内容",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createVNode$5(_component_VRow, null, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.selection.include,
                                "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((draft.value.selection.include) = $event)),
                                label: "必须包含（正则，可选）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.selection.exclude,
                                "onUpdate:modelValue": _cache[25] || (_cache[25] = $event => ((draft.value.selection.exclude) = $event)),
                                label: "必须排除（正则，可选）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      })
                    ]))
                  : _createCommentVNode$5("", true),
                (step.value===4)
                  ? (_openBlock$5(), _createElementBlock$5("section", _hoisted_11$3, [
                      _cache[57] || (_cache[57] = _createElementVNode$5("div", null, [
                        _createElementVNode$5("h3", null, "如何安全释放空间？"),
                        _createElementVNode$5("p", null, "新启用或风险扩大后先观察，不会立即删除。")
                      ], -1)),
                      _createVNode$5(_component_VSwitch, {
                        modelValue: draft.value.deletion.enabled,
                        "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((draft.value.deletion.enabled) = $event)),
                        color: "error",
                        label: "启用统一智能删种"
                      }, null, 8, ["modelValue"]),
                      _createVNode$5(_component_VSwitch, {
                        "model-value": draft.value.deletion.idle_zero_upload_hours!==null,
                        label: "主动淘汰长期零上传种子（不等空间满）",
                        "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => (draft.value.deletion.idle_zero_upload_hours=$event?72:null))
                      }, null, 8, ["model-value"]),
                      (draft.value.deletion.idle_zero_upload_hours!==null)
                        ? (_openBlock$5(), _createBlock$4(_component_VTextField, {
                            key: 0,
                            modelValue: draft.value.deletion.idle_zero_upload_hours,
                            "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((draft.value.deletion.idle_zero_upload_hours) = $event)),
                            modelModifiers: { number: true },
                            type: "number",
                            min: "24",
                            max: "720",
                            label: "连续零上传淘汰时间（小时）",
                            hint: "默认72小时；必须有完整真实观测且实际保种也达到该时长，站点最低保种、H&R和活动连接始终优先保护；不设释放GB额度",
                            "persistent-hint": ""
                          }, null, 8, ["modelValue"]))
                        : _createCommentVNode$5("", true),
                      (draft.value.deletion.enabled)
                        ? (_openBlock$5(), _createBlock$4(_component_VAlert, {
                            key: 1,
                            type: "info",
                            variant: "tonal"
                          }, {
                            default: _withCtx$4(() => [...(_cache[51] || (_cache[51] = [
                              _createTextVNode$5("前48小时只记录候选，不会实际删除；未完成、H&R、未到最低保种、正在上传或有活动连接的种子保持保护；Tracker单独报下载者时等待实际上传验证。", -1)
                            ]))]),
                            _: 1
                          }))
                        : _createCommentVNode$5("", true),
                      _createVNode$5(_component_VRow, null, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.deletion.min_seed_hours,
                                "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((draft.value.deletion.min_seed_hours) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                label: "站点最低保种时间（小时）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$5(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VTextField, {
                                modelValue: draft.value.deletion.exclude_tags,
                                "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((draft.value.deletion.exclude_tags) = $event)),
                                label: "永不删除的标签"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createElementVNode$5("div", _hoisted_12$2, [
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.deletion.delete_data,
                          "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((draft.value.deletion.delete_data) = $event)),
                          color: "error",
                          label: "清理时同时删除下载数据",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$5(_component_VSwitch, {
                          modelValue: draft.value.deletion.invalid_tracker_cleanup,
                          "onUpdate:modelValue": _cache[32] || (_cache[32] = $event => ((draft.value.deletion.invalid_tracker_cleanup) = $event)),
                          label: "清理Tracker明确拒绝的任务（保留数据）",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createVNode$5(_component_VExpansionPanels, {
                        modelValue: advanced.value,
                        "onUpdate:modelValue": _cache[44] || (_cache[44] = $event => ((advanced).value = $event)),
                        class: "mt-4"
                      }, {
                        default: _withCtx$4(() => [
                          _createVNode$5(_component_VExpansionPanel, { value: true }, {
                            default: _withCtx$4(() => [
                              _createVNode$5(_component_VExpansionPanelTitle, null, {
                                default: _withCtx$4(() => [...(_cache[52] || (_cache[52] = [
                                  _createTextVNode$5("高级设置（安全参数组）", -1)
                                ]))]),
                                _: 1
                              }),
                              _createVNode$5(_component_VExpansionPanelText, null, {
                                default: _withCtx$4(() => [
                                  _cache[54] || (_cache[54] = _createElementVNode$5("h4", null, "评分", -1)),
                                  _createVNode$5(_component_VRow, null, {
                                    default: _withCtx$4(() => [
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.selection_min_score,
                                            "onUpdate:modelValue": [
                                              _cache[33] || (_cache[33] = $event => ((draft.value.strategy.overrides.selection_min_score) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            max: "100",
                                            label: "选种最低分",
                                            hint: "越高越谨慎",
                                            "persistent-hint": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.deletion_score_threshold,
                                            "onUpdate:modelValue": [
                                              _cache[34] || (_cache[34] = $event => ((draft.value.strategy.overrides.deletion_score_threshold) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            max: "100",
                                            label: "低价值阈值",
                                            hint: "只处理低于该分且通过安全线的种子",
                                            "persistent-hint": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _cache[55] || (_cache[55] = _createElementVNode$5("h4", null, "候选确认", -1)),
                                  _createVNode$5(_component_VRow, null, {
                                    default: _withCtx$4(() => [
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.candidate_confirmations,
                                            "onUpdate:modelValue": [
                                              _cache[35] || (_cache[35] = $event => ((draft.value.strategy.overrides.candidate_confirmations) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "2",
                                            max: "6",
                                            label: "连续确认次数"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.confirmation_minutes,
                                            "onUpdate:modelValue": [
                                              _cache[36] || (_cache[36] = $event => ((draft.value.strategy.overrides.confirmation_minutes) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            label: "确认跨度（分钟）"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _cache[56] || (_cache[56] = _createElementVNode$5("h4", null, "下载健康", -1)),
                                  _createVNode$5(_component_VRow, null, {
                                    default: _withCtx$4(() => [
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.health.stalled_confirmations,
                                            "onUpdate:modelValue": _cache[37] || (_cache[37] = $event => ((draft.value.health.stalled_confirmations) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "2",
                                            max: "10",
                                            label: "卡住确认次数"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.health.stalled_window_minutes,
                                            "onUpdate:modelValue": _cache[38] || (_cache[38] = $event => ((draft.value.health.stalled_window_minutes) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "10",
                                            label: "卡住观察分钟"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.health.slow_after_hours,
                                            "onUpdate:modelValue": _cache[39] || (_cache[39] = $event => ((draft.value.health.slow_after_hours) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            label: "低速观察小时"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.health.slow_speed_kbps,
                                            "onUpdate:modelValue": _cache[40] || (_cache[40] = $event => ((draft.value.health.slow_speed_kbps) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            label: "低速阈值KB/s"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.health.max_download_hours,
                                            "onUpdate:modelValue": _cache[41] || (_cache[41] = $event => ((draft.value.health.max_download_hours) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            max: "720",
                                            label: "下载超时提醒（小时）",
                                            hint: "默认48小时，只标记处理，不自动删除未完成数据",
                                            "persistent-hint": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$5(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$4(() => [
                                          _createVNode$5(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.tracker_demand_grace_hours,
                                            "onUpdate:modelValue": [
                                              _cache[42] || (_cache[42] = $event => ((draft.value.strategy.overrides.tracker_demand_grace_hours) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "6",
                                            max: "168",
                                            label: "Tracker需求等待上传（小时）",
                                            hint: "完整观测期内零上传且无连接时，重新评估价值；真实上传立即保护",
                                            "persistent-hint": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _createVNode$5(_component_VBtn, {
                                    variant: "tonal",
                                    onClick: _cache[43] || (_cache[43] = $event => (chooseProfile(draft.value.strategy.profile==='custom'?'balanced':draft.value.strategy.profile)))
                                  }, {
                                    default: _withCtx$4(() => [...(_cache[53] || (_cache[53] = [
                                      _createTextVNode$5("恢复当前预设", -1)
                                    ]))]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              })
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }, 8, ["modelValue"])
                    ]))
                  : _createCommentVNode$5("", true)
              ]),
              _createElementVNode$5("aside", _hoisted_13$2, [
                _createVNode$5(_component_VIcon, {
                  icon: "mdi-text-box-check-outline",
                  color: "primary",
                  size: "28"
                }),
                _cache[58] || (_cache[58] = _createElementVNode$5("h3", null, "保存后会这样运行", -1)),
                _createElementVNode$5("p", null, _toDisplayString$5(preview.value), 1),
                _createVNode$5(_component_VChip, { variant: "tonal" }, {
                  default: _withCtx$4(() => [
                    _createTextVNode$5(_toDisplayString$5(_unref$5(profileLabel)(draft.value.strategy.profile)), 1)
                  ]),
                  _: 1
                })
              ])
            ]),
            _: 1
          }),
          _createVNode$5(_component_VDivider),
          _createVNode$5(_component_VCardActions, null, {
            default: _withCtx$4(() => [
              (step.value>1)
                ? (_openBlock$5(), _createBlock$4(_component_VBtn, {
                    key: 0,
                    variant: "text",
                    onClick: previous
                  }, {
                    default: _withCtx$4(() => [...(_cache[59] || (_cache[59] = [
                      _createTextVNode$5("上一步", -1)
                    ]))]),
                    _: 1
                  }))
                : _createCommentVNode$5("", true),
              _createVNode$5(_component_VSpacer),
              _createVNode$5(_component_VBtn, {
                variant: "text",
                onClick: close
              }, {
                default: _withCtx$4(() => [...(_cache[60] || (_cache[60] = [
                  _createTextVNode$5("取消", -1)
                ]))]),
                _: 1
              }),
              (step.value<4)
                ? (_openBlock$5(), _createBlock$4(_component_VBtn, {
                    key: 1,
                    color: "primary",
                    variant: "flat",
                    onClick: next
                  }, {
                    default: _withCtx$4(() => [...(_cache[61] || (_cache[61] = [
                      _createTextVNode$5("下一步", -1)
                    ]))]),
                    _: 1
                  }))
                : (_openBlock$5(), _createBlock$4(_component_VBtn, {
                    key: 2,
                    color: "primary",
                    variant: "flat",
                    loading: __props.saving,
                    onClick: save
                  }, {
                    default: _withCtx$4(() => [...(_cache[62] || (_cache[62] = [
                      _createTextVNode$5("保存任务", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"]))
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$5(_component_VDialog, {
        modelValue: saveConfirmOpen.value,
        "onUpdate:modelValue": _cache[46] || (_cache[46] = $event => ((saveConfirmOpen).value = $event)),
        "max-width": "32rem"
      }, {
        default: _withCtx$4(() => [
          _createVNode$5(_component_VCard, null, {
            default: _withCtx$4(() => [
              _createVNode$5(_component_VCardTitle, null, {
                default: _withCtx$4(() => [...(_cache[63] || (_cache[63] = [
                  _createTextVNode$5("确认保存这套规则", -1)
                ]))]),
                _: 1
              }),
              _createVNode$5(_component_VCardText, null, {
                default: _withCtx$4(() => [
                  _createElementVNode$5("p", null, _toDisplayString$5(preview.value), 1),
                  (draft.value.deletion.enabled)
                    ? (_openBlock$5(), _createBlock$4(_component_VAlert, {
                        key: 0,
                        type: "warning",
                        variant: "tonal",
                        class: "mt-4"
                      }, {
                        default: _withCtx$4(() => [
                          _createTextVNode$5(" 自动删种将" + _toDisplayString$5(draft.value.deletion.delete_data ? '删除下载器任务和对应数据' : '只移除下载器任务并保留数据') + "；新启用或放宽安全参数后会先进入观察期，硬安全线始终有效。 ", 1)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode$5("", true)
                ]),
                _: 1
              }),
              _createVNode$5(_component_VCardActions, null, {
                default: _withCtx$4(() => [
                  _createVNode$5(_component_VSpacer),
                  _createVNode$5(_component_VBtn, {
                    variant: "text",
                    onClick: _cache[45] || (_cache[45] = $event => (saveConfirmOpen.value=false))
                  }, {
                    default: _withCtx$4(() => [...(_cache[64] || (_cache[64] = [
                      _createTextVNode$5("返回修改", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode$5(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    loading: __props.saving,
                    onClick: confirmSave
                  }, {
                    default: _withCtx$4(() => [...(_cache[65] || (_cache[65] = [
                      _createTextVNode$5("确认保存", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"])
    ]),
    _: 1
  }, 8, ["model-value", "fullscreen"]))
}
}

};
const TaskWizardV9 = /*#__PURE__*/_export_sfc(_sfc_main$5, [['__scopeId',"data-v-6ecb6f0a"]]);

const {createElementVNode:_createElementVNode$4,unref:_unref$4,toDisplayString:_toDisplayString$4,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$4,createVNode:_createVNode$4,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$4} = await importShared('vue');


const _hoisted_1$4 = {
  class: "performance",
  "aria-label": "上传收益和保种情况"
};
const _hoisted_2$4 = ["disabled"];
const _hoisted_3$4 = {
  key: 0,
  class: "connection-note"
};

const _sfc_main$4 = {
  __name: 'TaskPerformance',
  props: { performance: { type: Object, default: () => ({}) }, loading: Boolean },
  emits: ['inspect'],
  setup(__props) {




return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$4("VIcon");

  return (_openBlock$4(), _createElementBlock$4("section", _hoisted_1$4, [
    _createElementVNode$4("div", null, [
      _cache[1] || (_cache[1] = _createElementVNode$4("span", null, "过去 24 小时上传", -1)),
      _createElementVNode$4("strong", null, _toDisplayString$4(__props.loading ? '—' : __props.performance.uploaded_bytes_24h === undefined ? '待统计' : _unref$4(formatBytes)(__props.performance.uploaded_bytes_24h)), 1),
      _createElementVNode$4("small", null, _toDisplayString$4(__props.performance.observation_complete ? '完整观测窗口' : `部分观测 · ${__props.performance.partial_window_count || 0} 个窗口尚不完整`), 1)
    ]),
    _createElementVNode$4("div", null, [
      _cache[2] || (_cache[2] = _createElementVNode$4("span", null, "有上传的种子", -1)),
      _createElementVNode$4("strong", null, [
        _createTextVNode$4(_toDisplayString$4(__props.performance.productive_count || 0), 1),
        _createElementVNode$4("em", null, " / " + _toDisplayString$4(__props.performance.active_count || 0), 1)
      ]),
      _cache[3] || (_cache[3] = _createElementVNode$4("small", null, "近期真正贡献上传", -1))
    ]),
    _createElementVNode$4("div", null, [
      _cache[5] || (_cache[5] = _createElementVNode$4("span", null, "已达到最低保种时长", -1)),
      _createElementVNode$4("strong", null, [
        _createTextVNode$4(_toDisplayString$4(__props.performance.minimum_met_count || 0), 1),
        _cache[4] || (_cache[4] = _createElementVNode$4("em", null, " 个", -1))
      ]),
      _createElementVNode$4("small", null, _toDisplayString$4(__props.performance.minimum_pending_count || 0) + " 个完成种子仍在保种", 1)
    ]),
    _createElementVNode$4("button", {
      type: "button",
      disabled: __props.loading,
      onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('inspect')))
    }, [
      _cache[6] || (_cache[6] = _createElementVNode$4("span", null, "已达保种 · 24 小时零上传", -1)),
      _createElementVNode$4("strong", null, _toDisplayString$4(_unref$4(formatBytes)(__props.performance.zero_upload_bytes)), 1),
      _createElementVNode$4("small", null, [
        _createTextVNode$4(_toDisplayString$4(__props.performance.zero_upload_count || 0) + " 个 · 查看原因 ", 1),
        _createVNode$4(_component_VIcon, {
          icon: "mdi-chevron-right",
          size: "14"
        })
      ])
    ], 8, _hoisted_2$4),
    (__props.performance.observation_complete&&__props.performance.tracker_demand_count>0&&__props.performance.connected_count===0&&__props.performance.productive_count===0)
      ? (_openBlock$4(), _createElementBlock$4("p", _hoisted_3$4, "Tracker 显示下载需求，但当前没有有效连接且近期零上传；若轮换种子后仍无改善，可核查下载器端口与 Tracker 连通性。"))
      : _createCommentVNode$4("", true)
  ]))
}
}

};
const TaskPerformance = /*#__PURE__*/_export_sfc(_sfc_main$4, [['__scopeId',"data-v-ab55a9c1"]]);

/** Workspace wording only; never mutates strategy or configuration. */
function deletionView(summary = {}, strategy = {}) {
  const deletion = summary.deletion || {};
  const taskPaused = summary.health?.status === 'task_paused';
  const pending = deletion.state === 'pending_evaluation' || !deletion.state;
  const title = taskPaused ? '任务暂停，暂不自动淘汰' : !deletion.enabled ? '自动淘汰未启用'
    : strategy.mode === 'shadow' ? '安全观察中，只记录计划'
    : strategy.mode === 'paused' ? '自动淘汰已暂停'
    : pending ? '等待检查种子表现'
    : Number(deletion.candidate_count || 0) > 0 ? '低收益种子等待安全复核' : '暂时没有需要淘汰的种子';
  return {
    title, pending,
    modeLabel: taskPaused ? '任务已暂停' : ({active:'自动淘汰开启',shadow:'安全观察中',paused:'自动淘汰暂停',disabled:'只选种，不淘汰'})[strategy.mode] || '等待检查',
    candidateLabel: pending ? '待检查' : String(deletion.candidate_count || 0),
    protectedLabel: pending ? '待检查' : String(deletion.protected_count || 0),
    rule: deletion.idle_zero_upload_hours
      ? '连续' + deletion.idle_zero_upload_hours + '小时零上传，满足保种和安全条件后主动淘汰。'
      : '长期零上传规则未启用；按近期真实收益和安全条件评估。',
    safety: deletion.min_seed_hours
      ? '最低保种' + deletion.min_seed_hours + '小时，未完成、H&R、正在上传和有效连接始终保护。'
      : '最低保种尚未设置，请完善安全设置；不会绕过保种保护。',
  }
}

function runPresentation(run = {}) {
  const selection = run.kind === 'brush';
  const title = selection ? '选种' : run.force_cleanup ? '手动安全清理' : '种子检查';
  const failed = run.success === false;
  const metrics = selection
    ? '新增 ' + (run.added_count || 0) + ' · 过滤 ' + (run.filtered_count || 0)
    : '活跃 ' + (run.active_count || 0) + ' · 候选 ' + (run.deletion_candidate_count || 0) + ' · 删除 ' + (run.deleted_count || 0);
  const deletionCompleted = Number(run.deleted_count || 0) > 0;
  return {
    title, metrics,
    result: failed ? '失败' : run.success === true ? '完成' : '运行记录',
    tone: failed ? 'error' : 'success',
    explanation: deletionCompleted
      ? '本次已删除 ' + run.deleted_count + ' 个通过最终安全复核的种子。' + (failed ? '其余处理未完成，请查看错误提示。' : '完整执行结果保留在审计记录中。')
      : run.deletion_message || '',
    error: run.error || '',
  }
}

const {unref:_unref$3,resolveComponent:_resolveComponent$3,createVNode:_createVNode$3,createElementVNode:_createElementVNode$3,toDisplayString:_toDisplayString$3,renderList:_renderList$3,Fragment:_Fragment$3,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,createTextVNode:_createTextVNode$3,withCtx:_withCtx$3,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$3} = await importShared('vue');


const _hoisted_1$3 = ["aria-busy"];
const _hoisted_2$3 = { class: "status-verdict" };
const _hoisted_3$3 = { class: "status-verdict__message" };
const _hoisted_4$3 = {
  key: 0,
  class: "status-verdict__actions"
};
const _hoisted_5$3 = { class: "status-section status-section--performance" };
const _hoisted_6$3 = { class: "status-columns" };
const _hoisted_7$3 = { class: "status-section status-section--decisions" };
const _hoisted_8$3 = { class: "section-heading" };
const _hoisted_9$2 = { class: "decision-totals" };
const _hoisted_10$2 = ["disabled"];
const _hoisted_11$2 = { key: 0 };
const _hoisted_12$1 = { key: 0 };
const _hoisted_13$1 = ["disabled"];
const _hoisted_14$1 = { key: 0 };
const _hoisted_15$1 = { key: 0 };
const _hoisted_16$1 = { class: "rule-note" };
const _hoisted_17$1 = {
  key: 0,
  class: "protection-details"
};
const _hoisted_18$1 = { class: "safety-note" };
const _hoisted_19$1 = {
  class: "status-section status-section--activity",
  "aria-label": "自动运行摘要"
};
const _hoisted_20$1 = ["disabled"];
const _hoisted_21$1 = ["disabled"];
const _hoisted_22$1 = { class: "activity-row activity-row--space" };
const _hoisted_23$1 = { class: "released-note" };
const _hoisted_24$1 = { class: "strategy-details" };
const _hoisted_25$1 = { class: "strategy-facts" };

const {computed: computed$2} = await importShared('vue');

const _sfc_main$3 = {
  __name: 'TaskStatusView',
  props: { summary: {type:Object,default:()=>({})}, strategy: {type:Object,default:()=>({})}, loading:Boolean, busy:Boolean },
  emits: ['inspect','action'],
  setup(__props) {

const props = __props;

const decision = computed$2(() => deletionView(props.summary, props.strategy));

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent$3("VIcon");
  const _component_VBtn = _resolveComponent$3("VBtn");
  const _component_VChip = _resolveComponent$3("VChip");
  const _component_VProgressLinear = _resolveComponent$3("VProgressLinear");

  return (_openBlock$3(), _createElementBlock$3("section", {
    class: "status-view",
    "aria-label": "任务表现与淘汰决策",
    "aria-busy": __props.loading
  }, [
    _createElementVNode$3("header", _hoisted_2$3, [
      _createElementVNode$3("div", _hoisted_3$3, [
        _createVNode$3(_component_VIcon, {
          icon: ({error:'mdi-alert-circle-outline',warning:'mdi-alert-circle-outline',info:'mdi-clock-outline',success:'mdi-check-circle-outline'})[__props.summary.health?.level] || 'mdi-clock-outline',
          color: _unref$3(healthTone)(__props.summary.health?.level),
          size: "25"
        }, null, 8, ["icon", "color"]),
        _createElementVNode$3("div", null, [
          _cache[5] || (_cache[5] = _createElementVNode$3("span", { class: "eyebrow" }, "当前结论", -1)),
          _createElementVNode$3("h2", null, _toDisplayString$3(__props.summary.health?.title || '正在读取任务'), 1),
          _createElementVNode$3("p", null, _toDisplayString$3(__props.summary.health?.message || '检查后展示实际表现和下一步。'), 1)
        ])
      ]),
      (__props.summary.recommended_actions?.length)
        ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_4$3, [
            (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(__props.summary.recommended_actions, (action) => {
              return (_openBlock$3(), _createBlock$3(_component_VBtn, {
                key: action.code,
                color: action.tone || 'primary',
                size: "small",
                variant: "tonal",
                disabled: action.enabled === false || __props.loading || __props.busy,
                onClick: $event => (_ctx.$emit('action',action))
              }, {
                default: _withCtx$3(() => [
                  _createTextVNode$3(_toDisplayString$3(action.label), 1)
                ]),
                _: 2
              }, 1032, ["color", "disabled", "onClick"]))
            }), 128))
          ]))
        : _createCommentVNode$3("", true)
    ]),
    _createElementVNode$3("section", _hoisted_5$3, [
      _cache[6] || (_cache[6] = _createElementVNode$3("div", { class: "section-heading" }, [
        _createElementVNode$3("h3", null, "上传与保种表现"),
        _createElementVNode$3("span", null, "真实增量 · 最近24小时")
      ], -1)),
      _createVNode$3(TaskPerformance, {
        performance: __props.summary.performance || {},
        loading: __props.loading,
        onInspect: _cache[0] || (_cache[0] = $event => (_ctx.$emit('inspect','income')))
      }, null, 8, ["performance", "loading"])
    ]),
    _createElementVNode$3("div", _hoisted_6$3, [
      _createElementVNode$3("section", _hoisted_7$3, [
        _createElementVNode$3("div", _hoisted_8$3, [
          _cache[7] || (_cache[7] = _createElementVNode$3("h3", null, "留种与淘汰", -1)),
          _createVNode$3(_component_VChip, {
            size: "x-small",
            variant: "tonal"
          }, {
            default: _withCtx$3(() => [
              _createTextVNode$3(_toDisplayString$3(decision.value.modeLabel), 1)
            ]),
            _: 1
          })
        ]),
        _createElementVNode$3("h4", null, _toDisplayString$3(decision.value.title), 1),
        _createElementVNode$3("p", null, _toDisplayString$3(__props.summary.deletion?.message || '获取实际上传和做种记录后判断，不会把未知数据当作零收益。'), 1),
        _createElementVNode$3("div", _hoisted_9$2, [
          _createElementVNode$3("button", {
            type: "button",
            disabled: __props.loading,
            onClick: _cache[1] || (_cache[1] = $event => (_ctx.$emit('inspect','deletion')))
          }, [
            _cache[9] || (_cache[9] = _createElementVNode$3("span", null, "待淘汰", -1)),
            _createElementVNode$3("strong", null, [
              _createTextVNode$3(_toDisplayString$3(decision.value.candidateLabel), 1),
              (!decision.value.pending)
                ? (_openBlock$3(), _createElementBlock$3("small", _hoisted_11$2, " 个"))
                : _createCommentVNode$3("", true)
            ]),
            (!decision.value.pending)
              ? (_openBlock$3(), _createElementBlock$3("small", _hoisted_12$1, "任务体积 " + _toDisplayString$3(_unref$3(formatBytes)(__props.summary.deletion?.candidate_bytes)), 1))
              : _createCommentVNode$3("", true),
            _createElementVNode$3("em", null, [
              _cache[8] || (_cache[8] = _createTextVNode$3("查看名单与原因 ", -1)),
              _createVNode$3(_component_VIcon, {
                icon: "mdi-chevron-right",
                size: "15"
              })
            ])
          ], 8, _hoisted_10$2),
          _createElementVNode$3("button", {
            type: "button",
            disabled: __props.loading,
            onClick: _cache[2] || (_cache[2] = $event => (_ctx.$emit('inspect','protection')))
          }, [
            _cache[11] || (_cache[11] = _createElementVNode$3("span", null, "继续保留 / 受保护", -1)),
            _createElementVNode$3("strong", null, [
              _createTextVNode$3(_toDisplayString$3(decision.value.protectedLabel), 1),
              (!decision.value.pending)
                ? (_openBlock$3(), _createElementBlock$3("small", _hoisted_14$1, " 个"))
                : _createCommentVNode$3("", true)
            ]),
            (!decision.value.pending)
              ? (_openBlock$3(), _createElementBlock$3("small", _hoisted_15$1, "任务体积 " + _toDisplayString$3(_unref$3(formatBytes)(__props.summary.deletion?.protected_bytes)), 1))
              : _createCommentVNode$3("", true),
            _createElementVNode$3("em", null, [
              _cache[10] || (_cache[10] = _createTextVNode$3("查看保护原因 ", -1)),
              _createVNode$3(_component_VIcon, {
                icon: "mdi-chevron-right",
                size: "15"
              })
            ])
          ], 8, _hoisted_13$1)
        ]),
        _createElementVNode$3("p", _hoisted_16$1, _toDisplayString$3(decision.value.rule) + "空间充足也会处理，不等待GB释放额度。", 1),
        (__props.strategy.deletion_blockers?.length)
          ? (_openBlock$3(), _createElementBlock$3("details", _hoisted_17$1, [
              _createElementVNode$3("summary", null, [
                _cache[12] || (_cache[12] = _createTextVNode$3("主要保留原因 ", -1)),
                _createElementVNode$3("span", null, _toDisplayString$3(__props.strategy.deletion_blockers.length) + " 类", 1)
              ]),
              _createElementVNode$3("ul", null, [
                (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(__props.strategy.deletion_blockers, (reason) => {
                  return (_openBlock$3(), _createElementBlock$3("li", {
                    key: reason.code
                  }, [
                    _createElementVNode$3("span", null, _toDisplayString$3(reason.label), 1),
                    _createElementVNode$3("strong", null, _toDisplayString$3(reason.count) + " 个", 1)
                  ]))
                }), 128))
              ]),
              _cache[13] || (_cache[13] = _createElementVNode$3("small", null, "同一种子可能命中多个原因，上方种子总数已去重。", -1))
            ]))
          : _createCommentVNode$3("", true),
        _createElementVNode$3("div", _hoisted_18$1, [
          _createVNode$3(_component_VIcon, {
            icon: "mdi-shield-check-outline",
            size: "18"
          }),
          _createElementVNode$3("span", null, _toDisplayString$3(decision.value.safety) + "排除标签同样有效。", 1)
        ])
      ]),
      _createElementVNode$3("aside", _hoisted_19$1, [
        _cache[21] || (_cache[21] = _createElementVNode$3("div", { class: "section-heading" }, [
          _createElementVNode$3("h3", null, "自动运行"),
          _createElementVNode$3("span", null, "点击查看详情")
        ], -1)),
        _createElementVNode$3("button", {
          type: "button",
          class: "activity-row",
          disabled: __props.loading,
          onClick: _cache[3] || (_cache[3] = $event => (_ctx.$emit('inspect','selection')))
        }, [
          _createVNode$3(_component_VIcon, {
            icon: "mdi-radar",
            size: "22",
            color: "primary"
          }),
          _createElementVNode$3("div", null, [
            _createElementVNode$3("strong", null, [
              _cache[14] || (_cache[14] = _createTextVNode$3("选种 ", -1)),
              _createElementVNode$3("span", null, "最近新增 " + _toDisplayString$3(__props.summary.selection?.added_count || 0) + " 个", 1)
            ]),
            _createElementVNode$3("p", null, _toDisplayString$3(__props.summary.selection?.source_checked ? '看到 ' + (__props.summary.selection.candidate_count || 0) + ' 个候选，过滤 ' + (__props.summary.selection.filtered_count || 0) + ' 个。' : '本轮尚未进入站点选种。'), 1),
            _createElementVNode$3("small", null, _toDisplayString$3(__props.summary.selection?.version_note || __props.summary.selection?.main_reason || '按需求、竞争和历史收益继续选种。'), 1)
          ]),
          _createVNode$3(_component_VIcon, {
            icon: "mdi-chevron-right",
            size: "18"
          })
        ], 8, _hoisted_20$1),
        _createElementVNode$3("button", {
          type: "button",
          class: "activity-row",
          disabled: __props.loading,
          onClick: _cache[4] || (_cache[4] = $event => (_ctx.$emit('inspect','download')))
        }, [
          _createVNode$3(_component_VIcon, {
            icon: "mdi-download-outline",
            size: "22",
            color: __props.summary.download?.issue_count ? 'warning' : 'success'
          }, null, 8, ["color"]),
          _createElementVNode$3("div", null, [
            _createElementVNode$3("strong", null, [
              _cache[15] || (_cache[15] = _createTextVNode$3("下载 ", -1)),
              _createElementVNode$3("span", null, _toDisplayString$3(__props.summary.download?.issue_count || 0) + " 个需关注", 1)
            ]),
            _createElementVNode$3("p", null, "超时 " + _toDisplayString$3(__props.summary.download?.overdue_count || 0) + " · 卡住 " + _toDisplayString$3(__props.summary.download?.stalled_count || 0) + " · 低速 " + _toDisplayString$3(__props.summary.download?.slow_count || 0), 1),
            _cache[16] || (_cache[16] = _createElementVNode$3("small", null, "未完成数据不会自动删除，异常可逐个处理。", -1))
          ]),
          _createVNode$3(_component_VIcon, {
            icon: "mdi-chevron-right",
            size: "18"
          })
        ], 8, _hoisted_21$1),
        _createElementVNode$3("div", _hoisted_22$1, [
          _createVNode$3(_component_VIcon, {
            icon: "mdi-harddisk",
            size: "22",
            color: "primary"
          }),
          _createElementVNode$3("div", null, [
            _createElementVNode$3("strong", null, [
              _cache[17] || (_cache[17] = _createTextVNode$3("任务空间 ", -1)),
              _createElementVNode$3("span", null, _toDisplayString$3(__props.summary.capacity?.percent === null || __props.summary.capacity?.percent === undefined ? '未设上限' : __props.summary.capacity.percent + '%'), 1)
            ]),
            _createElementVNode$3("p", null, _toDisplayString$3(_unref$3(formatBytes)(__props.summary.capacity?.current_bytes)) + " / " + _toDisplayString$3(__props.summary.capacity?.limit_bytes ? _unref$3(formatBytes)(__props.summary.capacity.limit_bytes) : '未设置'), 1),
            _createVNode$3(_component_VProgressLinear, {
              "model-value": Math.min(__props.summary.capacity?.percent || 0,100),
              color: (__props.summary.capacity?.percent || 0)>100 ? 'error' : 'primary',
              height: "4",
              rounded: ""
            }, null, 8, ["model-value", "color"]),
            _cache[18] || (_cache[18] = _createElementVNode$3("small", null, "只限制新增，不设清理停止线。", -1))
          ])
        ]),
        _createElementVNode$3("p", _hoisted_23$1, [
          _cache[19] || (_cache[19] = _createTextVNode$3("过去24h已释放 ", -1)),
          _createElementVNode$3("strong", null, _toDisplayString$3(_unref$3(formatBytes)(__props.strategy.actual_freed_bytes_24h)), 1),
          _cache[20] || (_cache[20] = _createElementVNode$3("small", null, "仅统计下载器已确认移除且删除数据的记录。", -1))
        ])
      ])
    ]),
    _createElementVNode$3("details", _hoisted_24$1, [
      _cache[22] || (_cache[22] = _createElementVNode$3("summary", null, [
        _createTextVNode$3("策略与学习详情 "),
        _createElementVNode$3("span", null, "专业数据，按需展开")
      ], -1)),
      _createElementVNode$3("div", _hoisted_25$1, [
        _createElementVNode$3("span", null, "引擎 " + _toDisplayString$3(__props.strategy.engine_version || '—'), 1),
        _createElementVNode$3("span", null, "样本 " + _toDisplayString$3(__props.strategy.learning_sample_count || 0), 1),
        _createElementVNode$3("span", null, "学习置信度 " + _toDisplayString$3(((__props.strategy.learning_confidence || 0)*100).toFixed(0)) + "%", 1),
        _createElementVNode$3("span", null, "误判率 " + _toDisplayString$3(((__props.strategy.false_positive_rate || 0)*100).toFixed(1)) + "%", 1)
      ]),
      _cache[23] || (_cache[23] = _createElementVNode$3("p", null, "近期单位容量上传收益决定保留价值；连续零上传仍需完整观测和连续确认。每个种子在真正删除前重新检查安全数据，先记录审计再执行。", -1)),
      _cache[24] || (_cache[24] = _createElementVNode$3("p", null, "每次检查逐个处理最多5个合格种子，剩余在后续检查继续；这是下载器请求批次，不是每日数量或GB释放限额。", -1))
    ])
  ], 8, _hoisted_1$3))
}
}

};
const TaskStatusView = /*#__PURE__*/_export_sfc(_sfc_main$3, [['__scopeId',"data-v-84cd70cd"]]);

const {createElementVNode:_createElementVNode$2,toDisplayString:_toDisplayString$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,createElementBlock:_createElementBlock$2,unref:_unref$2,normalizeClass:_normalizeClass$1} = await importShared('vue');


const _hoisted_1$2 = ["aria-busy"];
const _hoisted_2$2 = { class: "seed-filters" };
const _hoisted_3$2 = { class: "seed-desktop" };
const _hoisted_4$2 = ["title"];
const _hoisted_5$2 = {
  key: 0,
  class: "seed-retention"
};
const _hoisted_6$2 = { key: 0 };
const _hoisted_7$2 = { class: "seed-mobile" };
const _hoisted_8$2 = { class: "seed-mobile__metrics" };
const _hoisted_9$1 = { key: 0 };
const _hoisted_10$1 = {
  key: 0,
  class: "seed-retention"
};
const _hoisted_11$1 = {
  key: 1,
  class: "seed-empty"
};

const {useDisplay: useDisplay$2} = await importShared('vuetify');

const _sfc_main$2 = {
  __name: 'TaskTorrentTable',
  props: { torrents: { type: Object, default: () => ({items:[],total:0,page:1,page_size:50}) }, state: String, sort: String, filter: String, loading: Boolean },
  emits: ['state','sort','filter','page','inspect'],
  setup(__props) {



const display = useDisplay$2();
function seedTime(item) { return item.seeding_hours == null ? '未知' : item.seeding_hours + '小时' }
function upload(item) { return item.upload_coverage_hours_24h > 0 ? formatBytes(item.upload_delta_24h) : '待观测' }
function stateLabel(item) { return item.deleted ? '已移除' : item.download_overdue ? '下载超时' : item.download_health_label || (item.completed ? '已完成' : torrentProgress(item) + '%') }
function stateTone(item) { return item.download_overdue ? 'warning' : item.deleted ? 'secondary' : item.completed ? 'success' : 'default' }

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent$2("VBtn");
  const _component_VBtnToggle = _resolveComponent$2("VBtnToggle");
  const _component_VSelect = _resolveComponent$2("VSelect");
  const _component_VProgressLinear = _resolveComponent$2("VProgressLinear");
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VPagination = _resolveComponent$2("VPagination");

  return (_openBlock$2(), _createElementBlock$2("section", {
    class: "seed-panel",
    "aria-label": "托管种子表现",
    "aria-busy": __props.loading
  }, [
    _createElementVNode$2("header", null, [
      _createElementVNode$2("div", null, [
        _cache[5] || (_cache[5] = _createElementVNode$2("h3", null, "种子表现", -1)),
        _createElementVNode$2("p", null, "共 " + _toDisplayString$2(__props.torrents.total || 0) + " 个 · 保种按下载器实际时间计算", 1)
      ]),
      _createVNode$2(_component_VBtnToggle, {
        "model-value": __props.state,
        mandatory: "",
        density: "compact",
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (_ctx.$emit('state',$event)))
      }, {
        default: _withCtx$2(() => [
          _createVNode$2(_component_VBtn, { value: "active" }, {
            default: _withCtx$2(() => [...(_cache[6] || (_cache[6] = [
              _createTextVNode$2("当前", -1)
            ]))]),
            _: 1
          }),
          _createVNode$2(_component_VBtn, { value: "deleted" }, {
            default: _withCtx$2(() => [...(_cache[7] || (_cache[7] = [
              _createTextVNode$2("已移除", -1)
            ]))]),
            _: 1
          }),
          _createVNode$2(_component_VBtn, { value: "all" }, {
            default: _withCtx$2(() => [...(_cache[8] || (_cache[8] = [
              _createTextVNode$2("全部", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["model-value"])
    ]),
    _createElementVNode$2("div", _hoisted_2$2, [
      _createElementVNode$2("div", null, [
        _cache[9] || (_cache[9] = _createElementVNode$2("span", null, "筛选种子", -1)),
        _createVNode$2(_component_VSelect, {
          "model-value": __props.filter,
          "aria-label": "筛选种子",
          variant: "outlined",
          density: "compact",
          "hide-details": "",
          items: [{title:'全部种子',value:'all'},{title:'已达保种 · 24h零上传',value:'zero_upload'},{title:'已满足最低保种',value:'min_seed_met'},{title:'下载需要处理',value:'download_issues'},{title:'待淘汰种子',value:'candidates'},{title:'受保护 / 继续保留',value:'protected'}],
          "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => (_ctx.$emit('filter',$event)))
        }, null, 8, ["model-value"])
      ]),
      _createElementVNode$2("div", null, [
        _cache[10] || (_cache[10] = _createElementVNode$2("span", null, "显示顺序", -1)),
        _createVNode$2(_component_VSelect, {
          "model-value": __props.sort,
          "aria-label": "种子排序",
          variant: "outlined",
          density: "compact",
          "hide-details": "",
          items: [{title:'最近添加',value:'newest'},{title:'单位容量收益最低优先',value:'yield'},{title:'体积最大优先',value:'size'},{title:'保种时间最长优先',value:'seed_time'}],
          "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => (_ctx.$emit('sort',$event)))
        }, null, 8, ["model-value"])
      ]),
      (__props.filter === 'download_issues')
        ? (_openBlock$2(), _createBlock$2(_component_VBtn, {
            key: 0,
            variant: "tonal",
            color: "warning",
            disabled: __props.loading,
            onClick: _cache[3] || (_cache[3] = $event => (_ctx.$emit('inspect','download')))
          }, {
            default: _withCtx$2(() => [...(_cache[11] || (_cache[11] = [
              _createTextVNode$2("处理下载异常", -1)
            ]))]),
            _: 1
          }, 8, ["disabled"]))
        : _createCommentVNode$2("", true)
    ]),
    (__props.loading)
      ? (_openBlock$2(), _createBlock$2(_component_VProgressLinear, {
          key: 0,
          indeterminate: "",
          height: "2",
          color: "primary"
        }))
      : _createCommentVNode$2("", true),
    _createElementVNode$2("div", _hoisted_3$2, [
      _createElementVNode$2("table", null, [
        _cache[12] || (_cache[12] = _createElementVNode$2("thead", null, [
          _createElementVNode$2("tr", null, [
            _createElementVNode$2("th", null, "种子 / 加入时间"),
            _createElementVNode$2("th", null, "体积"),
            _createElementVNode$2("th", null, "实际保种"),
            _createElementVNode$2("th", null, "24h上传"),
            _createElementVNode$2("th", null, "累计上传"),
            _createElementVNode$2("th", null, "分享率"),
            _createElementVNode$2("th", null, "下载状态")
          ])
        ], -1)),
        _createElementVNode$2("tbody", null, [
          (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.torrents.items, (item) => {
            return (_openBlock$2(), _createElementBlock$2("tr", {
              key: item.hash
            }, [
              _createElementVNode$2("td", null, [
                _createElementVNode$2("strong", {
                  title: item.title
                }, _toDisplayString$2(item.title || item.hash), 9, _hoisted_4$2),
                _createElementVNode$2("small", null, "已加入 " + _toDisplayString$2(Number(item.age_hours || 0).toFixed(0)) + " 小时", 1),
                (item.retention_labels?.length)
                  ? (_openBlock$2(), _createElementBlock$2("small", _hoisted_5$2, _toDisplayString$2(item.retention_labels.join(' · ')), 1))
                  : _createCommentVNode$2("", true)
              ]),
              _createElementVNode$2("td", null, _toDisplayString$2(_unref$2(formatBytes)(item.size)), 1),
              _createElementVNode$2("td", null, [
                _createElementVNode$2("span", {
                  class: _normalizeClass$1({met:item.min_seed_met})
                }, _toDisplayString$2(seedTime(item)), 3),
                _createElementVNode$2("small", null, _toDisplayString$2(item.min_seed_met ? '已满足保种' : '最低 ' + (item.min_seed_hours || '未设置') + ' 小时'), 1)
              ]),
              _createElementVNode$2("td", null, [
                _createTextVNode$2(_toDisplayString$2(upload(item)), 1),
                (!item.upload_window_observed_24h)
                  ? (_openBlock$2(), _createElementBlock$2("small", _hoisted_6$2, "观测 " + _toDisplayString$2(Number(item.upload_coverage_hours_24h || 0).toFixed(1)) + "h", 1))
                  : _createCommentVNode$2("", true)
              ]),
              _createElementVNode$2("td", null, _toDisplayString$2(item.uploaded == null ? '未知' : _unref$2(formatBytes)(item.uploaded)), 1),
              _createElementVNode$2("td", null, _toDisplayString$2(item.ratio == null ? '—' : Number(item.ratio).toFixed(2)), 1),
              _createElementVNode$2("td", null, [
                _createVNode$2(_component_VChip, {
                  size: "x-small",
                  variant: "tonal",
                  color: stateTone(item)
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$2(stateLabel(item)), 1)
                  ]),
                  _: 2
                }, 1032, ["color"])
              ])
            ]))
          }), 128))
        ])
      ])
    ]),
    _createElementVNode$2("div", _hoisted_7$2, [
      (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.torrents.items, (item) => {
        return (_openBlock$2(), _createElementBlock$2("article", {
          key: item.hash
        }, [
          _createElementVNode$2("header", null, [
            _createElementVNode$2("strong", null, _toDisplayString$2(item.title || item.hash), 1),
            _createVNode$2(_component_VChip, {
              size: "x-small",
              variant: "tonal",
              color: stateTone(item)
            }, {
              default: _withCtx$2(() => [
                _createTextVNode$2(_toDisplayString$2(stateLabel(item)), 1)
              ]),
              _: 2
            }, 1032, ["color"])
          ]),
          _createElementVNode$2("dl", _hoisted_8$2, [
            _createElementVNode$2("div", null, [
              _cache[13] || (_cache[13] = _createElementVNode$2("dt", null, "实际保种", -1)),
              _createElementVNode$2("dd", {
                class: _normalizeClass$1({met:item.min_seed_met})
              }, [
                _createTextVNode$2(_toDisplayString$2(seedTime(item)), 1),
                _createElementVNode$2("small", null, _toDisplayString$2(item.min_seed_met ? '已满足保种' : '最低 ' + (item.min_seed_hours || '未设置') + ' 小时'), 1)
              ], 2)
            ]),
            _createElementVNode$2("div", null, [
              _cache[14] || (_cache[14] = _createElementVNode$2("dt", null, "24h上传", -1)),
              _createElementVNode$2("dd", null, [
                _createTextVNode$2(_toDisplayString$2(upload(item)), 1),
                (!item.upload_window_observed_24h)
                  ? (_openBlock$2(), _createElementBlock$2("small", _hoisted_9$1, "已观测 " + _toDisplayString$2(Number(item.upload_coverage_hours_24h || 0).toFixed(1)) + "h", 1))
                  : _createCommentVNode$2("", true)
              ])
            ]),
            _createElementVNode$2("div", null, [
              _cache[15] || (_cache[15] = _createElementVNode$2("dt", null, "体积", -1)),
              _createElementVNode$2("dd", null, _toDisplayString$2(_unref$2(formatBytes)(item.size)), 1)
            ]),
            _createElementVNode$2("div", null, [
              _cache[16] || (_cache[16] = _createElementVNode$2("dt", null, "分享率", -1)),
              _createElementVNode$2("dd", null, _toDisplayString$2(item.ratio == null ? '—' : Number(item.ratio).toFixed(2)), 1)
            ])
          ]),
          (item.retention_labels?.length)
            ? (_openBlock$2(), _createElementBlock$2("p", _hoisted_10$1, _toDisplayString$2(item.retention_labels.join(' · ')), 1))
            : _createCommentVNode$2("", true),
          _createElementVNode$2("details", null, [
            _cache[17] || (_cache[17] = _createElementVNode$2("summary", null, "更多数据与完整名称", -1)),
            _createElementVNode$2("p", null, _toDisplayString$2(item.title || item.hash), 1),
            _createElementVNode$2("small", null, "累计上传 " + _toDisplayString$2(item.uploaded == null ? '未知' : _unref$2(formatBytes)(item.uploaded)) + " · 已加入 " + _toDisplayString$2(Number(item.age_hours || 0).toFixed(0)) + " 小时", 1)
          ])
        ]))
      }), 128))
    ]),
    (!__props.torrents.items?.length)
      ? (_openBlock$2(), _createElementBlock$2("p", _hoisted_11$1, _toDisplayString$2(__props.loading ? '正在读取种子…' : '当前筛选下没有种子'), 1))
      : _createCommentVNode$2("", true),
    (__props.torrents.total > __props.torrents.page_size)
      ? (_openBlock$2(), _createBlock$2(_component_VPagination, {
          key: 2,
          "model-value": __props.torrents.page,
          length: Math.ceil(__props.torrents.total/__props.torrents.page_size),
          "total-visible": _unref$2(display).xs.value ? 3 : 5,
          "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => (_ctx.$emit('page',$event)))
        }, null, 8, ["model-value", "length", "total-visible"]))
      : _createCommentVNode$2("", true)
  ], 8, _hoisted_1$2))
}
}

};
const TaskTorrentTable = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-2b531113"]]);

const {createElementVNode:_createElementVNode$1,toDisplayString:_toDisplayString$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,resolveComponent:_resolveComponent$1,createBlock:_createBlock$1,renderList:_renderList$1,Fragment:_Fragment$1,createVNode:_createVNode$1,unref:_unref$1,createTextVNode:_createTextVNode$1,withCtx:_withCtx$1} = await importShared('vue');


const _hoisted_1$1 = ["aria-busy"];
const _hoisted_2$1 = { key: 0 };
const _hoisted_3$1 = { class: "run-history__body" };
const _hoisted_4$1 = { class: "run-history__title" };
const _hoisted_5$1 = { key: 0 };
const _hoisted_6$1 = { key: 0 };
const _hoisted_7$1 = {
  key: 0,
  class: "run-history__error"
};
const _hoisted_8$1 = {
  key: 1,
  class: "run-history__empty"
};

const {computed: computed$1} = await importShared('vue');

const {useDisplay: useDisplay$1} = await importShared('vuetify');

const _sfc_main$1 = {
  __name: 'TaskRunHistory',
  props: { events: {type:Object,default:()=>({items:[],total:0,page:1,page_size:20})}, loading:Boolean },
  emits: ['page'],
  setup(__props) {

const props = __props;

const display = useDisplay$1();
const rows = computed$1(() => (props.events.items || []).map(run => ({...run,view:runPresentation(run)})));

return (_ctx, _cache) => {
  const _component_VProgressLinear = _resolveComponent$1("VProgressLinear");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VPagination = _resolveComponent$1("VPagination");

  return (_openBlock$1(), _createElementBlock$1("section", {
    class: "run-history",
    "aria-label": "任务运行记录",
    "aria-busy": __props.loading
  }, [
    _createElementVNode$1("header", null, [
      _createElementVNode$1("div", null, [
        _cache[1] || (_cache[1] = _createElementVNode$1("h3", null, "运行记录", -1)),
        _createElementVNode$1("p", null, "共 " + _toDisplayString$1(__props.events.total || 0) + " 条 · 查看每次选种和检查的实际结果", 1)
      ]),
      (__props.events.total)
        ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_2$1, "第 " + _toDisplayString$1(__props.events.page || 1) + " 页", 1))
        : _createCommentVNode$1("", true)
    ]),
    (__props.loading)
      ? (_openBlock$1(), _createBlock$1(_component_VProgressLinear, {
          key: 0,
          indeterminate: "",
          height: "2",
          color: "primary"
        }))
      : _createCommentVNode$1("", true),
    _createElementVNode$1("ol", null, [
      (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(rows.value, (run, index) => {
        return (_openBlock$1(), _createElementBlock$1("li", {
          key: run.id || index
        }, [
          _createVNode$1(_component_VIcon, {
            icon: run.view.tone === 'error' ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline',
            color: run.view.tone,
            size: "20"
          }, null, 8, ["icon", "color"]),
          _createElementVNode$1("div", _hoisted_3$1, [
            _createElementVNode$1("div", _hoisted_4$1, [
              _createElementVNode$1("strong", null, _toDisplayString$1(run.view.title), 1),
              _createElementVNode$1("time", null, _toDisplayString$1(_unref$1(formatDateTime)(run.started_at)), 1),
              _createVNode$1(_component_VChip, {
                size: "x-small",
                color: run.view.tone,
                variant: "tonal"
              }, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$1(run.view.result), 1)
                ]),
                _: 2
              }, 1032, ["color"])
            ]),
            _createElementVNode$1("p", null, [
              _createTextVNode$1(_toDisplayString$1(run.view.metrics), 1),
              (run.freed_bytes)
                ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_5$1, " · 释放 " + _toDisplayString$1(_unref$1(formatBytes)(run.freed_bytes)), 1))
                : _createCommentVNode$1("", true)
            ]),
            (run.view.explanation || run.view.error)
              ? (_openBlock$1(), _createElementBlock$1("details", _hoisted_6$1, [
                  _cache[2] || (_cache[2] = _createElementVNode$1("summary", null, "查看本次说明", -1)),
                  _createElementVNode$1("p", null, _toDisplayString$1(run.view.explanation), 1),
                  (run.view.error)
                    ? (_openBlock$1(), _createElementBlock$1("p", _hoisted_7$1, _toDisplayString$1(run.view.error), 1))
                    : _createCommentVNode$1("", true)
                ]))
              : _createCommentVNode$1("", true)
          ])
        ]))
      }), 128))
    ]),
    (!rows.value.length)
      ? (_openBlock$1(), _createElementBlock$1("p", _hoisted_8$1, _toDisplayString$1(__props.loading ? '正在读取运行记录…' : '暂无运行记录，首次执行后会在这里显示。'), 1))
      : _createCommentVNode$1("", true),
    (__props.events.total > __props.events.page_size)
      ? (_openBlock$1(), _createBlock$1(_component_VPagination, {
          key: 2,
          "model-value": __props.events.page,
          length: Math.ceil(__props.events.total/__props.events.page_size),
          "total-visible": _unref$1(display).xs.value ? 3 : 5,
          "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => (_ctx.$emit('page',$event)))
        }, null, 8, ["model-value", "length", "total-visible"]))
      : _createCommentVNode$1("", true)
  ], 8, _hoisted_1$1))
}
}

};
const TaskRunHistory = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-b6719e3c"]]);

/** Only the newest request may update the selected task or its loading state. */
function createLatestRequest() {
  let sequence = 0;
  return {
    invalidate() { sequence += 1; },
    async run(request, { commit, error, settled } = {}) {
      const ticket = ++sequence;
      try {
        const result = await request();
        if (ticket !== sequence) return false
        commit?.(result);
        return true
      } catch (failure) {
        if (ticket === sequence) error?.(failure);
        return false
      } finally {
        if (ticket === sequence) settled?.();
      }
    },
  }
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createElementBlock:_createElementBlock,unref:_unref,normalizeClass:_normalizeClass,renderList:_renderList,Fragment:_Fragment} = await importShared('vue');


const _hoisted_1 = { class: "bf9" };
const _hoisted_2 = { class: "bf9__header" };
const _hoisted_3 = { class: "bf9__brand" };
const _hoisted_4 = { class: "bf9__header-actions" };
const _hoisted_5 = {
  key: 2,
  class: "bf9__empty"
};
const _hoisted_6 = {
  key: 3,
  class: "bf9__workspace",
  "aria-label": "任务工作区"
};
const _hoisted_7 = { class: "bf9__taskbar" };
const _hoisted_8 = { class: "bf9__task-identity" };
const _hoisted_9 = { class: "bf9__task-actions" };
const _hoisted_10 = { class: "bf9__primary-actions" };
const _hoisted_11 = { class: "bf9__secondary-actions" };
const _hoisted_12 = { class: "insight-intro" };
const _hoisted_13 = { class: "insight-list" };
const _hoisted_14 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_15 = { class: "insight-list" };
const _hoisted_16 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_17 = { class: "insight-intro" };
const _hoisted_18 = {
  key: 0,
  class: "insight-evaluated"
};
const _hoisted_19 = { class: "insight-list" };
const _hoisted_20 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_21 = { class: "insight-intro" };
const _hoisted_22 = { class: "insight-list" };
const _hoisted_23 = { class: "insight-metric" };
const _hoisted_24 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_25 = { class: "insight-list" };
const _hoisted_26 = { key: 0 };
const _hoisted_27 = { key: 0 };
const _hoisted_28 = { key: 1 };
const _hoisted_29 = { key: 1 };
const _hoisted_30 = { class: "insight-metric" };
const _hoisted_31 = { class: "download-issue-actions" };
const _hoisted_32 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_33 = { class: "settings-grid" };
const _hoisted_34 = { class: "settings-title" };
const _hoisted_35 = { class: "preview-metrics" };
const _hoisted_36 = {
  key: 1,
  class: "preview-list"
};
const _hoisted_37 = { class: "manual-delete-target" };

const {computed,inject,onMounted,onUnmounted,ref,watch} = await importShared('vue');

const {useDisplay} = await importShared('vuetify');


const _sfc_main = {
  __name: 'SmartBrushFlow',
  props: { api: { type: Object, default: () => ({}) }, pluginId: { type: String, default: 'SmartBrushFlow' }, showClose: Boolean },
  emits: ['close','action'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const toast = inject('moviepilot:toast', null);
const display = useDisplay();
const base = computed(() => `plugin/${props.pluginId}`);
const loading = ref(false), saving = ref(false), error = ref('');
const detailLoading = ref(false), detailRequests = createLatestRequest();
const status = ref({ enabled:false, summary:{}, tasks:[], options:{sites:[],downloaders:[]} });
const selectedId = ref(''), detail = ref(null), tab = ref('status'), torrentState = ref('active'), page = ref(1);
const runPage = ref(1);
const torrentSort = ref('newest'), torrentFilter = ref('all');
const wizard = ref(false), wizardTask = ref(newTaskV9());
const confirmOpen = ref(false), confirmAction = ref(null);
const deleteConfirmOpen = ref(false), deleteTarget = ref(null), deleteData = ref(false);
const cleanupPreviewOpen = ref(false), cleanupPreview = ref(null);
const settingsOpen = ref(false), settingsDraft = ref({});
const changeNotice = ref('');
const insightOpen = ref(false), insightKind = ref('selection');
let timer, cleanupTimer;
const tasks = computed(() => status.value.tasks || []);
const selected = computed(() => tasks.value.find(item => item.id === selectedId.value) || null);
const strategy = computed(() => detail.value?.strategy || selected.value?.strategy || {});
const summary = computed(() => strategy.value.ui_summary || {});
const task = computed(() => detail.value?.task?.id === selectedId.value ? detail.value.task : null);
const torrents = computed(() => detail.value?.torrents || {items:[],total:0,page:1,page_size:50});
const events = computed(() => detail.value?.events || {items:[],total:0,page:1,page_size:20});
const insightTitle = computed(() => ({selection:'选种详情',deletion:'待淘汰种子',protection:'受保护与继续保留的种子',download:'下载健康详情',income:'已达保种 · 24h零上传'}[insightKind.value]||'策略详情'));
const selectionDetails = computed(() => strategy.value.selection_explanations || []);
const deletionDetails = computed(() => strategy.value.pending_candidates || strategy.value.deletion_explanations || []);
const protectedDetails = computed(() => strategy.value.protected_items || []);
const downloadDetails = computed(() => summary.value.download?.issues || []);
const cleanupProgress = computed(() => detail.value?.summary?.cleanup_progress || selected.value?.cleanup_progress || null);
const cleanupActive = computed(() => ['queued','running'].includes(cleanupProgress.value?.state));

function notify(message, type='success'){ if(typeof toast?.[type]==='function') toast[type](message); else if(type==='error') error.value=message; }
async function loadDetail(){
  const id=selectedId.value, section=tab.value;
  if(!id)return
  detailLoading.value=true;
  await detailRequests.run(async()=>{
    const requests=[props.api.get(`${base.value}/tasks/${id}`)];
    if(section==='torrents')requests.push(props.api.get(`${base.value}/tasks/${id}/torrents?state=${torrentState.value}&page=${page.value}&page_size=50&sort=${torrentSort.value}&filter=${torrentFilter.value}`));
    if(section==='history')requests.push(props.api.get(`${base.value}/tasks/${id}/events?page=${runPage.value}&page_size=20`));
    const responses=await Promise.all(requests);
    const data=unwrapResponse(responses[0])||{};
    if(data.task?.id!==id)throw new Error('任务详情不匹配，请刷新后重试')
    if(section==='torrents')data.torrents=unwrapResponse(responses[1]);
    if(section==='history')data.events=unwrapResponse(responses[1])||{items:[],total:0,page:runPage.value,page_size:20};
    return data
  },{commit(data){if(id===selectedId.value)detail.value={...(detail.value||{}),...data};},error(err){error.value=err?.message||'加载任务失败';},settled(){detailLoading.value=false;}});
}
async function load(){ loading.value=true; try{ status.value=unwrapResponse(await props.api.get(`${base.value}/status`))||status.value; if(!tasks.value.some(item=>item.id===selectedId.value)) selectedId.value=tasks.value[0]?.id||''; await loadDetail(); scheduleCleanupDismiss(cleanupProgress.value); }catch(err){ error.value=err?.message||'加载刷流状态失败'; }finally{ loading.value=false; } }
function openSettings(){ const signin=status.value.signin||{}; settingsDraft.value={enabled:!!status.value.enabled,show_sidebar_nav:status.value.show_sidebar_nav!==false,global_disksize:status.value.global_disksize??null,global_maxdlcount:status.value.global_maxdlcount??null,global_maxupspeed:status.value.global_maxupspeed??null,global_maxdlspeed:status.value.global_maxdlspeed??null,signin_enabled:!!signin.enabled,signin_notify:signin.notify!==false,signin_cron:signin.cron||'17 7 * * *',signin_sites:[...(signin.site_ids||[])]}; settingsOpen.value=true; }
async function saveSettings(){ saving.value=true; try{ status.value=unwrapResponse(await props.api.post(`${base.value}/settings`,settingsDraft.value))||status.value; settingsOpen.value=false; await load(); notify('插件设置已保存'); }catch(err){ notify(err?.message||'保存设置失败','error'); }finally{ saving.value=false; } }
async function runSignin(){ saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/signin/run`,{})); await load(); notify('站点签到已执行'); }catch(err){ notify(err?.message||'签到失败','error'); }finally{ saving.value=false; } }
async function selectTask(id){ detailRequests.invalidate(); detail.value=null; selectedId.value=id; page.value=1; runPage.value=1; torrentState.value='active'; torrentFilter.value='all'; torrentSort.value='newest'; tab.value='status'; insightOpen.value=false; await loadDetail(); }
function createTask(){ wizardTask.value=newTaskV9(); wizard.value=true; }
function editTask(){ if(!task.value)return; wizardTask.value=cloneTaskV9(task.value); wizard.value=true; }
async function saveTask(payload){ saving.value=true; try{ const previous=task.value; const response=payload.id?await props.api.put(`${base.value}/tasks/${payload.id}`,payload):await props.api.post(`${base.value}/tasks`,payload); const data=unwrapResponse(response); selectedId.value=data?.task?.id||payload.id||selectedId.value; wizard.value=false; const effects=[]; if(!previous) effects.push('已建立新的选种与检查计划'); else { if(JSON.stringify(previous.capacity)!==JSON.stringify(payload.capacity)) effects.push('容量或速度限制已更新'); if(JSON.stringify(previous.selection)!==JSON.stringify(payload.selection)) effects.push('选种硬过滤与评分入口已更新'); if(JSON.stringify(previous.deletion)!==JSON.stringify(payload.deletion)||JSON.stringify(previous.strategy)!==JSON.stringify(payload.strategy)) effects.push('删种安全策略已更新，风险扩大时重新进入观察'); } changeNotice.value=effects.join('；')||'任务基础信息已更新'; await load(); notify(payload.id?'任务已更新':'任务已创建'); }catch(err){ notify(err?.message||'保存任务失败','error'); }finally{ saving.value=false; } }
function askAction(action){ confirmAction.value={...action,taskId:action.taskId||(action.code==='force_cleanup'?cleanupPreview.value?.task_id:selectedId.value)}; confirmOpen.value=true; }
async function executeAction(){ const action=confirmAction.value; if(!action)return; confirmOpen.value=false; if(action.code==='open_editor'){ confirmAction.value=null; editTask(); return } if(action.code==='preview_cleanup'){confirmAction.value=null;await askForceCleanup(action.taskId);return} saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/tasks/${action.taskId}/actions/${action.code}`,action.payload||{})); await load(); notify(action.success||'操作已提交'); if(action.code==='force_cleanup') startCleanupPolling(); }catch(err){ notify(err?.message||'操作失败','error'); }finally{ saving.value=false; confirmAction.value=null; } }
function topAction(code,label,confirm,success){ askAction({code,label,confirm,success,tone:'primary'}); }
function openInsight(kind){ insightKind.value=kind; insightOpen.value=true; }
function askDeleteUnhealthyDownload(item){ insightOpen.value=false; deleteTarget.value={...item,taskId:selectedId.value}; deleteData.value=false; deleteConfirmOpen.value=true; }
async function confirmDeleteUnhealthyDownload(){
  const item=deleteTarget.value;
  if(!item?.hash||!selectedId.value)return
  saving.value=true;
  try{
    const requestId=`manual-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
    const response=await props.api.post(`${base.value}/tasks/${item.taskId}/actions/delete_unhealthy_download`,{
      torrent_hash:item.hash, request_id:requestId, confirm:true, delete_data:deleteData.value,
    });
    unwrapResponse(response);
    deleteConfirmOpen.value=false;
    await load();
    notify(response?.message||'已提交单种移除请求');
  }catch(err){ deleteConfirmOpen.value=false; await load(); notify(err?.message||'移除下载失败','error'); }
  finally{ saving.value=false; deleteTarget.value=null; }
}
async function askForceCleanup(targetId=selectedId.value){
  if(!task.value||targetId!==selectedId.value)return
  const id=targetId, revision=task.value.revision;
  try{
    const preview=unwrapResponse(await props.api.post(`${base.value}/tasks/${id}/cleanup/preview`,{revision,relax_limits:true}));
    if(id!==selectedId.value)return
    cleanupPreview.value=preview;
    cleanupPreviewOpen.value=true;
  }catch(err){ notify(err?.message||'生成清理预览失败','error'); }
}
function confirmCleanupPreview(){
  const preview=cleanupPreview.value;
  if(!preview?.allowed)return
  cleanupPreviewOpen.value=false;
  const requestId=`cleanup-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
  askAction({code:'force_cleanup',label:'确认手动安全清理',tone:'error',success:'手动安全清理已提交',payload:{preview_id:preview.preview_id,revision:preview.revision,request_id:requestId,confirm:true,relax_limits:!!preview.relax_limits},confirm:`名单已冻结，有效期约5分钟；预计从下载器移除 ${preview.items?.length||0} 个任务，预计释放数据空间 ${formatBytes(preview.estimated_released_bytes||0)}。执行前仍会重新检查未完成、H&R、保种时间、上传、连接和需求保护。${preview.delete_data?'符合条件的任务及数据会被删除。':'只移除下载器任务，保留本地数据。'}确认继续吗？`});
}
function startCleanupPolling(){ window.clearTimeout(cleanupTimer); cleanupTimer=window.setTimeout(pollCleanup,700); }
function scheduleCleanupDismiss(progress){ if(!progress||!['completed','failed'].includes(progress.state))return; const delay=Math.max(Number(progress.display_until||0)*1000-Date.now(),0)+150; window.clearTimeout(cleanupTimer); cleanupTimer=window.setTimeout(()=>load(),delay); }
async function pollCleanup(){ const id=selectedId.value; if(!id)return; try{ const data=unwrapResponse(await props.api.get(`${base.value}/tasks/${id}`))||{}; if(id!==selectedId.value||data.task?.id!==id)return; detail.value={...(detail.value||{}),...data}; const progress=data.summary?.cleanup_progress; if(['queued','running'].includes(progress?.state)){ cleanupTimer=window.setTimeout(pollCleanup,900); return } await load(); scheduleCleanupDismiss(progress); if(progress?.state==='completed') notify(progress.message||'手动安全清理完成'); else if(progress?.state==='failed') notify(progress.error||'手动安全清理失败','error'); }catch(err){ cleanupTimer=window.setTimeout(pollCleanup,1600); } }
function reasonText(codes){ const labels={long_zero_upload:'连续长期零上传，满足保种后主动淘汰',insufficient_upload_history:'上传观测不足24小时',zero_upload_window_pending:'零上传时长尚未达到淘汰门槛',below_selection_threshold:'低于选种门槛',incomplete:'未完成下载',hit_and_run:'H&R保护',min_seed_time:'未达到最低保种时间',active_demand:'存在下载需求',trusted_active_demand:'Tracker需求仍在观察保护中',real_upload:'近期真实上传',active_connection:'存在活动连接',excluded_tag:'命中排除标签',low_value_unconfirmed:'低价值尚未连续确认',byte_cap:'容量额度已用尽',daily_count_cap:'每日数量额度已用尽',run_count_cap:'单轮数量额度已用尽',low_retention_value:'低收益，等待安全清理',smart_cold_cooldown:'仍在闲置保护时间内',valuable_seed:'仍有保留价值',safety_data_unknown:'下载器安全数据不完整',large_without_trusted_demand:'大种相对下载需求不足',oversized_for_task:'单种超过任务容量的25%',tracker_demand_unknown:'下载需求未知'}; return (codes||[]).map(code=>labels[code]||code).join(' · ')||'暂无补充原因' }
function downloadReason(item){ const labels={no_download_progress:'长时间没有下载进度',no_download_progress_with_connection:'有连接但长时间没有下载进度',low_effective_download_speed:'持续下载速度低于策略阈值',downloader_paused:'下载任务已暂停',downloader_queue:'下载器正在排队',downloader_checking:'下载器正在校验文件',downloader_error:'下载器报告任务错误',missing_download_measurement:'下载器未提供有效进度数据',insufficient_history:'观测记录不足，暂不能判断',confirming_no_progress:'正在确认是否停止下载',progressing:'下载仍有进度'}; return labels[item.reason]||item.reason||item.label||'需要检查下载状态' }
async function changeTorrentState(value){ torrentState.value=value; page.value=1; await loadDetail(); }
async function changePage(value){ page.value=value; await loadDetail(); }
async function changeRunPage(value){ runPage.value=value; await loadDetail(); }
async function changeTorrentSort(value){torrentSort.value=value;page.value=1;await loadDetail();}
async function changeTorrentFilter(value){torrentFilter.value=value;page.value=1;await loadDetail();}
async function openRetentionList(filter){insightOpen.value=false;torrentState.value='active';torrentFilter.value=filter;torrentSort.value='size';page.value=1;if(tab.value==='torrents')await loadDetail();else tab.value='torrents';}
function openZeroUploadList(){return openRetentionList('zero_upload')}
watch(tab,()=>loadDetail());
onMounted(()=>{ load(); timer=window.setInterval(load,30000); }); onUnmounted(()=>{ detailRequests.invalidate(); window.clearInterval(timer); window.clearTimeout(cleanupTimer); });

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCheckbox = _resolveComponent("VCheckbox");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("header", _hoisted_2, [
      _createElementVNode("div", null, [
        _createElementVNode("div", _hoisted_3, [
          _createVNode(_component_VIcon, {
            icon: "mdi-sync-circle",
            color: "primary",
            size: "34"
          }),
          _cache[34] || (_cache[34] = _createElementVNode("div", null, [
            _createElementVNode("h1", null, "智能刷流"),
            _createElementVNode("p", null, "看结论、处理异常，其余交给统一策略")
          ], -1))
        ])
      ]),
      _createElementVNode("div", _hoisted_4, [
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-refresh",
          loading: loading.value,
          onClick: load
        }, {
          default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-tune",
          onClick: openSettings
        }, {
          default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
            _createTextVNode("工具与设置", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VBtn, {
          color: "primary",
          variant: "tonal",
          "prepend-icon": "mdi-plus",
          onClick: createTask
        }, {
          default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
            _createTextVNode("新建任务", -1)
          ]))]),
          _: 1
        }),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 0,
              icon: "mdi-close",
              variant: "text",
              onClick: _cache[0] || (_cache[0] = $event => (emit('close')))
            }))
          : _createCommentVNode("", true)
      ])
    ]),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "error",
          variant: "tonal",
          closable: "",
          "onClick:close": _cache[1] || (_cache[1] = $event => (error.value=''))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (!status.value.enabled)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "warning",
          variant: "tonal"
        }, {
          default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
            _createTextVNode("插件当前未启用；任务和历史可以查看，但不会自动运行。", -1)
          ]))]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(TaskNavigator, {
      tasks: tasks.value,
      "selected-id": selectedId.value,
      onSelect: selectTask
    }, null, 8, ["tasks", "selected-id"]),
    (!tasks.value.length&&!loading.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
          _createVNode(_component_VIcon, {
            icon: "mdi-radar",
            size: "52"
          }),
          _cache[40] || (_cache[40] = _createElementVNode("h2", null, "还没有刷流任务", -1)),
          _cache[41] || (_cache[41] = _createElementVNode("p", null, "四步完成站点、容量、选种和安全规则。", -1)),
          _createVNode(_component_VBtn, {
            color: "primary",
            onClick: createTask
          }, {
            default: _withCtx(() => [...(_cache[39] || (_cache[39] = [
              _createTextVNode("创建第一个任务", -1)
            ]))]),
            _: 1
          })
        ]))
      : _createCommentVNode("", true),
    (selected.value)
      ? (_openBlock(), _createElementBlock("section", _hoisted_6, [
          _createElementVNode("header", _hoisted_7, [
            _createElementVNode("div", _hoisted_8, [
              _cache[42] || (_cache[42] = _createElementVNode("span", null, "当前任务", -1)),
              _createElementVNode("h2", null, _toDisplayString(selected.value.name), 1),
              _createElementVNode("p", null, _toDisplayString(selected.value.site_name) + " · 最近 " + _toDisplayString(selected.value.last_run?_unref(formatDateTime)(selected.value.last_run.started_at):'尚未运行') + " · 下次 " + _toDisplayString(selected.value.next_run_at?_unref(formatDateTime)(selected.value.next_run_at):'暂无计划'), 1)
            ]),
            _createElementVNode("div", _hoisted_9, [
              _createElementVNode("div", _hoisted_10, [
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  "prepend-icon": "mdi-radar",
                  disabled: !task.value||detailLoading.value||saving.value,
                  onClick: _cache[2] || (_cache[2] = $event => (topAction('run_selection','立即选种','将立即访问站点并可能添加符合条件的下载，确认继续吗？','选种任务已提交')))
                }, {
                  default: _withCtx(() => [...(_cache[43] || (_cache[43] = [
                    _createTextVNode("立即选种", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  variant: "tonal",
                  "prepend-icon": "mdi-progress-check",
                  disabled: !task.value||detailLoading.value||saving.value,
                  onClick: _cache[3] || (_cache[3] = $event => (topAction('run_check','检查种子','将立即检查下载、上传和删种候选，确认继续吗？','种子检查已提交')))
                }, {
                  default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
                    _createTextVNode("检查种子", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]),
              _createElementVNode("div", _hoisted_11, [
                _createVNode(_component_VBtn, {
                  variant: "text",
                  "prepend-icon": "mdi-pencil",
                  disabled: !task.value||detailLoading.value||saving.value,
                  onClick: editTask
                }, {
                  default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                    _createTextVNode("编辑任务", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  "prepend-icon": selected.value.enabled?'mdi-pause':'mdi-play',
                  disabled: !task.value||detailLoading.value||saving.value,
                  onClick: _cache[4] || (_cache[4] = $event => (topAction(selected.value.enabled?'pause_task':'resume_task',selected.value.enabled?'暂停任务':'恢复任务',selected.value.enabled?'暂停后将停止自动选种和检查，确认吗？':'恢复后将重新注册自动调度，确认吗？',selected.value.enabled?'任务已暂停':'任务已恢复')))
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(selected.value.enabled?'暂停任务':'恢复任务'), 1)
                  ]),
                  _: 1
                }, 8, ["prepend-icon", "disabled"])
              ])
            ])
          ]),
          (changeNotice.value)
            ? (_openBlock(), _createBlock(_component_VAlert, {
                key: 0,
                type: "info",
                variant: "tonal",
                closable: "",
                "onClick:close": _cache[5] || (_cache[5] = $event => (changeNotice.value=''))
              }, {
                default: _withCtx(() => [
                  _createTextVNode("本次修改影响：" + _toDisplayString(changeNotice.value), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (cleanupProgress.value)
            ? (_openBlock(), _createElementBlock("section", {
                key: 1,
                class: _normalizeClass(["bf9__cleanup-progress panel", `state-${cleanupProgress.value.state}`])
              }, [
                _createElementVNode("div", null, [
                  _createVNode(_component_VIcon, {
                    icon: cleanupActive.value?'mdi-delete-clock':cleanupProgress.value.state==='completed'?'mdi-check-circle':'mdi-alert-circle',
                    color: cleanupActive.value?'warning':cleanupProgress.value.state==='completed'?'success':'error'
                  }, null, 8, ["icon", "color"]),
                  _createElementVNode("div", null, [
                    _createElementVNode("strong", null, _toDisplayString(cleanupProgress.value.phase), 1),
                    _createElementVNode("p", null, _toDisplayString(cleanupProgress.value.state==='completed'?(cleanupProgress.value.message||`已删除 ${cleanupProgress.value.deleted_count||0} 个，释放 ${_unref(formatBytes)(cleanupProgress.value.freed_bytes||0)}`):`候选 ${cleanupProgress.value.candidate_count||0} · 已选 ${cleanupProgress.value.selected_count||0} · 已删 ${cleanupProgress.value.deleted_count||0}`), 1)
                  ])
                ]),
                _createElementVNode("strong", null, _toDisplayString(cleanupProgress.value.percent||0) + "%", 1),
                _createVNode(_component_VProgressLinear, {
                  "model-value": cleanupProgress.value.percent||0,
                  indeterminate: cleanupProgress.value.state==='queued',
                  color: cleanupProgress.value.state==='failed'?'error':cleanupProgress.value.state==='completed'?'success':'warning',
                  height: "7",
                  rounded: ""
                }, null, 8, ["model-value", "indeterminate", "color"])
              ], 2))
            : _createCommentVNode("", true),
          _createVNode(_component_VTabs, {
            modelValue: tab.value,
            "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((tab).value = $event)),
            color: "primary",
            class: "bf9__tabs"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VTab, { value: "status" }, {
                default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
                  _createTextVNode("概览", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VTab, { value: "torrents" }, {
                default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                  _createTextVNode("种子表现", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VTab, { value: "history" }, {
                default: _withCtx(() => [...(_cache[48] || (_cache[48] = [
                  _createTextVNode("运行记录", -1)
                ]))]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"]),
          _createVNode(_component_VDivider),
          _createVNode(_component_VWindow, {
            modelValue: tab.value,
            "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((tab).value = $event)),
            touch: false,
            class: "bf9__pages"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VWindowItem, { value: "status" }, {
                default: _withCtx(() => [
                  _createVNode(TaskStatusView, {
                    summary: summary.value,
                    strategy: strategy.value,
                    loading: detailLoading.value&&!task.value,
                    busy: saving.value,
                    onInspect: openInsight,
                    onAction: askAction
                  }, null, 8, ["summary", "strategy", "loading", "busy"])
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "torrents" }, {
                default: _withCtx(() => [
                  _createVNode(TaskTorrentTable, {
                    torrents: torrents.value,
                    state: torrentState.value,
                    sort: torrentSort.value,
                    filter: torrentFilter.value,
                    loading: detailLoading.value,
                    onState: changeTorrentState,
                    onSort: changeTorrentSort,
                    onFilter: changeTorrentFilter,
                    onPage: changePage,
                    onInspect: openInsight
                  }, null, 8, ["torrents", "state", "sort", "filter", "loading"])
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "history" }, {
                default: _withCtx(() => [
                  _createVNode(TaskRunHistory, {
                    events: events.value,
                    loading: detailLoading.value,
                    onPage: changeRunPage
                  }, null, 8, ["events", "loading"])
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]))
      : _createCommentVNode("", true),
    _createVNode(TaskWizardV9, {
      modelValue: wizard.value,
      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((wizard).value = $event)),
      task: wizardTask.value,
      sites: status.value.options.sites,
      downloaders: status.value.options.downloaders,
      api: __props.api,
      "plugin-base": base.value,
      saving: saving.value,
      onSave: saveTask
    }, null, 8, ["modelValue", "task", "sites", "downloaders", "api", "plugin-base", "saving"]),
    _createVNode(_component_VDialog, {
      modelValue: insightOpen.value,
      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((insightOpen).value = $event)),
      fullscreen: _unref(display).xs.value,
      "max-width": "58rem",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, { class: "bf9__insight" }, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "bf9__insight-heading" }, {
              default: _withCtx(() => [
                _createElementVNode("h2", null, _toDisplayString(insightTitle.value), 1),
                _createVNode(_component_VBtn, {
                  icon: "mdi-close",
                  "aria-label": "关闭详情",
                  variant: "text",
                  onClick: _cache[9] || (_cache[9] = $event => (insightOpen.value=false))
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (insightKind.value==='income')
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _createElementVNode("div", _hoisted_12, [
                        _cache[50] || (_cache[50] = _createElementVNode("p", null, "这些种子已达到最低保种时长，完整 24 小时没有上传。清理仍会复核 H&R、连接和连续确认。", -1)),
                        _createVNode(_component_VBtn, {
                          variant: "tonal",
                          onClick: openZeroUploadList
                        }, {
                          default: _withCtx(() => [...(_cache[49] || (_cache[49] = [
                            _createTextVNode("查看全部零上传种子", -1)
                          ]))]),
                          _: 1
                        })
                      ]),
                      _createElementVNode("div", _hoisted_13, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(summary.value.performance?.low_yield_items||[], (item) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: item.hash
                          }, [
                            _createElementVNode("div", null, [
                              _createElementVNode("strong", null, _toDisplayString(item.title||item.hash), 1),
                              _createElementVNode("small", null, "已保种 " + _toDisplayString(item.seeding_hours) + " 小时 · " + _toDisplayString(reasonText(item.reasons)), 1)
                            ]),
                            _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(item.size)), 1)
                          ]))
                        }), 128)),
                        (!summary.value.performance?.low_yield_items?.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_14, "暂无符合完整观测条件的零上传种子。"))
                          : _createCommentVNode("", true)
                      ])
                    ], 64))
                  : (insightKind.value==='selection')
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                        _cache[51] || (_cache[51] = _createElementVNode("p", { class: "mb-3" }, "最近一次选种评分及结果，分数越高越优先。", -1)),
                        _createElementVNode("div", _hoisted_15, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(selectionDetails.value, (item) => {
                            return (_openBlock(), _createElementBlock("article", {
                              key: item.title
                            }, [
                              _createElementVNode("div", null, [
                                _createElementVNode("strong", null, _toDisplayString(item.title||'未知候选'), 1),
                                _createElementVNode("small", null, _toDisplayString(reasonText(item.reasons)), 1)
                              ]),
                              _createVNode(_component_VChip, {
                                color: item.selected?'success':'default',
                                size: "small",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(Number(item.score||0).toFixed(1)) + " 分 · " + _toDisplayString(item.selected?'已选':'未选'), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]))
                          }), 128)),
                          (!selectionDetails.value.length)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_16, "最近没有可展示的站点候选，下一次看到候选后会记录评分。"))
                            : _createCommentVNode("", true)
                        ])
                      ], 64))
                    : (insightKind.value==='protection')
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                          _createElementVNode("div", _hoisted_17, [
                            _cache[53] || (_cache[53] = _createElementVNode("p", null, "以下种子来自最近一次检查，因安全保护或仍需观察而继续保留。原因可重叠，种子数量已去重。", -1)),
                            _createVNode(_component_VBtn, {
                              variant: "tonal",
                              onClick: _cache[10] || (_cache[10] = $event => (openRetentionList('protected')))
                            }, {
                              default: _withCtx(() => [...(_cache[52] || (_cache[52] = [
                                _createTextVNode("查看全部保留种子", -1)
                              ]))]),
                              _: 1
                            })
                          ]),
                          (strategy.value.evaluation_at)
                            ? (_openBlock(), _createElementBlock("p", _hoisted_18, "最近评估 " + _toDisplayString(_unref(formatDateTime)(strategy.value.evaluation_at*1000)) + " · 展示 " + _toDisplayString(protectedDetails.value.length) + " / " + _toDisplayString(summary.value.deletion?.protected_count||0) + " 个", 1))
                            : _createCommentVNode("", true),
                          _createElementVNode("div", _hoisted_19, [
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(protectedDetails.value, (item) => {
                              return (_openBlock(), _createElementBlock("article", {
                                key: item.hash
                              }, [
                                _createElementVNode("div", null, [
                                  _createElementVNode("strong", null, _toDisplayString(item.title||item.hash), 1),
                                  _createElementVNode("small", null, _toDisplayString(reasonText(item.reasons)), 1)
                                ]),
                                _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(item.size)), 1)
                              ]))
                            }), 128)),
                            (!protectedDetails.value.length)
                              ? (_openBlock(), _createElementBlock("div", _hoisted_20, _toDisplayString(summary.value.deletion?.state==='pending_evaluation'?'等待首次检查后显示保护名单。':'当前没有额外保护的种子。'), 1))
                              : _createCommentVNode("", true)
                          ])
                        ], 64))
                      : (insightKind.value==='deletion')
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                            _createElementVNode("div", _hoisted_21, [
                              _cache[55] || (_cache[55] = _createElementVNode("p", null, "这些是当前仍在下载器中的候选，真正删除前会再次复核全部硬安全线。", -1)),
                              _createVNode(_component_VBtn, {
                                variant: "tonal",
                                onClick: _cache[11] || (_cache[11] = $event => (openRetentionList('candidates')))
                              }, {
                                default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                                  _createTextVNode("查看全部候选", -1)
                                ]))]),
                                _: 1
                              }),
                              (deletionDetails.value.length)
                                ? (_openBlock(), _createBlock(_component_VBtn, {
                                    key: 0,
                                    color: "error",
                                    variant: "tonal",
                                    "prepend-icon": "mdi-delete-sweep",
                                    loading: cleanupActive.value,
                                    disabled: cleanupActive.value,
                                    onClick: _cache[12] || (_cache[12] = $event => {insightOpen.value=false;askForceCleanup();})
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(cleanupActive.value?'正在安全清理':'手动安全清理'), 1)
                                    ]),
                                    _: 1
                                  }, 8, ["loading", "disabled"]))
                                : _createCommentVNode("", true)
                            ]),
                            (cleanupProgress.value)
                              ? (_openBlock(), _createBlock(_component_VAlert, {
                                  key: 0,
                                  type: cleanupProgress.value.state==='failed'?'error':cleanupProgress.value.state==='completed'?'success':'warning',
                                  variant: "tonal",
                                  density: "compact",
                                  class: "mt-4"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(cleanupProgress.value.phase) + " · 已删 " + _toDisplayString(cleanupProgress.value.deleted_count||0) + " 个 · 释放 " + _toDisplayString(_unref(formatBytes)(cleanupProgress.value.freed_bytes||0)), 1)
                                  ]),
                                  _: 1
                                }, 8, ["type"]))
                              : _createCommentVNode("", true),
                            _createElementVNode("div", _hoisted_22, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(deletionDetails.value, (item) => {
                                return (_openBlock(), _createElementBlock("article", {
                                  key: item.hash
                                }, [
                                  _createElementVNode("div", null, [
                                    _createElementVNode("strong", null, _toDisplayString(item.title||item.hash), 1),
                                    _createElementVNode("small", null, _toDisplayString(item.recovered?'候选恢复上传或需求，已判为误判并保护':(item.selected?'本批待最终安全复核':reasonText(item.reasons))), 1)
                                  ]),
                                  _createElementVNode("div", _hoisted_23, [
                                    _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(item.size||0)), 1),
                                    _createVNode(_component_VChip, {
                                      size: "small",
                                      color: item.recovered?'success':'warning',
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(Number(item.score||0).toFixed(1)) + " 分", 1)
                                      ]),
                                      _: 2
                                    }, 1032, ["color"])
                                  ])
                                ]))
                              }), 128)),
                              (!deletionDetails.value.length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_24, "当前没有进入观察记录的删种候选。"))
                                : _createCommentVNode("", true)
                            ])
                          ], 64))
                        : (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                            _cache[58] || (_cache[58] = _createElementVNode("p", { class: "mb-3" }, "仅列出需要关注的下载；未完成数据不会自动删除。卡住或低速的种子可单独手动移除。", -1)),
                            _createElementVNode("div", _hoisted_25, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(downloadDetails.value, (item) => {
                                return (_openBlock(), _createElementBlock("article", {
                                  key: item.hash
                                }, [
                                  _createElementVNode("div", null, [
                                    _createElementVNode("strong", null, _toDisplayString(item.title), 1),
                                    _createElementVNode("small", null, _toDisplayString(downloadReason(item)), 1),
                                    (item.age_hours!==null&&item.age_hours!==undefined)
                                      ? (_openBlock(), _createElementBlock("small", _hoisted_26, [
                                          _createTextVNode("已下载 " + _toDisplayString(Number(item.age_hours||0).toFixed(1)) + " 小时", 1),
                                          (item.overdue)
                                            ? (_openBlock(), _createElementBlock("span", _hoisted_27, " · 超过设定时限"))
                                            : _createCommentVNode("", true),
                                          (item.eta_hours)
                                            ? (_openBlock(), _createElementBlock("span", _hoisted_28, " · 预计还需 " + _toDisplayString(Number(item.eta_hours).toFixed(1)) + " 小时", 1))
                                            : _createCommentVNode("", true)
                                        ]))
                                      : _createCommentVNode("", true),
                                    (item.action_error)
                                      ? (_openBlock(), _createElementBlock("small", _hoisted_29, "处理提示：" + _toDisplayString(item.action_error), 1))
                                      : _createCommentVNode("", true)
                                  ]),
                                  _createElementVNode("div", _hoisted_30, [
                                    _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(item.size||0)), 1),
                                    _createVNode(_component_VChip, {
                                      size: "small",
                                      color: "warning",
                                      variant: "tonal"
                                    }, {
                                      default: _withCtx(() => [
                                        _createTextVNode(_toDisplayString(item.overdue?'下载超时':item.label), 1)
                                      ]),
                                      _: 2
                                    }, 1024)
                                  ]),
                                  _createElementVNode("div", _hoisted_31, [
                                    (item.delete_pending)
                                      ? (_openBlock(), _createBlock(_component_VChip, {
                                          key: 0,
                                          size: "small",
                                          color: "info",
                                          variant: "tonal"
                                        }, {
                                          default: _withCtx(() => [...(_cache[56] || (_cache[56] = [
                                            _createTextVNode("移除结果核对中", -1)
                                          ]))]),
                                          _: 1
                                        }))
                                      : (['stalled','slow'].includes(item.state)||(item.state==='paused'&&item.auto_paused))
                                        ? (_openBlock(), _createBlock(_component_VBtn, {
                                            key: 1,
                                            size: "small",
                                            color: "error",
                                            variant: "tonal",
                                            "prepend-icon": "mdi-delete-outline",
                                            disabled: saving.value,
                                            onClick: $event => (askDeleteUnhealthyDownload(item))
                                          }, {
                                            default: _withCtx(() => [...(_cache[57] || (_cache[57] = [
                                              _createTextVNode("删除", -1)
                                            ]))]),
                                            _: 1
                                          }, 8, ["disabled", "onClick"]))
                                        : _createCommentVNode("", true)
                                  ])
                                ]))
                              }), 128)),
                              (!downloadDetails.value.length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_32, "当前没有卡住、低速、排队或报错的下载。"))
                                : _createCommentVNode("", true)
                            ])
                          ], 64))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[13] || (_cache[13] = $event => (insightOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[59] || (_cache[59] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue", "fullscreen"]),
    _createVNode(_component_VDialog, {
      modelValue: settingsOpen.value,
      "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((settingsOpen).value = $event)),
      fullscreen: _unref(display).xs.value,
      "max-width": "46rem",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [
                _createVNode(_component_VIcon, {
                  icon: "mdi-tune",
                  class: "mr-2"
                }),
                _cache[60] || (_cache[60] = _createTextVNode("工具与设置", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "bf9__settings" }, {
              default: _withCtx(() => [
                _createElementVNode("section", null, [
                  _cache[61] || (_cache[61] = _createElementVNode("h3", null, "插件运行", -1)),
                  _cache[62] || (_cache[62] = _createElementVNode("p", null, "这里只管理插件总开关和全局硬上限；每个任务仍独立管理自己的容量。", -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.enabled,
                    "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((settingsDraft.value.enabled) = $event)),
                    label: "启用智能刷流",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.show_sidebar_nav,
                    "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((settingsDraft.value.show_sidebar_nav) = $event)),
                    label: "显示侧边栏入口",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createElementVNode("div", _hoisted_33, [
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_disksize,
                      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((settingsDraft.value.global_disksize) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "全局做种硬上限（GB）",
                      hint: "达到后只阻止新增，不跨任务删种",
                      "persistent-hint": "",
                      clearable: ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_maxdlcount,
                      "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((settingsDraft.value.global_maxdlcount) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "全局下载并发硬上限",
                      clearable: ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_maxupspeed,
                      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((settingsDraft.value.global_maxupspeed) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "全局上传限速（KB/s）",
                      clearable: ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_maxdlspeed,
                      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((settingsDraft.value.global_maxdlspeed) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "全局下载限速（KB/s）",
                      clearable: ""
                    }, null, 8, ["modelValue"])
                  ])
                ]),
                _createVNode(_component_VDivider),
                _createElementVNode("section", null, [
                  _createElementVNode("div", _hoisted_34, [
                    _cache[64] || (_cache[64] = _createElementVNode("div", null, [
                      _createElementVNode("h3", null, "站点签到"),
                      _createElementVNode("p", null, "签到是独立工具，不参与选种、下载健康或删种决策。")
                    ], -1)),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      "prepend-icon": "mdi-login",
                      loading: saving.value,
                      onClick: runSignin
                    }, {
                      default: _withCtx(() => [...(_cache[63] || (_cache[63] = [
                        _createTextVNode("立即签到", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.signin_enabled,
                    "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((settingsDraft.value.signin_enabled) = $event)),
                    label: "启用自动签到",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.signin_notify,
                    "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((settingsDraft.value.signin_notify) = $event)),
                    label: "发送签到结果通知",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VTextField, {
                    modelValue: settingsDraft.value.signin_cron,
                    "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((settingsDraft.value.signin_cron) = $event)),
                    label: "签到 CRON",
                    hint: "默认每天 07:17：17 7 * * *",
                    "persistent-hint": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSelect, {
                    modelValue: settingsDraft.value.signin_sites,
                    "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((settingsDraft.value.signin_sites) = $event)),
                    items: status.value.options.sites,
                    multiple: "",
                    chips: "",
                    "closable-chips": "",
                    label: "签到站点",
                    hint: "留空时使用已启用刷流任务的站点",
                    "persistent-hint": ""
                  }, null, 8, ["modelValue", "items"]),
                  (status.value.signin?.last_run_at)
                    ? (_openBlock(), _createBlock(_component_VAlert, {
                        key: 0,
                        type: "info",
                        variant: "tonal",
                        density: "compact"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("最近签到：" + _toDisplayString(_unref(formatDateTime)(status.value.signin.last_run_at)) + "，成功 " + _toDisplayString((status.value.signin.last_results||[]).filter(item=>item.success).length) + "/" + _toDisplayString((status.value.signin.last_results||[]).length), 1)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode("", true)
                ])
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[25] || (_cache[25] = $event => (settingsOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[65] || (_cache[65] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  loading: saving.value,
                  onClick: saveSettings
                }, {
                  default: _withCtx(() => [...(_cache[66] || (_cache[66] = [
                    _createTextVNode("保存设置", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue", "fullscreen"]),
    _createVNode(_component_VDialog, {
      modelValue: cleanupPreviewOpen.value,
      "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((cleanupPreviewOpen).value = $event)),
      fullscreen: _unref(display).xs.value,
      "max-width": "48rem",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[67] || (_cache[67] = [
                _createTextVNode("清理预览（不会立即删除）", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _cache[71] || (_cache[71] = _createElementVNode("p", null, "以下名单来自本次只读评估，确认后还会再次执行全部硬安全线。", -1)),
                _createElementVNode("div", _hoisted_35, [
                  _createElementVNode("div", null, [
                    _cache[68] || (_cache[68] = _createElementVNode("span", null, "候选", -1)),
                    _createElementVNode("strong", null, _toDisplayString(cleanupPreview.value?.items?.length||0) + " 个", 1)
                  ]),
                  _createElementVNode("div", null, [
                    _cache[69] || (_cache[69] = _createElementVNode("span", null, "预计移除任务体积", -1)),
                    _createElementVNode("strong", null, _toDisplayString(_unref(formatBytes)(cleanupPreview.value?.expected_task_bytes_removed||0)), 1)
                  ]),
                  _createElementVNode("div", null, [
                    _cache[70] || (_cache[70] = _createElementVNode("span", null, "预计释放数据", -1)),
                    _createElementVNode("strong", null, _toDisplayString(_unref(formatBytes)(cleanupPreview.value?.estimated_released_bytes||0)), 1)
                  ])
                ]),
                (!cleanupPreview.value?.allowed)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "warning",
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode("当前没有可执行的名单：" + _toDisplayString(cleanupPreview.value?.blocked_reasons?.join('、')||'候选已被安全线拦截或状态已变化'), 1)
                      ]),
                      _: 1
                    }))
                  : (_openBlock(), _createElementBlock("div", _hoisted_36, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanupPreview.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("div", {
                          key: item.hash
                        }, [
                          _createElementVNode("strong", null, _toDisplayString(item.title||item.hash), 1),
                          _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(item.size||0)) + " · " + _toDisplayString(Number(item.score||0).toFixed(1)) + " 分", 1)
                        ]))
                      }), 128))
                    ]))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[27] || (_cache[27] = $event => (cleanupPreviewOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[72] || (_cache[72] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "error",
                  variant: "flat",
                  disabled: !cleanupPreview.value?.allowed,
                  onClick: confirmCleanupPreview
                }, {
                  default: _withCtx(() => [...(_cache[73] || (_cache[73] = [
                    _createTextVNode("确认名单并继续", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue", "fullscreen"]),
    _createVNode(_component_VDialog, {
      modelValue: deleteConfirmOpen.value,
      "onUpdate:modelValue": _cache[31] || (_cache[31] = $event => ((deleteConfirmOpen).value = $event)),
      "max-width": "38rem"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [...(_cache[74] || (_cache[74] = [
                _createTextVNode("确认移除下载", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _cache[76] || (_cache[76] = _createElementVNode("p", null, "将重新检查下载器中的进度。若种子已完成、卡住恢复推进或低速恢复正常，操作会被取消。", -1)),
                _createElementVNode("div", _hoisted_37, [
                  _createElementVNode("strong", null, _toDisplayString(deleteTarget.value?.title), 1),
                  _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(deleteTarget.value?.size||0)) + " · " + _toDisplayString(deleteTarget.value?.label), 1)
                ]),
                _createVNode(_component_VCheckbox, {
                  modelValue: deleteData.value,
                  "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((deleteData).value = $event)),
                  color: "error",
                  label: "同时删除本地下载数据",
                  hint: "默认仅移除下载器任务并保留文件；勾选后文件也会删除。",
                  "persistent-hint": "",
                  "hide-details": "auto"
                }, null, 8, ["modelValue"]),
                (deleteData.value)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      class: "mt-4",
                      type: "warning",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [...(_cache[75] || (_cache[75] = [
                        _createTextVNode("这会删除未完成的数据文件，通常无法恢复。请确认该下载确实不需要。", -1)
                      ]))]),
                      _: 1
                    }))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  disabled: saving.value,
                  onClick: _cache[30] || (_cache[30] = $event => (deleteConfirmOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[77] || (_cache[77] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  color: "error",
                  variant: "flat",
                  loading: saving.value,
                  onClick: confirmDeleteUnhealthyDownload
                }, {
                  default: _withCtx(() => [...(_cache[78] || (_cache[78] = [
                    _createTextVNode("确认删除", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: confirmOpen.value,
      "onUpdate:modelValue": _cache[33] || (_cache[33] = $event => ((confirmOpen).value = $event)),
      "max-width": "30rem"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(confirmAction.value?.label||'确认操作'), 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(confirmAction.value?.confirm||'确认执行这个操作吗？'), 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[32] || (_cache[32] = $event => (confirmOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[79] || (_cache[79] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: confirmAction.value?.tone||'primary',
                  variant: "flat",
                  loading: saving.value,
                  onClick: executeAction
                }, {
                  default: _withCtx(() => [...(_cache[80] || (_cache[80] = [
                    _createTextVNode("确认执行", -1)
                  ]))]),
                  _: 1
                }, 8, ["color", "loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const SmartBrushFlow = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-9cce68a0"]]);

export { SmartBrushFlow as S };

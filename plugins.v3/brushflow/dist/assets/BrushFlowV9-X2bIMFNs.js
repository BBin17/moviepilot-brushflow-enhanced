import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, f as formatBytes, a as formatDateTime, u as unwrapResponse } from './_plugin-vue_export-helper-DusmmjDQ.js';

const profileDefaults = {
  conservative: { selection_min_score: 40, max_add_per_run: 2, deletion_score_threshold: 35, candidate_confirmations: 4, confirmation_minutes: 60, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 2, max_delete_percent_day: 3, max_release_percent_run: 2, max_release_percent_day: 4, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 720, demand_confirmations: 2 },
  balanced: { selection_min_score: 30, max_add_per_run: 5, deletion_score_threshold: 40, candidate_confirmations: 3, confirmation_minutes: 30, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 3, max_delete_percent_day: 5, max_release_percent_run: 4, max_release_percent_day: 8, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 360, demand_confirmations: 2 },
  aggressive: { selection_min_score: 22, max_add_per_run: 8, deletion_score_threshold: 48, candidate_confirmations: 2, confirmation_minutes: 15, capacity_trigger_percent: 90, capacity_target_percent: 85, max_delete_per_run: 5, max_delete_percent_day: 10, max_release_percent_run: 8, max_release_percent_day: 15, max_release_gb_run: null, max_release_gb_day: null, cold_protection_minutes: 180, demand_confirmations: 2 },
};

function newTaskV9() {
  return {
    schema_version: 9,
    id: '',
    revision: 1,
    identity: { name: '', site_id: null, downloader: '', save_path: null, tag: null, enabled: true, notify: true },
    schedule: { brush_interval: 10, check_interval: 5, cron: null, active_time_range: null },
    goal: { enabled: false, ratio_target: null, reached_behavior: 'continue' },
    capacity: { limit_gb: null, max_downloads: null, upload_limit_kbps: null, download_limit_kbps: null, torrent_upload_limit_kbps: null, torrent_download_limit_kbps: null },
    selection: { enabled: true, source: 'page', promotion: 'free', exclude_hr: true, site_hr_active: false, exclude_subscriptions: true, size_min_gb: 0.5, size_max_gb: null, seeder_range: null, published_min_minutes: null, published_max_minutes: null, timezone_offset: 0, include: null, exclude: null },
    deletion: { enabled: false, min_seed_hours: null, exclude_tags: null, delete_data: true, invalid_tracker_cleanup: false, invalid_tracker_confirmations: 2, paused: false, observation_started_at: null, observation_until: null, observation_extensions: 0 },
    strategy: { profile: 'balanced', overrides: { ...profileDefaults.balanced } },
    health: { stalled_confirmations: 3, stalled_window_minutes: 30, slow_after_hours: 6, slow_speed_kbps: 128, auto_repair: true, pause_after_failed_repair: true },
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
    ['deletion','min_seed_hours'], ['strategy','overrides','max_release_gb_run'],
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
  const trigger = limit * Number(task.strategy.overrides.capacity_trigger_percent || 90) / 100;
  const target = limit * Number(task.strategy.overrides.capacity_target_percent || 85) / 100;
  return `${selection}；容量达到${trigger.toFixed(0)}GB开始安全清理，降到${target.toFixed(0)}GB停止；保种不足${task.deletion.min_seed_hours || 0}小时、正在上传、有真实需求或未完成的种子不会删除。`
}

function healthTone(level) {
  return ({ error: 'error', warning: 'warning', info: 'info', success: 'success' })[level] || 'secondary'
}

const {renderList:_renderList$2,Fragment:_Fragment$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,toDisplayString:_toDisplayString$2,createElementVNode:_createElementVNode$2,unref:_unref$2,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,createVNode:_createVNode$2,normalizeClass:_normalizeClass$2} = await importShared('vue');


const _hoisted_1$2 = {
  class: "task-health-grid",
  "aria-label": "刷流任务健康状态"
};
const _hoisted_2$2 = ["onClick"];
const _hoisted_3$2 = { class: "task-health-card__top" };
const _hoisted_4$2 = { class: "task-health-card__capacity" };
const _hoisted_5$2 = { class: "task-health-card__meta" };


const _sfc_main$2 = {
  __name: 'TaskHealthCards',
  props: { tasks: { type: Array, default: () => [] }, selectedId: { type: String, default: '' } },
  emits: ['select', 'create'],
  setup(__props) {




return (_ctx, _cache) => {
  const _component_VChip = _resolveComponent$2("VChip");
  const _component_VProgressLinear = _resolveComponent$2("VProgressLinear");
  const _component_VIcon = _resolveComponent$2("VIcon");

  return (_openBlock$2(), _createElementBlock$2("section", _hoisted_1$2, [
    (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(__props.tasks, (task) => {
      return (_openBlock$2(), _createElementBlock$2("button", {
        key: task.id,
        type: "button",
        class: _normalizeClass$2(["task-health-card", { selected: task.id === __props.selectedId }]),
        onClick: $event => (_ctx.$emit('select', task.id))
      }, [
        _createElementVNode$2("div", _hoisted_3$2, [
          _createElementVNode$2("div", null, [
            _createElementVNode$2("strong", null, _toDisplayString$2(task.name), 1),
            _createElementVNode$2("span", null, _toDisplayString$2(task.site_name) + " · " + _toDisplayString$2(task.downloader), 1)
          ]),
          _createVNode$2(_component_VChip, {
            size: "x-small",
            color: _unref$2(healthTone)(task.strategy?.ui_summary?.health?.level),
            variant: "tonal"
          }, {
            default: _withCtx$2(() => [
              _createTextVNode$2(_toDisplayString$2(task.strategy?.ui_summary?.health?.title || '等待检查'), 1)
            ]),
            _: 2
          }, 1032, ["color"])
        ]),
        _createElementVNode$2("div", _hoisted_4$2, [
          _createElementVNode$2("span", null, _toDisplayString$2(_unref$2(formatBytes)(task.seeding_size)), 1),
          _createElementVNode$2("small", null, _toDisplayString$2(task.strategy?.ui_summary?.capacity?.limit_bytes ? `上限 ${_unref$2(formatBytes)(task.strategy.ui_summary.capacity.limit_bytes)}` : '容量未设置'), 1)
        ]),
        _createVNode$2(_component_VProgressLinear, {
          "model-value": Math.min(task.strategy?.ui_summary?.capacity?.percent || 0, 100),
          color: (task.strategy?.ui_summary?.capacity?.percent || 0) > 100 ? 'error' : _unref$2(healthTone)(task.strategy?.ui_summary?.health?.level),
          height: "5",
          rounded: ""
        }, null, 8, ["model-value", "color"]),
        _createElementVNode$2("div", _hoisted_5$2, [
          _createElementVNode$2("span", null, "上传 " + _toDisplayString$2(Number(task.strategy?.uploaded_gb_per_day || 0).toFixed(1)) + " GB/天", 1),
          _createElementVNode$2("span", null, "异常 " + _toDisplayString$2((task.strategy?.ui_summary?.download?.stalled_count || 0) + (task.strategy?.ui_summary?.download?.slow_count || 0) + (task.strategy?.ui_summary?.download?.queued_count || 0) + (task.strategy?.ui_summary?.download?.error_count || 0)), 1)
        ]),
        _createElementVNode$2("p", null, _toDisplayString$2(task.strategy?.ui_summary?.health?.message || '首次检查后显示下一步。'), 1)
      ], 10, _hoisted_2$2))
    }), 128)),
    _createElementVNode$2("button", {
      type: "button",
      class: "task-health-card task-health-card--create",
      onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('create')))
    }, [
      _createVNode$2(_component_VIcon, {
        icon: "mdi-plus-circle-outline",
        size: "30"
      }),
      _cache[1] || (_cache[1] = _createElementVNode$2("strong", null, "新建刷流任务", -1)),
      _cache[2] || (_cache[2] = _createElementVNode$2("span", null, "按四步向导完成设置", -1))
    ])
  ]))
}
}

};
const TaskHealthCards = /*#__PURE__*/_export_sfc(_sfc_main$2, [['__scopeId',"data-v-13f92333"]]);

const {unref:_unref$1,toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createVNode:_createVNode$1,renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createElementVNode:_createElementVNode$1,normalizeClass:_normalizeClass$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1} = await importShared('vue');


const _hoisted_1$1 = { class: "wizard__steps" };
const _hoisted_2$1 = ["onClick"];
const _hoisted_3$1 = { class: "wizard__content" };
const _hoisted_4$1 = {
  key: 1,
  class: "wizard-section"
};
const _hoisted_5$1 = { class: "switches" };
const _hoisted_6$1 = {
  key: 2,
  class: "wizard-section"
};
const _hoisted_7$1 = {
  key: 3,
  class: "wizard-section"
};
const _hoisted_8$1 = { class: "profile-grid" };
const _hoisted_9$1 = ["onClick"];
const _hoisted_10$1 = { class: "switches" };
const _hoisted_11$1 = {
  key: 4,
  class: "wizard-section"
};
const _hoisted_12$1 = { class: "switches" };
const _hoisted_13$1 = { class: "wizard__summary" };

const {computed: computed$1,ref: ref$1,watch} = await importShared('vue');

const {useDisplay} = await importShared('vuetify');


const _sfc_main$1 = {
  __name: 'TaskWizardV9',
  props: { modelValue: Boolean, task: Object, sites: { type: Array, default: () => [] }, downloaders: { type: Array, default: () => [] }, saving: Boolean },
  emits: ['update:modelValue', 'save'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const display = useDisplay();
const step = ref$1(1);
const draft = ref$1(cloneTaskV9());
const error = ref$1('');
const advanced = ref$1(false);
const saveConfirmOpen = ref$1(false);
const steps = ['站点与任务', '空间与速度', '选种方式', '删种与安全'];
const siteName = computed$1(() => props.sites.find(item => Number(item.value) === Number(draft.value.identity.site_id))?.title || '当前站点');
const preview = computed$1(() => taskPreview(draft.value, siteName.value));

watch(() => props.modelValue, value => { if (value) { draft.value = cloneTaskV9(props.task); step.value = 1; error.value = ''; advanced.value = false; } });

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
  emit('save', normalizeTaskV9(draft.value));
}

return (_ctx, _cache) => {
  const _component_VToolbarTitle = _resolveComponent$1("VToolbarTitle");
  const _component_VSpacer = _resolveComponent$1("VSpacer");
  const _component_VBtn = _resolveComponent$1("VBtn");
  const _component_VToolbar = _resolveComponent$1("VToolbar");
  const _component_VDivider = _resolveComponent$1("VDivider");
  const _component_VAlert = _resolveComponent$1("VAlert");
  const _component_VTextField = _resolveComponent$1("VTextField");
  const _component_VCol = _resolveComponent$1("VCol");
  const _component_VSelect = _resolveComponent$1("VSelect");
  const _component_VRow = _resolveComponent$1("VRow");
  const _component_VSwitch = _resolveComponent$1("VSwitch");
  const _component_VExpansionPanelTitle = _resolveComponent$1("VExpansionPanelTitle");
  const _component_VExpansionPanelText = _resolveComponent$1("VExpansionPanelText");
  const _component_VExpansionPanel = _resolveComponent$1("VExpansionPanel");
  const _component_VExpansionPanels = _resolveComponent$1("VExpansionPanels");
  const _component_VIcon = _resolveComponent$1("VIcon");
  const _component_VChip = _resolveComponent$1("VChip");
  const _component_VCardText = _resolveComponent$1("VCardText");
  const _component_VCardActions = _resolveComponent$1("VCardActions");
  const _component_VCard = _resolveComponent$1("VCard");
  const _component_VCardTitle = _resolveComponent$1("VCardTitle");
  const _component_VDialog = _resolveComponent$1("VDialog");

  return (_openBlock$1(), _createBlock$1(_component_VDialog, {
    "model-value": __props.modelValue,
    fullscreen: _unref$1(display).smAndDown.value,
    "max-width": "72rem",
    scrollable: "",
    "onUpdate:modelValue": _cache[50] || (_cache[50] = value => emit('update:modelValue', value))
  }, {
    default: _withCtx$1(() => [
      _createVNode$1(_component_VCard, { class: "wizard" }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VToolbar, { color: "transparent" }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VToolbarTitle, null, {
                default: _withCtx$1(() => [
                  _createTextVNode$1(_toDisplayString$1(draft.value.id ? '编辑任务' : '新建任务'), 1)
                ]),
                _: 1
              }),
              _createVNode$1(_component_VSpacer),
              _createVNode$1(_component_VBtn, {
                icon: "mdi-close",
                onClick: close
              })
            ]),
            _: 1
          }),
          _createVNode$1(_component_VDivider),
          _createVNode$1(_component_VCardText, { class: "wizard__body" }, {
            default: _withCtx$1(() => [
              _createElementVNode$1("nav", _hoisted_1$1, [
                (_openBlock$1(), _createElementBlock$1(_Fragment$1, null, _renderList$1(steps, (label, index) => {
                  return _createElementVNode$1("button", {
                    key: label,
                    type: "button",
                    class: _normalizeClass$1({active:step.value===index+1,done:step.value>index+1}),
                    onClick: $event => (step.value=index+1)
                  }, [
                    _createElementVNode$1("span", null, _toDisplayString$1(index+1), 1),
                    _createTextVNode$1(_toDisplayString$1(label), 1)
                  ], 10, _hoisted_2$1)
                }), 64))
              ]),
              _createElementVNode$1("main", _hoisted_3$1, [
                (error.value)
                  ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                      key: 0,
                      type: "error",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(error.value), 1)
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode$1("", true),
                (step.value===1)
                  ? (_openBlock$1(), _createElementBlock$1("section", _hoisted_4$1, [
                      _cache[51] || (_cache[51] = _createElementVNode$1("div", null, [
                        _createElementVNode$1("h3", null, "这个任务刷哪个站？"),
                        _createElementVNode$1("p", null, "站点和下载器保存后仍可修改，历史数据会继续关联。")
                      ], -1)),
                      _createVNode$1(_component_VRow, null, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.identity.name,
                                "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((draft.value.identity.name) = $event)),
                                label: "任务名称"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VSelect, {
                                modelValue: draft.value.identity.site_id,
                                "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((draft.value.identity.site_id) = $event)),
                                items: __props.sites,
                                label: "站点"
                              }, null, 8, ["modelValue", "items"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VSelect, {
                                modelValue: draft.value.identity.downloader,
                                "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((draft.value.identity.downloader) = $event)),
                                items: __props.downloaders,
                                label: "下载器"
                              }, null, 8, ["modelValue", "items"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.identity.save_path,
                                "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((draft.value.identity.save_path) = $event)),
                                label: "保存目录",
                                placeholder: "留空使用下载器默认目录"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createVNode$1(_component_VRow, null, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                      _createElementVNode$1("div", _hoisted_5$1, [
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.identity.enabled,
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((draft.value.identity.enabled) = $event)),
                          label: "启用任务",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.identity.notify,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((draft.value.identity.notify) = $event)),
                          label: "发送通知",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.goal.enabled,
                          "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((draft.value.goal.enabled) = $event)),
                          label: "设置分享率目标",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      (draft.value.goal.enabled)
                        ? (_openBlock$1(), _createBlock$1(_component_VRow, { key: 0 }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VCol, {
                                cols: "12",
                                md: "6"
                              }, {
                                default: _withCtx$1(() => [
                                  _createVNode$1(_component_VTextField, {
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
                              _createVNode$1(_component_VCol, {
                                cols: "12",
                                md: "6"
                              }, {
                                default: _withCtx$1(() => [
                                  _createVNode$1(_component_VSelect, {
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
                        : _createCommentVNode$1("", true)
                    ]))
                  : _createCommentVNode$1("", true),
                (step.value===2)
                  ? (_openBlock$1(), _createElementBlock$1("section", _hoisted_6$1, [
                      _cache[52] || (_cache[52] = _createElementVNode$1("div", null, [
                        _createElementVNode$1("h3", null, "给任务多少空间和带宽？"),
                        _createElementVNode$1("p", null, "任务容量独立计算；全局限制只负责阻止继续新增。")
                      ], -1)),
                      _createVNode$1(_component_VRow, null, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.capacity.limit_gb,
                                "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((draft.value.capacity.limit_gb) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "0",
                                label: "任务容量上限（GB）",
                                hint: "自动删种按90%开始、85%停止",
                                "persistent-hint": ""
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.capacity.upload_limit_kbps,
                                "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((draft.value.capacity.upload_limit_kbps) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                label: "总上传限速（KB/s）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.capacity.download_limit_kbps,
                                "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((draft.value.capacity.download_limit_kbps) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                label: "总下载限速（KB/s）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                  : _createCommentVNode$1("", true),
                (step.value===3)
                  ? (_openBlock$1(), _createElementBlock$1("section", _hoisted_7$1, [
                      _cache[53] || (_cache[53] = _createElementVNode$1("div", null, [
                        _createElementVNode$1("h3", null, "优先选择什么种子？"),
                        _createElementVNode$1("p", null, "明确的体积、H&R和文本规则始终是硬过滤。")
                      ], -1)),
                      _createElementVNode$1("div", _hoisted_8$1, [
                        (_openBlock$1(), _createElementBlock$1(_Fragment$1, null, _renderList$1(['conservative','balanced','aggressive'], (profile) => {
                          return _createElementVNode$1("button", {
                            key: profile,
                            type: "button",
                            class: _normalizeClass$1({active:draft.value.strategy.profile===profile}),
                            onClick: $event => (chooseProfile(profile))
                          }, [
                            _createElementVNode$1("strong", null, _toDisplayString$1(_unref$1(profileLabel)(profile)), 1),
                            _createElementVNode$1("span", null, _toDisplayString$1(profile==='conservative'?'更少新增，适合空间紧张':profile==='balanced'?'收益与稳定性平衡':'更积极抢新种'), 1)
                          ], 10, _hoisted_9$1)
                        }), 64))
                      ]),
                      _createVNode$1(_component_VRow, null, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VSelect, {
                                modelValue: draft.value.selection.promotion,
                                "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((draft.value.selection.promotion) = $event)),
                                label: "促销要求",
                                items: [{title:'全部',value:'all'},{title:'免费',value:'free'},{title:'2X免费',value:'2xfree'}]
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VSelect, {
                                modelValue: draft.value.selection.source,
                                "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((draft.value.selection.source) = $event)),
                                label: "种子来源",
                                items: [{title:'站点列表页',value:'page'},{title:'RSS',value:'rss'}]
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                      _createElementVNode$1("div", _hoisted_10$1, [
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.selection.enabled,
                          "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((draft.value.selection.enabled) = $event)),
                          label: "启用智能选种",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.selection.exclude_hr,
                          "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((draft.value.selection.exclude_hr) = $event)),
                          label: "排除H&R",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.selection.exclude_subscriptions,
                          "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((draft.value.selection.exclude_subscriptions) = $event)),
                          label: "排除订阅内容",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createVNode$1(_component_VRow, null, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.selection.include,
                                "onUpdate:modelValue": _cache[24] || (_cache[24] = $event => ((draft.value.selection.include) = $event)),
                                label: "必须包含（正则，可选）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
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
                  : _createCommentVNode$1("", true),
                (step.value===4)
                  ? (_openBlock$1(), _createElementBlock$1("section", _hoisted_11$1, [
                      _cache[62] || (_cache[62] = _createElementVNode$1("div", null, [
                        _createElementVNode$1("h3", null, "如何安全释放空间？"),
                        _createElementVNode$1("p", null, "新启用或风险扩大后先观察，不会立即删除。")
                      ], -1)),
                      _createVNode$1(_component_VSwitch, {
                        modelValue: draft.value.deletion.enabled,
                        "onUpdate:modelValue": _cache[26] || (_cache[26] = $event => ((draft.value.deletion.enabled) = $event)),
                        color: "error",
                        label: "启用统一智能删种"
                      }, null, 8, ["modelValue"]),
                      (draft.value.deletion.enabled)
                        ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                            key: 0,
                            type: "info",
                            variant: "tonal"
                          }, {
                            default: _withCtx$1(() => [...(_cache[54] || (_cache[54] = [
                              _createTextVNode$1("前48小时只记录候选，不会实际删除；未完成、H&R、未到最低保种、正在上传或有真实需求的种子永久保护。", -1)
                            ]))]),
                            _: 1
                          }))
                        : _createCommentVNode$1("", true),
                      _createVNode$1(_component_VRow, null, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.deletion.min_seed_hours,
                                "onUpdate:modelValue": _cache[27] || (_cache[27] = $event => ((draft.value.deletion.min_seed_hours) = $event)),
                                modelModifiers: { number: true },
                                type: "number",
                                min: "1",
                                label: "站点最低保种时间（小时）"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          }),
                          _createVNode$1(_component_VCol, {
                            cols: "12",
                            md: "6"
                          }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VTextField, {
                                modelValue: draft.value.deletion.exclude_tags,
                                "onUpdate:modelValue": _cache[28] || (_cache[28] = $event => ((draft.value.deletion.exclude_tags) = $event)),
                                label: "永不删除的标签"
                              }, null, 8, ["modelValue"])
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      _createElementVNode$1("div", _hoisted_12$1, [
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.deletion.delete_data,
                          "onUpdate:modelValue": _cache[29] || (_cache[29] = $event => ((draft.value.deletion.delete_data) = $event)),
                          color: "error",
                          label: "清理时同时删除下载数据",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]),
                        _createVNode$1(_component_VSwitch, {
                          modelValue: draft.value.deletion.invalid_tracker_cleanup,
                          "onUpdate:modelValue": _cache[30] || (_cache[30] = $event => ((draft.value.deletion.invalid_tracker_cleanup) = $event)),
                          label: "清理Tracker明确拒绝的任务（保留数据）",
                          "hide-details": ""
                        }, null, 8, ["modelValue"])
                      ]),
                      _createVNode$1(_component_VExpansionPanels, {
                        modelValue: advanced.value,
                        "onUpdate:modelValue": _cache[47] || (_cache[47] = $event => ((advanced).value = $event)),
                        class: "mt-4"
                      }, {
                        default: _withCtx$1(() => [
                          _createVNode$1(_component_VExpansionPanel, { value: true }, {
                            default: _withCtx$1(() => [
                              _createVNode$1(_component_VExpansionPanelTitle, null, {
                                default: _withCtx$1(() => [...(_cache[55] || (_cache[55] = [
                                  _createTextVNode$1("高级设置（安全参数组）", -1)
                                ]))]),
                                _: 1
                              }),
                              _createVNode$1(_component_VExpansionPanelText, null, {
                                default: _withCtx$1(() => [
                                  _cache[57] || (_cache[57] = _createElementVNode$1("h4", null, "评分", -1)),
                                  _createVNode$1(_component_VRow, null, {
                                    default: _withCtx$1(() => [
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.selection_min_score,
                                            "onUpdate:modelValue": [
                                              _cache[31] || (_cache[31] = $event => ((draft.value.strategy.overrides.selection_min_score) = $event)),
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
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.deletion_score_threshold,
                                            "onUpdate:modelValue": [
                                              _cache[32] || (_cache[32] = $event => ((draft.value.strategy.overrides.deletion_score_threshold) = $event)),
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
                                  _cache[58] || (_cache[58] = _createElementVNode$1("h4", null, "容量控制", -1)),
                                  _createVNode$1(_component_VRow, null, {
                                    default: _withCtx$1(() => [
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.capacity_trigger_percent,
                                            "onUpdate:modelValue": [
                                              _cache[33] || (_cache[33] = $event => ((draft.value.strategy.overrides.capacity_trigger_percent) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            max: "100",
                                            label: "容量触发线（%）",
                                            hint: "默认90%开始清理",
                                            "persistent-hint": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.capacity_target_percent,
                                            "onUpdate:modelValue": [
                                              _cache[34] || (_cache[34] = $event => ((draft.value.strategy.overrides.capacity_target_percent) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            max: "99",
                                            label: "容量停止线（%）",
                                            hint: "默认降到85%停止",
                                            "persistent-hint": ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _cache[59] || (_cache[59] = _createElementVNode$1("h4", null, "候选确认", -1)),
                                  _createVNode$1(_component_VRow, null, {
                                    default: _withCtx$1(() => [
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
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
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
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
                                  _cache[60] || (_cache[60] = _createElementVNode$1("h4", null, "删除限额", -1)),
                                  _createVNode$1(_component_VRow, null, {
                                    default: _withCtx$1(() => [
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "4"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.max_delete_per_run,
                                            "onUpdate:modelValue": [
                                              _cache[37] || (_cache[37] = $event => ((draft.value.strategy.overrides.max_delete_per_run) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            label: "每轮最多删除（个）"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "4"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.max_release_percent_run,
                                            "onUpdate:modelValue": [
                                              _cache[38] || (_cache[38] = $event => ((draft.value.strategy.overrides.max_release_percent_run) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            max: "100",
                                            label: "每轮最多释放（容量%）"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "4"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.max_release_percent_day,
                                            "onUpdate:modelValue": [
                                              _cache[39] || (_cache[39] = $event => ((draft.value.strategy.overrides.max_release_percent_day) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            max: "100",
                                            label: "每天最多释放（容量%）"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.max_release_gb_run,
                                            "onUpdate:modelValue": [
                                              _cache[40] || (_cache[40] = $event => ((draft.value.strategy.overrides.max_release_gb_run) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            label: "每轮GB上限（可选）",
                                            clearable: ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "6"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.strategy.overrides.max_release_gb_day,
                                            "onUpdate:modelValue": [
                                              _cache[41] || (_cache[41] = $event => ((draft.value.strategy.overrides.max_release_gb_day) = $event)),
                                              markCustom
                                            ],
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "0",
                                            label: "每天GB上限（可选）",
                                            clearable: ""
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _cache[61] || (_cache[61] = _createElementVNode$1("h4", null, "下载健康", -1)),
                                  _createVNode$1(_component_VRow, null, {
                                    default: _withCtx$1(() => [
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.health.stalled_confirmations,
                                            "onUpdate:modelValue": _cache[42] || (_cache[42] = $event => ((draft.value.health.stalled_confirmations) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "2",
                                            max: "10",
                                            label: "卡住确认次数"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.health.stalled_window_minutes,
                                            "onUpdate:modelValue": _cache[43] || (_cache[43] = $event => ((draft.value.health.stalled_window_minutes) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "10",
                                            label: "卡住观察分钟"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.health.slow_after_hours,
                                            "onUpdate:modelValue": _cache[44] || (_cache[44] = $event => ((draft.value.health.slow_after_hours) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            label: "低速观察小时"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      }),
                                      _createVNode$1(_component_VCol, {
                                        cols: "12",
                                        md: "3"
                                      }, {
                                        default: _withCtx$1(() => [
                                          _createVNode$1(_component_VTextField, {
                                            modelValue: draft.value.health.slow_speed_kbps,
                                            "onUpdate:modelValue": _cache[45] || (_cache[45] = $event => ((draft.value.health.slow_speed_kbps) = $event)),
                                            modelModifiers: { number: true },
                                            type: "number",
                                            min: "1",
                                            label: "低速阈值KB/s"
                                          }, null, 8, ["modelValue"])
                                        ]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }),
                                  _createVNode$1(_component_VBtn, {
                                    variant: "tonal",
                                    onClick: _cache[46] || (_cache[46] = $event => (chooseProfile(draft.value.strategy.profile==='custom'?'balanced':draft.value.strategy.profile)))
                                  }, {
                                    default: _withCtx$1(() => [...(_cache[56] || (_cache[56] = [
                                      _createTextVNode$1("恢复当前预设", -1)
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
                  : _createCommentVNode$1("", true)
              ]),
              _createElementVNode$1("aside", _hoisted_13$1, [
                _createVNode$1(_component_VIcon, {
                  icon: "mdi-text-box-check-outline",
                  color: "primary",
                  size: "28"
                }),
                _cache[63] || (_cache[63] = _createElementVNode$1("h3", null, "保存后会这样运行", -1)),
                _createElementVNode$1("p", null, _toDisplayString$1(preview.value), 1),
                _createVNode$1(_component_VChip, { variant: "tonal" }, {
                  default: _withCtx$1(() => [
                    _createTextVNode$1(_toDisplayString$1(_unref$1(profileLabel)(draft.value.strategy.profile)), 1)
                  ]),
                  _: 1
                })
              ])
            ]),
            _: 1
          }),
          _createVNode$1(_component_VDivider),
          _createVNode$1(_component_VCardActions, null, {
            default: _withCtx$1(() => [
              (step.value>1)
                ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                    key: 0,
                    variant: "text",
                    onClick: previous
                  }, {
                    default: _withCtx$1(() => [...(_cache[64] || (_cache[64] = [
                      _createTextVNode$1("上一步", -1)
                    ]))]),
                    _: 1
                  }))
                : _createCommentVNode$1("", true),
              _createVNode$1(_component_VSpacer),
              _createVNode$1(_component_VBtn, {
                variant: "text",
                onClick: close
              }, {
                default: _withCtx$1(() => [...(_cache[65] || (_cache[65] = [
                  _createTextVNode$1("取消", -1)
                ]))]),
                _: 1
              }),
              (step.value<4)
                ? (_openBlock$1(), _createBlock$1(_component_VBtn, {
                    key: 1,
                    color: "primary",
                    variant: "flat",
                    onClick: next
                  }, {
                    default: _withCtx$1(() => [...(_cache[66] || (_cache[66] = [
                      _createTextVNode$1("下一步", -1)
                    ]))]),
                    _: 1
                  }))
                : (_openBlock$1(), _createBlock$1(_component_VBtn, {
                    key: 2,
                    color: "primary",
                    variant: "flat",
                    loading: __props.saving,
                    onClick: save
                  }, {
                    default: _withCtx$1(() => [...(_cache[67] || (_cache[67] = [
                      _createTextVNode$1("保存任务", -1)
                    ]))]),
                    _: 1
                  }, 8, ["loading"]))
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode$1(_component_VDialog, {
        modelValue: saveConfirmOpen.value,
        "onUpdate:modelValue": _cache[49] || (_cache[49] = $event => ((saveConfirmOpen).value = $event)),
        "max-width": "32rem"
      }, {
        default: _withCtx$1(() => [
          _createVNode$1(_component_VCard, null, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_VCardTitle, null, {
                default: _withCtx$1(() => [...(_cache[68] || (_cache[68] = [
                  _createTextVNode$1("确认保存这套规则", -1)
                ]))]),
                _: 1
              }),
              _createVNode$1(_component_VCardText, null, {
                default: _withCtx$1(() => [
                  _createElementVNode$1("p", null, _toDisplayString$1(preview.value), 1),
                  (draft.value.deletion.enabled)
                    ? (_openBlock$1(), _createBlock$1(_component_VAlert, {
                        key: 0,
                        type: "warning",
                        variant: "tonal",
                        class: "mt-4"
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(" 自动删种将" + _toDisplayString$1(draft.value.deletion.delete_data ? '删除下载器任务和对应数据' : '只移除下载器任务并保留数据') + "；新启用或放宽安全参数后会先进入观察期，硬安全线始终有效。 ", 1)
                        ]),
                        _: 1
                      }))
                    : _createCommentVNode$1("", true)
                ]),
                _: 1
              }),
              _createVNode$1(_component_VCardActions, null, {
                default: _withCtx$1(() => [
                  _createVNode$1(_component_VSpacer),
                  _createVNode$1(_component_VBtn, {
                    variant: "text",
                    onClick: _cache[48] || (_cache[48] = $event => (saveConfirmOpen.value=false))
                  }, {
                    default: _withCtx$1(() => [...(_cache[69] || (_cache[69] = [
                      _createTextVNode$1("返回修改", -1)
                    ]))]),
                    _: 1
                  }),
                  _createVNode$1(_component_VBtn, {
                    color: "primary",
                    variant: "flat",
                    loading: __props.saving,
                    onClick: confirmSave
                  }, {
                    default: _withCtx$1(() => [...(_cache[70] || (_cache[70] = [
                      _createTextVNode$1("确认保存", -1)
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
const TaskWizardV9 = /*#__PURE__*/_export_sfc(_sfc_main$1, [['__scopeId',"data-v-6d6c38d7"]]);

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createElementBlock:_createElementBlock,unref:_unref,normalizeClass:_normalizeClass,renderList:_renderList,Fragment:_Fragment,normalizeStyle:_normalizeStyle} = await importShared('vue');


const _hoisted_1 = { class: "bf9" };
const _hoisted_2 = { class: "bf9__header" };
const _hoisted_3 = { class: "bf9__brand" };
const _hoisted_4 = { class: "bf9__header-actions" };
const _hoisted_5 = {
  key: 2,
  class: "bf9__empty"
};
const _hoisted_6 = { class: "bf9__taskbar" };
const _hoisted_7 = {
  key: 0,
  class: "bf9__attention"
};
const _hoisted_8 = { class: "bf9__capacity panel" };
const _hoisted_9 = { class: "capacity-track" };
const _hoisted_10 = { class: "capacity-labels" };
const _hoisted_11 = { class: "bf9__summary-grid" };
const _hoisted_12 = { class: "panel" };
const _hoisted_13 = { key: 0 };
const _hoisted_14 = { class: "panel" };
const _hoisted_15 = { class: "panel" };
const _hoisted_16 = { class: "bf9__facts" };
const _hoisted_17 = { class: "panel mt-4" };
const _hoisted_18 = { class: "bf9__list-head" };
const _hoisted_19 = { class: "torrent-list" };
const _hoisted_20 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_21 = { class: "panel mt-4" };
const _hoisted_22 = { class: "event-list" };
const _hoisted_23 = { key: 0 };
const _hoisted_24 = {
  key: 0,
  class: "bf9__empty small"
};
const _hoisted_25 = { class: "settings-grid" };
const _hoisted_26 = { class: "settings-title" };

const {computed,inject,onMounted,onUnmounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'BrushFlowV9',
  props: { api: { type: Object, default: () => ({}) }, pluginId: { type: String, default: 'BrushFlow' }, showClose: Boolean },
  emits: ['close','action'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const toast = inject('moviepilot:toast', null);
const base = computed(() => `plugin/${props.pluginId}`);
const loading = ref(false), saving = ref(false), error = ref('');
const status = ref({ enabled:false, summary:{}, tasks:[], options:{sites:[],downloaders:[]} });
const selectedId = ref(''), detail = ref(null), tab = ref('status'), torrentState = ref('active'), page = ref(1);
const wizard = ref(false), wizardTask = ref(newTaskV9());
const confirmOpen = ref(false), confirmAction = ref(null);
const settingsOpen = ref(false), settingsDraft = ref({});
const changeNotice = ref('');
let timer;
const tasks = computed(() => status.value.tasks || []);
const selected = computed(() => tasks.value.find(item => item.id === selectedId.value) || null);
const strategy = computed(() => detail.value?.strategy || selected.value?.strategy || {});
const summary = computed(() => strategy.value.ui_summary || {});
const task = computed(() => detail.value?.task || null);
const torrents = computed(() => detail.value?.torrents || {items:[],total:0,page:1,page_size:50});
const runs = computed(() => detail.value?.runs || []);

function notify(message, type='success'){ if(typeof toast?.[type]==='function') toast[type](message); else if(type==='error') error.value=message; }
async function loadDetail(){ if(!selectedId.value)return; try{ const [baseDetail,torrentData,eventData]=await Promise.all([props.api.get(`${base.value}/tasks/${selectedId.value}`),props.api.get(`${base.value}/tasks/${selectedId.value}/torrents?state=${torrentState.value}&page=${page.value}&page_size=50`),props.api.get(`${base.value}/tasks/${selectedId.value}/events?page=1&page_size=20`)]); detail.value={...(unwrapResponse(baseDetail)||{}),torrents:unwrapResponse(torrentData),runs:unwrapResponse(eventData)?.items||[]}; }catch(err){ error.value=err?.message||'加载任务失败'; } }
async function load(){ loading.value=true; try{ status.value=unwrapResponse(await props.api.get(`${base.value}/status`))||status.value; if(!tasks.value.some(item=>item.id===selectedId.value)) selectedId.value=tasks.value[0]?.id||''; await loadDetail(); }catch(err){ error.value=err?.message||'加载刷流状态失败'; }finally{ loading.value=false; } }
function openSettings(){ const signin=status.value.signin||{}; settingsDraft.value={enabled:!!status.value.enabled,show_sidebar_nav:status.value.show_sidebar_nav!==false,global_disksize:status.value.global_disksize??null,global_maxdlcount:status.value.global_maxdlcount??null,global_maxupspeed:status.value.global_maxupspeed??null,global_maxdlspeed:status.value.global_maxdlspeed??null,signin_enabled:!!signin.enabled,signin_notify:signin.notify!==false,signin_cron:signin.cron||'17 7 * * *',signin_sites:[...(signin.site_ids||[])]}; settingsOpen.value=true; }
async function saveSettings(){ saving.value=true; try{ status.value=unwrapResponse(await props.api.post(`${base.value}/settings`,settingsDraft.value))||status.value; settingsOpen.value=false; await load(); notify('插件设置已保存'); }catch(err){ notify(err?.message||'保存设置失败','error'); }finally{ saving.value=false; } }
async function runSignin(){ saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/signin/run`,{})); await load(); notify('站点签到已执行'); }catch(err){ notify(err?.message||'签到失败','error'); }finally{ saving.value=false; } }
async function selectTask(id){ selectedId.value=id; page.value=1; torrentState.value='active'; tab.value='status'; await loadDetail(); }
function createTask(){ wizardTask.value=newTaskV9(); wizard.value=true; }
function editTask(){ if(!task.value)return; wizardTask.value=cloneTaskV9(task.value); wizard.value=true; }
async function saveTask(payload){ saving.value=true; try{ const previous=task.value; const response=payload.id?await props.api.put(`${base.value}/tasks/${payload.id}`,payload):await props.api.post(`${base.value}/tasks`,payload); const data=unwrapResponse(response); selectedId.value=data?.task?.id||payload.id||selectedId.value; wizard.value=false; const effects=[]; if(!previous) effects.push('已建立新的选种与检查计划'); else { if(JSON.stringify(previous.capacity)!==JSON.stringify(payload.capacity)) effects.push('容量或速度限制已更新'); if(JSON.stringify(previous.selection)!==JSON.stringify(payload.selection)) effects.push('选种硬过滤与评分入口已更新'); if(JSON.stringify(previous.deletion)!==JSON.stringify(payload.deletion)||JSON.stringify(previous.strategy)!==JSON.stringify(payload.strategy)) effects.push('删种安全策略已更新，风险扩大时重新进入观察'); } changeNotice.value=effects.join('；')||'任务基础信息已更新'; await load(); notify(payload.id?'任务已更新':'任务已创建'); }catch(err){ notify(err?.message||'保存任务失败','error'); }finally{ saving.value=false; } }
function askAction(action){ confirmAction.value=action; confirmOpen.value=true; }
async function executeAction(){ const action=confirmAction.value; if(!action)return; confirmOpen.value=false; if(action.code==='open_editor'){ confirmAction.value=null; editTask(); return } saving.value=true; try{ unwrapResponse(await props.api.post(`${base.value}/tasks/${selectedId.value}/actions/${action.code}`,{})); await load(); notify(action.success||'操作已提交'); }catch(err){ notify(err?.message||'操作失败','error'); }finally{ saving.value=false; confirmAction.value=null; } }
function topAction(code,label,confirm,success){ askAction({code,label,confirm,success,tone:'primary'}); }
async function changeTorrentState(value){ torrentState.value=value; page.value=1; await loadDetail(); }
async function changePage(value){ page.value=value; await loadDetail(); }
onMounted(()=>{ load(); timer=window.setInterval(load,30000); }); onUnmounted(()=>window.clearInterval(timer));

return (_ctx, _cache) => {
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VExpansionPanelTitle = _resolveComponent("VExpansionPanelTitle");
  const _component_VExpansionPanelText = _resolveComponent("VExpansionPanelText");
  const _component_VExpansionPanel = _resolveComponent("VExpansionPanel");
  const _component_VExpansionPanels = _resolveComponent("VExpansionPanels");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VBtnToggle = _resolveComponent("VBtnToggle");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VPagination = _resolveComponent("VPagination");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("header", _hoisted_2, [
      _createElementVNode("div", null, [
        _createElementVNode("div", _hoisted_3, [
          _createVNode(_component_VIcon, {
            icon: "mdi-sync-circle",
            color: "primary",
            size: "34"
          }),
          _cache[23] || (_cache[23] = _createElementVNode("div", null, [
            _createElementVNode("h1", null, "站点刷流"),
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
          default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
            _createTextVNode("刷新", -1)
          ]))]),
          _: 1
        }, 8, ["loading"]),
        _createVNode(_component_VBtn, {
          variant: "text",
          "prepend-icon": "mdi-tune",
          onClick: openSettings
        }, {
          default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
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
          default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
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
          default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
            _createTextVNode("插件当前未启用；任务和历史可以查看，但不会自动运行。", -1)
          ]))]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(TaskHealthCards, {
      tasks: tasks.value,
      "selected-id": selectedId.value,
      onSelect: selectTask,
      onCreate: createTask
    }, null, 8, ["tasks", "selected-id"]),
    (!tasks.value.length&&!loading.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
          _createVNode(_component_VIcon, {
            icon: "mdi-radar",
            size: "52"
          }),
          _cache[29] || (_cache[29] = _createElementVNode("h2", null, "还没有刷流任务", -1)),
          _cache[30] || (_cache[30] = _createElementVNode("p", null, "四步完成站点、容量、选种和安全规则。", -1)),
          _createVNode(_component_VBtn, {
            color: "primary",
            onClick: createTask
          }, {
            default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
              _createTextVNode("创建第一个任务", -1)
            ]))]),
            _: 1
          })
        ]))
      : _createCommentVNode("", true),
    (selected.value)
      ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
          _createElementVNode("section", _hoisted_6, [
            _createElementVNode("div", null, [
              _createElementVNode("h2", null, _toDisplayString(selected.value.name), 1),
              _createElementVNode("p", null, _toDisplayString(selected.value.site_name) + " · 最近 " + _toDisplayString(selected.value.last_run?_unref(formatDateTime)(selected.value.last_run.started_at):'尚未运行') + " · 下次 " + _toDisplayString(selected.value.next_run_at?_unref(formatDateTime)(selected.value.next_run_at):'暂无计划'), 1)
            ]),
            _createElementVNode("div", null, [
              _createVNode(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-radar",
                onClick: _cache[2] || (_cache[2] = $event => (topAction('run_selection','立即选种','将立即访问站点并可能添加符合条件的下载，确认继续吗？','选种任务已提交')))
              }, {
                default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                  _createTextVNode("立即选种", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VBtn, {
                variant: "tonal",
                "prepend-icon": "mdi-progress-check",
                onClick: _cache[3] || (_cache[3] = $event => (topAction('run_check','检查种子','将立即检查下载、上传和删种候选，确认继续吗？','种子检查已提交')))
              }, {
                default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                  _createTextVNode("检查种子", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VBtn, {
                variant: "text",
                "prepend-icon": "mdi-pencil",
                onClick: editTask
              }, {
                default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
                  _createTextVNode("编辑任务", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VBtn, {
                variant: "text",
                "prepend-icon": selected.value.enabled?'mdi-pause':'mdi-play',
                onClick: _cache[4] || (_cache[4] = $event => (topAction(selected.value.enabled?'pause_task':'resume_task',selected.value.enabled?'暂停任务':'恢复任务',selected.value.enabled?'暂停后将停止自动选种和检查，确认吗？':'恢复后将重新注册自动调度，确认吗？',selected.value.enabled?'任务已暂停':'任务已恢复')))
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(selected.value.enabled?'暂停':'恢复'), 1)
                ]),
                _: 1
              }, 8, ["prepend-icon"])
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
          _createVNode(_component_VTabs, {
            modelValue: tab.value,
            "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((tab).value = $event)),
            color: "primary"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VTab, { value: "status" }, {
                default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                  _createTextVNode("状态", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VTab, { value: "torrents" }, {
                default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                  _createTextVNode("种子", -1)
                ]))]),
                _: 1
              }),
              _createVNode(_component_VTab, { value: "history" }, {
                default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
                  _createTextVNode("记录", -1)
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
            touch: false
          }, {
            default: _withCtx(() => [
              _createVNode(_component_VWindowItem, { value: "status" }, {
                default: _withCtx(() => [
                  _createElementVNode("section", {
                    class: _normalizeClass(["bf9__conclusion", `tone-${summary.value.health?.level||'info'}`])
                  }, [
                    _createVNode(_component_VIcon, {
                      icon: summary.value.health?.level==='success'?'mdi-check-circle':summary.value.health?.level==='error'?'mdi-alert-circle':'mdi-information',
                      size: "36"
                    }, null, 8, ["icon"]),
                    _createElementVNode("div", null, [
                      _cache[37] || (_cache[37] = _createElementVNode("span", null, "当前结论", -1)),
                      _createElementVNode("h2", null, _toDisplayString(summary.value.health?.title||'等待首次检查'), 1),
                      _createElementVNode("p", null, _toDisplayString(summary.value.health?.message||'插件完成第一次检查后会告诉你下一步。'), 1)
                    ])
                  ], 2),
                  (summary.value.recommended_actions?.length)
                    ? (_openBlock(), _createElementBlock("section", _hoisted_7, [
                        _cache[38] || (_cache[38] = _createElementVNode("div", null, [
                          _createElementVNode("h3", null, "需要处理"),
                          _createElementVNode("p", null, "这些操作都会先说明影响，再由你确认。")
                        ], -1)),
                        _createElementVNode("div", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(summary.value.recommended_actions, (action) => {
                            return (_openBlock(), _createBlock(_component_VBtn, {
                              key: action.code,
                              color: action.tone||'primary',
                              variant: "tonal",
                              onClick: $event => (askAction(action))
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(action.label), 1)
                              ]),
                              _: 2
                            }, 1032, ["color", "onClick"]))
                          }), 128))
                        ])
                      ]))
                    : _createCommentVNode("", true),
                  _createElementVNode("section", _hoisted_8, [
                    _createElementVNode("header", null, [
                      _createElementVNode("div", null, [
                        _cache[39] || (_cache[39] = _createElementVNode("h3", null, "容量", -1)),
                        _createElementVNode("p", null, _toDisplayString(_unref(formatBytes)(summary.value.capacity?.current_bytes||selected.value.seeding_size)) + " / " + _toDisplayString(summary.value.capacity?.limit_bytes?_unref(formatBytes)(summary.value.capacity.limit_bytes):'未设置上限'), 1)
                      ]),
                      _createElementVNode("strong", null, _toDisplayString(summary.value.capacity?.percent??0) + "%", 1)
                    ]),
                    _createElementVNode("div", _hoisted_9, [
                      _createElementVNode("i", {
                        class: "target",
                        style: _normalizeStyle({left:`${strategy.value.capacity_target_percent||85}%`})
                      }, null, 4),
                      _createElementVNode("i", {
                        class: "trigger",
                        style: _normalizeStyle({left:`${strategy.value.capacity_trigger_percent||90}%`})
                      }, null, 4),
                      _createElementVNode("span", {
                        style: _normalizeStyle({width:`${Math.min(summary.value.capacity?.percent||0,100)}%`})
                      }, null, 4)
                    ]),
                    _createElementVNode("div", _hoisted_10, [
                      _createElementVNode("span", null, "目标 " + _toDisplayString(strategy.value.capacity_target_percent||85) + "%", 1),
                      _createElementVNode("span", null, "开始清理 " + _toDisplayString(strategy.value.capacity_trigger_percent||90) + "%", 1),
                      _cache[40] || (_cache[40] = _createElementVNode("span", null, "上限 100%", -1))
                    ])
                  ]),
                  _createElementVNode("div", _hoisted_11, [
                    _createElementVNode("article", _hoisted_12, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-radar",
                        color: "primary"
                      }),
                      _cache[41] || (_cache[41] = _createElementVNode("h3", null, "选种", -1)),
                      _createElementVNode("strong", null, "新增 " + _toDisplayString(summary.value.selection?.added_count||0) + " 个", 1),
                      _createElementVNode("p", null, "本轮看到 " + _toDisplayString(summary.value.selection?.candidate_count||0) + " 个，过滤 " + _toDisplayString(summary.value.selection?.filtered_count||0) + " 个。", 1),
                      (summary.value.selection?.main_reason)
                        ? (_openBlock(), _createElementBlock("small", _hoisted_13, "主要原因：" + _toDisplayString(summary.value.selection.main_reason), 1))
                        : _createCommentVNode("", true)
                    ]),
                    _createElementVNode("article", _hoisted_14, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-shield-check",
                        color: "warning"
                      }),
                      _cache[42] || (_cache[42] = _createElementVNode("h3", null, "安全删种", -1)),
                      _createElementVNode("strong", null, _toDisplayString(summary.value.deletion?.candidate_count||0) + " 个候选", 1),
                      _createElementVNode("p", null, _toDisplayString(summary.value.deletion?.message||'暂无删种计划。'), 1),
                      _createElementVNode("small", null, "保护 " + _toDisplayString(summary.value.deletion?.protected_count||0) + " 个 / " + _toDisplayString(_unref(formatBytes)(summary.value.deletion?.protected_bytes||0)), 1)
                    ]),
                    _createElementVNode("article", _hoisted_15, [
                      _createVNode(_component_VIcon, {
                        icon: "mdi-download-circle",
                        color: summary.value.download?.state==='healthy'?'success':'warning'
                      }, null, 8, ["color"]),
                      _cache[43] || (_cache[43] = _createElementVNode("h3", null, "下载健康", -1)),
                      _createElementVNode("strong", null, _toDisplayString(summary.value.download?.state==='healthy'?'正常':'需要关注'), 1),
                      _createElementVNode("p", null, "卡住 " + _toDisplayString(summary.value.download?.stalled_count||0) + " · 低速 " + _toDisplayString(summary.value.download?.slow_count||0) + " · 排队 " + _toDisplayString(summary.value.download?.queued_count||0) + " · 报错 " + _toDisplayString(summary.value.download?.error_count||0), 1),
                      _cache[44] || (_cache[44] = _createElementVNode("small", null, "未完成数据绝不自动删除", -1))
                    ])
                  ]),
                  _createVNode(_component_VExpansionPanels, { class: "mt-4" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VExpansionPanel, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_VExpansionPanelTitle, null, {
                            default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                              _createTextVNode("策略详情（专业信息）", -1)
                            ]))]),
                            _: 1
                          }),
                          _createVNode(_component_VExpansionPanelText, null, {
                            default: _withCtx(() => [
                              _createElementVNode("div", _hoisted_16, [
                                _createElementVNode("div", null, [
                                  _cache[46] || (_cache[46] = _createElementVNode("span", null, "策略预设", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(_unref(profileLabel)(task.value?.strategy?.profile)), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[47] || (_cache[47] = _createElementVNode("span", null, "安全观察（影子期）", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(strategy.value.mode_label||'未启用'), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[48] || (_cache[48] = _createElementVNode("span", null, "学习置信度", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(Math.round((strategy.value.learning_confidence||0)*100)) + "%", 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[49] || (_cache[49] = _createElementVNode("span", null, "有效样本", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(strategy.value.learning_sample_count||0), 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[50] || (_cache[50] = _createElementVNode("span", null, "误判率", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(((strategy.value.false_positive_rate||0)*100).toFixed(1)) + "%", 1)
                                ]),
                                _createElementVNode("div", null, [
                                  _cache[51] || (_cache[51] = _createElementVNode("span", null, "单位容量收益", -1)),
                                  _createElementVNode("strong", null, _toDisplayString(((strategy.value.unit_capacity_yield_per_day||0)*100).toFixed(3)) + "%/天", 1)
                                ])
                              ])
                            ]),
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
              }),
              _createVNode(_component_VWindowItem, { value: "torrents" }, {
                default: _withCtx(() => [
                  _createElementVNode("section", _hoisted_17, [
                    _createElementVNode("header", _hoisted_18, [
                      _createElementVNode("div", null, [
                        _cache[52] || (_cache[52] = _createElementVNode("h3", null, "托管种子", -1)),
                        _createElementVNode("p", null, "共 " + _toDisplayString(torrents.value.total) + " 个", 1)
                      ]),
                      _createVNode(_component_VBtnToggle, {
                        "model-value": torrentState.value,
                        mandatory: "",
                        density: "compact",
                        "onUpdate:modelValue": changeTorrentState
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VBtn, { value: "active" }, {
                            default: _withCtx(() => [...(_cache[53] || (_cache[53] = [
                              _createTextVNode("活跃", -1)
                            ]))]),
                            _: 1
                          }),
                          _createVNode(_component_VBtn, { value: "deleted" }, {
                            default: _withCtx(() => [...(_cache[54] || (_cache[54] = [
                              _createTextVNode("已删除", -1)
                            ]))]),
                            _: 1
                          }),
                          _createVNode(_component_VBtn, { value: "all" }, {
                            default: _withCtx(() => [...(_cache[55] || (_cache[55] = [
                              _createTextVNode("全部", -1)
                            ]))]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }, 8, ["model-value"])
                    ]),
                    _createElementVNode("div", _hoisted_19, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(torrents.value.items, (item) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: item.hash||item.title
                        }, [
                          _createElementVNode("div", null, [
                            _createElementVNode("strong", null, _toDisplayString(item.title||item.hash), 1),
                            _createElementVNode("span", null, _toDisplayString(item.download_health_label|| (item.deleted?'已删除':'正常')), 1)
                          ]),
                          _createElementVNode("span", null, _toDisplayString(_unref(formatBytes)(item.size||item.total_size)), 1),
                          _createElementVNode("span", null, "上传 " + _toDisplayString(_unref(formatBytes)(item.uploaded)), 1),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(Number(item.ratio||0).toFixed(2)), 1)
                            ]),
                            _: 2
                          }, 1024)
                        ]))
                      }), 128)),
                      (!torrents.value.items?.length)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_20, "暂无种子"))
                        : _createCommentVNode("", true)
                    ]),
                    (torrents.value.total>torrents.value.page_size)
                      ? (_openBlock(), _createBlock(_component_VPagination, {
                          key: 0,
                          "model-value": page.value,
                          length: Math.ceil(torrents.value.total/torrents.value.page_size),
                          "onUpdate:modelValue": changePage
                        }, null, 8, ["model-value", "length"]))
                      : _createCommentVNode("", true)
                  ])
                ]),
                _: 1
              }),
              _createVNode(_component_VWindowItem, { value: "history" }, {
                default: _withCtx(() => [
                  _createElementVNode("section", _hoisted_21, [
                    _cache[56] || (_cache[56] = _createElementVNode("h3", null, "最近运行", -1)),
                    _createElementVNode("div", _hoisted_22, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(runs.value, (run) => {
                        return (_openBlock(), _createElementBlock("article", {
                          key: run.id
                        }, [
                          _createVNode(_component_VIcon, {
                            icon: run.success===false?'mdi-alert-circle':'mdi-check-circle',
                            color: run.success===false?'error':'success'
                          }, null, 8, ["icon", "color"]),
                          _createElementVNode("div", null, [
                            _createElementVNode("strong", null, _toDisplayString(run.kind==='brush'?'选种刷新':'种子检查'), 1),
                            _createElementVNode("span", null, _toDisplayString(_unref(formatDateTime)(run.started_at)) + " · " + _toDisplayString(run.kind==='brush'?`新增 ${run.added_count||0}，过滤 ${run.filtered_count||0}`:`活跃 ${run.active_count||0}，删除 ${run.deleted_count||0}`), 1),
                            (run.error)
                              ? (_openBlock(), _createElementBlock("small", _hoisted_23, _toDisplayString(run.error), 1))
                              : _createCommentVNode("", true)
                          ])
                        ]))
                      }), 128)),
                      (!runs.value.length)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_24, "暂无运行记录"))
                        : _createCommentVNode("", true)
                    ])
                  ])
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ], 64))
      : _createCommentVNode("", true),
    _createVNode(TaskWizardV9, {
      modelValue: wizard.value,
      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((wizard).value = $event)),
      task: wizardTask.value,
      sites: status.value.options.sites,
      downloaders: status.value.options.downloaders,
      saving: saving.value,
      onSave: saveTask
    }, null, 8, ["modelValue", "task", "sites", "downloaders", "saving"]),
    _createVNode(_component_VDialog, {
      modelValue: settingsOpen.value,
      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((settingsOpen).value = $event)),
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
                _cache[57] || (_cache[57] = _createTextVNode("工具与设置", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, { class: "bf9__settings" }, {
              default: _withCtx(() => [
                _createElementVNode("section", null, [
                  _cache[58] || (_cache[58] = _createElementVNode("h3", null, "插件运行", -1)),
                  _cache[59] || (_cache[59] = _createElementVNode("p", null, "这里只管理插件总开关和全局硬上限；每个任务仍独立管理自己的容量。", -1)),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.enabled,
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((settingsDraft.value.enabled) = $event)),
                    label: "启用站点刷流",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.show_sidebar_nav,
                    "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((settingsDraft.value.show_sidebar_nav) = $event)),
                    label: "显示侧边栏入口",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createElementVNode("div", _hoisted_25, [
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_disksize,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((settingsDraft.value.global_disksize) = $event)),
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
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((settingsDraft.value.global_maxdlcount) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "全局下载并发硬上限",
                      clearable: ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_maxupspeed,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((settingsDraft.value.global_maxupspeed) = $event)),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "全局上传限速（KB/s）",
                      clearable: ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settingsDraft.value.global_maxdlspeed,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((settingsDraft.value.global_maxdlspeed) = $event)),
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
                  _createElementVNode("div", _hoisted_26, [
                    _cache[61] || (_cache[61] = _createElementVNode("div", null, [
                      _createElementVNode("h3", null, "站点签到"),
                      _createElementVNode("p", null, "签到是独立工具，不参与选种、下载健康或删种决策。")
                    ], -1)),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      "prepend-icon": "mdi-login",
                      loading: saving.value,
                      onClick: runSignin
                    }, {
                      default: _withCtx(() => [...(_cache[60] || (_cache[60] = [
                        _createTextVNode("立即签到", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.signin_enabled,
                    "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((settingsDraft.value.signin_enabled) = $event)),
                    label: "启用自动签到",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSwitch, {
                    modelValue: settingsDraft.value.signin_notify,
                    "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((settingsDraft.value.signin_notify) = $event)),
                    label: "发送签到结果通知",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VTextField, {
                    modelValue: settingsDraft.value.signin_cron,
                    "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((settingsDraft.value.signin_cron) = $event)),
                    label: "签到 CRON",
                    hint: "默认每天 07:17：17 7 * * *",
                    "persistent-hint": ""
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_VSelect, {
                    modelValue: settingsDraft.value.signin_sites,
                    "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((settingsDraft.value.signin_sites) = $event)),
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
                  onClick: _cache[19] || (_cache[19] = $event => (settingsOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[62] || (_cache[62] = [
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
                  default: _withCtx(() => [...(_cache[63] || (_cache[63] = [
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
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: confirmOpen.value,
      "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((confirmOpen).value = $event)),
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
                  onClick: _cache[21] || (_cache[21] = $event => (confirmOpen.value=false))
                }, {
                  default: _withCtx(() => [...(_cache[64] || (_cache[64] = [
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
                  default: _withCtx(() => [...(_cache[65] || (_cache[65] = [
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
const BrushFlowV9 = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cc8c6a1d"]]);

export { BrushFlowV9 as B };

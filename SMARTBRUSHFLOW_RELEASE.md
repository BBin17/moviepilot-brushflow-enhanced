# 智能刷流发布与安装记录

## 固定身份

当前发布版本：`1.3.1`（2026-10-14）

- 插件 ID：`SmartBrushFlow`
- 展示名：智能刷流
- 源码目录：`plugins.v3/smartbrushflow/`
- 版本唯一来源：`plugins.v3/smartbrushflow/version.py`
- 市场索引：根目录 `package.v3.json`
- API 前缀：`/api/v1/plugin/SmartBrushFlow`
- qB 标签前缀：`智能刷流-`
- 侧栏分组：`discovery`，位置为“发现 → 推荐 → 探索 → 智能刷流”；权限仍为`manage`。1.2.1只调整入口，不重新开始已有观察期。
- GitHub：`https://github.com/BBin17/moviepilot-brushflow-enhanced`

## 发布检查

```bash
python3 scripts/check_smartbrushflow_release.py
node scripts/check_smartbrushflow_frontend_defaults.mjs
python3 -m compileall -q plugins.v3/smartbrushflow
uv run pytest -q
uv run ruff check plugins.v3/smartbrushflow tests/v3/smartbrushflow
pnpm --dir plugins.v3/smartbrushflow build
git diff --check
```

发布时只提交智能刷流本次变更和构建产物，不要把工作区中的 `1lou*`、`qb-rules/` 或旧版 BrushFlow 的未完成修改一起提交。

## 必须发布安装用的 Release 资产

市场清单中的 `release: true` 表示安装依赖 GitHub Release，单独推送代码会出现“有更新”和更新说明，但版本历史没有可安装按钮。已核对1.1.5使用下列两种标签，同一压缩包同时附到两者：

- `SmartBrushFlow_v1.2.0`：插件级版本历史识别的标签。
- `v1.2.0`：仓库 Latest Release 使用的兼容标签。
- 资产名：`smartbrushflow_v1.2.0.zip`；压缩包根目录必须是 `smartbrushflow/`，包含 `__init__.py`、`host.py`、所有相对导入模块和 `dist/assets/remoteEntry.js`。

源码和生产构建提交、推送后，使用同一个已验证提交打包、创建两个 Release。示例中的版本号每次与 `version.py` 保持一致：

```bash
sbf_release_dir=$(mktemp -d /tmp/smartbrushflow-release.XXXXXX)
git archive --format=zip --prefix=smartbrushflow/ --output="$sbf_release_dir/smartbrushflow_v1.2.0.zip" HEAD:plugins.v3/smartbrushflow
unzip -l "$sbf_release_dir/smartbrushflow_v1.2.0.zip"
gh release create SmartBrushFlow_v1.2.0 "$sbf_release_dir/smartbrushflow_v1.2.0.zip" --target "$(git rev-parse HEAD)" --title "SmartBrushFlow 1.2.0" --notes-file <本次发行说明文件> --latest=false
gh release create v1.2.0 "$sbf_release_dir/smartbrushflow_v1.2.0.zip" --target "$(git rev-parse HEAD)" --title "SmartBrushFlow 1.2.0" --notes-file <同一发行说明文件> --latest
```

`git archive`只包含已提交文件，避免将 node_modules、Python缓存或NAS凭据混入发行包。必须核对所有新增的Python模块和前端组件构建产物都已提交。

`gh release create --target`使用`git rev-parse HEAD`返回的完整提交SHA，不要用缩写SHA（GitHub可能拒绝，报`target_commitish is invalid`）。

## MoviePilot 安装流程

当前 MoviePilot 地址：`http://192.168.8.10:13000`。

1. 将本次源码、测试、清单和前端 `dist/` 一起提交，正常推送到仓库 `main`，并按上节创建两个Release及zip资产。仅更新已安装的 `SmartBrushFlow`。
2. 在 MoviePilot 的插件市场点击同步源，再到“我的插件”找到“智能刷流”。
3. 从卡片菜单选择“更新”，在版本历史中点击“更新到最新版本”，核对卡片为 `1.2.0` 且运行中。
4. 整页刷新并从侧栏进入“智能刷流”；浏览器持有旧远程组件时，后台更新后也必须刷新页面。
5. 核对憨憨、馒头、咖啡的容量、最低保种、促销、大小范围、目录和种子数量。首次升级到1.2会保存 `v1_2_policy_backups` 并为已启用自动删种的任务重新观察48小时；重复重载不会重置倒计时。
6. 查看上传收益面板、种子表的实际保种时长、24h零上传筛选与下载超时提示；切换任务时核对详情对应正确站点。

“接管历史种子”已移除，不属于更新步骤。常规更新使用卡片“更新”，保留原任务与本地学习历史。

如果安装后版本回退，先查看 MoviePilot 的插件日志。最先检查的是 V3 SDK 导入、`package.v3.json` 版本、GitHub Release 资产中的插件目录和 `remoteEntry.js`，不要重复点击安装或重置旧插件。

## 1.2.0 实机验收（2026-10-13）

- 通过上述市场流程更新完成；“我的插件”显示智能刷流 `v1.2.0`、运行中，整页刷新后新前端正常加载。
- 憨憨、馒头、咖啡三个任务保留，容量上限分别为800、800、200GB；全部显示新的48小时安全观察倒计时。
- 馒头仍使用原目录 `/media/刷流/馒头`、最低保种72小时、自定义95%触发/90%目标；咖啡仍使用原目录 `/media/刷流/咖啡`、最低保种72小时、自定义95%触发/90%目标。查看向导后取消，未保存任何配置修改。
- 憨憨实测65个完成种子，其中61个已达到原48小时最低保种，过去24小时零上传，占约672GB；210GB的大种实际保种440.3小时。零上传筛选按体积降序正确返回，保种时间来自下载器而非加入时间。
- 新安全检查记录显示实际删除0；原“Tracker重复需求”保护已转为“低价值尚未连续确认”，仍保留连续确认和观察期安全门槛。本次未手动清理或提前启用删种。
- 馒头新24小时累计增量显示约3.0GB；旧界面约0.6GB的显示口径问题已经修复。收益仍取决于真实下载需求和连通性，不能以升级代替收益验证。
- 发布前通过170个后端测试、前端异步请求竞态测试、生产构建、ruff和版本一致性检查。

## 1.2.1 侧栏调整

- 只将`get_sidebar_nav()`中的`section`由`organize`改为`discovery`，保留`main`路由、`manage`权限和显示开关。
- MoviePilot宿主将插件入口追加在分组内置菜单之后，因此发现组中显示“推荐 → 探索 → 智能刷流”。依据：[官方侧栏注册说明](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/faq/17-register-plugin-sidebar-nav.md)、[宿主导航合并实现](https://github.com/jxxghp/MoviePilot-Frontend/blob/v3/src/layouts/default/components/DefaultLayout.vue)。不要用DOM脚本移动宿主菜单。
- 添加侧栏注册与启用/隐藏状态测试，171个后端测试及前端生产构建通过。更新不会改变原有收益策略或观察倒计时。
- 已通过MoviePilot市场更新到1.2.1，整页刷新后实机确认入口位于“发现 → 推荐 → 探索 → 智能刷流”，原“整理”分组不再出现重复入口。

## 1.2.2 空间恢复优化

- 完整24小时零上传、已通过所有硬保护及连续确认的候选，优先覆盖容量欠额，再优先减少超量释放；窗口不完整仍使用原评分档位。单轮与滚动24小时数量/容量限额不改变。
- `ui_summary.deletion.quota`从当前删除账本实时计算剩余额度和最早可用时间；未确认请求继续占额度，失败/跳过/过期记录不占额度。恢复时间为估算，候选及安全线变化会影响最终执行。
- 超过单轮容量上限的大种明确提示“等待不会解决”；首页的“预览空间恢复清理”复用已有名单冻结、确认、最终复核及审计流程，不提交直接删除。
- 保留三个任务配置、发现分组入口及已有观察状态；未手动执行清理或放宽NAS上的限额。
- 发布前186个后端测试、前端竞态/默认值测试、生产构建、编译及ruff通过。GitHub两个Release均附带含`recovery.py`及新远程组件的完整zip，MoviePilot已更新1.2.2并整页刷新。
- 实机额度显示：憨憨欠23.2GB、剩余0/6个数量名额，最早估算10/15 10:01恢复；馒头欠12.2GB、剩余0/2；咖啡欠6.0GB、剩余0/1。全部按滚动24小时计算，不是午夜清零。
- 实机“预览空间恢复清理”正确返回1个24.1GB的合格种子，足以覆盖憨憨23.2GB欠额；仅生成预览后取消，未点击“确认名单并继续”，没有发起实际清理。

## 1.3.0 表现驱动留种与UI重做

- 用户明确要求不再用容量停止线、每日或每轮释放GB额度留种，长期零上传无保留必要，但必须满足站点最低保种。
- `policy_for_document`固定使用表现驱动模式，忽略旧释放额度；容量仅限制新增总大小，不再等待85%回落。旧规则保存到不可覆盖的`v1_3_task_config_backups`，保留任务开关、最低保种、目录、过滤、删除数据选择和已有观察状态。
- 默认完整连续72小时零上传、实际做种也达到72小时，且最低保种/其他硬保护/连续确认全部通过才主动淘汰。观测断档、计数重置或缺失安全数据不会被误判为闲置。
- 近期仍有收益的种子按真实1/6/24小时单位容量收益和本地学习评分；自动逐个复核、先写审计，每次检查5个I/O批次，后续检查继续，无滚动每日数量限额或释放GB目标。手动名单最多10个，无25%容量门槛。
- 概览重做为上传表现、待淘汰、受保护及原因，下方只显示空间硬上限、选种和下载状态。配置向导移除容量触发/停止线及GB释放限额。

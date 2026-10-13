# 智能刷流发布与安装记录

## 固定身份

当前发布版本：`1.2.0`（2026-10-13）

- 插件 ID：`SmartBrushFlow`
- 展示名：智能刷流
- 源码目录：`plugins.v3/smartbrushflow/`
- 版本唯一来源：`plugins.v3/smartbrushflow/version.py`
- 市场索引：根目录 `package.v3.json`
- API 前缀：`/api/v1/plugin/SmartBrushFlow`
- qB 标签前缀：`智能刷流-`
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

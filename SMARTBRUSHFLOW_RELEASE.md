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

## MoviePilot 安装流程

当前 MoviePilot 地址：`http://192.168.8.10:13000`。

1. 将本次源码、测试、清单和前端 `dist/` 一起提交，正常推送到仓库 `main`。仅更新已安装的 `SmartBrushFlow`。
2. 在 MoviePilot 的插件市场点击同步源，再到“我的插件”找到“智能刷流”。
3. 从卡片菜单选择“更新”，在版本历史中点击“更新到最新版本”，核对卡片为 `1.2.0` 且运行中。
4. 整页刷新并从侧栏进入“智能刷流”；浏览器持有旧远程组件时，后台更新后也必须刷新页面。
5. 核对憨憨、馒头、咖啡的容量、最低保种、促销、大小范围、目录和种子数量。首次升级到1.2会保存 `v1_2_policy_backups` 并为已启用自动删种的任务重新观察48小时；重复重载不会重置倒计时。
6. 查看上传收益面板、种子表的实际保种时长、24h零上传筛选与下载超时提示；切换任务时核对详情对应正确站点。

“接管历史种子”已移除，不属于更新步骤。常规更新使用卡片“更新”，保留原任务与本地学习历史。

如果安装后版本回退，先查看 MoviePilot 的插件日志。最先检查的是 V3 SDK 导入、`package.v3.json` 版本、GitHub Release 资产中的插件目录和 `remoteEntry.js`，不要重复点击安装或重置旧插件。

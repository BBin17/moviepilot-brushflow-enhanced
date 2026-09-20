# 智能刷流发布与安装记录

## 固定身份

当前发布版本：`1.1.1`

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
pnpm --dir plugins.v3/smartbrushflow build
git diff --check
```

发布时只提交智能刷流本次变更和构建产物，不要把工作区中的 `1lou*`、`qb-rules/` 或旧版 BrushFlow 的未完成修改一起提交。

## MoviePilot 安装流程

1. 在 MoviePilot 的插件市场同步自定义仓库。
2. 在“我的插件”找到“智能刷流”，确认版本为 `1.1.1`。
3. 点击安装；安装后刷新整页，再从侧栏进入“智能刷流”。
4. 打开任务后点击“接管历史种子”；它只按旧版 `刷流-*` 标签纳管现有 qB 种子，并补回当前 `智能刷流-站点` 管理标签，不新增下载、不删除任务或数据。
5. 核对旧“站点刷流”仍在、旧任务数量不变，再继续新建智能刷流任务。

如果安装后版本回退，先查看 MoviePilot 的插件日志。最先检查的是 V3 SDK 导入、`package.v3.json` 版本、GitHub Release 资产中的插件目录和 `remoteEntry.js`，不要重复点击安装或重置旧插件。

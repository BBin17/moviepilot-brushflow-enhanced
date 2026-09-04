# BrushFlow 发布与 MoviePilot 更新操作手册

最后实机验证：2026-09-04，MoviePilot 已从 8.0.2 更新到 8.1.0，三个刷流任务及其历史配置保留并继续运行。

## 唯一发布源

- GitHub 仓库：`https://github.com/BBin17/moviepilot-brushflow-enhanced.git`
- 分支：`main`
- 插件 ID：`BrushFlow`
- 版本必须同时一致：`plugins.v3/brushflow/version.py`、`plugins.v3/brushflow/package.json`、根目录 `package.v3.json`。

不要从旧的重复源码目录发布，也不要只改仓库总清单的版本号；MoviePilot 实际展示的是插件包内部版本。

## 每次发布

在仓库根目录执行：

```bash
node scripts/check_brushflow_frontend_defaults.mjs
python3 scripts/check_brushflow_release.py
npm run build
git status --short
git add <本次改动的文件>
git commit -m "<说明>"
git push origin main
```

只暂存本次改动；工作区中的其他未跟踪文件不属于插件发布内容。推送成功后，在 GitHub 确认 `main` 已包含新提交和新版本号。

## 更新 MoviePilot 中已安装的插件

MoviePilot 地址：`http://192.168.100.10:13000`。

1. 进入 **插件** → **插件市场**，点击右上角的圆形刷新按钮，同步自定义 GitHub 插件源。
2. 回到 **我的插件**。BrushFlow 卡片显示“有更新”后，点击卡片右上角 `···` → **更新**。
3. 在“版本历史”窗口点击 **更新到最新版本**。
4. 等待卡片从“正在更新”恢复为“运行中”，并确认版本号已变为目标版本。
5. 进入 **站点刷流**，确认任务列表、任务数量和策略概览仍在；不需要重新创建任务。

本次 8.1.0 的核验结果：咖啡、馒头刷流、憨憨均为运行中；咖啡任务显示引擎 8.1.0、超额恢复运行中、既有学习数据与安全保护均保留。

## 卡住或版本不显示时

- 插件市场的“同步源”超过约 60 秒仍在转：先刷新 MoviePilot 页面，再回到“我的插件”检查。此次实测页面请求持续转圈，但刷新后卡片已出现“有更新”，说明不要在转圈时反复点击。
- 没有“有更新”：先确认 GitHub `main` 已推送，并用 `python3 scripts/check_brushflow_release.py` 检查三个版本文件是否一致；再检查 MoviePilot 的自定义插件源和 NAS 到 GitHub 的网络连通性。
- 更新成功、日志显示已重新加载，但卡片仍是旧版本：刷新页面；仍不变时才在绿联 Docker 项目 `moviepilot-v3` 中重启 MoviePilot 容器，然后重新核对版本。qB 与下载数据不受此操作影响，但 MP 会短暂不可用。
- 不要用“重置”或“卸载”代替更新；它们不是版本刷新步骤，可能影响现有插件配置或服务状态。

## 更新完成的最低核验

- 插件卡片：`运行中`，版本号为本次目标版本，且不再显示“有更新”。
- 站点刷流：原任务仍在，运行状态正常。
- 对涉及删种逻辑的版本：查看“策略概览”的引擎版本、容量闭环、影子状态和最近决策解释；确认没有绕过 H&R、最低保种、真实上传和活动连接保护。

# MoviePilot 刷流插件

MoviePilot V3 的多站点刷流插件。9.0 系列重构为单一嵌套任务模型、统一收益决策链和健康优先交互界面。

固定发布、MoviePilot 更新和实机核验步骤见 [更新操作手册](BRUSHFLOW_UPDATE_RUNBOOK.md)。旧版插件的详细行为与 API 见 [站点刷流说明](plugins.v3/brushflow/README.md)，新插件的说明见 [智能刷流说明](plugins.v3/smartbrushflow/README.md)。

## 独立插件：智能刷流 1.1.0

`SmartBrushFlow` 是全新的 MoviePilot V3 插件 ID，目录、配置前缀、API、前端联邦入口、任务数据和 qB 标签都与旧版 `BrushFlow` 分开。两者可以同时安装；安装智能刷流不会迁移、覆盖或删除咖啡、馒头、憨憨等旧任务。

从 1.0.0 开始，新插件按 V3 SDK 合同维护：主类位于 `plugins.v3/smartbrushflow/__init__.py`，市场索引位于 `package.v3.json` 的 `SmartBrushFlow` 条目，版本检查使用 `scripts/check_smartbrushflow_release.py`。

## 9.1 / 1.1 重点

- 响应式任务健康卡、白话结论、推荐操作和四步配置向导。
- 本地 30 天收益学习；未知 Tracker 人数保持中性。
- 任务独立 90%→85% 容量闭环，全局限制只阻止新增。
- 未完成、H&R、最低保种、排除标签、真实上传、有效连接和可信需求为永久硬保护。
- 新启用删种先观察 48 小时，影子期实际删除为 0。
- 卡住或长期低速下载自动安全修复一次，持续异常后暂停并保留全部未完成数据。
- 任务种子与运行记录使用分页 API，任务更新带 revision 冲突保护。
- 手动清理必须先生成只读预览；名单、配置版本和有效期都会在执行前再次校验。
- 状态页显示当前评估的保护数量/容量，区分历史观察候选与当前可处理候选。
- 旧条件删种、动态删种、全局删种托管、模拟运行和 7.3 兼容引擎已移除。

## 升级

插件 ID 与配置前缀保持为 `BrushFlow`，可直接从当前 MoviePilot 版本升级到 9.1.0；独立插件 `SmartBrushFlow` 当前为 1.1.0。咖啡、馒头、憨憨等现有任务会自动迁移；升级前配置保存到只读迁移备份，原始种子身份、学习数据和审计继续保留。

发布仓库：[BBin17/moviepilot-brushflow-enhanced](https://github.com/BBin17/moviepilot-brushflow-enhanced)

本项目沿用上游 GPL-3.0 许可证。

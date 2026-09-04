# BrushFlow Enhanced 9.0.5

MoviePilot V3 的多站点刷流插件。9.0 系列重构为单一嵌套任务模型、统一收益决策链和健康优先交互界面。

固定发布、MoviePilot 更新和实机核验步骤见 [更新操作手册](BRUSHFLOW_UPDATE_RUNBOOK.md)，插件详细行为与 API 见 [插件说明](plugins.v3/brushflow/README.md)。

## 9.0 重点

- 响应式任务健康卡、白话结论、推荐操作和四步配置向导。
- 本地 30 天收益学习；未知 Tracker 人数保持中性。
- 任务独立 90%→85% 容量闭环，全局限制只阻止新增。
- 未完成、H&R、最低保种、排除标签、真实上传、有效连接和可信需求为永久硬保护。
- 新启用删种先观察 48 小时，影子期实际删除为 0。
- 卡住或长期低速下载自动安全修复一次，持续异常后暂停并保留全部未完成数据。
- 任务种子与运行记录使用分页 API，任务更新带 revision 冲突保护。
- 旧条件删种、动态删种、全局删种托管、模拟运行和 7.3 兼容引擎已移除。

## 升级

插件 ID 与配置前缀保持为 `BrushFlow`，可直接从当前 MoviePilot 版本升级到 9.0.5。咖啡、馒头、憨憨等现有任务会自动迁移；升级前配置保存到只读迁移备份，原始种子身份、学习数据和审计继续保留。

发布仓库：[BBin17/moviepilot-brushflow-enhanced](https://github.com/BBin17/moviepilot-brushflow-enhanced)

本项目沿用上游 GPL-3.0 许可证。

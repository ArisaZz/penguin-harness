# Evo-Harness RSI 工具包

- **Date:** 2026-10-28
- **Type:** feature
- **Scope:** `skills`
- **PR:** [Saigyouji-Yuyuko1000/penguin-harness#3](https://github.com/Saigyouji-Yuyuko1000/penguin-harness/pull/3)

[English](2026-10-28-evo-benchmark-adapters.md)

新增 Evo-Harness RSI 插件，使用现有原生委派、会话续接与 Agent State 接口。

## 细节

汇报统一使用 `baseline`／`final`、测试重复次数、版本、得分及资源字段；各方法的学习记录与 Test 重复测量统计分别保留。

训练进度统一使用编号的 `step` 标签，原算法阶段名称保留用于追溯。

插件发布包不包含开发测试文件。

- 按清单解析数据集并固定官方资源版本，提供单次训练反馈、根目录 `SKILL.md` 导出和原生 State 安装校验。

- 新增单次训练、原 Solver 会话中的负反馈反思，以及一次独立批量编译。
- 校验候选证据引用、ADD／MERGE／REVISE／SKIP 决策及字节预算内的完整 Skill 导出。
- 冻结后的任务上下文包含全部通用描述和匹配主题的完整正文。
- 默认对 baseline／final 分别完成三次完整测试，提供原生评分记录和按重复测试计算的统计。
- 完成插件依赖、目录和文档登记。

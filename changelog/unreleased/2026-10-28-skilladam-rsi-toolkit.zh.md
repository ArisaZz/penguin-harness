# SkillAdam RSI 工具包

- **Date:** 2026-10-28
- **Type:** feature
- **Scope:** `skills`
- **PR:** [#1374](https://github.com/Prism-Shadow/penguin-harness/pull/1374)

[English](2026-10-28-skilladam-rsi-toolkit.md)

在插件库中加入了 `skilladam-rsi-toolkit`。主控 Penguin 读取 Project 中选定的 Benchmark，组织连续训练，并在保留测试题上评测冻结的 Skill。

## 细节

- 添加了 S0 初始化、持续更新的问题记录、按方差调整编辑预算和候选评测的训练说明。
- 添加了计算优化器状态及生成评估中心记录的辅助脚本。
- 添加了每组训练一次、默认对每份冻结 State 测试三次的流程说明，分别汇报 Train/Test，并按各次测试均分计算平均值与样本标准差。

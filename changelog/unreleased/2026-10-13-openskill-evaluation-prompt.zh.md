# OpenSkill 正式评估推迟到技能冻结后

- **Date:** 2026-10-13
- **Type:** fix
- **Scope:** `web`
- **PR:** [#1](https://github.com/ArisaZz/penguin-harness/pull/1)

[English](2026-10-13-openskill-evaluation-prompt.md)

评估中心为 `openskill-rsi-toolkit` 生成的中英文提示词已改为：构建阶段使用独立虚拟测试，全部 Case 的技能冻结后才正式评估基线与最终 State。提示词禁止对中间候选进行正式评估，以及根据正式反馈继续修订技能；虚拟结果单独保存，不写入正式评分记录。其他 RSI 方法保留原有评估指令。

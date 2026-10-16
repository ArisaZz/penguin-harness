# Defer OpenSkill target evaluation until skills are frozen

- **Date:** 2026-10-13
- **Type:** fix
- **Scope:** `web`
- **PR:** [#1](https://github.com/ArisaZz/penguin-harness/pull/1)

[中文版](2026-10-13-openskill-evaluation-prompt.zh.md)

The Evaluation Center's English and Chinese prompts for `openskill-rsi-toolkit` were updated to use independent virtual tests during construction and evaluate the baseline and final State only after every Case's skills are frozen. The prompts prohibit intermediate target evaluations and skill revisions based on target feedback, and keep virtual results separate from the scoreboard. Other RSI methods retain their evaluation instructions.

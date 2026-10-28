# SkillAdam RSI toolkit

- **Date:** 2026-10-28
- **Type:** feature
- **Scope:** `skills`
- **PR:** [#1374](https://github.com/Prism-Shadow/penguin-harness/pull/1374)

[中文版](2026-10-28-skilladam-rsi-toolkit.zh.md)

Added `skilladam-rsi-toolkit` to the plugin library. A controller Penguin reads the selected Project Benchmarks, arranges continuous training, and evaluates frozen Skills on held-out tasks.

## Details

- Added learner instructions for S0 initialization, an evolving issue tracker, a variance-controlled edit budget, and candidate evaluation.
- Added a numerical helper for optimizer state and Evaluation Center records.
- Added a train-once protocol with three test repetitions of each frozen State by default, separate Train/Test results, and test repetition means with sample standard deviation.

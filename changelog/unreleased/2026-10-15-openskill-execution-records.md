# OpenSkill execution records and held-out evaluation

- **Date:** 2026-10-15
- **Type:** feature
- **Scope:** `skills`

[中文版](2026-10-15-openskill-execution-records.zh.md)

OpenSkill gained an append-only experiment journal, portable skill contracts and optional
held-out evaluation. It retained virtual-only construction feedback, the persistent creator,
the fixed skill plan and final-revision export before target evaluation.

## Details

- Recorded practice revisions, verification attempts, evidence hashes and termination reasons;
  rejected premature evaluation, spent budgets and mutations to frozen artifacts.
- Added resource/path checks and requirement-to-test coverage records. Skill usage records
  distinguished self-reports from a separate trace audit.
- Added optional `test_benchmark_id` and empty-reader control matrices without changing the
  shared evaluation protocol or scoreboard schema.
- Added a plugin test command and behavior tests for record recovery, isolation boundaries,
  retry ordering, packaging and complete evaluation matrices.
- Documented the v1 paper review and the remaining limits of prompt-level access restrictions.
  Existing experiment data and installed skills were left untouched.

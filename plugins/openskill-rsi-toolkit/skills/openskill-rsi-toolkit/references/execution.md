# Recorded execution

Use this reference for every new experiment. `scripts/experiment.py` records phase changes,
practice revisions and verification attempts. It checks artifacts and budgets; it does not
launch agents, provide a filesystem sandbox, prove a verifier's semantics or stop a running
process at its deadline. The controller still isolates inputs, dispatches roles and aborts
overdue work. Do not bypass a refused transition by editing the journal.

## Initialize and resume

Write a JSON configuration outside the journal, then run:

```bash
python3 "<skill_dir>/scripts/experiment.py" init "<OUT>" "<config.json>"
```

Configuration:

```json
{
  "test_agent_id": "target",
  "benchmark_id": "construction-benchmark",
  "case_ids": ["CASE-001"],
  "test_benchmark_id": null,
  "test_case_ids": [],
  "runs": 1,
  "include_baseline": true,
  "include_reader_control": false,
  "max_refinement_retries": 3,
  "max_targeted_searches": 3,
  "max_virtual_tests": 60,
  "construction_timeout_minutes": 30,
  "practice_prefixes": [],
  "runtime": {
    "construction": { "provider": "provider", "model_id": "model", "thinking_level": "medium" },
    "target": { "provider": "provider", "model_id": "model", "thinking_level": "medium" }
  }
}
```

Replace every example identity with the actual value. Also record `method`, paper URL,
pinned source revision, installed Skill version/hash, baseline State version/hash,
environment versions, isolation actually enforced, additional budgets and declared
adaptations as configuration fields. `practice_prefixes` lists this experiment's container
mount roots; the helper also rejects `/opt/openskill-skills` and OUT paths in deployable text.

With `test_benchmark_id`, use a distinct published Benchmark and declare its Case ids from
metadata only. Do not read its statements, inputs, rubric or traces during construction.
Only construction Cases reach creators and verifiers. The final evaluation plan targets
the test set; it does not additionally score the training set. Without this parameter,
the original same-task protocol remains the default. Report the split as an adaptation,
and report any known overlap; benchmark names alone do not prove a clean split.

The journal is authoritative for execution state. Each command publishes a new, atomically
written `journal/NNNNNN.json` containing the request, UTC time, previous-record hash and
resulting state. Old records are never replaced. Read it after compaction or interruption:

```bash
python3 "<skill_dir>/scripts/experiment.py" status "<OUT>"
```

Resume the recorded creator, attempts and phase; never reset counters or recreate the
experiment to continue a spent budget. A pending attempt must be inspected and completed
from its actual evidence before another begins. A missing creator cannot be replaced with
a fresh session and called the same run: preserve available artifacts and record interruption.
Do not remove a stale `.journal.lock` until its writer is known to have stopped.

These helpers create records only for new experiments. They do not convert or modify previous
`experiment.yaml` runs, installed libraries, snapshots or scores. Historical runs remain
readable as evidence under their recorded Skill version; do not initialize a journal over them.

## Record construction

Write each request as a JSON file, and issue it with:

```bash
python3 "<skill_dir>/scripts/experiment.py" event "<OUT>" "<request.json>"
```

All Case events include `case_id`. Use these actions in order:

| Action | Additional fields | When |
| --- | --- | --- |
| `start-case` | none | Before this Case's research; starts its wall clock |
| `plan` | `skills`: fixed list of 1–4 names; `creator_session_id` | After research/planning and creation of its persistent creator |
| `revision` | `creator_session_id`, `hypothesis` | After initial practice or a failure-driven revision and practice execution |
| `begin-verification` | optional existing `verifier_session_id` | Before dispatching any pytest attempt, including verifier repairs |
| `finish-verification` | `pytest_exit_code`, `verifier_session_id` | After that attempt stops, even if it failed to generate a report |
| `targeted-search` | `classification: NEEDS-DR`, sanitized `query` | Before issuing each gap search; failed requests also spend budget |
| `finish-case` | `reason` | When creator/verifier writes have stopped |

The live skills are `OUT/tasks/<case_id>/skills/<name>/`. Put each practice execution's
outputs in a new `practice/revision-N/`, starting at 0; do not edit earlier outputs. A
`revision` hashes the skills and outputs and preserves an immutable skill copy under
`revisions/revision-N/`. For subsequent revisions, `hypothesis` connects the failed assertion
and independent evidence to the intended change and expected behavior. The helper verifies
that revisions come from the same creator and follow failed verification, not target scores.

`begin-verification` reserves the attempt and spends budget before execution. Its returned
directory is `verify/attempt-N/`, starting at 1. Create it and save `suite.py`, `report.xml`,
`coverage.json`, raw logs and diagnosis there. Never overwrite a prior attempt, rerun pytest
inside an attempt, or omit an attempt because only the verifier changed. If the process fails
without reports, finish it with the actual exit code (use a nonzero runner code when no
pytest process started); its result is unscored. If the verifier failed to launch, record
the dispatch failure identifier as `verifier_session_id` and explain it in the diagnosis.

The helper invokes the existing JUnit parser, records evidence hashes and checks requirement
coverage and skill structure. Coverage is a verifier-authored list, grounded in public inputs:

```json
[
  {
    "requirement": "Numeric totals retain required precision",
    "required": true,
    "source": "public instruction section and independent computation/reference",
    "status": "covered",
    "tests": ["suite::test_precision"]
  }
]
```

Test ids are the JUnit `classname` plus `::` plus `name`, including parameter suffixes.
Unresolved requirements use `status: unverified`; keep their required flag true. A required
entry needs a source and passing, executed assertions. Missing, malformed or incomplete
coverage prevents `surrogate_pass` even when the numeric pass rate is 1. This checks the
declared mapping, not whether the verifier identified every requirement or chose correct
expected values. Independent review of the evidence remains necessary.

With the default retry limit, reserve at most three verifications and execute at most four
practice revisions. The edit after the third failure can still be exported without a fourth
verification. No best-of-N selection, extra final verification or rollback is introduced.

Termination reasons are `surrogate_pass`, `max_refinement_retries`, `time_budget`,
`context_budget`, `verifier_failure`, `environment_failure`, `contaminated`, `interrupted`
or `construction_failed`. A deployable result needs valid final skills, even after a budget
or verifier stop. A contaminated Case or a missing/invalid skill set blocks global deployment.
Do not label a timeout or unresolved requirement as success. Final and last-tested digests
remain separate, and `final_was_tested` identifies whether the virtual result applies.

## Freeze and measure

Assemble the library from the last registered revisions, including their `contract.json`
files, as `initialization.md` specifies. Finish every Case, stop all writers, then submit
`{"action": "freeze"}`. It verifies the planned contents, portable resources, historical
evidence and final hashes. Save the command's complete JSON response outside the library as
`OUT/freeze.json`; its `library` field is the manifest. Require exit code 0 and `phase: frozen`
before deployment. Content fixes must happen before the last revision is recorded and the
Case is closed; do not repair skills after freezing or substitute an older passing version.

Snapshot baseline and final State as usual. Submit `begin-evaluation` with the actual
`states` mapping, each entry holding `version` and `sha256`:

```json
{
  "action": "begin-evaluation",
  "states": {
    "baseline": { "version": 1, "sha256": "actual full State digest" },
    "final": { "version": 2, "sha256": "actual full State digest" }
  }
}
```

Follow the returned `evaluation_plan` and the unchanged `evaluation.md` for every cell. The
helper never reads the Benchmark or launches a scored run. The controller still verifies
live State digests before and after each matrix and publishes complete matrices to the
proper Benchmark's scoreboard. Construction remains closed even if evaluation fails.

Keep worker protocol results as JSON under OUT, grouped as
`[{"variant": "baseline", "benchmark_id": "...", "cells": [<worker result>, ...]}, ...]`.
Submit `finish-evaluation` with `outcome: complete` and `record: <relative JSON path>` only
after scoreboard publication. The helper checks the exact planned cells, versions and
runtime; it does not recompute scoreboard averages. On an unfinished evaluation, use
`outcome: incomplete` and a report path instead. Preserve partial evidence and report which
matrices were published, without inventing an aggregate for missing cells.

`include_reader_control` is an optional ablation, false by default. Declare its extra
`test Cases × runs` cost before construction. Prepare a separate State with the final
reader mechanism and an empty library/index, preserving baseline configuration and all
unrelated content. Snapshot it as `reader_control` and record that State in
`begin-evaluation`. Measure it only after the final library freezes. It supplements the
original baseline, never selects skills and never supplies construction feedback.

# Scores, versions and resource records

Keep a readable report and the structured output of `evaluation_results.py`. The required
records are:

| Record | OpenSkill content |
| --- | --- |
| Test comparison | Pre-training base and frozen final State, each repetition's complete-test score, `mean`, `std`, and final-minus-baseline gain |
| Accuracy | The same statistics when the Benchmark defines the metric as accuracy; otherwise keep its native score name |
| Training | Virtual-test measurements by attempt/revision, coverage, feedback action, revision hashes, final tested status and stopping reason |
| Versions | Fixed experiment version, report schema, Harness/runner/benchmark/model/toolkit versions, source pins, frozen Skill versions and State digests |
| Cost | Recorded USD per construction unit and per test Case/repetition/State, plus failed attempts and separate Train/Test/controller totals |
| Time | Start, finish and elapsed time at those same levels; agent-only duration when available; summed durations separately from actual campaign wall time |
| Tokens | Cached input, uncached input, output, total input and total tokens at the same levels, with separate Train/Test/controller totals |

## Fix the record before launch

Add these fields to the executor configuration; replace the examples with actual values:

```json
{
  "experiment_version": "<fixed campaign version>",
  "component_versions": {
    "harness": "<actual version/commit>",
    "runner": "<actual Harbor or other runner version>",
    "toolkit": "<installed package version>",
    "skill": "<installed OpenSkill version>",
    "skill_sha256": "<installed Skill digest>",
    "model_revision": null
  },
  "reporting_metric": {
    "name": "benchmark_score",
    "definition": "<public Benchmark definition of its 0..100 score>"
  }
}
```

Use the user's experiment/component versions when supplied and actually available; otherwise
resolve compatible installed versions and record them. Do not relabel an installed component
with a requested version it does not implement. A provider alias alone does not establish a
concrete model revision: keep that revision null when unavailable, with the actual provider,
model id and thinking level already fixed in `runtime`. The binding supplies Benchmark package
versions, manifest hashes and task-source commit. The report includes measured State versions
and hashes, the library digest and each exported Skill's frontmatter version and digest.

For several units, use one campaign version in their configs. Initialization generates one
stable experiment version if omitted; resuming does not regenerate it. The current structured
report schema is `openskill-results/v1`. Existing experiments are not rewritten to invent
missing provenance.

Set `reporting_metric.name` to `accuracy` only when the Benchmark's public definition supports
that label; provide the definition. Both score and accuracy use `0..100` here, and SD is in
percentage points. A graded reward is not automatically binary task accuracy. Without an
accuracy definition, `accuracy` is null and `mean`/`std` describe the native Benchmark score.
Do not read private rubrics during construction to discover a metric definition.

## Baseline and training curves

The baseline is the State saved **before construction**, not a score that must be measured
before construction. Evaluate that State and the learned State only after the global freeze.
Their results cover the same Test Cases and repetition count. Report both with sample SD
and the final-minus-baseline gain. The helper also retains repetition-wise differences;
pairing repetition indices does not imply shared random seeds or a causal significance test.

OpenSkill's construction has no official Train accuracy or target-score optimization curve.
Keep `training.benchmark_score_curve`, `accuracy` and `std` null with the explanation. Do not
enable `/api/judge`, grade saved Train answers or introduce a target score to fill these fields.
`training.units[].virtual_curve` contains actual virtual-test rates (`0..1`), acceptance and
coverage flags, attempts, revision indices and feedback actions. Failed/interrupted verifier
executions have a null rate. Preserve nonmonotonic measurements rather than taking a running
maximum. An untested final revision stays untested. These proxy records must be labeled
virtual validation, never Train accuracy. Keep one training run without across-training-run SD.

## Collect native resource evidence

Normalize one native artifact without launching or scoring anything:

```bash
python3 "<skill_dir>/scripts/resource_usage.py" normalize harbor "<trial/result.json>"
python3 "<skill_dir>/scripts/resource_usage.py" normalize penguin "<native usage-summary.json>"
```

For Harbor, `agent_result.cost_usd` is the monetary measurement. `n_input_tokens` includes
`n_cache_tokens`; `n_output_tokens` already includes thinking and response. Derive uncached
input only when total input and cached input are both present. Trial start/finish timestamps
give elapsed time; preserve `agent_execution` timing separately.

For Penguin, token records use `cache_read`, `cache_write`, `output`; exported cost summaries
use `cacheRead`, `cacheWrite`, `output`. Read tokens from the token fields, not monetary
`costParts`. Cached input + uncached input gives total input; add output once for total tokens.
Read a recorded USD cost when available. A summary marked `hasUncosted` has an unknown complete
cost. Never infer current prices, read credentials or query private configuration to fill it.

The isolated executor already saves role messages and process timestamps. Collect them with:

```bash
python3 "<skill_dir>/scripts/resource_usage.py" collect-construction "<OUT>"
```

Save the output to a new resource-ledger file in OUT. It sums only `token_usage.request` for
each invocation, including interrupted roles; it never sums cumulative `session` counters
again when the creator resumes. It reads no answer, hidden rubric or credential. It records
observed role token counts and process timing, leaving USD unknown. Reconcile recorded native
cost summaries, independent research calls and any other missing usage before declaring
Train coverage complete. This initial collection deliberately marks coverage partial.

## Resource ledger

Maintain `OUT/measurements.json` outside the frozen library. One row owns one disjoint native
invocation or aggregate of requests. A row's identity, source paths and usage ids make it
auditable. For example, a Test record after normalization is:

```json
{
  "schema_version": 1,
  "coverage": { "train": "partial", "test": "partial", "controller": "unknown" },
  "experiment_time": { "started_at": null, "finished_at": null },
  "records": [
    {
      "record_id": "test-baseline-case1-r1",
      "phase": "test",
      "case_id": "<published Case id>",
      "variant": "baseline",
      "run": 1,
      "session_id": "<exact scored trial/session id>",
      "status": "completed",
      "usage_ids": ["<native request ids or one disjoint aggregate coverage id>"],
      "artifact_paths": ["<native result or usage artifact>"],
      "format": "canonical",
      "usage": {
        "cost_usd": null,
        "started_at": null,
        "finished_at": null,
        "duration_ms": null,
        "agent_duration_ms": null,
        "tokens": { "cached_input": null, "uncached_input": null, "output": null,
                    "total_input": null, "total": null }
      }
    }
  ]
}
```

For a training row, use `phase: train` and its construction Case id; omit variant/run.
Use `phase: controller` for coordination overhead not already included in training/test
invocations. For convenience, `format: harbor` or `penguin` accepts the native JSON object
in `usage`; the normalizer selects only the required fields. Keep the original artifact.
The controller reads detailed usage alongside each worker's unchanged protocol YAML; never
add token fields to that YAML or the native scoreboard schema.

List every underlying request in `usage_ids` when an aggregate includes child calls. Choose
either the disjoint request rows or their aggregate, never both. Repeated ids are rejected.
Different record labels do not make overlapping usage independent. If only a creator Session
total exists, replace its covered operation rows with one aggregate; do not assign that full
Session total to each revision. A field measured later updates its existing record rather
than appending another charge. Preserve previous ledger versions for audit.

Keep failed/not-started/interrupted attempts with their own ids and measured consumption.
Their usage belongs in totals even though they have no score cell. A successful Test row must
match its exact Case, repetition, variant and session; do not attach another trial's usage.
Missing resource rows fall back to recorded cell cost/duration, with tokens and timestamps
unknown and coverage partial. Do not invent zero-cost or zero-token measurements.

`coverage` is `complete` only after reconciling every requested invocation, including failures;
otherwise use `partial` or `unknown`. Totals include `known_total`, `unknown_records`, coverage,
and a full `total` that is null when incomplete. A missing cost does not discard known tokens.
Per-unit training resources are shared by all skills produced in that unit: link the listed
skill ids to the shared cost record, rather than splitting it arbitrarily or counting it once
per skill. Truly isolated per-skill measurements may be recorded separately with evidence.

## Produce and publish the report

```bash
python3 "<skill_dir>/scripts/evaluation_results.py" report "<OUT>" "evaluation-matrices.json" \
  --measurements "measurements.json" --time "<UTC timestamp>" --summary "<public summary>"
```

This joins resources to `matrices[].cases[].trials`, adds construction-unit summaries and
virtual curves, and emits separate Train/Test/controller and experiment totals. It hashes
the supplied ledger for provenance. Retain each regenerated report and its ledger hash.
The `scoreboard_record` stays in the host's existing shape; detailed versions/tokens belong
in the report. Publish as `experiment-organization.md` specifies.

For a campaign, add `"measurements": "measurements.json"` to each entry of its experiment
manifest. The aggregate command checks disjoint usage across units and emits resource totals
alongside the overall scores. Attribute shared controller calls once, not once per Benchmark.
Add campaign `experiment_time.started_at` and `finished_at` from actual lifecycle timestamps.
Summed durations may exceed elapsed wall time under concurrency; the recorded campaign time
is authoritative. Keep source records, failure coverage and all measured versions in the
final report even when some cost or token fields remain unknown.

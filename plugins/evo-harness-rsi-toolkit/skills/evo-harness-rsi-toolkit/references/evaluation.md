# Run workers and collect measurements

The benchmark supplies the evaluator and defines its Train/Test splits. Use its measured scores and execution evidence throughout. The controller schedules one whole training run per benchmark or independent training unit, then three test repetitions of each frozen State by default. The Solver attempts, original-session reflections and one batch Evolver stay inside the training Target's Session and environment.

## Common report fields

Use these names in the final experiment report so results from different RSI methods can
be compared. Keep native worker protocols, journals and `scoreboard.yaml` unchanged;
translate their fields when assembling the report, retaining the original artifacts.

| Field | Meaning |
| --- | --- |
| `method` | Toolkit method id: `skilladam`, `evo-harness`, `openskill` or `trace`. |
| `experiment_version`, `component_versions` | Stable report identity and the actual Harness, runner, Benchmark, model and toolkit versions. User-specified versions take priority. |
| `benchmark_id`, `training_unit_id` | Published evaluation Benchmark id and the independent unit that produced its learned artifact. Record the paired Train package separately; Train and Test are separate measurements of one experiment. |
| `phase` | `train`, `test` or `controller` for resource attribution. |
| `variant` | `baseline` for the pre-training State, `final` for the frozen learned State. Record any requested extra control by its own name. |
| `run`, `runs` | One-based complete-test repetition index and total repetitions, normally 3. A retry, training iteration or candidate is not another test repetition. |
| `state_version`, `state_sha256` | Measured frozen State identity; distinct from the experiment version. Map native `version`/`expected_version` here. |
| `repetition_scores`, `mean`, `std` | Every complete repetition's score, their mean and sample standard deviation with denominator `runs - 1`. One repetition gives `std: null`. |
| `final_minus_baseline` | Final Test mean minus baseline Test mean, in score units. Calculate from unrounded means. |
| `case_id`, `score` | Published case id and its measured score in each test repetition. Record the metric, scale and aggregation rule; call it accuracy only when the Benchmark does. |
| `cost_usd` | Measured USD for this record; native scoreboard `cost` has this unit but its aggregate fields are averages. |
| `started_at`, `finished_at`, `duration_ms` | Actual UTC timestamps and elapsed milliseconds at the same granularity as cost. |
| `tokens` | `cached_input`, `uncached_input`, `output`, `total_input` and `total`, in tokens. |
| `curve_kind` | `benchmark_score` for measured training scores, `virtual_validation` for proxy checks, or `none` when no iterative measurements exist. |
| `step`, `native_stage` | Zero-based training record order and optional original stage label. `step` is independent of the Test repetition `run`; `native_stage` maps back to original artifacts. |

Use `baseline` and `final` in result tables, even when the method calls its learned
artifact a bank or library. `baseline` describes the State saved before learning; its
measurement may happen after learning when the method requires that order. Record its
base configuration and any fixed reader in `baseline_definition`. Do not call it
“No Skill” if a user-supplied learned Skill was already present. `final` means the
method's exported result, which may be a training-selected checkpoint rather than the
last attempted revision. Record that selection separately.

Display training progress as `Step 0`, `Step 1`, and so on, with the recorded State or
artifact version. Keep method-specific names such as `S0`, `H1` and `B0` in `native_stage`
or raw records. A step orders observed training stages; it does not imply a new accepted
State or an improvement. Preserve current/candidate scores, acceptance decisions and
regressions where the method has them. When `curve_kind` is `none`, do not invent a curve.

For each Benchmark, and for the equal-weight overall result, include a comparison with
this shape (illustrative scores):

```json
{
  "baseline": { "repetition_scores": [60, 70, 80], "mean": 70, "std": 10 },
  "final": { "repetition_scores": [75, 80, 85], "mean": 80, "std": 5 },
  "final_minus_baseline": 10
}
```

For a case, compute statistics from its own repetition scores. For a Benchmark, first
aggregate all selected cases within each repetition; for overall, first average the same
selected Benchmarks within each repetition. Only then calculate `mean` and `std`.
Keep full precision until display. These are repeated-test means, not best-of-three or
pass@3. No intermediate-Skill Test comparison is required.

Retain one resource summary per complete training unit, including all its learned files,
and one record per Test `benchmark_id × variant × case_id × run`. Keep disjoint controller
usage and failed-attempt usage, separate Train/Test totals, and actual experiment wall time.
A library with several Skills has one shared training cost, not a repeated charge per file.
Missing measurements remain `null`; label incomplete totals. Keep the method's own training
stages and diagnostics alongside these common fields, without pooling virtual rates,
training scores or optimizer variance into Test `std`.

## The launch worker

Receive the experiment root, benchmark, training unit, phase, test repetition index when testing, published case ID if applicable, native task path, resolved checkout, State archive and identity, runtime, optional install bundle and unique output path from the controller. Resolve the selected benchmark's launch instructions through [initialization.md](initialization.md).

A training worker runs one complete learning trial. A test worker runs one held-out question in one test repetition using the specified frozen State. Neither changes the experiment or launches another experiment controller.

Wait for completion using the available managed background mechanism, then return the status and exact trial/artifact paths. A launched process or an idle Agent is not by itself a completed trial. Use the native result to distinguish completion, interruption and infrastructure failure.

Follow the selected benchmark's retry rules. A diagnosed infrastructure failure before the Target starts can be repaired and retried under a new job name, retaining the failed attempt. A completed wrong answer or low score is a measurement. Interrupted learning that already used the model remains incomplete work; do not silently replace it with a fresh successful run.

## Read native results

For a scored Harbor trial, take reward from the trial's `verifier_result.rewards` using the benchmark's declared metric and scale. Convert a normalized `0..1` reward to `0..100` for reporting; preserve other metric scales as documented. Collect cost and token usage from `agent_result`, timestamps from the native execution records, and actual model usage/outcome for runtime identity. Missing grade data is incomplete; a measured zero is valid.

For training, collect the final answer grades from the benchmark's documented result artifacts. Each continuous learning trial contributes its cost and duration once. Read the per-task scores, original Solver Session IDs, negative candidates, batch decisions and frozen library from the learning records. Use the same display scale as Test while retaining the raw values. Keep online measurements distinct from the final verifier grade.

For Test, gather every requested case in each repetition for the pre-training base State and final learned State. All repetitions of a version use the same State archive and digest. Both versions use the same task set, base State, model, tools and scoring conditions; each trial begins with a fresh environment and conversation. Test feedback never revises a learned Skill. With N held-out cases and R repetitions, the two States need 2RN task trials (6N at the default of three repetitions). Training is performed once.

Reconcile the experiment index with native trial results, matching each score to the case and frozen State actually evaluated. Keep failed or superseded attempts separately, with their costs and reasons. In progress reports, show completed coverage and compare versions only on their shared completed cases.

## Record cost, time and tokens

Keep these measurements together at the following granularity:

| Record | Scope |
| --- | --- |
| Training | One record for the complete training run that produces one learned Skill, identified by benchmark/training unit and exported Skill/State version. Include the coordinator, all Solver/reflection calls and the one batch Evolver; do not count delegated usage twice. |
| Test | One record for each benchmark, frozen State, test case and repetition. Keep its score, cost, time and token usage together. |

Each record includes cost in USD, start and finish timestamps, elapsed duration and the token breakdown below. Keep the native trial/session and artifact paths so the measurements can be traced back.

| Token metric | Penguin usage |
| --- | --- |
| Cached input | `cache_read` in token records, or `cacheRead` in cost summaries: input served from cache hits. |
| Uncached input | `cache_write` or `cacheWrite`: input on a cache miss. |
| Output | `output`: thinking and response tokens combined. |
| Total input | Cached input + uncached input. |
| Total tokens | Total input + output. |

For Harbor, read `cost_usd`, `n_input_tokens`, `n_output_tokens` and `n_cache_tokens` from `agent_result` when supplied. These give cost, total input, output and cached input respectively. Derive uncached input as total input minus cached input only when both are available. Penguin's per-session usage artifact, such as `agent/penguin-cost-by-session.json`, retains the original `cacheRead`, `cacheWrite` and `output` breakdown. Cached input is already part of total input; thinking tokens are already part of output. Do not add either twice.

Use the native trial's start and finish timestamps for elapsed wall-clock duration, with the same timing boundary for Train and Test. Preserve agent-only execution time separately when available.

Sum costs and each token category into separate Train and Test totals, retaining the per-Skill and per-case records. Count each underlying request once: session/model breakdowns and parent/child summaries may describe the same usage. Keep controller and scheduling usage separate from the training and test trials, and include it once in the experiment total.

Report summed training durations and summed test durations separately from actual experiment wall-clock time; concurrent trials overlap. Keep failed-attempt usage visible in the totals. Mark missing measurements as unknown (`null` in structured output), and label any partial totals rather than treating missing usage as zero.

## Publish to the Evaluation Center

When the experiment includes published Penguin Benchmarks, use the existing `scoreboard.yaml` format used by APE and OPRO. The numerical helper's `report` command validates a complete evaluation matrix and prints the standard evaluation record itself.

A matrix identifies `benchmark_id`, `agent_id`, `version`, `state_sha256`, `runtime` (`provider`, `model_id`, `thinking_level`), `case_ids`, `runs` and `cells`. Each scored cell contains:

```json
{
  "protocol_version": 1, "status": "ok",
  "case_id": "<published case ID>", "run": 1,
  "agent_id": "<Target ID>", "expected_version": 1,
  "provider": "<provider>", "model_id": "<model ID>", "thinking_level": "<level>",
  "score": 75.0, "cost": null, "duration_ms": 1000,
  "session_id": "harbor:<unique trial name>"
}
```

Build the spec with the same benchmark, agent, runtime, case IDs and runs, plus a descriptive `label`. Use the actual measured State version, file digest and native trial identity. Then run:

```bash
python3 "$TOOLKIT/scripts/evo.py" report \
  --matrix "$MATRIX" --spec "$SPEC" --time "$UTC_TIME" \
  --step "$STEP" --summary "$SUMMARY"
```

Append the returned record under `evaluations` in that Benchmark's scoreboard and preserve existing records. Only complete matrices are published; incomplete work stays visible in the experiment index.

A combined training task may be **one published Train case** containing several questions. Map it as the selected benchmark declares, measured using the initial learner State, with `runs: 1`. Its final grade is not an independent evaluation of a frozen candidate Skill. Keep the inner batch learning record in the experiment output rather than inventing separate Harbor trial identities for its questions.

For Test, publish one matrix per benchmark/training unit and frozen version, covering every held-out case with `runs: 3` by default. Each case has cells with `run: 1`, `run: 2` and `run: 3`, all measured from the same frozen State. The pre-training baseline and final State each have a matrix. If the request changes the test repetition count, use that count in both the matrix and its spec. Keep detailed versions and token usage in the experiment report alongside these standard Evaluation Center entries.

## Finish the experiment report

Include the fixed experiment/report version and the resolved runtime, benchmark, model, toolkit and measured Skill/State versions recorded during [initialization](initialization.md). Each report must identify the actual versions used, with user-specified versions taking priority.

For each frozen State, each test repetition includes every selected test case. Apply the benchmark's aggregation rule separately to each repetition. For a benchmark scored by the mean of N test cases, with R test repetitions:

```text
repeat_score[r] = sum_q score[r, q] / N
mean = sum_r repeat_score[r] / R
sample_std = sqrt(sum_r (repeat_score[r] - mean)^2 / (R - 1))
```

Report `mean ± std`, where `std = sample_std`, and retain the R repetition scores. For example, three complete-test means of 60, 70 and 80 give `70 ± 10`. The standard deviation measures variation between complete test repetitions of the same frozen State. Calculate this standard deviation from repetition scores, not pooled case scores or an average of per-case standard deviations. Per-case summaries use that case's own R scores; preserve the individual measurements with their resource usage.

For an aggregate across benchmarks on a common scale, average the same selected benchmarks within each repetition. This gives R overall scores; apply the mean and sample-standard-deviation formulas to those scores. Do not average the benchmarks' standard deviations.

One test repetition has no sample standard deviation. Train has one measured pass and no across-training-run standard deviation. Keep Train and Test separate.

Always report the pre-training baseline and final Test scores, with their `mean`, `std` and final-minus-baseline gain. These are measurements of the same held-out set using the frozen base and learned States; training scores do not substitute for either.

For Evo, report the single training pass and compilation artifacts. There are no
candidate retests or iterative acceptance scores from which to draw a training
curve. A single training run has no across-run sample variance.
Set `curve_kind: none`; retain the per-task training scores and compilation decisions.

For declared mean-score Benchmarks, the helper also validates complete matrices
and computes repetition statistics:

```bash
python3 "$TOOLKIT/scripts/evo.py" summarize --request summary-request.json
```

The request has `matrices`, one full native matrix per selected benchmark for
one frozen condition, each declaring `aggregation: "mean"`. Use the matrix
fields described above. The output retains domain repetition scores, overall
repetition scores, mean, sample variance and sample standard deviation. Missing,
duplicate, failed or mismatched cells invalidate the result; a measured zero is
valid. One repetition returns `null` variance/std. Use the Benchmark's own rule
when aggregation is not a mean; this helper refuses unsupported aggregation.

The Evaluation Center's cost and duration fields are averages, not experiment totals. Include the separate Train/Test cost, time and token totals and their detailed records from the measurement section above.

Run `summarize` separately for `baseline` and `final`. Map its `domains` entries to the selected Benchmarks and retain their `repetition_scores`, `mean` and `std` in the common comparison, alongside its `overall` result. Compute `final_minus_baseline` from the unrounded means. The helper's `variance` is an additional diagnostic, not the value after ±.

Keep frozen State archives, source identities, per-case results and artifact paths with the report. Save both a readable summary and structured scores, and deliver the results in the user's requested format. Continue scheduling until training and every requested test repetition are accounted for; report a concrete blocker when completion is impossible.

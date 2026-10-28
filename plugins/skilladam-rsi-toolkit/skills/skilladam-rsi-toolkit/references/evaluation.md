# Run workers and collect measurements

The benchmark supplies the evaluator and defines its Train/Test splits. Use its measured scores and execution evidence throughout. The controller schedules one whole training run per benchmark or independent training unit, then three test repetitions of each frozen State by default. Inner SkillAdam iterations stay inside the training Target's Session.

## The launch worker

Receive the experiment root, benchmark, training unit, phase, test repetition index when testing, published case ID if applicable, native task path, resolved checkout, State archive and identity, runtime, optional install bundle and unique output path from the controller. Resolve the selected benchmark's launch instructions through [benchmark.md](benchmark.md).

A training worker runs one complete learning trial. A test worker runs one held-out question in one test repetition using the specified frozen State. Neither changes the experiment or launches another experiment controller.

Wait for completion using the available managed background mechanism, then return the status and exact trial/artifact paths. A launched process or an idle Agent is not by itself a completed trial. Use the native result to distinguish completion, interruption and infrastructure failure.

Follow the selected benchmark's retry rules. A diagnosed infrastructure failure before the Target starts can be repaired and retried under a new job name, retaining the failed attempt. A completed wrong answer or low score is a measurement. Interrupted learning that already used the model remains incomplete work; do not silently replace it with a fresh successful run.

## Read native results

For a scored Harbor trial, take reward from the trial's `verifier_result.rewards` using the benchmark's declared metric and scale. Convert a normalized `0..1` reward to `0..100` for reporting; preserve other metric scales as documented. Use the trial's `agent_result.cost_usd` when present, execution timestamps for duration, and actual model usage/outcome for runtime identity. Missing grade data is incomplete; a measured zero is valid.

For training, collect the final answer grades from the benchmark's documented result artifacts. Each continuous learning trial contributes its cost and duration once. Read no-Skill, S0, current/candidate scores, decisions and optimizer history from the learner's indexed records for the learning curve. Use the same display scale as Test while retaining the raw values. Keep online measurements distinct from the final verifier grade.

For Test, gather every requested case in each of the three repetitions for every frozen version. All repetitions of a version use the same State archive and digest. All versions use the same task set, base State, model, tools and scoring conditions; each trial begins with a fresh environment and conversation. Test feedback never revises a learned Skill. With N held-out cases and three comparison States, three test repetitions require 9N task trials; training is performed once.

Reconcile the experiment index with native trial results, matching each score to the case and frozen State actually evaluated. Keep failed or superseded attempts separately, with their costs and reasons. In progress reports, show completed coverage and compare versions only on their shared completed cases.

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
python3 "$TOOLKIT/scripts/skilladam.py" report \
  --matrix "$MATRIX" --spec "$SPEC" --time "$UTC_TIME" \
  --step "$STEP" --summary "$SUMMARY"
```

Append the returned record under `evaluations` in that Benchmark's scoreboard and preserve existing records. Only complete matrices are published; incomplete work stays visible in the experiment index.

A combined training task may be **one published Train case** containing several questions. Map it as the selected benchmark declares, measured using the initial learner State, with `runs: 1`. Its final grade is not an independent evaluation of a frozen candidate Skill. Keep the inner learning curve in the experiment output rather than inventing separate Harbor trial identities for its questions.

For Test, publish one matrix per benchmark/training unit and frozen version, covering every held-out case with `runs: 3` by default. Each case has cells with `run: 1`, `run: 2` and `run: 3`, all measured from the same frozen State. No-Skill, S0 and final each have their own matrix. If the request changes the test repetition count, use that count in both the matrix and its spec.

## Finish the experiment report

For each frozen State, each test repetition includes every selected test case. Apply the benchmark's aggregation rule separately to each repetition. For a benchmark scored by the mean of N test cases, with R test repetitions:

```text
repeat_score[r] = sum_q score[r, q] / N
mean = sum_r repeat_score[r] / R
sample_std = sqrt(sum_r (repeat_score[r] - mean)^2 / (R - 1))
```

Report `mean ± sample_std` and retain the R repetition scores. For example, three complete-test means of 60, 70 and 80 give `70 ± 10`. The standard deviation measures variation between complete test repetitions of the same frozen State. Calculate this standard deviation from repetition scores, not pooled case scores or an average of per-case standard deviations.

For an aggregate across benchmarks on a common scale, average the same selected benchmarks within each repetition. This gives R overall scores; apply the mean and sample-standard-deviation formulas to those scores. Do not average the benchmarks' standard deviations.

One test repetition has no sample standard deviation. Train has one measured learning curve and no across-training-run standard deviation. Keep Train and Test separate.

Separate the gain from initialization (no Skill to S0) from the gain after optimization (S0 to final). Show rejected candidates separately from the retained-Skill curve. When S0 and final contain identical Skill files, describe any difference between their test scores as variation between repeated measurements.

The Evaluation Center's cost and duration fields are averages, not experiment totals. Calculate total cost separately from the native trials and recorded controller/worker usage, counting each underlying model run once; do not add child usage again when a parent total already includes it. Mark unavailable costs as unknown. Record actual wall-clock time separately from summed trial durations.

Keep frozen State archives, source identities, per-case results and artifact paths with the report. Save both a readable summary and structured scores, and deliver the results in the user's requested format. Continue scheduling until training and every requested test repetition are accounted for; report a concrete blocker when completion is impossible.

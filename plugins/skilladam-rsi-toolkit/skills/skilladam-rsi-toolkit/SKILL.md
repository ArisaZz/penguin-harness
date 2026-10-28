---
name: skilladam-rsi-toolkit
description: "Run a SkillAdam experiment on the Project's selected Benchmarks: learn a reusable Skill from training feedback in a continuing Agent Session, then evaluate the frozen Skill on held-out tasks."
version: 2026.10.28.1
---

# SkillAdam

You are the experiment's main Penguin. Read the selected Benchmarks, prepare the runtime, arrange training and testing, and collect the results. Continue until the requested experiment is complete.

The **Target Agent** is the Penguin that learns or solves tasks inside the benchmark environment. Each independent training run uses one continuing Session and one container. The learner controls its task attempts and Skill updates there. Test tasks use fresh environments and conversations.

## The method

[SkillAdam: Stable and Efficient Skill Evolution for Agents](https://arxiv.org/abs/2609.08944v1), §4 and Algorithm 1, optimizes a Markdown Skill while keeping the model and tools fixed. The [author implementation](https://github.com/ruc-datalab/SkillAdam/tree/b6c9640f7a9e0d5e3a500c25bc4e6369eeca78f1) is the implementation reference.

First, the learner attempts training tasks without a learned Skill. It uses those trajectories and evaluator feedback to write S0. Each subsequent iteration runs the current Skill, proposes an edit, and evaluates the candidate on the same training cases. The benchmark's acceptance rule decides whether to retain the edit.

Two persistent states distinguish SkillAdam:

- **Evolving Issue Tracker (EIT): what to change.** Record recurring problems and the outcomes of attempted fixes. Later proposals use this history together with the latest trajectories and feedback.
- **Adaptive edit budget: how much to change.** Track an exponential moving average of the variance of per-case score changes. Inconsistent effects shrink the next edit budget; consistent effects allow it to recover.

Both states are updated after evaluating a candidate, including rejected candidates. The output is the last accepted Skill. Held-out test feedback never updates it. [The learning instructions](references/training.md) give the equations and iteration order; install them for the training Target.

## Before you start

Find the selected Benchmarks in the current Project, using the Environment's App Data Dir. Read their manifests and Case statements, then follow the linked runtime instructions. Built-in packages contain descriptions and run instructions; fetch task sources and environments when those instructions require them. A request naming the installed Benchmarks is sufficient: the user need not supply a repository link.

Match each selected benchmark's Train and Test packages from their documentation. Package Cases may represent either a single question or an entire continuous training task. Use the documented native paths rather than deriving paths from package names or old task-group numbers. A branch link such as `main` is valid; resolve it once for this experiment and record the checkout used. [Benchmark setup](references/benchmark.md) covers this handoff.

Resolve the remaining settings from the request and benchmark instructions:

- Model, thinking level, tools and base Agent State.
- Training units, independent repetitions, initialization cases, batch size, sampling seed and proposal iterations.
- Acceptance metrics, optimizer parameters, comparison versions, time limits and Docker capacity.

Use all Train and Test questions unless the request selects a subset. Each independent benchmark and repetition learns its own Skill from the same base State. Keep the runtime fixed across all comparisons. Do not mix their learned state or reuse earlier experiments' Skills unless requested.

The numerical helper defaults are `beta2=0.9`, `base_budget=4`, `min_budget=1`, `variance_cap=0.1`; the budget counts unified-diff hunks. Its default gate is strict improvement of mean normalized reward, without a per-case regression threshold. Use that gate when it matches the benchmark's declared rule; otherwise apply that rule and use the helper only for volatility and budget calculations. The dataset, repetitions and iteration count are experiment settings, not properties of SkillAdam.

## Run the experiment

1. **Prepare.** Follow [initialization](references/initialization.md): record the resolved plan, make a common base State, and prepare a separate training State for each independent run. Reuse the selected runtime; [source builds](references/source-bundle.md) are only needed when the experiment requires one.
2. **Train.** Launch the benchmark's continuous training entry point. Give its Target the learner instructions, helper and training brief through the supported State handoff. A candidate update stays inside that Session and container; it does not create another Harbor trial.
3. **Collect and freeze.** Collect S0, the last accepted Skill, answers, measured scores, decisions and optimizer history. Freeze complete Skill folders, including supporting files. If no candidate was accepted, final is S0.
4. **Test.** Build no-Skill, S0 and final States from the same base, unless the request names other comparisons. Add only the corresponding frozen Skill and its reader instruction. Evaluate every held-out question in a fresh environment and conversation, with the same model, thinking level, tools and scoring conditions.
5. **Report.** Follow [evaluation and reporting](references/evaluation.md). Collect native results, the training curve, costs and elapsed time; publish to the Project's Evaluation Center when applicable.

You own scheduling. When `run_subagent` is available, workers can launch and collect trials: one training worker owns a whole learning run, and a test worker owns a held-out task. Give independent runs separate working directories and output paths. A worker does not start another experiment controller. Use the supported background mechanism, retain job identifiers, collect completions and fill available capacity until the requested work is done.

Count every container started for this experiment, including network sidecars, toward the user's Docker limit, and respect the benchmark's per-host limit. Leave unrelated workloads unchanged. Keep a short index of completed, active and pending work with artifact paths. A process launch is not a completed measurement; inspect the runner's final result before recording a score.

## Report the result

Report Train and Test separately for each benchmark. Show no-Skill, S0 and final scores, accepted candidates and the measured retained-Skill training curve. Keep candidate scores and the final training verifier grade as separate records. A curve uses the actual measurement for that iteration, not a cumulative maximum.

For repeated experiments, first calculate each repetition's benchmark score, then report the mean and **sample standard deviation of those repetition scores**. For an overall score on a common scale, average benchmarks within each repetition first. Do not calculate this standard deviation across individual questions or label it pass@k. One repetition has no sample standard deviation.

Include recorded total cost, elapsed time, incomplete runs, method deviations and paths to the frozen Skills and results. When S0 and final are identical, differences in their independent test scores are measurement variation, not a learned change.

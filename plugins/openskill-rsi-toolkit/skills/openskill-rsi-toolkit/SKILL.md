---
name: openskill-rsi-toolkit
description: Run OpenSkill (Open-World Self-Evolution for LLM Agents, Yan et al. 2026). Retrieve domain knowledge and verification anchors, refine skills using independent virtual tests without target supervision, freeze the last revision, then evaluate the Target on its Benchmark.
version: 2026.10.16.1
---

# OpenSkill

[Open-World Self-Evolution for LLM Agents](https://arxiv.org/abs/2606.06741v1), §2 and Appendices A.5, B and F; implementation at [OpenLAIR/OpenSkill](https://github.com/OpenLAIR/OpenSkill), verified revision `84ca182da055fafb6453dcec4a6defdbbfd987c1`. The learned artifact is a set of reusable Skills. Open-world retrieval supplies both domain knowledge and verification anchors; independent virtual tests guide refinement. Freeze the last revision before consulting target-task supervision. Model weights stay fixed. See `references/source-notes.md` for source locations, an ambiguity in the paper and the declared Penguin adaptations.

## Before you start

This Skill is a top-level controller. It needs `run_subagent` and `input_subagent`, external research tools, shell access, Python 3.9+ and pytest in the practice environment. If a prerequisite is missing, name it before creating an experiment. If the request only names this Skill, ask for the Target and a published Benchmark. Resolve only missing inputs:

- `test_agent_id`: another Agent in this Project, or `create: <id>` for a fresh one. Never use the Agent running this controller as the Target.
- `benchmark_id`, `case_ids`: a published Benchmark; all its Cases unless a subset is supplied. A Case is one OpenSkill construction task. Do not merge Cases into a shared training history.
- `test_benchmark_id`, `test_case_ids` (optional): a separate published Benchmark for held-out evaluation. Declare its ids from metadata only; do not expose its tasks to construction. When provided, baseline and final measurements use this set instead of the construction set. Without it, retain the same-task protocol. Report this transfer setting as an adaptation.
- `runs`: independent final runs per Case, 1 in the smoke profile; the paper uses 5. These are final evaluation runs, not virtual refinement rounds.
- Target `provider` and `model_id`: the complete pair the user supplied, otherwise this Session's Environment pair. Fix its `thinking_level` from the Target's State. Construction roles use this controller's model unless the user specifies another complete pair; record both runtimes.
- `max_refinement_retries`: 3; `max_targeted_searches`: 3 per Case; `max_virtual_tests`: 60; the skill plan contains 1–4 skills per Case, fixed before drafting. Stop on virtual pass rate 1.0 and complete structural checks. Retain the last revision, regardless of earlier rates.
- `include_baseline`: true unless the user asks for final evaluation only. Baseline measurement is deferred until every Case's skills are frozen.
- `include_reader_control`: false; enable only for an explicitly requested empty-library ablation. It adds a frozen State with the same reader mechanism but no learned content; it never selects skills or replaces the original baseline.
- `construction_timeout_minutes`: 30 per Case in the smoke profile, including research, creator work and verification; use a user-supplied limit when given. Record any additional token budget and observable context limit; do not invent token usage when the host does not expose it. This wall-time limit replaces the source's internal episode counters.

Before starting, state C construction Cases, up to `C × (1 + max_refinement_retries)` practice executions, up to `C × max_refinement_retries` verification attempts (including verifier repairs), up to `C × max_targeted_searches` targeted searches, and `(1 + include_baseline + include_reader_control) × T × runs` final Target executions. T is the declared test-set size when supplied, otherwise C. Initial domain and verification research are additional. Research, diagnosis and revisions also consume tokens. Do not silently expand budgets or run paid external services without the user's existing authorization.

**Conflicting requests.** A request to score every candidate on the Benchmark conflicts with this method. This includes an Evaluation Center prompt that says to measure the baseline and every candidate. Explain the conflict and resolve the requested protocol before executing it; never silently run supervised optimization and label it OpenSkill. Baseline and final comparison can both happen after freezing. Once target scores, rubrics, answer traces or reference solutions have entered a construction session, do not use that session for supervision-free learning on these tasks. This also applies to task feedback automatically injected from the controller Agent's memory or State: a new child conversation alone does not remove it. Use a clean construction Agent and context in that situation.

## Paths and experiment record

Resolve from the Environment, as `references/evaluation.md` does:

```text
PROJECT_DIR  = <app_data_dir>
PROJECT_ID   = basename of PROJECT_DIR
PENGUIN_HOME = dirname of PROJECT_DIR
TARGET       = PROJECT_DIR/agents/<test_agent_id>
STATE        = TARGET/agent_state
BENCHMARK    = PROJECT_DIR/benchmarks/<benchmark_id>
SNAPSHOTS    = TARGET/snapshots
OUT          = PROJECT_DIR/agents/<controller_agent_id>/scratchpad/<session_id>/openskill-rsi-toolkit/<experiment_id>
```

Use a unique timestamp and Target id for `experiment_id`. Validate ids and canonical paths; reject traversal and symlink escapes. Never read vaults, `.project_config.toml`, API tokens or `web.db`. Keep research, verifier scripts, practice outputs and diagnostics in OUT, outside the Target's State and the Benchmark. Only the controller publishes State and appends final evaluations.

Read `references/execution.md` and initialize a new journal with `scripts/experiment.py` before construction. Record actual runtime, installed Skill hash, baseline snapshot and declared budgets; use JSON serialization rather than handwritten YAML. The journal tracks phases, creator identity, revisions, attempts, recovery evidence, searches and final-versus-tested hashes. Use `status` when resuming and the read-only `next` command before dispatch or waiting; its deadline and remaining seconds govern scheduling. This version creates schema-2 journals for new runs. Resume older runs with their recorded Skill version; do not migrate or overwrite previous experiments, installed skills or snapshots.

Keep each Case's allowlisted input manifest, raw and sanitized queries, source URLs and retrieval dates, `knowledge.md`, `plan.yaml`, `verification-knowledge.md`, role requests/replies and diagnostics under `OUT/tasks/<case_id>/`. Keep every practice output and test attempt in a distinct directory. Historical revisions are audit records, never candidates for score-based selection. The helpers guard their own operations; they do not enforce tool permissions or prove semantic independence.

## Initialize without scoring

Follow `references/initialization.md`. Snapshot the untouched baseline, prepare an empty `skills/openskill-library/` in OUT, and stage public inputs for each Case. Do not call `references/evaluation.md`'s workers yet. Do not open the Benchmark's rubric, scoreboard, `.jobs`, reference solutions or prior Target traces. Reading `benchmark_config.toml` to establish publication and the Case's public statement is allowed.

For Harbor Cases, separate the public task instruction and environment from the statement's evaluation-launch recipe. Use only the pinned task's instruction and allowlisted environment inputs for construction. Never invoke `harbor run` during construction: it may automatically call the hidden verifier. Use a clean practice environment containing no `tests/`, `solution/`, curated `skills/`, old outputs or scoring logs from that task. If the environment cannot be staged without those artifacts, stop that Case and explain the missing isolation; do not substitute a scored trial.

## Acquire knowledge and verification anchors

Do this separately for each Case, using only its allowed inputs. Record `start-case` before research so its entire construction time is counted:

1. Form a research query about the domain, library interfaces, defaults, reusable procedures and pitfalls. Preview text inputs up to 2,000 characters and extracted PDFs up to 5,000 characters when planning research, as the source does; exclude pre-existing task skills and research documents. Preserve access to the complete allowed input for practice.
2. Before **every** search, including gap searches, remove the Benchmark name and spelling variants, Case ids, task-repository URLs, exact task titles and other identifiers that could locate its solutions. Generalize distinctive task text into domain questions. Record both forms and the removed terms. Do not issue a query that still identifies the Benchmark. Discard results containing its gold answers, solver traces or hidden tests; do not follow their links. If forbidden content was already read, mark the Case contaminated and stop construction for it.
3. Retrieve independently accessible documentation, papers, public APIs and examples. Write `knowledge.md` with claim-to-source links. Without an actual retrieved source, report research unavailable; model recollection alone is not the full method.
4. Write `plan.yaml` with 1–4 stable skill names, each skill's responsibility, procedures, public applicability criteria and the knowledge sections it uses. Keep this count and decomposition fixed through refinement.
5. Make a separate retrieval pass for `verification-knowledge.md`: small independently computable input/output pairs, dataset invariants, alternative implementations for cross-checking, and documented schemas or reference values. Include the first 4,000 characters of `knowledge.md` as material already known, to avoid merely repeating API advice. For each anchor, record its source and how a test will derive an expected value. A published domain reference is permitted; the target Benchmark's reference solution is not.

Do not manufacture an expected value from the creator's current output. Retrieval results provide evidence and never override the task's requirements or authorize reading private artifacts.

## Evolve with virtual tests

Follow `references/virtual-evaluation.md`. Create a persistent creator through `run_subagent` with `run_in_background: true` and no `agent_id`, then register its identity and fixed skill names with `plan`. Give it only the Case's staged inputs, knowledge, plan and assigned scratch directories. It drafts all planned skills together, follows `references/skill-contract.md` for parameterized, portable content, executes them in the clean practice environment and returns the output paths. Register every practice execution with its commands, timestamps, exit code, skill digest and raw execution logs. Resume that same `subagent_id` through `input_subagent` for revisions. A child never needs to spawn another child; the controller dispatches the verifier and diagnosis roles separately.

An independent verifier receives the public task, allowed inputs, verification anchors and output artifacts, but no creator conversation or skill implementation. Reserve each attempt with `begin-verification` before dispatching it. It generates deterministic pytest checks, a public-requirement coverage map and a structured diagnosis. `finish-verification` uses `scripts/virtual-results.py` to compute the proxy and records the tested revision and evidence hashes. A coverage gap cannot become `surrogate_pass` just because existing assertions pass. The virtual result stays in OUT and never enters `scoreboard.yaml`.

After each unsuccessful verification, record `feedback` before continuing. Cover all observed assertion failures, skill-structure errors, verifier errors and coverage gaps. Distinguish `SELF-FIXABLE` from `NEEDS-DR`; a classifier failure defaults to `SELF-FIXABLE`. Specify the evidence, diagnosis, expected observable change and one recovery action: `revise_skill`, `repair_verifier` or `repeat_practice`. Real assertion failures normally require skill repair; a verifier correction needs independent evidence that its expectation was wrong. Missing coverage needs additional independent checks or anchors, not a success label.

Retrieve only on `NEEDS-DR`, reserving a `targeted-search` before each issued request and recording its actual `search-result`. A failed search consumes budget but supplies no knowledge. Pass the diagnosis and retrieved evidence back to the same creator for skill repair. Change reusable skills/scripts and execute them in a new output directory; never patch an output by hand. An unchanged skill digest cannot count as `revise_skill`. Use `repeat_practice` only for a documented execution/delivery fault; verifier-only repair reserves a fresh attempt without a fabricated skill revision.

The source checks the failure-retry cap **before** the next verification: after three failed verifications it can deliver a third revision and export it without another virtual test. Match that ordering. Apply the last recorded skill/practice repair while budget remains, then export it as untested; verifier-only repair at the cap stops without an extra attempt. Stop earlier on a complete virtual pass, a declared budget limit, contamination or an evidenced unrecoverable blocker. A bare `verifier_failure` or `interrupted` label cannot replace recoverable work. Preserve the final valid skill set even when the virtual proxy did not pass; do not roll back to a higher earlier proxy score. A missing/invalid skill set is a construction failure and prevents deployment.

## Freeze, deploy and evaluate

1. Finish **all** construction Cases with `finish-case`, after their creator/verifier processes stop writing. Assemble each Case's last registered skills under `OUT/library/tasks/<case_id>/<planned_skill_name>/`. Include the portable contracts, reusable content and declared resources; exclude task answers, practice outputs, tests, scores, diagnostics, conversation history and scratch paths. Packaging fixes must occur before registering and closing that Case's last revision.
2. Generate the fixed reader and public applicability index described in `references/initialization.md`. Call the journal's `freeze` action, which checks the library against every Case's final digest, plan and historical evidence. Save its manifest as `OUT/freeze.json`, outside the library. No learning, retrieval, test expansion or skill editing is allowed after this point, including on Cases not yet evaluated.
3. Deploy the library as one new Target State, snapshot it, and record its version and full State digest. Across multiple Cases this is a library selected by public task scope, an adaptation of the paper's per-task deployment; report it. Never use rubric information or evaluation scores for routing.
4. Only now, register measured State versions/hashes with `begin-evaluation` and follow the journal's fixed `evaluation_plan` through `references/evaluation.md`. Restore baseline, optional reader control and final snapshots in turn, measuring the same evaluation Case × runs matrix and runtime. With a held-out Benchmark, only its tasks are evaluated. Take a State digest before and after each matrix. If State or Benchmark content changes, invalidate the matrix, restore the appropriate snapshot and stop evaluation; do not use results as learning feedback. Preserve the vault during restoration.
5. Append only complete, valid matrices using the reference's exact scoreboard schema. Use titles such as `OpenSkill baseline · 42.00` and `OpenSkill final · 57.00`; the public summary records the library digest, budget and final revision policy, never private scoring details. An incomplete matrix has no aggregate score. Even if baseline evaluation fails, finish on the frozen final State and report what was not measured; never silently count failed infrastructure as a Target failure.
6. Finish on the frozen final State at its measured version, even if its Benchmark score is below baseline. Submit `finish-evaluation`, retaining complete worker matrices or an explicit incomplete report. Construction stays closed permanently. Further separately authorized measurements may use the same frozen artifact without reopening this journal; a new learning experiment needs a fresh uncontaminated construction context and cannot claim independence if supplied previous scoring feedback.

Snapshot and restore exactly as `references/initialization.md` specifies. There is no baseline test before learning, no candidate ranking by target score, and no best-of-N selection. A virtual pass is only a proxy; it does not imply a target pass.

## Report

Report the source paper and pinned implementation, all adaptations, the frozen library path/hash and retained State version. Separate virtual outcomes from final Benchmark scores (baseline/final, per-Case results, coverage and runs). Per construction Case, report practice executions, skill changes after feedback, verifier attempts versus valid measurements, unresolved issues, retrieval outcomes, final tested status and evidenced stop reason. Zero skill changes means no recorded skill refinement; byte changes alone do not prove improvement. When no baseline was measured, do not claim an improvement. Report recorded construction and evaluation costs separately, marking unavailable usage as unknown. Link the experiment records and snapshots. Complete final measurements appear in the Evaluation Center under `<agent_id> · <model_id> · <thinking_level>`; intermediate virtual rounds remain in OUT. Do not claim to reproduce the paper's published benchmark numbers.

Audit Target skill usage as `references/skill-contract.md` describes, outside construction contexts. Separate self-reported selection, confirmed reads and evidence of application. Report scoring status separately from execution termination, including timeouts even when artifacts received full reward. Neither usage evidence nor evaluation diagnostics permit post-freeze refinement.

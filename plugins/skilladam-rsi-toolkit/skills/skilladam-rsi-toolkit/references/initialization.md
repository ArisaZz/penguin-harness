# Prepare the experiment

Resolve the Project from the current Penguin Environment's App Data Dir. Use the host and output directory named by the user; otherwise use this Session's workspace or scratchpad. Record the selected packages, task sources, runtime, repetitions, learning parameters, comparison versions and resource limits in a short experiment record.

## Runtime and directories

Read the selected Case statements and benchmark instructions. They specify Docker, Harbor or another runner, its adapter, model configuration, task paths and artifact collection. Reuse the current CLI and configured model connection. Follow the benchmark's installation procedure for the Target; a source build is described in [source-bundle.md](source-bundle.md) when required. The adapter copies credentials privately; keep them out of prompts and experiment records.

Use a separate directory for each benchmark and repetition, with its own State archives, jobs, frozen Skills and results. Keep a launch index so the controller can resume collection after context compaction. Keep task source and grading implementation unchanged during the experiment. Benchmark source is fetched once per experiment from the link in the installed package; an existing unrelated checkout is not an input.

Before launching repeated runs, verify that a training attempt can obtain the evaluator feedback required by SkillAdam. A reachable business service alone does not confirm that training feedback is available.

Inspect active runs without changing ownership or permissions on their mounted log directories. Organize a completed trial's artifacts after its runner exits, so collection does not interrupt another trial's logging.

## The common base State

Use the requested base Agent, or create a fresh Agent through the CLI. It is separate from the experiment controller. A new Agent can be created with:

```bash
penguin agent create --agent-id <unused-id> --project-id <project-id> --json
```

Use the same base for all comparisons, without a learned business Skill unless one was requested as the baseline. Set the requested thinking level in `system_config.yaml`. Disable persistent memory and state-mutating hooks in these experiment States. Align the State's turn limits, including `compaction.max_session_turns`, and the runner's limits with the benchmark. These settings do not clear the continuing training conversation.

Snapshot this base before adding learning instructions. Pass the selected provider, model and thinking level explicitly to every launch, including delegated task-solving calls.

## The training State

Copy the base, then install:

| Toolkit file | Destination relative to the training Agent State |
| --- | --- |
| `references/training.md` | `skills/skilladam-training/SKILL.md` |
| `scripts/skilladam.py` | `skills/skilladam-training/scripts/skilladam.py` |

Add `training-request.json` at the State root. It contains this run's benchmark, training cases, repetition, seed, batch rule, proposal iterations, optimizer parameters, acceptance rule, runtime and export locations. Resolve these values from the experiment; do not make the learner infer them from other runs.

Write `skills/skilladam-training/benchmark-training.md` from the selected benchmark's learner-facing instructions: where training inputs and tools are, how to request feedback, what the score means, and where to export answers, S0, the final Skill and learning records. Include the selected training material; held-out questions and repository grader files do not belong in this brief.

Add a short reader instruction to the training State's `AGENTS.md`:

```text
For a whole training run, read training-request.json beside this file and
skills/skilladam-training/SKILL.md, then complete the learning process in
this continuing Session and environment. For a delegated rollout or single
task, follow only that solving request; do not start an optimization loop.
```

The training Target receives learner instructions, not the outer experiment-controller Skill.

## The test States

After training, identify S0 and the last accepted Skill from the learning records. Preserve their complete folders. Starting from the original base, prepare one no-Skill State, one with S0 and one with the final Skill. Test States receive neither training method instructions nor optimizer history, training answers or conversations.

Use the same reader instruction in all test States:

```text
Complete the supplied benchmark task. If a learned task-solving Skill is
installed in your Agent State, read its SKILL.md and relevant supporting
files before substantive task actions, and apply it to this task.
```

Keep each State frozen during measurement and record its version and digest. Preserve existing snapshots; distinct States of the same Agent use distinct versions.

## State handoff

Follow the runner's current State-import contract. For the Penguin Harbor adapter, `agent_state_tar` takes an archive whose root contains the State files, not an enclosing `agent_state/` directory:

```bash
tar --exclude=./.vault.toml --exclude=./memory --exclude=./schedule \
  -czf "$STATE_TAR" -C "$STATE_DIR" .
```

The executable installation and the Agent State are separate inputs. Pass the frozen archive to the adapter using the argument documented by the benchmark. Verify that the exported S0/final Skill reaches its corresponding test State before launching tests.

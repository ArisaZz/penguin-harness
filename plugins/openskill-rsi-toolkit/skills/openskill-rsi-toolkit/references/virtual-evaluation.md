# Virtual evaluation during construction

This protocol implements the practice loop in OpenSkill §2.2.2 and Appendix B. It never calls the shared `evaluation.md` protocol, reads a target rubric or writes the Evaluation Center's scoreboard. All roles operate on one Case's staged public inputs and independently retrieved knowledge. Target evaluation begins only after all Cases are frozen.

## Creator

The controller starts one background `run_subagent` session per Case and retains its `subagent_id`. Omit `agent_id`; record the construction runtime. A creator receives:

```text
Role: OpenSkill creator. Work only in the assigned practice directories.
Public instruction and allowed input manifest: <paths>
Domain knowledge and skill plan: <paths>
Reusable skill destination: <scratch path>
Practice environment and output destination: <paths and launch instructions>

Draft all planned skills together. Each SKILL.md needs a matching name,
description and dated version. Follow the supplied skill-contract.md: describe
applicability, parameters, output contracts, checks and limitations; include a
contract.json with a stable id and every resource. Put reusable code in scripts/
and cite references. Resolve resources relative to the skill, not a practice root.
Execute the task using those skills and the allowed inputs. Generate outputs by
running the procedures, rather than embedding this task's answer in a Skill.
Return the skill and output paths, revision hash and commands actually executed.
Do not read target scores, tests, rubrics, solutions, old traces or other Cases.
Do not spawn subagents or change the Target Agent State. Await controller feedback
before making another revision.
```

The actual task input is permitted during practice, as in the source. "Virtual" describes the independently generated verifier and its supervision, not a requirement to invent unrelated user tasks. Small synthetic inputs and documented examples can add checks when they exercise the same skills. Keep these checks grounded and record that coverage.

On each revision, resume the same creator with `input_subagent`. Supply the structured virtual failures, diagnosis and any gap research. Keep the planned skill count fixed. The creator fixes skills/scripts and re-executes in a clean output directory or restores the input environment first. Use `practice/revision-N/` and register `revision` as `execution.md` describes; the helper preserves each skill revision and hashes its outputs before another attempt. Outputs must come from the recorded skill revision; stale files cannot satisfy a later test. State the proposed correction and observable behavior expected from it, then check that prediction in the next allowed verification.

## Independent verifier

The controller starts a separate verifier session with `run_subagent`, no `agent_id`. Its context contains only:

- the task instruction and allowlisted environment inputs;
- verification anchors with source citations;
- output artifacts from this practice execution;
- its own previous test script and failure list, if a suite needs refinement.

Do not give it creator prompts, conversation, private reasoning, skill scripts or implementation code. It may inspect code when the requested deliverable itself is source code, but not the creator's reusable implementation of that deliverable; record that distinction. Never pass GT paths or even a GT pass/fail bit. Its separate Session does not inherit the creator's conversation. Tell it not to browse parent directories, consult other traces or use target scoring files.

Ask the verifier to:

1. Map each public requirement to an independently supported expectation. Use verification knowledge or independent computation from inputs and documented rules. An assertion based solely on the current output is circular and invalid. Task instructions take precedence over a retrieved page that disagrees.
2. Write a pytest suite with at most 60 collected test cases, including parameterized instances. Prefer equality on exact values; numeric tolerances must follow the documented contract. Test content as well as shape. At least 60% of tests should read and validate actual outputs, following the upstream verifier prompt. Every check needs a requirement/source mapping. No live LLM judgments, unseeded randomness or web lookups inside tests.
3. Use assertion failures for incorrect/missing target outputs. Test setup, import, collection and execution errors are verifier failures, not low skill scores. Do not mark required checks skipped, xfailed or deselected to reach a pass.
4. Run pytest once in the reserved attempt directory and save the script, raw log and JUnit XML report. Return broken test code to the controller for a new budgeted attempt; do not perform unrecorded reruns inside this session. Preserve expected values unless independent evidence proves the previous oracle wrong. Never weaken a test because the creator failed it. Test repair and added checks need a recorded reason, source and new suite hash; rates from different suites are not directly comparable.
5. Return a per-failure diagnosis: assertion id, observed value, expected value and its source, likely cause, and a specific revision suggestion. Do not change creator output or skill code.
6. Save `coverage.json` using `execution.md`'s requirement-to-test format. Include unresolved required checks as `unverified`, even if all implemented assertions pass. Do not omit a diagnostic concern from the coverage map to obtain success. The map and its sources remain verifier evidence outside the deployed library.

Before dispatch, the controller reserves `begin-verification`; after the attempt, it records
`finish-verification` with the actual exit code and verifier session. An attempt without a
valid report still spends budget. Execute in the recorded practice environment, using
absolute paths to the newly reserved attempt's report file:

```bash
python3 -m pytest "<virtual_suite>" -q --junitxml="<fresh_report.xml>"
```

Capture the command's exit code immediately and pass it to the shipped parser (whose path is relative to this Skill directory):

```bash
python3 "<skill_dir>/scripts/virtual-results.py" "<fresh_report.xml>" --pytest-exit-code <captured_code>
```

Do not reuse a previous report if pytest failed to write this one. The parser uses the individual JUnit test cases, excludes skipped tests from the denominator, rejects empty/all-skipped suites, duplicate test identities, errors, inconsistent exit codes and more than 60 tests. `status: ok` means the report is valid, not that the skills passed. Only `passed == total`, valid skill structure and coverage of every required check allow `surrogate_pass`. Optional skips must be justified; skipping a required check prevents that exit even when the numeric rate is 1.

Save the parser's JSON as the virtual measurement. A parser `status: failed` has no `pass_rate`; repair the cause in a separately reserved attempt within the retry/time budget or terminate with a verifier failure. Do not substitute 0 or let an LLM estimate a missing rate. Finalize the attempt only after all logs, diagnoses and coverage are written; the helper seals their hashes. The scripts need only Python's standard library; pytest is needed to produce the report.

## Diagnosis and retrieval

Give a separate classifier call the failed assertions, verifier diagnosis and prior domain knowledge, with no creator implementation. Ask for one decision and its brief evidence:

- `SELF-FIXABLE`: the needed rule is already known; fix implementation, format, types or indexing.
- `NEEDS-DR`: a missing domain rule, algorithm choice, reference value or API behavior requires external evidence.

An unavailable or malformed classifier result defaults to `SELF-FIXABLE`, matching the source. If a gap is identified and the Case has searches remaining, sanitize the query as SKILL.md requires and retrieve the missing evidence. Track topics and decrement the search budget on each issued search, including failed requests; this stricter bound is a declared adaptation of upstream's successful-result counter. Never expand the cap to compensate for empty results. Append the findings and citations to the feedback; a gap with no evidence stays unresolved.

## Retry ordering and termination

Use `retries = 0` for the initial draft. The loop is:

```text
create skills; execute practice task
while retries < max_refinement_retries:
    independently verify current outputs; record tested revision and suite hash
    if virtual rate == 1 and structure and requirement coverage are complete:
        stop: surrogate_pass
    if unrecoverable verifier/environment failure or declared budget reached:
        stop with that reason, with no invented virtual score
    diagnose; optionally retrieve missing knowledge within the search cap
    retries += 1
    revise in the same creator session; regenerate outputs
stop: max_refinement_retries
export the current skill set if structurally valid, otherwise construction_failed
```

Verifier errors and structural failures spend this retry budget too. If only the verifier needs repair, the retry may keep the skill bytes unchanged; record this instead of forcing a useless skill edit. With the source default 3, there are at most three verification attempts and four practice executions; the final revision after the third failed attempt is not re-verified. If the user changes this to an initial verification plus three verified refinements, label it an adaptation and account for the extra verifier call.

The source's internal episode limits are creator 60 / verifier 20, idle 3 / stale 10, with a context warning at 70% and export/stop at 90%. Penguin subagent turns are not Terminus episodes. Enforce the declared wall-time limit (30 minutes per Case by default) from the start of its research, and record that replacement rather than pretending to apply unavailable counters. Check elapsed time between calls and while waiting on background roles; at the deadline, abort the active role with `input_subagent`, stop its practice process, and wait for writes to settle before preserving artifacts. If measured context usage is available, warn at 70% and stop at 90%; do not repeatedly restart a creator to evade the budget. A stalled role or unsupported verifier must end with its reason, never an automatic pass. An invalid current skill set cannot be replaced by an older revision and called the final OpenSkill result.

At termination record the **current** skill digest, the digest of the last tested skill revision, the most recent valid virtual result and whether it applies to the exported revision. Do not carry a previous revision's pass rate forward. No best-of-N restore, no score-based tie-break, and no target evaluation as a substitute verifier.

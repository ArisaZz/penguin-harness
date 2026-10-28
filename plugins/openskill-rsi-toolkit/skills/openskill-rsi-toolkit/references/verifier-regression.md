# Developing the verifier without repeating construction

Use an offline acceptance gate before a separately authorized live pilot. It combines
fixed regressions with real SDK/container loops using a local scripted model. Passing tests does not establish benchmark
performance. Keep a stopped experiment immutable and never import development transcripts,
test-specific expected values or old target feedback into a fresh formal construction run.

The plugin's `tests/fixtures/verifier-evidence/` is an authored public fixture for the observed
permission/threshold failure pattern. It distinguishes supported arithmetic from an enum
that does not assign permissions and a measurement that does not establish a threshold.
`test_oracle.py` checks refusal and honest incomplete coverage without model requests.
`test_executor.py` uses a scripted provider at the model boundary with real SDK sessions and
containers; it exercises feedback, revision, reviewed verification, freeze and SDK loading.
No script claims a semantic proof merely because a citation exists.

The executor loop also covers the author-to-practice transition: an author writes a
deployment report, the same Session applies skills with a fresh output mount, and the
report remains inaccessible. The cooperative fixture reads the host's read-only practice
context and completes refinement through freeze/loading. A fixture that still reads the
missing report stops without importing its partial answer. Host-side skill/input changes
also prevent registration despite a successful tool exit. These scripted checks exercise
the real SDK and containers without model charges; they do not prove that a live model
will always follow the handoff instructions.

## Offline acceptance gate

From a repository checkout, install the locked dependencies and build Penguin core and its
dependencies. Supply a reviewed, pinned GDPevo practice image with Python/pytest and its
service startup profile. The command refuses an existing report and makes no paid model calls:

```bash
python3 -B plugins/openskill-rsi-toolkit/tests/acceptance.py \
  --image sha256:<reviewed-image-id> \
  --sdk "<repo>/packages/core/dist/index.js" \
  --report "<new-directory-outside-plugin>/acceptance.json"
```

The gate fails on any error, failure or skipped test. It records script/test fingerprints,
the SDK entry digest and image ID, and fails if the tested inputs changed during execution.
Its report is development evidence; it neither launches nor authorizes a formal experiment.

| Scenario | Required outcome |
| --- | --- |
| Faulty skill, supported failure, feedback and revision | Same creator repairs and applies skills; independent verification, final freeze and SDK loading succeed |
| Same requirement text in distinct tasks | Stable IDs survive preflight, measured coverage and final collection |
| Honest missing evidence | Gap remains visible; feedback/research consume the existing budget; retry exhaustion closes the Case without a success claim |
| Measured skill bug plus unknown policy and empty research | One recorded fallback resumes the same creator; executable skill changes, fresh practice and independent tests succeed; evidence-limited closure retains the unknown policy |
| Passing output proxy with an observed documented-interface defect | A sealed v2 review routes feedback to the same creator; changed resources and fresh practice receive independent regression checks before resolution |
| Final-attempt skill finding | The final repair executes without another verification; closure preserves the unverified finding and distinct final/tested hashes |
| Stale review, silently dropped finding or invented regression ID | Refuse the transition without changing the journal or consuming a model call |
| New finding after a clean review, or repair of only some findings | Append evidence before sealing feedback without overwriting history; allow relevant partial progress and retain unresolved defects |
| Unknown policy without an observed defect | No manufactured skill revision; only passing supported checks can qualify for evidence-limited closure |
| Malformed coverage or nonexistent mapped test | Strict run stops even after passing pytest; raw measurement remains available |
| Missing suite, failed practice or changed frozen input | No successful import or unrecorded retry; failure artifacts remain |
| Separate public, independent and additional research | Official pytest reads each declared environment root; replay shares the same contract |
| Invalid research selection before repair | No model call, staging, STOP or budget charge; correcting the selection uses the original remaining allowance |
| Same-family failures in one model response under recovery v2 | One allowance, later correction and complete delivery; an incorrect answer still receives independent failure feedback and a real skill revision |
| Exhausted local correction under recovery v2 | Retained failure enters bounded fresh execution; counts persist, unchanged-skill reruns are not skill revisions, and exhausted execution repair stops |
| Changed sealed retrieval evidence | Stop before dispatch; no downgrade to a correctable request error |
| Deadline, exhausted retries or interrupted measurement | No extra attempt; preserve the last eligible revision and report whether it was tested |
| Stop or startup failure | No later model dispatch; owned containers are removed |

`tests/fixtures/repeated-requirements.json` keeps only exact IDs/texts from the observed
first-Train collision and the source-file digest. Its test expectations are authored fixtures,
not copied answers. Budget/deadline transitions also have deterministic journal tests.

## Read-only protocol replay

For an existing completed or interrupted verifier attempt, pass its artifact directory and
the corresponding independent planning view explicitly:

```bash
python3 "<skill_dir>/scripts/protocol_replay.py" \
  "<old_OUT>/tasks/<case>/verify/attempt-1" \
  "<old_OUT>/.executor/<case>/verify-1/plan-view"
```

This reads the original plan, review, coverage, process receipt and JUnit report. It checks
source seals and uses the same coverage validator and failure classification as collection.
It never executes recorded code, invokes a model or writes into the old experiment. Standard
output is a development assessment; redirect it to a new report outside the old experiment
if needed. Exit zero means valid recorded protocol, including an honest gap or failed
assertion; exit two means invalid protocol or missing evidence. Neither result proves that
the natural-language review was correct. There is no skill deployment or benchmark score.

## Model-backed development replay

`scripts/verifier_replay.py` uses the same planning, review, test-authoring and measurement
functions as construction, without a creator or construction journal. It accepts only fresh
output directories. Each replay allows one plan and one official suite, sharing a declared
1–30 minute deadline (15 minutes by default). A failure is retained and fenced, not retried.
Use a new directory after a code fix; neither directory becomes a formal experiment.

Prepare a request with the reviewed `executor` configuration from `executor.md` (SDK/Project,
Docker, Node, pinned sanitized image, uid/gid and startup settings), a fixed model and explicit
file maps. Credentials stay in the configured Project, never in this request:

```json
{
  "executor": {"sdk": "<SDK path>", "penguin_home": "<configured root>", "project_id": "<id>", "docker": "<binary>", "node": "<binary>", "image": "sha256:<id>", "sanitized_image": true, "uid": 1000, "gid": 1000},
  "runtime": {"provider": "<provider>", "model_id": "<model>", "thinking_level": "<level>"},
  "timeout_minutes": 15,
  "public": {"task.md": "<absolute public file>"},
  "research": {"anchors.md": "<absolute independent research file>"},
  "outputs": {"answer.json": "<absolute candidate file>"}
}
```

The controller must review the selected source contents; file maps do not detect hidden
answers in an incorrectly selected file. Do not import creator code as research. Copies
preserve the original files, and candidate outputs are absent from the planning mount.

```bash
python3 "<skill_dir>/scripts/verifier_replay.py" plan "<new_OUT>" "<request.json>"
python3 "<skill_dir>/scripts/verifier_replay.py" status "<OUT>"
```

Inspect `.executor/replay/oracle/plan.json` and its public sources. Write an independent
controller review using `executor.md`'s schema and the hashes in `oracle/seal.json`.
Missing rules stay unverified. For a live fixture replay, do not supply the fixture's authored
plan or review decisions to the model; assess its own proposed requirements and claims.

```bash
python3 "<skill_dir>/scripts/verifier_replay.py" check "<OUT>" "<review.json>"
python3 "<skill_dir>/scripts/verifier_replay.py" verify "<OUT>" "<review.json>"
```

`check` validates the review record without a model request or measurement. It does not judge
semantic entailment. `verify` resumes the same verifier, runs one suite, and records a
development result in `replay.json`. Supported assertions can pass while coverage remains
incomplete; missing rules must not be hidden to make a fixture pass. A rejected promotion
never reaches official pytest. Every result retains `benchmark_score: null`; there is no
freeze, deployment, target scoring or scoreboard command. `executor.py` cannot adopt it as
a construction journal. For cancellation, use `verifier_replay.py stop <OUT>`.

## Formal-run entry conditions

Before another GDPevo batch, require a passing offline gate for the current scripts/runtime
and read-only replay of the applicable historical failures. If model-specific behavior still
needs investigation, use a separately authorized small replay with the specified model.
Next run only the first Train group, checking practice, reviewed verification, any necessary
feedback/revision and final Case closure before expanding the batch. Define the failure/stop
policy before launching. A real model can still propose unsupported claims;
the controller review is part of the procedure, not evidence that the model cannot err.
Report unresolved public-information gaps separately from execution faults and task errors.
Formal construction begins fresh with its original budgets, independent roles and global
freeze before baseline/final scoring. Development checks grant no extra formal attempts.

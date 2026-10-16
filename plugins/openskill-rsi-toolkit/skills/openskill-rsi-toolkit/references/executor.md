# Isolated construction executor

New experiments use `scripts/executor.py`. It owns construction role launches, measured
practice commands, pytest execution, process shutdown and journal transitions. The Skill
remains the controller for research, diagnosis, packaging and final evaluation. Do not
dispatch construction through unrestricted `run_subagent`, SSH helpers or shared containers.

## Requirements and trust boundary

Run the executor on the Linux machine with the practice images and a local Docker daemon.
It requires Python 3.9+, Node 24+, the built Penguin core SDK and a configured Penguin Project.
Model credentials stay in that Project and are resolved by the SDK; never copy them into a
request, prompt, environment image or container. Remote experiments run the executor on the
remote machine. SSH remains a controller operation, unavailable to construction roles.

Supply a reviewed practice image pinned by local `sha256:` image id. It must contain the
public task environment, `/usr/bin/env`, a compatible shell, Python and pytest, and be able
to run the mounted host Node binary. It must contain **no graders, solutions, preinstalled
task skills, prior outputs, credentials or scoring logs**, including in its startup services.
The `sanitized_image` flag records the controller's review; it is not an automatic image audit.
An image whose startup requires an external service is unsupported until that service can
run privately inside the same container. Preflight failure must stop the operation.

Each author and each official measurement gets a fresh container with no external network,
no Docker socket, its own process namespace and bounded resources. Business APIs may run
on that container's loopback interface. Tools run as the specified non-root uid/gid, normally
the executor user's ids so output files remain readable on the host. The image entrypoint
can initialize its local service using CHOWN/SETUID/SETGID; tool processes cannot acquire
those privileges. Do not share service state or writable volumes across roles.

The trusted launcher calls the existing core SDK. It creates a dedicated empty Agent State,
disables memory/vault/skill/schedule injection and exposes only `read_file`, `write_file`,
`edit_file`, `exec_command` and `input_command`. All file and command operations use the SDK's
`confineSpawn` boundary. Fresh verifier Agent/Session identities prevent inherited creator
history. The creator resumes its recorded SDK Session. Role containers receive only their
workspace, explicit read-only input views, their own read-only SDK scratch files, and the Node
executable. The journal, other roles, SDK state and host credentials are absent.

This protects against a role browsing the host or another role. The controller, the SDK,
Docker daemon and reviewed image remain trusted. A controller can still leak forbidden
information by copying it into an approved public file or writing it in feedback. Review
input contents, research provenance, output allowlists and diagnosis text. Containers cannot
prove semantic independence, verifier correctness or that a learned skill will generalize.

## Initialize

Use the existing configuration in `execution.md`, adding:

```json
{
  "execution_mode": "isolated-v1",
  "executor": {
    "sdk": "/path/to/penguin-harness/packages/core/dist/index.js",
    "penguin_home": "/path/to/penguin-data-root",
    "project_id": "default_project",
    "docker": "/usr/bin/docker",
    "node": "/usr/bin/node",
    "image": "sha256:<64 hexadecimal digits>",
    "sanitized_image": true,
    "uid": 1000,
    "gid": 1000,
    "memory": "4g",
    "cpus": 2
  }
}
```

Use actual paths/ids. `image` comes from `docker image inspect --format '{{.Id}}' <image>`.
Optional `case_images` maps construction Case ids to their own pinned image ids. Optional
`entrypoint` and `command` replace the image startup command when needed; they are controller
configuration, never model-provided Docker arguments. Public services must start from clean
state on every invocation. File deliverables are supported; a task whose only output is a
mutated service/database must first provide an explicit public export as a deliverable.

```bash
python3 "<skill_dir>/scripts/executor.py" init "<OUT>" "<config.json>"
python3 "<skill_dir>/scripts/executor.py" event "<OUT>" "<start-case.json>"
```

`init` checks every declared construction Case's pinned image before creating the journal.
It makes no model requests and does not start construction clocks. All images must pass;
the first failure stops the batch, writes `preflight.json` and `STOP`, and cleans up its
container. Do not reuse that directory. Existing runs remain on their recorded Skill version.

To check environments separately, without a configured model or creating a journal, run:

```bash
python3 "<skill_dir>/scripts/executor.py" preflight "<fresh_CHECK_DIR>" "<config.json>"
```

This uses the same `execution_mode`, `case_ids` and `executor` image/runtime settings.
Use a different fresh OUT for the later `init`; it repeats the checks. SIGTERM or
`executor.py stop <CHECK_DIR>` cancels a standalone preflight and cleans up, including
when no journal has been created yet.

### GDPevo business services

Set `executor.startup_profile` to `gdpevo` for the reviewed GDPevo practice images. Omit
`entrypoint` and `command` with this profile. The executor mounts the plugin's
`gdpevo_start.py` read-only and records its digest. The image's service directory, command,
port and health path come from its reviewed `GDPEVO_*` configuration. No benchmark checkout
or generated Dockerfile needs editing. Images retaining the normal GDPevo entrypoint are
refused unless this profile is selected.

The trusted supervisor starts the service as `taskenv`, which opens its own private log
after changing identity. The service receives `TASK_ENV_ENABLE_JUDGE=0`; its data and API
semantics are unchanged. Startup does not restore DAC_OVERRIDE, KILL or privileged mode.
The ordinary role uid/gid must differ from `taskenv`; it must have no taskenv group access.

Before each role or official measurement, the executor checks the non-root SDK worker,
zero effective capabilities, no-new-privileges, writable outputs and read-only input mounts.
With the GDPevo profile it also waits for the health API, confirms the role cannot list the
private service directory, and requires HTTP 404 from an empty judge request. That request
contains no candidate answer. The image review is still required; these probes do not audit
all routes or replace removal of grading assets. `startup_timeout_seconds` defaults to 120,
is limited to 300, and is bounded by the active Case deadline during construction.

`preflight.json` records the batch outcome. Container records under `.executor/containers/`
record readiness, the bootstrap hash and probe outcomes. Before removing a container, the
executor attempts to save its state, exit/OOM information and bounded logs under that
directory's `diagnostics/`. It saves command stderr on startup errors. Log collection is
limited to three seconds and 64 KiB per stream per command, and cannot block mandatory
cleanup on failure. These private diagnostics never enter creator/verifier views or skills.

`start-case.json` is `{"action":"start-case","case_id":"CASE-001"}`. Start the clock before
research. Then retrieve and stage public files under `OUT/tasks/CASE-001/inputs/public/`,
domain knowledge under `inputs/knowledge/` and independent anchors under `inputs/anchors/`.
These files are copied and hashed before the first role starts. The original Benchmark tree
is never mounted. Source links, clean queries and retrieval dates belong in the research files.

The executor serializes operations within OUT. Separate experiments can run concurrently.
All Cases declared in one experiment still share its final global freeze. A busy lock causes
a refusal; it does not launch a second writer. `status` and `next` remain read-only and can
be used while an operation is running.

## Creator and official practice

Prepare the initial request after reviewing its inputs and fixed deliverable allowlist:

```json
{
  "case_id": "CASE-001",
  "skills": ["calculate"],
  "hypothesis": "Aggregate all rows using the documented adjustment rule",
  "public": {
    "task.md": "tasks/CASE-001/inputs/public/task.md",
    "rows.json": "tasks/CASE-001/inputs/public/rows.json"
  },
  "knowledge": {"knowledge.md": "tasks/CASE-001/inputs/knowledge/knowledge.md"},
  "anchors": {"anchors.md": "tasks/CASE-001/inputs/anchors/anchors.md"},
  "outputs": ["total.txt"]
}
```

```bash
python3 "<skill_dir>/scripts/executor.py" creator "<OUT>" "<creator-request.json>"
```

The executor creates the persistent creator, records its actual session id before the first
model request, and supplies the portable skill contract. It stops the author container,
copies the authored skills and starts a fresh practice environment. The default
`practice_mode: agent` resumes that same creator to read and apply the frozen skills.
The original workspace and skill snapshot are read-only; a separate output directory is
writable. Markdown procedures and executable resources are both supported. Model completion
alone is insufficient: the declared result files must exist and pass safe import checks.

For a task fully represented by a reusable command, set `executor.practice_mode` to
`command` before initialization and report the adaptation. Its creator also writes
`practice.json`, for example:

```json
{"argv":["python3","${SKILLS}/calculate/scripts/total.py","${INPUTS}/rows.json","${OUTPUTS}/total.txt"]}
```

The executor substitutes the three roots and runs the argv array directly in a fresh
container. At least one argument must name a real frozen skill file. This establishes a
file reference, not semantic use; inspect the trace and command to establish how it was
applied. Arguments can repeat and never undergo host shell interpolation.

Both modes import only declared output files and register actual process times, exit status,
logs and the skill hash. Agent mode retains the SDK tool stream as execution evidence; a
self-written receipt is never used. Symlinks, hardlinks, special files and traversal are
rejected at import. Executable bits on copied resources are retained without privileged bits.
The creator's private workspace persists for revisions; the business environment does not.
Learned content must be portable. Temporary execution paths must not enter deployed skills.

## Verifier, feedback and repair

```bash
python3 "<skill_dir>/scripts/executor.py" verifier "<OUT>" "<case-request.json>"
```

`case-request.json` contains `{"case_id":"CASE-001"}`. The executor reserves one attempt
before staging or launching. Its fresh verifier sees public inputs, independent anchors,
the declared practice results and, on repair, its previous verification evidence. It cannot
see creator skills, history or workspace. It writes `suite.py` and `coverage.json`; the
executor copies these, stops that role and runs pytest exactly once in a fresh measurement
container. Tests locate files through `OPENSKILL_INPUTS` and `OPENSKILL_OUTPUTS`. JUnit ids are
`suite::test_name`, including parameter suffixes, because the executor fixes pytest's root.

A read-only pytest collection hook rejects more than the configured number of collected
tests before test execution, including parameter expansion. The executor collects the real
exit code and JUnit XML. Author failure is `not_started`;
interrupted pytest is `interrupted`. Neither becomes a valid measurement. A failed launch
still spends the reserved attempt. The existing parser, structure and coverage checks decide
acceptance. There is no retry hidden inside an attempt; role exploratory tool calls are not
official measurements and cannot write the final report or spend an extra official attempt.

After an unsuccessful attempt, inspect `next` and the sealed pytest evidence. Record the
complete `feedback` event through `executor.py event` using `execution.md`'s schema. The
controller diagnoses from public requirements and virtual evidence; it must not inject
target scoring data or creator implementation into verifier feedback. A subsequent creator
request needs only `case_id` and `hypothesis`; it resumes the same creator. Verifier repair
uses a new `verifier` invocation and spends another attempt without fabricating a revision.

For `NEEDS-DR`, reserve and collect searches through `executor.py event`. Save retrieval
evidence under `OUT/tasks/<case_id>/research/`. A role request may add `research_files`, a
destination-to-source map, but every source must be a hash-sealed `search-result` evidence
file in that directory. Arbitrary files from another role cannot be passed through this field.
Initial files stay immutable; new research augments the role's next input view.

All budgets and final-version rules in `execution.md` remain in force. In particular, the
third failed verification may be followed by the final skill revision, with no fourth test.
The executor refuses dispatch when `next` calls for feedback, retrieval, termination or a
different role. It does not invent a recovery decision or silently change an expected value.

## Stop, recovery and final freeze

```bash
python3 "<skill_dir>/scripts/executor.py" stop "<OUT>"
python3 "<skill_dir>/scripts/executor.py" recover "<OUT>"
```

`stop` sets a permanent fence and removes only this experiment's labelled containers. The
running launcher aborts its model stream and disposes command sessions. Deadline expiry
and SIGTERM also stop workers. A cleanup that cannot be confirmed leaves a STOP fence and
cannot seal a verification as completed. Check the command's exit code; a requested stop
is not proof of shutdown when Docker itself is unavailable.

After a host crash, use `recover` once the old executor process has exited. It obtains the
writer lock, stops owned containers, preserves partial artifacts and closes pending attempts
as interrupted. It never reruns a command or reconstructs a successful measurement from a
leftover XML. Uncollected creator work stays available for inspection, but is not silently
registered or retried. Record its evidenced failure/interruption; do not remove operation
directories, clear STOP or replace a missing creator to continue that run.

Use `executor.py event` for `finish-case`, `freeze` and evaluation journal events. Packaging
and deployment follow `initialization.md`; scored workers still follow the unchanged
`evaluation.md` only after the global freeze. Direct `experiment.py event` mutations are
refused for isolated journals. Old journals remain unchanged and use their recorded helper
version; this executor refuses to adopt them.

Audit `OUT/.executor/` for input manifests, role launch contracts, streamed messages, actual
process receipts and container ownership records. `OUT/tasks/` contains registered practice,
verification and journal evidence. None of the private runtime records enters the library.
The new mechanism does not repair or validate previous benchmark results retroactively.

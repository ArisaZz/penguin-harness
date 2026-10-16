"""Execute OpenSkill construction through isolated roles; never launch target scoring.

Usage: executor.py preflight|init|event|creator|verifier OUT REQUEST.json
       executor.py status|next|stop|recover OUT
The trusted controller owns retrieval, semantic review and final deployment. Workers
cannot mutate this journal. One executor operation owns OUT at a time.
"""

import argparse
import fcntl
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Installed Skill bytes are versioned artifacts; do not add Python cache files there.
sys.dont_write_bytecode = True

import experiment
from artifacts import digest, identifier, read_json, require, strings, tree
from isolation import Boundary, CleanupFailed, copy_files, files, launch_lock, regular, save, stamp, stop_container
from runtime import check_runtime

HERE = Path(__file__).resolve().parent
MODE = "isolated-v1"


@contextmanager
def lock(out):
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".executor.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another executor owns this experiment; use stop to cancel it") from exc
        yield


def event(out, action, **fields):
    return experiment.run("event", out, {"action": action, **fields}, executor=True)


def settings(state):
    require(state["config"].get("execution_mode") == MODE,
            "This executor requires a new isolated-v1 experiment; do not migrate an older run")
    return state["config"]["executor"]


def relative(out, path):
    return path.relative_to(out).as_posix()


def stage(out, mapping, dest):
    require(isinstance(mapping, dict), "An explicit destination-to-source file map is required")
    for name, source in mapping.items():
        # Validate destination independently of source; never copy a directory wholesale.
        rel = Path(name)
        require(rel.parts and not rel.is_absolute() and ".." not in rel.parts, "Invalid staged name")
        target = dest / rel
        require(not target.exists(), "Duplicate staged input")
        target.parent.mkdir(parents=True, exist_ok=True)
        origin = regular(out, source)
        target.write_bytes(origin.read_bytes())
        target.chmod(0o644 | (origin.stat().st_mode & 0o111))


def launch(config, sandbox, work, view, identity, prompt, runtime, deadline, record, on_ready):
    record.mkdir(parents=True, exist_ok=False)
    setup = {**config, "container": sandbox.name, "work": str(work), "writable": str(sandbox.work),
             "readonly": list(map(str, sandbox.readonly)),
             **identity, "runtime": runtime, "deadline": deadline, "prompt": prompt,
             "messages": str(record / "messages.jsonl"), "result": str(record / "result.json")}
    save(record / "launch.json", setup)
    process = None
    started, completed, handshaken = stamp(), False, False
    argv = [config["node"], str(HERE / "launch.mjs"), str(record / "launch.json")]
    with (record / "launcher.log").open("wb") as log:
        try:
            sandbox.check()
            process = subprocess.Popen(argv,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while not selector.select(timeout=0.2):
                    sandbox.check()
                    require(process.poll() is None, "Role launcher failed before identity handshake")
                line = process.stdout.readline()
                require(line, f"Role launcher failed before identity handshake; inspect {record / 'launcher.log'}")
                ready = json.loads(line)
            sandbox.check()
            identity["session_id"] = ready["session_id"]
            handshaken = True
            on_ready(identity)
            process.stdin.write(b"go\n")
            process.stdin.flush()
            process.stdin.close()
            while process.poll() is None:
                sandbox.check()
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            sandbox.check()
            require(process.returncode == 0 and read_json(record / "result.json").get("completed"),
                    f"Role did not finish; inspect {record / 'launcher.log'}")
            completed = True
        finally:
            if process:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                process.stdin.close()
                process.stdout.close()
            receipt = {"argv": argv, "started_at": started, "finished_at": stamp(),
                       "execution_status": "completed" if completed else ("interrupted" if handshaken else "not_started"),
                       "exit_code": process.returncode if process else None}
            save(record / "launcher.process.json", receipt)
    return receipt


class Executor:
    def __init__(self, out, case_id):
        self.out = out
        self.state = experiment.run("status", out)
        self.config = settings(self.state)
        self.cid = identifier(case_id)
        self.config = {**self.config, "image": self.config.get("case_images", {}).get(self.cid, self.config["image"])}
        self.case = self.state["cases"][self.cid]
        self.guidance = experiment.run("next", out)["cases"][self.cid]
        self.deadline = self.guidance["deadline_at"]
        self.root = experiment.case_root(out, self.cid)
        self.private = out / ".executor" / self.cid
        self.control = out / ".executor" / "containers"
        self.stop = out / "STOP"
        require(self.state["phase"] == "construction" and not self.case.get("finished"), "Construction is closed")
        require(not self.stop.exists() and self.guidance["remaining_seconds"] > 0, "Experiment stopped or expired")
        self.runtime = self.state["config"]["runtime"]["construction"]

    def boundary(self, work, readonly):
        return Boundary(self.config, self.control, work, readonly, self.deadline, self.stop)

    def identity(self, role):
        return {"role": role, "agent_id": "openskill_" + uuid.uuid4().hex}

    def scratch(self, identity):
        folder = Path(self.config["penguin_home"]) / self.config["project_id"] / "agents" / identity["agent_id"] / "scratchpad"
        folder.mkdir(parents=True, exist_ok=True)
        return folder.resolve()

    def prepare(self, request):
        plan = self.private / "plan.json"
        if plan.exists():
            result = read_json(plan)
            require(digest(tree(self.private / "inputs")) == result["inputs_sha256"], "Pinned inputs changed")
            return result
        require(self.guidance["next_action"] == "research_and_plan", "Initial plan is no longer allowed")
        names = request["skills"]
        strings(names, "planned skills")
        require(1 <= len(names) <= 4, "Plan must contain 1–4 skills")
        for name in names:
            identifier(name)
        strings(request["outputs"], "public result allowlist")
        for name in request["outputs"]:
            require(not Path(name).is_absolute() and ".." not in Path(name).parts, "Invalid result path")
        inputs = self.private / "inputs"
        for role in ("public", "knowledge", "anchors"):
            require(request.get(role), f"Missing independently reviewed {role} inputs")
            allowed = self.root / "inputs" / role
            require(all(regular(self.out, source).resolve().is_relative_to(allowed.resolve())
                        for source in request[role].values()), f"{role} files must come from {allowed}")
            stage(self.out, request[role], inputs / role)
        # The portable skill contract is part of the creator's input, never the verifier's.
        contract = inputs / "knowledge" / "openskill-contract.md"
        require(not contract.exists(), "Reserved contract filename")
        contract.write_bytes((HERE.parent / "references/skill-contract.md").read_bytes())
        result = {"skills": names, "outputs": request["outputs"], "inputs_sha256": digest(tree(inputs)),
                  "creator": self.identity("creator")}
        save(plan, result)
        return result

    def view(self, role, destination, request, plan):
        inputs = self.private / "inputs"
        copy_files(inputs / "public", destination / "public", files(inputs / "public"))
        source = inputs / ("knowledge" if role == "creator" else "anchors")
        copy_files(source, destination / "research", files(source))
        # Newly retrieved gap evidence is explicitly selected, never a dump of controller history.
        extra = request.get("research_files", {})
        registered = {}
        for search in self.case["searches"]:
            if search.get("result", {}).get("outcome") == "retrieved":
                registered.update(search["result"]["evidence"])
        for source in extra.values():
            require(source in registered and regular(self.out, source).resolve().is_relative_to(
                (self.root / "research").resolve()), "Additional research must be sealed search-result evidence under this Case's research directory")
        if extra:
            experiment.verify_evidence(self.out, {source: registered[source] for source in extra.values()})
        stage(self.out, extra, destination / "additional-research")
        if self.case.get("attempts"):
            latest = self.case["attempts"][-1]
            if latest.get("feedback"):
                save(destination / "feedback.json", latest["feedback"])
                previous = Path(latest["directory"])
                require(tree(previous, allow_empty=True) == latest["evidence"], "Previous verifier evidence changed")
                names = [name for name in ("suite.py", "coverage.json", "report.xml", "pytest.log", "failure.txt")
                         if name in latest["evidence"]]
                copy_files(previous, destination / "previous-verification", names)
        if role == "verifier":
            outputs = self.root / "practice" / f"revision-{len(self.case['revisions']) - 1}"
            copy_files(outputs, destination / "outputs", plan["outputs"])

    def creator(self, request):
        require(self.guidance["next_action"] in ("research_and_plan", "initial_practice", "revise_skill", "repeat_practice"),
                "Creator is not the next allowed action")
        plan = self.prepare(request)
        number = len(self.case["revisions"])
        operation = self.private / f"practice-{number}"
        require(not operation.exists(), "Uncollected practice exists; inspect it, do not silently rerun")
        work = self.private / "creator-work"
        work.mkdir(parents=True, exist_ok=True)
        view = operation / "view"
        self.view("creator", view, request, plan)
        identity = plan["creator"]
        identity_file = self.private / "creator.json"
        if identity_file.exists():
            identity = read_json(identity_file)
        elif "creator_session_id" in self.case:
            raise ValueError("Persistent creator identity is missing; never replace it with a fresh session")
        prompt = (f"Public task and research: {view}. Fixed skill names: {json.dumps(plan['skills'])}. "
            f"Write reusable skills and contracts to {work}/skills. Follow research/openskill-contract.md. "
            f"Hypothesis: {request['hypothesis']}. The executor will freeze your skills for practice in a fresh "
            "environment and collect actual results. No target grading or network is available. ")
        mode = self.config.get("practice_mode", "agent")
        if mode == "command":
            prompt += (f"Write {work}/practice.json with an argv string array. "
                "Use ${SKILLS}, ${INPUTS} and ${OUTPUTS}; the executor substitutes absolute paths. "
                "At least one argument must name a real file under ${SKILLS}/. "
                f"Execute the skills to produce these paths under ${{OUTPUTS}}: {json.dumps(plan['outputs'])}.")
        else:
            prompt += "Prepare skills only in this turn. The executor will resume you to apply them with read-only skills."

        def ready(actual):
            if "creator_session_id" not in self.case:
                self.case = event(self.out, "plan", case_id=self.cid, skills=plan["skills"],
                                  creator_session_id=actual["session_id"])["cases"][self.cid]
            else:
                require(actual["session_id"] == self.case["creator_session_id"], "Creator identity changed")
            save(identity_file, actual)

        with self.boundary(work, [view, self.scratch(identity)]) as sandbox:
            launch(self.config, sandbox, work, view, identity, prompt, self.runtime, self.deadline,
                   operation / "author", ready)
        # No author process survives to modify these inputs during the measured execution.
        skills = operation / "skills"
        copy_files(work / "skills", skills, files(work / "skills"))
        outputs = operation / "outputs"
        outputs.mkdir()
        if mode == "command":
            command = read_json(regular(work, "practice.json"))["argv"]
            require(isinstance(command, list) and command and
                    all(isinstance(arg, str) and "\0" not in arg for arg in command) and command[0],
                    "Practice argv must be a nonempty string array")
            referenced = [arg[len("${SKILLS}/"):] for arg in command if arg.startswith("${SKILLS}/")]
            require(referenced, "Command practice must reference a frozen skill file")
            for source in referenced:
                regular(skills, source)
            substitutions = {"${SKILLS}": str(skills), "${INPUTS}": str(view / "public"), "${OUTPUTS}": str(outputs)}
            for key, value in substitutions.items():
                command = [arg.replace(key, value) for arg in command]
            with self.boundary(outputs, [skills, view]) as sandbox:
                receipt = sandbox.run(command, operation / "practice.log")
            if self.state["config"].get("stop_on_recurrence"):
                require(receipt["execution_status"] == "completed" and receipt["exit_code"] == 0,
                        "Official practice command failed; stop_on_recurrence is enabled")
            evidence = [operation / "practice.process.json", operation / "practice.log"]
        else:
            prompt = (f"Apply the frozen skills under {skills} to the public task at {view}/public. "
                      f"Read their SKILL.md files and use their procedures. Write {json.dumps(plan['outputs'])} "
                      f"under {outputs}. This is the official practice execution. Skills and research are read-only; "
                      "do not revise them or patch results from an earlier run. Report limitations honestly.")
            with self.boundary(outputs, [work, skills, view, self.scratch(identity)]) as sandbox:
                config = {**self.config, "stop_on_tool_failure": self.state["config"].get("stop_on_recurrence", False)}
                receipt = launch(config, sandbox, work, view, identity, prompt, self.runtime, self.deadline,
                                 operation / "execution", ready)
            command = receipt["argv"]
            evidence = [operation / "execution/launcher.process.json", operation / "execution/messages.jsonl"]
            (operation / "practice.log").write_bytes((operation / "execution/messages.jsonl").read_bytes())
        # Import only declared result files, never the creator's tree or execution logs.
        target = self.root / "practice" / f"revision-{number}"
        copy_files(outputs, target, plan["outputs"])
        live = self.root / "skills"
        if live.exists():
            require(digest(tree(live)) == self.case["revisions"][-1]["skills_sha256"], "Live skill bytes changed outside executor")
            shutil.rmtree(live)
        copy_files(skills, live, files(skills))
        log = self.root / "executions" / f"run-{number}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes((operation / "practice.log").read_bytes())
        receipt_path = log.with_suffix(".json")
        save(receipt_path, {"creator_session_id": identity["session_id"], "skills_sha256": digest(tree(live)),
             "output_directory": relative(self.out, target), "commands": [json.dumps(command)],
             "exit_code": receipt["exit_code"], "started_at": receipt["started_at"], "finished_at": receipt["finished_at"],
             "isolation": MODE, "practice_mode": mode,
             "evidence": [relative(self.out, log), *[relative(self.out, path) for path in evidence],
                 relative(self.out, operation / "author/messages.jsonl")]})
        return event(self.out, "revision", case_id=self.cid, creator_session_id=identity["session_id"],
                     hypothesis=request["hypothesis"], execution_record=relative(self.out, receipt_path))

    def verifier(self, request):
        require(self.guidance["next_action"] in ("begin_verification", "repair_verifier"),
                "Verifier is not the next allowed action")
        plan = self.prepare(request)
        # Spend budget before any staging, launcher or model work can fail.
        reserved = event(self.out, "begin-verification", case_id=self.cid)
        attempt = reserved["cases"][self.cid]["attempts"][-1]
        folder = Path(attempt["directory"])
        folder.mkdir(parents=True)
        operation = self.private / f"verify-{attempt['number']}"
        work, view = operation / "author-work", operation / "view"
        work.mkdir(parents=True)
        identity = self.identity("verifier")
        outcome, code, failure = "not_started", None, None
        try:
            self.view("verifier", view, request, plan)
            prompt = (f"Use only {view}/public, {view}/research, any additional research and {view}/outputs. "
                f"Write {work}/suite.py with at most {self.state['config']['max_virtual_tests']} deterministic pytest tests, "
                f"and {work}/coverage.json mapping every public requirement to JUnit classname::name ids. "
                "Each entry needs requirement, required=true, source, status=covered|unverified, tests=[ids]. "
                "JUnit ids use suite::test_function (with any parameter suffix). "
                "Derive expected results from independent anchors, never by copying the observed output. "
                "At least 60% of checks must validate actual deliverables. Wrong or missing deliverables "
                "are assertion failures; setup/import errors are verifier failures. Do not skip, xfail, "
                "deselect or weaken required checks to obtain a pass. Use no randomness, network or LLM judgments. "
                "Preserve earlier expectations unless independent evidence establishes an oracle correction. "
                "Use OPENSKILL_INPUTS and OPENSKILL_OUTPUTS environment variables to locate inputs/results. "
                "The executor runs the official pytest attempt. Do not generate report.xml or claim a pass. "
                "You have no creator implementation or conversation. Report missing anchors honestly.")
            with self.boundary(work, [view, self.scratch(identity)]) as sandbox:
                launch(self.config, sandbox, work, view, identity, prompt, self.runtime, self.deadline,
                       operation / "author", lambda actual: save(operation / "identity.json", actual))
            suite = operation / "suite"
            copy_files(work, suite, ["suite.py", "coverage.json"])
            copy_files(suite, folder, ["suite.py", "coverage.json"])
            results = operation / "results"
            results.mkdir()
            guard = operation / "guard"
            guard.mkdir()
            (guard / "openskill_limit.py").write_text(
                "import pytest\ndef pytest_collection_finish(session):\n"
                f"    if len(session.items) > {self.state['config']['max_virtual_tests']}:\n"
                "        pytest.exit('OpenSkill virtual test budget exceeded before execution', returncode=4)\n")
            command = ["/usr/bin/env", "OPENSKILL_INPUTS=" + str(view / "public"),
                       "OPENSKILL_OUTPUTS=" + str(view / "outputs"), "PYTHONPATH=" + str(guard),
                       "python3", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "openskill_limit",
                       "--rootdir=" + str(suite), str(suite / "suite.py"), "--junitxml=" + str(results / "report.xml")]
            with self.boundary(results, [suite, view, guard]) as sandbox:
                outcome = "interrupted"
                receipt = sandbox.run(command, folder / "pytest.log")
                outcome, code = receipt["execution_status"], receipt["exit_code"]
            if (results / "report.xml").exists():
                copy_files(results, folder, ["report.xml"])
        except CleanupFailed:
            raise  # Never seal evidence while a worker might still be writing it.
        except (Exception, KeyboardInterrupt) as exc:
            failure = f"{type(exc).__name__}: {exc}"
            (folder / "failure.txt").write_text(failure + "\n", encoding="utf-8")
        save(folder / "executor.json", {"isolation": MODE, "execution_status": outcome,
             "pytest_exit_code": code, "verifier_session_id": identity.get("session_id"), "failure": failure})
        result = event(self.out, "finish-verification", case_id=self.cid, execution_status=outcome,
                       pytest_exit_code=code, verifier_session_id=identity.get("session_id", "dispatch-" + identity["agent_id"]))
        return result


def stop(out, state):
    config = settings(state)
    (out / "STOP").write_text(stamp() + "\n")
    control = out / ".executor" / "containers"
    with launch_lock(control):
        for record in control.glob("openskill-*.json"):
            data = read_json(record)
            stop_container(config["docker"], control, data["container"])
    return {"stopped": True, "fence": str(out / "STOP")}


def preflight(out, request, full=False):
    """Check every declared construction image without a journal, role or model call."""
    config = settings({"config": request})
    require(config.get("sanitized_image") is True, "Review and attest the construction images first")
    require(not (out / "STOP").exists() and not (out / "journal").exists(),
            "Preflight requires a fresh directory, not an existing or stopped experiment")
    report = out / "preflight.json"
    require(not report.exists(), "Never overwrite a preflight; use a fresh directory")
    strings(request["case_ids"], "construction cases")
    result = {"started_at": stamp(), "status": "running", "docker": config["docker"],
              "cases": [], "model_requests": 0, "scope": "runtime_and_environments" if full else "environments"}
    save(report, result)
    try:
        if full:
            result["runtime"] = check_runtime(out, request, session=True)
            if config.get("runtime_manifest"):
                manifest = read_json(Path(config["runtime_manifest"]))
                require(manifest["runtime_fingerprint"] == result["runtime"]["fingerprint"],
                        "Prepared runtime manifest does not match the configured SDK")
            save(report, result)
        for case_id in request["case_ids"]:
            identifier(case_id)
            case_config = {**config, "image": config.get("case_images", {}).get(case_id, config["image"])}
            work = out / ".executor" / "preflight" / case_id
            work.mkdir(parents=True, exist_ok=False)
            deadline = (datetime.now(timezone.utc) + timedelta(seconds=330)).isoformat()
            boundary = Boundary(case_config, out / ".executor/containers", work, [], deadline, out / "STOP")
            row = {"case_id": case_id, "image": case_config["image"], "status": "checking",
                   "container_record": relative(out, boundary.record)}
            result["cases"].append(row)
            save(report, result)
            with boundary:
                row["status"] = "ready"
            row["cleanup_confirmed"] = True
            save(report, result)
        result["status"] = "ready"
    except BaseException as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        if result["cases"]:
            result["cases"][-1]["status"] = "failed"
        (out / "STOP").write_text("Environment preflight failed; no construction may start.\n")
        raise
    finally:
        result["finished_at"] = stamp()
        save(report, result)
    return result


def fail_experiment(out, state, error):
    """Preserve the first failure and fence the entire experiment before cleanup."""
    record = out / ".executor" / "failure.json"
    if not record.exists():
        save(record, {"at": stamp(), "error_type": type(error).__name__, "error": str(error)})
    return stop(out, state)


def run(command, out, request=None):
    out = Path(out).resolve()
    if command in ("status", "next"):
        result = experiment.run(command, out)
        result["stopped"] = (out / "STOP").exists()
        if result["stopped"] and command == "next":
            result["next_action"] = "stopped"
            for case in result["cases"].values():
                case["next_action"] = "stopped"
        return result
    if command == "stop":
        state = (experiment.run("status", out) if (out / "journal").exists() else
                 {"config": {"execution_mode": MODE, "executor": {"docker": read_json(out / "preflight.json")["docker"]}}})
        return stop(out, state)
    with lock(out):
        if command == "preflight":
            return preflight(out, request)
        if command == "init":
            require(request.get("execution_mode") == MODE, "Set execution_mode to isolated-v1")
            config = settings({"config": request})
            for name in ("docker", "node", "sdk", "penguin_home"):
                require(Path(config[name]).is_absolute() and Path(config[name]).exists(), f"Invalid {name} path")
            identifier(config["project_id"])
            require((Path(config["penguin_home"]) / config["project_id"] / ".project_config.toml").is_file(),
                    "Configure the construction model in the existing Penguin Project first")
            require(config.get("sanitized_image") is True, "Review and attest the image contains no graders, solutions or prior skills")
            require(config.get("practice_mode", "agent") in ("agent", "command"), "Invalid practice_mode")
            require(not (out / "STOP").exists(), "Never reuse a stopped experiment")
            require(type(request.get("stop_on_recurrence", False)) is bool, "stop_on_recurrence must be boolean")
            preflight(out, request, full=True)
            return experiment.run("init", out, request, executor=True)
        state = experiment.run("status", out)
        settings(state)
        if command == "recover":
            stop(out, state)
            for cid, case in state["cases"].items():
                if case.get("pending"):
                    folder = Path(case["attempts"][-1]["directory"])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / "recovery.txt").write_text("Host interruption; workers stopped. No completed measurement inferred.\n")
                    state = event(out, "finish-verification", case_id=cid, execution_status="interrupted",
                                  verifier_session_id=case["attempts"][-1].get("verifier_session_id") or "host-interruption")
            return state
        if command == "event":
            require(request["action"] not in ("plan", "revision", "begin-verification", "finish-verification"),
                    "Role transitions are owned by the executor")
            if (out / "STOP").exists():
                require(request["action"] in ("feedback", "finish-case", "search-result"), "Stopped experiment cannot restart")
            return event(out, **request)
        if command in ("creator", "verifier"):
            require(not (out / "STOP").exists(), "Stopped experiment cannot restart")
            try:
                ready = read_json(out / "preflight.json")
                require(ready.get("runtime", {}).get("fingerprint"),
                        "This executor requires a runtime-checked init; resume old runs with their recorded Skill")
                check_runtime(out, state["config"], expected=ready["runtime"]["fingerprint"])
            except BaseException as error:
                fail_experiment(out, state, error)
                raise
            try:
                worker = Executor(out, request["case_id"])
                result = worker.creator(request) if command == "creator" else worker.verifier(request)
                if command == "verifier" and state["config"].get("stop_on_recurrence"):
                    attempt = result["cases"][request["case_id"]]["attempts"][-1]
                    require(attempt["execution_status"] == "completed" and attempt["result"]["status"] == "ok",
                            "Verification produced no valid measurement; stop_on_recurrence is enabled")
                return result
            except BaseException as error:
                if state["config"].get("stop_on_recurrence"):
                    fail_experiment(out, state, error)
                raise
        raise ValueError("Unknown executor operation")


def main():
    def cancelled(_signum, _frame):
        raise KeyboardInterrupt("Executor received a termination signal")
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "init", "event", "creator", "verifier", "status", "next", "stop", "recover"])
    parser.add_argument("out", type=Path)
    parser.add_argument("request", nargs="?", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.command, args.out, read_json(args.request) if args.request else None)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"OpenSkill executor: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Record OpenSkill construction and guard phase changes; never run or score an agent."""

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
from artifacts import check_case, check_library, digest, identifier, read_json, require, strings, tree
import workflow

spec = importlib.util.spec_from_file_location("virtual_results", Path(__file__).with_name("virtual-results.py"))
virtual_results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(virtual_results)


def now():
    return datetime.now(timezone.utc).isoformat()


def positive(value, label):
    require(type(value) is int and value > 0, f"{label} must be a positive integer")


def nonempty(value, label):
    require(isinstance(value, str) and value.strip(), f"Missing {label}")


def load(out):
    require(not (out / "journal").is_symlink(), "Journal must not be a symlink")
    records = sorted((out / "journal").glob("*.json"))
    require(records, "No journal: use init for a new experiment")
    previous = None
    for number, path in enumerate(records, 1):
        require(not path.is_symlink() and path.name == f"{number:06d}.json", "Broken journal sequence")
        record = read_json(path)
        require(record["sequence"] == number and record["previous"] == previous, "Broken journal chain")
        previous = digest(record)
    return copy.deepcopy(record["state"]), len(records), previous


@contextmanager
def locked(out):
    require(out.is_dir() and not out.is_symlink(), "Expected a real experiment directory")
    lock = out / ".journal.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError("Journal is locked; verify the owner stopped before recovering the lock") from None
    try:
        yield
    finally:
        lock.rmdir()


def append(out, state, request, sequence, previous):
    folder = out / "journal"
    require(not folder.is_symlink(), "Journal must not be a symlink")
    folder.mkdir(exist_ok=True)
    record = {"sequence": sequence + 1, "previous": previous, "time": now(),
              "request": request, "state": state}
    # Publish a complete file without replacing any earlier event, even after a crash.
    fd, name = tempfile.mkstemp(prefix=".event-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, folder / f"{sequence + 1:06d}.json")
    finally:
        os.unlink(name)


def initialize(config):
    config = copy.deepcopy(config)
    identifier(config["benchmark_id"])
    identifier(config["test_agent_id"])
    strings(config["case_ids"], "construction cases")
    for case in config["case_ids"]:
        identifier(case)
    test = config.get("test_benchmark_id")
    if test is not None:
        identifier(test)
        require(test != config["benchmark_id"], "Held-out Benchmark must differ from construction Benchmark")
        strings(config.get("test_case_ids"), "test cases")
        for case in config["test_case_ids"]:
            identifier(case)
    else:
        require(not config.get("test_case_ids"), "test_case_ids needs test_benchmark_id")
    defaults = {"runs": 1, "max_refinement_retries": 3, "max_targeted_searches": 3,
                "max_virtual_tests": 60, "construction_timeout_minutes": 30,
                "include_baseline": True, "include_reader_control": False}
    for key, value in defaults.items():
        config.setdefault(key, value)
        if key in ("include_baseline", "include_reader_control"):
            require(type(config[key]) is bool, f"{key} must be boolean")
        else:
            positive(config[key], key)
    require(config["max_virtual_tests"] <= 60, "At most 60 virtual tests")
    for role in ("construction", "target"):
        for key in ("provider", "model_id", "thinking_level"):
            nonempty(config["runtime"][role][key], f"{role}.{key}")
    return {"schema_version": 2, "phase": "construction", "config": config, "cases": {}}


def case_root(out, case_id):
    path = out / "tasks" / identifier(case_id)
    require(path.resolve().is_relative_to(out.resolve()), "Case path escapes experiment")
    return path


def prefixes(out, state):
    extra = state["config"].get("practice_prefixes", [])
    strings(extra, "practice prefixes", allow_empty=True)
    return ["/opt/openskill-skills", str(out.resolve()), *extra]


def expired(case, config):
    return workflow.clock(case, config, datetime.now(timezone.utc))["remaining_seconds"] == 0


def coverage_complete(path, result):
    if not path.exists() or result["status"] != "ok":
        return False
    coverage = read_json(path)
    require(isinstance(coverage, list) and coverage, "Coverage must list public requirements")
    passed = {f'{item["classname"]}::{item["name"]}' for item in result["tests"] if item["status"] == "passed"}
    seen = set()
    complete = True
    for entry in coverage:
        nonempty(entry["requirement"], "requirement")
        require(entry["requirement"] not in seen, "Duplicate coverage requirement")
        seen.add(entry["requirement"])
        require(type(entry["required"]) is bool, "Coverage required must be boolean")
        require(entry["status"] in ("covered", "unverified"), "Invalid coverage status")
        strings(entry["tests"], "coverage test ids", allow_empty=True)
        if entry["required"]:
            complete &= (entry["status"] == "covered" and isinstance(entry.get("source"), str)
                         and bool(entry["source"].strip()) and bool(entry["tests"])
                         and set(entry["tests"]).issubset(passed))
    return bool(complete and any(entry["required"] for entry in coverage))


def evaluation_plan(state):
    config = state["config"]
    benchmark = config.get("test_benchmark_id") or config["benchmark_id"]
    cases = config.get("test_case_ids") if config.get("test_benchmark_id") else config["case_ids"]
    variants = ["baseline", "final"] if config["include_baseline"] else ["final"]
    if config["include_reader_control"]:
        variants.insert(-1, "reader_control")
    return [{"variant": variant, "benchmark_id": benchmark, "case_id": case, "run": run}
            for variant in variants for case in cases for run in range(1, config["runs"] + 1)]


def verify_history(out, root, case):
    for revision in case["revisions"]:
        number = revision["revision"]
        require(digest(tree(root / "revisions" / f"revision-{number}")) == revision["skills_sha256"],
                "Historical skill revision changed")
        require(digest(tree(root / "practice" / f"revision-{number}")) == revision["outputs_sha256"],
                "Historical practice output changed")
        verify_evidence(out, revision["execution_evidence"])
    for attempt in case["attempts"]:
        folder = Path(attempt["directory"])
        actual = tree(folder, allow_empty=True) if folder.exists() else {}
        require(actual == attempt["evidence"], "Historical verification evidence changed")
        if "feedback" in attempt:
            verify_evidence(out, attempt["feedback"]["evidence"])
    for search in case["searches"]:
        if "result" in search:
            verify_evidence(out, search["result"]["evidence"])
    if "termination_evidence" in case:
        verify_evidence(out, case["termination_evidence"])


def report_path(out, relative):
    path = out / relative
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts
            and path.resolve().is_relative_to(out.resolve()) and path.is_file()
            and not path.is_symlink(), "Report must exist as a regular file inside OUT")
    return path


def seal_evidence(out, paths):
    strings(paths, "evidence paths")
    result = {}
    for relative in paths:
        payload = report_path(out, relative).read_bytes()
        require(payload.strip(), "Evidence file is empty")
        result[relative] = hashlib.sha256(payload).hexdigest()
    return result


def verify_evidence(out, evidence):
    require(seal_evidence(out, list(evidence)) == evidence, "Recorded execution or recovery evidence changed")


def execution_receipt(out, root, case, config, revision, skills, relative):
    path = report_path(out, relative)
    require(path.resolve().is_relative_to(root.resolve()), "Execution receipt must belong to its Case")
    record = read_json(path)
    require(record["creator_session_id"] == case["creator_session_id"], "Execution used another creator")
    require(record["skills_sha256"] == digest(skills), "Execution receipt describes different skills")
    expected = root / "practice" / f"revision-{revision}"
    require(record["output_directory"] == expected.relative_to(out).as_posix(),
            "Execution receipt describes another practice directory")
    strings(record["commands"], "executed commands")
    require(type(record["exit_code"]) is int, "Execution receipt needs the actual process exit code")
    started, finished = (datetime.fromisoformat(record[k]) for k in ("started_at", "finished_at"))
    require(started.tzinfo is not None and finished.tzinfo is not None, "Execution timestamps need a timezone")
    earliest = (case["attempts"][-1]["feedback"]["recorded_at"] if revision else case["started_at"])
    require(datetime.fromisoformat(earliest) <= started <= finished <= datetime.now(timezone.utc),
            "Practice execution must follow its feedback and cannot be in the future")
    deadline = workflow.clock(case, config, datetime.now(timezone.utc))["deadline_at"]
    require(finished <= datetime.fromisoformat(deadline), "Practice execution exceeded the construction deadline")
    evidence = seal_evidence(out, record["evidence"])
    evidence.update(seal_evidence(out, [relative]))
    return evidence


def stop_record(out, case, reason, request):
    record = read_json(report_path(out, request["record"]))
    require(record["reason"] == reason, "Stop evidence names another reason")
    require(record["workers_stopped"] is True, "Stop role writes before closing the Case")
    nonempty(record["cause"], "stop cause")
    evidence = seal_evidence(out, record["evidence"])
    evidence.update(seal_evidence(out, [request["record"]]))
    if reason in ("verifier_failure", "environment_failure"):
        require(record["recoverable"] is False, "Recoverable failures must continue within the budget")
        strings(record.get("recovery_attempts", []), "recovery attempts", allow_empty=True)
        if not record.get("recovery_attempts"):
            nonempty(record.get("why_recovery_impossible"), "why recovery cannot be attempted")
    if reason == "verifier_failure":
        decision = workflow.feedback(case)
        last = case["attempts"][-1]
        require(decision["next_action"] == "repair_verifier", "Skill/practice faults need their recorded recovery")
        require("skill_structure" not in workflow.issues(last), "A skill structural fault is not a verifier failure")
        if "assertion_failure" in workflow.issues(last):
            nonempty(decision.get("oracle_correction"), "independent evidence of an incorrect verifier")
    if reason == "context_budget":
        used, limit = record["context_used"], record["context_limit"]
        require(type(used) is int and type(limit) is int and limit > 0 and used >= .9 * limit,
                "Context stop requires an observed usage at or above 90%")
    if reason == "interrupted":
        require(record["interruption"] in ("user_stop", "creator_unavailable", "host_interruption"),
                "Interruption needs an external cause; time exhaustion uses time_budget")
    case["termination_evidence"] = evidence


def validate_matrices(out, state, relative):
    matrices = read_json(report_path(out, relative))
    require(isinstance(matrices, list), "Matrix record must be a list")
    expected = {(p["variant"], p["benchmark_id"], p["case_id"], p["run"]) for p in state["evaluation_plan"]}
    seen = set()
    config = state["config"]
    for matrix in matrices:
        variant, benchmark = matrix["variant"], matrix["benchmark_id"]
        require(variant in state["measured_states"], "Unknown measured variant")
        for cell in matrix["cells"]:
            positive(cell["run"], "Run index")
            positive(cell["expected_version"], "Measured State version")
            key = (variant, benchmark, cell["case_id"], cell["run"])
            require(key in expected and key not in seen, "Unexpected or duplicate evaluation cell")
            require(cell["status"] == "ok" and cell["agent_id"] == config["test_agent_id"], "Invalid scored cell")
            require(cell["expected_version"] == state["measured_states"][variant]["version"], "State version mismatch")
            require(all(cell[k] == config["runtime"]["target"][k]
                        for k in ("provider", "model_id", "thinking_level")), "Evaluation runtime mismatch")
            require(type(cell["score"]) in (int, float) and math.isfinite(cell["score"])
                    and 0 <= cell["score"] <= 100, "Invalid score")
            nonempty(cell["session_id"], "evaluation session id")
            seen.add(key)
    require(seen == expected, "Incomplete evaluation matrix")
    return digest(matrices)


def apply_event(out, state, request):
    require(state["schema_version"] == 2,
            "Historical journal is read-only here; resume with its recorded Skill version, never migrate it")
    kind = request["action"]
    config = state["config"]
    if kind in ("freeze", "begin-evaluation", "finish-evaluation"):
        if kind == "freeze":
            require(state["phase"] == "construction", "Freeze only from construction")
            require(set(state["cases"]) == set(config["case_ids"]), "Not every construction Case started")
            require(all(c.get("finished") and c.get("deployable") for c in state["cases"].values()),
                    "Every Case must finish with a valid, uncontaminated last revision")
            plans = {key: case["skills"] for key, case in state["cases"].items()}
            library = check_library(out / "library", plans, prefixes(out, state))
            for case_id, case in state["cases"].items():
                verify_history(out, case_root(out, case_id), case)
                require(library["cases"][case_id]["sha256"] == case["final_sha256"],
                        "Library is not the last recorded revision")
            state.update(phase="frozen", library=library, frozen_at=now())
            state["evaluation_plan"] = evaluation_plan(state)
        else:
            require(state["phase"] in ("frozen", "evaluation"), "Evaluation requires global freeze")
            require(digest(tree(out / "library")) == state["library"]["sha256"], "Frozen library changed")
            if kind == "begin-evaluation":
                require(state["phase"] == "frozen", "Evaluation requires global freeze")
                variants = {p["variant"] for p in state["evaluation_plan"]}
                require(set(request["states"]) == variants, "Snapshot variants differ from evaluation plan")
                for snapshot in request["states"].values():
                    positive(snapshot["version"], "State version")
                    require(isinstance(snapshot["sha256"], str) and
                            re.fullmatch(r"[0-9a-f]{64}", snapshot["sha256"]), "Invalid State SHA-256 digest")
                state["measured_states"] = request["states"]
                state["phase"] = "evaluation"
            else:
                require(state["phase"] == "evaluation", "No evaluation is in progress")
                require(request["outcome"] in ("complete", "incomplete"), "Invalid evaluation outcome")
                nonempty(request["record"], "evaluation matrix/report path")
                report_path(out, request["record"])
                if request["outcome"] == "complete":
                    state["matrix_sha256"] = validate_matrices(out, state, request["record"])
                state.update(phase="evaluated", evaluation_outcome=request["outcome"],
                             evaluation_record=request["record"])
        return

    require(state["phase"] == "construction", "Construction is closed after freeze")
    case_id = identifier(request["case_id"])
    require(case_id in config["case_ids"], "Case is not in the construction set")
    root = case_root(out, case_id)
    if kind == "start-case":
        require(case_id not in state["cases"], "Case already started; resume its recorded state")
        state["cases"][case_id] = {"started_at": now(), "attempts": [], "revisions": [], "searches": []}
        return
    case = state["cases"][case_id]
    require(not case.get("finished"), "Case is closed")
    if kind not in ("revision", "finish-verification", "search-result", "finish-case"):
        require(not expired(case, config), "Construction time budget exhausted")
    if kind == "plan":
        require("skills" not in case, "Skill plan and creator are fixed")
        strings(request["skills"], "planned skills")
        require(1 <= len(request["skills"]) <= 4, "Plan must contain 1–4 skills")
        for name in request["skills"]:
            identifier(name)
        nonempty(request["creator_session_id"], "creator session")
        case.update(skills=request["skills"], creator_session_id=request["creator_session_id"])
    elif kind == "revision":
        require(request["creator_session_id"] == case["creator_session_id"], "Resume the same creator")
        require(not case.get("pending"), "Cannot revise while verification is active")
        if case["revisions"]:
            require(case["attempts"] and case["attempts"][-1].get("finished"), "Verify before another revision")
            last = case["attempts"][-1]
            require(last["revision"] == len(case["revisions"]) - 1, "Current revision has not been verified")
            require(not last["accepted"], "Stop on a complete virtual pass")
            decision = workflow.research_ready(case)
            require(decision["next_action"] in ("revise_skill", "repeat_practice"),
                    "Repair the verifier in a new attempt without inventing a practice revision")
        require(len(case["revisions"]) <= config["max_refinement_retries"], "Practice budget exhausted")
        revision = len(case["revisions"])
        skills = tree(root / "skills")
        outputs = tree(root / "practice" / f"revision-{revision}")
        change = "initial" if not revision else decision["next_action"]
        if revision:
            changed = digest(skills) != case["revisions"][-1]["skills_sha256"]
            require(changed == (change == "revise_skill"),
                    "Skill repair must change skills; unchanged skills are repeat_practice, not refinement")
        nonempty(request["hypothesis"], "revision hypothesis")
        execution = execution_receipt(out, root, case, config, revision, skills, request["execution_record"])
        snapshot = root / "revisions" / f"revision-{revision}"
        if snapshot.exists():
            require(tree(snapshot) == skills, "Revision snapshot exists with different content")
        else:
            shutil.copytree(root / "skills", snapshot)
        case["revisions"].append({"revision": revision, "skills_sha256": digest(skills),
                                  "outputs_sha256": digest(outputs), "hypothesis": request["hypothesis"],
                                  "change_kind": change, "execution_evidence": execution})
    elif kind == "begin-verification":
        require(case["revisions"] and not case.get("pending"), "Need a revision and no active verification")
        require(len(case["attempts"]) < config["max_refinement_retries"], "Verification budget exhausted")
        require(not case["attempts"] or not case["attempts"][-1]["accepted"], "Stop on a complete virtual pass")
        revision = case["revisions"][-1]
        if case["attempts"] and case["attempts"][-1]["revision"] == revision["revision"]:
            require(workflow.research_ready(case)["next_action"] == "repair_verifier",
                    "Apply feedback and re-execute practice before another verification")
        require(digest(tree(root / "skills")) == revision["skills_sha256"], "Unrecorded skill revision")
        require(digest(tree(root / "practice" / f'revision-{revision["revision"]}')) == revision["outputs_sha256"],
                "Practice outputs changed after revision registration")
        number = len(case["attempts"]) + 1
        folder = root / "verify" / f"attempt-{number}"
        require(not folder.exists(), "Attempt directory already exists; do not overwrite evidence")
        verifier = request.get("verifier_session_id")
        if verifier is not None:
            nonempty(verifier, "verifier session")
            require(verifier != case["creator_session_id"], "Verifier must be a separate session")
        case["attempts"].append({"number": number, "revision": revision["revision"],
                                 "skill_sha256": revision["skills_sha256"],
                                 "directory": str(folder), "verifier_session_id": verifier,
                                 "finished": False})
        case["pending"] = number
    elif kind == "finish-verification":
        require(case.get("pending"), "No verification is active")
        attempt = case["attempts"][-1]
        verifier = request.get("verifier_session_id") or attempt["verifier_session_id"]
        nonempty(verifier, "verifier session")
        require(verifier != case["creator_session_id"] and
                (attempt["verifier_session_id"] is None or verifier == attempt["verifier_session_id"]),
                "Verification session differs from its reservation or creator isolation")
        revision = case["revisions"][attempt["revision"]]
        require(digest(tree(root / "skills")) == attempt["skill_sha256"], "Skills changed during verification")
        require(digest(tree(root / "practice" / f'revision-{attempt["revision"]}')) == revision["outputs_sha256"],
                "Verifier changed practice outputs")
        folder = Path(attempt["directory"])
        require(folder.resolve().is_relative_to(root.resolve()), "Verification path escapes Case")
        execution_status = request["execution_status"]
        require(execution_status in ("completed", "interrupted", "not_started"), "Invalid verification execution status")
        if execution_status == "completed":
            require(type(request["pytest_exit_code"]) is int, "pytest_exit_code must be an integer")
            result = virtual_results.read_result(folder / "report.xml", request["pytest_exit_code"], config["max_virtual_tests"])
        else:
            require(request.get("pytest_exit_code") is None, "Uncompleted pytest has no completed exit code")
            result = virtual_results.failed("verification_" + execution_status, "No completed virtual measurement")
        evidence = tree(folder, allow_empty=True) if folder.exists() else {}
        coverage_error = None
        try:
            coverage = coverage_complete(folder / "coverage.json", result)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            coverage, coverage_error = False, str(exc)
        structure_error = None
        try:
            check_case(root / "skills", case_id, case["skills"], prefixes(out, state))
            structure = True
        except (OSError, ValueError, KeyError, TypeError) as exc:
            structure, structure_error = False, str(exc)
        accepted = (result["status"] == "ok" and result["pass_rate"] == 1 and coverage and structure
                    and "suite.py" in evidence)
        attempt.update(finished=True, execution_status=execution_status, result=result, evidence=evidence, coverage_complete=coverage,
                       coverage_error=coverage_error, structure_valid=structure, structure_error=structure_error,
                       accepted=accepted,
                       verifier_session_id=verifier)
        case.pop("pending")
    elif kind == "feedback":
        require(case["attempts"] and not case.get("pending"), "Finish verification before diagnosing it")
        workflow.validate_feedback(case, request)
        evidence = seal_evidence(out, request["evidence"])
        case["attempts"][-1]["feedback"] = {**request, "evidence": evidence, "recorded_at": now()}
    elif kind == "targeted-search":
        require(case["attempts"] and case["attempts"][-1].get("finished")
                and not case["attempts"][-1]["accepted"], "Gap retrieval follows failed virtual verification")
        require(request["classification"] == "NEEDS-DR", "Only knowledge gaps trigger targeted retrieval")
        require(workflow.feedback(case)["classification"] == "NEEDS-DR", "Search must follow the recorded gap diagnosis")
        require(case["attempts"][-1]["revision"] == case["revisions"][-1]["revision"],
                "Verify the new practice execution before diagnosing another gap")
        require(len(case["searches"]) < config["max_targeted_searches"], "Targeted search budget exhausted")
        nonempty(request["query"], "sanitized query")
        forbidden = [config["benchmark_id"], config.get("test_benchmark_id"), *config["case_ids"],
                     *config.get("test_case_ids", [])]
        require(not any(word and word.lower() in request["query"].lower() for word in forbidden),
                "Query contains a Benchmark/Case identifier")
        case["searches"].append({"query": request["query"], "time": now(),
                                "attempt": case["attempts"][-1]["number"]})
    elif kind == "search-result":
        positive(request["search"], "Search index")
        require(request["search"] <= len(case["searches"]), "No such reserved search")
        search = case["searches"][request["search"] - 1]
        require("result" not in search, "Search result is sealed")
        require(not case.get("pending") and search["attempt"] == case["attempts"][-1]["number"],
                "Collect the search result before the next attempt")
        require(request["outcome"] in ("retrieved", "unavailable"), "Invalid retrieval outcome")
        nonempty(request["summary"], "retrieval finding or failure")
        if request["outcome"] == "retrieved":
            strings(request["sources"], "retrieved source URLs")
        search["result"] = {**request, "evidence": seal_evidence(out, request["evidence"])}
    elif kind == "finish-case":
        require(not case.get("pending"), "Finish the active verification record first")
        reason = request["reason"]
        require(reason in ("surrogate_pass", "max_refinement_retries", "time_budget", "context_budget",
                           "verifier_failure", "environment_failure", "contaminated", "interrupted",
                           "construction_failed"), "Invalid termination reason")
        if reason == "surrogate_pass":
            require(not expired(case, config) and case["attempts"] and case["attempts"][-1]["accepted"],
                    "Surrogate success requires passing assertions, coverage, structure and remaining time")
        if reason == "max_refinement_retries":
            require(len(case["attempts"]) == config["max_refinement_retries"], "Verification budget not exhausted")
            last = case["attempts"][-1]
            require(not last["accepted"], "A complete pass must finish as surrogate_pass")
            decision = workflow.feedback(case)
            if decision["next_action"] != "repair_verifier":
                require(case["revisions"][-1]["revision"] > last["revision"],
                        "Apply the final failure-driven practice revision before exporting; use time_budget if expired")
        if reason == "time_budget":
            require(expired(case, config), "Time budget not exhausted")
        if reason not in ("surrogate_pass", "max_refinement_retries", "time_budget"):
            stop_record(out, case, reason, request)
        deployable = reason not in ("contaminated", "construction_failed") and bool(case["revisions"])
        if deployable:
            current = check_case(root / "skills", case_id, case["skills"], prefixes(out, state))
            require(current["sha256"] == case["revisions"][-1]["skills_sha256"], "Unrecorded final revision")
            last = case["attempts"][-1] if case["attempts"] else None
            if reason == "surrogate_pass":
                require(current["sha256"] == last["skill_sha256"], "Passing tests describe another revision")
            valid = [a for a in case["attempts"] if workflow.measured(a)]
            tested = valid[-1] if valid else None
            current_attempts = [a for a in valid if a["revision"] == case["revisions"][-1]["revision"]]
            case.update(final_sha256=current["sha256"], last_tested_sha256=tested["skill_sha256"] if tested else None,
                        last_valid_verification_attempt=tested["number"] if tested else None,
                        final_was_tested=bool(current_attempts and current["sha256"] == current_attempts[-1]["skill_sha256"]),
                        final_verification_issues=(workflow.issues(last) if last and
                            last["revision"] == case["revisions"][-1]["revision"] else ["not_run"]))
        case.update(finished=True, reason=reason, deployable=deployable)
    else:
        raise ValueError(f"Unknown action: {kind}")


def run(command, out, payload=None, *, executor=False):
    out = Path(out)
    if command == "status":
        return load(out)[0]
    if command == "next":
        state = load(out)[0]
        require(state["schema_version"] == 2, "Use the recorded Skill version for a historical journal")
        return workflow.guidance(state, datetime.now(timezone.utc))
    if command == "init":
        require(payload.get("execution_mode") in (None, "isolated-v1"), "Unknown execution mode")
        require(payload.get("execution_mode") != "isolated-v1" or executor,
                "Initialize isolated runs through executor.py")
        state = initialize(payload)
        out.mkdir(parents=True, exist_ok=True)
        with locked(out):
            require(not (out / "journal").exists() and not (out / "experiment.yaml").exists(),
                    "Existing experiment: never initialize or migrate it implicitly")
            append(out, state, {"action": "init"}, 0, None)
        return state
    with locked(out):
        state, sequence, previous = load(out)
        require(state["config"].get("execution_mode") != "isolated-v1" or executor,
                "Isolated runs accept mutations only through executor.py; role receipts cannot be self-reported")
        apply_event(out, state, payload)
        append(out, state, payload, sequence, previous)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "event", "status", "next"))
    parser.add_argument("out", type=Path)
    parser.add_argument("request", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        require(args.command in ("status", "next") or args.request is not None, "A JSON request file is required")
        result = run(args.command, args.out, read_json(args.request) if args.request else None)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        print(json.dumps({"status": "failed", "message": str(exc)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

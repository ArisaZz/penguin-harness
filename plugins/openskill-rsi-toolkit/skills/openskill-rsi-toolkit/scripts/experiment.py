#!/usr/bin/env python3
"""Record OpenSkill construction and guard phase changes; never run or score an agent."""

import argparse
import copy
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
    return {"schema_version": 1, "phase": "construction", "config": config, "cases": {}}


def case_root(out, case_id):
    path = out / "tasks" / identifier(case_id)
    require(path.resolve().is_relative_to(out.resolve()), "Case path escapes experiment")
    return path


def prefixes(out, state):
    extra = state["config"].get("practice_prefixes", [])
    strings(extra, "practice prefixes", allow_empty=True)
    return ["/opt/openskill-skills", str(out.resolve()), *extra]


def expired(case, config):
    seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(case["started_at"])).total_seconds()
    return seconds >= config["construction_timeout_minutes"] * 60


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


def verify_history(root, case):
    for revision in case["revisions"]:
        number = revision["revision"]
        require(digest(tree(root / "revisions" / f"revision-{number}")) == revision["skills_sha256"],
                "Historical skill revision changed")
        require(digest(tree(root / "practice" / f"revision-{number}")) == revision["outputs_sha256"],
                "Historical practice output changed")
    for attempt in case["attempts"]:
        folder = Path(attempt["directory"])
        actual = tree(folder, allow_empty=True) if folder.exists() else {}
        require(actual == attempt["evidence"], "Historical verification evidence changed")


def report_path(out, relative):
    path = out / relative
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts
            and path.resolve().is_relative_to(out.resolve()) and path.is_file()
            and not path.is_symlink(), "Report must exist as a regular file inside OUT")
    return path


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
                verify_history(case_root(out, case_id), case)
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
    if kind not in ("finish-verification", "finish-case"):
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
        require(len(case["revisions"]) <= config["max_refinement_retries"], "Practice budget exhausted")
        revision = len(case["revisions"])
        skills = tree(root / "skills")
        outputs = tree(root / "practice" / f"revision-{revision}")
        nonempty(request["hypothesis"], "revision hypothesis")
        snapshot = root / "revisions" / f"revision-{revision}"
        if snapshot.exists():
            require(tree(snapshot) == skills, "Revision snapshot exists with different content")
        else:
            shutil.copytree(root / "skills", snapshot)
        case["revisions"].append({"revision": revision, "skills_sha256": digest(skills),
                                  "outputs_sha256": digest(outputs), "hypothesis": request["hypothesis"]})
    elif kind == "begin-verification":
        require(case["revisions"] and not case.get("pending"), "Need a revision and no active verification")
        require(len(case["attempts"]) < config["max_refinement_retries"], "Verification budget exhausted")
        require(not case["attempts"] or not case["attempts"][-1]["accepted"], "Stop on a complete virtual pass")
        revision = case["revisions"][-1]
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
        require(type(request["pytest_exit_code"]) is int, "pytest_exit_code must be an integer")
        result = virtual_results.read_result(folder / "report.xml", request["pytest_exit_code"], config["max_virtual_tests"])
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
        attempt.update(finished=True, result=result, evidence=evidence, coverage_complete=coverage,
                       coverage_error=coverage_error, structure_valid=structure, structure_error=structure_error,
                       accepted=accepted,
                       verifier_session_id=verifier)
        case.pop("pending")
    elif kind == "targeted-search":
        require(case["attempts"] and case["attempts"][-1].get("finished")
                and not case["attempts"][-1]["accepted"], "Gap retrieval follows failed virtual verification")
        require(request["classification"] == "NEEDS-DR", "Only knowledge gaps trigger targeted retrieval")
        require(len(case["searches"]) < config["max_targeted_searches"], "Targeted search budget exhausted")
        nonempty(request["query"], "sanitized query")
        forbidden = [config["benchmark_id"], config.get("test_benchmark_id"), *config["case_ids"],
                     *config.get("test_case_ids", [])]
        require(not any(word and word.lower() in request["query"].lower() for word in forbidden),
                "Query contains a Benchmark/Case identifier")
        case["searches"].append({"query": request["query"], "time": now()})
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
        if reason == "time_budget":
            require(expired(case, config), "Time budget not exhausted")
        deployable = reason not in ("contaminated", "construction_failed") and bool(case["revisions"])
        if deployable:
            current = check_case(root / "skills", case_id, case["skills"], prefixes(out, state))
            require(current["sha256"] == case["revisions"][-1]["skills_sha256"], "Unrecorded final revision")
            last = case["attempts"][-1] if case["attempts"] else None
            if reason == "surrogate_pass":
                require(current["sha256"] == last["skill_sha256"], "Passing tests describe another revision")
            case.update(final_sha256=current["sha256"], last_tested_sha256=last["skill_sha256"] if last else None,
                        final_was_tested=bool(last and current["sha256"] == last["skill_sha256"]))
        case.update(finished=True, reason=reason, deployable=deployable)
    else:
        raise ValueError(f"Unknown action: {kind}")


def run(command, out, payload=None):
    out = Path(out)
    if command == "status":
        return load(out)[0]
    if command == "init":
        state = initialize(payload)
        out.mkdir(parents=True, exist_ok=True)
        with locked(out):
            require(not (out / "journal").exists() and not (out / "experiment.yaml").exists(),
                    "Existing experiment: never initialize or migrate it implicitly")
            append(out, state, {"action": "init"}, 0, None)
        return state
    with locked(out):
        state, sequence, previous = load(out)
        apply_event(out, state, payload)
        append(out, state, payload, sequence, previous)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "event", "status"))
    parser.add_argument("out", type=Path)
    parser.add_argument("request", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        require(args.command == "status" or args.request is not None, "A JSON request file is required")
        result = run(args.command, args.out, read_json(args.request) if args.request else None)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        print(json.dumps({"status": "failed", "message": str(exc)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

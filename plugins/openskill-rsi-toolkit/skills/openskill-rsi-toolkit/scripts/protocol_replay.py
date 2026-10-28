#!/usr/bin/env python3
"""Read-only development audit of recorded verifier artifacts; no model or test execution.

Usage: protocol_replay.py ATTEMPT_DIRECTORY PLAN_VIEW [--max-tests 60]
An exit code of zero means the recorded verification protocol is valid, including an
honest coverage gap or failed assertion. It never means a benchmark or skill passed.
"""

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import experiment
import oracle
import workflow
from artifacts import digest, read_json, require, tree


def audit(folder, plan_view, maximum=60):
    folder, plan_view = Path(folder), Path(plan_view)
    require(type(maximum) is int and 0 < maximum <= 60, "At most 60 virtual tests")
    before = tree(folder)
    receipt = read_json(folder / "executor.json")
    outcome, code = receipt["execution_status"], receipt["pytest_exit_code"]
    require(outcome in ("completed", "interrupted", "not_started"), "Invalid execution status")
    if outcome == "completed":
        require(type(code) is int, "Completed measurement needs an integer exit code")
        result = experiment.virtual_results.read_result(folder / "report.xml", code, maximum)
    else:
        require(code is None, "Uncompleted measurement cannot supply an exit code")
        result = experiment.virtual_results.failed("verification_" + outcome, "No completed measurement")
    complete, error = False, None
    try:
        reviewed = folder / "oracle"
        require(oracle.validate_plan(read_json(reviewed / "plan.json"), plan_view)
                == read_json(reviewed / "seal.json"), "Pinned verification plan or independent inputs changed")
        complete = oracle.coverage_complete(folder / "coverage.json", result, reviewed=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        error = str(exc)
    require(tree(folder) == before, "Recorded artifacts changed during read-only replay")
    attempt = {"execution_status": outcome, "result": result, "evidence": before,
               "coverage_complete": complete, "coverage_error": error, "structure_valid": True}
    return {"scope": "development_protocol_replay", "protocol_valid": not workflow.verifier_failed(attempt),
            "measurement_valid": workflow.measured(attempt), "result": result,
            "coverage_complete": complete, "coverage_error": error,
            "verification_issues": workflow.issues(attempt), "artifact_sha256": digest(before),
            "semantic_review_performed": False, "skill_structure_checked": False,
            "benchmark_score": None, "deployable": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("plan_view", type=Path)
    parser.add_argument("--max-tests", type=int, default=60)
    args = parser.parse_args()
    try:
        result = audit(args.attempt, args.plan_view, args.max_tests)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["protocol_valid"] else 2
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"OpenSkill protocol replay: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Development-only verifier replay; never creates a construction or scoring journal.

Usage: verifier_replay.py plan OUT REQUEST.json
       verifier_replay.py check|verify OUT REVIEW.json
       verifier_replay.py status|stop OUT
The trusted controller supplies explicit public/research/output file maps. Old runs
remain read-only. A fresh replay has one planning turn and one measured suite, with
one deadline; failures cannot be retried in place or exported as learned skills.
"""

import argparse
import json
import signal
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True

import executor
import oracle
from artifacts import digest, read_json, require, tree
from isolation import copy_files, files, regular, save, stamp
from runtime import check_runtime

SCOPE = "development_verifier_replay"


def import_files(mapping, destination):
    require(isinstance(mapping, dict) and mapping, "Supply an explicit nonempty replay file map")
    for name, source in mapping.items():
        relative = Path(name)
        require(relative.parts and not relative.is_absolute() and ".." not in relative.parts,
                "Replay destinations must remain in their assigned input category")
        source = Path(source)
        require(source.is_absolute(), "Replay sources must be explicit absolute file paths")
        target = destination / relative
        source = regular(source.parent, source.name)
        require(not target.exists(), "Duplicate replay destination")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(source.read_bytes())


def stop(out, state):
    return executor.stop(out, {"config": {"execution_mode": executor.MODE, "executor": state["executor"]}})


def run(command, out, request=None):
    out = Path(out).resolve()
    if command == "plan":
        require(not out.exists(), "Replay needs a fresh directory; never reuse an experiment or failed replay")
        minutes = request.get("timeout_minutes", 15)
        require(type(minutes) is int and 0 < minutes <= 30, "Development replay timeout must be 1–30 minutes")
        state = {"scope": SCOPE, "status": "planning", "started_at": stamp(),
                 "deadline": (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(),
                 "executor": request["executor"], "runtime": request["runtime"],
                 "max_virtual_tests": request.get("max_virtual_tests", 60), "benchmark_score": None}
        require(type(state["max_virtual_tests"]) is int and 0 < state["max_virtual_tests"] <= 60,
                "At most 60 virtual tests")
        out.mkdir(parents=True)
        save(out / "replay.json", state)
    else:
        state = read_json(out / "replay.json")
        require(state.get("scope") == SCOPE and not (out / "journal").exists(),
                "Not a development replay; historical experiments cannot be resumed here")
        if command == "status":
            return {**state, "stopped": (out / "STOP").exists()}
        if command == "stop":
            return stop(out, state)
        require(not (out / "STOP").exists(), "Replay stopped; no retry is permitted")
        require(state["status"] == "awaiting_review", "Replay is not awaiting evidence review")
    operation = out / ".executor/replay"
    folder = out / "measurement"
    with executor.lock(out):
        if command != "plan":
            # A prior process may have finished between the first read and lock acquisition.
            state = read_json(out / "replay.json")
            require(state.get("scope") == SCOPE and not (out / "journal").exists(),
                    "Not a development replay")
            require(not (out / "STOP").exists(), "Replay stopped; no retry is permitted")
            require(state["status"] == "awaiting_review", "Replay is not awaiting evidence review")
        config = state["executor"]
        if command in ("check", "verify"):
            # Invalid controller reviews cannot start a model, alter a prior record or spend another attempt.
            plan, seal, review = oracle.load_review(operation, Path(request))
            require(digest(tree(out / "candidate")) == state["outputs_sha256"], "Pinned replay outputs changed")
            if command == "check":
                return {"scope": SCOPE, "status": "review_valid", "semantic_proof": False,
                        "supported": sum(d["status"] == "supported" for d in review["decisions"]),
                        "unverified": sum(d["status"] == "unverified" for d in review["decisions"])}
        try:
            if command == "plan":
                for role, destination in (("public", operation / "plan-view/public"),
                                          ("research", operation / "plan-view/research"),
                                          ("outputs", out / "candidate")):
                    import_files(request[role], destination)
                state["outputs_sha256"] = digest(tree(out / "candidate"))
                cfg = {"execution_mode": executor.MODE, "executor": config, "case_ids": ["replay"],
                       "runtime": {"construction": state["runtime"]}}
                ready = executor.preflight(out, cfg, full=True)
                state["runtime_fingerprint"] = ready["runtime"]["fingerprint"]
                save(out / "replay.json", state)
                identity = {"role": "verifier", "agent_id": "openskill_" + uuid.uuid4().hex}
                executor.draft_verifier(config, state["runtime"], state["deadline"], out / "STOP",
                                        out / ".executor/containers", operation, identity)
                state["status"] = "awaiting_review"
            elif command == "verify":
                check_runtime(out, {"executor": config, "runtime": {"construction": state["runtime"]}},
                              expected=state["runtime_fingerprint"])
                save(operation / "oracle/review.json", review)
                state["status"] = "measuring"
                save(out / "replay.json", state)
                copy_files(operation / "plan-view", operation / "view", files(operation / "plan-view"))
                copy_files(out / "candidate", operation / "view/outputs", files(out / "candidate"))
                folder.mkdir()
                receipt = executor.measure_verifier(config, state["runtime"], state["deadline"], out / "STOP",
                    out / ".executor/containers", operation, folder, state["max_virtual_tests"])
                result = executor.experiment.virtual_results.read_result(folder / "report.xml", receipt["exit_code"],
                                                                        state["max_virtual_tests"])
                require(result["status"] == "ok", "Replay did not produce a valid measurement")
                state["result"] = result
                complete = oracle.coverage_complete(folder / "coverage.json", result, reviewed=True)
                state.update(status="completed", result=result, coverage_complete=complete,
                             benchmark_score=None, deployable=False)
            else:
                raise ValueError("Unknown replay command")
        except BaseException as error:
            state.update(status="failed", error=f"{type(error).__name__}: {error}")
            stop(out, state)
            raise
        finally:
            state["updated_at"] = stamp()
            save(out / "replay.json", state)
    return state


def main():
    def cancelled(_signum, _frame):
        raise KeyboardInterrupt("Development replay cancelled")
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "check", "verify", "status", "stop"])
    parser.add_argument("out", type=Path)
    parser.add_argument("request", nargs="?", type=Path)
    args = parser.parse_args()
    request = read_json(args.request) if args.command == "plan" else args.request
    try:
        print(json.dumps(run(args.command, args.out, request), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"OpenSkill development replay: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

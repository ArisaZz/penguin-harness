"""Derive construction decisions from recorded evidence, without launching any role."""

from datetime import datetime, timedelta

from artifacts import require, strings


def text(value, name):
    require(isinstance(value, str) and value.strip(), f"Missing {name}")


def clock(case, config, current):
    deadline = datetime.fromisoformat(case["started_at"]) + timedelta(
        minutes=config["construction_timeout_minutes"])
    return {"deadline_at": deadline.isoformat(),
            "remaining_seconds": max(0, (deadline - current).total_seconds())}


def issues(attempt):
    found = []
    if not measured(attempt):
        found.append("verifier_error")
    elif attempt["result"]["failed"]:
        found.append("assertion_failure")
    if not attempt["structure_valid"]:
        found.append("skill_structure")
    if not attempt["coverage_complete"]:
        found.append("coverage_gap")
    return found


def measured(attempt):
    return (attempt.get("execution_status") == "completed"
            and attempt.get("result", {}).get("status") == "ok"
            and "suite.py" in attempt.get("evidence", {}))


def feedback(case):
    require(case["attempts"] and case["attempts"][-1].get("finished")
            and not case["attempts"][-1]["accepted"], "Feedback requires a finished unsuccessful attempt")
    result = case["attempts"][-1].get("feedback")
    require(result is not None, "Record feedback for the latest attempt before continuing")
    return result


def validate_feedback(case, request):
    last = case["attempts"][-1]
    require(last.get("finished") and not last["accepted"], "Diagnose a finished unsuccessful attempt")
    require(request["attempt"] == last["number"], "Feedback refers to another attempt")
    require("feedback" not in last, "Feedback is sealed; continue its recorded action")
    require(request["classification"] in ("SELF-FIXABLE", "NEEDS-DR"), "Invalid gap-versus-bug classification")
    require(request["next_action"] in ("revise_skill", "repair_verifier", "repeat_practice"),
            "Feedback must name a recovery action")
    strings(request["issues"], "diagnosed issues")
    require(set(request["issues"]) == set(issues(last)), "Diagnose every observed failure and coverage gap")
    for key in ("diagnosis", "expected_change"):
        text(request[key], key)
    if "skill_structure" in request["issues"]:
        require(request["next_action"] == "revise_skill", "Invalid skill structure needs a skill revision")
    if request["next_action"] == "repair_verifier" and "assertion_failure" in request["issues"]:
        text(request.get("oracle_correction"), "independent evidence that the previous expectation was wrong")
    if request["next_action"] == "repeat_practice":
        text(request.get("execution_issue"), "execution or delivery fault to repair without editing skills")


def research_ready(case):
    decision = feedback(case)
    if decision["classification"] == "NEEDS-DR":
        searches = [s for s in case["searches"] if s["attempt"] == case["attempts"][-1]["number"]]
        require(searches and all("result" in s for s in searches),
                "Complete and record the issued gap searches before continuing")
        require(any(s["result"]["outcome"] == "retrieved" for s in searches),
                "No retrieved evidence for the knowledge gap; record a blocker instead of inventing a rule")
    return decision


def guidance(state, current):
    result = {"phase": state["phase"], "observed_at": current.isoformat(), "cases": {}}
    for cid, case in state["cases"].items():
        timing = clock(case, state["config"], current)
        attempts = case["attempts"]
        revisions = case["revisions"]
        last = attempts[-1] if attempts else None
        count = len(attempts)
        remaining = max(0, state["config"]["max_refinement_retries"] - count)
        if case.get("finished"):
            action = "closed"
        elif case.get("pending"):
            action = "abort_and_collect_verification" if not timing["remaining_seconds"] else "collect_verification"
        elif not timing["remaining_seconds"]:
            action = "stop_writers_then_finish_time_budget"
        elif "skills" not in case:
            action = "research_and_plan"
        elif not revisions:
            action = "initial_practice"
        elif last and last["accepted"]:
            action = "finish_surrogate_pass"
        elif last is None or last["revision"] != revisions[-1]["revision"]:
            action = "begin_verification" if remaining else "finish_max_refinement_retries"
        elif "feedback" not in last:
            action = "record_feedback"
        else:
            decision = last["feedback"]
            searches = [s for s in case["searches"] if s["attempt"] == last["number"]]
            if decision["next_action"] == "repair_verifier" and not remaining:
                action = "finish_max_refinement_retries"
            elif any("result" not in s for s in searches):
                action = "collect_search_result"
            elif decision["classification"] == "NEEDS-DR" and not any(
                    s.get("result", {}).get("outcome") == "retrieved" for s in searches):
                action = ("targeted_search" if len(case["searches"]) < state["config"]["max_targeted_searches"]
                          else "document_unresolved_gap")
            else:
                action = decision["next_action"]
        result["cases"][cid] = {**timing, "next_action": action,
            "verification_attempts_remaining": remaining,
            "targeted_searches_remaining": max(0, state["config"]["max_targeted_searches"] - len(case["searches"])),
            "practice_executions": len(revisions),
            "skill_changes_after_feedback": sum(r.get("change_kind") == "revise_skill" for r in revisions),
            "valid_virtual_measurements": sum(measured(a) for a in attempts),
            "latest_issues": issues(last) if last and last.get("finished") else []}
    return result

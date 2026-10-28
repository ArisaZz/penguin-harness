#!/usr/bin/env python3
"""Evo batch validation, native Skill export and complete-test reporting.

Standard library only. No model calls or task scheduling. The grade command sends one authorized training answer to its native judge.
The evaluation matrix/scoreboard format follows the sibling RSI toolkits.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_object(path):
    value = json.loads(
        Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object
    )
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def finite(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if (
        not math.isfinite(value)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(f"{label} is outside its finite range")
    return float(value)


def positive_int(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def matrix_results(matrix):
    """Require a complete, identified case x run matrix before averaging repeats."""
    for key in ("benchmark_id", "agent_id"):
        nonempty(matrix.get(key), key)
    version = positive_int(matrix.get("version"), "version")
    digest = matrix.get("state_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("state_sha256 must be a SHA-256 hex digest")
    runtime = matrix.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime must identify provider, model_id and thinking_level")
    for key in ("provider", "model_id", "thinking_level"):
        nonempty(runtime.get(key), key)
    cases = matrix.get("case_ids")
    if not isinstance(cases, list) or not cases:
        raise ValueError("case_ids must be a nonempty list")
    for case in cases:
        nonempty(case, "case_id")
    if len(set(cases)) != len(cases):
        raise ValueError("duplicate case id")
    runs = positive_int(matrix.get("runs"), "runs")
    cells = matrix.get("cells")
    if not isinstance(cells, list):
        raise ValueError("cells must be a list")
    expected = {(case, run) for case in cases for run in range(1, runs + 1)}
    seen, sessions = {}, set()
    for cell in cells:
        if not isinstance(cell, dict) or cell.get("status") != "ok":
            raise ValueError("failed or malformed cell: the matrix has no score")
        if (
            type(cell.get("protocol_version")) is not int
            or cell["protocol_version"] != 1
        ):
            raise ValueError("unsupported cell protocol")
        if (
            cell.get("agent_id") != matrix["agent_id"]
            or type(cell.get("expected_version")) is not int
            or cell["expected_version"] != version
        ):
            raise ValueError("cell Target/version mismatch")
        for key in ("provider", "model_id", "thinking_level"):
            if cell.get(key) != runtime[key]:
                raise ValueError(f"cell runtime mismatch: {key}")
        case = nonempty(cell.get("case_id"), "cell case_id")
        run = positive_int(cell.get("run"), "cell run")
        key = (case, run)
        if key not in expected or key in seen:
            raise ValueError("unexpected or duplicate case/run cell")
        session = nonempty(cell.get("session_id"), "session_id")
        if session in sessions:
            raise ValueError("one trial/session cannot score multiple cells")
        sessions.add(session)
        if "cost" not in cell:
            raise ValueError("cell cost must be numeric or null")
        if cell["cost"] is not None:
            finite(cell["cost"], "cost")
        duration = cell.get("duration_ms")
        if type(duration) is not int or duration < 0:
            raise ValueError("duration_ms must be a nonnegative integer")
        seen[key] = finite(cell.get("score"), "score", maximum=100) / 100
    if seen.keys() != expected:
        raise ValueError("incomplete case/run matrix")
    means = {
        case: statistics.mean(seen[case, run] for run in range(1, runs + 1))
        for case in sorted(cases)
    }
    return means, sessions


def report(matrix, spec, time, step, summary):
    """Format existing worker scores as one standard scoreboard evaluation.

    The frozen spec prevents a partial or changing batch from becoming a curve point.
    No files are written and no task output or grading material is read.
    """
    matrix_results(matrix)
    for key in ("benchmark_id", "agent_id", "runtime", "runs"):
        if matrix[key] != spec.get(key):
            raise ValueError(f"reporting specification mismatch: {key}")
    cases = spec.get("case_ids")
    if not isinstance(cases, list) or not cases:
        raise ValueError("reporting case_ids must be a nonempty list")
    for case in cases:
        nonempty(case, "reporting case_id")
    if len(set(cases)) != len(cases) or set(cases) != set(matrix["case_ids"]):
        raise ValueError("matrix does not cover the frozen reporting set")
    label = nonempty(spec.get("label"), "reporting label")
    nonempty(step, "step")
    nonempty(summary, "summary")
    timestamp = datetime.fromisoformat(nonempty(time, "time").replace("Z", "+00:00"))
    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp)
    ):
        raise ValueError("measurement time must include the UTC timezone")

    def known_mean(values):
        known = [value for value in values if value is not None]
        return round(statistics.mean(known), 6) if known else None

    cells = {(cell["case_id"], cell["run"]): cell for cell in matrix["cells"]}
    records = []
    for case in cases:
        runs = [
            {
                key: cells[case, run][key]
                for key in ("score", "cost", "duration_ms", "session_id")
            }
            for run in range(1, matrix["runs"] + 1)
        ]
        records.append(
            {
                "case": case,
                "score": statistics.mean(run["score"] for run in runs),
                "cost": known_mean(run["cost"] for run in runs),
                "duration_ms": round(
                    statistics.mean(run["duration_ms"] for run in runs)
                ),
                "runs": runs,
            }
        )
    return {
        "time": timestamp.isoformat().replace("+00:00", "Z"),
        "agent_id": matrix["agent_id"],
        "version": matrix["version"],
        **{
            key: matrix["runtime"][key]
            for key in ("provider", "model_id", "thinking_level")
        },
        "summary_title": f"{label}: {step}",
        "summary": summary,
        "score": round(statistics.mean(case["score"] for case in records), 2),
        "cost": known_mean(case["cost"] for case in records),
        "duration_ms": round(statistics.mean(case["duration_ms"] for case in records)),
        "cases": records,
    }


def string_list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for item in value:
        nonempty(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"duplicate {label}")
    return value


def entries(value):
    if not isinstance(value, list):
        raise ValueError("library must be a list")
    result, counts = {}, {}
    for item in value:
        key = nonempty(item.get("id"), "entry id")
        if key in result:
            raise ValueError("duplicate entry id")
        level = item.get("level")
        if level not in ("general", "topic"):
            raise ValueError("entry level must be general or topic")
        clean = {field: nonempty(item.get(field), field)
                 for field in ("id", "level", "trigger", "scope", "body")}
        if level == "general":
            clean["description"] = nonempty(item.get("description"), "description")
            group = (level, None)
        else:
            clean["topic"] = nonempty(item.get("topic"), "topic")
            group = (level, clean["topic"])
        counts[group] = counts.get(group, 0) + 1
        if counts[group] > 5:
            raise ValueError("at most five general entries and five per topic")
        result[key] = clean
    return result


READER = """# Evo method reader

Use every general description and every full method for the assigned topic
provided below before substantive task work. Each method remains conditional
on its trigger and scope. General bodies are private and are not loaded.
When there are no methods, solve using the unchanged base instructions.
Do not select, retrieve, truncate or borrow methods from another topic.
"""


def render(library, topic, max_bytes=16000):
    library = entries(library)
    nonempty(topic, "topic")
    if type(max_bytes) is not int or not 0 < max_bytes <= 16000:
        raise ValueError("max_bytes must be an integer in 1..16000")
    files = {"SKILL.md":
             '---\nname: evo-reader\ndescription: "Read the frozen Evo methods."\n---\n' + READER}
    manifest, context = [], [READER]
    for key, entry in sorted(library.items()):
        name = "evo-method-" + hashlib.sha256(key.encode()).hexdigest()[:20]
        path = f"{name}/SKILL.md"
        description = entry.get("description", entry["trigger"])
        visible = description if entry["level"] == "general" else entry["body"]
        body = (f"# Method {key}\n\nTrigger: {entry['trigger']}\n\n"
                f"Scope: {entry['scope']}\n\n{visible}\n")
        files[path] = (f"---\nname: {name}\ndescription: "
                       + json.dumps(description, ensure_ascii=False) + "\n---\n" + body)
        manifest.append({field: entry[field] for field in ("id", "level", "topic")
                         if field in entry} | {"path": path})
        if entry["level"] == "general" or entry["topic"] == topic:
            context.append(body)
    files["manifest.json"] = json.dumps(
        {"version": 1, "entries": manifest}, ensure_ascii=False, indent=2) + "\n"
    size = sum(len(body.encode("utf-8")) for body in files.values())
    if size > max_bytes:
        raise ValueError(f"complete Skill package is {size} bytes; limit is {max_bytes}")
    return files, "\n".join(context), size


def compile_batch(request):
    """Validate references and four-operation decisions; never invent or rank lessons."""
    tasks = string_list(request["task_ids"], "task_ids")
    if not tasks:
        raise ValueError("task_ids must be nonempty")
    contexts = {}
    sessions = set()
    for ctx in request["contexts"]:
        task = nonempty(ctx.get("task_id"), "task_id")
        attempt = nonempty(ctx.get("attempt_id"), "attempt_id")
        session = nonempty(ctx.get("session_id"), "session_id")
        if task in contexts or task not in tasks or session in sessions:
            raise ValueError("each training task needs its own original Solver Session")
        if ctx.get("status") != "ok" or type(ctx.get("negative")) is not bool:
            raise ValueError("training feedback must be successfully graded")
        inputs = string_list(ctx["input_sha256"], "input_sha256")
        if any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in inputs):
            raise ValueError("invalid input SHA-256")
        string_list(ctx["tool_call_ids"], "tool_call_ids")
        contexts[task] = ctx
        sessions.add(session)
    if set(contexts) != set(tasks):
        raise ValueError("incomplete training contexts")
    candidates = {}
    for candidate in request["candidates"]:
        cid = nonempty(candidate.get("id"), "candidate id")
        ctx = contexts.get(candidate.get("task_id"))
        if cid in candidates or ctx is None or not ctx["negative"]:
            raise ValueError("candidate must have one negatively graded source")
        if candidate.get("attempt_id") != ctx["attempt_id"]:
            raise ValueError("candidate attempt mismatch")
        prefix = f"{ctx['task_id']}-{ctx['attempt_id']}-"
        if not cid.startswith(prefix) or len(cid) == len(prefix):
            raise ValueError("candidate id must start with task_id-attempt_id-")
        for field in ("lesson", "trigger", "scope_hint"):
            nonempty(candidate.get(field), field)
        evidence = candidate.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("candidate needs evidence")
        for item in evidence:
            nonempty(item.get("claim"), "evidence claim")
            if item.get("epistemic") not in ("observed", "inferred"):
                raise ValueError("evidence must distinguish observed and inferred")
            kind = item.get("kind")
            if kind not in ("input", "tool", "answer", "feedback"):
                raise ValueError("invalid evidence kind")
            if kind == "input" and item.get("sha256") not in ctx["input_sha256"]:
                raise ValueError("input evidence is outside this attempt")
            if kind == "tool" and item.get("tool_call_id") not in ctx["tool_call_ids"]:
                raise ValueError("tool evidence is outside the original Solver Session")
        candidates[cid] = candidate
    before = entries(request["library"])
    after, used, edited, covered = dict(before), set(), set(), set()
    for decision in request["decisions"]:
        op = decision.get("op")
        if op not in ("ADD", "MERGE", "REVISE", "SKIP"):
            raise ValueError("invalid compilation operation")
        nonempty(decision.get("reason"), "decision reason")
        ids = string_list(decision["candidate_ids"], "candidate_ids")
        if not ids or not set(ids) <= candidates.keys():
            raise ValueError("decision must reference known candidates")
        if op == "SKIP":
            level = decision.get("level", "all")
        else:
            entry = entries([decision["entry"]])
            key, item = next(iter(entry.items()))
            level = item["level"]
            if key in edited:
                raise ValueError("combine edits to the same entry")
            if op == "ADD":
                if key in before:
                    raise ValueError("ADD needs a new entry id")
            elif key not in before or any(
                    item.get(field) != before[key].get(field) for field in ("level", "topic")):
                raise ValueError("MERGE/REVISE needs an existing entry in the same level/topic")
            after[key] = item
            edited.add(key)
        if level not in ("general", "topic", "all"):
            raise ValueError("invalid decision level")
        for cid in ids:
            for layer in (("general", "topic") if level == "all" else (level,)):
                if (cid, layer) in used:
                    raise ValueError("candidate used more than once per level")
                used.add((cid, layer))
        covered.update(ids)
    if covered != candidates.keys():
        raise ValueError("every candidate needs a decision")
    library = [after[key] for key in sorted(after)]
    render(library, request["topic"], request.get("max_bytes", 16000))
    return {"library": library, "decisions": request["decisions"]}


def export(request, output):
    files, context, size = render(request["library"], request["topic"],
                                  request.get("max_bytes", 16000))
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=False)
    inventory = {}
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        inventory[name] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {"directory": str(destination.resolve()), "bytes": size,
            "sha256": inventory, "topic": request["topic"], "context": context,
            "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest()}


def repeat_statistics(values):
    return {"repetition_scores": values, "mean": statistics.mean(values),
            "variance": statistics.variance(values) if len(values) > 1 else None,
            "std": statistics.stdev(values) if len(values) > 1 else None}


def summarize(request):
    """One frozen condition: cases -> domain per repeat -> overall per repeat."""
    matrices = request["matrices"]
    if not isinstance(matrices, list) or not matrices:
        raise ValueError("matrices must be nonempty")
    domains, sessions, runtime, runs = {}, set(), matrices[0]["runtime"], matrices[0]["runs"]
    for matrix in matrices:
        _, current_sessions = matrix_results(matrix)
        if matrix["runs"] != runs or matrix["runtime"] != runtime:
            raise ValueError("domains must use the same runtime and repetition count")
        if matrix["benchmark_id"] in domains or sessions & current_sessions:
            raise ValueError("duplicate domain or reused trial/session")
        if matrix.get("aggregation") != "mean":
            raise ValueError("helper supports declared mean aggregation only")
        sessions.update(current_sessions)
        scores = [statistics.mean(cell["score"] for cell in matrix["cells"]
                                  if cell["run"] == run) for run in range(1, runs + 1)]
        domains[matrix["benchmark_id"]] = repeat_statistics(scores)
    overall = [statistics.mean(domain["repetition_scores"][i] for domain in domains.values())
               for i in range(runs)]
    return {"domains": domains, "overall": repeat_statistics(overall)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("compile", "export", "install", "grade", "summarize"):
        command = commands.add_parser(name)
        command.add_argument("--request", required=True)
        if name == "export":
            command.add_argument("--output", required=True)
        if name == "install":
            command.add_argument("--state", required=True)
    publication = commands.add_parser("report")
    for name in ("matrix", "spec", "time", "step", "summary"):
        publication.add_argument("--" + name, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    try:
        if command == "report":
            args["matrix"], args["spec"] = read_object(args["matrix"]), read_object(args["spec"])
            result = report(**args)
        else:
            request = read_object(args["request"])
            if command == "grade":
                from feedback import grade
                result = grade(request)
            elif command == "install":
                from state import install_package
                result = install_package(request, args["state"])
            else:
                result = (export(request, args["output"]) if command == "export" else
                          compile_batch(request) if command == "compile" else summarize(request))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 2 if command == "grade" and result["status"] != "ok" else 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError, OverflowError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

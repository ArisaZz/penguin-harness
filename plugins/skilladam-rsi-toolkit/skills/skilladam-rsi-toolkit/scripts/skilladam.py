#!/usr/bin/env python3
"""Validate SkillAdam patches and assess paired Penguin evaluation matrices.

Standard library only. Reads experiment artifacts; never publishes a Target state.
Equations follow SkillAdam edit_budget.py at b6c9640f7a9e0d5e3a500c25bc4e6369eeca78f1.
The gate uses mean-score improvement; callers supply the selected training cases.
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


def assess(
    before,
    after,
    *,
    previous_variance=0.0,
    beta2=0.9,
    base_budget=4,
    min_budget=1,
    variance_cap=0.1,
    min_gain=0.0,
    max_case_drop=None,
    case_ids=None,
):
    baseline, before_sessions = matrix_results(before)
    candidate, after_sessions = matrix_results(after)
    for key in ("benchmark_id", "agent_id", "runtime", "runs"):
        if before[key] != after[key]:
            raise ValueError(f"paired matrices differ in {key}")
    if baseline.keys() != candidate.keys():
        raise ValueError("paired matrices must cover exactly the same cases")
    if (
        after["version"] <= before["version"]
        or after["state_sha256"] == before["state_sha256"]
    ):
        raise ValueError("candidate must have a new version and state hash")
    if before_sessions & after_sessions:
        raise ValueError("baseline and candidate cannot reuse the same trial/session")
    if case_ids is not None:
        if not isinstance(case_ids, list) or not case_ids:
            raise ValueError("gate case_ids must be a nonempty list")
        for case in case_ids:
            nonempty(case, "gate case_id")
        if len(set(case_ids)) != len(case_ids) or not set(case_ids) <= baseline.keys():
            raise ValueError("gate cases must be unique members of the reporting set")
        baseline = {case: baseline[case] for case in sorted(case_ids)}
        candidate = {case: candidate[case] for case in sorted(case_ids)}
    return compare(
        baseline, candidate, previous_variance=previous_variance, beta2=beta2,
        base_budget=base_budget, min_budget=min_budget, variance_cap=variance_cap,
        min_gain=min_gain, max_case_drop=max_case_drop,
    )


def compare(
    before, after, *, previous_variance=0.0, beta2=0.9, base_budget=4,
    min_budget=1, variance_cap=0.1, min_gain=0.0, max_case_drop=None,
):
    """Paper equations on paired normalized scores, independent of a runner schema.

    The primary metric is the equally weighted mean. A per-case gate is an
    optional experiment override retained for older callers, never a default.
    Case IDs are opaque; the caller selects training data from the benchmark split.
    """
    if not isinstance(before, dict) or not before or not isinstance(after, dict):
        raise ValueError("before and after must be nonempty case-to-score maps")
    if before.keys() != after.keys():
        raise ValueError("paired score maps must cover exactly the same cases")
    for case in before:
        nonempty(case, "case id")
    baseline = {case: finite(before[case], case, maximum=1) for case in sorted(before)}
    candidate = {case: finite(after[case], case, maximum=1) for case in sorted(after)}
    previous_variance = finite(previous_variance, "previous_variance")
    beta2 = finite(beta2, "beta2", maximum=1)
    if beta2 == 1:
        raise ValueError("beta2 must be less than one")
    variance_cap = finite(variance_cap, "variance_cap")
    if variance_cap == 0:
        raise ValueError("variance_cap must be positive")
    base_budget = positive_int(base_budget, "base_budget")
    min_budget = positive_int(min_budget, "min_budget")
    if min_budget > base_budget:
        raise ValueError("min_budget cannot exceed base_budget")
    min_gain = finite(min_gain, "min_gain", maximum=1)
    if max_case_drop is not None:
        max_case_drop = finite(max_case_drop, "max_case_drop", maximum=1)
    deltas = {case: candidate[case] - baseline[case] for case in baseline}
    values = list(deltas.values())
    mean_gain = statistics.mean(values)
    sample_variance = statistics.variance(values) if len(values) > 1 else 0.0
    variance = beta2 * previous_variance + (1 - beta2) * sample_variance
    ratio = max(0.0, min(variance / variance_cap, 1.0))
    budget = max(min_budget, round(base_budget * (1 - ratio)))
    # Avoid treating floating-point representation noise at a gate boundary as evidence.
    improved = mean_gain > min_gain and not math.isclose(
        mean_gain, min_gain, rel_tol=0, abs_tol=1e-12
    )
    regressions = [
        case
        for case, delta in deltas.items()
        if max_case_drop is not None and delta < -max_case_drop
        and not math.isclose(delta, -max_case_drop, rel_tol=0, abs_tol=1e-12)
    ]
    return {
        "accepted": improved and not regressions,
        "reason": (
            "protected case regressed"
            if regressions
            else (
                "mean reward improved"
                if improved
                else "no strict mean reward improvement"
            )
        ),
        "baseline_mean_reward": statistics.mean(baseline.values()),
        "candidate_mean_reward": statistics.mean(candidate.values()),
        "mean_gain": mean_gain,
        "per_case_deltas": deltas,
        "regressed_cases": regressions,
        "sample_variance": sample_variance,
        "previous_variance": previous_variance,
        "next_variance": variance,
        "next_budget": budget,
    }


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


def frontmatter(text):
    end = text.find("\n---\n", 4)
    if not text.startswith("---\n") or end < 0:
        raise ValueError("working Skill must have YAML frontmatter")
    return text[: end + 5]


def apply_patch(source, patch, budget):
    """Apply only exact-context, LF unified hunks to one virtual SKILL.md.

    No filesystem paths from the patch are ever opened. Multi-file patches,
    offsets/fuzz, binary patches and no-final-newline markers are rejected.
    """
    positive_int(budget, "budget")
    if "\r" in source or not source.endswith("\n"):
        raise ValueError("working Skill must use LF and end in a newline")
    original_frontmatter = frontmatter(source)
    if patch == "":
        return source, 0
    if "\r" in patch or not patch.endswith("\n"):
        raise ValueError("patch must use LF and end in a newline")
    lines = patch.splitlines(keepends=True)
    if lines[:2] != ["--- a/SKILL.md\n", "+++ b/SKILL.md\n"]:
        raise ValueError("patch must target only a/SKILL.md -> b/SKILL.md")
    old = source.splitlines(keepends=True)
    output, cursor, index, hunks = [], 0, 2, 0
    while index < len(lines):
        match = re.fullmatch(
            r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n", lines[index]
        )
        if not match:
            raise ValueError("expected a unified diff hunk header")
        start, count, new_start, new_count = (
            int(value) if value is not None else 1 for value in match.groups()
        )
        position = start if count == 0 else start - 1
        new_position = new_start if new_count == 0 else new_start - 1
        if position < cursor or position > len(old):
            raise ValueError("hunk offset or overlapping hunks")
        output.extend(old[cursor:position])
        cursor = position
        if new_position != len(output):
            raise ValueError("candidate hunk position mismatch")
        consumed = produced = 0
        index += 1
        hunks += 1
        if hunks > budget:
            raise ValueError("patch exceeds the hunk budget")
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            prefix, text = line[0], line[1:]
            if prefix not in (" ", "+", "-"):
                raise ValueError("invalid unified diff line")
            if prefix in (" ", "-"):
                if cursor >= len(old) or old[cursor] != text:
                    raise ValueError("patch context does not match the current Skill")
                cursor += 1
                consumed += 1
            if prefix in (" ", "+"):
                output.append(text)
                produced += 1
            if consumed > count or produced > new_count:
                raise ValueError("hunk line counts exceed the header")
            index += 1
        if consumed != count or produced != new_count:
            raise ValueError("hunk line counts do not match the header")
    if not hunks:
        raise ValueError("nonempty patch has no hunks")
    output.extend(old[cursor:])
    candidate = "".join(output)
    if frontmatter(candidate) != original_frontmatter:
        raise ValueError("a proposal cannot edit working-Skill frontmatter")
    if not candidate[len(original_frontmatter) :].strip():
        raise ValueError("working Skill body cannot be empty")
    return candidate, hunks


def prepare(skill, proposal, budget, output):
    if set(proposal) != {"reasoning", "patch"} or any(
        not isinstance(proposal[key], str) for key in proposal
    ):
        raise ValueError("proposal requires exactly the reasoning and patch strings")
    source = Path(skill).read_bytes().decode("utf-8")
    candidate, hunks = apply_patch(source, proposal["patch"], budget)
    result = {
        "status": "noop" if candidate == source else "ready",
        "hunks": hunks,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
    }
    if candidate != source:
        # Exclusive creation prevents overwriting an earlier proposal or the live Skill.
        with Path(output).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(candidate)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    patch = commands.add_parser(
        "prepare", help="validate a proposal and create a separate candidate"
    )
    patch.add_argument("--skill", required=True)
    patch.add_argument("--proposal", required=True)
    patch.add_argument("--budget", required=True, type=int)
    patch.add_argument("--output", required=True)
    gate = commands.add_parser(
        "assess", help="gate complete paired matrices and calculate the next budget"
    )
    paired = commands.add_parser(
        "compare", help="compare normalized case-to-score maps from an online judge"
    )
    gate.add_argument(
        "--case-ids", nargs="+",
        help="frozen gate batch within the complete reporting matrices",
    )
    for command_parser in (gate, paired):
        command_parser.add_argument("--before", required=True)
        command_parser.add_argument("--after", required=True)
        command_parser.add_argument("--previous-variance", required=True, type=float)
        for name, default, kind in [
            ("beta2", 0.9, float),
            ("base-budget", 4, int),
            ("min-budget", 1, int),
            ("variance-cap", 0.1, float),
            ("min-gain", 0.0, float),
            ("max-case-drop", None, float),
        ]:
            command_parser.add_argument("--" + name, default=default, type=kind)
    publication = commands.add_parser(
        "report", help="validate and format scored cells for the existing scoreboard"
    )
    for name in ("matrix", "spec", "time", "step", "summary"):
        publication.add_argument("--" + name, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    try:
        if command == "prepare":
            args["proposal"] = read_object(args["proposal"])
            result = prepare(**args)
        elif command in ("assess", "compare"):
            args["before"] = read_object(args["before"])
            args["after"] = read_object(args["after"])
            result = (assess if command == "assess" else compare)(**args)
        else:
            args["matrix"] = read_object(args["matrix"])
            args["spec"] = read_object(args["spec"])
            result = report(**args)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, OverflowError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

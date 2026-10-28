"""Observable Evo artifact contracts (no model, network, Docker or grader calls).

Given a completed training batch, compilation accepts supported four-operation
decisions and rejects missing evidence, foreign references and duplicate edits.
Given a private library, export includes exact matching-topic methods and general
descriptions, respects the complete byte budget and never overwrites a package.
Given native trial matrices, reports retain every measurement, reject incomplete
or mismatched cells and calculate variation between complete repetitions.
Given malformed CLI input, the command fails without writing an export.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import evo


def entry(key="method-1", level="topic", topic="orders"):
    result = {"id": key, "level": level, "trigger": "When counting failed days",
              "scope": "Use the task's date basis", "body": "Deduplicate dates, then count."}
    if level == "general":
        result["description"] = "Group by the requested unit before counting; check the task's grain."
        result["body"] = "PRIVATE_GENERAL_BODY"
    else:
        result["topic"] = topic
    return result


def batch():
    candidate = {"id": "t1-a1-c1", "task_id": "t1", "attempt_id": "a1",
                 "lesson": "Retain the join and deduplicate the requested date unit.",
                 "trigger": "A task counts failed days", "scope_hint": "Dates are in task timezone",
                 "evidence": [{"kind": "input", "sha256": "a" * 64,
                               "claim": "The output asks for days", "epistemic": "observed"},
                              {"kind": "tool", "tool_call_id": "call-1",
                               "claim": "Several rows can share a date", "epistemic": "observed"}]}
    return {"task_ids": ["t1", "t2"], "topic": "orders", "library": [],
            "contexts": [{"task_id": task, "attempt_id": "a1", "session_id": "session-" + task,
                          "status": "ok", "negative": task == "t1",
                          "input_sha256": ["a" * 64], "tool_call_ids": ["call-1"]}
                         for task in ("t1", "t2")],
            "candidates": [candidate],
            "decisions": [{"op": "ADD", "candidate_ids": ["t1-a1-c1"],
                           "reason": "Keep the join; count date units instead of rows.",
                           "entry": entry()}]}


def matrix(benchmark="orders", cases=("c1", "c2"), scores=(20, 50, 80)):
    runtime = {"provider": "fixture", "model_id": "fixed-model", "thinking_level": "medium"}
    return {"benchmark_id": benchmark, "agent_id": "frozen-target", "version": 2,
            "state_sha256": "a" * 64, "runtime": runtime, "aggregation": "mean",
            "case_ids": list(cases), "runs": len(scores),
            "cells": [{"protocol_version": 1, "status": "ok", "case_id": case,
                       "run": run, "agent_id": "frozen-target", "expected_version": 2,
                       **runtime, "score": score, "cost": None, "duration_ms": 1000,
                       "session_id": f"{benchmark}-{case}-{run}"}
                      for case in cases for run, score in enumerate(scores, 1)]}


class CompilationTests(unittest.TestCase):
    def test_compilation_preserves_authored_method_and_does_not_mutate_evidence(self):
        request = batch()
        snapshot = copy.deepcopy(request)
        result = evo.compile_batch(request)
        self.assertEqual(result["library"], [entry()])
        self.assertEqual(request, snapshot)

    def test_revise_and_merge_keep_the_existing_identity_and_other_methods(self):
        for operation in ("REVISE", "MERGE"):
            with self.subTest(operation=operation):
                request = batch()
                request["library"] = [entry(), entry("untouched")]
                request["decisions"][0]["op"] = operation
                request["decisions"][0]["entry"]["body"] = "Updated supported method."
                result = evo.compile_batch(request)["library"]
                self.assertEqual(result[0]["body"], "Updated supported method.")
                self.assertEqual(result[1], entry("untouched"))

    def test_one_candidate_can_support_both_levels_once(self):
        request = batch()
        decision = copy.deepcopy(request["decisions"][0])
        decision["entry"] = entry("general-1", "general")
        request["decisions"].append(decision)
        self.assertEqual(len(evo.compile_batch(request)["library"]), 2)

    def test_skip_and_empty_candidates_produce_no_invented_methods(self):
        request = batch()
        request["decisions"] = [{"op": "SKIP", "candidate_ids": ["t1-a1-c1"],
                                 "reason": "Premise remains unsupported."}]
        self.assertEqual(evo.compile_batch(request)["library"], [])
        request["candidates"], request["decisions"] = [], []
        self.assertEqual(evo.compile_batch(request), {"library": [], "decisions": []})

    def test_compilation_rejects_invalid_sources_and_incomplete_rosters(self):
        def mutate(request, kind):
            if kind == "success":
                request["contexts"][0]["negative"] = False
            elif kind == "grader error":
                request["contexts"][0]["status"] = "failed"
            elif kind == "missing context":
                request["contexts"].pop()
            elif kind == "shared session":
                request["contexts"][1]["session_id"] = "session-t1"
            elif kind == "foreign input":
                request["candidates"][0]["evidence"][0]["sha256"] = "b" * 64
            elif kind == "foreign tool":
                request["candidates"][0]["evidence"][1]["tool_call_id"] = "other-session"
            elif kind == "wrong attempt":
                request["candidates"][0]["attempt_id"] = "a2"
            elif kind == "unknown certainty":
                request["candidates"][0]["evidence"][0]["epistemic"] = "verified"
            else:
                request["candidates"][0]["evidence"] = []
        for kind in ("success", "grader error", "missing context", "shared session", "foreign input",
                     "foreign tool", "wrong attempt", "unknown certainty", "empty evidence"):
            with self.subTest(kind=kind):
                request = batch()
                mutate(request, kind)
                with self.assertRaises(ValueError):
                    evo.compile_batch(request)

    def test_compilation_rejects_missing_duplicate_or_invalid_decisions(self):
        for kind in ("uncovered", "duplicate candidate", "duplicate target", "unknown candidate",
                     "invalid op", "missing target", "existing add", "move topic", "empty reason"):
            with self.subTest(kind=kind):
                request = batch()
                decision = request["decisions"][0]
                if kind == "uncovered":
                    request["decisions"] = []
                elif kind == "duplicate candidate":
                    request["decisions"].append({"op": "SKIP", "level": "topic",
                                                 "candidate_ids": ["t1-a1-c1"], "reason": "Duplicate"})
                elif kind == "duplicate target":
                    request["decisions"].append(copy.deepcopy(decision))
                elif kind == "unknown candidate":
                    decision["candidate_ids"] = ["foreign"]
                elif kind == "invalid op":
                    decision["op"] = "ACCEPT"
                elif kind == "missing target":
                    decision["op"] = "REVISE"
                elif kind == "existing add":
                    request["library"] = [entry()]
                elif kind == "move topic":
                    request["library"] = [entry()]
                    decision["op"] = "MERGE"
                    decision["entry"]["topic"] = "other"
                else:
                    decision["reason"] = ""
                with self.assertRaises(ValueError):
                    evo.compile_batch(request)


class ExportTests(unittest.TestCase):
    def test_export_hides_general_bodies_and_loads_all_matching_methods(self):
        library = [entry("general", "general"), entry(), entry("second"),
                   entry("foreign", topic="other")]
        with tempfile.TemporaryDirectory() as temp:
            result = evo.export({"library": library, "topic": "orders"}, Path(temp) / "skills")
            contents = [path.read_bytes() for path in Path(result["directory"]).rglob("*") if path.is_file()]
            self.assertNotIn(b"PRIVATE_GENERAL_BODY", b"".join(contents))
            self.assertNotIn("Method foreign", result["context"])
            self.assertIn("Method method-1", result["context"])
            self.assertIn("Method second", result["context"])
            self.assertIn(library[0]["description"], result["context"])
            self.assertEqual(result["bytes"], sum(map(len, contents)))
            for name, digest in result["sha256"].items():
                self.assertEqual(hashlib.sha256((Path(result["directory"]) / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(hashlib.sha256(result["context"].encode()).hexdigest(), result["context_sha256"])

    def test_budget_counts_the_complete_utf8_package_and_never_clips(self):
        method = entry()
        method["body"] = "日期分组方法。" * 50
        _, _, exact = evo.render([method], "orders")
        files, _, size = evo.render([method], "orders", exact)
        self.assertEqual(size, exact)
        self.assertIn(method["body"], "".join(files.values()))
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "skills"
            with self.assertRaises(ValueError):
                evo.export({"library": [method], "topic": "orders", "max_bytes": exact - 1}, destination)
            self.assertFalse(destination.exists())

    def test_export_refuses_to_overwrite_an_existing_package(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "skills"
            evo.export({"library": [], "topic": "orders"}, destination)
            original = (destination / "SKILL.md").read_bytes()
            with self.assertRaises(FileExistsError):
                evo.export({"library": [entry()], "topic": "orders"}, destination)
            self.assertEqual((destination / "SKILL.md").read_bytes(), original)

    def test_entry_limits_apply_per_topic_and_general_descriptions_are_required(self):
        library = [entry(str(i)) for i in range(5)] + [entry("other", topic="other")]
        evo.render(library, "orders")
        for invalid in (library + [entry("sixth")], [entry(str(i), "general") for i in range(6)],
                        [entry(), entry()], [entry() | {"level": "unknown"}]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    evo.render(invalid, "orders")
        invalid = entry("general", "general")
        del invalid["description"]
        with self.assertRaises(ValueError):
            evo.render([invalid], "orders")


class ReportingTests(unittest.TestCase):
    def test_round_first_statistics_keep_domain_and_case_measurements(self):
        first = matrix(scores=(20, 50, 80))
        second = matrix("other", cases=("c1",), scores=(80, 50, 20))
        result = evo.summarize({"matrices": [first, second]})
        self.assertEqual(result["domains"]["orders"]["repetition_scores"], [20, 50, 80])
        self.assertEqual(result["domains"]["orders"]["variance"], 900)
        self.assertEqual(result["overall"], {"repetition_scores": [50, 50, 50],
                                             "mean": 50, "std": 0, "variance": 0})

    def test_a_real_zero_counts_and_one_repetition_has_unknown_variance(self):
        result = evo.summarize({"matrices": [matrix(scores=(0,))]})["overall"]
        self.assertEqual(result["mean"], 0)
        self.assertIsNone(result["std"])
        self.assertIsNone(result["variance"])

    def test_invalid_measurements_never_become_a_partial_average(self):
        for kind in ("missing", "duplicate", "failed", "runtime", "version", "reused trial",
                     "nan", "bool", "negative cost", "missing cost", "negative duration", "unknown rule"):
            with self.subTest(kind=kind):
                value = matrix()
                cell = value["cells"][0]
                if kind == "missing":
                    value["cells"].pop()
                elif kind == "duplicate":
                    value["cells"].append(copy.deepcopy(cell))
                elif kind == "failed":
                    cell["status"] = "failed"
                elif kind in ("runtime", "version"):
                    cell["model_id" if kind == "runtime" else "expected_version"] = "different"
                elif kind == "reused trial":
                    value["cells"][1]["session_id"] = cell["session_id"]
                elif kind in ("nan", "bool"):
                    cell["score"] = float("nan") if kind == "nan" else True
                elif kind == "negative cost":
                    cell["cost"] = -1
                elif kind == "missing cost":
                    del cell["cost"]
                elif kind == "negative duration":
                    cell["duration_ms"] = -1
                else:
                    value["aggregation"] = "sum"
                with self.assertRaises(ValueError):
                    evo.summarize({"matrices": [value]})

    def test_reports_follow_the_native_scoreboard_format_and_frozen_spec(self):
        value = matrix(scores=(60, 70, 80))
        value["cells"][0]["cost"] = 0.25
        spec = {key: value[key] for key in ("benchmark_id", "agent_id", "runtime", "runs", "case_ids")}
        spec["label"] = "Evo final"
        record = evo.report(value, spec, "2026-10-28T12:00:00Z", "Test", "Three complete repetitions.")
        self.assertEqual(record["score"], 70)
        self.assertEqual(len(record["cases"]), 2)
        self.assertEqual(len(record["cases"][0]["runs"]), 3)
        self.assertIsNone(record["cases"][1]["cost"])
        spec["case_ids"] = ["c1"]
        with self.assertRaises(ValueError):
            evo.report(value, spec, "2026-10-28T12:00:00Z", "Test", "Incomplete")

    def test_cross_domain_matrices_cannot_duplicate_trials_or_change_runtime(self):
        first = matrix()
        for kind in ("duplicate domain", "session", "runtime", "runs"):
            with self.subTest(kind=kind):
                second = matrix("other", scores=(20,) if kind == "runs" else (20, 50, 80))
                if kind == "duplicate domain":
                    second["benchmark_id"] = first["benchmark_id"]
                elif kind == "session":
                    second["cells"][0]["session_id"] = first["cells"][0]["session_id"]
                elif kind == "runtime":
                    second["runtime"]["model_id"] = "different"
                    for cell in second["cells"]:
                        cell["model_id"] = "different"
                with self.assertRaises(ValueError):
                    evo.summarize({"matrices": [first, second]})


class CommandTests(unittest.TestCase):
    def test_cli_rejects_duplicate_json_keys_and_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "request.json"
            output = Path(temp) / "output"
            source.write_text('{"library": [], "library": [], "topic": "orders"}')
            with patch("sys.argv", ["evo.py", "export", "--request", str(source), "--output", str(output)]):
                with redirect_stderr(io.StringIO()) as errors:
                    self.assertEqual(evo.main(), 2)
            self.assertIn("duplicate JSON key", errors.getvalue())
            self.assertFalse(output.exists())

    def test_cli_compiles_and_prints_an_exportable_library(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "request.json"
            source.write_text(json.dumps(batch()))
            with patch("sys.argv", ["evo.py", "compile", "--request", str(source)]):
                with redirect_stdout(io.StringIO()) as result:
                    self.assertEqual(evo.main(), 0)
            self.assertEqual(json.loads(result.getvalue())["library"], [entry()])


if __name__ == "__main__":
    unittest.main()

"""Behavior checks, using synthetic scores and temporary files; no model calls.

Given a repeated-case evaluation, the gate weights case means equally and normalizes percentages.
Given inconsistent improvements, the next patch shrinks even when the candidate is rejected.
Given a tie or uniform harm, the gate retains the previous Skill independently of variance.
Given missing/failed/reused/mismatched cells, assessment yields no decision.
Given differently named training cases, the numerical decision stays the same.
Given invalid parameters or nonfinite scores, assessment fails rather than spending a budget.
Given a valid patch, preparation writes only a separate candidate and preserves the source.
Given bad context, extra files, excess hunks or changed metadata, no candidate is published.
Given an empty patch or an occupied output, preparation does not overwrite any artifact.
Given a reporting matrix and a frozen batch, only that batch drives the gate.
Given an incomplete reporting matrix, a smaller gate batch cannot hide the failure.
Given scored repeats on a fixed panel, reporting preserves trials and aggregates their scores.
Given changed coverage/runtime or a failed cell, reporting emits no scoreboard record.
"""

import copy
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from skilladam import apply_patch, assess, compare, prepare, report


SOURCE = "---\nname: skilladam-working-skill\nversion: 2026.10.13.1\n---\n\nCheck the task.\nUse evidence.\nVerify the answer.\n"


def matrix(scores, version):
    runtime = {"provider": "fixture", "model_id": "fixture", "thinking_level": "medium"}
    ids = [f"case-{i:03d}" for i in range(1, len(scores) + 1)]
    cells = []
    for case, repeats in zip(ids, scores):
        for run, score in enumerate(repeats, 1):
            cells.append(
                {
                    "protocol_version": 1,
                    "status": "ok",
                    "case_id": case,
                    "run": run,
                    "agent_id": "fixture",
                    "expected_version": version,
                    **runtime,
                    "score": score,
                    "cost": None,
                    "duration_ms": 1,
                    "session_id": f"harbor:v{version}-{case}-{run}",
                }
            )
    return {
        "benchmark_id": "fixture-training",
        "agent_id": "fixture",
        "version": version,
        "state_sha256": f"{version:064x}",
        "runtime": runtime,
        "case_ids": ids,
        "runs": len(scores[0]),
        "cells": cells,
    }


def diff(before, after, context=3):
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile="a/SKILL.md",
            tofile="b/SKILL.md",
            n=context,
        )
    )


class GateTests(unittest.TestCase):
    def test_mean_improvement_has_no_implicit_per_case_gate(self):
        before = {"train_001": 0.0, "train_002": 1.0}
        after = {"train_001": 1.0, "train_002": 0.5}
        result = compare(before, after)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["mean_gain"], 0.25)
        self.assertAlmostEqual(result["sample_variance"], 1.125)
        self.assertEqual(result["next_budget"], 1)
        self.assertFalse(compare(before, after, max_case_drop=0.1)["accepted"])

    def test_online_scores_and_shared_matrices_agree(self):
        online = compare({"a": 0.2, "b": 0.6}, {"a": 0.8, "b": 0.5})
        shared = assess(matrix([[20], [60]], 1), matrix([[80], [50]], 2))
        for key in ("accepted", "mean_gain", "next_variance", "next_budget"):
            self.assertEqual(online[key], shared[key])

    def test_online_comparison_requires_paired_finite_training_feedback(self):
        for before, after in [({}, {}), ({"a": 0}, {"b": 1}),
                              ({"a": 0}, {"a": float("nan")}),
                              ({"": 0}, {"": 1})]:
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                compare(before, after)

    def test_only_the_frozen_batch_drives_the_gate(self):
        before, after = matrix([[20], [100]], 1), matrix([[40], [0]], 2)
        selected = before["case_ids"][:1]
        result = assess(before, after, case_ids=selected)
        self.assertTrue(result["accepted"])
        self.assertEqual(list(result["per_case_deltas"]), selected)
        self.assertFalse(assess(before, after)["accepted"])
        for batch in ([], [selected[0], selected[0]], ["missing"], [None]):
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                assess(before, after, case_ids=batch)

    def test_selecting_a_batch_cannot_hide_an_incomplete_reporting_matrix(self):
        before, after = matrix([[20], [100]], 1), matrix([[40], [0]], 2)
        after["cells"].pop()
        with self.assertRaises(ValueError):
            assess(before, after, case_ids=before["case_ids"][:1])

    def test_percentage_repeats_are_paired_by_case_not_cell_order(self):
        before = matrix([[0, 100], [20, 40]], 1)
        after = matrix([[50, 100], [40, 60]], 2)
        after["cells"].reverse()
        result = assess(before, after)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["mean_gain"], 0.225)
        self.assertAlmostEqual(result["sample_variance"], 0.00125)
        self.assertEqual(result["next_budget"], 4)

    def test_rejected_tradeoff_still_shrinks_next_budget(self):
        result = assess(matrix([[0], [100]], 1), matrix([[100], [0]], 2))
        self.assertFalse(result["accepted"])
        self.assertAlmostEqual(result["sample_variance"], 2.0)
        self.assertAlmostEqual(result["next_variance"], 0.2)
        self.assertEqual(result["next_budget"], 1)

    def test_uniform_harm_and_ties_are_rejected_even_without_variance(self):
        for scores in ([[40], [40]], [[50], [50]]):
            with self.subTest(scores=scores):
                result = assess(matrix([[50], [50]], 1), matrix(scores, 2))
                self.assertFalse(result["accepted"])
                self.assertEqual(result["sample_variance"], 0)
                self.assertEqual(result["next_budget"], 4)

    def test_exact_regression_boundary_is_allowed_but_gain_must_exceed_threshold(self):
        before, after = matrix([[80], [0]], 1), matrix([[70], [40]], 2)
        self.assertTrue(assess(before, after)["accepted"])
        self.assertFalse(assess(before, after, min_gain=0.15)["accepted"])
        single = assess(matrix([[10]], 1), matrix([[30]], 2), previous_variance=0.1)
        self.assertEqual(single["sample_variance"], 0)
        self.assertAlmostEqual(single["next_variance"], 0.09)
        self.assertEqual(single["next_budget"], 1)

    def test_incomplete_failed_duplicate_or_mismatched_cells_produce_no_decision(self):
        before, after = matrix([[10], [20]], 1), matrix([[30], [40]], 2)
        bad_matrices = []
        missing = copy.deepcopy(after)
        missing["cells"].pop()
        bad_matrices.append(missing)
        duplicate = copy.deepcopy(after)
        duplicate["cells"].append(duplicate["cells"][0])
        bad_matrices.append(duplicate)
        for key, value in [
            ("status", "failed"),
            ("provider", "other"),
            ("expected_version", 1),
            ("run", 2),
            ("case_id", "unknown"),
            ("session_id", before["cells"][0]["session_id"]),
            ("duration_ms", -1),
            ("cost", -1),
            ("protocol_version", True),
        ]:
            changed = copy.deepcopy(after)
            changed["cells"][0][key] = value
            bad_matrices.append(changed)
        for bad in bad_matrices:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    assess(before, bad)

    def test_training_case_names_do_not_change_the_decision(self):
        before, after = matrix([[10]], 1), matrix([[20]], 2)
        expected = assess(before, after)
        for value in (before, after):
            value["benchmark_id"] = "custom-benchmark"
            value["case_ids"] = ["write-test-plan"]
            value["cells"][0]["case_id"] = value["case_ids"][0]
        actual = assess(before, after)
        for key in ("accepted", "mean_gain", "next_variance", "next_budget"):
            self.assertEqual(actual[key], expected[key])

    def test_nonfinite_scores_and_invalid_parameters_fail(self):
        before, after = matrix([[10]], 1), matrix([[20]], 2)
        for value in [float("nan"), float("inf"), -1, 101, True, None, "50"]:
            bad = copy.deepcopy(after)
            bad["cells"][0]["score"] = value
            with self.subTest(score=value), self.assertRaises(ValueError):
                assess(before, bad)
        for kwargs in [
            {"variance_cap": 0},
            {"beta2": 1.1},
            {"previous_variance": -1},
            {"min_budget": 5},
            {"base_budget": True},
            {"min_gain": -1},
            {"max_case_drop": float("nan")},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                assess(before, after, **kwargs)


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.matrix = matrix([[0, 100], [20, 40]], 2)
        self.spec = {
            key: self.matrix[key]
            for key in ("benchmark_id", "agent_id", "runtime", "case_ids", "runs")
        }
        self.spec["label"] = "SkillAdam smoke 2/30 Train fixture"

    def record(self, matrix=None, spec=None, time="2026-10-13T07:00:00Z"):
        return report(
            self.matrix if matrix is None else matrix,
            self.spec if spec is None else spec,
            time,
            "candidate v2",
            "Fixed panel; this is not a full Benchmark score.",
        )

    def test_fixed_panel_keeps_zero_scores_trials_and_unknown_costs(self):
        self.matrix["cells"][0]["cost"] = 0
        self.matrix["cells"][1]["cost"] = 0.002
        self.matrix["cells"].reverse()
        result = self.record()
        self.assertEqual(result["score"], 40)
        self.assertEqual(result["cost"], 0.001)
        self.assertEqual(result["cases"][0]["runs"][0]["score"], 0)
        self.assertIsNone(result["cases"][1]["cost"])
        self.assertEqual(
            result["cases"][1]["runs"][1]["session_id"],
            "harbor:v2-case-002-2",
        )
        self.assertTrue(result["summary_title"].startswith(self.spec["label"]))
        self.assertEqual(result["version"], 2)

    def test_unpriced_evaluation_remains_unpriced(self):
        self.assertIsNone(self.record()["cost"])

    def test_changed_panel_runtime_and_failed_cells_produce_no_record(self):
        for key, value in (
            ("case_ids", self.spec["case_ids"][:1]),
            ("case_ids", self.spec["case_ids"] * 2),
            ("case_ids", None),
            ("case_ids", [None]),
            ("runs", 2 + 1),
            ("benchmark_id", "another-benchmark"),
            ("agent_id", "another-target"),
            ("runtime", {"provider": "other"}),
            ("label", ""),
        ):
            spec = {**self.spec, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.record(spec=spec)
        broken = copy.deepcopy(self.matrix)
        broken["cells"][0]["status"] = "failed"
        with self.assertRaises(ValueError):
            self.record(matrix=broken)
        for timestamp in (
            "2026-10-13T07:00:00", "2026-10-13T07:00:00+01:00", "invalid"
        ):
            with self.subTest(time=timestamp), self.assertRaises(ValueError):
                self.record(time=timestamp)

    def test_cli_formats_a_complete_panel_and_rejects_a_partial_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, spec = root / "matrix.json", root / "spec.json"
            inputs.write_text(json.dumps(self.matrix))
            spec.write_text(json.dumps(self.spec))
            command = [
                sys.executable,
                str(Path(__file__).with_name("skilladam.py")),
                "report", "--matrix", str(inputs), "--spec", str(spec),
                "--time", "2026-10-13T07:00:00Z", "--step", "candidate v2",
                "--summary", "Fixed panel",
            ]
            valid = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertEqual(json.loads(valid.stdout)["score"], 40)
            self.matrix["cells"].pop()
            inputs.write_text(json.dumps(self.matrix))
            invalid = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(invalid.stdout, "")


class PatchTests(unittest.TestCase):
    def test_valid_patch_creates_separate_candidate_and_preserves_source(self):
        candidate = SOURCE.replace(
            "Use evidence.", "Gather evidence before drawing conclusions."
        )
        with tempfile.TemporaryDirectory() as directory:
            source, output = (
                Path(directory) / "SKILL.md",
                Path(directory) / "candidate.md",
            )
            source.write_text(SOURCE)
            result = prepare(
                source,
                {
                    "reasoning": "Evidence was missing.",
                    "patch": diff(SOURCE, candidate),
                },
                1,
                output,
            )
            self.assertEqual(result["status"], "ready")
            self.assertEqual(source.read_text(), SOURCE)
            self.assertEqual(output.read_text(), candidate)

    def test_insertions_deletions_and_separate_hunks_apply_exactly(self):
        for candidate in [
            SOURCE + "Check the output format.\n",
            SOURCE.replace("Use evidence.\n", ""),
            SOURCE.replace("Check the task.", "Read the task.").replace(
                "Verify the answer.", "Verify the format."
            ),
        ]:
            with self.subTest(candidate=candidate):
                result, _ = apply_patch(SOURCE, diff(SOURCE, candidate, context=0), 2)
                self.assertEqual(result, candidate)

    def test_bad_context_paths_metadata_or_budget_never_create_an_output(self):
        good = diff(SOURCE, SOURCE.replace("Use evidence.", "Inspect evidence."))
        candidates = [
            good.replace("Use evidence.", "Missing line."),
            good.replace("a/SKILL.md", "a/../AGENTS.md"),
            diff(SOURCE, SOURCE.replace("2026.10.13.1", "2026.10.13.2")),
            diff(
                SOURCE,
                SOURCE.replace("Check the task.", "Read the task.").replace(
                    "Verify the answer.", "Verify the format."
                ),
                context=0,
            ),
            good + "--- a/AGENTS.md\n+++ b/AGENTS.md\n@@ -1 +1 @@\n-old\n+new\n",
            re.sub(r"@@ .*? @@", "@@ -4,9 +4,9 @@", good, count=1),
            diff(
                SOURCE,
                "---\nname: skilladam-working-skill\nversion: 2026.10.13.1\n---\n\n",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            source, output = (
                Path(directory) / "SKILL.md",
                Path(directory) / "candidate.md",
            )
            source.write_text(SOURCE)
            for patch in candidates:
                with self.subTest(patch=patch), self.assertRaises(ValueError):
                    prepare(source, {"reasoning": "test", "patch": patch}, 1, output)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_text(), SOURCE)

    def test_empty_patch_and_existing_output_do_not_overwrite_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = (
                Path(directory) / "SKILL.md",
                Path(directory) / "candidate.md",
            )
            source.write_text(SOURCE)
            self.assertEqual(
                prepare(
                    source, {"reasoning": "no recurring issue", "patch": ""}, 1, output
                )["status"],
                "noop",
            )
            self.assertFalse(output.exists())
            output.write_text("previous candidate\n")
            with self.assertRaises(FileExistsError):
                prepare(
                    source,
                    {"reasoning": "test", "patch": diff(SOURCE, SOURCE + "Check.\n")},
                    1,
                    output,
                )
            self.assertEqual(output.read_text(), "previous candidate\n")

    def test_cli_rejects_invalid_json_without_creating_a_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            proposal, output = (
                Path(directory) / "proposal.json",
                Path(directory) / "candidate.md",
            )
            proposal.write_text('{"patch":"", "patch":"", "reasoning":"duplicate"}')
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("skilladam.py")),
                    "prepare",
                    "--skill",
                    str(Path(directory) / "missing.md"),
                    "--proposal",
                    str(proposal),
                    "--budget",
                    "1",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("duplicate", json.loads(result.stderr)["error"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

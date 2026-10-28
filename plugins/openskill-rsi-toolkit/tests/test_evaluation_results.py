"""Repeated-test reporting scenarios; no network, model or evaluator calls.

Given three complete repetitions, report sample SD of repetition means and native scoreboard records.
Given opposing task fluctuations, distinguish whole-test SD from mean task variance.
Given one repetition, report unavailable sample variance/SD rather than zero.
Given missing, duplicated, failed or mismatched cells, publish no aggregate.
Given a reused trial across cases or States, reject duplicate measurement evidence.
Given unknown costs, retain null totals and keep scored-trial duration separate from wall time.
Given several selected benchmarks, aggregate equally within repetitions before calculating SD.
Given omitted benchmarks or incompatible repetitions/runtimes, reject an overall result.
Given construction or changed frozen artifacts, the journal reporting boundary refuses statistics.
Given declared accuracy and fixed versions, show base/final mean, std and measured gain.
Given virtual revisions, retain actual nonmonotonic proxy measurements without inventing Train accuracy.
Given resource records, join each test cell and include failed attempts in separate Train/Test totals.
Given mismatched resource identity or duplicated campaign usage, refuse misleading attribution.
"""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import evaluation_results as results
import experiment


def fixture(benchmark="test", rows=((40, 50, 60), (80, 90, 100))):
    cases = [f"case-{i}" for i in range(len(rows))]
    runs = len(rows[0])
    runtime = {"provider": "example", "model_id": "flash", "thinking_level": "max"}
    state = experiment.initialize({"benchmark_id": "train", "case_ids": ["train-1"],
                                   "test_benchmark_id": benchmark, "test_case_ids": cases,
                                   "test_agent_id": "target-" + benchmark, "runs": runs,
                                   "runtime": {"construction": runtime, "target": runtime}})
    state.update(phase="evaluation", measured_states={
        "baseline": {"version": 1, "sha256": "a" * 64}, "final": {"version": 2, "sha256": "b" * 64}})
    state["evaluation_plan"] = experiment.evaluation_plan(state)
    matrices = []
    for variant, snapshot in state["measured_states"].items():
        cells = [{"protocol_version": 1, "status": "ok", "case_id": case, "run": r,
                  "agent_id": state["config"]["test_agent_id"], "expected_version": snapshot["version"],
                  **runtime, "score": score, "cost": 0.1, "duration_ms": 1000,
                  "session_id": f"{benchmark}-{variant}-{case}-{r}"}
                 for case, row in zip(cases, rows) for r, score in enumerate(row, 1)]
        matrices.append({"variant": variant, "benchmark_id": benchmark, "cells": cells})
    return state, matrices


def report(state, matrices):
    return results.report(state, matrices, "2026-10-28T00:00:00Z", "Frozen State")


class EvaluationResultsTest(unittest.TestCase):
    def test_accuracy_comparison_and_versions_identify_the_measured_states(self):
        state, matrices = fixture()
        state["config"].update(experiment_version="campaign-user-v2",
                               reporting_metric={"name": "accuracy", "definition": "Benchmark-defined mean correctness"},
                               component_versions={"harness": "test-version", "model_revision": None})
        for cell in matrices[1]["cells"]:
            cell["score"] = 50 + cell["score"] / 2
        result = report(state, matrices)
        self.assertEqual(result["experiment_version"], "campaign-user-v2")
        self.assertEqual(result["versions"]["declared"]["harness"], "test-version")
        self.assertEqual(result["matrices"][0]["accuracy"], {"mean": 70, "std": 10, "scale": "0..100"})
        self.assertEqual(result["comparison"]["final_minus_baseline"]["mean"], 15)
        self.assertEqual(result["comparison"]["final_minus_baseline"]["std"], 5)
        state["config"]["reporting_metric"]["name"] = "benchmark_score"
        self.assertIsNone(report(state, matrices)["matrices"][0]["accuracy"])

    def test_virtual_training_curve_is_not_a_target_score_curve(self):
        state, matrices = fixture()
        attempts = [{"number": i, "revision": i - 1, "execution_status": "completed",
                     "result": {"status": "ok", "passed": passed, "total": 10, "pass_rate": passed / 10},
                     "evidence": {"suite.py": "sha"}, "coverage_complete": False,
                     "feedback": {"action": "feedback", "next_action": "revise_skill", "classification": "SELF-FIXABLE"}}
                    for i, passed in [(1, 8), (2, 5)]]
        attempts.append({"number": 3, "revision": 2, "execution_status": "interrupted"})
        state["cases"] = {"train-1": {"skills": ["read", "decide"], "attempts": attempts,
                                      "revisions": [{}, {}, {}], "reason": "time_budget", "final_was_tested": False}}
        train = report(state, matrices)["training"]
        self.assertIsNone(train["accuracy"])
        self.assertIsNone(train["std"])
        self.assertIsNone(train["benchmark_score_curve"])
        self.assertEqual([v["virtual_pass_rate"] for v in train["units"][0]["virtual_curve"]], [0.8, 0.5, None])
        self.assertEqual(train["units"][0]["virtual_curve"][0]["feedback_action"], "revise_skill")
        self.assertEqual(train["units"][0]["skill_ids"], ["train-1/read", "train-1/decide"])

    def test_resource_rows_bind_to_cells_and_keep_failed_attempt_cost(self):
        state, matrices = fixture()
        cell = matrices[0]["cells"][0]
        def resource(key, phase, case, cost, **extra):
            return {"record_id": key, "phase": phase, "case_id": case, "status": "completed",
                    "usage_ids": [key], "artifact_paths": [key + ".json"], "format": "canonical",
                    "usage": {"cost_usd": cost, "duration_ms": 1000,
                              "tokens": {"cached_input": 40, "uncached_input": 60, "output": 20}}, **extra}
        train = resource("train-1-execution", "train", "train-1", 3)
        measured = resource("scored-test", "test", cell["case_id"], cell["cost"],
                            variant="baseline", run=1, session_id=cell["session_id"])
        failed = resource("failed-test", "test", cell["case_id"], 0.05, status="failed",
                          variant="baseline", run=1, session_id="failed-trial")
        ledger = {"schema_version": 1, "coverage": {"train": "complete", "test": "partial"},
                  "records": [train, measured, failed]}
        result = results.report(state, matrices, "2026-10-28T00:00:00Z", "Test", ledger)
        self.assertEqual(result["resources"]["totals"]["train"]["cost_usd"]["total"], 3)
        self.assertAlmostEqual(result["resources"]["totals"]["test"]["cost_usd"]["known_total"], 1.25)
        self.assertIsNone(result["resources"]["totals"]["test"]["cost_usd"]["total"])
        trial = result["matrices"][0]["cases"][0]["trials"][0]
        self.assertEqual(trial["resources"]["tokens"]["total"], 120)
        self.assertEqual(len(result["matrices"][0]["cases"][0]["trials"]), 3)
        self.assertEqual(result["matrices"][0]["mean"], 70)
        for change in [{"run": 2}, {"variant": "final"}, {"status": "failed"},
                       {"usage": {"cost_usd": 999}}]:
            bad = copy.deepcopy(ledger)
            bad["records"][1].update(change)
            with self.assertRaises(ValueError):
                results.report(state, matrices, "2026-10-28T00:00:00Z", "Test", bad)

    def test_three_complete_test_scores_have_sample_standard_deviation(self):
        state, matrices = fixture()
        before = copy.deepcopy((state, matrices))
        value = report(state, matrices)["matrices"][0]
        self.assertEqual(value["repetition_scores"], [60, 70, 80])
        self.assertEqual(value["mean"], 70)
        self.assertEqual(value["sample_std"], 10)
        self.assertEqual(value["sample_variance"], 100)
        self.assertEqual(value["state_sha256"], "a" * 64)
        record = value["scoreboard_record"]
        self.assertEqual(record["score"], 70)
        self.assertEqual([r["score"] for r in record["cases"][0]["runs"]], [40, 50, 60])
        self.assertNotIn("sample_std", record)  # The native scoreboard schema stays unchanged.
        self.assertIn("sample SD 10.00", record["summary"])
        self.assertEqual((state, matrices), before)

    def test_mean_task_variance_is_not_whole_test_variance(self):
        value = report(*fixture(rows=((0, 50, 100), (100, 50, 0))))["matrices"][0]
        self.assertEqual(value["repetition_scores"], [50, 50, 50])
        self.assertEqual(value["sample_std"], 0)
        self.assertEqual(value["mean_case_sample_variance"], 2500)
        self.assertEqual([c["sample_std"] for c in value["cases"]], [50, 50])

    def test_one_repetition_has_no_sample_standard_deviation(self):
        value = report(*fixture(rows=((0,), (100,))))["matrices"][0]
        self.assertEqual(value["mean"], 50)
        self.assertIsNone(value["sample_std"])
        self.assertIsNone(value["sample_variance"])
        self.assertIsNone(value["mean_case_sample_variance"])
        self.assertIsNone(value["cases"][0]["sample_std"])

    def test_invalid_measurements_cannot_be_reported(self):
        state, original = fixture()
        mutations = []
        for key, value in [("score", float("nan")), ("score", True), ("score", 101),
                           ("cost", -1), ("cost", float("inf")), ("duration_ms", True),
                           ("duration_ms", -1), ("status", "failed"), ("protocol_version", True),
                           ("model_id", "different"), ("thinking_level", "low"), ("provider", "other"),
                           ("agent_id", "other"), ("expected_version", 99), ("run", True),
                           ("case_id", "unexpected"), ("session_id", "")]:
            changed = copy.deepcopy(original)
            changed[0]["cells"][0][key] = value
            mutations.append(changed)
        short = copy.deepcopy(original); short[0]["cells"].pop(); mutations.append(short)
        duplicate = copy.deepcopy(original); duplicate[0]["cells"].append(duplicate[0]["cells"][0]); mutations.append(duplicate)
        wrong_hash = copy.deepcopy(original); wrong_hash[0]["state_sha256"] = "c" * 64; mutations.append(wrong_hash)
        empty = copy.deepcopy(original); empty.append({"variant": "extra", "benchmark_id": "test", "cells": []}); mutations.append(empty)
        missing_cost = copy.deepcopy(original); del missing_cost[0]["cells"][0]["cost"]; mutations.append(missing_cost)
        mutations.extend([[], original[:-1], original + [original[0]]])
        for index, matrices in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                report(state, matrices)

    def test_reused_trial_is_rejected_even_across_variants(self):
        state, original = fixture()
        for matrix_index, cell_index in [(0, 1), (1, 0)]:
            matrices = copy.deepcopy(original)
            matrices[matrix_index]["cells"][cell_index]["session_id"] = matrices[0]["cells"][0]["session_id"]
            with self.assertRaisesRegex(ValueError, "trial/session"):
                report(state, matrices)

    def test_unknown_costs_are_not_reported_as_zero(self):
        state, matrices = fixture()
        for cell in matrices[0]["cells"]:
            cell["cost"] = None
        value = report(state, matrices)["matrices"][0]
        self.assertIsNone(value["scoreboard_record"]["cost"])
        self.assertIsNone(value["scored_trial_cost"]["total"])
        self.assertEqual(value["scored_trial_cost"]["unknown_trials"], 6)
        self.assertEqual(value["summed_trial_duration_ms"], 6000)
        self.assertEqual(value["scoreboard_record"]["duration_ms"], 1000)
        matrices[0]["cells"][0]["cost"] = 1
        value = report(state, matrices)["matrices"][0]
        self.assertEqual(value["scored_trial_cost"]["known_total"], 1)
        self.assertIsNone(value["scored_trial_cost"]["total"])

    def test_overall_averages_benchmarks_within_each_repetition(self):
        a = report(*fixture("test-a"))  # Two cases, repeat means 60, 70, 80.
        b = report(*fixture("test-b", ((80, 70, 60),)))  # One case, inverse fluctuation.
        total = results.aggregate([a, b], ["test-a", "test-b"])
        self.assertEqual(total["variants"][0]["repetition_scores"], [70, 70, 70])
        self.assertEqual(total["variants"][0]["sample_std"], 0)
        single = results.aggregate([report(*fixture(rows=((50,),)))], ["test"])
        self.assertIsNone(single["variants"][0]["sample_std"])

    def test_incomplete_or_incompatible_campaign_has_no_overall_score(self):
        a = report(*fixture("test-a"))
        b = report(*fixture("test-b"))
        for reports in [[a], [a, a], [a, report(*fixture("test-b", ((50,),)))]]:
            with self.assertRaises(ValueError):
                results.aggregate(reports, ["test-a", "test-b"])
        for mutation in ("runtime", "variant", "session"):
            bad = copy.deepcopy(b)
            if mutation == "runtime":
                bad["matrices"][0]["runtime"]["model_id"] = "other"
            elif mutation == "variant":
                bad["matrices"].pop()
            else:
                bad["matrices"][0]["scoreboard_record"]["cases"][0]["runs"][0]["session_id"] = (
                    a["matrices"][0]["scoreboard_record"]["cases"][0]["runs"][0]["session_id"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                results.aggregate([a, bad], ["test-a", "test-b"])

    def test_journal_report_refuses_construction(self):
        state, _ = fixture()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            experiment.run("init", out, state["config"])
            with self.assertRaisesRegex(ValueError, "global freeze"):
                results.from_journal(out, "matrices.json", "2026-10-28T00:00:00Z", "Test")

    def test_reporting_requires_a_utc_timestamp_and_public_summary(self):
        state, matrices = fixture()
        for time, summary in [("2026-10-28T00:00:00", "Test"), ("2026-10-28T00:00:00+08:00", "Test"),
                              ("2026-10-28T00:00:00Z", "")]:
            with self.assertRaises(ValueError):
                results.report(state, matrices, time, summary)


if __name__ == "__main__":
    unittest.main()

"""Exercise the public experiment helper with real temporary artifacts.

Given unfinished construction, evaluation and global freezing are refused without journal changes.
Given one completed construction, every evaluation repetition uses its same frozen States.
Given completed matrices, the read-only report uses the journal and cannot change its records.
Given a campaign manifest, the CLI aggregates its selected Benchmarks and refuses omissions.
Given a declared experiment/component version, initialization records it and resume preserves it.
Given a test split, only its declared cells enter final evaluation; test Cases cannot enter construction.
Given independent verification, passing checks with missing requirements cannot claim success.
Given verifier failures, each reserved attempt spends budget even when no report was produced.
Given three failed attempts, the final revision remains exportable but cannot be tested a fourth time.
Given a passing revision, further refinement and retrieval are refused.
Given frozen artifacts, construction stays closed and modified libraries cannot be evaluated.
Given incomplete, duplicate or mismatched cells, completion is refused without changing the scoreboard.
Given saved events, a new reader recovers creator identity and attempts; corrupt history is rejected.
Given a fixed plan, changing the creator, mutating outputs or overwriting evidence is rejected.
Given a deadline, new work stops and the last valid artifacts can be preserved honestly.
Given contaminated construction, no artifact can be deployed.
Given malformed configuration or an existing experiment, initialization leaves it untouched.
Given a knowledge gap, failed searches still spend the declared retrieval budget.
Given an opted-in empty-reader control, it adds its own fixed evaluation matrix.
Given a malformed coverage map, the attempt is recorded as incomplete and still spends budget.
Given a reserved attempt, dispatch can bind its separate verifier after reservation.
Given an older passing artifact, freeze refuses to replace the last registered revision with it.
Given CLI errors or a concurrent writer, no extra journal event is published.
Given passing checks but an unusable skill, structural diagnostics prevent a success claim.
Given failed verification, continuing without a complete diagnosis is refused without a journal write.
Given a skill repair, unchanged bytes cannot count as refinement; an explicit execution repair can rerun them.
Given an execution receipt, wrong identities, stale timestamps and missing evidence cannot register practice.
Given an interrupted or unstarted verifier, even a passing XML cannot mark the final artifact tested.
Given an earlier valid measurement, a later verifier error does not erase that measurement.
Given NEEDS-DR, a reserved or failed search cannot stand in for retrieved evidence.
Given a recoverable failure, a bare stop label cannot end construction as an unrecoverable error.
Given a false oracle claim, verifier repair requires an independent correction and cannot repair skill structure.
Given the last failed verification, stopping at the cap cannot omit its recorded skill repair.
Given an exhausted verifier budget, repair-only termination can preserve an honestly untested artifact.
Given a near deadline, read-only guidance permits remaining work and switches to abort only at expiry.
Given no explicit short budget, ongoing verification can continue beyond a smoke run's window.
Given an explicitly shortened budget, reopening the journal preserves its original deadline.
Given practice finished before its deadline, delayed collection succeeds but late execution is rejected.
Given sealed recovery evidence, subsequent mutation prevents freezing.
Given a schema-1 journal, status remains readable and new events cannot migrate it.
Given executable faulty skills, independent feedback followed by a real code change fixes regenerated output.
Given required process review, missing, stale or unresolved evidence blocks completion;
valid review permits completion, but later evidence changes prevent global freezing.
"""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import experiment
from artifacts import check_case, check_library, check_usage, digest, read_json, tree


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def skill(root, case="train-1", name="calculate"):
    folder = root / name
    (folder / "scripts").mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Compute totals from supplied rows.\nversion: 2026.10.15.1\n---\n"
        "Use scripts/total.py relative to this skill.\n", encoding="utf-8")
    (folder / "scripts/total.py").write_text("print(sum([1, 2]))\n", encoding="utf-8")
    write_json(folder / "contract.json", {"id": f"{case}/{name}", "applies_when": "Sum numeric rows",
               "parameters": {"input_file": "Path to public rows"}, "outputs": ["total: integer sum"],
               "checks": ["Compare with independently computed sum"], "limitations": [],
               "resources": ["scripts/total.py"]})


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "experiment"
        self.config = {"benchmark_id": "train", "case_ids": ["train-1"], "test_agent_id": "target",
                       "test_benchmark_id": "test", "test_case_ids": ["test-1", "test-2"],
                       "runtime": {role: {"provider": "example", "model_id": "model", "thinking_level": "medium"}
                                   for role in ("construction", "target")}}
        experiment.run("init", self.out, self.config)

    def event(self, action, **kwargs):
        return experiment.run("event", self.out, {"action": action, **kwargs})

    def ce(self, action, **kwargs):
        if action == "finish-verification":
            kwargs.setdefault("execution_status", "completed")
        return self.event(action, case_id="train-1", **kwargs)

    def status(self):
        return experiment.run("status", self.out)

    def rejected(self, action, **kwargs):
        before = self.status()
        with self.assertRaises((ValueError, KeyError, OSError)):
            self.event(action, **kwargs)
        self.assertEqual(self.status(), before)

    def draft(self):
        self.ce("start-case")
        self.ce("plan", skills=["calculate"], creator_session_id="creator")
        self.root = self.out / "tasks/train-1"
        skill(self.root / "skills")
        self.revision(0)

    def revision(self, number):
        if number:
            self.feedback()
        outputs = self.root / "practice" / f"revision-{number}"
        outputs.mkdir(parents=True)
        (outputs / "total.txt").write_text("3\n", encoding="utf-8")
        if number:
            with (self.root / "skills/calculate/scripts/total.py").open("a") as stream:
                stream.write(f"# revision {number}\n")
        return self.ce("revision", creator_session_id="creator", hypothesis="Sum rows before formatting",
                       execution_record=self.receipt(number))

    def receipt(self, number, **changes):
        stamp = datetime.now(timezone.utc).isoformat()
        log = self.root / "executions" / f"run-{number}.log"
        log.parent.mkdir(exist_ok=True)
        log.write_text("Executed total.py; wrote total.txt; exit 0\n")
        relative = f"tasks/train-1/executions/run-{number}.json"
        write_json(self.out / relative, {"creator_session_id": "creator",
            "skills_sha256": digest(tree(self.root / "skills")),
            "output_directory": f"tasks/train-1/practice/revision-{number}",
            "commands": ["python3 calculate/scripts/total.py"], "exit_code": 0,
            "started_at": stamp, "finished_at": stamp,
            "evidence": [log.relative_to(self.out).as_posix()], **changes})
        return relative

    def feedback(self, action="revise_skill", classification="SELF-FIXABLE", **changes):
        last = self.status()["cases"]["train-1"]["attempts"][-1]
        log = self.root / "diagnoses" / f'attempt-{last["number"]}.txt'
        log.parent.mkdir(exist_ok=True)
        log.write_text("Independent arithmetic expectation and observed output disagree.\n")
        return self.ce("feedback", **{"attempt": last["number"], "classification": classification,
            "next_action": action, "issues": experiment.workflow.issues(last), "diagnosis": "Inspect the failed arithmetic check",
            "expected_change": "Regenerated output agrees with independent sum", "evidence": [log.relative_to(self.out).as_posix()],
            **changes})

    def stop(self, reason, **changes):
        log = self.root / "stop.log"
        log.write_text("Role stopped; unavailable execution dependency confirmed.\n")
        relative = "tasks/train-1/stop.json"
        write_json(self.out / relative, {"reason": reason, "cause": "Execution dependency unavailable",
            "workers_stopped": True, "recoverable": False, "why_recovery_impossible": "Offline dependency has no available replacement",
            "interruption": "host_interruption", "evidence": [log.relative_to(self.out).as_posix()], **changes})
        return self.ce("finish-case", reason=reason, record=relative)

    def verify(self, passed=True, covered=True):
        state = self.ce("begin-verification", verifier_session_id="verifier")
        folder = Path(state["cases"]["train-1"]["attempts"][-1]["directory"])
        folder.mkdir(parents=True)
        (folder / "suite.py").write_text("def test_sum():\n    assert 1 + 2 == 3\n", encoding="utf-8")
        outcome = "" if passed else '<failure message="wrong total"/>'
        (folder / "report.xml").write_text(f'<testsuite><testcase classname="rows" name="sum">{outcome}</testcase></testsuite>')
        write_json(folder / "coverage.json", [{"requirement": "sum", "required": True,
                   "source": "Public arithmetic rule", "status": "covered" if covered else "unverified",
                   "tests": ["rows::sum"]}])
        return self.ce("finish-verification", pytest_exit_code=0 if passed else 1)

    def assemble(self):
        library = self.out / "library"
        shutil.copytree(self.root / "skills", library / "tasks/train-1")
        (library / "SKILL.md").write_text("Read index.md.\n")
        (library / "index.md").write_text("Sum rows: tasks/train-1/calculate/SKILL.md\n")

    def frozen(self):
        self.draft()
        self.verify()
        self.ce("finish-case", reason="surrogate_pass")
        self.assemble()
        return self.event("freeze")

    def test_process_review_cannot_be_skipped_stale_or_changed_after_acceptance(self):
        # Start a separate journal through the public helper with the new-run review requirement.
        self.out = self.out.parent / "reviewed"
        experiment.run("init", self.out, {**self.config, "process_review_required": True})
        self.draft()
        self.verify()
        revision = self.status()["cases"]["train-1"]["revisions"][-1]
        finish = {"case_id": "train-1", "reason": "surrogate_pass", "process_review": "tasks/train-1/review/final.json"}
        self.rejected("finish-case", **finish)
        review = {key: revision[key] for key in ("skills_sha256", "outputs_sha256")}
        review["checks"] = {key: {"status": "passed", "finding": "Reviewed public fixture and reusable sum artifact",
            "evidence": ["tasks/train-1/executions/run-0.log", "tasks/train-1/skills/calculate/SKILL.md"]}
            for key in ("delivery", "portable_content", "construction_isolation")}
        path = self.out / finish["process_review"]
        write_json(path, {**review, "skills_sha256": "0" * 64})
        self.rejected("finish-case", **finish)
        for key in review["checks"]:
            bad = copy.deepcopy(review)
            bad["checks"][key]["status"] = "unverified"
            write_json(path, bad)
            self.rejected("finish-case", **finish)
        write_json(path, review)
        self.event("finish-case", **finish)
        self.assemble()
        path.write_text(path.read_text() + "\n")
        self.rejected("freeze")

    def begin_evaluation(self):
        variants = {p["variant"] for p in self.status()["evaluation_plan"]}
        self.snapshots = {v: {"version": i + 1, "sha256": "a" * 64} for i, v in enumerate(sorted(variants))}
        return self.event("begin-evaluation", states=self.snapshots)

    def matrices(self):
        result = []
        for variant, snapshot in self.snapshots.items():
            cells = []
            for case in ("test-1", "test-2"):
                for run in range(1, self.status()["config"]["runs"] + 1):
                    cells.append({"protocol_version": 1, "case_id": case, "run": run,
                                  "status": "ok", "agent_id": "target",
                                  **self.config["runtime"]["target"], "expected_version": snapshot["version"],
                                  "score": 100, "cost": None, "duration_ms": 10,
                                  "session_id": f"trial-{variant}-{case}-{run}"})
            result.append({"variant": variant, "benchmark_id": "test", "cells": cells})
        return result

    def test_unfinished_construction_cannot_freeze_or_evaluate(self):
        self.rejected("freeze")
        self.rejected("begin-evaluation", states={})
        self.rejected("start-case", case_id="test-1")

    def test_experiment_versions_are_fixed_when_reopening_the_journal(self):
        out = Path(self.temp.name) / "versioned"
        config = {**self.config, "experiment_version": "requested-v3",
                  "component_versions": {"harness": "installed-version", "model_revision": None}}
        initial = experiment.run("init", out, config)
        experiment.run("event", out, {"action": "start-case", "case_id": "train-1"})
        restored = experiment.run("status", out)
        self.assertEqual(restored["config"]["experiment_version"], "requested-v3")
        self.assertEqual(restored["config"]["component_versions"], initial["config"]["component_versions"])
        self.assertEqual(restored["config"]["component_versions"]["harness"], "installed-version")
        self.assertIsNone(restored["config"]["component_versions"]["model_revision"])

    def test_split_evaluates_only_held_out_cells_and_closes_construction(self):
        state = self.frozen()
        self.assertEqual({p["benchmark_id"] for p in state["evaluation_plan"]}, {"test"})
        self.assertEqual({p["case_id"] for p in state["evaluation_plan"]}, {"test-1", "test-2"})
        self.rejected("start-case", case_id="train-1")
        self.begin_evaluation()
        write_json(self.out / "matrices.json", self.matrices())
        result = self.event("finish-evaluation", outcome="complete", record="matrices.json")
        self.assertEqual(result["phase"], "evaluated")
        self.rejected("begin-evaluation", states=self.snapshots)

    def test_single_construction_supplies_every_frozen_state_repetition(self):
        state = self.frozen()
        self.assertEqual(set(state["cases"]), {"train-1"})
        self.assertEqual(len(state["cases"]["train-1"]["revisions"]), 1)
        self.assertEqual({(p["variant"], p["case_id"], p["run"]) for p in state["evaluation_plan"]},
                         {(v, c, r) for v in ("baseline", "final")
                          for c in ("test-1", "test-2") for r in (1, 2, 3)})
        self.begin_evaluation()
        self.rejected("start-case", case_id="train-1")
        matrices = self.matrices()
        matrices[0]["cells"][-1]["session_id"] = matrices[1]["cells"][0]["session_id"]
        write_json(self.out / "matrices.json", matrices)
        self.rejected("finish-evaluation", outcome="complete", record="matrices.json")

    def test_reporting_completed_journal_is_read_only(self):
        self.frozen()
        self.begin_evaluation()
        write_json(self.out / "matrices.json", self.matrices())
        self.event("finish-evaluation", outcome="complete", record="matrices.json")
        write_json(self.out / "measurements.json", {"schema_version": 1, "records": []})
        before = tree(self.out)
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "evaluation_results.py"),
                                 "report", str(self.out), "matrices.json", "--time", "2026-10-28T00:00:00Z",
                                 "--measurements", "measurements.json",
                                 "--summary", "Frozen library evaluation"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["matrices"][0]["repetition_scores"], [100, 100, 100])
        self.assertEqual(report["matrices"][0]["state_sha256"], self.snapshots["baseline"]["sha256"])
        self.assertEqual(report["measurements_sha256"], digest({"schema_version": 1, "records": []}))
        self.assertIsNotNone(report["training"]["units"][0]["construction_time"]["duration_ms"])
        self.assertEqual(report["training"]["units"][0]["skills"][0]["version"], "2026.10.15.1")
        self.assertEqual(tree(self.out), before)
        with self.assertRaisesRegex(ValueError, "differs from the completed"):
            write_json(self.out / "different.json", self.matrices()[:-1])
            experiment.evaluation_results.from_journal(self.out, "different.json", "2026-10-28T00:00:00Z", "Test")
        (self.out / "library/index.md").write_text("Changed after evaluation")
        with self.assertRaisesRegex(ValueError, "Frozen library changed"):
            experiment.evaluation_results.from_journal(self.out, "matrices.json", "2026-10-28T00:00:00Z", "Test")

    def test_campaign_cli_requires_every_declared_benchmark(self):
        self.frozen()
        self.begin_evaluation()
        write_json(self.out / "matrices.json", self.matrices())
        manifest = Path(self.temp.name) / "campaign.json"
        plan = {"benchmark_ids": ["test"],
                "experiments": [{"out": str(self.out), "record": "matrices.json"}]}
        write_json(manifest, plan)
        before = tree(self.out)
        command = [sys.executable, "-B", str(SCRIPTS / "evaluation_results.py"), "aggregate", str(manifest),
                   "--time", "2026-10-28T00:00:00Z", "--summary", "Frozen State campaign"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["overall"]["variants"][0]["repetition_scores"], [100, 100, 100])
        self.assertEqual(tree(self.out), before)
        plan["benchmark_ids"].append("missing")
        write_json(manifest, plan)
        rejected = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(rejected.stdout, "")
        self.assertIn("incomplete", rejected.stderr)
        self.assertEqual(tree(self.out), before)

    def test_coverage_gap_prevents_claiming_success(self):
        self.draft()
        result = self.verify(covered=False)
        self.assertFalse(result["cases"]["train-1"]["attempts"][-1]["accepted"])
        self.rejected("finish-case", case_id="train-1", reason="surrogate_pass")

    def test_passing_checks_do_not_hide_a_broken_skill_contract(self):
        self.ce("start-case")
        self.ce("plan", skills=["calculate"], creator_session_id="creator")
        self.root = self.out / "tasks/train-1"
        skill(self.root / "skills")
        contract = self.root / "skills/calculate/contract.json"
        data = read_json(contract)
        data["resources"].append("scripts/missing.py")
        write_json(contract, data)
        self.revision(0)
        state = self.verify()
        attempt = state["cases"]["train-1"]["attempts"][-1]
        self.assertFalse(attempt["accepted"])
        self.assertIn("missing.py", attempt["structure_error"])
        self.rejected("finish-case", case_id="train-1", reason="surrogate_pass")
        before = self.status()
        with self.assertRaises(ValueError):
            self.feedback(action="repair_verifier")
        self.assertEqual(self.status(), before)

    def test_failed_verifier_attempts_spend_budget_without_a_report(self):
        self.draft()
        for _ in range(3):
            self.ce("begin-verification", verifier_session_id="verifier")
            result = self.ce("finish-verification", pytest_exit_code=2)
            self.assertEqual(result["cases"]["train-1"]["attempts"][-1]["result"]["status"], "failed")
            self.feedback(action="repair_verifier")
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")

    def test_last_revision_is_exported_untested_without_best_of_n(self):
        self.draft()
        for number in range(1, 4):
            self.verify(passed=False)
            self.revision(number)
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")
        state = self.ce("finish-case", reason="max_refinement_retries")
        case = state["cases"]["train-1"]
        self.assertFalse(case["final_was_tested"])
        self.assertNotEqual(case["final_sha256"], case["last_tested_sha256"])
        self.assemble()
        self.assertEqual(self.event("freeze")["library"]["cases"]["train-1"]["sha256"], case["final_sha256"])

    def test_complete_pass_stops_refinement_and_gap_search(self):
        self.draft()
        self.verify()
        self.rejected("revision", case_id="train-1", creator_session_id="creator", hypothesis="More work")
        self.rejected("targeted-search", case_id="train-1", classification="NEEDS-DR", query="arithmetic")

    def test_changed_frozen_library_cannot_start_evaluation(self):
        self.frozen()
        (self.out / "library/index.md").write_text("changed")
        self.rejected("begin-evaluation", states={})

    def test_incomplete_duplicate_wrong_runtime_and_version_cannot_complete(self):
        self.frozen()
        self.begin_evaluation()
        complete = self.matrices()
        mutations = []
        short = copy.deepcopy(complete); short[0]["cells"].pop(); mutations.append(short)
        duplicate = copy.deepcopy(complete); duplicate[0]["cells"].append(duplicate[0]["cells"][0]); mutations.append(duplicate)
        for key, value in (("model_id", "different"), ("expected_version", 999), ("score", float("nan"))):
            changed = copy.deepcopy(complete); changed[0]["cells"][0][key] = value; mutations.append(changed)
        for value in mutations:
            write_json(self.out / "matrices.json", value)
            self.rejected("finish-evaluation", outcome="complete", record="matrices.json")
        self.assertFalse((self.out / "scoreboard.yaml").exists())
        self.rejected("finish-evaluation", outcome="incomplete", record="failure.md")
        (self.out / "failure.md").write_text("Missing cells; no aggregate published.\n")
        self.assertEqual(self.event("finish-evaluation", outcome="incomplete", record="failure.md")["phase"], "evaluated")

    def test_resume_preserves_creator_and_rejects_corrupt_history(self):
        self.draft()
        self.verify(passed=False)
        state = experiment.run("status", Path(str(self.out)))
        self.assertEqual(state["cases"]["train-1"]["creator_session_id"], "creator")
        self.assertEqual(len(state["cases"]["train-1"]["attempts"]), 1)
        first = self.out / "journal/000001.json"
        data = read_json(first); data["state"]["config"]["runs"] = 9; write_json(first, data)
        with self.assertRaises(ValueError):
            self.status()

    def test_fixed_creator_and_independent_verifier_are_required(self):
        self.draft()
        self.rejected("plan", case_id="train-1", skills=["other"], creator_session_id="replacement")
        self.rejected("revision", case_id="train-1", creator_session_id="replacement", hypothesis="retry")
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="creator")

    def test_changed_outputs_and_old_evidence_prevent_freeze(self):
        self.draft()
        self.ce("begin-verification", verifier_session_id="verifier")
        output = self.root / "practice/revision-0/total.txt"
        output.write_text("4\n")
        self.rejected("finish-verification", case_id="train-1", pytest_exit_code=0)
        output.write_text("3\n")
        self.ce("finish-verification", pytest_exit_code=2)
        self.feedback(action="repair_verifier")
        self.stop("verifier_failure")
        self.assemble()
        evidence = self.root / "verify/attempt-1"
        evidence.mkdir(parents=True)
        (evidence / "report.xml").write_text("late write")
        self.rejected("freeze")

    def test_deadline_stops_work_but_preserves_last_valid_revision(self):
        self.draft()
        later = datetime.now(timezone.utc) + timedelta(
            minutes=self.status()["config"]["construction_timeout_minutes"] + 1)
        class Later(datetime):
            @classmethod
            def now(cls, tz=None):
                return later
        with patch.object(experiment, "datetime", Later):
            self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")
            state = self.ce("finish-case", reason="time_budget")
        self.assertTrue(state["cases"]["train-1"]["deployable"])
        self.assertFalse(state["cases"]["train-1"]["final_was_tested"])

    def test_contaminated_case_blocks_deployment(self):
        self.draft()
        self.stop("contaminated")
        self.assemble()
        self.rejected("freeze")

    def test_initialization_rejects_existing_or_invalid_experiments(self):
        with self.assertRaises(ValueError):
            experiment.run("init", self.out, self.config)
        for change in ({"runs": True}, {"max_virtual_tests": 61}, {"test_benchmark_id": "train"},
                       {"case_ids": ["../outside"]}, {"case_ids": ["a", "a"]}, {"test_case_ids": []}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                experiment.run("init", self.out.parent / "invalid", {**self.config, **change})
        old = self.out.parent / "legacy"; old.mkdir(); (old / "experiment.yaml").write_text("phase: frozen\n")
        with self.assertRaises(ValueError):
            experiment.run("init", old, self.config)
        self.assertEqual((old / "experiment.yaml").read_text(), "phase: frozen\n")

    def test_gap_search_counts_issued_requests_and_rejects_identifiers(self):
        self.draft()
        self.verify(passed=False)
        self.feedback(classification="NEEDS-DR")
        self.rejected("targeted-search", case_id="train-1", classification="NEEDS-DR", query="train-1 solution")
        self.rejected("targeted-search", case_id="train-1", classification="SELF-FIXABLE", query="arithmetic")
        for _ in range(3):
            self.ce("targeted-search", classification="NEEDS-DR", query="arithmetic precision")
        self.rejected("targeted-search", case_id="train-1", classification="NEEDS-DR", query="rounding")

    def test_reader_control_is_opt_in_and_single_benchmark_default_stays_available(self):
        self.assertNotIn("reader_control", {p["variant"] for p in experiment.evaluation_plan(self.status())})
        config = {**self.config, "test_benchmark_id": None, "test_case_ids": [], "include_reader_control": True,
                  "include_baseline": False}
        state = experiment.initialize(config)
        plan = experiment.evaluation_plan(state)
        self.assertEqual({p["variant"] for p in plan}, {"reader_control", "final"})
        self.assertEqual({p["case_id"] for p in plan}, {"train-1"})

    def test_malformed_coverage_is_preserved_without_free_repairs(self):
        self.draft()
        state = self.ce("begin-verification", verifier_session_id="verifier")
        folder = Path(state["cases"]["train-1"]["attempts"][-1]["directory"])
        folder.mkdir(parents=True)
        (folder / "suite.py").write_text("def test_sum():\n    assert True\n")
        (folder / "report.xml").write_text('<testsuite><testcase name="sum"/></testsuite>')
        (folder / "coverage.json").write_text("malformed")
        state = self.ce("finish-verification", pytest_exit_code=0)
        attempt = state["cases"]["train-1"]["attempts"][-1]
        self.assertTrue(attempt["finished"])
        self.assertFalse(attempt["accepted"])
        self.assertTrue(attempt["coverage_error"])
        self.rejected("finish-verification", case_id="train-1", pytest_exit_code=0)

    def test_reservation_precedes_verifier_dispatch(self):
        self.draft()
        self.ce("begin-verification")
        self.rejected("finish-verification", case_id="train-1", pytest_exit_code=2, verifier_session_id="creator")
        state = self.ce("finish-verification", pytest_exit_code=2, verifier_session_id="new-verifier")
        self.assertEqual(state["cases"]["train-1"]["attempts"][0]["verifier_session_id"], "new-verifier")

    def test_freeze_rejects_restoring_an_older_revision(self):
        self.draft()
        self.verify(passed=False)
        self.revision(1)
        self.stop("interrupted")
        self.assemble()
        library = self.out / "library/tasks/train-1"
        shutil.rmtree(library)
        shutil.copytree(self.root / "revisions/revision-0", library)
        self.rejected("freeze")

    def test_cli_reports_failure_without_mutating_a_saved_experiment(self):
        before = self.status()
        request = self.out / "request.json"
        write_json(request, {"action": "begin-evaluation", "states": {}})
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "experiment.py"), "event",
                                 str(self.out), str(request)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.assertEqual(self.status(), before)
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "experiment.py"), "status", str(self.out)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), before)

    def test_a_concurrent_writer_is_not_overwritten(self):
        (self.out / ".journal.lock").mkdir()
        self.rejected("start-case", case_id="train-1")
        self.assertTrue((self.out / ".journal.lock").is_dir())

    def test_every_case_must_finish_before_global_freeze(self):
        config = {**self.config, "case_ids": ["train-1", "train-2"]}
        other = self.out.parent / "two-cases"
        experiment.run("init", other, config)
        self.out = other
        self.draft()
        self.verify()
        self.ce("finish-case", reason="surrogate_pass")
        self.assemble()
        self.rejected("freeze")

    def test_failed_checks_require_diagnosis_and_skill_repair(self):
        self.draft()
        self.verify(passed=False)
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")
        self.rejected("revision", case_id="train-1", creator_session_id="creator", hypothesis="Retry")
        for changes in ({"issues": []}, {"attempt": 2}, {"diagnosis": ""}, {"evidence": []}):
            before = self.status()
            with self.assertRaises(ValueError):
                self.feedback(**changes)
            self.assertEqual(self.status(), before)
        self.feedback()
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")
        outputs = self.root / "practice/revision-1"
        outputs.mkdir(); (outputs / "total.txt").write_text("3\n")
        self.rejected("revision", case_id="train-1", creator_session_id="creator", hypothesis="Unchanged",
                      execution_record=self.receipt(1))
        self.assertEqual(experiment.run("next", self.out)["cases"]["train-1"]["skill_changes_after_feedback"], 0)

    def test_explicit_rerun_is_not_a_skill_change_or_a_tested_new_execution(self):
        self.draft()
        self.verify(passed=False)
        self.feedback(action="repeat_practice", execution_issue="Prior command wrote the wrong output directory")
        shutil.copytree(self.root / "practice/revision-0", self.root / "practice/revision-1")
        self.ce("revision", creator_session_id="creator", hypothesis="Correct the output argument",
                execution_record=self.receipt(1))
        next_case = experiment.run("next", self.out)["cases"]["train-1"]
        self.assertEqual(next_case["practice_executions"], 2)
        self.assertEqual(next_case["skill_changes_after_feedback"], 0)
        case = self.stop("interrupted")["cases"]["train-1"]
        self.assertEqual(case["final_sha256"], case["last_tested_sha256"])
        self.assertFalse(case["final_was_tested"])
        self.assertEqual(case["final_verification_issues"], ["not_run"])

    def test_receipts_must_describe_the_current_execution(self):
        self.ce("start-case")
        self.ce("plan", skills=["calculate"], creator_session_id="creator")
        self.root = self.out / "tasks/train-1"
        skill(self.root / "skills")
        output = self.root / "practice/revision-0"
        output.mkdir(parents=True); (output / "total.txt").write_text("3\n")
        for changes in ({"creator_session_id": "other"}, {"skills_sha256": "old"},
                        {"output_directory": "practice/old"}, {"evidence": []}, {"exit_code": None},
                        {"started_at": "2000-01-01T00:00:00+00:00"},
                        {"finished_at": "2100-01-01T00:00:00+00:00"}):
            self.rejected("revision", case_id="train-1", creator_session_id="creator", hypothesis="Execute",
                          execution_record=self.receipt(0, **changes))
        self.ce("revision", creator_session_id="creator", hypothesis="Execute", execution_record=self.receipt(0))

    def test_unfinished_verification_cannot_use_a_passing_report(self):
        self.draft()
        for status in ("not_started", "interrupted"):
            state = self.ce("begin-verification", verifier_session_id="verifier")
            folder = Path(state["cases"]["train-1"]["attempts"][-1]["directory"])
            folder.mkdir(parents=True)
            (folder / "suite.py").write_text("def test_sum(): assert 1 + 2 == 3\n")
            (folder / "report.xml").write_text('<testsuite><testcase name="sum"/></testsuite>')
            self.rejected("finish-verification", case_id="train-1", execution_status=status, pytest_exit_code=0)
            state = self.ce("finish-verification", execution_status=status)
            attempt = state["cases"]["train-1"]["attempts"][-1]
            self.assertFalse(attempt["accepted"])
            self.assertNotIn("pass_rate", attempt["result"])
            self.feedback(action="repair_verifier")
        case = self.stop("verifier_failure")["cases"]["train-1"]
        self.assertFalse(case["final_was_tested"])
        self.assertIsNone(case["last_tested_sha256"])

    def test_later_verifier_failure_keeps_the_last_valid_measurement(self):
        self.draft()
        self.verify(covered=False)
        self.feedback(action="repair_verifier")
        self.ce("begin-verification", verifier_session_id="verifier")
        self.ce("finish-verification", execution_status="interrupted")
        self.feedback(action="repair_verifier")
        case = self.stop("verifier_failure")["cases"]["train-1"]
        self.assertTrue(case["final_was_tested"])
        self.assertEqual(case["last_valid_verification_attempt"], 1)
        self.assertIn("verifier_error", case["final_verification_issues"])

    def test_gap_search_needs_retrieved_evidence_before_repair(self):
        self.draft()
        self.verify(covered=False)
        self.feedback(action="repair_verifier", classification="NEEDS-DR")
        self.ce("targeted-search", classification="NEEDS-DR", query="precision rules")
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")
        evidence = "tasks/train-1/retrieval-1.txt"
        (self.out / evidence).write_text("Provider request failed; no rule retrieved.\n")
        self.ce("search-result", search=1, outcome="unavailable", summary="Provider unavailable", evidence=[evidence])
        self.rejected("begin-verification", case_id="train-1", verifier_session_id="verifier")
        self.ce("targeted-search", classification="NEEDS-DR", query="documented decimal precision")
        evidence = "tasks/train-1/retrieval-2.txt"
        (self.out / evidence).write_text("Public documentation on decimal precision.\n")
        self.ce("search-result", search=2, outcome="retrieved", summary="Precision rule located",
                sources=["https://docs.python.org/3/library/decimal.html"], evidence=[evidence])
        self.rejected("search-result", case_id="train-1", search=2, outcome="unavailable")
        self.assertEqual(len(self.status()["cases"]["train-1"]["searches"]), 2)
        self.verify()
        self.ce("finish-case", reason="surrogate_pass")

    def test_early_stop_requires_nonrecoverable_evidence(self):
        self.draft()
        self.ce("begin-verification", verifier_session_id="verifier")
        self.ce("finish-verification", execution_status="not_started")
        self.feedback(action="repair_verifier")
        self.rejected("finish-case", case_id="train-1", reason="verifier_failure")
        for changes in ({"recoverable": True}, {"workers_stopped": False}, {"evidence": []},
                        {"why_recovery_impossible": ""}):
            before = self.status()
            with self.assertRaises(ValueError):
                self.stop("verifier_failure", **changes)
            self.assertEqual(self.status(), before)
        self.assertTrue(self.stop("verifier_failure")["cases"]["train-1"]["finished"])

    def test_context_and_interruption_stops_require_observed_causes(self):
        self.draft()
        for reason, changes in (("context_budget", {"context_used": 89, "context_limit": 100}),
                                ("interrupted", {"interruption": "time_remaining_is_short"})):
            before = self.status()
            with self.assertRaises(ValueError):
                self.stop(reason, **changes)
            self.assertEqual(self.status(), before)
        self.assertEqual(self.stop("context_budget", context_used=90, context_limit=100)
                         ["cases"]["train-1"]["reason"], "context_budget")

    def test_oracle_repair_needs_an_independent_correction(self):
        self.draft()
        self.verify(passed=False)
        before = self.status()
        with self.assertRaises(ValueError):
            self.feedback(action="repair_verifier")
        self.assertEqual(self.status(), before)
        self.feedback(action="repair_verifier", oracle_correction="Public instruction requires integer addition")
        self.verify()
        self.ce("finish-case", reason="surrogate_pass")

    def test_final_failure_cannot_skip_its_skill_repair(self):
        self.draft()
        for number in range(1, 3):
            self.verify(passed=False)
            self.revision(number)
        self.verify(passed=False)
        self.rejected("finish-case", case_id="train-1", reason="max_refinement_retries")
        self.feedback()
        self.rejected("finish-case", case_id="train-1", reason="max_refinement_retries")
        self.rejected("finish-case", case_id="train-1", reason="time_budget")

    def test_verifier_cap_preserves_an_untested_artifact_without_new_practice(self):
        self.draft()
        for _ in range(3):
            self.ce("begin-verification", verifier_session_id="verifier")
            self.ce("finish-verification", execution_status="not_started")
            self.feedback(action="repair_verifier")
        self.assertEqual(experiment.run("next", self.out)["cases"]["train-1"]["next_action"],
                         "finish_max_refinement_retries")
        case = self.ce("finish-case", reason="max_refinement_retries")["cases"]["train-1"]
        self.assertFalse(case["final_was_tested"])
        self.assertEqual(len(case["revisions"]), 1)

    def test_guidance_is_read_only_and_uses_the_real_deadline(self):
        self.draft()
        self.ce("begin-verification", verifier_session_id="verifier")
        before = tree(self.out / "journal")
        start = datetime.fromisoformat(self.status()["cases"]["train-1"]["started_at"])
        budget = self.status()["config"]["construction_timeout_minutes"] * 60
        for seconds, action, remaining in ((budget - 10, "collect_verification", 10),
                                           (budget, "abort_and_collect_verification", 0)):
            with patch.object(experiment, "datetime") as clock:
                clock.now.return_value = start + timedelta(seconds=seconds)
                case = experiment.run("next", self.out)["cases"]["train-1"]
            self.assertEqual(case["next_action"], action)
            self.assertEqual(case["remaining_seconds"], remaining)
        self.assertEqual(tree(self.out / "journal"), before)

    def test_default_budget_allows_verification_beyond_smoke_window(self):
        self.draft()
        self.ce("begin-verification", verifier_session_id="verifier")
        start = datetime.fromisoformat(self.status()["cases"]["train-1"]["started_at"])
        with patch.object(experiment, "datetime") as clock:
            clock.now.return_value = start + timedelta(minutes=95)
            case = experiment.run("next", self.out)["cases"]["train-1"]
        self.assertEqual(case["next_action"], "collect_verification")
        self.assertGreater(case["remaining_seconds"], 0)

    def test_explicit_short_budget_still_expires_after_journal_reload(self):
        self.out = Path(self.temp.name) / "explicit-short-run"
        experiment.run("init", self.out, {**self.config, "construction_timeout_minutes": 30})
        self.draft()
        self.ce("begin-verification", verifier_session_id="verifier")
        start = datetime.fromisoformat(self.status()["cases"]["train-1"]["started_at"])
        before = tree(self.out / "journal")
        with patch.object(experiment, "datetime") as clock:
            clock.now.return_value = start + timedelta(minutes=31)
            case = experiment.run("next", self.out)["cases"]["train-1"]
        self.assertEqual(case["next_action"], "abort_and_collect_verification")
        self.assertEqual(case["remaining_seconds"], 0)
        self.assertEqual(tree(self.out / "journal"), before)

    def test_delayed_collection_accepts_timely_execution_only(self):
        self.ce("start-case")
        self.ce("plan", skills=["calculate"], creator_session_id="creator")
        self.root = self.out / "tasks/train-1"; skill(self.root / "skills")
        outputs = self.root / "practice/revision-0"
        outputs.mkdir(parents=True); (outputs / "total.txt").write_text("3\n")
        start = datetime.fromisoformat(self.status()["cases"]["train-1"]["started_at"])
        timely = self.receipt(0)
        late_time = start + timedelta(minutes=self.status()["config"]["construction_timeout_minutes"] + 1)
        with patch.object(experiment, "datetime", wraps=datetime) as clock:
            clock.now.return_value = late_time
            late = self.receipt(0, finished_at=late_time.isoformat())
            self.rejected("revision", case_id="train-1", creator_session_id="creator", hypothesis="Late",
                          execution_record=late)
            timely = self.receipt(0)
            self.ce("revision", creator_session_id="creator", hypothesis="Already finished", execution_record=timely)
            self.ce("finish-case", reason="time_budget")

    def test_mutated_execution_evidence_prevents_freeze(self):
        self.draft(); self.verify()
        self.ce("finish-case", reason="surrogate_pass")
        (self.root / "executions/run-0.log").write_text("Different execution\n")
        self.assemble()
        self.rejected("freeze")

    def test_old_journal_is_readable_without_implicit_migration(self):
        path = self.out / "journal/000001.json"
        record = read_json(path); record["state"]["schema_version"] = 1; write_json(path, record)
        before = tree(self.out / "journal")
        self.assertEqual(self.status()["schema_version"], 1)
        self.rejected("start-case", case_id="train-1")
        self.assertEqual(tree(self.out / "journal"), before)

    def test_executable_skill_improves_only_after_feedback_and_code_change(self):
        self.ce("start-case"); self.ce("plan", skills=["calculate"], creator_session_id="creator")
        self.root = self.out / "tasks/train-1"; skill(self.root / "skills")
        script = self.root / "skills/calculate/scripts/total.py"
        # The verifier uses independent public arithmetic, never the skill implementation.
        for number, expression in enumerate(("max", "sum")):
            script.write_text(f"import sys\nprint({expression}(map(int, sys.argv[1:])))\n")
            output = self.root / f"practice/revision-{number}"
            output.mkdir(parents=True)
            result = subprocess.run([sys.executable, str(script), "1", "2"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            (output / "total.txt").write_text(result.stdout)
            receipt = self.receipt(number, commands=[f"python3 {script} 1 2"])
            (self.root / f"executions/run-{number}.log").write_text(result.stdout)
            self.ce("revision", creator_session_id="creator", hypothesis="Use addition for numeric rows",
                    execution_record=receipt)
            state = self.ce("begin-verification", verifier_session_id="verifier")
            folder = Path(state["cases"]["train-1"]["attempts"][-1]["directory"]); folder.mkdir(parents=True)
            suite = folder / "suite.py"
            suite.write_text("import pathlib, sys\nassert int(pathlib.Path(sys.argv[1]).read_text()) == 3\n")
            checked = subprocess.run([sys.executable, str(suite), str(output / "total.txt")],
                                     capture_output=True, text=True)
            (folder / "check.log").write_text(checked.stderr or "Check passed\n")
            failure = '<failure message="Expected public arithmetic sum 3"/>' if checked.returncode else ""
            (folder / "report.xml").write_text(f'<testsuite><testcase classname="rows" name="sum">{failure}</testcase></testsuite>')
            write_json(folder / "coverage.json", [{"requirement": "sum", "required": True,
                "source": "Public arithmetic 1 + 2 = 3", "status": "covered", "tests": ["rows::sum"]}])
            self.ce("finish-verification", pytest_exit_code=checked.returncode)
            if number == 0:
                self.assertEqual(checked.returncode, 1)
                self.feedback()
            else:
                self.assertEqual(checked.returncode, 0)
        case = self.ce("finish-case", reason="surrogate_pass")["cases"]["train-1"]
        self.assertTrue(case["final_was_tested"])
        self.assertNotEqual(case["revisions"][0]["skills_sha256"], case["final_sha256"])
        self.assertEqual(experiment.run("next", self.out)["cases"]["train-1"]["skill_changes_after_feedback"], 1)
        self.assemble(); self.assertEqual(self.event("freeze")["phase"], "frozen")


    def test_controlled_delivery_continuation_registers_a_fenced_revision_only_once(self):
        self.draft()
        # The stopped practice had already authored the skill repair and written
        # the answers; its role was fenced while correcting a probe diagnostic.
        # The live tree still holds the last registered revision, so the
        # continuation must import the fenced practice's skills explicitly.
        live_sha = digest(tree(self.root / "skills"))
        practice = self.out / ".executor/train-1/practice-stop"
        (practice / "skills").mkdir(parents=True)
        shutil.copytree(self.root / "skills", practice / "skills", dirs_exist_ok=True)
        with (practice / "skills/calculate/scripts/total.py").open("a") as stream:
            stream.write("# continued repair\n")
        skills_sha = digest(tree(practice / "skills"))
        (practice / "view/public").mkdir(parents=True)
        (practice / "view/public/rows.json").write_text("[1, 2, -1]", encoding="utf-8")
        (practice / "outputs").mkdir()
        (practice / "outputs/total.txt").write_text("3\n", encoding="utf-8")
        (practice / "outputs/probe.json").write_text('{"status": "pass"}\n', encoding="utf-8")
        (practice / "execution").mkdir()
        write_json(practice / "execution/result.json", {"completed": False,
                   "error_code": "PRACTICE_HARD_FAILURE", "error": "edit_file text mismatch"})
        write_json(practice / "integrity-before.json", {"status": "passed",
                   "expected": {"skills": skills_sha, "inputs": digest(tree(practice / "view"))},
                   "actual": {"skills": skills_sha, "inputs": digest(tree(practice / "view"))}})
        write_json(self.out / ".executor/train-1/plan.json", {"outputs": ["total.txt", "probe.json"]})
        target = self.root / "practice/revision-1"
        target.mkdir(parents=True)
        (target / "total.txt").write_text("3\n", encoding="utf-8")
        (target / "probe.json").write_text('{"status": "pass"}\n', encoding="utf-8")
        outputs = tree(target)
        record = {"schema_version": 1, "case_id": "train-1", "revision": 1,
                  "practice": ".executor/train-1/practice-stop",
                  "stop": {"sha256": "0" * 64},
                  "stopped_role": {"completed": False, "error_code": "PRACTICE_HARD_FAILURE",
                                   "diagnosis": "The role was fenced while correcting a probe diagnostic.",
                                   "evidence": [".executor/train-1/practice-stop/execution/result.json"]},
                  "integrity": {"status": "passed", "skills_expected": skills_sha,
                                "skills_actual": skills_sha,
                                "inputs_expected": digest(tree(practice / "view")),
                                "inputs_actual": digest(tree(practice / "view"))},
                  "inputs_sha256": digest(tree(practice / "view")),
                  "skills_sha256": skills_sha, "outputs_sha256": digest(outputs),
                  "skills_source": {"source": ".executor/train-1/practice-stop/skills",
                                    "reason": "fenced practice revision",
                                    "previous_sha256": live_sha, "sha256": skills_sha,
                                    "imported": True},
                  "answers": {"total.txt": outputs["total.txt"]}, "outputs": outputs,
                  "repair": {"actor": "controller", "action": "delivery-repair",
                             "source": "tasks/train-1/review/probe.py",
                             "allowed_paths": ["work/run_probes.py"],
                             "required_probes": ["P1"], "probe_status": {"P1": "pass"},
                             "answer_files_preserved": True},
                  "role_success_claimed": False, "evidence": []}
        record_path = self.root / "review/continuation-1/continuation.json"
        record["repair"]["probe_status"] = {"P1": "fail"}
        write_json(record_path, record)
        request = {"action": "continuation-delivery", "case_id": "train-1",
                   "record": record_path.relative_to(self.out).as_posix(),
                   "practice": ".executor/train-1/practice-stop",
                   "hypothesis": "Repair only the delivery diagnostic"}
        before = self.status()
        with self.assertRaisesRegex(ValueError, "Required probe did not pass"):
            self.event(**request)
        self.assertEqual(self.status(), before)
        record["repair"]["probe_status"] = {"P1": "pass"}
        write_json(record_path, record)
        state = self.event(**request)
        case = state["cases"]["train-1"]
        self.assertEqual(len(case["revisions"]), 2)
        self.assertEqual(case["revisions"][-1]["delivery_kind"], "continuation")
        self.assertEqual(case["revisions"][-1]["change_kind"], "revise_skill")
        self.assertEqual(case["revisions"][-1]["skills_sha256"], skills_sha)
        self.assertEqual(case["continuations"][0]["role_success_claimed"], False)
        self.assertTrue((self.root / "revisions/revision-1/calculate/SKILL.md").is_file())
        self.assertIn("# continued repair", (self.root / "skills/calculate/scripts/total.py").read_text())
        before = self.status()
        with self.assertRaisesRegex(ValueError, "One controlled delivery continuation"):
            self.event(**request)
        self.assertEqual(self.status(), before)

class ArtifactTest(unittest.TestCase):
    """Given portable content it validates; bad paths, unknown usage and symlinks fail.

    Given a usage claim, validation labels it self-report and never claims trace verification.
    Given a changed final library, usage from the former library cannot be attributed to it.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        skill(self.root / "tasks/train-1")
        (self.root / "SKILL.md").write_text("Read index.md")
        (self.root / "index.md").write_text("tasks/train-1/calculate/SKILL.md")

    def test_portable_skills_validate_and_practice_paths_do_not(self):
        manifest = check_library(self.root, {"train-1": ["calculate"]})
        self.assertIn("train-1/calculate", manifest["cases"]["train-1"]["skill_ids"])
        with (self.root / "tasks/train-1/calculate/SKILL.md").open("a") as stream:
            stream.write("Run /opt/openskill-skills/calculate/run.py")
        with self.assertRaises(ValueError):
            check_library(self.root, {"train-1": ["calculate"]}, ["/opt/openskill-skills"])

    def test_missing_escaping_resources_and_symlinks_are_rejected(self):
        contract = self.root / "tasks/train-1/calculate/contract.json"
        base = read_json(contract)
        for path in ("/etc/hosts", "../other.txt", "scripts/missing.py"):
            write_json(contract, {**base, "resources": [path]})
            with self.assertRaises(ValueError):
                check_library(self.root, {"train-1": ["calculate"]})
        write_json(contract, base)
        (contract.parent / "linked").symlink_to(contract)
        with self.assertRaises(ValueError):
            check_library(self.root, {"train-1": ["calculate"]})

    def test_usage_is_self_report_not_proof_of_application(self):
        record = {"library_sha256": digest(tree(self.root)), "skills": [
            {"id": "train-1/calculate", "status": "applied", "evidence": ["trace.jsonl:12; ran total.py"]}]}
        self.assertEqual(check_usage(self.root, record)["evidence_level"], "self_report_only")
        bad = copy.deepcopy(record); bad["skills"][0]["id"] = "unknown"
        with self.assertRaises(ValueError):check_usage(self.root, bad)
        bad = copy.deepcopy(record); bad["skills"][0]["evidence"] = []
        with self.assertRaises(ValueError):check_usage(self.root, bad)
        with self.assertRaises(ValueError):check_usage(self.root, {"library_sha256": "old", "skills": []})
        empty = {"library_sha256": record["library_sha256"], "skills": [], "reason": "No applicable skill"}
        self.assertEqual(check_usage(self.root, empty)["skills"], [])


if __name__ == "__main__":
    unittest.main()

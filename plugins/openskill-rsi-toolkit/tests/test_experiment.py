"""Exercise the public experiment helper with real temporary artifacts.

Given unfinished construction, evaluation and global freezing are refused without journal changes.
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
        outputs = self.root / "practice" / f"revision-{number}"
        outputs.mkdir(parents=True)
        (outputs / "total.txt").write_text("3\n", encoding="utf-8")
        if number:
            with (self.root / "skills/calculate/scripts/total.py").open("a") as stream:
                stream.write(f"# revision {number}\n")
        return self.ce("revision", creator_session_id="creator", hypothesis="Sum rows before formatting")

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

    def begin_evaluation(self):
        variants = {p["variant"] for p in self.status()["evaluation_plan"]}
        self.snapshots = {v: {"version": i + 1, "sha256": "a" * 64} for i, v in enumerate(sorted(variants))}
        return self.event("begin-evaluation", states=self.snapshots)

    def matrices(self):
        result = []
        for variant, snapshot in self.snapshots.items():
            cells = []
            for case in ("test-1", "test-2"):
                cells.append({"case_id": case, "run": 1, "status": "ok", "agent_id": "target",
                              **self.config["runtime"]["target"], "expected_version": snapshot["version"],
                              "score": 100, "session_id": f"trial-{variant}-{case}"})
            result.append({"variant": variant, "benchmark_id": "test", "cells": cells})
        return result

    def test_unfinished_construction_cannot_freeze_or_evaluate(self):
        self.rejected("freeze")
        self.rejected("begin-evaluation", states={})
        self.rejected("start-case", case_id="test-1")

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

    def test_failed_verifier_attempts_spend_budget_without_a_report(self):
        self.draft()
        for _ in range(3):
            self.ce("begin-verification", verifier_session_id="verifier")
            result = self.ce("finish-verification", pytest_exit_code=2)
            self.assertEqual(result["cases"]["train-1"]["attempts"][-1]["result"]["status"], "failed")
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
        self.ce("finish-case", reason="verifier_failure")
        self.assemble()
        evidence = self.root / "verify/attempt-1"
        evidence.mkdir(parents=True)
        (evidence / "report.xml").write_text("late write")
        self.rejected("freeze")

    def test_deadline_stops_work_but_preserves_last_valid_revision(self):
        self.draft()
        later = datetime.now(timezone.utc) + timedelta(hours=1)
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
        self.ce("finish-case", reason="contaminated")
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
        self.ce("finish-case", reason="interrupted")
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

"""Verifier evidence scenarios, using immutable public fixtures and no model calls.

Given genuine quotations that do not justify permissions or thresholds, a controller's
unverified finding prevents a generated coverage map from promoting either claim.
Given independently computable arithmetic, supported checks remain usable while gaps stay visible.
Given a missing source, fabricated quotation, candidate-output citation or escaping path,
planning is refused instead of accepting a reference-shaped string as evidence.
Given a hypothesis or incomplete/stale review, no approved expectation is produced.
Given an omitted requirement, changed expectation or stale source, continuation is refused.
Given a reviewed development replay, check does not start a model, create a journal,
modify the old input files, or expose a deployment/score action.
Given a host-generated coverage template, copying it preserves the reviewed bindings;
real supported tests can be filled in without hashing, and unsupported promotion still fails.
Given repeated requirement prose from the real first Train group, distinct IDs survive
both preflight and measured coverage; unresolved evidence still prevents acceptance.
Given a mapped test that failed, coverage is incomplete; a nonexistent test is a protocol
error even when another requirement is unverified. A changed sealed plan is also refused.
Given recorded artifacts, offline replay performs no execution and leaves all files
unchanged; gaps, failing assertions, invented tests and interrupted runs stay distinct.
Given passing supported checks and unknown rules, an evidence summary separates them;
missing supported tests, zero supported claims and failed assertions never qualify for closure.
"""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import oracle
import verifier_replay
import protocol_replay
from artifacts import digest, read_json, tree
from isolation import save

FIXTURE = Path(__file__).parent / "fixtures/verifier-evidence"


class OracleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.view = self.root / "view"
        for name in ("public", "research"):
            shutil.copytree(FIXTURE / name, self.view / name)
        self.plan = read_json(FIXTURE / "plan.json")
        self.seal = oracle.validate_plan(self.plan, self.view)
        self.review = {k: self.seal[k] for k in ("plan_sha256", "inputs_sha256")}
        self.review.update(reviewer="fixture controller", scope="independent_evidence",
                           decisions=read_json(FIXTURE / "review-decisions.json"))

    def coverage(self):
        return [{"requirement_id": e["id"], "requirement": e["requirement"], "required": True,
                 "expectation_sha256": digest(e), "source": "public records",
                 "status": "covered" if e["id"] == "total" else "unverified",
                 "tests": ["suite::test_total"] if e["id"] == "total" else []}
                for e in self.plan["requirements"]]

    def test_real_but_irrelevant_citations_cannot_bypass_evidence_review(self):
        for key in ("permissions", "threshold"):
            coverage = self.coverage()
            entry = next(e for e in coverage if e["requirement_id"] == key)
            entry.update(status="covered", tests=["suite::test_guessed_rule"])
            with self.subTest(requirement=key), self.assertRaisesRegex(ValueError, "Unsupported expectation"):
                oracle.validate_coverage(self.plan, self.seal, self.review, coverage)

    def measured_fixture(self):
        rows = read_json(FIXTURE.parent / "repeated-requirements.json")["requirements"]
        self.plan["requirements"] = [{**copy.deepcopy(self.plan["requirements"][0]), **row} for row in rows]
        self.seal = oracle.validate_plan(self.plan, self.view)
        self.review.update({k: self.seal[k] for k in ("plan_sha256", "inputs_sha256")})
        self.review["decisions"] = [{"id": e["id"], "status": "supported", "finding": "Authored arithmetic fixture"}
                                    for e in self.plan["requirements"]]
        coverage = oracle.coverage_template(self.plan, self.seal, self.review)
        for entry in coverage:
            entry.update(status="covered", tests=["suite::test_total"])
        measured = {"status": "ok", "tests": [{"classname": "suite", "name": "test_total", "status": "passed"}]}
        for name, value in (("plan", self.plan), ("seal", self.seal), ("review", self.review)):
            save(self.root / f"measurement/oracle/{name}.json", value)
        path = self.root / "measurement/coverage.json"
        save(path, coverage)
        return path, coverage, measured

    def test_distinct_ids_with_identical_prose_survive_measured_coverage(self):
        path, coverage, measured = self.measured_fixture()
        self.assertTrue(oracle.validate_coverage(self.plan, self.seal, self.review, coverage))
        self.assertTrue(oracle.coverage_complete(path, measured, reviewed=True))
        self.review["decisions"][-1]["status"] = "unverified"
        save(path.parent / "oracle/review.json", self.review)
        coverage[-1].update(status="unverified", tests=[])
        save(path, coverage)
        self.assertFalse(oracle.coverage_complete(path, measured, reviewed=True))

    def test_evidence_summary_does_not_confuse_unknown_rules_with_supported_checks(self):
        path, coverage, measured = self.measured_fixture()
        self.review["decisions"][-1]["status"] = "unverified"
        save(path.parent / "oracle/review.json", self.review)
        coverage[-1].update(status="unverified", tests=[])
        save(path, coverage)
        summary = oracle.evidence_summary(path, measured)
        self.assertTrue(summary["supported_checks_passed"])
        self.assertEqual(summary["unverified"], [coverage[-1]["requirement_id"]])
        measured["tests"][0]["status"] = "failed"
        self.assertFalse(oracle.evidence_summary(path, measured)["supported_checks_passed"])
        measured["tests"][0]["status"] = "passed"
        coverage[0].update(status="unverified", tests=[])
        save(path, coverage)
        self.assertFalse(oracle.evidence_summary(path, measured)["supported_checks_passed"])
        for d in self.review["decisions"]:
            d["status"] = "unverified"
        for row in coverage:
            row.update(status="unverified", tests=[])
        save(path.parent / "oracle/review.json", self.review)
        save(path, coverage)
        self.assertFalse(oracle.evidence_summary(path, measured)["supported_checks_passed"])
        coverage[0].update(status="covered", tests=["suite::invented"])
        save(path, coverage)
        with self.assertRaisesRegex(ValueError, "Unsupported expectation"):
            oracle.evidence_summary(path, measured)

    def test_failed_tests_and_invalid_mappings_are_distinct(self):
        path, coverage, measured = self.measured_fixture()
        measured["tests"][0]["status"] = "failed"
        self.assertFalse(oracle.coverage_complete(path, measured, reviewed=True))
        measured["tests"][0]["status"] = "passed"
        coverage[0].update(status="unverified", tests=[])
        coverage[-1]["tests"] = ["suite::missing"]
        save(path, coverage)
        with self.assertRaisesRegex(ValueError, "not present in JUnit"):
            oracle.coverage_complete(path, measured, reviewed=True)

    def test_measured_coverage_refuses_stale_plan_and_missing_map(self):
        path, coverage, measured = self.measured_fixture()
        plan = copy.deepcopy(self.plan)
        plan["requirements"][0]["expectation"] = "Changed after review"
        save(path.parent / "oracle/plan.json", plan)
        with self.assertRaisesRegex(ValueError, "sealed plan"):
            oracle.coverage_complete(path, measured, reviewed=True)
        path.unlink()
        with self.assertRaises(OSError):
            oracle.coverage_complete(path, measured, reviewed=True)

    def test_offline_replay_preserves_records_and_distinguishes_outcomes(self):
        path, coverage, measured = self.measured_fixture()
        folder = path.parent
        (folder / "suite.py").write_text("raise RuntimeError('Recorded code must never be executed by replay')")
        for scenario in ("pass", "gap", "assertion", "mapping", "interrupted", "stale_source"):
            with self.subTest(scenario=scenario):
                rows = copy.deepcopy(coverage)
                if scenario == "gap":
                    rows[-1].update(status="unverified", tests=[])
                if scenario == "mapping":
                    rows[-1]["tests"] = ["suite::nonexistent"]
                save(path, rows)
                failure = '<failure message="Wrong arithmetic"/>' if scenario == "assertion" else ""
                (folder / "report.xml").write_text('<testsuite><testcase classname="suite" name="test_total">'
                                                  + failure + '</testcase></testsuite>')
                save(folder / "executor.json", {"execution_status": "interrupted" if scenario == "interrupted" else "completed",
                     "pytest_exit_code": None if scenario == "interrupted" else int(scenario == "assertion")})
                if scenario == "stale_source":
                    (self.view / "public/task.md").write_text("Changed public evidence")
                before = tree(self.root)
                result = protocol_replay.audit(folder, self.view)
                self.assertEqual(tree(self.root), before)
                self.assertFalse(result["deployable"])
                self.assertIsNone(result["benchmark_score"])
                self.assertEqual(result["protocol_valid"], scenario in ("pass", "gap", "assertion"))
                self.assertEqual(result["coverage_complete"], scenario == "pass")
                self.assertEqual(result["measurement_valid"], scenario != "interrupted")
                self.assertEqual("verifier_error" in result["verification_issues"],
                                 scenario in ("mapping", "interrupted", "stale_source"))
                self.assertEqual("assertion_failure" in result["verification_issues"], scenario == "assertion")

    def test_supported_arithmetic_remains_usable_without_erasing_gaps(self):
        self.assertFalse(oracle.validate_coverage(self.plan, self.seal, self.review, self.coverage()))
        plan = {**self.plan, "requirements": self.plan["requirements"][:1]}
        seal = oracle.validate_plan(plan, self.view)
        review = {**self.review, **{k: seal[k] for k in ("plan_sha256", "inputs_sha256")},
                  "decisions": self.review["decisions"][:1]}
        self.assertTrue(oracle.validate_coverage(plan, seal, review, self.coverage()[:1]))

    def test_host_template_preserves_bindings_without_claiming_coverage(self):
        coverage = json.loads(json.dumps(oracle.coverage_template(self.plan, self.seal, self.review)))
        self.assertFalse(oracle.validate_coverage(self.plan, self.seal, self.review, coverage))
        self.assertTrue(all(e["status"] == "unverified" and not e["tests"] for e in coverage))
        coverage[0].update(status="covered", tests=["suite::test_total"])
        self.assertFalse(oracle.validate_coverage(self.plan, self.seal, self.review, coverage))
        coverage[1].update(status="covered", tests=["suite::test_guessed_permission"])
        with self.assertRaisesRegex(ValueError, "Unsupported expectation"):
            oracle.validate_coverage(self.plan, self.seal, self.review, coverage)

    def test_sources_must_exist_match_and_stay_independent(self):
        for ref in ({"path": "public/missing.json", "quote": "anything"},
                    {"path": "public/records.json", "quote": "both permissions are view"},
                    {"path": "outputs/answer.json", "quote": "view"},
                    {"path": "public/../../secret", "quote": "secret"}):
            plan = copy.deepcopy(self.plan)
            plan["requirements"][1]["sources"] = [ref]
            with self.subTest(ref=ref), self.assertRaises((ValueError, OSError)):
                oracle.validate_plan(plan, self.view)

    def test_hypotheses_and_incomplete_or_stale_reviews_cannot_be_approved(self):
        plan = copy.deepcopy(self.plan)
        plan["requirements"][1]["basis"] = "hypothesis"
        seal = oracle.validate_plan(plan, self.view)
        review = copy.deepcopy(self.review)
        review.update({k: seal[k] for k in ("plan_sha256", "inputs_sha256")})
        review["decisions"][1]["status"] = "supported"
        with self.assertRaisesRegex(ValueError, "hypothesis"):
            oracle.validate_review(plan, seal, review)
        for changed in ({**self.review, "decisions": self.review["decisions"][:1]},
                        {**self.review, "plan_sha256": "0" * 64},
                        {**self.review, "scope": "matches_candidate"}):
            with self.subTest(review=changed), self.assertRaises(ValueError):
                oracle.validate_review(self.plan, self.seal, changed)

    def test_coverage_cannot_drop_rewrite_or_assert_an_unverified_requirement(self):
        for mutation in ("omit", "rename", "digest", "test_unverified", "duplicate"):
            coverage = self.coverage()
            if mutation == "omit": coverage.pop()
            elif mutation == "rename": coverage[1]["requirement"] = "Check only that the user exists"
            elif mutation == "digest": coverage[0]["expectation_sha256"] = "0" * 64
            elif mutation == "test_unverified": coverage[1]["tests"] = ["suite::test_guess"]
            else: coverage.append(copy.deepcopy(coverage[0]))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                oracle.validate_coverage(self.plan, self.seal, self.review, coverage)

    def test_replay_check_is_read_only_and_stale_sources_block_continuation(self):
        out = self.root / "replay"
        operation = out / ".executor/replay"
        shutil.copytree(self.view, operation / "plan-view")
        shutil.copytree(FIXTURE / "outputs", out / "candidate")
        save(operation / "oracle/plan.json", self.plan)
        save(operation / "oracle/seal.json", self.seal)
        save(out / "review.json", self.review)
        save(out / "replay.json", {"scope": verifier_replay.SCOPE, "status": "awaiting_review",
             "executor": {}, "outputs_sha256": digest(tree(out / "candidate"))})
        before = tree(out)
        result = verifier_replay.run("check", out, out / "review.json")
        self.assertEqual((result["supported"], result["unverified"]), (1, 2))
        self.assertFalse(result["semantic_proof"])
        # The executor lock file is the only administrative artifact created by a check.
        self.assertEqual({k: v for k, v in tree(out).items() if k != ".executor.lock"}, before)
        self.assertFalse((out / "journal").exists())
        (operation / "plan-view/public/records.json").write_text("{}")
        with self.assertRaises(ValueError):
            verifier_replay.run("verify", out, out / "review.json")
        self.assertEqual(read_json(out / "replay.json")["status"], "awaiting_review")


if __name__ == "__main__":
    unittest.main()

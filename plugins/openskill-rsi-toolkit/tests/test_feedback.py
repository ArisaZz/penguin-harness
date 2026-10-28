"""Bounded feedback decisions without model calls or rewritten experiment history.

Given only unknown policy, refinement needs an evidenced observable skill defect.
Given unavailable research, only one recorded skill fallback can proceed; pending
searches, verifier repair and the historical strict policy cannot use that allowance.
Given searches exhausted in a previous round, a new bug can use the single fallback
without issuing an extra search; pending responses must still be collected.
Given invalid, incomplete or failed checks, evidence-limited closure remains unavailable.
Given a malformed policy, initialization refuses it before producing journal state.
Given a measured revision in v2, a skill review precedes feedback or successful closure.
Given a known skill defect and passing output tests, closure is refused and skill repair
remains available even after a complete proxy pass or a separate verifier repair.
Given a new revision, old passing results cannot replace its independent verification.
Given a clean review with only unknown policy, closure needs no manufactured revision.
Given an observed resource defect, an unrelated file edit cannot register as its repair.
Given several findings, a revision may repair one affected resource while retaining the others.
"""

import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"))
import experiment
import workflow
import skill_review


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        self.config = {"feedback_policy": "bounded-evidence-v1", "max_refinement_retries": 3,
                       "max_targeted_searches": 3, "construction_timeout_minutes": 30}
        self.attempt = {"number": 1, "revision": 0, "finished": True, "accepted": False,
            "execution_status": "completed", "result": {"status": "ok", "failed": 0, "pass_rate": 1},
            "evidence": {"suite.py": "digest"}, "structure_valid": True, "coverage_complete": False,
            "coverage_error": None, "evidence_summary": {"supported": ["sum"], "unverified": ["policy"],
                                                         "supported_checks_passed": True}}
        self.decision = {"attempt": 1, "classification": "NEEDS-DR", "next_action": "revise_skill",
            "issues": ["coverage_gap"], "diagnosis": "Missing evidence is incorrectly reported as an empty record",
            "expected_change": "Record retrieval failures separately and retain the unknown policy",
            "evidence": ["observed.json"]}
        self.case = {"started_at": datetime.now(timezone.utc).isoformat(), "skills": ["collector"],
                     "attempts": [self.attempt], "revisions": [{"revision": 0}], "searches": []}

    def action(self, config=None):
        state = {"phase": "construction", "config": config or self.config, "cases": {"one": self.case}}
        return workflow.guidance(state, datetime.now(timezone.utc))["cases"]["one"]["next_action"]

    def test_unknown_policy_does_not_manufacture_a_skill_defect(self):
        with self.assertRaisesRegex(ValueError, "not an observed skill defect"):
            workflow.validate_feedback(self.case, self.decision, self.config)
        finding = {"observation": "HTTP 404 became an empty successful collection in the public trace",
                   "planned_change": "Keep failed retrieval status separate from empty success",
                   "validation": "A public missing-route fixture must produce a missing-evidence entry",
                   "evidence": ["observed.json"]}
        request = {**self.decision, "skill_findings": [finding]}
        workflow.validate_feedback(self.case, request, self.config)
        finding["evidence"] = ["unsealed.json"]
        with self.assertRaisesRegex(ValueError, "Seal the evidence"):
            workflow.validate_feedback(self.case, request, self.config)

    def test_fallback_needs_completed_search_and_cannot_be_used_for_verifier_repair(self):
        self.attempt["feedback"] = self.decision
        self.assertEqual(self.action(), "targeted_search")
        self.case["searches"] = [{"attempt": 1}]
        self.assertEqual(self.action(), "collect_search_result")
        self.case["searches"][0]["result"] = {"outcome": "unavailable"}
        self.assertEqual(self.action(), "record_research_fallback")
        with self.assertRaises(ValueError):
            workflow.research_ready(self.case, self.config)
        self.decision["next_action"] = "repair_verifier"
        self.assertFalse(workflow.fallback_available(self.case, self.config))
        self.decision["next_action"] = "revise_skill"
        self.attempt["research_fallback"] = {"unresolved": ["policy"]}
        self.assertEqual(self.action(), "revise_skill")
        self.assertEqual(workflow.research_ready(self.case, self.config), self.decision)
        self.assertFalse(workflow.fallback_available(self.case, self.config))
        self.case["searches"].append({"attempt": 1})
        self.assertEqual(self.action(), "collect_search_result")
        with self.assertRaisesRegex(ValueError, "pending searches"):
            workflow.research_ready(self.case, self.config)

    def test_search_cap_does_not_require_an_extra_search_before_bounded_skill_repair(self):
        self.attempt.update(number=2, feedback=self.decision)
        self.case["searches"] = [{"attempt": 1, "result": {"outcome": "unavailable"}} for _ in range(3)]
        self.assertEqual(self.action(), "record_research_fallback")
        previous = copy.deepcopy(self.attempt)
        previous.update(number=1, research_fallback={"unresolved": ["earlier gap"]})
        self.case["attempts"].insert(0, previous)
        self.assertEqual(self.action(), "document_unresolved_gap")

    def test_historical_strict_policy_keeps_its_original_continuation_rules(self):
        strict = {**self.config, "feedback_policy": "strict"}
        self.attempt["feedback"] = self.decision
        self.case["searches"] = [{"attempt": 1, "result": {"outcome": "unavailable"}}]
        self.assertEqual(self.action(strict), "targeted_search")
        with self.assertRaises(ValueError):
            workflow.research_ready(self.case, strict)
        del self.attempt["feedback"]
        with self.assertRaisesRegex(ValueError, "Evidence-limited closure"):
            workflow.validate_feedback(self.case, {**self.decision, "next_action": "finish_evidence_limited"}, strict)

    def test_failed_or_missing_checks_cannot_close_as_evidence_limited(self):
        request = {**self.decision, "next_action": "finish_evidence_limited"}
        workflow.validate_feedback(self.case, request, self.config)
        for change in ({"coverage_error": "invalid test mapping"}, {"structure_valid": False},
                       {"execution_status": "not_started"}, {"evidence": {}},
                       {"result": {"status": "ok", "failed": 1, "pass_rate": 0.5}},
                       {"evidence_summary": {"supported_checks_passed": False, "unverified": ["policy"]}},
                       {"evidence_summary": {"supported_checks_passed": True, "unverified": []}}):
            attempt = {**self.attempt, **change}
            case = {**self.case, "attempts": [attempt]}
            with self.subTest(change=change), self.assertRaises(ValueError):
                workflow.validate_feedback(case, {**request, "issues": workflow.issues(attempt)}, self.config)

    def test_invalid_policy_never_produces_initial_state(self):
        with self.assertRaisesRegex(ValueError, "Invalid feedback_policy"):
            experiment.initialize({"feedback_policy": "accept_everything"})
        with self.assertRaisesRegex(ValueError, "reviewed verification"):
            experiment.initialize(self.config)


class SkillFeedbackTest(unittest.TestCase):
    setUp = FeedbackTest.setUp
    action = FeedbackTest.action

    def setup_review(self, findings=None):
        self.config["feedback_policy"] = "bounded-evidence-v2"
        self.finding = {"id": "list-input", "observation": "Documented list input calls dict.get and raises",
                       "planned_change": "Handle list and object inputs separately",
                       "validation": "Independently check both documented input forms after fresh practice",
                       "affected_resources": ["collector/scripts/fetch.py"], "evidence": ["observed.json"]}
        self.case["revisions"][-1]["skill_review"] = {
            "findings": [self.finding] if findings is None else findings, "record": "review.json"}

    def test_measurement_needs_skill_review_before_feedback_or_closure(self):
        self.config["feedback_policy"] = "bounded-evidence-v2"
        self.assertEqual(self.action(), "review_skills")
        with self.assertRaisesRegex(ValueError, "Review the current skills"):
            workflow.validate_feedback(self.case, {**self.decision, "next_action": "finish_evidence_limited"}, self.config)
        self.setup_review([])
        workflow.validate_feedback(self.case, {**self.decision, "next_action": "finish_evidence_limited"}, self.config)

    def test_known_defect_cannot_be_closed_or_lost_when_other_checks_pass(self):
        self.setup_review()
        closing = {**self.decision, "issues": ["coverage_gap", "skill_behavior"],
                   "next_action": "finish_evidence_limited"}
        with self.assertRaisesRegex(ValueError, "Unresolved skill findings"):
            workflow.validate_feedback(self.case, closing, self.config)
        repair = {**closing, "next_action": "revise_skill", "classification": "SELF-FIXABLE",
                  "skill_findings": [self.finding]}
        workflow.validate_feedback(self.case, repair, self.config)
        self.attempt["feedback"] = repair
        self.assertEqual(self.action(), "revise_skill")
        del self.attempt["feedback"]
        self.attempt.update(accepted=True, coverage_complete=True)
        repair["issues"] = ["skill_behavior"]
        workflow.validate_feedback(self.case, repair, self.config)
        self.attempt["feedback"] = repair
        self.assertEqual(self.action(), "revise_skill")
        self.case["revisions"].append({"revision": 1})
        self.assertEqual(self.action(), "begin_verification")

    def test_verifier_repair_keeps_findings_and_cannot_substitute_for_skill_change(self):
        self.setup_review()
        repair = {**self.decision, "issues": ["coverage_gap", "skill_behavior"],
                  "next_action": "repair_verifier", "classification": "SELF-FIXABLE"}
        with self.assertRaisesRegex(ValueError, "Repair the known skill"):
            workflow.validate_feedback(self.case, repair, self.config)
        repair["oracle_correction"] = "The template allows secondary actions; remove the primary-only assertion"
        workflow.validate_feedback(self.case, repair, self.config)
        self.attempt["feedback"] = repair
        self.case["attempts"].append({**self.attempt, "number": 2})
        self.case["attempts"][-1].pop("feedback")
        self.assertEqual(self.action(), "record_feedback")
        guide = workflow.guidance({"phase": "construction", "config": self.config, "cases": {"one": self.case}},
                                  datetime.now(timezone.utc))["cases"]["one"]
        self.assertEqual(guide["open_skill_findings"], [self.finding])
        self.assertFalse(guide["evidence_limited_eligible"])

    def test_unrelated_edits_cannot_count_as_repairing_a_known_resource(self):
        self.setup_review()
        before = {"collector/scripts/fetch.py": "bug", "collector/SKILL.md": "original"}
        with self.assertRaisesRegex(ValueError, "affected skill resource"):
            skill_review.check_change(self.case, before, {**before, "collector/SKILL.md": "cosmetic edit"})
        skill_review.check_change(self.case, before, {**before, "collector/scripts/fetch.py": "fix"})

    def test_partial_progress_is_allowed_without_erasing_other_findings(self):
        self.setup_review()
        other = {**self.finding, "id":"object-input", "affected_resources":["collector/scripts/send.py"]}
        self.case["revisions"][-1]["skill_review"]["findings"].append(other)
        before = {"collector/scripts/fetch.py":"bug", "collector/scripts/send.py":"bug"}
        skill_review.check_change(self.case, before, {**before, "collector/scripts/fetch.py":"fix"})
        self.assertEqual(skill_review.findings(self.case), [self.finding, other])
        with self.assertRaisesRegex(ValueError, "Unresolved skill findings"):
            skill_review.require_clear(self.case, self.config)


if __name__ == "__main__":
    unittest.main()

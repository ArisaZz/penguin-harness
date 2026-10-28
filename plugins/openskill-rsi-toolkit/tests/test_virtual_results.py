"""Exercise the shipped parser through its CLI using temporary JUnit reports.

Given mixed passed, failed and skipped checks, parsing computes a proxy from executed checks.
Given ordinary assertion failures, parsing returns a valid zero rate rather than a runner error.
Given a complete passing suite, parsing accepts either pytest JUnit root shape.
Given empty or all-skipped suites, parsing refuses to invent a passing score.
Given setup/collection/teardown errors, parsing returns an unscored verifier failure.
Given a stopped pytest process or a stale report, parsing rejects the exit/report mismatch.
Given malformed/missing reports or duplicate identities, parsing rejects ambiguous evidence.
Given a suite above the test budget or expected-failure markers, parsing rejects invalid checks.
Given a lower declared test cap, parsing enforces that cap.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts/virtual-results.py"


class VirtualResultsTest(unittest.TestCase):
    def run_report(self, xml, code=0, max_tests=60):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.xml"
            if xml is not None:
                report.write_text(xml, encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(SCRIPT), str(report), "--pytest-exit-code", str(code),
                 "--max-tests", str(max_tests)],
                capture_output=True, text=True, check=False,
            )
        result = json.loads(process.stdout)
        self.assertEqual(process.returncode, 0 if result["status"] == "ok" else 2)
        return result

    def assert_unscored(self, result):
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("pass_rate", result)
        self.assertNotIn("score", result)

    def test_mixed_results_count_executed_checks_and_preserve_diagnostics(self):
        result = self.run_report('''<testsuites><testsuite tests="999" failures="0">
          <testcase classname="sample" name="exact"/>
          <testcase classname="sample" name="value"><failure message="wrong value">2 != 3</failure></testcase>
          <testcase classname="sample" name="optional"><skipped message="unsupported"/></testcase>
        </testsuite></testsuites>''', code=1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual((result["passed"], result["failed"], result["skipped"], result["total"]), (1, 1, 1, 2))
        self.assertEqual(result["pass_rate"], 0.5)
        self.assertEqual(result["tests"][1]["detail"], "2 != 3")

    def test_assertion_failure_is_a_valid_zero_rate(self):
        result = self.run_report('<testsuite><testcase name="output"><failure message="missing"/></testcase></testsuite>', code=1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pass_rate"], 0)

    def test_complete_suite_accepts_both_junit_roots(self):
        suite = '<testsuite><testcase classname="a" name="same"/><testcase classname="b" name="same"/></testsuite>'
        for xml in (suite, f"<testsuites>{suite}</testsuites>"):
            with self.subTest(xml=xml):
                result = self.run_report(xml)
                self.assertEqual(result["total"], 2)
                self.assertEqual(result["pass_rate"], 1)

    def test_no_executed_checks_have_no_score(self):
        for xml in ('<testsuite/>', '<testsuite><testcase name="skip"><skipped/></testcase></testsuite>'):
            with self.subTest(xml=xml):
                result = self.run_report(xml)
                self.assert_unscored(result)
                self.assertEqual(result["failure_code"], "no_tests")

    def test_verifier_errors_have_no_score(self):
        for xml in (
            '<testsuite><testcase name="setup"><error>dependency missing</error></testcase></testsuite>',
            '<testsuite><testcase name="passed"/><error>collection failed</error></testsuite>',
            '<testsuite><testcase name="both"><failure>assertion</failure><error>teardown</error></testcase></testsuite>',
        ):
            with self.subTest(xml=xml):
                result = self.run_report(xml, code=1)
                self.assert_unscored(result)
                self.assertEqual(result["failure_code"], "verifier_error")

    def test_interrupted_or_inconsistent_runs_have_no_score(self):
        passing = '<testsuite><testcase name="ok"/></testsuite>'
        failing = '<testsuite><testcase name="bad"><failure/></testcase></testsuite>'
        for xml, code in ((passing, 2), (passing, 5), (passing, 1), (failing, 0)):
            with self.subTest(code=code, xml=xml):
                self.assert_unscored(self.run_report(xml, code=code))

    def test_missing_malformed_and_ambiguous_reports_have_no_score(self):
        for xml in (
            None, '<testsuite>', '<notjunit/>', '<testsuite><testcase/></testsuite>',
            '<testsuite><testcase name="same"/><testcase name="same"/></testsuite>',
            '<testsuite><testcase name="both"><failure/><skipped/></testcase></testsuite>',
        ):
            with self.subTest(xml=xml):
                result = self.run_report(xml)
                self.assert_unscored(result)
                self.assertEqual(result["failure_code"], "invalid_report")

    def test_test_budget_counts_parameterized_and_skipped_checks(self):
        cases = ''.join(f'<testcase name="row[{i}]"><skipped/></testcase>' for i in range(60))
        result = self.run_report(f'<testsuite><testcase name="ok"/>{cases}</testsuite>')
        self.assert_unscored(result)
        self.assertEqual(result["failure_code"], "too_many_tests")

    def test_expected_failures_cannot_create_a_passing_proxy(self):
        result = self.run_report('<testsuite><testcase name="ok"/><testcase name="xfail"><skipped type="pytest.xfail"/></testcase></testsuite>')
        self.assert_unscored(result)

    def test_lower_test_budget_is_enforced(self):
        result = self.run_report('<testsuite><testcase name="one"/><testcase name="two"/></testsuite>', max_tests=1)
        self.assert_unscored(result)
        self.assertEqual(result["failure_code"], "too_many_tests")


if __name__ == "__main__":
    unittest.main()

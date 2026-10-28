"""Recovery policy behavior with a virtual clock and real Node code.

Given a local exception, only a completed command closes its correction window.
Given a second failure during correction, changing error type cannot extend time.
Given cancellation, permission errors or unknown faults, no recovery is authorized.
Given exhausted total or same-error allowances, no further continuation is granted.
Given a frozen-skill traceback, correction returns to authoring rather than patching it.
Given conflicting modes or invalid limits, initialization refuses them before any worker.
Given a sealed usage report, invented refunds or excess grants cannot enter the journal.
Given v2 sibling failures, one allowance covers the family and a later response must correct it.
Given a later repeated failure, v2 charges another allowance without extending the deadline.
Given ordinary nonzero exits, v2 permits correction but never signal or boundary failures.
Given coalesced evidence, only a prior grant from the same request/family can justify it.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import executor
import recovery


class RecoveryTest(unittest.TestCase):
    def simulate(self, steps, prior=None, **limits):
        script = """
import {ToolRecovery} from MODULE;
const spec=JSON.parse(process.argv[1]);let time=0;
const r=new ToolRecovery(spec.limits,spec.prior,'/work/skills',()=>time);
let code=null;
for(const step of spec.steps){
  time=step.time??time;
  try {if(step.finish)r.finish();else r.observe(step.output);}
  catch(e){code=e.code;break;}
}
process.stdout.write(JSON.stringify({code,...r.report()}));
""".replace("MODULE", json.dumps((SCRIPTS / "recovery.mjs").as_uri()))
        result = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script,
            json.dumps({"limits": {**recovery.DEFAULTS, **limits}, "prior": prior or {"used": 0, "families": {}},
                        "steps": steps})], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def call(self, ident, output, reason="fatal", name="exec_command", time=0):
        return [{"time": time, "output": {"type": "tool_call", "tool_call_id": ident, "name": name}},
                {"time": time, "output": {"type": "tool_call_output", "tool_call_id": ident,
                                           "stop_reason": reason, "output": output}}]

    def test_local_error_needs_a_completed_command_not_a_claim_or_background_process(self):
        first = self.call("bad", "KeyError: 'SELF_SERVICE'\n[exit code: 1]")
        for continuation in ([], self.call("read", "ok", "completed", "read_file"),
                             self.call("running", "[process still running with process_id abc]", "completed")):
            result = self.simulate(first + continuation + [{"finish": True}])
            self.assertEqual(result["code"], "PRACTICE_RECOVERY_UNRESOLVED")
        result = self.simulate(first + self.call("fixed", "checked", "completed") + [{"finish": True}])
        self.assertIsNone(result["code"])
        self.assertEqual(result["usage"]["used"], 1)
        self.assertIsNone(result["pending"])

    def test_different_error_does_not_extend_the_correction_deadline(self):
        steps = self.call("a", "KeyError: 'a'\n[exit code: 1]")
        steps += self.call("b", "NameError: name 'b' is not defined\n[exit code: 1]", time=119000)
        result = self.simulate(steps + [{"time": 120000, "finish": True}])
        self.assertEqual(result["code"], "RECOVERY_TIME_EXHAUSTED")

    def test_boundary_cancellation_and_unknown_errors_never_receive_recovery(self):
        for output, reason in (("KeyError: 'x'\nPermission denied\n[exit code: 1]", "fatal"),
                               ("KeyError: 'x'\n[exit code: 1]", "aborted"),
                               ("crashed\n[exit code: 139]", "fatal")):
            with self.subTest(output=output):
                result = self.simulate(self.call("bad", output, reason))
                self.assertEqual(result["code"], "PRACTICE_HARD_FAILURE")
                self.assertEqual(result["usage"]["used"], 0)

    def test_prior_allowances_cannot_be_reset_by_changing_error_text(self):
        first = self.call("a", "KeyError: 'different-field'\n[exit code: 1]")
        result = self.simulate(first, {"used": 1, "families": {"exec_command:KeyError": 1}})
        self.assertEqual(result["code"], "RECOVERY_BUDGET_EXHAUSTED")
        result = self.simulate(first, {"used": 3, "families": {"exec_command:NameError": 3}})
        self.assertEqual(result["code"], "RECOVERY_BUDGET_EXHAUSTED")

    def test_v2_edit_file_mismatch_is_a_bounded_local_correction(self):
        mismatch = ('old_string not found in "work/run_probes.py". Make sure it matches '
                    "the file content exactly, including whitespace and indentation.")
        steps = self.request() + self.call("edit-a", mismatch, name="edit_file")
        # The next model response corrects the text. A successful edit closes the
        # correction window; only a later request may do so.
        steps += self.request()
        steps += [{"output": {"type": "tool_call", "tool_call_id": "edit-b", "name": "edit_file"}},
                  {"output": {"type": "tool_call_output", "tool_call_id": "edit-b",
                              "stop_reason": "completed", "output": "Updated work/run_probes.py"}}]
        result = self.simulate(steps + [{"finish": True}], version=2)
        self.assertIsNone(result["code"])
        self.assertEqual(result["usage"]["used"], 1)
        self.assertEqual(result["usage"]["families"], {"edit_file:EditMismatch": 1})
        self.assertIsNone(result["pending"])

    def test_v2_edit_file_mismatch_cannot_edit_frozen_skills_or_inputs(self):
        for path, code in (("skills/calculate/SKILL.md", "SKILL_EXECUTION_FAILED"),
                           ("inputs/public/rows.json", "PRACTICE_HARD_FAILURE")):
            with self.subTest(path=path):
                text = (f'old_string not found in "{path}". Make sure it matches '
                        "the file content exactly, including whitespace and indentation.")
                result = self.simulate(self.request() + self.call("edit", text, name="edit_file"), version=2)
                self.assertEqual(result["code"], code)
                self.assertEqual(result["usage"]["used"], 0)

    def test_v2_edit_file_mismatch_shares_the_bounded_family(self):
        text = ('old_string not found in "work/a.py". Make sure it matches '
                "the file content exactly, including whitespace and indentation.")
        result = self.simulate(self.request() + self.call("edit", text, name="edit_file"),
                               {"used": 2, "families": {"edit_file:EditMismatch": 2}}, version=2)
        self.assertEqual(result["code"], "RECOVERY_BUDGET_EXHAUSTED")
        self.assertEqual(result["usage"]["used"], 2)

    def test_frozen_skill_error_returns_to_authoring_without_local_allowance(self):
        for source in ("/work/skills/calculator/run.py", "skills/calculator/run.py"):
            result = self.simulate(self.call("bad", f'  File "{source}", line 3\nKeyError: x\n[exit code: 1]'))
            self.assertEqual(result["code"], "SKILL_EXECUTION_FAILED")
            self.assertEqual(result["usage"]["used"], 0)

    def test_invalid_configuration_stops_before_any_environment_requirement(self):
        for config in ({"recovery_policy": {}, "stop_on_recurrence": True},
                       {"recovery_policy": {"max_tool_recoveries": -1}},
                       {"recovery_policy": {"recovery_seconds": 0}},
                       {"recovery_policy": {"unknown": 4}}):
            with self.subTest(config=config), tempfile.TemporaryDirectory() as folder:
                out = Path(folder) / "experiment"
                with self.assertRaisesRegex(ValueError, "recovery|Recovery|Same-error|Choose"):
                    executor.run("init", out, config)
                self.assertFalse((out / "preflight.json").exists())
                self.assertFalse((out / "journal").exists())

    def test_usage_report_cannot_refund_or_invent_a_recovery(self):
        case = {"tool_recovery": {"used": 1, "families": {"exec_command:KeyError": 1}}}
        report = {"prior": case["tool_recovery"], "usage": {"used": 0, "families": {}}, "events": []}
        with self.assertRaisesRegex(ValueError, "accounting"):
            recovery.validate_tool_report(report, case, {"recovery_policy": {}})
        report.update(usage={"used": 2, "families": {"exec_command:KeyError": 2}},
                      events=[{"decision": "recover", "family": "exec_command:KeyError"}])
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            recovery.validate_tool_report(report, case, {"recovery_policy": {}})

    def request(self, time=0):
        return [{"time": time, "output": {"type": "request_begin"}}]

    def test_v2_siblings_share_allowance_but_cannot_claim_correction_in_the_same_response(self):
        steps = self.request() + self.call("a", "KeyError: 0\n[exit code: 1]")
        steps += self.call("unrelated", "ok", "completed")
        steps += self.call("b", "KeyError: 0\n[exit code: 1]")
        unresolved = self.simulate(steps + [{"finish": True}], version=2)
        self.assertEqual(unresolved["code"], "PRACTICE_RECOVERY_UNRESOLVED")
        result = self.simulate(steps + self.request() + self.call("fixed", "ok", "completed")
                               + [{"finish": True}], version=2)
        self.assertIsNone(result["code"])
        self.assertEqual(result["usage"]["used"], 1)
        self.assertEqual([e["decision"] for e in result["events"]], ["recover", "coalesced"])
        self.assertIsNone(result["pending"])
        self.assertEqual(recovery.validate_tool_report(result, {}, {"recovery_policy": {"version": 2}}),
                         result["usage"])

    def test_v2_later_response_spends_another_allowance_and_keeps_the_original_deadline(self):
        steps = self.request() + self.call("a", "KeyError: 0\n[exit code: 1]")
        steps += self.request(119000) + self.call("b", "KeyError: 0\n[exit code: 1]", time=119000)
        result = self.simulate(steps + [{"time": 120000, "finish": True}],
                               version=2, max_same_error_recoveries=2)
        self.assertEqual(result["code"], "RECOVERY_TIME_EXHAUSTED")
        self.assertEqual(result["usage"]["used"], 2)
        exhausted = self.simulate(steps, version=2)
        self.assertEqual(exhausted["code"], "RECOVERY_BUDGET_EXHAUSTED")
        # Without request boundaries, never silently group distinct failures.
        ungrouped = self.simulate(self.call("a", "KeyError: 0\n[exit code: 1]") +
                                 self.call("b", "KeyError: 0\n[exit code: 1]"), version=2)
        self.assertEqual(ungrouped["code"], "RECOVERY_BUDGET_EXHAUSTED")

    def test_v2_ordinary_command_exit_can_recover_but_signals_and_boundaries_cannot(self):
        for diagnostic in ("[exit code: 1]", "unrecognized argument\n[exit code: 2]",
                           "AssertionError: incorrect temporary check\n[exit code: 1]"):
            result = self.simulate(self.request() + self.call("bad", diagnostic) +
                self.request() + self.call("fixed", "ok", "completed") + [{"finish": True}], version=2)
            self.assertIsNone(result["code"])
            self.assertEqual(result["usage"]["used"], 1)
        for diagnostic, reason in (("KeyError: 0\n[exit code: 125]", "fatal"),
                                   ("[exit code: 137]", "fatal"),
                                   ("Permission denied\n[exit code: 1]", "fatal"),
                                   ("KeyError: 0\n[exit code: 1]", "aborted"),
                                   ("unknown failure without process status", "fatal")):
            result = self.simulate(self.request() + self.call("bad", diagnostic, reason), version=2)
            self.assertEqual(result["code"], "PRACTICE_HARD_FAILURE")
            self.assertEqual(result["usage"]["used"], 0)
        result = self.simulate(self.request() + self.call("bad",
            '  File "/work/skills/calculate/run.py", line 2\nAssertionError\n[exit code: 1]'), version=2)
        self.assertEqual(result["code"], "SKILL_EXECUTION_FAILED")

    def test_v2_coalescing_cannot_refund_other_requests_or_families(self):
        import copy
        result = self.simulate(self.request() + self.call("a", "KeyError: 0\n[exit code: 1]") +
                              self.call("b", "KeyError: 0\n[exit code: 1]"), version=2)
        for changes in ({"request": 2}, {"request": 0}, {"family": "exec_command:TypeError"},
                        {"recovery_tool_call_id": "invented"}, {"deadline": 999999}, {"decision": "ignored"},
                        {"decision": "recover"}):
            report = copy.deepcopy(result)
            report["events"][1].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "recovery"):
                recovery.validate_tool_report(report, {}, {"recovery_policy": {"version": 2}})

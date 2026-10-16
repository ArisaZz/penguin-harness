"""Executor boundary scenarios, with no paid model requests.

Given isolated mode, manual role receipts and old-journal migration are refused.
Given linked or escaping artifacts, staging fails before importing private data.
Given a STOP fence or expired deadline, no worker is started.
Given a live executor, a second writer cannot start another role.
Given a real Docker boundary, both SDK read_file and shell cannot read host canaries;
public inputs remain read-only, outputs are writable, and privileged tools are absent.
Given an image that cannot start, execution fails closed without a surviving container.
Given a running measurement cancelled by STOP, descendants stop and no completed result is recorded.
Given a faulty skill and independent pytest feedback, the same real SDK creator session
repairs its skill, a fresh verifier measures it, and the final revision is the tested one.
Given too many parameterized tests, none execute and the failed attempt still spends budget.
Given a verifier that supplies no suite, no score is inferred and a fresh attempt needs feedback.
Given a controller mapping creator code as research, transfer is refused before a verifier sees it.
Given a GDPevo service, every role and pytest starts only after business readiness.
Given failed batch initialization, no model request or construction journal is created.
Given strict stopping, an unmeasured verifier fences the experiment but failed assertions still permit refinement.
Given failed official practice that leaves an output, strict stopping imports no revision and makes no further model call.
Given STOP during image inspection, no container starts after inspection completes.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import executor
import experiment
from isolation import Boundary, Interrupted, copy_files, save
from scripted_provider import Provider

REPO = SCRIPTS.parents[4]
SDK = Path(os.environ.get("OPENSKILL_TEST_SDK", REPO / "packages/core/dist/index.js"))
IMAGE = os.environ.get("OPENSKILL_TEST_IMAGE")


class ExecutorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.out = self.base / "run"
        self.config = {"benchmark_id": "train", "case_ids": ["one"], "test_agent_id": "target",
                       "runtime": {r: {"provider": "test", "model_id": "test", "thinking_level": "medium"}
                                   for r in ("construction", "target")}}

    def test_manual_receipts_cannot_enter_isolated_journal(self):
        self.config["execution_mode"] = executor.MODE
        with self.assertRaisesRegex(ValueError, "executor.py"):
            experiment.run("init", self.out, self.config)
        experiment.run("init", self.out, self.config, executor=True)
        with self.assertRaisesRegex(ValueError, "executor.py"):
            experiment.run("event", self.out, {"action": "start-case", "case_id": "one"})
        self.assertEqual(experiment.run("status", self.out)["cases"], {})

    def test_older_journal_is_not_migrated(self):
        experiment.run("init", self.out, self.config)
        before = experiment.run("status", self.out)
        with self.assertRaisesRegex(ValueError, "new isolated-v1"):
            executor.run("event", self.out, {"action": "start-case", "case_id": "one"})
        self.assertEqual(before, experiment.run("status", self.out))

    def test_links_and_traversal_cannot_cross_roles(self):
        source = self.base / "source"
        source.mkdir()
        secret = self.base / "secret"
        secret.write_text("private")
        (source / "link").symlink_to(secret)
        os.link(secret, source / "hardlink")
        for entry in ("link", "hardlink", "../secret", str(secret)):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                copy_files(source, self.base / "import", [entry])
        self.assertFalse((self.base / "import").exists())

    def test_lock_blocks_duplicate_execution(self):
        with executor.lock(self.out):
            with self.assertRaisesRegex(ValueError, "Another executor"):
                with executor.lock(self.out):
                    self.fail("Second writer entered")

    def test_deadline_and_stop_prevent_launch(self):
        self.out.mkdir()
        cfg = {"docker": "/nonexistent-docker", "uid": 1000, "gid": 1000}
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with self.assertRaises(Interrupted):
            with Boundary(cfg, self.base / "control", self.out, [], expired, self.base / "STOP"):
                self.fail("Expired worker started")
        (self.base / "STOP").touch()
        future = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
        with self.assertRaises(Interrupted):
            with Boundary(cfg, self.base / "control", self.out, [], future, self.base / "STOP"):
                self.fail("Stopped worker started")
        self.assertFalse((self.base / "control").exists())

    def test_stop_during_image_inspection_prevents_creation(self):
        self.out.mkdir()
        cfg = {"image": "sha256:" + "a" * 64, "docker": "/unused", "uid": 1000, "gid": 1000}
        deadline = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
        boundary = Boundary(cfg, self.base / "control", self.out, [], deadline, self.base / "STOP")
        def inspected(args):
            self.assertEqual(args[:2], ["image", "inspect"])
            boundary.stop.touch()
            return subprocess.CompletedProcess(args, 0, json.dumps([{"Id": cfg["image"]}]))
        with patch.object(boundary, "docker_call", side_effect=inspected) as call:
            with self.assertRaises(Interrupted):
                with boundary:
                    self.fail("Stopped worker started")
            self.assertEqual(call.call_count, 1)


@unittest.skipUnless(IMAGE, "Set OPENSKILL_TEST_IMAGE to a local Python/pytest Debian image id for real isolation tests")
class DockerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.work, self.view = self.base / "work", self.base / "view"
        self.work.mkdir()
        self.view.mkdir()
        self.control = self.base / "control"
        self.stop = self.base / "STOP"
        self.config = {"image": IMAGE, "docker": shutil.which("docker"), "node": shutil.which("node"),
                       "uid": os.getuid(), "gid": os.getgid(), "entrypoint": "/bin/sleep", "command": ["infinity"]}
        self.deadline = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()

    def boundary(self):
        return Boundary(self.config, self.control, self.work, [self.view], self.deadline, self.stop)

    def test_real_sdk_file_and_shell_tools_are_confined(self):
        secret = self.base / "creator-SKILL.md"
        secret.write_text("PRIVATE-CANARY")
        public = self.view / "task.txt"
        public.write_text("PUBLIC-CANARY")
        with self.boundary() as sandbox:
            spec = {**self.config, "container": sandbox.name, "work": str(self.work), "readonly": [str(self.view)],
                    "sdk": str(SDK), "public": str(public), "secret": str(secret),
                    "role": "verifier", "runtime": {"thinking_level": "medium"}}
            save(self.base / "probe.json", spec)
            result = subprocess.run([self.config["node"], str(Path(__file__).with_name("probe-tools.mjs")),
                                     str(self.base / "probe.json")], text=True, capture_output=True, timeout=40,
                                    env={**os.environ, "OPENSKILL_HOST_CANARY": "HOST-SECRET"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # Network none removes every interface except loopback; public task services may use loopback.
            receipt = sandbox.run(["python3", "-c", "import os; assert os.listdir('/sys/class/net') == ['lo']"], self.base / "network.log")
            self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(public.read_text(), "PUBLIC-CANARY")
        self.assertEqual((self.work / "own.txt").read_text(), "own output")
        check = subprocess.run([self.config["docker"], "inspect", sandbox.name], capture_output=True)
        self.assertNotEqual(check.returncode, 0)

    def test_failed_start_has_no_fallback_or_surviving_container(self):
        self.config["entrypoint"] = "/does-not-exist"
        boundary = self.boundary()
        with self.assertRaises(subprocess.CalledProcessError):
            with boundary:
                self.fail("Failed boundary was accepted")
        self.assertEqual(list(self.work.iterdir()), [])
        check = subprocess.run([self.config["docker"], "inspect", boundary.name], capture_output=True)
        self.assertNotEqual(check.returncode, 0)

    def test_stop_kills_measurement_and_preserves_interrupted_receipt(self):
        # The test uses a visible STOP file to synchronize with a real running process.
        self.stop = self.work / "STOP"
        log = self.base / "cancel.log"
        with self.assertRaises(Interrupted):
            with self.boundary() as sandbox:
                sandbox.run(["python3", "-c", "from pathlib import Path; import subprocess; "
                             "p=subprocess.Popen(['sleep','600']); Path('STOP').touch(); p.wait()"], log)
        receipt = json.loads(log.with_suffix(".process.json").read_text())
        self.assertEqual(receipt["execution_status"], "interrupted")
        self.assertIsNone(receipt["exit_code"])
        check = subprocess.run([self.config["docker"], "inspect", sandbox.name], capture_output=True)
        self.assertNotEqual(check.returncode, 0)


@unittest.skipUnless(IMAGE, "Set OPENSKILL_TEST_IMAGE for the real SDK/executor loop")
class LoopTest(unittest.TestCase):
    def setUp(self):
        DockerTest.setUp(self)
        Provider.verifier_tests = 1
        Provider.omit_suite = False
        Provider.practice_exit_code = 0
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_agent_practice_resumes_creator_and_repairs_skill_with_independent_verification(self):
        self.run_loop("agent")

    def test_command_practice_repairs_skill_with_independent_verification(self):
        self.run_loop("command")

    def test_gdpevo_service_supports_the_full_agent_refinement_loop(self):
        self.config.pop("entrypoint")
        self.config.pop("command")
        self.config["startup_profile"] = "gdpevo"
        self.run_loop("agent")

    def test_failed_initialization_makes_no_model_request(self):
        self.config["entrypoint"] = "/does-not-exist"
        before = len(Provider.requests)
        with self.assertRaises(subprocess.CalledProcessError):
            self.create_run("agent")
        self.assertEqual(len(Provider.requests), before)
        self.assertFalse((self.base / "experiment/journal").exists())
        self.assertTrue((self.base / "experiment/STOP").exists())

    def run_loop(self, mode):
        out, request = self.create_run(mode, strict=True)
        state = executor.run("creator", out, request)
        creator = state["cases"]["one"]["creator_session_id"]
        self.assertEqual((out / "tasks/one/practice/revision-0/total.txt").read_text(), "3")
        state = executor.run("verifier", out, {"case_id": "one"})
        case = state["cases"]["one"]
        self.assertEqual(case["attempts"][0]["result"]["pass_rate"], 0)
        self.assertFalse((out / "STOP").exists())
        self.assertNotEqual(case["attempts"][0]["verifier_session_id"], creator)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["latest_issues"],
                         ["assertion_failure", "coverage_gap"], json.dumps(case["attempts"][0], indent=2))
        executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": 1,
                     "issues": ["assertion_failure", "coverage_gap"], "classification": "SELF-FIXABLE",
                     "next_action": "revise_skill", "diagnosis": "The last negative row was omitted",
                     "expected_change": "Include every row so total is 2", "evidence": ["tasks/one/verify/attempt-1/pytest.log"]})
        state = executor.run("creator", out, {"case_id": "one", "hypothesis": "Include every row"})
        self.assertEqual(state["cases"]["one"]["creator_session_id"], creator)
        self.assertEqual((out / "tasks/one/practice/revision-1/total.txt").read_text(), "2")
        state = executor.run("verifier", out, {"case_id": "one"})
        self.assertTrue(state["cases"]["one"]["attempts"][-1]["accepted"])
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "finish_surrogate_pass")
        state = executor.run("event", out, {"action": "finish-case", "case_id": "one", "reason": "surrogate_pass"})
        self.assertTrue(state["cases"]["one"]["final_was_tested"])
        with self.assertRaises(ValueError):
            executor.run("creator", out, {"case_id": "one", "hypothesis": "An extra edit"})

    def test_excess_parameterized_tests_do_not_execute(self):
        out, request = self.create_run("command")
        executor.run("creator", out, request)
        Provider.verifier_tests = 61
        state = executor.run("verifier", out, {"case_id": "one"})
        case = state["cases"]["one"]
        self.assertEqual(len(case["attempts"]), 1)
        self.assertEqual(case["attempts"][0]["result"]["status"], "failed")
        self.assertFalse((out / ".executor/one/verify-1/results/executed.txt").exists())
        self.assertIn("budget exceeded", (out / "tasks/one/verify/attempt-1/pytest.log").read_text())

    def test_missing_suite_is_unmeasured_and_needs_feedback(self):
        out, request = self.create_run("command")
        executor.run("creator", out, request)
        Provider.omit_suite = True
        state = executor.run("verifier", out, {"case_id": "one"})
        attempt = state["cases"]["one"]["attempts"][0]
        self.assertEqual(attempt["execution_status"], "not_started")
        self.assertEqual(attempt["result"]["status"], "failed")
        self.assertFalse((out / "tasks/one/verify/attempt-1/report.xml").exists())
        with self.assertRaises(ValueError):
            executor.run("verifier", out, {"case_id": "one"})
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 1)

    def test_strict_failure_stops_without_starting_another_attempt(self):
        out, request = self.create_run("command", strict=True)
        executor.run("creator", out, request)
        Provider.omit_suite = True
        with self.assertRaisesRegex(ValueError, "no valid measurement"):
            executor.run("verifier", out, {"case_id": "one"})
        self.assertTrue((out / "STOP").exists())
        self.assertTrue((out / ".executor/failure.json").exists())
        before = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("verifier", out, {"case_id": "one"})
        self.assertEqual(len(Provider.requests), before)
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 1)

    def test_command_failure_with_output_is_stopped(self):
        self.check_failed_practice("command")

    def test_agent_tool_failure_with_output_stops_before_next_model_request(self):
        self.check_failed_practice("agent")

    def check_failed_practice(self, mode):
        out, request = self.create_run(mode, strict=True)
        Provider.practice_exit_code = 23
        before = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("creator", out, request)
        self.assertEqual(len(Provider.requests) - before, 3 if mode == "agent" else 2)
        self.assertTrue((out / "STOP").exists())
        operation = out / ".executor/one/practice-0"
        self.assertEqual((operation / "outputs/total.txt").read_text(), "3")
        case = executor.run("status", out)["cases"]["one"]
        self.assertEqual(case["revisions"], [])
        self.assertEqual(case["attempts"], [])
        self.assertFalse((out / "tasks/one/practice/revision-0").exists())
        if mode == "agent":
            result = json.loads((operation / "execution/result.json").read_text())
            self.assertEqual(result["error_code"], "PRACTICE_TOOL_FAILED")
        else:
            receipt = json.loads((operation / "practice.process.json").read_text())
            self.assertEqual(receipt["exit_code"], 23)
        guidance = executor.run("next", out)
        self.assertTrue(guidance["stopped"])
        self.assertEqual(guidance["cases"]["one"]["next_action"], "stopped")
        probes = list((out / ".executor/runtime").iterdir())
        count = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "Stopped"):
            executor.run("creator", out, request)
        self.assertEqual(len(Provider.requests), count)
        self.assertEqual(list((out / ".executor/runtime").iterdir()), probes)

    def test_creator_source_cannot_be_imported_as_verifier_research(self):
        out, request = self.create_run("command")
        executor.run("creator", out, request)
        count = len(Provider.requests)
        state = executor.run("verifier", out, {"case_id": "one", "research_files": {
            "extra.md": "tasks/one/skills/calculate/SKILL.md"}})
        self.assertEqual(len(Provider.requests), count)
        self.assertEqual(state["cases"]["one"]["attempts"][0]["execution_status"], "not_started")
        self.assertFalse((out / ".executor/one/verify-1/view/additional-research").exists())

    def create_run(self, mode, strict=False):
        out = self.base / "experiment"
        home = self.base / "penguin"
        home.mkdir()
        sdk = SDK
        setup = ("import {saveProjectConfig} from " + json.dumps(sdk.as_uri()) + ";"
                 "await saveProjectConfig(process.argv[1], 'test', {version:1,models:[{provider:'test',model_id:'test',"
                 "client_type:'openai-chat',api_key:'local-fixture-only',base_url:process.argv[2],context_window:131072}]});")
        subprocess.run([self.config["node"], "--input-type=module", "-e", setup, str(home),
                        f"http://127.0.0.1:{self.server.server_port}/v1"], check=True, capture_output=True)
        config = {"benchmark_id": "train", "case_ids": ["one"], "test_agent_id": "target", "stop_on_recurrence": strict,
                  "runtime": {r: {"provider": "test", "model_id": "test", "thinking_level": "medium"}
                              for r in ("construction", "target")}, "execution_mode": executor.MODE,
                  "executor": {**self.config, "sanitized_image": True, "sdk": str(sdk),
                               "penguin_home": str(home), "project_id": "test", "practice_mode": mode}}
        executor.run("init", out, config)
        executor.run("event", out, {"action": "start-case", "case_id": "one"})
        (out / "tasks/one/inputs/public").mkdir(parents=True)
        (out / "tasks/one/inputs/knowledge").mkdir()
        (out / "tasks/one/inputs/anchors").mkdir()
        (out / "tasks/one/inputs/public/rows.json").write_text("[1, 2, -1]")
        (out / "tasks/one/inputs/knowledge/knowledge.md").write_text("Sum every numeric row. Source: https://docs.python.org/3/library/functions.html#sum")
        (out / "tasks/one/inputs/anchors/anchors.md").write_text("Independent anchor: 1 + 2 - 1 = 2, by integer arithmetic.")
        request = {"case_id": "one", "skills": ["calculate"], "outputs": ["total.txt"],
                   "public": {"rows.json": "tasks/one/inputs/public/rows.json"}, "knowledge": {"knowledge.md": "tasks/one/inputs/knowledge/knowledge.md"},
                   "anchors": {"anchors.md": "tasks/one/inputs/anchors/anchors.md"}, "hypothesis": "Initial arithmetic implementation"}
        return out, request


if __name__ == "__main__":
    unittest.main()

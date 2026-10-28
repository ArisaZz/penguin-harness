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
Given revised practice selecting the common skill/output parent, the same creator finishes
inside its writable workspace without exposing the host's experiment parent.
Given a practice workspace remounted over author files, SDK tools see frozen inputs and fresh
outputs only; author-private files are hidden and read-only input writes remain refused.
Given undeclared, duplicate, relative or shadowing mount destinations, validation refuses
them before any container record or process is created.
Given passing output tests, case completion still requires a digest-bound controller review.
Given a verification plan, no candidate outputs are mounted before controller review;
continuation uses the same verifier session and spends no second attempt.
Given a missing/stale review, dispatch makes no model request and leaves the pending attempt intact.
Given an unsupported permission promoted to covered, no pytest process starts and strict stopping fences the run.
Given an honestly unresolved permission, valid arithmetic tests run but surrogate success remains unavailable.
Given a changed plan source, continuation is refused before model dispatch.
Given a completed refinement, the last library freezes, loads through the real SDK,
and its installed script applies to a new input without construction paths.
Given a development replay, only verifier roles run; its measured result cannot freeze,
deploy, retry in place or become a benchmark score, and source artifacts stay unchanged.
Given an author report remembered in the creator's session, official practice uses a real
read-only handoff, completes refinement and freezes without importing that report.
Given a practice that still reads an author-only report, strict stop preserves partial
outputs as diagnostics and makes no further model call or revision.
Given a host-side change to frozen skills or public inputs during practice, the executor
records an integrity failure and refuses output import even when the tool exits zero.
Given a removed input directory, integrity failure is retained instead of a passing receipt.
Given a preexisting practice context, handoff creation refuses to overwrite evidence.
Given repeated requirement wording with distinct IDs, the full refinement still freezes.
Given a nonexistent coverage test ID and passing pytest, strict stop retains the measured
result, fences the run, cleans containers and prevents all further model dispatch.
Given honest coverage gaps through the retry cap, feedback and independent research
consume the existing budget; case closure preserves the last revision without claiming success.
Given graded recovery and a temporary self-check KeyError, bounded correction completes
delivery but independent verification still rejects a wrong answer.
Given a repeated error or total recovery exhaustion, no further model request or output import occurs.
Given a frozen skill failure, the same creator must revise the skill before fresh practice;
old partial outputs stay diagnostic and execution repair cannot exceed its Case budget.
Given an invalid verifier artifact, one reviewed repair spends the original attempt budget;
a repeated invalid artifact stops and a real assertion failure still follows skill feedback.
Given a recovered practice followed by another revision, recovery allowances never reset.
Given a command killed with a signal-style status, no skill-repair allowance is granted.
Given public, independent and additional research in separate directories, official pytest
and development replay read each through its explicit runtime path without host fallbacks.
Given malformed research selection before a verifier or practice repair, dispatch refuses
without spending budget, staging files, probing runtime or calling a model; a corrected request works.
Given changed or hard-linked sealed research, dispatch still fences the experiment before another model call.
Given a measured bug plus unknown policy, one documented empty-search fallback resumes
the same creator, changes executable skills, regenerates and independently verifies outputs;
passing supported checks then close as evidence_limited with the unknown policy retained.
Unknowns alone cannot manufacture a skill defect, bypass supported failures or claim full success.
Given the observed optional-list loader defect with passing task checks, v2 requires an
evidenced review, refuses closure, transfers the diagnostic to the same creator, and records
a real resource change, fresh practice and independent list/object regression verification.
An unresolved finding cannot disappear after verifier repair or a new revision; stale or
fabricated resolution evidence and unrelated edits cannot substitute for the fix.
Given a last-attempt finding, final repair stays within the cap and cannot claim verified resolution.
Given sealed review evidence changed later, continuation refuses the altered record.
Given creator diagnostics, the independent verifier's view excludes those files.
Given a clean sealed review followed by a newly observed defect before feedback,
append the finding without overwriting the earlier review or permitting early closure.
Given v2 sibling command failures, the next response corrects them, delivery is verified,
and a supported assertion failure still drives a real same-creator skill revision.
Given exhausted v2 local recovery, retained diagnostics permit bounded fresh practice;
allowances never reset, frozen skills remain unchanged, and exhausted execution repair stops.
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
import verifier_replay
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

    def test_invalid_mount_destinations_cannot_create_a_boundary(self):
        work, view = self.base / "work", self.base / "view"
        work.mkdir()
        view.mkdir()
        cfg = {"docker": "/unused", "uid": 1000, "gid": 1000}
        for targets in ({self.base / "secret": work}, {work: Path("relative")},
                        {work: self.base / "../escape"}, {view: work}, {view: work.parent}):
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                Boundary(cfg, self.base / "control", work, [view],
                         datetime.now(timezone.utc).isoformat(), self.base / "STOP", targets=targets)
        self.assertFalse((self.base / "control").exists())

    def test_lock_blocks_duplicate_execution(self):
        with executor.lock(self.out):
            with self.assertRaisesRegex(ValueError, "Another executor"):
                with executor.lock(self.out):
                    self.fail("Second writer entered")

    def test_removed_input_directory_has_a_failed_integrity_record(self):
        (self.out / "skills").mkdir(parents=True)
        (self.out / "skills/script.py").write_text("pass")
        with self.assertRaisesRegex(ValueError, "Practice inputs changed"):
            executor.check_practice_inputs(self.out, {"skills": "unused", "inputs": "unused"}, "after")
        record = json.loads((self.out / "integrity-after.json").read_text())
        self.assertEqual(record["status"], "failed")
        self.assertIn("error", record)

    def test_existing_context_is_preserved_when_handoff_is_refused(self):
        (self.out / "view").mkdir(parents=True)
        context = self.out / "view/practice-context.json"
        context.write_text('{"evidence":"preserve"}')
        with self.assertRaisesRegex(ValueError, "context already exists"):
            executor.practice_handoff(self.out, Path("skills"), Path("inputs"), Path("."), ["answer.json"])
        self.assertEqual(context.read_text(), '{"evidence":"preserve"}')

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

    def test_practice_workspace_hides_author_files_and_keeps_inputs_readonly(self):
        secret = self.work / "author-private.txt"
        secret.write_text("PRIVATE-CANARY")
        (self.view / "task.txt").write_text("PUBLIC-CANARY")
        outputs = self.base / "outputs"
        outputs.mkdir()
        with Boundary(self.config, self.control, outputs, [self.view], self.deadline, self.stop,
                      targets={outputs: self.work, self.view: self.work / "inputs"}) as sandbox:
            spec = {**self.config, "container": sandbox.name, "work": str(self.work),
                    "readonly": [str(self.work / "inputs")], "sdk": str(SDK),
                    "public": str(self.work / "inputs/task.txt"), "secret": str(secret),
                    "role": "creator", "runtime": {"thinking_level": "medium"}}
            save(self.base / "probe.json", spec)
            result = subprocess.run([self.config["node"], str(Path(__file__).with_name("probe-tools.mjs")),
                                     str(self.base / "probe.json")], text=True, capture_output=True, timeout=40,
                                    env={**os.environ, "OPENSKILL_HOST_CANARY": "HOST-SECRET"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((outputs / "own.txt").read_text(), "own output")
        self.assertFalse((self.work / "own.txt").exists())
        self.assertEqual(secret.read_text(), "PRIVATE-CANARY")
        self.assertEqual((self.view / "task.txt").read_text(), "PUBLIC-CANARY")

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
        Provider.practice_from_skill_parent = False
        Provider.unsupported_oracle = False
        Provider.promote_unsupported = False
        Provider.practice_handoff = None
        Provider.practice_hook = None
        Provider.repeated_requirements = False
        Provider.unknown_test_mapping = False
        Provider.practice_scripts = None
        Provider.practice_script_index = 0
        Provider.skill_exception = False
        Provider.additional_research = False
        Provider.plan_loader_bug = False
        Provider.plan_loader_checks = False
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

    def test_revised_practice_can_use_the_common_skill_and_output_workspace(self):
        Provider.practice_from_skill_parent = True
        self.run_loop("agent")

    def test_command_practice_repairs_skill_with_independent_verification(self):
        self.run_loop("command")

    def test_repeated_requirement_wording_survives_refinement_and_freeze(self):
        Provider.repeated_requirements = True
        self.run_loop("command")

    def test_handoff_preserves_creator_history_without_exposing_author_reports(self):
        Provider.practice_handoff = "use_context"
        self.run_loop("agent")
        out = self.base / "experiment"
        self.assertTrue((out / ".executor/one/creator-work/reports/deployment-check.md").is_file())
        for index in (0, 1):
            operation = out / f".executor/one/practice-{index}"
            self.assertFalse((operation / "outputs/reports/deployment-check.md").exists())
            for stage in ("before", "after"):
                self.assertEqual(json.loads((operation / f"integrity-{stage}.json").read_text())["status"], "passed")

    def test_missing_author_report_remains_a_strict_failure(self):
        Provider.practice_handoff = "use_author_report"
        out, request = self.create_run("agent", strict=True)
        before = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("creator", out, request)
        self.assertEqual(len(Provider.requests) - before, 3)
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(executor.run("status", out)["cases"]["one"]["revisions"], [])
        self.assertEqual((out / ".executor/one/practice-0/outputs/total.txt").read_text(), "3")
        self.assertIn("FileNotFoundError", (out / ".executor/one/practice-0/execution/messages.jsonl").read_text())
        self.assertFalse((out / "tasks/one/practice/revision-0").exists())

    def test_changed_frozen_skills_prevent_import_of_successful_practice(self):
        self.check_changed_practice_input("skills/calculate/SKILL.md", "Changed externally")

    def test_changed_public_input_prevents_import_of_successful_practice(self):
        self.check_changed_practice_input("view/public/rows.json", "[8, 2, -1]")

    def test_changed_handoff_prevents_import_of_successful_practice(self):
        self.check_changed_practice_input("view/practice-context.json", "{}")

    def check_changed_practice_input(self, path, content):
        out, request = self.create_run("agent", strict=True)
        operation = out / ".executor/one/practice-0"
        Provider.practice_hook = lambda: (operation / path).write_text(content)
        with self.assertRaisesRegex(ValueError, "Practice inputs changed"):
            executor.run("creator", out, request)
        self.assertTrue((out / "STOP").exists())
        self.assertTrue(json.loads((operation / "execution/result.json").read_text())["completed"])
        self.assertEqual(json.loads((operation / "integrity-after.json").read_text())["status"], "failed")
        self.assertEqual(executor.run("status", out)["cases"]["one"]["revisions"], [])
        self.assertFalse((out / "tasks/one/practice/revision-0").exists())

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
        state = self.verify(out)
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
        state = self.verify(out)
        self.assertTrue(state["cases"]["one"]["attempts"][-1]["accepted"])
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "finish_surrogate_pass")
        finish = {"action": "finish-case", "case_id": "one", "reason": "surrogate_pass"}
        with self.assertRaises(ValueError):
            executor.run("event", out, finish)
        self.assertFalse(executor.run("status", out)["cases"]["one"].get("finished"))
        revision = state["cases"]["one"]["revisions"][-1]
        review = {key: revision[key] for key in ("skills_sha256", "outputs_sha256")}
        review["checks"] = {key: {"status": "passed", "finding": "Reviewed the fixture's execution and reusable sum skill",
            "evidence": ["tasks/one/executions/run-1.log", "tasks/one/skills/calculate/SKILL.md"]}
            for key in ("delivery", "portable_content", "construction_isolation")}
        save(out / "tasks/one/review/final.json", review)
        state = executor.run("event", out, {**finish, "process_review": "tasks/one/review/final.json"})
        self.assertTrue(state["cases"]["one"]["final_was_tested"])
        library = out / "library"
        shutil.copytree(out / "tasks/one/skills", library / "tasks/one")
        (library / "SKILL.md").write_text("---\nname: openskill-library\ndescription: Read the public applicability index.\n"
                                         "version: 2026.10.19.2\n---\nRead index.md and apply the matching skill.\n")
        (library / "index.md").write_text("Sum numeric rows: tasks/one/calculate/SKILL.md\n")
        frozen = executor.run("event", out, {"action": "freeze"})
        self.assertEqual(frozen["phase"], "frozen")
        payload = {"name": "openskill-library", "content": (library / "SKILL.md").read_text(),
                   "files": {p.relative_to(library).as_posix(): p.read_text()
                             for p in library.rglob("*") if p.is_file() and p != library / "SKILL.md"}}
        save(self.base / "install.json", payload)
        script = ("import {installSkill,listInstalledSkills} from " + json.dumps(SDK.as_uri()) + ";"
                  "import {readFile} from 'node:fs/promises';"
                  "await installSkill(process.argv[1],'test','fresh-target',JSON.parse(await readFile(process.argv[2],'utf8')));"
                  "const skills=await listInstalledSkills(process.argv[1],'test','fresh-target');"
                  "if(skills.length!==1||skills[0].name!=='openskill-library'||!skills[0].description)throw Error('Library not loaded');")
        subprocess.run([self.config["node"], "--input-type=module", "-e", script,
                        str(self.base / "penguin"), str(self.base / "install.json")], check=True, capture_output=True)
        installed = self.base / "penguin/test/agents/fresh-target/agent_state/skills/openskill-library"
        (self.base / "new-rows.json").write_text("[4, -2, 7]")
        subprocess.run([sys.executable, str(installed / "tasks/one/calculate/scripts/total.py"),
                        str(self.base / "new-rows.json"), str(self.base / "new-total.txt")], check=True)
        self.assertEqual((self.base / "new-total.txt").read_text(), "9")
        with self.assertRaises(ValueError):
            executor.run("creator", out, {"case_id": "one", "hypothesis": "An extra edit"})

    def test_excess_parameterized_tests_do_not_execute(self):
        out, request = self.create_run("command")
        executor.run("creator", out, request)
        Provider.verifier_tests = 61
        state = self.verify(out)
        case = state["cases"]["one"]
        self.assertEqual(len(case["attempts"]), 1)
        self.assertEqual(case["attempts"][0]["result"]["status"], "failed")
        self.assertFalse((out / ".executor/one/verify-1/results/executed.txt").exists())
        self.assertIn("budget exceeded", (out / "tasks/one/verify/attempt-1/pytest.log").read_text())

    def test_missing_suite_is_unmeasured_and_needs_feedback(self):
        out, request = self.create_run("command")
        executor.run("creator", out, request)
        Provider.omit_suite = True
        state = self.verify(out)
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
            self.verify(out)
        self.assertTrue((out / "STOP").exists())
        self.assertTrue((out / ".executor/failure.json").exists())
        before = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("verifier", out, {"case_id": "one"})
        self.assertEqual(len(Provider.requests), before)
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 1)

    def test_graded_self_check_recovery_does_not_pass_a_wrong_answer(self):
        out, request = self.create_run("agent", graded={})
        Provider.practice_scripts = ["${BASE_COMMAND} && python3 -c \"{}['SELF_SERVICE']\"",
                                     "python3 -c \"assert {'self_service_fixes':1}['self_service_fixes']==1\""]
        state = executor.run("creator", out, request)
        self.assertFalse((out / "STOP").exists())
        self.assertEqual(state["cases"]["one"]["tool_recovery"]["used"], 1)
        self.assertEqual(len(state["cases"]["one"]["revisions"]), 1)
        state = self.verify(out)
        attempt = state["cases"]["one"]["attempts"][-1]
        self.assertFalse(attempt["accepted"])
        self.assertEqual(attempt["result"]["failed"], 1)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "record_feedback")

    def test_graded_repeated_error_stops_before_another_request(self):
        out, request = self.create_run("agent", graded={})
        Provider.practice_scripts = ["${BASE_COMMAND} && python3 -c \"{}['a']\"",
                                     "python3 -c \"{}['different-key']\"", "true"]
        before = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "RECOVERY_BUDGET_EXHAUSTED"):
            executor.run("creator", out, request)
        self.assertEqual(len(Provider.requests) - before, 4)
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(executor.run("status", out)["cases"]["one"]["revisions"], [])

    def test_v2_sibling_failures_continue_to_independent_feedback_and_skill_revision(self):
        out, request = self.create_run("agent", graded={"version": 2, "max_same_error_recoveries": 1})
        Provider.practice_scripts = [
            ["${BASE_COMMAND} && python3 -c \"{}[0]\"", "python3 -c \"{}[0]\""], "true"]
        state = executor.run("creator", out, request)
        case = state["cases"]["one"]
        creator = case["creator_session_id"]
        self.assertFalse((out / "STOP").exists())
        self.assertEqual(case["tool_recovery"]["used"], 1)
        report = json.loads((out / ".executor/one/practice-0/execution/recovery.json").read_text())
        self.assertEqual([e["decision"] for e in report["events"]], ["recover", "coalesced"])
        old_hash = case["revisions"][0]["skills_sha256"]
        old_output = (out / "tasks/one/practice/revision-0/total.txt").read_bytes()
        state = self.verify(out)
        attempt = state["cases"]["one"]["attempts"][-1]
        self.assertFalse(attempt["accepted"])
        executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": 1,
            "issues": experiment.workflow.issues(attempt), "classification": "SELF-FIXABLE",
            "next_action": "revise_skill", "diagnosis": "Last row omitted", "expected_change": "Include all rows",
            "evidence": ["tasks/one/verify/attempt-1/pytest.log"]})
        Provider.practice_scripts = None
        executor.run("creator", out, {"case_id": "one", "hypothesis": "Include every row"})
        case = self.verify(out)["cases"]["one"]
        self.assertEqual(case["creator_session_id"], creator)
        self.assertNotEqual(case["revisions"][-1]["skills_sha256"], old_hash)
        self.assertEqual(case["revisions"][-1]["change_kind"], "revise_skill")
        self.assertEqual(case["tool_recovery"]["used"], 1)
        self.assertTrue(case["attempts"][-1]["accepted"])
        self.assertEqual((out / "tasks/one/practice/revision-0/total.txt").read_bytes(), old_output)

    def test_v2_exhausted_local_recovery_returns_to_bounded_execution_repair(self):
        out, request = self.create_run("agent", graded={"version": 2, "max_tool_recoveries": 1,
                                                       "max_same_error_recoveries": 1})
        Provider.practice_scripts = ["${BASE_COMMAND} && python3 -c \"{}[0]\"",
                                     "python3 -c \"{}[0]\"", "true"]
        state = executor.run("creator", out, request)
        case = state["cases"]["one"]
        creator = case["creator_session_id"]
        failure = case["execution_failures"][0]
        self.assertEqual(failure["error_code"], "RECOVERY_BUDGET_EXHAUSTED")
        self.assertEqual(case["revisions"], [])
        self.assertFalse((out / "STOP").exists())
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "repair_execution")
        self.assertEqual(len(case["attempts"]), 0)
        Provider.practice_scripts = ["${BASE_COMMAND}"]
        state = executor.run("creator", out, {"case_id": "one", "hypothesis": "Correct inspector invocation",
            "execution_recovery": {"action": "repeat_practice", "diagnosis": "Inspector assumed a list",
                                   "expected_change": "Apply frozen skill and deliver total.txt"}})
        case = state["cases"]["one"]
        self.assertEqual(case["creator_session_id"], creator)
        self.assertEqual(case["tool_recovery"]["used"], 1)
        self.assertEqual(len(case["execution_repairs"]), 1)
        self.assertNotIn("execution_pending", case)
        self.assertEqual(case["revisions"][0]["skills_sha256"], failure["skills_sha256"])
        self.assertFalse((out / ".executor/one/practice-0-recovery-1/author").exists())
        self.assertFalse(self.verify(out)["cases"]["one"]["attempts"][-1]["accepted"])

    def test_v2_execution_repair_exhaustion_stops_without_resetting_tool_allowances(self):
        out, request = self.create_run("agent", graded={"version": 2, "max_execution_repairs": 1,
            "max_tool_recoveries": 1, "max_same_error_recoveries": 1})
        Provider.practice_scripts = ["${BASE_COMMAND} && python3 -c \"{}[0]\"",
                                     "python3 -c \"{}[0]\""]
        executor.run("creator", out, request)
        with self.assertRaisesRegex(ValueError, "Execution repair budget exhausted"):
            executor.run("creator", out, {"case_id": "one", "hypothesis": "Correct invocation",
                "execution_recovery": {"action": "repeat_practice", "diagnosis": "Inspector assumed a list",
                                       "expected_change": "Deliver output without a failed inspector"}})
        case = executor.run("status", out)["cases"]["one"]
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(case["tool_recovery"]["used"], 1)
        self.assertEqual(len(case["execution_failures"]), 2)
        self.assertEqual(case["revisions"], [])
        before = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("creator", out, request)
        self.assertEqual(len(Provider.requests), before)

    def test_graded_frozen_skill_repair_uses_fresh_practice_and_same_creator(self):
        out, request = self.create_run("agent", graded={})
        Provider.skill_exception = True
        state = executor.run("creator", out, request)
        creator = state["cases"]["one"]["creator_session_id"]
        self.assertEqual(state["cases"]["one"]["revisions"], [])
        self.assertFalse((out / "STOP").exists())
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "repair_execution")
        old = (out / ".executor/one/practice-0/outputs/total.txt").read_bytes()
        Provider.skill_exception = False
        state = executor.run("creator", out, {"case_id": "one", "hypothesis": "Include every row",
            "execution_recovery": {"action": "revise_skill", "diagnosis": "Frozen script raised KeyError",
                                   "expected_change": "Script completes from public inputs"}})
        case = state["cases"]["one"]
        self.assertEqual(case["creator_session_id"], creator)
        self.assertEqual(len(case["execution_repairs"]), 1)
        self.assertNotIn("execution_pending", case)
        self.assertEqual((out / ".executor/one/practice-0/outputs/total.txt").read_bytes(), old)
        self.assertEqual((out / "tasks/one/practice/revision-0/total.txt").read_text(), "2")
        self.assertTrue(self.verify(out)["cases"]["one"]["attempts"][-1]["accepted"])

    def test_graded_execution_repair_exhaustion_cannot_import_partial_outputs(self):
        out, request = self.create_run("command", graded={})
        Provider.practice_exit_code = 23
        executor.run("creator", out, request)
        with self.assertRaisesRegex(ValueError, "Execution repair budget exhausted"):
            executor.run("creator", out, {"case_id": "one", "hypothesis": "Include every row",
                "execution_recovery": {"action": "revise_skill", "diagnosis": "Script exits 23",
                                       "expected_change": "Return a successful process result"}})
        self.assertTrue((out / "STOP").exists())
        case = executor.run("status", out)["cases"]["one"]
        self.assertEqual(case["revisions"], [])
        self.assertEqual(len(case["execution_failures"]), 2)

    def test_graded_verifier_repair_spends_existing_attempts(self):
        out, request = self.create_run("command", graded={})
        executor.run("creator", out, request)
        Provider.omit_suite = True
        state = self.verify(out)
        self.assertFalse((out / "STOP").exists())
        attempt = state["cases"]["one"]["attempts"][-1]
        executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": 1,
            "issues": experiment.workflow.issues(attempt), "classification": "SELF-FIXABLE",
            "next_action": "repair_verifier", "diagnosis": "Verifier omitted its suite",
            "expected_change": "Deliver an executable independent suite",
            "evidence": ["tasks/one/verify/attempt-1/failure.txt"]})
        Provider.omit_suite = False
        state = self.verify(out)
        case = state["cases"]["one"]
        self.assertEqual(len(case["attempts"]), 2)
        self.assertFalse(case["attempts"][-1]["accepted"])
        self.assertFalse((out / "STOP").exists())
        self.assertEqual(executor.run("next", out)["cases"]["one"]["recovery"]["verifier_repairs"], 0)

    def research_repair(self):
        out, request = self.create_run("command", graded={})
        request["hypothesis"] = "Include every row"
        executor.run("creator", out, request)
        Provider.omit_suite = True
        state = self.verify(out)
        executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": 1,
            "issues": experiment.workflow.issues(state["cases"]["one"]["attempts"][-1]),
            "classification": "NEEDS-DR", "next_action": "repair_verifier",
            "diagnosis": "Suite omitted; retrieve an independent arithmetic cross-check",
            "expected_change": "Read the supported evidence and deliver executable tests",
            "evidence": ["tasks/one/verify/attempt-1/failure.txt"]})
        evidence = []
        for number, outcome in enumerate(("retrieved", "unavailable"), 1):
            executor.run("event", out, {"action": "targeted-search", "case_id": "one",
                "classification": "NEEDS-DR", "query": "independent arithmetic reference"})
            path = f"tasks/one/research/search-{number}.json"
            save(out / path, {"expected": 2} if outcome == "retrieved" else {"results": []})
            executor.run("event", out, {"action": "search-result", "case_id": "one", "search": number,
                "outcome": outcome, "summary": "Public arithmetic" if outcome == "retrieved" else "No further source",
                "sources": ["https://docs.python.org/3/library/functions.html#sum"], "evidence": [path]})
            evidence.append(path)
        Provider.omit_suite = False
        return out, evidence

    def test_invalid_research_request_preserves_repair_then_supported_evidence_is_measured(self):
        out, (supported, unavailable) = self.research_repair()
        before = executor.run("status", out)
        files_before = executor.tree(out / ".executor")
        count = len(Provider.requests)
        invalid = [None, [], {"empty.json": unavailable}, {"code.py": "tasks/one/skills/calculate/SKILL.md"},
                   {"../escape": supported}, {"/absolute": supported}, {"": supported}, {"nul\x00": supported},
                   {"a": supported, "a/b": supported}, {"a/b": supported, "a": supported},
                   {"a/b": supported, "a//b": supported}, {"a": []}, {1: supported}]
        for mapping in invalid:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                executor.run("verifier-plan", out, {"case_id": "one", "research_files": mapping})
            self.assertEqual(executor.run("status", out), before)
            self.assertEqual(executor.tree(out / ".executor"), files_before)
            self.assertEqual(len(Provider.requests), count)
            self.assertFalse((out / "STOP").exists())
        self.assertEqual(executor.run("next", out)["cases"]["one"]["recovery"]["verifier_repairs"], 1)
        Provider.additional_research = True
        review = self.reviewed_plan(out, {"business/api-evidence.json": supported})
        state = executor.run("verifier", out, review)
        case = state["cases"]["one"]
        self.assertEqual(len(case["attempts"]), 2)
        self.assertTrue(case["attempts"][-1]["accepted"])
        self.assertEqual(case["attempts"][-1]["result"]["pass_rate"], 1)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["recovery"]["verifier_repairs"], 0)
        self.assertFalse((out / "STOP").exists())

    def test_changed_sealed_research_still_stops_before_dispatch(self):
        out, (supported, _) = self.research_repair()
        save(out / supported, {"expected": 99})
        count = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            executor.run("verifier-plan", out, {"case_id": "one", "research_files": {"extra.json": supported}})
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(len(Provider.requests), count)
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 1)

    def test_linked_research_with_unchanged_bytes_still_stops_before_dispatch(self):
        out, (supported, _) = self.research_repair()
        os.link(out / supported, self.base / "linked-evidence.json")
        count = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "research integrity failed"):
            executor.run("verifier-plan", out, {"case_id": "one", "research_files": {"extra.json": supported}})
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(len(Provider.requests), count)
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 1)

    def test_graded_second_invalid_verifier_stops(self):
        out, request = self.create_run("command", graded={})
        executor.run("creator", out, request)
        Provider.omit_suite = True
        state = self.verify(out)
        attempt = state["cases"]["one"]["attempts"][-1]
        executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": 1,
            "issues": experiment.workflow.issues(attempt), "classification": "SELF-FIXABLE",
            "next_action": "repair_verifier", "diagnosis": "Missing suite", "expected_change": "Supply suite",
            "evidence": ["tasks/one/verify/attempt-1/failure.txt"]})
        with self.assertRaisesRegex(ValueError, "Verifier repair budget exhausted"):
            self.verify(out)
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 2)

    def test_graded_tool_budget_persists_across_skill_revisions(self):
        out, request = self.create_run("agent", graded={"max_tool_recoveries": 1})
        Provider.practice_scripts = ["${BASE_COMMAND} && python3 -c \"{}['a']\"", "true"]
        executor.run("creator", out, request)
        state = self.verify(out)
        attempt = state["cases"]["one"]["attempts"][-1]
        executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": 1,
            "issues": experiment.workflow.issues(attempt), "classification": "SELF-FIXABLE",
            "next_action": "revise_skill", "diagnosis": "Last row omitted", "expected_change": "Include all rows",
            "evidence": ["tasks/one/verify/attempt-1/pytest.log"]})
        Provider.practice_scripts = ["${BASE_COMMAND} && python3 -c \"undefined_value\"", "true"]
        with self.assertRaisesRegex(ValueError, "RECOVERY_BUDGET_EXHAUSTED"):
            executor.run("creator", out, {"case_id": "one", "hypothesis": "Include every row"})
        self.assertTrue((out / "STOP").exists())
        case = executor.run("status", out)["cases"]["one"]
        self.assertEqual(case["tool_recovery"]["used"], 1)
        self.assertEqual(len(case["revisions"]), 1)

    def test_graded_missing_delivery_repeats_frozen_skills_without_authoring(self):
        out, request = self.create_run("agent", graded={})
        Provider.practice_scripts = ["printf diagnostic > partial.txt"]
        state = executor.run("creator", out, request)
        before = len(Provider.requests)
        self.assertEqual(state["cases"]["one"]["revisions"], [])
        before_request = executor.run("status", out)
        with self.assertRaisesRegex(ValueError, "research"):
            executor.run("creator", out, {"case_id": "one", "research_files": {"bad": "unregistered"},
                "execution_recovery": {"action": "repeat_practice", "diagnosis": "Missing result",
                                       "expected_change": "Deliver total.txt"}})
        self.assertEqual(executor.run("status", out), before_request)
        self.assertEqual(len(Provider.requests), before)
        self.assertFalse((out / "STOP").exists())
        Provider.practice_scripts = ["${BASE_COMMAND} && test ! -e partial.txt"]
        state = executor.run("creator", out, {"case_id": "one", "hypothesis": "Deliver required result",
            "execution_recovery": {"action": "repeat_practice", "diagnosis": "Declared file was absent",
                                   "expected_change": "Execute frozen script and deliver total.txt"}})
        self.assertEqual(len(Provider.requests) - before, 2)
        self.assertEqual(len(state["cases"]["one"]["revisions"]), 1)
        self.assertTrue((out / ".executor/one/practice-0/outputs/partial.txt").exists())
        self.assertFalse((out / "tasks/one/practice/revision-0/partial.txt").exists())

    def test_graded_permission_failure_cannot_spend_local_recovery(self):
        out, request = self.create_run("agent", graded={})
        Provider.practice_scripts = ["python3 -c \"open('skills/calculate/SKILL.md','w').write('changed')\"", "true"]
        before = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "PRACTICE_HARD_FAILURE"):
            executor.run("creator", out, request)
        self.assertEqual(len(Provider.requests) - before, 3)
        self.assertTrue((out / "STOP").exists())
        self.assertEqual(executor.run("status", out)["cases"]["one"]["tool_recovery"]["used"], 0)

    def test_graded_command_signal_failure_does_not_offer_skill_repair(self):
        out, request = self.create_run("command", graded={})
        Provider.practice_exit_code = 137
        with self.assertRaisesRegex(ValueError, "signal or permission failure"):
            executor.run("creator", out, request)
        self.assertTrue((out / "STOP").exists())
        case = executor.run("status", out)["cases"]["one"]
        self.assertNotIn("execution_pending", case)
        self.assertEqual(case["revisions"], [])

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
        out, request = self.create_run("command", strict=True)
        executor.run("creator", out, request)
        count = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "research"):
            executor.run("verifier-plan", out, {"case_id": "one", "research_files": {
                "extra.md": "tasks/one/skills/calculate/SKILL.md"}})
        self.assertEqual(len(Provider.requests), count)
        self.assertEqual(executor.run("status", out)["cases"]["one"]["attempts"], [])
        self.assertFalse((out / ".executor/one/verify-1").exists())
        self.assertFalse((out / "STOP").exists())

    def reviewed_plan(self, out, research_files=None):
        state = executor.run("verifier-plan", out, {"case_id": "one", "research_files": research_files or {}})
        attempt = state["cases"]["one"]["attempts"][-1]
        self.assertFalse(attempt["finished"])
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "review_verification_plan")
        operation = out / attempt["planning"]["operation"]
        plan = json.loads((operation / "oracle/plan.json").read_text())
        seal = json.loads((operation / "oracle/seal.json").read_text())
        review = {key: seal[key] for key in ("plan_sha256", "inputs_sha256")}
        review.update(reviewer="test controller", scope="independent_evidence", decisions=[
            {"id": e["id"], "status": "unverified" if e["basis"] == "hypothesis" else "supported",
             "finding": "Sum is independently computable from the numeric rows; no permission policy was supplied."}
            for e in plan["requirements"]])
        relative = f"tasks/one/review/attempt-{attempt['number']}.json"
        save(out / relative, review)
        return {"case_id": "one", "review": relative}

    def verify(self, out):
        return executor.run("verifier", out, self.reviewed_plan(out))

    def test_passing_proxy_with_unknown_policy_still_repairs_documented_list_input(self):
        self.check_reviewed_skill_refinement(unknown=True)

    def test_complete_proxy_pass_does_not_hide_an_observed_skill_defect(self):
        self.check_reviewed_skill_refinement(unknown=False)

    def test_last_attempt_allows_final_skill_repair_but_retains_unverified_finding(self):
        self.check_reviewed_skill_refinement(unknown=False, verification_budget=1)

    def check_reviewed_skill_refinement(self, unknown, verification_budget=3):
        Provider.plan_loader_bug = True
        Provider.unsupported_oracle = unknown
        out, request = self.create_run("agent", graded={}, feedback_policy=None,
                                       verification_budget=verification_budget)
        public = out / "tasks/one/inputs/public"
        for name, value in (("list.json", ["first", "second"]),
                            ("object.json", {"requests": ["first", "second"]})):
            save(public / name, value)
            request["public"][name] = f"tasks/one/inputs/public/{name}"
        (public / "plan-contract.txt").write_text("Accept a list or an object containing requests.")
        request["public"]["plan-contract.txt"] = "tasks/one/inputs/public/plan-contract.txt"
        request.update(hypothesis="Include every row", outputs=["total.txt", "loader.json"])
        first = executor.run("creator", out, request)["cases"]["one"]
        creator = first["creator_session_id"]
        root = out / "tasks/one"
        original_output = (root / "practice/revision-0/loader.json").read_bytes()
        observed = json.loads(original_output)
        self.assertEqual(observed["object"]["exit_code"], 0)
        self.assertIn("AttributeError", observed["list"]["stderr"])
        case = self.verify(out)["cases"]["one"]
        self.assertEqual(case["attempts"][-1]["result"]["pass_rate"], 1)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "review_skills")
        revision = case["revisions"][-1]
        diagnostic = "tasks/one/diagnoses/list-plan.json"
        save(out / diagnostic, {"contract": "Accept a list or an object containing requests.",
                               "observed": observed, "expected": "Both forms return the supplied request count"})
        finding = {"id":"list-plan", "observation":"Documented list input calls dict.get and raises AttributeError",
                   "planned_change":"Branch on object/list before accessing requests; preserve both forms",
                   "validation":"Execute the frozen resource on both public forms and independently check counts",
                   "affected_resources":["calculate/scripts/total.py"],
                   "evidence":[diagnostic,"tasks/one/revisions/revision-0/calculate/scripts/total.py",
                               "tasks/one/practice/revision-0/loader.json"]}
        review = {k:revision[k] for k in ("revision","skills_sha256","outputs_sha256")}
        review.update(assessment="Checked the advertised optional interface against its actual frozen execution",
                      findings=[finding], resolved=[], feedback_files={"list-plan.json":diagnostic})
        relative = "tasks/one/review/skills-0.json"
        save(out / relative, review)
        event = {"action":"skill-review","case_id":"one","record":relative}
        before = executor.run("status", out)
        for change in ({"outputs_sha256":"0"*64}, {"feedback_files":{"../escape":diagnostic}},
                       {"feedback_files":{"source.py":finding["evidence"][1]}}):
            save(out / relative, {**review, **change})
            with self.subTest(change=change), self.assertRaises(ValueError):
                executor.run("event", out, event)
            self.assertEqual(executor.run("status", out), before)
        save(out / relative, review)
        if not unknown:
            clean_record = "tasks/one/review/skills-0-initial.json"
            save(out / clean_record, {**review, "assessment":"Initial output checks passed; no defect identified yet",
                                     "findings":[], "feedback_files":{}})
            executor.run("event", out, {**event,"record":clean_record})
            self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "finish_surrogate_pass")
        executor.run("event", out, event)
        with self.assertRaises(ValueError):
            executor.run("event", out, event)
        guide = executor.run("next", out)["cases"]["one"]
        self.assertFalse(guide["evidence_limited_eligible"])
        feedback = {"action":"feedback","case_id":"one","attempt":1,"issues":guide["latest_issues"],
                    "classification":"SELF-FIXABLE","next_action":"revise_skill",
                    "diagnosis":finding["observation"],"expected_change":finding["validation"],
                    "skill_findings":[finding],"evidence":finding["evidence"]}
        with self.assertRaisesRegex(ValueError, "Unresolved skill findings"):
            executor.run("event", out, {**feedback,"next_action":"finish_evidence_limited"})
        with self.assertRaisesRegex(ValueError, "Unresolved skill findings"):
            executor.run("event", out, {"action":"finish-case","case_id":"one","reason":"surrogate_pass"})
        executor.run("event", out, feedback)
        with self.assertRaisesRegex(ValueError, "before its feedback is sealed"):
            executor.run("event", out, event)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "revise_skill")
        revised = executor.run("creator", out, {"case_id":"one",
            "hypothesis":"Include every row. Repair documented plan forms"})["cases"]["one"]
        self.assertEqual(revised["creator_session_id"], creator)
        self.assertEqual(revised["revisions"][-1]["change_kind"], "revise_skill")
        self.assertNotEqual(revision["skills_sha256"], revised["revisions"][-1]["skills_sha256"])
        self.assertEqual((root / "practice/revision-0/loader.json").read_bytes(), original_output)
        self.assertEqual(json.loads((out / ".executor/one/practice-1/view/finding-evidence/list-plan.json").read_text())["observed"], observed)
        if verification_budget == 1:
            self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "finish_max_refinement_retries")
            count = len(Provider.requests)
            with self.assertRaises(ValueError):
                executor.run("verifier-plan", out, {"case_id":"one"})
            self.assertEqual(len(Provider.requests), count)
            process = {k:revised["revisions"][-1][k] for k in ("skills_sha256","outputs_sha256")}
            process["checks"] = {key:{"status":"passed","finding":"Reusable skill repaired and freshly executed; verification cap retained",
                "evidence":["tasks/one/executions/run-1.log","tasks/one/review/skills-0.json"]}
                for key in ("delivery","portable_content","construction_isolation")}
            save(root / "review/process.json", process)
            closed = executor.run("event", out, {"action":"finish-case","case_id":"one",
                "reason":"max_refinement_retries","process_review":"tasks/one/review/process.json"})["cases"]["one"]
            self.assertFalse(closed["final_was_tested"])
            self.assertEqual(closed["unresolved_skill_findings"], [finding])
            self.assertNotEqual(closed["last_tested_sha256"], closed["final_sha256"])
            return
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "begin_verification")
        Provider.plan_loader_checks = True
        case = self.verify(out)["cases"]["one"]
        self.assertEqual(case["attempts"][-1]["result"]["failed"], 0)
        self.assertEqual(case["attempts"][-1]["result"]["total"], 2)
        self.assertNotEqual(case["attempts"][-1]["verifier_session_id"], creator)
        for name in ("plan-view", "view"):
            view = out / ".executor/one/verify-2" / name
            self.assertTrue(view.is_dir())
            self.assertFalse((view / "skill-review.json").exists())
            self.assertFalse((view / "finding-evidence").exists())
        resolution = {k:case["revisions"][-1][k] for k in ("revision","skills_sha256","outputs_sha256")}
        resolution.update(assessment="Fresh frozen executions and independent count checks confirm both forms",
                          findings=[], resolved=[])
        relative = "tasks/one/review/skills-1.json"
        save(out / relative, resolution)
        event = {"action":"skill-review","case_id":"one","record":relative}
        with self.assertRaisesRegex(ValueError, "Retain or independently resolve"):
            executor.run("event", out, event)
        resolution["resolved"] = [{"id":"list-plan","finding":"Both actual invocations exit zero with correct counts",
                                   "evidence":["tasks/one/verify/attempt-2/report.xml",
                                               "tasks/one/practice/revision-1/loader.json"],
                                   "tests":["suite::fabricated"]}]
        save(out / relative, resolution)
        with self.assertRaisesRegex(ValueError, "actually passed"):
            executor.run("event", out, event)
        resolution["resolved"][0]["tests"] = ["suite::test_plan_forms"]
        save(out / relative, resolution)
        executor.run("event", out, event)
        guide = executor.run("next", out)["cases"]["one"]
        self.assertEqual(guide["skill_changes_after_feedback"], 1)
        self.assertEqual(guide["open_skill_findings"], [])
        self.assertEqual(guide["verification_attempts_remaining"], 1)
        reason = "evidence_limited" if unknown else "surrogate_pass"
        if unknown:
            executor.run("event", out, {**feedback,"attempt":2,"issues":["coverage_gap"],"skill_findings":[],
                "next_action":"finish_evidence_limited","diagnosis":"Contract defect resolved; permission policy remains unknown",
                "expected_change":"Retain unresolved permissions without claiming complete correctness"})
        process = {k:resolution[k] for k in ("skills_sha256","outputs_sha256")}
        process["checks"] = {key:{"status":"passed","finding":"Reviewed real isolated execution and reusable resources",
            "evidence":["tasks/one/executions/run-1.log","tasks/one/review/skills-1.json"]}
            for key in ("delivery","portable_content","construction_isolation")}
        save(root / "review/process.json", process)
        save(root / "close.json", {"reason":reason,"workers_stopped":True,
            "cause":"Documented skill defect resolved with independent regression evidence",
            "unresolved":["permissions"] if unknown else [],"evidence":["tasks/one/review/skills-1.json"]})
        closed = executor.run("event", out, {"action":"finish-case","case_id":"one","reason":reason,
            "record":"tasks/one/close.json","process_review":"tasks/one/review/process.json"})["cases"]["one"]
        self.assertTrue(closed["finished"])
        self.assertTrue(closed["final_was_tested"])
        self.assertEqual(closed["unresolved_skill_findings"], [])
        (out / (diagnostic if unknown else clean_record)).write_text("changed after review")
        count = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            executor.run("creator", out, {"case_id":"one"})
        self.assertEqual(len(Provider.requests), count)

    def test_missing_or_stale_review_does_not_spend_another_attempt_or_call_model(self):
        out, request = self.create_run("command", strict=True)
        executor.run("creator", out, request)
        continuation = self.reviewed_plan(out)
        case = executor.run("status", out)["cases"]["one"]
        verifier = case["attempts"][0]["verifier_session_id"]
        before = len(Provider.requests)
        with self.assertRaises((ValueError, KeyError)):
            executor.run("verifier", out, {"case_id": "one"})
        path = out / continuation["review"]
        original = path.read_bytes()
        data = json.loads(original)
        data["plan_sha256"] = "0" * 64
        save(path, data)
        with self.assertRaisesRegex(ValueError, "bind the exact plan"):
            executor.run("verifier", out, continuation)
        self.assertEqual(len(Provider.requests), before)
        self.assertEqual(len(executor.run("status", out)["cases"]["one"]["attempts"]), 1)
        self.assertFalse((out / "STOP").exists())
        path.write_bytes(original)
        state = executor.run("verifier", out, continuation)
        self.assertEqual(state["cases"]["one"]["attempts"][0]["verifier_session_id"], verifier)

    def test_unsupported_promotion_never_starts_pytest(self):
        out, request = self.create_run("command", strict=True)
        executor.run("creator", out, request)
        Provider.unsupported_oracle = Provider.promote_unsupported = True
        with self.assertRaisesRegex(ValueError, "no valid measurement"):
            self.verify(out)
        self.assertTrue((out / "STOP").exists())
        self.assertFalse((out / ".executor/one/verify-1/results").exists())
        attempt = executor.run("status", out)["cases"]["one"]["attempts"][0]
        self.assertEqual(attempt["execution_status"], "not_started")
        self.assertIn("Unsupported expectation", (Path(attempt["directory"]) / "failure.txt").read_text())

    def test_honest_gap_remains_unverified_after_valid_measurement(self):
        out, request = self.create_run("command", strict=True)
        request["hypothesis"] = "Include every row"
        executor.run("creator", out, request)
        Provider.unsupported_oracle = True
        state = self.verify(out)
        attempt = state["cases"]["one"]["attempts"][0]
        self.assertEqual(attempt["result"]["pass_rate"], 1)
        self.assertFalse(attempt["accepted"])
        self.assertEqual(executor.run("next", out)["cases"]["one"]["latest_issues"], ["coverage_gap"])
        self.assertFalse((out / "STOP").exists())

    def test_empty_search_fallback_repairs_real_skill_and_closes_with_honest_unknowns(self):
        policy = {"version": 1, "max_tool_recoveries": 3, "max_same_error_recoveries": 1,
                  "recovery_seconds": 120, "max_execution_repairs": 1, "max_verifier_repairs": 1}
        out, request = self.create_run("agent", graded=policy)
        initial = executor.run("creator", out, request)["cases"]["one"]
        creator = initial["creator_session_id"]
        Provider.unsupported_oracle = True
        first = self.verify(out)["cases"]["one"]["attempts"][-1]
        self.assertEqual(first["result"]["failed"], 1)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["latest_issues"],
                         ["assertion_failure", "coverage_gap"])
        evidence = ["tasks/one/verify/attempt-1/pytest.log"]
        feedback = {"action": "feedback", "case_id": "one", "attempt": 1,
            "issues": ["assertion_failure", "coverage_gap"], "classification": "NEEDS-DR",
            "next_action": "revise_skill", "diagnosis": "The skill omits the final row; permission policy is unknown",
            "expected_change": "Sum every row, preserving the unresolved policy", "evidence": evidence}
        before = executor.run("status", out)
        with self.assertRaisesRegex(ValueError, "Evidence-limited closure"):
            executor.run("event", out, {**feedback, "next_action": "finish_evidence_limited"})
        self.assertEqual(executor.run("status", out), before)
        executor.run("event", out, feedback)
        fallback = {"action": "research-fallback", "case_id": "one", "attempt": 1,
            "reason": "The public policy search returned no usable source", "unresolved": ["permissions"],
            "planned_change": "Fix the documented row omission using existing arithmetic knowledge",
            "validation": "Regenerated total is compared with all public rows by the independent verifier",
            "evidence": evidence}
        with self.assertRaisesRegex(ValueError, "Fallback needs"):
            executor.run("event", out, fallback)
        executor.run("event", out, {"action": "targeted-search", "case_id": "one",
            "classification": "NEEDS-DR", "query": "public sharing policy"})
        with self.assertRaisesRegex(ValueError, "Fallback needs"):
            executor.run("event", out, fallback)
        save(out / "tasks/one/research/empty.json", {"results": []})
        executor.run("event", out, {"action": "search-result", "case_id": "one", "search": 1,
            "outcome": "unavailable", "summary": "Fixture policy search returned no records",
            "evidence": ["tasks/one/research/empty.json"]})
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "record_research_fallback")
        rationale = out / "tasks/one/fallback-rationale.txt"
        rationale.write_text("The known sum defect can be fixed while permission policy remains unresolved.\n")
        fallback["evidence"] = [*evidence, "tasks/one/research/empty.json", "tasks/one/fallback-rationale.txt"]
        executor.run("event", out, fallback)
        before = executor.run("status", out)
        with self.assertRaisesRegex(ValueError, "Fallback needs"):
            executor.run("event", out, fallback)
        self.assertEqual(executor.run("status", out), before)
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "revise_skill")
        request["hypothesis"] = "Include every row"
        state = executor.run("creator", out, request)
        case = state["cases"]["one"]
        self.assertEqual(case["creator_session_id"], creator)
        self.assertEqual(case["revisions"][-1]["change_kind"], "revise_skill")
        self.assertNotEqual(case["revisions"][0]["skills_sha256"], case["revisions"][1]["skills_sha256"])
        self.assertEqual((out / "tasks/one/practice/revision-0/total.txt").read_text(), "3")
        self.assertEqual((out / "tasks/one/practice/revision-1/total.txt").read_text(), "2")
        staged = out / ".executor/one/practice-1/view/research-fallback.json"
        self.assertEqual(json.loads(staged.read_text())["unresolved"], ["permissions"])
        state = self.verify(out)
        case = state["cases"]["one"]
        self.assertEqual(case["attempts"][-1]["result"]["pass_rate"], 1)
        self.assertFalse(case["attempts"][-1]["accepted"])
        guide = executor.run("next", out)["cases"]["one"]
        self.assertTrue(guide["evidence_limited_eligible"])
        self.assertEqual(guide["research_fallbacks_remaining"], 0)
        self.assertEqual(guide["recovery"]["verifier_repairs"], 1)
        closing = {**feedback, "attempt": 2, "issues": ["coverage_gap"],
                   "evidence": ["tasks/one/verify/attempt-2/pytest.log"]}
        with self.assertRaisesRegex(ValueError, "not an observed skill defect"):
            executor.run("event", out, closing)
        executor.run("event", out, {**closing, "next_action": "finish_evidence_limited",
            "diagnosis": "All supported arithmetic checks pass; no permission rule was retrieved",
            "expected_change": "Retain the final skills with the policy gap explicitly reported"})
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "finish_evidence_limited")
        revision = case["revisions"][-1]
        review = {key: revision[key] for key in ("skills_sha256", "outputs_sha256")}
        review["checks"] = {key: {"status": "passed", "finding": "Actual arithmetic skill applied in isolated practice",
            "evidence": ["tasks/one/executions/run-1.log", "tasks/one/skills/calculate/scripts/total.py"]}
            for key in ("delivery", "portable_content", "construction_isolation")}
        save(out / "tasks/one/review/final.json", review)
        stop = {"reason": "evidence_limited", "workers_stopped": True,
                "cause": "Supported checks pass; no public permission rule is available in the collected evidence",
                "unresolved": ["permissions"], "evidence": closing["evidence"]}
        save(out / "tasks/one/close.json", stop)
        finish = {"action": "finish-case", "case_id": "one", "reason": "evidence_limited",
                  "record": "tasks/one/close.json", "process_review": "tasks/one/review/final.json"}
        save(out / "tasks/one/close.json", {**stop, "unresolved": []})
        with self.assertRaisesRegex(ValueError, "Retain every unresolved"):
            executor.run("event", out, finish)
        save(out / "tasks/one/close.json", stop)
        with self.assertRaises(ValueError):
            executor.run("event", out, {**finish, "reason": "surrogate_pass"})
        state = executor.run("event", out, finish)
        self.assertEqual(state["cases"]["one"]["reason"], "evidence_limited")
        self.assertTrue(state["cases"]["one"]["final_was_tested"])
        self.assertEqual(state["cases"]["one"]["final_verification_issues"], ["coverage_gap"])
        self.assertFalse((out / "STOP").exists())
        shutil.copytree(out / "tasks/one/skills", out / "library/tasks/one")
        (out / "library/SKILL.md").write_text("Read index.md.\n")
        (out / "library/index.md").write_text("Sum rows: tasks/one/calculate/SKILL.md\n")
        original = rationale.read_bytes()
        rationale.write_bytes(original + b"changed")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            executor.run("event", out, {"action": "freeze"})
        rationale.write_bytes(original)
        self.assertEqual(executor.run("event", out, {"action": "freeze"})["phase"], "frozen")
        count = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("event", out, fallback)
        self.assertEqual(len(Provider.requests), count)

    def test_coverage_protocol_error_stops_even_after_passing_pytest(self):
        out, request = self.create_run("command", strict=True)
        request["hypothesis"] = "Include every row"
        executor.run("creator", out, request)
        Provider.unknown_test_mapping = True
        with self.assertRaisesRegex(ValueError, "Verification protocol failed"):
            self.verify(out)
        attempt = executor.run("status", out)["cases"]["one"]["attempts"][-1]
        self.assertEqual(attempt["result"]["pass_rate"], 1)
        self.assertIn("not present in JUnit", attempt["coverage_error"])
        self.assertFalse(attempt["accepted"])
        self.assertEqual(experiment.workflow.issues(attempt), ["verifier_error", "coverage_gap"])
        self.assertTrue((out / "STOP").exists())
        before = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "Stopped"):
            executor.run("verifier-plan", out, {"case_id": "one"})
        self.assertEqual(len(Provider.requests), before)
        for path in (out / ".executor/containers").glob("openskill-*.json"):
            record = json.loads(path.read_text())
            check = subprocess.run([self.config["docker"], "inspect", record["container"]], capture_output=True)
            self.assertNotEqual(check.returncode, 0)

    def test_honest_gap_closes_at_retry_limit_without_inventing_a_pass(self):
        out, request = self.create_run("command", strict=True)
        request["hypothesis"] = "Include every row"
        executor.run("creator", out, request)
        Provider.unsupported_oracle = True
        for number in range(1, 4):
            state = self.verify(out)
            self.assertFalse(state["cases"]["one"]["attempts"][-1]["accepted"])
            self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "record_feedback")
            evidence = [f"tasks/one/verify/attempt-{number}/pytest.log"]
            executor.run("event", out, {"action": "feedback", "case_id": "one", "attempt": number,
                "issues": ["coverage_gap"], "classification": "NEEDS-DR", "next_action": "repair_verifier",
                "diagnosis": "The supplied evidence has no permission policy",
                "expected_change": "Look for independent policy evidence; preserve the gap if absent", "evidence": evidence})
            if number < 3:
                executor.run("event", out, {"action": "targeted-search", "case_id": "one",
                    "classification": "NEEDS-DR", "query": "public permission policy documentation"})
                executor.run("event", out, {"action": "search-result", "case_id": "one", "search": number,
                    "outcome": "retrieved", "summary": "The independent fixture document only covers arithmetic",
                    "sources": ["https://docs.python.org/3/library/functions.html#sum"],
                    "evidence": ["tasks/one/inputs/anchors/anchors.md"]})
                self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "repair_verifier")
        self.assertEqual(executor.run("next", out)["cases"]["one"]["next_action"], "finish_max_refinement_retries")
        before = len(Provider.requests)
        with self.assertRaises(ValueError):
            executor.run("event", out, {"action": "finish-case", "case_id": "one", "reason": "surrogate_pass"})
        revision = state["cases"]["one"]["revisions"][-1]
        review = {key: revision[key] for key in ("skills_sha256", "outputs_sha256")}
        review["checks"] = {key: {"status": "passed", "finding": "Checked public arithmetic artifact and isolated execution",
            "evidence": ["tasks/one/executions/run-0.log", "tasks/one/skills/calculate/SKILL.md"]}
            for key in ("delivery", "portable_content", "construction_isolation")}
        save(out / "tasks/one/review/final.json", review)
        state = executor.run("event", out, {"action": "finish-case", "case_id": "one",
            "reason": "max_refinement_retries", "process_review": "tasks/one/review/final.json"})
        case = state["cases"]["one"]
        self.assertTrue(case["finished"])
        self.assertTrue(case["final_was_tested"])
        self.assertEqual(case["final_sha256"], revision["skills_sha256"])
        self.assertEqual(len(case["attempts"]), 3)
        self.assertEqual(len(case["revisions"]), 1)
        self.assertEqual(len(Provider.requests), before)
        self.assertFalse((out / "STOP").exists())

    def test_changed_plan_source_refuses_continuation(self):
        out, request = self.create_run("command")
        executor.run("creator", out, request)
        continuation = self.reviewed_plan(out)
        (out / ".executor/one/verify-1/plan-view/public/rows.json").write_text("[99]")
        before = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            executor.run("verifier", out, continuation)
        self.assertEqual(len(Provider.requests), before)

    def test_development_replay_never_runs_a_creator_or_exports_a_benchmark_result(self):
        original, _ = self.create_run("command")
        config = executor.run("status", original)["config"]
        candidate = self.base / "total.txt"
        candidate.write_text("2")
        out = self.base / "replay"
        before = len(Provider.requests)
        state = verifier_replay.run("plan", out, {"executor": config["executor"],
            "runtime": config["runtime"]["construction"],
            "public": {"rows.json": str(original / "tasks/one/inputs/public/rows.json")},
            "research": {"anchors.md": str(original / "tasks/one/inputs/anchors/anchors.md")},
            "outputs": {"total.txt": str(candidate)}})
        self.assertEqual(state["status"], "awaiting_review")
        seal = json.loads((out / ".executor/replay/oracle/seal.json").read_text())
        review = {k: seal[k] for k in ("plan_sha256", "inputs_sha256")}
        review.update(reviewer="fixture controller", scope="independent_evidence", decisions=[
            {"id": "sum", "status": "supported", "finding": "Public arithmetic independently gives 2."}])
        save(out / "review.json", review)
        result = verifier_replay.run("verify", out, out / "review.json")
        self.assertEqual(result["result"]["pass_rate"], 1)
        self.assertFalse(result["deployable"])
        self.assertIsNone(result["benchmark_score"])
        self.assertFalse((out / "journal").exists())
        self.assertFalse((out / "library").exists())
        self.assertEqual(candidate.read_text(), "2")
        for call in Provider.requests[before:]:
            self.assertNotIn("Fixed skill names:", json.dumps(call["messages"]))
        count = len(Provider.requests)
        with self.assertRaisesRegex(ValueError, "No journal"):
            executor.run("event", out, {"action": "freeze"})
        with self.assertRaises(ValueError):
            verifier_replay.run("verify", out, out / "review.json")
        self.assertEqual(len(Provider.requests), count)

    def create_run(self, mode, strict=False, graded=None, feedback_policy="bounded-evidence-v1", verification_budget=3):
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
                  "max_refinement_retries": verification_budget,
                  "runtime": {r: {"provider": "test", "model_id": "test", "thinking_level": "medium"}
                              for r in ("construction", "target")}, "execution_mode": executor.MODE,
                  "executor": {**self.config, "sanitized_image": True, "sdk": str(sdk),
                               "penguin_home": str(home), "project_id": "test", "practice_mode": mode}}
        if graded is not None:
            config["recovery_policy"] = graded
        if feedback_policy is not None:
            config["feedback_policy"] = feedback_policy
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

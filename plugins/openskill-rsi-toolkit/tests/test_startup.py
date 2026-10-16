"""Real container startup regressions; no paid model or benchmark scoring.

Given a private taskenv service, readiness requires its API while role access stays denied.
Given a service startup failure, its diagnostic survives cleanup and no role is launched.
Given an unhealthy service or enabled judge, batch initialization stops without a journal.
Given a role using the service identity, startup refuses it before exposing private data.
Given cancellation during startup, the container is removed and no ready result appears.
Given SIGTERM during inspect, log collection or removal, cleanup finishes before cancellation propagates.
Given a service exiting between log snapshots, its final Docker log is collected before removal.
Given a noisy or stuck diagnostic command, collection is bounded in bytes and time.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"))
import executor
from isolation import Boundary, Interrupted, capture

IMAGE = os.environ.get("OPENSKILL_TEST_IMAGE")
SERVICE = '''import os,sys
from http.server import HTTPServer,BaseHTTPRequestHandler
assert os.getuid()!=0
mode=sys.argv[1]
if mode=='exit':
    print('SERVICE-START-FAILURE',flush=True)
    sys.exit(23)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503 if mode in ('unhealthy','cancel') else 200);self.end_headers()
        if mode=='cancel':
            from pathlib import Path
            for work in Path('/tmp').glob('openskill-startup-test-*/work'):
                (work/'STOP').touch()
    def do_POST(self):
        self.send_response(200 if mode=='judge' else 404);self.end_headers()
HTTPServer(('127.0.0.1',9003),Handler).serve_forever()
'''


class CaptureTest(unittest.TestCase):
    def test_noisy_diagnostic_is_truncated(self):
        result = capture([sys.executable, "-c", "import sys;sys.stdout.write('x'*1000000)"], limit=1024)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["stdout"]), 1024)

    def test_stuck_diagnostic_times_out(self):
        result = capture([sys.executable, "-c", "import signal;signal.pause()"], timeout=0.05)
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["exit_code"], 0)


@unittest.skipUnless(IMAGE, "Set OPENSKILL_TEST_IMAGE to a reviewed GDPevo image for service regressions")
class StartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="openskill-startup-fixture-")
        root = Path(cls.build.name)
        (root / "service.py").write_text(SERVICE)
        cls.base_tag = "openskill-startup-test-base:" + uuid.uuid4().hex
        subprocess.run(["docker", "tag", IMAGE, cls.base_tag], check=True, capture_output=True)
        (root / "Dockerfile").write_text(
            f"FROM {cls.base_tag}\nUSER root\nCOPY service.py /opt/gdpevo/env/fixture.py\n"
            "ARG MODE\nENV GDPEVO_START_CMD=\"python3 fixture.py ${MODE}\"\n"
            "ENV GDPEVO_PORT=9003 GDPEVO_HEALTH_PATH=/health GDPEVO_ENV_DIR=/opt/gdpevo/env\n")
        cls.images = {}
        for mode in ("ready", "exit", "unhealthy", "judge", "cancel"):
            built = subprocess.run(["docker", "build", "-q", "--build-arg", "MODE=" + mode, str(root)],
                                   capture_output=True, text=True)
            if built.returncode:
                raise RuntimeError(built.stderr)
            cls.images[mode] = built.stdout.strip().splitlines()[-1]

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "image", "rm", *cls.images.values()], capture_output=True, check=True)
        subprocess.run(["docker", "image", "rm", cls.base_tag], capture_output=True, check=True)
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="openskill-startup-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.config = {"image": self.images["ready"], "docker": shutil.which("docker"),
                       "node": shutil.which("node"), "uid": os.getuid(), "gid": os.getgid(),
                       "startup_profile": "gdpevo", "startup_timeout_seconds": 2}

    def boundary(self):
        return Boundary(self.config, self.root / "containers", self.work, [],
                        (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(), self.root / "STOP")

    def assert_removed(self, boundary):
        result = subprocess.run([self.config["docker"], "inspect", boundary.name], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_service_ready_without_private_access(self):
        boundary = self.boundary()
        with boundary:
            receipt = boundary.run(["python3", "-c", "import urllib.request;from pathlib import Path;"
                "assert urllib.request.urlopen('http://127.0.0.1:9003/health').status==200;"
                "Path('answer.txt').write_text('own output')"], self.root / "practice.log")
            self.assertEqual(receipt["exit_code"], 0)
            result = subprocess.run(boundary.exec_argv(["cat", "/opt/gdpevo/env/fixture.py"]), capture_output=True)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.work / "answer.txt").read_text(), "own output")
        self.assert_removed(boundary)

    def test_service_failure_preserves_private_log_before_cleanup(self):
        self.config["image"] = self.images["exit"]
        boundary = self.boundary()
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            with boundary:
                self.fail("Failed service accepted")
        diagnostic = json.loads((self.root / "containers/diagnostics" / (boundary.name + ".json")).read_text())
        self.assertIn("SERVICE-START-FAILURE", json.dumps(diagnostic))
        self.assert_removed(boundary)

    def test_batch_stops_at_unhealthy_image_without_starting_a_journal(self):
        config = {"execution_mode": executor.MODE, "case_ids": ["one", "two", "three"],
                  "executor": {**self.config, "sanitized_image": True,
                               "case_images": {"two": self.images["unhealthy"]}}}
        out = self.root / "batch"
        with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
            executor.run("preflight", out, config)
        report = json.loads((out / "preflight.json").read_text())
        self.assertEqual([(r["case_id"], r["status"]) for r in report["cases"]], [("one", "ready"), ("two", "failed")])
        self.assertTrue((out / "STOP").exists())
        self.assertFalse((out / "journal").exists())
        self.assertFalse((out / ".executor/preflight/three").exists())
        for row in report["cases"]:
            record = json.loads((out / row["container_record"]).read_text())
            self.assertEqual(record["status"], "stopped")
        with self.assertRaisesRegex(ValueError, "fresh directory"):
            executor.run("preflight", out, config)

    def test_enabled_judge_is_refused(self):
        self.config["image"] = self.images["judge"]
        boundary = self.boundary()
        with self.assertRaisesRegex(ValueError, "judge must be unavailable"):
            with boundary:
                self.fail("Enabled judge accepted")
        self.assert_removed(boundary)

    def test_service_identity_cannot_be_used_by_a_role(self):
        # Obtain the image account, rather than assuming a distro's assigned uid.
        result = subprocess.run(["docker", "run", "--rm", "--network", "none", "--entrypoint", "id",
                                 self.images["ready"], "-u", "taskenv"], check=True, text=True, capture_output=True)
        self.config["uid"] = int(result.stdout)
        # Work must be writable so the identity check, rather than a mount failure, rejects this role.
        self.work.chmod(0o777)
        boundary = self.boundary()
        with self.assertRaisesRegex(ValueError, "identity overlaps"):
            with boundary:
                self.fail("Service identity accepted")
        self.assert_removed(boundary)

    def test_cancellation_during_startup_removes_container(self):
        self.config["image"] = self.images["cancel"]
        self.work.chmod(0o777)
        boundary = self.boundary()
        boundary.stop = self.work / "STOP"
        with self.assertRaises(Interrupted):
            with boundary:
                self.fail("Cancelled service accepted")
        record = json.loads(boundary.record.read_text())
        self.assertNotIn("ready_at", record)
        self.assert_removed(boundary)

    def test_sigterm_during_cleanup_still_removes_container_and_allows_stop(self):
        self.cancel_during("logs")

    def test_sigterm_during_cleanup_inspect_still_removes_container(self):
        self.cancel_during("inspect")

    def test_sigterm_during_removal_preserves_confirmed_cleanup(self):
        self.cancel_during("rm")

    def cancel_during(self, phase):
        wrapper = self.root / "docker"
        # Fake only the Docker executable edge: deliver a real signal when its log
        # command starts. All container operations still use the real daemon.
        wrapper.write_text("#!/usr/bin/env python3\nimport os,signal,sys\nfrom pathlib import Path\n"
                           f"marker=Path({str(self.root / 'signal-sent')!r})\n"
                           f"if sys.argv[1]=={phase!r} and (sys.argv[1]!='inspect' or len(sys.argv)==3) and not marker.exists():\n"
                           " marker.touch();os.kill(os.getppid(),signal.SIGTERM)\n"
                           f"os.execv({self.config['docker']!r},[{self.config['docker']!r},*sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        config = {"execution_mode": executor.MODE, "case_ids": ["one", "two"],
                  "executor": {**self.config, "docker": str(wrapper), "sanitized_image": True}}
        (self.root / "config.json").write_text(json.dumps(config))
        out = self.root / "cancel-check"
        result = subprocess.run([sys.executable, "-B", executor.__file__, "preflight", str(out),
                                 str(self.root / "config.json")], text=True, capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / "signal-sent").exists())
        report = json.loads((out / "preflight.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(report["cases"]), 1)
        record = json.loads((out / report["cases"][0]["container_record"]).read_text())
        self.assertEqual(record["status"], "stopped")
        check = subprocess.run([self.config["docker"], "inspect", record["container"]], capture_output=True)
        self.assertNotEqual(check.returncode, 0)
        self.assertTrue(executor.run("stop", out)["stopped"])

    def test_service_exit_between_snapshots_preserves_final_log(self):
        wrapper = self.root / "docker"
        # At the Docker edge, terminate the service just before the private-log
        # exec and wait for its supervisor to exit, reproducing the removal race.
        wrapper.write_text("#!/usr/bin/env python3\nimport os,subprocess,sys\n"
            f"docker={self.config['docker']!r}\n"
            "if sys.argv[1]=='exec' and sys.argv[-1]=='logs':\n"
            " name=sys.argv[4]\n"
            " code=\"import os,signal;from pathlib import Path;Path('/opt/gdpevo/log/service.log').open('a').write('FINAL-SERVICE-FAILURE\\\\n');p=Path('/proc/1/task/1/children').read_text().split();os.kill(int(p[0]),signal.SIGKILL)\"\n"
            " subprocess.run([docker,'exec','--user','taskenv',name,'python3','-c',code],check=True)\n"
            " subprocess.run([docker,'wait',name],check=True,stdout=subprocess.DEVNULL)\n"
            "os.execv(docker,[docker,*sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        self.config["docker"] = str(wrapper)
        boundary = self.boundary()
        with boundary:
            pass
        diagnostic = json.loads((self.root / "containers/diagnostics" / (boundary.name + ".json")).read_text())
        self.assertIn("FINAL-SERVICE-FAILURE", diagnostic["container_logs_recheck"]["stdout"])
        state = json.loads(diagnostic["state_recheck"]["stdout"])
        self.assertFalse(state["Running"])
        self.assertNotEqual(state["ExitCode"], 0)
        self.assert_removed(boundary)


if __name__ == "__main__":
    unittest.main()

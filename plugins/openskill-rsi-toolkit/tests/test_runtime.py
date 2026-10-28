"""Runtime deployment regressions, using the real Node loader and Penguin SDK.

Given an incomplete SDK, init stops before Docker, a journal or a model request.
Given an incompatible SDK interface, init refuses it before constructing any Case.
Given a valid configured SDK, the no-turn Session probe succeeds and removes its Agent.
Given an unknown model, the probe stops without disclosing credentials or leaving an Agent.
Given changed SDK bytes, a previously checked runtime cannot silently continue.
Given a bad archive checksum, an escaping member or an existing destination, deployment refuses it.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import executor
from runtime import check_runtime
from prepare_runtime import prepare

SDK = Path(os.environ.get("OPENSKILL_TEST_SDK", SCRIPTS.parents[4] / "packages/core/dist/index.js"))


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "data"
        self.project = self.home / "test"
        self.project.mkdir(parents=True)
        self.out = self.base / "experiment"
        self.node = shutil.which("node")
        self.config = {"execution_mode": "isolated-v1", "case_ids": ["one"],
            "runtime": {"construction": {"provider": "test", "model_id": "test", "thinking_level": "medium"}},
            "executor": {"sdk": str(SDK), "node": self.node, "docker": shutil.which("false"),
                         "penguin_home": str(self.home), "project_id": "test", "sanitized_image": True}}
        (self.project / ".project_config.toml").write_text("version = 1\n")

    def configure_model(self):
        code = ("import {saveProjectConfig} from " + json.dumps(SDK.as_uri()) + ";"
            "await saveProjectConfig(process.argv[1], 'test', {version:1,models:[{provider:'test',model_id:'test',"
            "client_type:'openai-chat',api_key:'fixture-must-not-leak',base_url:'http://127.0.0.1:9/v1',context_window:131072}]});")
        subprocess.run([self.node, "--input-type=module", "-e", code, str(self.home)], check=True, capture_output=True)

    def test_incomplete_sdk_fails_before_docker_or_journal(self):
        broken = self.base / "broken"
        broken.mkdir()
        entry = broken / "index.mjs"
        entry.write_bytes(SDK.read_bytes())
        self.config["executor"]["sdk"] = str(entry)
        with self.assertRaisesRegex(ValueError, "Runtime preflight failed"):
            executor.run("init", self.out, self.config)
        report = json.loads((self.out / "preflight.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["cases"], [])
        self.assertFalse((self.out / "journal").exists())
        self.assertTrue((self.out / "STOP").exists())
        probe = json.loads(next((self.out / ".executor/runtime").glob("*/report.json")).read_text())
        self.assertEqual(probe["error_code"], "ERR_MODULE_NOT_FOUND")
        self.assertEqual(probe["model_requests"], 0)

    def test_incompatible_exports_refused_before_construction(self):
        entry = self.base / "wrong.mjs"
        entry.write_text("export const unrelated = 1;\n")
        self.config["executor"]["sdk"] = str(entry)
        with self.assertRaisesRegex(ValueError, "SDK export unavailable"):
            executor.run("init", self.out, self.config)
        self.assertFalse((self.out / "journal").exists())

    def test_configured_sdk_creates_and_disposes_without_model_request(self):
        self.configure_model()
        result = check_runtime(self.out, self.config, session=True)
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["session"]["created"] and result["session"]["disposed"])
        self.assertFalse(result["session"]["resume_checked"])
        self.assertEqual(result["model_requests"], 0)
        self.assertEqual(list((self.project / "agents").iterdir()), [])

    def test_unknown_model_stops_without_credentials_or_agents(self):
        self.configure_model()
        self.config["runtime"]["construction"]["model_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "configuration check failed"):
            executor.run("init", self.out, self.config)
        self.assertFalse((self.out / "journal").exists())
        self.assertEqual(list((self.project / "agents").iterdir()), [])
        for file in self.out.rglob("*"):
            if file.is_file(): self.assertNotIn("fixture-must-not-leak", file.read_text())

    def test_replaced_sdk_invalidates_previous_runtime_check(self):
        copied = self.base / "core"
        shutil.copytree(SDK.parent, copied / "dist")
        shutil.copy2(SDK.parent.parent / "package.json", copied / "package.json")
        (copied / "node_modules").symlink_to(SDK.parent.parent / "node_modules", target_is_directory=True)
        entry = copied / "dist/index.js"
        self.config["executor"]["sdk"] = str(entry)
        first = check_runtime(self.out, self.config)
        with entry.open("a") as stream: stream.write("\n// changed deployment\n")
        with self.assertRaisesRegex(ValueError, "Runtime changed"):
            check_runtime(self.out, self.config, expected=first["fingerprint"])

    def test_unsafe_or_mismatched_source_never_builds(self):
        archive = self.base / "source.tar"
        with tarfile.open(archive, "w") as tar:
            header = tarfile.TarInfo("../outside")
            header.size = 1
            tar.addfile(header, io.BytesIO(b"x"))
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            prepare(archive, self.base / "bad-checksum", "a" * 40, "0" * 64, Path(self.node), Path("/missing-pnpm"))
        self.assertFalse((self.base / "bad-checksum").exists())
        with self.assertRaisesRegex(ValueError, "forbidden member"):
            prepare(archive, self.base / "bad-member", "a" * 40, checksum, Path(self.node), Path("/missing-pnpm"))
        self.assertFalse((self.base / "bad-member/outside").exists())
        with self.assertRaises(FileExistsError):
            prepare(archive, self.base / "bad-member", "a" * 40, checksum, Path(self.node), Path("/missing-pnpm"))


if __name__ == "__main__":
    unittest.main()

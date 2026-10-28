"""Given a compiled export, install its exact bytes into a fresh native State;
then freeze/restore it without learning records or changes to the common config.
Given stale bytes or a conflicting State, refuse before writing new methods.
Given a real grader reply, keep its complete feedback and reuse the receipt;
transport failure or interruption must never become zero or trigger a new call.
All grading responses below are synthetic, with HTTP faked at its boundary.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import evo
import feedback
from state import install_package
from test_evo import batch, entry


class StateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "agent_state"
        self.state.mkdir()
        (self.state / "system_config.yaml").write_text("version: 2\nskills:\n  enabled: false\n")
        (self.state / "AGENTS.md").write_text("COMMON_BASE_INSTRUCTIONS")

    def test_compilation_export_install_and_archive_restore_keep_the_frozen_context(self):
        library = evo.compile_batch(batch())["library"] + [entry("general", "general")]
        receipt = evo.export({"library": library, "topic": "orders"}, self.root / "export")
        # The native training verifier requires a nonempty root SKILL.md.
        self.assertTrue((self.root / "export/SKILL.md").read_text().strip())
        config = (self.state / "system_config.yaml").read_bytes()
        installed = install_package(receipt, self.state)
        self.assertEqual((self.state / "system_config.yaml").read_bytes(), config)
        self.assertEqual((self.state / "AGENTS.md").read_text().count(receipt["context"]), 1)
        self.assertTrue((self.state / "AGENTS.md").read_text().startswith("COMMON_BASE_INSTRUCTIONS\n\n"))
        self.assertNotIn("PRIVATE_GENERAL_BODY", (self.state / "AGENTS.md").read_text())
        frozen = self.root / "frozen.tar.gz"
        with tarfile.open(frozen, "w:gz") as archive:
            for path in sorted(self.state.iterdir()):
                archive.add(path, arcname=path.name)
        restored = self.root / "restored"
        with tarfile.open(frozen) as archive:
            self.assertIn("system_config.yaml", archive.getnames())
            self.assertNotIn("agent_state/system_config.yaml", archive.getnames())
            archive.extractall(restored)
        self.assertEqual((restored / "AGENTS.md").read_bytes(), (self.state / "AGENTS.md").read_bytes())
        for name, digest in installed["installed"].items():
            self.assertEqual(hashlib.sha256((restored / name).read_bytes()).hexdigest(), digest)
        self.assertFalse((restored / "training-request.json").exists())

    def test_noop_library_exports_a_valid_reader_and_install_is_idempotent(self):
        receipt = evo.export({"library": [], "topic": "orders"}, self.root / "empty")
        install_package(receipt, self.state)
        original = (self.state / "AGENTS.md").read_bytes()
        install_package(receipt, self.state)
        self.assertEqual((self.state / "AGENTS.md").read_bytes(), original)
        self.assertTrue((self.state / "skills/evo-reader/SKILL.md").read_text().strip())
        self.assertEqual(json.loads((self.state / "skills/evo-reader/manifest.json").read_text())["entries"], [])

    def test_changed_export_or_context_is_refused_before_native_state_changes(self):
        receipt = evo.export({"library": [entry()], "topic": "orders"}, self.root / "export")
        before = (self.state / "AGENTS.md").read_bytes()
        for kind in ("file", "context", "topic", "path", "extra"):
            with self.subTest(kind=kind):
                request = copy.deepcopy(receipt)
                if kind == "file":
                    request["sha256"]["SKILL.md"] = "0" * 64
                elif kind == "context":
                    request["context"] += "UNFROZEN_RULE"
                elif kind == "topic":
                    request["topic"] = "other"
                elif kind == "extra":
                    (Path(request["directory"]) / "unfrozen.txt").write_text("PRIVATE_UNFROZEN_MATERIAL")
                else:
                    request["sha256"]["../outside"] = "0" * 64
                with self.assertRaises(ValueError):
                    install_package(request, self.state)
                self.assertEqual((self.state / "AGENTS.md").read_bytes(), before)
                self.assertFalse((self.state / "skills").exists())
                if kind == "extra":
                    (Path(request["directory"]) / "unfrozen.txt").unlink()

    def test_a_stale_native_skill_slot_cannot_be_silently_replaced(self):
        receipt = evo.export({"library": [entry()], "topic": "orders"}, self.root / "export")
        old = self.state / "skills/evo-reader/SKILL.md"
        old.parent.mkdir(parents=True)
        old.write_text("OLDER_FROZEN_SKILL")
        with self.assertRaisesRegex(ValueError, "different content"):
            install_package(receipt, self.state)
        self.assertEqual(old.read_text(), "OLDER_FROZEN_SKILL")
        self.assertEqual((self.state / "AGENTS.md").read_text(), "COMMON_BASE_INSTRUCTIONS")


class FeedbackHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        answer = self.root / "answer.json"
        answer.write_text('{"synthetic": true}')
        self.request = {"task_id": "train_001", "train_ids": ["train_001"],
                        "url": "http://127.0.0.1:9024/api/judge", "answer": str(answer),
                        "feedback_dir": str(self.root / "feedback")}

    def test_one_http_grade_retains_complete_feedback_and_reuses_the_same_receipt(self):
        raw = '{"score": 0.5, "correct": false, "detail": "AUTHORIZED_FEEDBACK"}'
        with patch("feedback.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status, response.read.return_value = 200, raw.encode()
            result = feedback.grade(self.request)
            again = feedback.grade(self.request)
            self.assertEqual(opener.return_value.open.call_count, 1)
            call = opener.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(call.data), {"task_id": "train_001", "answer": {"synthetic": True}})
        self.assertEqual(result, again)
        self.assertEqual(result["raw_response"], raw)
        self.assertEqual(result["score"], 0.5)
        self.assertFalse(result["correct"])
        self.assertEqual(result["status"], "ok")

    def test_transport_failure_is_recorded_without_score_or_retry(self):
        with patch("feedback.build_opener") as opener:
            opener.return_value.open.side_effect = OSError("synthetic transport failure")
            result = feedback.grade(self.request)
            again = feedback.grade(self.request)
            self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertEqual(result, again)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["score"])

    def test_pending_interrupted_calls_and_answer_edits_are_not_rescored(self):
        directory = Path(self.request["feedback_dir"])
        directory.mkdir()
        pending = directory / "train_001.pending.json"
        pending.write_text("{}")
        with patch("feedback.build_opener") as opener:
            with self.assertRaises(FileExistsError):
                feedback.grade(self.request)
            opener.assert_not_called()
        pending.unlink()
        with patch("feedback.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status, response.read.return_value = 200, b'{"score": 1, "correct": true}'
            feedback.grade(self.request)
        Path(self.request["answer"]).write_text('{"edited": true}')
        with patch("feedback.build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "identity changed"):
                feedback.grade(self.request)
            opener.assert_not_called()

    def test_heldout_tasks_and_foreign_feedback_hosts_are_rejected_without_http(self):
        for field, value in (("task_id", "test_001"), ("url", "http://example.invalid/api/judge")):
            with self.subTest(field=field), patch("feedback.build_opener") as opener:
                with self.assertRaises(ValueError):
                    feedback.grade(self.request | {field: value})
                opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()

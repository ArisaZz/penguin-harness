"""Native package binding scenarios; no network, Docker or model requests.

Given a published Workspace package, inspect/stage exposes only public statement files.
Given a moving Harbor ref, staging requires one pinned checkout and retains the real task path.
Given a grouped GDPevo Train package, public questions are staged and only paired Test ids are read.
Given absent pairing, traversal, links, private input trees or a mismatched source, no binding is published.
Given changed evaluation settings, executor initialization refuses the native binding.
Given an existing binding, staging cannot overwrite its evidence.
Given changed public inputs or package metadata, initialization and later verification refuse them.
Given a manifest run count, the default plan repeats evaluation three times without duplicating construction.
Given an explicit repetition count, the bound plan and later reads retain it.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import native_benchmark as native
import experiment


class NativeBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.scratch = self.project / "agents/controller/scratchpad/session-test"
        self.scratch.mkdir(parents=True)
        self.revision = "a" * 40
        self.checkout = self.root / ("benchmark-" + self.revision)
        self.checkout.mkdir()
        (self.checkout / ".penguin-ready").touch()

    def package(self, name, case, statement, runs=2):
        root = self.project / "benchmarks" / name
        (root / case / "statement").mkdir(parents=True)
        (root / "benchmark_config.toml").write_text(f'id = "{name}"\nstatus = "published"\nruns = {runs}\n')
        (root / case / "statement/README.md").write_text(statement)
        # Invalid UTF-8 is a canary: accidentally reading private text would fail the test.
        (root / case / "rubric").mkdir()
        (root / case / "rubric/README.md").write_bytes(b"\xffPRIVATE_SCORING")
        (root / "scoreboard.yaml").write_bytes(b"\xffPRIVATE_SCORE")
        return root

    def statement(self, task="train_tasks", directory="benchmarks/gdpevo-crm/tasks", ref="feature/new-layout"):
        return (f"# Public package statement\n- Task: `{task}` in "
                f"https://github.com/example/tasks/tree/{ref}/{directory}/{task}\n"
                "## How this case is run\nHarbor:\n```bash\n"
                f"uvx --from harbor==0.23.0 harbor run -p {directory} -i {task} \\\n"
                "-a penguin_agent:PenguinAgent -m <provider>/<model_id> \\\n"
                "--allow-agent-host <model provider API host> -k 1 -n 1\n```\n")

    def grouped(self):
        name = "penguinharness-benchmark-gdpevo-crm-train"
        case = "CASE-001-train_tasks"
        self.package(name, case, self.statement())
        test = self.package(name[:-6] + "-test", "CASE-001-crm-test-001", "held-out")
        (test / "CASE-001-crm-test-001/statement/README.md").write_bytes(b"\xffHELD_OUT_QUESTION")
        task = self.checkout / "benchmarks/gdpevo-crm/tasks/train_tasks"
        workspace = task / "environment/workspace/train_tasks"
        for q in ["train_001", "train_002"]:
            root = workspace / q
            (root / "input/payloads").mkdir(parents=True)
            (root / "instruction.md").write_text("Compute the public sum")
            (root / "input/payloads/answer_template.json").write_text('{"sum":null}')
            (root / "input/prompt.txt").write_text("1 + 2")
        (task / "task.toml").write_text('[metadata]\nsplit="train"\ntask_group="task_group_003"\n')
        (task / "instruction.md").write_text("Use /api/judge for TARGET_FEEDBACK")
        (task / "solution").mkdir()
        (task / "solution/answers.json").write_bytes(b"\xffGOLD_ANSWER")
        (task.parent / "env").mkdir()
        return name, case, task

    def test_workspace_stages_public_inputs_without_a_checkout(self):
        root = self.package("local", "CASE-001", "Answer the question")
        (root / "CASE-001/statement/task.md").write_text("Additional task details")
        result = native.stage(self.project, "local", None, None, self.scratch / "binding")
        self.assertEqual(result["protocol"], "same-task")
        self.assertIsNone(result["source_pin"])
        public = Path(result["cases"][0]["public_directory"])
        self.assertEqual((public / "README.md").read_text(), "Answer the question")
        self.assertEqual((public / "task.md").read_text(), "Additional task details")
        self.assertEqual(set(result["cases"][0]["public_sha256"]), {"task.md", "README.md"})

    def test_test_repetitions_do_not_multiply_construction_or_rewrite_manifest(self):
        root = self.package("local", "CASE-001", "Answer the question", runs=1)
        before = (root / "benchmark_config.toml").read_bytes()
        binding = native.stage(self.project, "local", None, None, self.scratch / "binding")
        runtime = {"provider": "test", "model_id": "test", "thinking_level": "max"}
        state = experiment.initialize({**binding["config"], "benchmark_binding": binding,
                                       "test_agent_id": "target",
                                       "runtime": {"construction": runtime, "target": runtime}})
        self.assertEqual(state["config"]["case_ids"], ["CASE-001"])
        self.assertEqual({(p["variant"], p["run"]) for p in experiment.evaluation_plan(state)},
                         {(v, r) for v in ("baseline", "final") for r in (1, 2, 3)})
        self.assertEqual((root / "benchmark_config.toml").read_bytes(), before)
        self.assertTrue(native.verify(binding)["verified"])

    def test_explicit_single_repetition_survives_binding_verification(self):
        self.package("local", "CASE-001", "Answer the question", runs=7)
        binding = native.stage(self.project, "local", None, None, self.scratch / "binding", runs=1)
        runtime = {"provider": "test", "model_id": "test", "thinking_level": "max"}
        state = experiment.initialize({**binding["config"], "benchmark_binding": binding,
                                       "test_agent_id": "target",
                                       "runtime": {"construction": runtime, "target": runtime}})
        self.assertEqual({(p["variant"], p["run"]) for p in experiment.evaluation_plan(state)},
                         {("baseline", 1), ("final", 1)})
        self.assertTrue(native.verify(binding)["verified"])

    def test_domain_pair_keeps_group_identity_and_excludes_judge_and_test_content(self):
        name, case, task = self.grouped()
        result = native.stage(self.project, name, self.checkout, self.revision, self.scratch / "binding", runs=3)
        self.assertEqual(result["config"]["case_ids"], [case])
        self.assertEqual(result["config"]["test_case_ids"], ["CASE-001-crm-test-001"])
        self.assertEqual(result["runs"], 3)
        item = result["cases"][0]
        self.assertEqual(item["question_count"], 2)
        self.assertEqual(item["outputs"], ["answers/train_001.json", "answers/train_002.json"])
        self.assertEqual(item["environment"]["shared_env"], str(task.parent / "env"))
        self.assertEqual(item["harbor"]["ref"], "feature/new-layout")
        public = Path(item["public_directory"])
        for path in public.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"TARGET_FEEDBACK", path.read_bytes())
                self.assertNotIn(b"GOLD_ANSWER", path.read_bytes())
        self.assertNotIn("rubric", json.dumps(item["public_sha256"]))
        self.assertEqual(result["source_pin"]["commit"], self.revision)

    def test_missing_domain_pair_cannot_fall_back_to_train_scoring(self):
        self.package("penguinharness-benchmark-gdpevo-crm-train", "CASE-001-train_tasks", self.statement())
        with self.assertRaises(FileNotFoundError):
            native.inspect(self.project, "penguinharness-benchmark-gdpevo-crm-train")
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_held_out_package_cannot_be_used_as_construction(self):
        name, _, _ = self.grouped()
        with self.assertRaisesRegex(ValueError, "paired GDPevo Train"):
            native.inspect(self.project, name[:-6] + "-test")

    def test_explicit_held_out_subset_does_not_open_test_statements(self):
        name, _, _ = self.grouped()
        test = self.project / "benchmarks" / (name[:-6] + "-test")
        (test / "CASE-002-crm-test-002").mkdir()
        chosen = ["CASE-002-crm-test-002"]
        binding = native.stage(self.project, name, self.checkout, self.revision,
                               self.scratch / "binding", test_case_ids=chosen)
        self.assertEqual(binding["config"]["test_case_ids"], chosen)
        self.assertTrue(native.verify(binding)["verified"])
        with self.assertRaisesRegex(ValueError, "held-out Case selection"):
            native.inspect(self.project, name, test_case_ids=["CASE-missing"])

    def test_ref_and_launch_must_identify_the_same_safe_task(self):
        for statement in [self.statement().replace("-i train_tasks", "-i other"),
                          self.statement(directory="../outside"),
                          self.statement().replace("-k 1", "--extra-docker-compose tools/shared.yaml -k 1")]:
            with self.subTest(statement=statement):
                with self.assertRaises(ValueError):
                    native.harbor_case(statement, "CASE-001-train_tasks")

    def test_explicit_commit_mismatch_refuses_staging(self):
        self.package("harbor", "CASE-001-task", self.statement(task="task", ref="b" * 40))
        out = self.scratch / "binding"
        with self.assertRaisesRegex(ValueError, "another commit"):
            native.stage(self.project, "harbor", self.checkout, self.revision, out)
        self.assertFalse(out.exists())

    def test_manifest_and_public_symlinks_are_rejected_before_staging(self):
        root = self.package("local", "CASE-001", "Public")
        (root / "CASE-001/statement/secret.txt").symlink_to(root / "scoreboard.yaml")
        out = self.scratch / "binding"
        with self.assertRaisesRegex(ValueError, "Symlink"):
            native.stage(self.project, "local", None, None, out)
        self.assertFalse(out.exists())
        with self.assertRaises(ValueError):
            native.inspect(self.project, "../local")

    def test_private_subtree_cannot_be_promoted_to_public_inputs(self):
        name, _, task = self.grouped()
        private = task / "environment/workspace/train_tasks/train_001/input/solution"
        private.mkdir()
        (private / "answer.json").write_text('{"gold":true}')
        out = self.scratch / "binding"
        with self.assertRaisesRegex(ValueError, "Private material"):
            native.stage(self.project, name, self.checkout, self.revision, out)
        self.assertFalse(out.exists())

    def test_staging_requires_scratchpad_and_cannot_overwrite(self):
        self.package("local", "CASE-001", "Public")
        with self.assertRaises(ValueError):
            native.stage(self.project, "local", None, None, self.project / "benchmarks/new")
        out = self.scratch / "binding"
        native.stage(self.project, "local", None, None, out)
        before = (out / "binding.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            native.stage(self.project, "local", None, None, out)
        self.assertEqual((out / "binding.json").read_bytes(), before)

    def test_executor_refuses_settings_that_change_the_bound_evaluation(self):
        name, _, _ = self.grouped()
        binding = native.stage(self.project, name, self.checkout, self.revision, self.scratch / "binding")
        runtime = {"provider": "test", "model_id": "test", "thinking_level": "max"}
        config = {**binding["config"], "benchmark_binding": binding, "test_agent_id": "target",
                  "runtime": {"construction": runtime, "target": runtime}}
        self.assertEqual(experiment.initialize(config)["phase"], "construction")
        for patch in [{"runs": 9}, {"test_benchmark_id": None}, {"case_ids": ["other"]}, {"test_case_ids": ["other"]}]:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    experiment.initialize({**config, **patch})

    def test_changed_public_inputs_cannot_be_used_under_a_stale_binding(self):
        self.package("local", "CASE-001", "Original instruction")
        binding = native.stage(self.project, "local", None, None, self.scratch / "binding")
        (Path(binding["cases"][0]["public_directory"]) / "README.md").write_text("Different task")
        with self.assertRaisesRegex(ValueError, "Staged public inputs changed"):
            native.verify(binding)

    def test_changed_case_statement_or_manifest_invalidates_comparison(self):
        root = self.package("local", "CASE-001", "Original instruction")
        binding = native.stage(self.project, "local", None, None, self.scratch / "binding")
        statement = root / "CASE-001/statement/README.md"
        statement.write_text("Different instruction")
        with self.assertRaisesRegex(ValueError, "statement changed"):
            native.verify(binding)
        statement.write_text("Original instruction")
        (root / "benchmark_config.toml").write_text('id="local"\nstatus="published"\nruns=7\n')
        with self.assertRaisesRegex(ValueError, "package changed"):
            native.verify(binding)


if __name__ == "__main__":
    unittest.main()

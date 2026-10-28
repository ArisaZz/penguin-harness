"""Resource measurement scenarios; only temporary files and recorded JSON are used.

Given Harbor counters, cached tokens stay inside input and output is counted once.
Given Penguin buckets, request/cost-summary names produce the same normalized totals.
Given unavailable or inconsistent counters, preserve unknowns or reject contradictions.
Given timestamps, preserve native elapsed time separately from agent-only time.
Given disjoint operations, total Train/Test costs and tokens with explicit coverage.
Given overlapping parent/child usage, refuse double counting.
Given interrupted construction logs and resumed Sessions, sum request deltas, not cumulative totals.
Given native artifacts, the CLI emits only normalized measurements without changing the source.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/openskill-rsi-toolkit/scripts"
sys.path.insert(0, str(SCRIPTS))
import experiment
import resource_usage as usage


def row(key="r1", phase="train", case="train-1", **extra):
    return {"record_id": key, "phase": phase, "case_id": case, "status": "completed",
            "usage_ids": [key], "artifact_paths": [key + ".json"], "format": "canonical",
            "usage": {"cost_usd": 1.5, "started_at": "2026-10-28T00:00:00Z",
                      "finished_at": "2026-10-28T00:00:02Z",
                      "tokens": {"cached_input": 40, "uncached_input": 60, "output": 20}}, **extra}


class ResourceUsageTest(unittest.TestCase):
    def test_harbor_cached_input_and_thinking_are_not_added_twice(self):
        raw = {"agent_result": {"cost_usd": 0.5, "n_input_tokens": 100, "n_cache_tokens": 40,
                                "n_output_tokens": 20, "n_reasoning_tokens": 10},
               "started_at": "2026-10-28T00:00:00Z", "finished_at": "2026-10-28T00:00:05Z",
               "agent_execution": {"started_at": "2026-10-28T00:00:01Z", "finished_at": "2026-10-28T00:00:04Z"}}
        measured = usage.normalize(raw, "harbor")
        self.assertEqual(measured["tokens"], {"cached_input": 40, "uncached_input": 60, "output": 20,
                                              "total_input": 100, "total": 120})
        self.assertEqual(measured["cost_usd"], 0.5)
        self.assertEqual(measured["duration_ms"], 5000)
        self.assertEqual(measured["agent_duration_ms"], 3000)

    def test_penguin_request_and_cost_summary_buckets_agree(self):
        request = {"cache_read": 40, "cache_write": 60, "output": 20, "total": 120}
        summary = {"cacheRead": 40, "cacheWrite": 60, "output": 20, "total": 120, "cost": 0.5}
        self.assertEqual(usage.tokens(request, "penguin"), usage.normalize(summary, "penguin")["tokens"])
        self.assertIsNone(usage.normalize({**summary, "hasUncosted": True}, "penguin")["cost_usd"])

    def test_missing_data_stays_unknown_and_zero_is_measured(self):
        value = usage.normalize({"agent_result": {"n_input_tokens": 100, "n_output_tokens": 0}}, "harbor")
        self.assertIsNone(value["tokens"]["uncached_input"])
        self.assertIsNone(value["tokens"]["cached_input"])
        self.assertEqual(value["tokens"]["total"], 100)
        self.assertIsNone(value["cost_usd"])
        empty = usage.normalize({})
        self.assertTrue(all(v is None for v in empty["tokens"].values()))

    def test_inconsistent_or_invalid_measurements_are_rejected(self):
        for raw in [{"cached_input": 101, "total_input": 100},
                    {"uncached_input": 101, "total_input": 100},
                    {"cached_input": 40, "uncached_input": 60, "total_input": 80},
                    {"total_input": 100, "output": 20, "total": 140},
                    {"output": True}, {"cached_input": -1}, {"output": float("nan")}]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                usage.tokens(raw)
        for raw in [{"started_at": "2026-10-28T00:00:02Z", "finished_at": "2026-10-28T00:00:01Z"},
                    {"started_at": "2026-10-28T00:00:00"}, {"duration_ms": -1},
                    {"started_at": "2026-10-28T00:00:00Z", "finished_at": "2026-10-28T00:00:01Z", "duration_ms": 2000}]:
            with self.assertRaises(ValueError):
                usage.timing(raw)

    def test_totals_keep_parallel_wall_time_and_partial_cost_separate(self):
        data = usage.ledger({"schema_version": 1, "records": [row(), row("r2")]})
        totals = usage.summarize(data["records"], "complete")
        self.assertEqual(totals["cost_usd"]["total"], 3)
        self.assertEqual(totals["summed_duration_ms"]["total"], 4000)
        self.assertEqual(totals["wall_time_ms"], 2000)
        self.assertEqual(totals["tokens"]["total"]["total"], 240)
        data["records"][1]["cost_usd"] = None
        partial = usage.summarize(data["records"], "complete")
        self.assertIsNone(partial["cost_usd"]["total"])
        self.assertEqual(partial["cost_usd"]["known_total"], 1.5)
        self.assertEqual(partial["cost_usd"]["unknown_records"], 1)
        self.assertIsNone(usage.summarize(data["records"], "partial")["tokens"]["total"]["total"])

    def test_duplicate_and_parent_child_overlap_cannot_be_totaled(self):
        for rows in [[row(), row()], [row(), row("r2", usage_ids=["r1", "r2"])]]:
            with self.assertRaises(ValueError):
                usage.ledger({"schema_version": 1, "records": rows})

    def test_constructor_collector_uses_request_deltas_and_keeps_failed_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            state = {"config": {"case_ids": ["train-1"]}}
            for index, status in [(1, "completed"), (2, "interrupted")]:
                folder = out / f".executor/train-1/creator-{index}/execution"
                folder.mkdir(parents=True)
                (folder / "launcher.process.json").write_text(json.dumps({
                    "execution_status": status, "started_at": "2026-10-28T00:00:00Z",
                    "finished_at": "2026-10-28T00:00:02Z"}))
                (folder / "result.json").write_text(json.dumps({"session_id": "same-creator"}))
                event = {"id": f"usage-{index}", "type": "event_msg", "payload": {
                    "type": "token_usage", "request": {"cache_read": 4, "cache_write": 6, "output": 2, "total": 12},
                    "session": {"cache_read": 400, "cache_write": 600, "output": 200, "total": 1200}}}
                (folder / "messages.jsonl").write_text(json.dumps(event) + '\n{"truncated":')
            before = {str(p): p.read_bytes() for p in out.rglob('*') if p.is_file()}
            raw = usage.collect_construction(out, state)
            data = usage.ledger(raw)
            self.assertEqual(sum(r["tokens"]["total"] for r in data["records"]), 24)
            self.assertEqual([r["status"] for r in data["records"]], ["completed", "interrupted"])
            self.assertEqual(data["coverage"]["train"], "partial")
            self.assertTrue(all(r["cost_usd"] is None for r in data["records"]))
            self.assertEqual({str(p): p.read_bytes() for p in out.rglob('*') if p.is_file()}, before)

    def test_normalize_cli_reads_native_artifact_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "result.json"
            source.write_text(json.dumps({"agent_result": {"n_input_tokens": 100, "n_cache_tokens": 20,
                                                          "n_output_tokens": 30, "cost_usd": 0.2}}))
            before = source.read_bytes()
            result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "resource_usage.py"), "normalize",
                                     "harbor", str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["tokens"]["total"], 130)
            self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

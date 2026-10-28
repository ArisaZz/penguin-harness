#!/usr/bin/env python3
"""Run the complete offline gate with real SDK/container tests and a local scripted model.

Missing container configuration or any skipped/failed test fails this gate. Its report
records the tested files and runtime, never an algorithm score or permission to launch.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
TESTS = Path(__file__).resolve().parent
PLUGIN = TESTS.parent
sys.path.insert(0, str(PLUGIN / "skills/openskill-rsi-toolkit/scripts"))
from artifacts import digest, tree


def fingerprint():
    return {"scripts_sha256": digest(tree(PLUGIN / "skills/openskill-rsi-toolkit/scripts")),
            "tests_sha256": digest(tree(TESTS))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Reviewed local GDPevo image, pinned sha256 ID")
    parser.add_argument("--sdk", required=True, type=Path, help="Built Penguin core index.js")
    parser.add_argument("--report", required=True, type=Path, help="New JSON report outside the plugin")
    args = parser.parse_args()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image) or not args.sdk.is_file():
        parser.error("Supply a pinned image and an existing built SDK")
    if args.report.resolve().is_relative_to(PLUGIN):
        parser.error("Keep development reports outside the plugin's source tree")
    os.environ["OPENSKILL_TEST_IMAGE"] = args.image
    os.environ["OPENSKILL_TEST_SDK"] = str(args.sdk.resolve())
    before = fingerprint()
    sdk_sha256 = hashlib.sha256(args.sdk.read_bytes()).hexdigest()
    report = {"scope": "development_acceptance", "started_at": datetime.now(timezone.utc).isoformat(),
              **before, "sdk": str(args.sdk.resolve()), "sdk_sha256": sdk_sha256, "image": args.image,
              "model": "local scripted fixture", "passed": False, "benchmark_score": None}
    # Refuse an existing report before any test starts; retain partial evidence on interruption.
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.flush()
        try:
            suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
            result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
            unchanged = before == fingerprint() and hashlib.sha256(args.sdk.read_bytes()).hexdigest() == sdk_sha256
            report.update(tests_run=result.testsRun, skipped=[(str(t), why) for t, why in result.skipped],
                          failures=[str(t) for t, _ in result.failures], errors=[str(t) for t, _ in result.errors],
                          inputs_unchanged=unchanged,
                          passed=result.wasSuccessful() and result.testsRun > 0 and not result.skipped and unchanged)
        finally:
            report["finished_at"] = datetime.now(timezone.utc).isoformat()
            stream.seek(0)
            json.dump(report, stream, indent=2)
            stream.write("\n")
            stream.truncate()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

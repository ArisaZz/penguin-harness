"""Persist one real GDPevo training grade per task, without transport retries."""
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def grade(request):
    task = request["task_id"]
    if not isinstance(task, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", task):
        raise ValueError("invalid training task id")
    if task not in request["train_ids"]:
        raise ValueError("training judge cannot receive a held-out task")
    url = urlsplit(request["url"])
    if (url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1")
            or url.username or url.password or url.query or url.fragment or url.path != "/api/judge"):
        raise ValueError("use the declared container-local training /api/judge endpoint")
    answer_path = Path(request["answer"])
    raw = answer_path.read_bytes()
    answer = json.loads(raw)
    if not isinstance(answer, dict):
        raise ValueError("GDPevo answers must be JSON objects")
    identity = {"task_id": task, "url": request["url"],
                "answer_sha256": hashlib.sha256(raw).hexdigest()}
    directory = Path(request["feedback_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    ledger = directory / f"{task}.json"
    pending = directory / f"{task}.pending.json"
    if ledger.exists():
        previous = json.loads(ledger.read_text(encoding="utf-8"))
        if any(previous.get(key) != value for key, value in identity.items()):
            raise ValueError("graded answer identity changed; do not rescore")
        return previous
    # Claim before sending HTTP. An interrupted or ambiguous request is never repeated.
    with pending.open("x", encoding="utf-8") as handle:
        json.dump(identity, handle)
    record = {**identity, "status": "error", "score": None, "correct": None,
              "raw_response": None}
    try:
        body = json.dumps({"task_id": task, "answer": answer}).encode()
        call = Request(request["url"], data=body, headers={"Content-Type": "application/json"})
        with build_opener(ProxyHandler({}), NoRedirect()).open(call, timeout=30) as response:
            record["http_status"] = response.status
            record["raw_response"] = response.read().decode("utf-8")
        feedback = json.loads(record["raw_response"])
        score = feedback["score"]
        if (record["http_status"] != 200 or type(score) not in (int, float)
                or not math.isfinite(score) or not 0 <= score <= 1
                or type(feedback["correct"]) is not bool):
            raise ValueError("training judge did not return a valid normalized score/correct")
        record.update(status="ok", score=score, correct=feedback["correct"],
                      negative=not feedback["correct"] or score < 1)
    except (OSError, ValueError, KeyError, TypeError) as error:
        record["error"] = str(error)
    with ledger.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, allow_nan=False)
    return record

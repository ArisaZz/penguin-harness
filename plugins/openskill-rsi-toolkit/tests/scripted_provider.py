"""Local OpenAI-compatible model edge for executor integration tests only."""

import json
import re
import shlex
import uuid
from http.server import BaseHTTPRequestHandler


class Provider(BaseHTTPRequestHandler):
    requests = []
    verifier_tests = 1
    omit_suite = False

    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(body)
        messages = body["messages"]
        latest = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        if isinstance(latest, list):
            latest = "\n".join(p.get("text", "") for p in latest)
        calls = []
        if messages[-1]["role"] != "tool":
            def write(file, content):
                calls.append({"index": len(calls), "id": "call_" + uuid.uuid4().hex, "type": "function",
                              "function": {"name": "write_file", "arguments": json.dumps({"file_path": file, "content": content})}})
            if "Apply the frozen skills under " in latest:
                skills = re.search(r"Apply the frozen skills under (\S+) to", latest)[1]
                inputs = re.search(r"public task at (\S+)\. Read", latest)[1]
                outputs = re.search(r"under (\S+)\. This is", latest)[1]
                command = ("cat " + shlex.quote(skills + "/calculate/SKILL.md") + " && " +
                           "python3 " + shlex.quote(skills + "/calculate/scripts/total.py") + " " +
                           shlex.quote(inputs + "/rows.json") + " " + shlex.quote(outputs + "/total.txt"))
                calls.append({"index": 0, "id": "call_" + uuid.uuid4().hex, "type": "function",
                              "function": {"name": "exec_command", "arguments": json.dumps({"cmd": command, "workdir": outputs})}})
            elif "Fixed skill names:" in latest:
                root = re.search(r"Write reusable skills and contracts to (\S+)/skills", latest)[1]
                content = ("---\nname: calculate\ndescription: Sum supplied numeric rows.\nversion: 2026.10.16.1\n---\n"
                           "Run scripts/total.py with an input JSON array path and output text path.\n")
                write(root + "/skills/calculate/SKILL.md", content)
                write(root + "/skills/calculate/contract.json", json.dumps({"id": "one/calculate", "applies_when": "Sum numeric rows",
                      "parameters": {"input_file": "JSON array path", "output_file": "Result path"},
                      "outputs": ["integer total"], "checks": ["Independently sum all rows"], "limitations": [],
                      "resources": ["scripts/total.py"]}))
                rows = "rows" if "Include every row" in latest else "rows[:-1]"
                write(root + "/skills/calculate/scripts/total.py",
                      "import json,sys\nfrom pathlib import Path\nrows=json.loads(Path(sys.argv[1]).read_text())\n"
                      f"Path(sys.argv[2]).write_text(str(sum({rows})))\n")
                write(root + "/practice.json", json.dumps({"argv": ["python3", "${SKILLS}/calculate/scripts/total.py",
                      "${INPUTS}/rows.json", "${OUTPUTS}/total.txt"]}))
            else:
                root = re.search(r"Write (\S+)/suite.py", latest)[1]
                if type(self).omit_suite:
                    write(root + "/diagnosis.txt", "Verification anchors unavailable.")
                else:
                    write(root + "/suite.py", "import json,os,pytest\nfrom pathlib import Path\n"
                      f"@pytest.mark.parametrize('index', range({type(self).verifier_tests}))\n"
                      "def test_sum(index):\n"
                      "    Path('executed.txt').write_text('executed')\n"
                      "    rows=json.loads((Path(os.environ['OPENSKILL_INPUTS'])/'rows.json').read_text())\n"
                      "    actual=int((Path(os.environ['OPENSKILL_OUTPUTS'])/'total.txt').read_text())\n"
                      "    assert actual == sum(rows)\n")
                write(root + "/coverage.json", json.dumps([{"requirement": "Sum all rows", "required": True,
                      "source": "Public rows and independent arithmetic", "status": "covered", "tests": ["suite::test_sum[0]"]}]))
        delta = {"role": "assistant", "tool_calls": calls} if calls else {"role": "assistant", "content": "Artifacts prepared."}
        chunks = [{"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": 1, "model": "test",
                   "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                  {"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": 1, "model": "test",
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if calls else "stop"}],
                   "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}}]
        wire = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(wire.encode())))
        self.end_headers()
        self.wfile.write(wire.encode())

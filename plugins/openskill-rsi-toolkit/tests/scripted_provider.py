"""Local OpenAI-compatible model edge for executor integration tests only."""

import copy
import json
import re
import shlex
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler


class Provider(BaseHTTPRequestHandler):
    requests = []
    verifier_tests = 1
    omit_suite = False
    practice_exit_code = 0
    practice_from_skill_parent = False
    unsupported_oracle = False
    promote_unsupported = False
    practice_handoff = None
    practice_hook = None
    repeated_requirements = False
    unknown_test_mapping = False
    practice_scripts = None
    practice_script_index = 0
    practice_base_command = ""
    skill_exception = False
    additional_research = False
    plan_loader_bug = False
    plan_loader_checks = False

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
                type(self).practice_base_command = command
                if type(self).plan_loader_bug:
                    command += " && python3 - <<'PY'\n" + (
                        "import json,subprocess\nfrom pathlib import Path\n"
                        f"skill={skills + '/calculate/scripts/total.py'!r}\n"
                        f"inputs=Path({inputs!r})\noutputs=Path({outputs!r})\n"
                        "results={}\n"
                        "for form in ('list','object'):\n"
                        "    proc=subprocess.run(['python3',skill,'--plan',str(inputs/(form+'.json'))],capture_output=True,text=True)\n"
                        "    results[form]={'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}\n"
                        "(outputs/'loader.json').write_text(json.dumps(results))\nPY")
                type(self).practice_script_index = 0
                if type(self).practice_hook:
                    type(self).practice_hook()
                if type(self).practice_handoff:
                    # Reproduce the real failure: remembered author report, fresh output mount.
                    # The cooperative fixture uses the actual host handoff when supplied;
                    # the refusal fixture still reads the unavailable report after writing output.
                    check = ("from pathlib import Path\nimport errno,json\n"
                        "report=Path('reports/deployment-check.md')\n"
                        "context=Path('inputs/practice-context.json')\n")
                    if type(self).practice_handoff == "use_context":
                        check += ("if context.exists():\n"
                            "    m=json.loads(context.read_text())\n"
                            "    assert not report.exists()\n"
                            "    assert m['author_scratch_available'] is False\n"
                            "    assert m['outputs']==['total.txt']\n"
                            "    assert Path(m['skills_root'],'calculate/SKILL.md').is_file()\n"
                            "    assert 'public/rows.json' in m['input_files']\n"
                            "    assert 'reports/deployment-check.md' not in m['input_files']\n"
                            "    try: context.write_text('{}')\n"
                            "    except OSError as error: assert error.errno in (errno.EACCES, errno.EROFS)\n"
                            "    else: raise AssertionError('Handoff is writable')\n"
                            "else:\n    report.read_text()\n")
                    else:
                        check += "report.read_text()\n"
                    command += " && python3 - <<'PY'\n" + check + "PY"
                calls.append({"index": 0, "id": "call_" + uuid.uuid4().hex, "type": "function",
                              "function": {"name": "exec_command", "arguments": json.dumps({"cmd": command,
                                  "workdir": str(Path(skills).parent) if type(self).practice_from_skill_parent else outputs})}})
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
                      "import json,sys\nfrom pathlib import Path\n" +
                      (("if sys.argv[1]=='--plan':\n"
                        "    payload=json.loads(Path(sys.argv[2]).read_text())\n"
                        + ("    rows=payload['requests'] if isinstance(payload,dict) else payload\n"
                           if "Repair documented plan forms" in latest else "    rows=payload.get('requests',payload)\n") +
                        "    print(len(rows))\n    raise SystemExit(0)\n") if type(self).plan_loader_bug else "") +
                      "rows=json.loads(Path(sys.argv[1]).read_text())\n"
                      f"Path(sys.argv[2]).write_text(str(sum({rows})))\n"
                      + ("raise KeyError('frozen-skill-bug')\n" if type(self).skill_exception else "") +
                      f"raise SystemExit({type(self).practice_exit_code})\n")
                write(root + "/practice.json", json.dumps({"argv": ["python3", "${SKILLS}/calculate/scripts/total.py",
                      "${INPUTS}/rows.json", "${OUTPUTS}/total.txt"]}))
                if type(self).practice_handoff:
                    write(root + "/reports/deployment-check.md", "Author-only integrity notes. Never a task input.\n")
            elif "Prepare an independent verification plan" in latest:
                root = re.search(r"Write (\S+)/verification-plan.json", latest)[1]
                requirements = [{"id": "sum", "requirement": "Sum all rows", "required": True,
                    "basis": "derived", "expectation": "The output equals the sum of every numeric row.",
                    "reasoning": "Add every number in the public rows, including negative values.",
                    "sources": [{"path": "public/rows.json", "quote": "[1, 2, -1]"},
                                {"path": "research/anchors.md", "quote": "1 + 2 - 1 = 2"}]}]
                if type(self).unsupported_oracle:
                    requirements.append({"id": "permissions", "requirement": "Exact sharing permissions",
                        "required": True, "basis": "hypothesis", "expectation": "Both users may need view permission.",
                        "reasoning": "The public list of users provides no permission assignment.", "sources": []})
                if type(self).repeated_requirements:
                    requirements.append({**copy.deepcopy(requirements[0]), "id": "sum-second-task"})
                if type(self).additional_research:
                    requirements[0]["sources"].append({"path": "additional-research/business/api-evidence.json",
                                                       "quote": '"expected": 2'})
                if type(self).plan_loader_checks:
                    requirements.append({"id":"plan-forms","requirement":"Accept both documented plan forms",
                        "required":True,"basis":"derived","expectation":"Both forms load all supplied requests",
                        "reasoning":"Count each request in the independently supplied public list and object inputs",
                        "sources":[{"path":"public/plan-contract.txt","quote":"Accept a list or an object containing requests."}]})
                write(root + "/verification-plan.json", json.dumps({"schema_version": 1, "requirements": requirements}))
                # Planning receives neither the candidate nor a creator implementation.
                calls.append({"index": len(calls), "id": "call_" + uuid.uuid4().hex, "type": "function",
                    "function": {"name": "exec_command", "arguments": json.dumps({"cmd":
                        "python3 -c \"from pathlib import Path; assert not Path('inputs/outputs').exists(); "
                        "assert not Path('inputs/skills').exists()\""})}})
            else:
                root = re.search(r"Write (\S+)/suite.py", latest)[1]
                if type(self).omit_suite:
                    write(root + "/diagnosis.txt", "Verification anchors unavailable.")
                else:
                    write(root + "/suite.py", "import json,os,pytest,re\nfrom pathlib import Path\n"
                      f"@pytest.mark.parametrize('index', range({type(self).verifier_tests}))\n"
                      "def test_sum(index):\n"
                      "    Path('executed.txt').write_text('executed')\n"
                      "    rows=json.loads((Path(os.environ['OPENSKILL_INPUTS'])/'rows.json').read_text())\n"
                      "    anchor=(Path(os.environ['OPENSKILL_RESEARCH'])/'anchors.md').read_text()\n"
                      "    expected=int(re.search(r'= (-?\\d+)',anchor)[1])\n"
                      "    extra=Path(os.environ['OPENSKILL_ADDITIONAL_RESEARCH'])\n"
                      "    assert extra.is_dir()\n"
                      + ("    assert json.loads((extra/'business/api-evidence.json').read_text())['expected'] == expected\n"
                         if type(self).additional_research else "") +
                      "    actual=int((Path(os.environ['OPENSKILL_OUTPUTS'])/'total.txt').read_text())\n"
                      "    assert actual == expected == sum(rows)\n")
                    if type(self).plan_loader_checks:
                        # This checks actual frozen-skill executions, not an author's assertion of a fix.
                        calls[-1]["function"]["arguments"] = json.dumps({"file_path":root+"/suite.py", "content":
                            json.loads(calls[-1]["function"]["arguments"])["content"] +
                            "\ndef test_plan_forms():\n"
                            "    results=json.loads((Path(os.environ['OPENSKILL_OUTPUTS'])/'loader.json').read_text())\n"
                            "    for form in ('list','object'):\n"
                            "        data=json.loads((Path(os.environ['OPENSKILL_INPUTS'])/(form+'.json')).read_text())\n"
                            "        expected=len(data['requests'] if isinstance(data,dict) else data)\n"
                            "        assert results[form]['exit_code']==0, results[form]['stderr']\n"
                            "        assert int(results[form]['stdout'])==expected\n"})
                command = ("python3 - <<'PY'\nimport json\nfrom pathlib import Path\n"
                    "result=json.loads(Path('oracle/coverage-template.json').read_text())\n"
                    "r=json.loads(Path('oracle/review.json').read_text())\n"
                    "decisions={d['id']:d['status'] for d in r['decisions']}\n"
                    "for entry in result:\n"
                    f"    covered=decisions[entry['requirement_id']]=='supported' or {type(self).promote_unsupported!r}\n"
                    "    entry.update(source='Public rows and independent arithmetic',status='covered' if covered else 'unverified',"
                    f"tests=[{'suite::missing' if type(self).unknown_test_mapping else 'suite::test_sum[0]'!r}] if covered else [])\n"
                    + ("    if entry['requirement_id']=='plan-forms': entry['tests']=['suite::test_plan_forms']\n"
                       if type(self).plan_loader_checks else "") +
                    "Path('coverage.json').write_text(json.dumps(result))\nPY")
                calls.append({"index": len(calls), "id": "call_" + uuid.uuid4().hex, "type": "function",
                              "function": {"name": "exec_command", "arguments": json.dumps({"cmd": command})}})
        if "Apply the frozen skills under " in latest and type(self).practice_scripts is not None:
            index = type(self).practice_script_index
            calls = []
            if index < len(type(self).practice_scripts):
                batch = type(self).practice_scripts[index]
                if isinstance(batch, str):
                    batch = [batch]
                type(self).practice_script_index += 1
                for cmd in batch:
                    cmd = cmd.replace("${BASE_COMMAND}", type(self).practice_base_command)
                    calls.append({"index": len(calls), "id": "call_" + uuid.uuid4().hex, "type": "function",
                                  "function": {"name": "exec_command", "arguments": json.dumps({"cmd": cmd})}})
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

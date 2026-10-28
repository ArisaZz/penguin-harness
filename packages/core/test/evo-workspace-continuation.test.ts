/**
 * Given an exported Evo package installed into a native State, a real child Session
 * receives its frozen context before reading public input. When feedback arrives,
 * the same Solver/model continues with its original observations and answer.
 * Scripted model boundary only; native State, tools, IO and traces are real.
 */
import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import { createAgent, GenerativeModel, userText, assistantText, toolCall } from "../src/index.js";
import type { Session } from "../src/index.js";
import { seedProject } from "./seeded-project.js";
import { stubProviderKeys } from "./provider-keys.js";
let root: string, parent: Session | undefined, restore: (() => void) | undefined;
afterEach(async () => {
  parent?.dispose();
  restore?.();
  vi.restoreAllMocks();
  if (root) await fs.rm(root, { recursive: true, force: true });
});
it("loads an exported Evo State and retains the original Solver through feedback", async () => {
  root = await fs.mkdtemp(path.join(os.tmpdir(), "evo-native-workspace-"));
  restore = stubProviderKeys();
  await seedProject(root);
  const dir = path.join(root, "workspace");
  await fs.mkdir(dir);
  const fact = path.join(dir, "public-fact.txt");
  await fs.writeFile(fact, "AUTHORIZED_FACT_OBSERVED\n");
  vi.spyOn(globalThis, "fetch").mockRejectedValue(Error("No network in native continuation test"));
  const roles = new WeakMap<object, "parent" | "solver">();
  let childModel: object | undefined,
    observed = false,
    solved = false,
    reflected = false,
    sent = false,
    started = false,
    handle = "",
    childId = "",
    count = 0;
  vi.spyOn(GenerativeModel.prototype, "streamGenerate").mockImplementation(async function* (
    this: GenerativeModel,
    params,
  ) {
    const text = JSON.stringify(params.newMessages);
    let role = roles.get(this);
    if (!role) {
      role = text.includes("ORIGINAL_PROBLEM") ? "solver" : "parent";
      roles.set(this, role);
    }
    if (role === "solver") {
      if (!childModel) childModel = this;
      expect(this).toBe(childModel);
      if (text.includes("FULL_AUTHORIZED_FEEDBACK")) {
        expect(observed && solved).toBe(true);
        reflected = true;
        yield assistantText("REFLECTED_MEMORY_FROM_ORIGINAL_HISTORY");
      } else if (!observed && text.includes("AUTHORIZED_FACT_OBSERVED")) {
        observed = true;
        solved = true;
        yield assistantText("FROZEN_ANSWER");
      } else {
        yield toolCall({
          name: "read_file",
          arguments: JSON.stringify({ file_path: fact }),
          toolCallId: "original-read",
        });
      }
    } else {
      expect(++count).toBeLessThan(20);
      if (!started) {
        started = true;
        yield toolCall({
          name: "run_subagent",
          arguments: JSON.stringify({
            description: "Solver",
            prompt: "ORIGINAL_PROBLEM",
            provider: "deepseek",
            model_id: "deepseek-flash",
            thinking_level: "max",
            run_in_background: true,
          }),
          toolCallId: "original-dispatch",
        });
      } else {
        const child = parent!.listBackgroundSubagents()[0];
        if (child) {
          handle = child.subagentId!;
          childId = child.sessionId;
        }
        expect(handle).not.toBe("");
        if (reflected && !child?.running) yield assistantText("Complete.");
        else if (solved && !child?.running && !sent) {
          sent = true;
          yield toolCall({
            name: "input_subagent",
            arguments: JSON.stringify({
              description: "Continue the original Solver with its real feedback",
              subagent_id: handle,
              prompt: "FULL_AUTHORIZED_FEEDBACK",
              yield_time_ms: 1000,
            }),
            toolCallId: "feedback",
          });
        } else
          yield toolCall({
            name: "input_subagent",
            arguments: JSON.stringify({
              description: "Collect the same Solver",
              subagent_id: handle,
              yield_time_ms: 1000,
            }),
            toolCallId: "wait-" + count,
          });
      }
    }
    return { status: "completed" as const };
  });
  const agent = await createAgent({ root, agentId: "controller" });
  const helper = path.resolve(
    import.meta.dirname,
    "../../../plugins/evo-harness-rsi-toolkit/skills/evo-harness-rsi-toolkit/scripts/evo.py",
  );
  const stateDir = path.join(root, "default_project/agents/controller/agent_state");
  const exportRequest = path.join(root, "library.json");
  const exportReceipt = path.join(root, "export-receipt.json");
  await fs.writeFile(
    exportRequest,
    JSON.stringify({
      topic: "fixture",
      library: [
        {
          id: "fixture-method",
          level: "topic",
          topic: "fixture",
          trigger: "This fixture",
          scope: "Public fixture input",
          body: "FROZEN_TOPIC_BODY_BEFORE_BUSINESS",
        },
      ],
    }),
  );
  const receipt = execFileSync(
    "python3",
    ["-B", helper, "export", "--request", exportRequest, "--output", path.join(root, "export")],
    { encoding: "utf8" },
  );
  await fs.writeFile(exportReceipt, receipt);
  execFileSync(
    "python3",
    ["-B", helper, "install", "--request", exportReceipt, "--state", stateDir],
    { encoding: "utf8" },
  );
  parent = await agent.createSession({
    workspaceDir: dir,
    source: "user",
    provider: "deepseek",
    modelId: "deepseek-flash",
    thinkingLevel: "max",
  });
  for await (const _ of parent.run([userText("PARENT_CONTROL")], {
    approve: async () => "allow",
  })) {
  }
  expect(reflected).toBe(true);
  const rows: any[] = [];
  const visit = async (p: string): Promise<void> => {
    for (const e of await fs.readdir(p, { withFileTypes: true })) {
      const f = path.join(p, e.name);
      if (e.isDirectory()) await visit(f);
      else if (e.name.startsWith(childId) && e.name.endsWith(".jsonl"))
        rows.push(
          ...(await fs.readFile(f, "utf8"))
            .trim()
            .split("\n")
            .map((x) => JSON.parse(x)),
        );
    }
  };
  await visit(path.join(root, "default_project/agents/controller/traces"));
  expect(
    new Set(rows.filter((r) => r.type === "session_meta").map((r) => r.payload.session_id)),
  ).toEqual(new Set([childId]));
  expect(rows.find((r) => r.type === "session_meta").payload.workspace).toBe(dir);
  const system = rows.find((r) => r.type === "session_meta").payload.system_prompt;
  expect(system).toContain("<!-- evo-frozen-context -->");
  expect(system).toContain("FROZEN_TOPIC_BODY_BEFORE_BUSINESS");
  expect(JSON.stringify(rows)).toContain("AUTHORIZED_FACT_OBSERVED");
  expect(JSON.stringify(rows)).toContain("FROZEN_ANSWER");
  expect(JSON.stringify(rows)).toContain("FULL_AUTHORIZED_FEEDBACK");
}, 20000);

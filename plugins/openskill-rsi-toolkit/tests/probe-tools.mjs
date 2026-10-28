/** Real SDK tools: public reads and own writes work; private reads and input mutation fail. */
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { confiner, roleConfig } from "../skills/openskill-rsi-toolkit/scripts/launch.mjs";

const config = JSON.parse(await fs.readFile(process.argv[2], "utf8"));
const sdk = await import(pathToFileURL(config.sdk).href);
const env = new sdk.Environment({
  workspaceDir: config.work,
  toolConfig: { customTools: roleConfig(sdk, config).tools.builtin, mcpServers: [] },
  confineSpawn: () => confiner(config),
});
async function call(name, args) {
  let last;
  for await (const message of env.executeTool({
    toolCall: sdk.toolCall({ name, arguments: JSON.stringify(args), toolCallId: "probe" }),
    approve: async () => "allow",
  }))
    last = message;
  return JSON.stringify(last);
}
try {
  assert.match(await call("read_file", { file_path: config.public }), /PUBLIC-CANARY/);
  assert.match(
    await call("exec_command", { cmd: `cat '${config.public}'`, login: false }),
    /PUBLIC-CANARY/,
  );
  assert.doesNotMatch(await call("read_file", { file_path: config.secret }), /PRIVATE-CANARY/);
  assert.doesNotMatch(
    await call("exec_command", { cmd: `cat '${config.secret}'`, login: false }),
    /PRIVATE-CANARY/,
  );
  assert.match(
    await call("write_file", { file_path: config.work + "/own.txt", content: "own output" }),
    /completed/,
  );
  assert.match(await call("read_file", { file_path: config.work + "/own.txt" }), /own output/);
  await call("write_file", { file_path: config.public, content: "MUTATED" });
  assert.match(await call("read_file", { file_path: config.public }), /PUBLIC-CANARY/);
  assert.match(await call("run_subagent", { prompt: "escape" }), /Unknown tool/);
  assert.match(
    await call("exec_command", { cmd: "true", workdir: "/", login: false }),
    /outside the role mounts/,
  );
  assert.doesNotMatch(
    await call("exec_command", { cmd: "printenv OPENSKILL_HOST_CANARY", login: false }),
    /HOST-SECRET/,
  );
  console.log("confined SDK tools passed");
} finally {
  env.dispose();
}

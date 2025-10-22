// Example script that reads wizard answers and displays escrow settings.
// This does not execute escrow; use your Anchor client and on-chain tests.

import * as fs from "fs";
import * as path from "path";

function loadAnswers(root: string): any {
  const p = path.join(root, "blueprint.answers.json");
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return {};
  }
}

async function main() {
  const root = process.cwd();
  const answers = loadAnswers(root);
  const mint = (answers.mint || "").toString();

  console.log("Escrow config (from blueprint.answers.json):\n");
  console.log(`  Token mint (optional): ${mint || '(not set)'}`);
  console.log("\nNext steps:");
  console.log("  - Implement full flows in your client; use init/deposit/withdraw/cancel.");
  console.log("  - After deploy, use /program wizard <PROGRAM_ID> to run a flow.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});


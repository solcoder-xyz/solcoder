// Example script that reads wizard answers and shows registry settings.
// This does not perform on-chain operations; use your Anchor client.

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
  const keyType = (answers.key_type || "string").toString();
  const valueType = (answers.value_type || "string").toString();

  console.log("Registry settings (from blueprint.answers.json):\n");
  console.log(`  Key type  : ${keyType}`);
  console.log(`  Value type: ${valueType}`);
  console.log("\nNext steps:");
  console.log("  - Use the upsert/remove instructions in programs/<name>/src/lib.rs.");
  console.log("  - After deploy, call /program wizard <PROGRAM_ID> to try instructions.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});


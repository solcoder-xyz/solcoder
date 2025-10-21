// This example script reads wizard answers to show token metadata.
// It does not mint on-chain by itself; use spl-token CLI or an Anchor client.

import * as fs from "fs";
import * as path from "path";

function loadAnswers(root: string): any {
  const p = path.join(root, "blueprint.answers.json");
  try {
    const raw = fs.readFileSync(p, "utf8");
    return JSON.parse(raw);
  } catch (e) {
    return {};
  }
}

async function main() {
  const root = process.cwd();
  const answers = loadAnswers(root);
  const name = answers.token_name || "SolCoder Token";
  const symbol = answers.symbol || "SCT";
  const decimals = Number.isFinite(answers.decimals) ? answers.decimals : 9;

  console.log("Token metadata (from blueprint.answers.json):\n");
  console.log(`  Name    : ${name}`);
  console.log(`  Symbol  : ${symbol}`);
  console.log(`  Decimals: ${decimals}`);
  console.log("\nNext steps:");
  console.log("  - Create a mint on devnet with spl-token CLI (example):");
  console.log("      spl-token create-token --decimals", decimals);
  console.log("  - Create an associated token account and mint an initial supply:");
  console.log("      spl-token create-account <MINT>\n      spl-token mint <MINT> <AMOUNT>");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});


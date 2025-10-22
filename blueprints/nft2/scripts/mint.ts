// Example script that reads wizard answers and displays NFT metadata settings.
// This does not mint on-chain; use Metaplex or your Anchor client for minting.

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
  const name = answers.name || "SolCoder NFT";
  const symbol = answers.symbol || "SCN";
  const uri = answers.uri || "https://example.com/metadata.json";

  console.log("NFT metadata (from blueprint.answers.json):\n");
  console.log(`  Name  : ${name}`);
  console.log(`  Symbol: ${symbol}`);
  console.log(`  URI   : ${uri}`);
  console.log("\nNext steps:");
  console.log("  - Use Metaplex or your Anchor client to create a mint and set metadata.");
  console.log("  - After deploy, run /program inspect <PROGRAM_ID> to explore instructions.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});


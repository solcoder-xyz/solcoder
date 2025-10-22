// This example script reads wizard answers to show token metadata and toggles.
// It does not mint on-chain by itself; use spl-token CLI or SolCoder quick flow.

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
  const feeBps = Number.isFinite(answers.transfer_fee_bps) ? answers.transfer_fee_bps : undefined;
  const interestBps = Number.isFinite(answers.interest_rate_bps) ? answers.interest_rate_bps : undefined;
  const metadataPtr = answers.metadata_pointer_uri || undefined;

  console.log("Token configuration (from blueprint.answers.json):\n");
  console.log(`  Name                : ${name}`);
  console.log(`  Symbol              : ${symbol}`);
  console.log(`  Decimals            : ${decimals}`);
  if (feeBps !== undefined) console.log(`  Transfer Fee (bps)  : ${feeBps}`);
  if (interestBps !== undefined) console.log(`  Interest Rate (bps) : ${interestBps}`);
  if (metadataPtr) console.log(`  Metadata Pointer URI: ${metadataPtr}`);
  console.log("\nSuggested steps (devnet):");
  console.log("  - Create mint with Token-2022 and your toggles (where supported)");
  console.log("  - Create wallet ATA and mint initial supply");
  console.log("  - Transfer between ATAs\n");
  console.log("SolCoder quick flow:");
  console.log("  /new token --quick --decimals", decimals, "--supply 1000000 --cluster devnet");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});


// Simple transfer example using spl-token CLI output
// Adjust values after running scripts/mint.ts
import { execSync } from 'node:child_process';

function sh(cmd: string) {
  return execSync(cmd, { stdio: 'inherit' });
}

const RPC = process.env.SOLANA_URL || 'https://api.devnet.solana.com';
const PROGRAM_2022 = '--program-2022';

const MINT = process.env.MINT || '<REPLACE_WITH_MINT>'; // from mint.ts output
const DEST = process.env.DEST || '<REPLACE_WITH_DEST_ATA>'; // destination ATA
const AMOUNT = process.env.AMOUNT || '1';

if (MINT.startsWith('<')) {
  console.error('Set MINT env to the mint address');
  process.exit(2);
}

console.log('Transferring tokens...');
sh(`spl-token transfer ${MINT} ${AMOUNT} ${DEST} ${PROGRAM_2022} -u ${RPC}`);
console.log('Done');


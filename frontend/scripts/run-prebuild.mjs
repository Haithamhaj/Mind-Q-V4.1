#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const toBool = (value) => {
  if (!value) return false;
  const normalized = value.toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
};

const skipReason = (() => {
  if (process.env.VERCEL && !toBool(process.env.VERCEL_FORCE_PREBUILD)) {
    return 'VERCEL detected (set VERCEL_FORCE_PREBUILD=1 to run anyway).';
  }
  if (toBool(process.env.SKIP_FRONTEND_PREBUILD)) {
    return 'SKIP_FRONTEND_PREBUILD set - skipping Python reconcile step.';
  }
  return null;
})();

if (skipReason) {
  console.log(`[prebuild] ${skipReason}`);
  process.exit(0);
}

const pythonCandidates = Array.from(
  new Set(
    [process.env.PYTHON_CMD, process.env.PYTHON, 'python', 'python3', 'python3.11', 'python3.10'].filter(Boolean)
  )
);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, '..');
const args = ['-m', 'bi.reconcile.run', 'artifacts/p09.parquet', 'artifacts/p10.parquet', 'bi/semantic/metrics.yml'];

let lastSpawnError = null;

for (const pythonCommand of pythonCandidates) {
  console.log(`[prebuild] Running ${pythonCommand} ${args.join(' ')}`);

  const result = spawnSync(pythonCommand, args, {
    stdio: 'inherit',
    cwd: frontendRoot
  });

  if (result.error) {
    if (result.error.code === 'ENOENT') {
      console.warn(`[prebuild] ${pythonCommand} not found in PATH.`);
      lastSpawnError = result.error;
      continue;
    }

    console.error('[prebuild] Failed to start Python process:', result.error.message);
    process.exit(1);
  }

  if (typeof result.status === 'number') {
    process.exit(result.status);
  }
}

console.error('[prebuild] Could not find a usable Python interpreter.');
if (lastSpawnError) {
  console.error('[prebuild] Last error:', lastSpawnError.message);
}
console.error('[prebuild] Tried commands:', pythonCandidates.join(', '));
console.error('[prebuild] You can also set SKIP_FRONTEND_PREBUILD=1 to bypass this step.');
process.exit(1);

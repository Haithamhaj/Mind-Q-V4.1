#!/usr/bin/env node
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(frontendRoot, '..');
const configPath = path.resolve(repoRoot, 'performance-budget.json');

if (!existsSync(configPath)) {
  console.error('[budget] Missing performance-budget.json at repo root.');
  process.exit(1);
}

let config;
try {
  config = JSON.parse(readFileSync(configPath, 'utf8'));
} catch (error) {
  console.error('[budget] Failed to parse performance-budget.json:', error.message);
  process.exit(1);
}

const budgets = Array.isArray(config.budgets) ? config.budgets : [];
if (!budgets.length) {
  console.error('[budget] No budgets defined in performance-budget.json.');
  process.exit(1);
}

const failures = [];

const toKB = (bytes) => bytes / 1024;

const sizeOfPath = (targetPath, filterRegex) => {
  const stats = statSync(targetPath);
  if (stats.isFile()) {
    return stats.size;
  }

  let total = 0;
  const stack = [targetPath];

  while (stack.length) {
    const current = stack.pop();
    const info = statSync(current);

    if (info.isDirectory()) {
      const entries = readdirSync(current);
      for (const entry of entries) {
        stack.push(path.join(current, entry));
      }
      continue;
    }

    if (!filterRegex) {
      total += info.size;
      continue;
    }

    const relative = path.relative(frontendRoot, current).replace(/\\/g, '/');
    if (filterRegex.test(relative)) {
      total += info.size;
    }
  }

  return total;
};

const normalizeRegex = (pattern) => {
  if (!pattern) {
    return null;
  }

  try {
    return new RegExp(pattern);
  } catch (error) {
    console.warn(`[budget] Ignoring invalid filter regex "${pattern}": ${error.message}`);
    return null;
  }
};

console.log('\nPerformance budget check');
console.log('='.repeat(28));

for (const budget of budgets) {
  const targetPath = path.resolve(frontendRoot, budget.path);
  const optional = Boolean(budget.optional);

  if (!existsSync(targetPath)) {
    const message = `[budget] Path not found for "${budget.name}": ${budget.path}`;
    if (optional) {
      console.log(`${message} (optional, skipped)`);
      continue;
    }

    console.error(message);
    failures.push({ name: budget.name, reason: 'missing' });
    continue;
  }

  const filterRegex = normalizeRegex(budget.filter);
  const bytes = sizeOfPath(targetPath, filterRegex);
  const sizeKB = toKB(bytes);
  const warnKB = typeof budget.warnKB === 'number' ? budget.warnKB : null;
  const maxKB = typeof budget.maxKB === 'number' ? budget.maxKB : null;

  if (maxKB === null) {
    console.error(`[budget] Budget "${budget.name}" is missing maxKB.`);
    failures.push({ name: budget.name, reason: 'no-limit' });
    continue;
  }

  const status = sizeKB <= maxKB ? 'PASS' : 'FAIL';
  const formattedSize = sizeKB.toFixed(2);
  const formattedLimit = maxKB.toFixed(2);
  const prefix = status === 'PASS' ? '[PASS]' : '[FAIL]';

  console.log(`${prefix} ${budget.name}: ${formattedSize} KB (limit ${formattedLimit} KB)`);

  if (status === 'FAIL') {
    failures.push({ name: budget.name, reason: 'limit', sizeKB, maxKB });
    continue;
  }

  if (warnKB !== null && sizeKB > warnKB) {
    console.log(`[WARN] ${budget.name}: exceeded warning threshold ${warnKB.toFixed(2)} KB`);
  }
}

if (Array.isArray(config.metrics) && config.metrics.length) {
  console.log('\nReference metrics (manual verification)');
  console.log('--------------------------------------');
  for (const metric of config.metrics) {
    const name = metric.metric || 'metric';
    const target = typeof metric.targetMs === 'number' ? `${metric.targetMs} ms` : 'n/a';
  const notes = metric.notes ? ` - ${metric.notes}` : '';
    console.log(`• ${name}: target ${target}${notes}`);
  }
}

if (failures.length) {
  console.error('\nPerformance budget violations detected.');
  process.exit(1);
}

console.log('\nAll enforced performance budgets passed.');

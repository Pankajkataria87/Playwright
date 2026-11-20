// Shared helpers: find plans and read the URL from each plan's header.
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

export const config = JSON.parse(readFileSync('agentic.config.json', 'utf8'));

/** URL priority: BASE_URL env  >  "**URL:**" line in the plan  >  defaultUrl in agentic.config.json */
export function urlFor(planPath) {
  if (process.env.BASE_URL) return process.env.BASE_URL;
  const m = readFileSync(planPath, 'utf8').match(/^\*\*URL:\*\*\s*(\S+)/mi);
  return m?.[1] || config.defaultUrl || '';
}

/** plans/login.md -> "login";  plans/QA-42/billing-tab.md -> "qa-42-billing-tab" */
export const slug = planPath =>
  relative(config.plansDir, planPath).replace(/\.md$/i, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

const isPlan = f => f.endsWith('.md') && !f.split(/[\\/]/).pop().startsWith('_');

/** Plans inside a folder (recursive), skipping files/folders that start with "_". */
export function plansIn(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap(f => {
    if (f.startsWith('_')) return [];
    const p = join(dir, f);
    return statSync(p).isDirectory() ? plansIn(p) : isPlan(p) ? [p] : [];
  }).sort();
}

export const allPlans = () => plansIn(config.plansDir);

/** Expand CLI args (files and/or folders) into a list of plan files. */
export function resolvePlans(args) {
  return [...new Set(args.flatMap(a =>
    existsSync(a) && statSync(a).isDirectory() ? plansIn(a) : isPlan(a) && existsSync(a) ? [a] : []))];
}

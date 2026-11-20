// Shared helpers: find plans and read the URL from each plan's header.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';

export const config = JSON.parse(readFileSync('agentic.config.json', 'utf8'));

/** URL priority: BASE_URL env  >  "**URL:**" line in the plan  >  defaultUrl in agentic.config.json */
export function urlFor(planPath) {
  if (process.env.BASE_URL) return process.env.BASE_URL;
  const m = readFileSync(planPath, 'utf8').match(/^\*\*URL:\*\*\s*(\S+)/mi);
  return m?.[1] || config.defaultUrl || '';
}

export const slug = planPath => basename(planPath, '.md').toLowerCase().replace(/[^a-z0-9-]+/g, '-');

/** All plans, excluding files starting with "_" (templates/examples). */
export function allPlans() {
  const dir = config.plansDir;
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter(f => f.endsWith('.md') && !f.startsWith('_')).map(f => join(dir, f));
}

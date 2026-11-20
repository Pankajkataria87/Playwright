#!/usr/bin/env node
// Turn Markdown plans into Playwright tests with an AI agent, run them, report.
//
//   npm run plan plans/login.md                       # one plan
//   npm run plan plans/login.md plans/checkout.md     # several plans
//   npm run plan plans/QA-42/                         # every plan in a folder (recursive)
//   npm run plan -- --all                             # every plan in plans/
//   ... -- --print       print the prompt(s) instead (paste into Devin / any agent)
//   ... -- --run-only    skip generation, just run existing tests
//   BASE_URL=https://staging.x.com npm run plan ...   # override every plan's URL
import { spawnSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { urlFor, slug, config, allPlans, resolvePlans } from './plans.mjs';

const args = process.argv.slice(2);
const PRINT = args.includes('--print');
const RUN_ONLY = args.includes('--run-only');
const plans = args.includes('--all') ? allPlans() : resolvePlans(args.filter(a => !a.startsWith('--')));

if (!plans.length) {
  console.error('No plans found.\nUsage: npm run plan <plan.md | folder>... [-- --all --print --run-only]');
  process.exit(1);
}

const jobs = plans.map(p => ({ plan: p, name: slug(p), url: urlFor(p), out: `${config.outputDir}/${slug(p)}` }));
const missing = jobs.filter(j => !j.url);
if (missing.length) {
  console.error('No URL for: ' + missing.map(j => j.plan).join(', ') +
    '\nAdd "**URL:** https://..." to the plan, set BASE_URL, or set defaultUrl in agentic.config.json.');
  process.exit(1);
}

const promptFor = j => `Follow prompts/agent.md for the plan ${j.plan}.
Name: ${j.name}
URL: ${j.url}
Output folder: ${j.out}/
Use the Playwright generator agent to write the tests and the healer agent to fix failures, if available.`;

// --print: one prompt covering all plans, ready to paste into Devin / any agent.
if (PRINT) {
  if (jobs.length === 1) console.log(promptFor(jobs[0]));
  else {
    console.log(`Follow prompts/agent.md for each plan below, one after another.
Reuse page objects between plans that share a URL host.
At the end, run: npx playwright test ${jobs.map(j => `--project=${j.name}`).join(' ')}
and report one table per plan.\n`);
    for (const j of jobs) console.log(`- ${j.plan} → name: ${j.name}, URL: ${j.url}, output: ${j.out}/`);
  }
  process.exit(0);
}

const run = (cmd, a, env = {}) => spawnSync(cmd, a, { stdio: 'inherit', env: { ...process.env, ...env } });

console.log(`\n${jobs.length} plan(s):`);
for (const j of jobs) console.log(`  • ${j.plan}  →  ${j.out}/  (${j.url})`);

if (!RUN_ONLY) {
  if (spawnSync('claude', ['--version'], { stdio: 'ignore' }).status !== 0) {
    console.error('\nClaude Code not found. Install it (npm i -g @anthropic-ai/claude-code)\n' +
                  'or use --print and paste the prompt into Devin / another agent.');
    process.exit(1);
  }
  // Check each distinct URL opens once, before spending agent time.
  for (const url of new Set(jobs.map(j => j.url))) {
    console.log(`\n── Seed check: ${url}`);
    if (run('npx', ['playwright', 'test', '--project=seed'], { BASE_URL: url }).status !== 0) {
      console.error(`Seed failed: ${url} could not be opened. Fix that first.`);
      process.exit(1);
    }
  }
  // Plans run one after another so later plans can reuse page objects from earlier ones.
  for (const j of jobs) {
    console.log(`\n── Generating: ${j.plan}`);
    mkdirSync(j.out, { recursive: true });
    run('claude', [
      '-p', promptFor(j),
      '--permission-mode', 'acceptEdits',
      '--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash(npx playwright:*),Bash(npx tsc:*),mcp__playwright-test',
    ], { BASE_URL: j.url });
  }
}

console.log('\n── Final run (all selected plans) ──');
const res = run('npx', ['playwright', 'test', ...jobs.map(j => `--project=${j.name}`)]);
console.log('\nReport: npm run report   (HTML, grouped by plan/project)   •   JUnit: test-results/results.xml');
process.exit(res.status ?? 1);

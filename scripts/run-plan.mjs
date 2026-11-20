#!/usr/bin/env node
// Turn a Markdown plan into Playwright tests with an AI agent, run them, report.
//
//   npm run plan plans/login.md                 # Claude Code + Playwright agents (local)
//   npm run plan plans/login.md -- --print      # just print the prompt (paste into Devin / any agent)
//   npm run plan plans/login.md -- --run-only   # skip generation, run existing tests
//   BASE_URL=https://staging.x.com npm run plan plans/login.md   # override the plan's URL
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { urlFor, slug, config } from './plans.mjs';

const args = process.argv.slice(2);
const plan = args.find(a => a.endsWith('.md'));
const PRINT = args.includes('--print');
const RUN_ONLY = args.includes('--run-only');

if (!plan || !existsSync(plan)) {
  console.error('Usage: npm run plan plans/<name>.md [-- --print | --run-only]');
  process.exit(1);
}
const name = slug(plan);
const url = urlFor(plan);
if (!url) {
  console.error(`No URL for ${plan}. Add "**URL:** https://..." to the plan, set BASE_URL, or set defaultUrl in agentic.config.json.`);
  process.exit(1);
}
const out = `${config.outputDir}/${name}`;

const prompt = `Follow prompts/agent.md for the plan ${plan}.
Name: ${name}
URL: ${url}
Output folder: ${out}/
Use the Playwright generator agent to write the tests and the healer agent to fix failures, if available.`;

if (PRINT) {
  console.log(prompt);
  process.exit(0);
}

const env = { ...process.env, BASE_URL: url };
const run = (cmd, a, opts = {}) => spawnSync(cmd, a, { stdio: 'inherit', env, ...opts });

console.log(`\nPlan: ${plan}\nURL:  ${url}\nOut:  ${out}/\n`);

if (!RUN_ONLY) {
  if (run('npx', ['playwright', 'test', '--project=seed']).status !== 0) {
    console.error('\nSeed failed: the URL could not be opened. Fix that first.');
    process.exit(1);
  }
  if (spawnSync('claude', ['--version'], { stdio: 'ignore' }).status !== 0) {
    console.error('\nClaude Code not found. Either install it (npm i -g @anthropic-ai/claude-code)\n' +
                  'or run with --print and paste the prompt into Devin / another agent.');
    process.exit(1);
  }
  mkdirSync(out, { recursive: true });
  run('claude', [
    '-p', prompt,
    '--permission-mode', 'acceptEdits',
    '--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash(npx playwright:*),Bash(npx tsc:*),mcp__playwright-test',
  ]);
}

console.log('\n── Final run ──');
const res = run('npx', ['playwright', 'test', `--project=${name}`]);
console.log(`\nReport: npm run report   (HTML)   •   JUnit: test-results/results.xml`);
process.exit(res.status ?? 1);

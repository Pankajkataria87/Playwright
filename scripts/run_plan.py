#!/usr/bin/env python3
"""Turn Markdown plans into Playwright tests with an AI agent, run them, report.

  npm run plan KAN-1                                # plan fetched from Jira issue KAN-1 (scripts/jira_plan.py)
  npm run plan plans/login.md                       # one plan
  npm run plan plans/login.md plans/checkout.md     # several plans
  npm run plan plans/QA-42/                         # every plan in a folder (recursive)
  npm run plan -- --all                             # every plan in plans/
  ... -- --print       print the prompt(s) instead (paste into Devin / any agent)
  ... -- --run-only    skip generation, just run existing tests
  ... -- --no-jira-report   don't post results back to the Jira issue(s) (scripts/jira_report.py)
  BASE_URL=https://staging.x.com npm run plan ...   # override every plan's URL
  npm run validate     check plans against plans/_template.md (done here too, before anything runs)
  npm run pii          check for PII (done here too: a plan with PII is never sent to an agent)
  npm run usage        tokens/cost per plan for every execution (logged to reports/agent-usage.jsonl)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
sys.stdout.reconfigure(line_buffering=True)

from jira_plan import JiraError, JiraRejected, fetch_plan, is_key  # noqa: E402
from jira_report import post_rejection, post_report  # noqa: E402
from pii import find_pii, pii_message  # noqa: E402
from plans import all_plans, config, read, resolve_plans, slug, url_for  # noqa: E402
from usage import USAGE_LOG, append_usage, print_usage, tokens_from  # noqa: E402
from validate_plan import rejection, validate_plan  # noqa: E402


def fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


args = sys.argv[1:]
PRINT = '--print' in args
RUN_ONLY = '--run-only' in args
JIRA_REPORT = '--no-jira-report' not in args


def reject(msg: str, per_key: dict[str, str] | None = None) -> None:
    """Stop the run; for plans from Jira, also comment the reason on each rejected issue."""
    print(msg, file=sys.stderr)
    for key, why in (per_key or {}).items() if JIRA_REPORT else ():
        try:
            print(post_rejection(key, why), file=sys.stderr)
        except JiraError as e:
            print(f'Jira rejection not posted: {e}', file=sys.stderr)
    sys.exit(1)


jira_plans: dict[str, str] = {}
for a in [a for a in args if is_key(a)]:
    try:
        jira_plans[a] = fetch_plan(a)
    except JiraRejected as e:
        reject(str(e), {a: str(e)})
    except JiraError as e:
        fail(str(e))
fetched = list(jira_plans.values())
plans = all_plans() if '--all' in args else resolve_plans(
    [a for a in args if not a.startswith('--') and not is_key(a)] + fetched)

if not plans:
    fail('No plans found.\nUsage: npm run plan <JIRA-KEY | plan.md | folder>... [-- --all --print --run-only]')

# Reject the whole execution if any plan deviates from plans/_template.md, before any agent time.
deviations = [e for p in plans for e in validate_plan(p)]
if deviations:
    reject(rejection(deviations),
           {k: rejection(errs) for k, p in jira_plans.items() if (errs := validate_plan(p))})

# Never send a plan containing PII to an agent (pii-guard skill). Values are masked, also in Jira comments.
pii = [{**h, 'where': p} for p in plans for h in find_pii(read(p))]
if pii:
    reject(pii_message(pii),
           {k: pii_message(hits) for k, p in jira_plans.items() if (hits := [h for h in pii if h['where'] == p])})

jobs = [{'plan': p, 'name': slug(p), 'url': url_for(p), 'out': f"{config['outputDir']}/{slug(p)}"} for p in plans]
missing = [j['plan'] for j in jobs if not j['url']]
if missing:
    fail('No URL for: ' + ', '.join(missing) +
         '\nAdd "**URL:** https://..." to the plan, set BASE_URL, or set defaultUrl in agentic.config.json.')


def prompt_for(j: dict) -> str:
    return (f"Follow prompts/agent.md for the plan {j['plan']}.\n"
            f"Name: {j['name']}\n"
            f"URL: {j['url']}\n"
            f"Output folder: {j['out']}/\n"
            'Use the Playwright generator agent to write the tests and the healer agent to fix failures, if available.')


projects = [f"--project={j['name']}" for j in jobs]

# --print: one prompt covering all plans, ready to paste into Devin / any agent.
if PRINT:
    if len(jobs) == 1:
        print(prompt_for(jobs[0]))
    else:
        print('Follow prompts/agent.md for each plan below, one after another.\n'
              'Reuse page objects between plans that share a URL host.\n'
              f"At the end, run: npx playwright test {' '.join(projects)}\n"
              'and report one table per plan.\n')
        for j in jobs:
            print(f"- {j['plan']} → name: {j['name']}, URL: {j['url']}, output: {j['out']}/")
    sys.exit(0)


def run(cmd: list[str], env: dict | None = None) -> int:
    return subprocess.run(cmd, env={**os.environ, **(env or {})}).returncode


def run_agent(j: dict) -> tuple[int, dict | None]:
    """Runs Claude Code with streamed JSON so progress is shown live and the final
    `result` event (tokens, cost, turns) can be captured."""
    cmd = ['claude', '-p', prompt_for(j), '--output-format', 'stream-json', '--verbose',
           '--permission-mode', 'acceptEdits',
           '--allowedTools', 'Read,Edit,Write,Glob,Grep,Bash(npx playwright:*),Bash(npx tsc:*),mcp__playwright-test']
    try:
        child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
                                 env={**os.environ, 'BASE_URL': j['url']})
    except OSError as e:
        return 1, {'is_error': True, 'result': str(e)}
    result = None
    for line in child.stdout:
        line = line.rstrip('\n')
        try:
            ev = json.loads(line)
        except ValueError:
            print(line)
            continue
        if not isinstance(ev, dict):
            print(line)
        elif ev.get('type') == 'result':
            result = ev
        elif ev.get('type') == 'assistant':
            for c in (ev.get('message') or {}).get('content') or []:
                if c.get('type') == 'text' and (c.get('text') or '').strip():
                    print(c['text'].strip())
                elif c.get('type') == 'tool_use':
                    print(f"  · {c.get('name')}")
    return child.wait(), result


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def claude_installed() -> bool:
    try:
        return subprocess.run(['claude', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


execution = now()
usage: list[dict] = []

print(f'\n{len(jobs)} plan(s):')
for j in jobs:
    print(f"  • {j['plan']}  →  {j['out']}/  ({j['url']})")

if not RUN_ONLY:
    if not claude_installed():
        fail('\nClaude Code not found. Install it (npm i -g @anthropic-ai/claude-code)\n'
             'or use --print and paste the prompt into Devin / another agent.')
    # Check each distinct URL opens once, before spending agent time.
    for url in dict.fromkeys(j['url'] for j in jobs):
        print(f'\n── Seed check: {url}')
        if run(['npx', 'playwright', 'test', '--project=seed'], {'BASE_URL': url}) != 0:
            fail(f'Seed failed: {url} could not be opened. Fix that first.')
    # Plans run one after another so later plans can reuse page objects from earlier ones.
    for j in jobs:
        print(f"\n── Generating: {j['plan']}")
        os.makedirs(j['out'], exist_ok=True)
        code, result = run_agent(j)
        ok = code == 0 and bool(result) and not result.get('is_error')
        r = result or {}
        entry = {
            'run': execution, 'at': now(), 'plan': j['plan'], 'name': j['name'], 'agent': 'claude-code',
            'session': r.get('session_id'), 'models': list((r.get('modelUsage') or {}).keys()),
            **tokens_from(result), 'costUsd': r.get('total_cost_usd') or 0,
            'turns': r.get('num_turns') or 0, 'durationMs': r.get('duration_ms') or 0, 'ok': ok,
        }
        if not ok:
            entry['error'] = r.get('result') or f'claude exited with code {code}'
        append_usage(entry)
        usage.append(entry)
        if not ok:
            print(f"Agent failed for {j['plan']}: {entry['error']}", file=sys.stderr)

print('\n── Final run (all selected plans) ──')
status = run(['npx', 'playwright', 'test', *projects])
if usage:
    print(f'\n── Agent usage (this execution, logged to {USAGE_LOG}) ──')
    print_usage(usage)
print('\nReport: npm run report   (HTML, grouped by plan/project)   •   JUnit: test-results/results.xml')
# Plans that came from Jira get their results posted back to the same issue (pass or fail).
if JIRA_REPORT and jira_plans:
    print('\n── Jira report ──')
    for key, path in jira_plans.items():
        try:
            print(post_report(key, slug(path), url_for(path)))
        except JiraError as e:
            print(f'Jira report not posted: {e}', file=sys.stderr)
sys.exit(status)

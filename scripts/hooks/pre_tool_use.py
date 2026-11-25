#!/usr/bin/env python3
"""Claude Code PreToolUse hook (registered in .claude/settings.json).
Blocks the agent from reading, writing tests for, or running a plan that doesn't follow
plans/_template.md, and from writing a new plan that doesn't. Exit 2 = block; stderr goes to the agent.
"""
import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from plans import config, all_plans, slug  # noqa: E402
from validate_plan import validate_plan, rejection  # noqa: E402

ev = json.loads(sys.stdin.read() or '{}')
tool = ev.get('tool_name')
inp = ev.get('tool_input') or {}
plans_dir, out_dir = config['plansDir'], config['outputDir']


def posix(p):
    return p.replace(os.sep, '/')


def rel(f):
    return posix(os.path.relpath(os.path.abspath(f)))


def is_plan_path(f):
    return f.startswith(f'{plans_dir}/') and f.endswith('.md') and not any(s.startswith('_') for s in f.split('/'))


by_slug = {slug(p): posix(p) for p in all_plans()}

errors = []
if tool in ('Read', 'Write', 'Edit', 'MultiEdit') and inp.get('file_path'):
    f = rel(inp['file_path'])
    if is_plan_path(f):
        if tool == 'Read' and os.path.exists(f):
            errors = validate_plan(f)
        if tool == 'Write':
            errors = validate_plan(f, inp.get('content') or '')
        # Edit/MultiEdit stay allowed so a plan can be fixed; it is checked again when read or run.
    elif f.startswith(f'{out_dir}/'):
        plan = by_slug.get(f[len(out_dir) + 1:].split('/')[0])
        if plan:
            errors = validate_plan(plan)

cmd = inp.get('command') or ''
if tool == 'Bash' and re.search(r'playwright\s+test\b', cmd):
    projects = re.findall(r'--project[= ]["\']?([\w.-]+)', cmd, re.ASCII)
    named = projects or [n for n in by_slug if f'{out_dir}/{n}' in cmd]
    plans = [by_slug[n] for n in named if n in by_slug] if named else list(by_slug.values())
    errors = [e for p in plans for e in validate_plan(p)]

if errors:
    sys.stderr.write(f'{rejection(errors)}\nStop and report these deviations to the user. Do not work around this check.\n')
    sys.exit(2)

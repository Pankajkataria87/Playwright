#!/usr/bin/env python3
"""Deterministic check that a QA plan follows plans/_template.md (no AI involved).
Used by `npm run plan`, the Claude Code PreToolUse hook (scripts/hooks/pre_tool_use.py) and:
  npm run validate                  # every plan
  npm run validate plans/IR-1020/   # files and/or folders
"""
from __future__ import annotations

import re
import sys

from plans import all_plans, read, resolve_plans

TEMPLATE = 'plans/_template.md'
HEADER_FIELDS = ['URL', 'Starting state']
TABLE_HEADER = ['Field', 'Input', 'Expected']


def cells(line: str) -> list[str]:
    return [c.strip() for c in re.sub(r'^\||\|$', '', line.strip()).split('|')]


def validate_plan(path: str, text: str | None = None) -> list[str]:
    """Returns "file:line  problem" strings; empty means the plan is valid."""
    if text is None:
        text = read(path)
    errors: list[str] = []

    def err(n: int, msg: str) -> None:
        errors.append(f'{path}:{n}  {msg}')

    # Drop HTML comments but keep their line breaks so line numbers stay right.
    lines = re.sub(r'<!--[\s\S]*?-->', lambda m: re.sub(r'[^\n]', '', m.group()), text).split('\n')
    header: dict = {}
    scenarios: list[dict] = []
    title, section, fields, scenario = False, 'header', None, None

    def close(s: dict | None) -> None:
        if not s:
            return
        if not s['steps']:
            err(s['line'], f"scenario {s['no']}: needs \"**Steps:**\" with at least one numbered step")
        if not s['expected']:
            err(s['line'], f"scenario {s['no']}: needs \"**Expected:**\" with at least one \"- \" bullet")

    for i, raw in enumerate(lines):
        n, line = i + 1, raw.rstrip()
        if not line.strip():
            continue
        if re.search(r'<[^<>]+>', re.sub(r'`[^`]*`', '', line)):
            err(n, f'unfilled placeholder: {line.strip()}')
        if not title:
            title = True
            if re.match(r'# \S', line):
                continue
            err(n, 'the first line must be "# <Feature name>"')
        if line.startswith('# '):
            err(n, 'only one "# Title" is allowed')
            continue
        m = re.match(r'## (.+)', line)
        if m:
            close(scenario)
            scenario = None
            if re.match(r'Field checks\b', m.group(1), re.I):
                if fields or scenarios:
                    err(n, '"## Field checks" may appear once, before the scenarios')
                fields = {'line': n, 'header': False, 'rows': 0}
                section = 'fields'
            else:
                section = 'scenarios'
            continue
        m = re.match(r'###(.*)', line)
        if m:
            close(scenario)
            scenario = None
            if section != 'scenarios':
                err(n, 'scenarios must be under a "## Scenarios" (or other "##" group) heading')
            s = re.fullmatch(r' (\d+)\. (\S.*)', m.group(1))
            if not s:
                err(n, 'scenario heading must be "### <number>. <name>"')
                continue
            if int(s.group(1)) != len(scenarios) + 1:
                err(n, f'scenario is numbered {s.group(1)}, expected {len(scenarios) + 1} (1, 2, 3... with no gaps)')
            scenario = {'no': s.group(1), 'line': n, 'part': None, 'steps': 0, 'expected': 0}
            scenarios.append(scenario)
            continue
        if line.startswith('#'):
            err(n, 'only "#", "##" and "### N. Name" headings are allowed')
            continue

        if section == 'header':
            m = re.fullmatch(r'\*\*([^*]+):\*\*(.*)', line)
            if not m or m.group(1) not in HEADER_FIELDS:
                allowed = ' and '.join(f'"**{f}:**"' for f in HEADER_FIELDS)
                err(n, f'unexpected line in the header; only {allowed} are allowed')
                continue
            if m.group(1) in header:
                err(n, f'"**{m.group(1)}:**" appears twice')
            header[m.group(1)] = {'value': m.group(2).strip(), 'line': n}
            continue

        if section == 'fields':
            if not line.startswith('|'):
                err(n, 'only the table is allowed under "## Field checks"')
                continue
            if not fields['header']:
                fields['header'] = True
                if cells(line) != TABLE_HEADER:
                    err(n, f'table header must be "| {" | ".join(TABLE_HEADER)} |"')
                continue
            if re.fullmatch(r'\|[\s:|-]+\|', line):
                continue
            c = cells(line)
            if len(c) != 3 or not all(c):
                err(n, 'each row needs 3 filled cells: | Field | Input | Expected |')
                continue
            fields['rows'] += 1
            continue

        if not scenario:
            err(n, 'text outside a scenario; under a "##" heading only "### N. Name" scenarios are allowed')
            continue
        if line == '**Steps:**':
            if scenario['part']:
                err(n, '"**Steps:**" must come first and only once')
            scenario['part'] = 'steps'
            continue
        if line == '**Expected:**':
            if scenario['part'] != 'steps':
                err(n, '"**Expected:**" must come after "**Steps:**" and only once')
            scenario['part'] = 'expected'
            continue
        m = re.match(r'(\d+)\. \S', line)
        if scenario['part'] == 'steps' and m:
            if int(m.group(1)) != scenario['steps'] + 1:
                err(n, f"step is numbered {m.group(1)}, expected {scenario['steps'] + 1}")
            scenario['steps'] += 1
            continue
        if scenario['part'] == 'expected' and re.match(r'- \S', line):
            scenario['expected'] += 1
            continue
        if re.match(r'\s+\S', line) and (scenario['steps'] or scenario['expected']):
            continue  # wrapped line
        err(n, 'under "**Steps:**" only numbered steps ("1. ...") are allowed' if scenario['part'] == 'steps'
            else 'under "**Expected:**" only bullets ("- ...") are allowed' if scenario['part'] == 'expected'
            else 'a scenario must start with "**Steps:**"')
    close(scenario)

    if not title:
        err(1, 'the plan is empty')
    if 'URL' not in header:
        err(1, 'missing "**URL:** https://..." in the header')
    elif not re.fullmatch(r'https?://\S+', header['URL']['value']):
        err(header['URL']['line'], '"**URL:**" must be a single http(s) URL')
    start = header.get('Starting state')
    if not (start and start['value']):
        err(start['line'] if start else 1, 'missing or empty "**Starting state:**" in the header')
    if fields and not fields['rows']:
        err(fields['line'], '"## Field checks" needs at least one row (or delete the section)')
    if not scenarios:
        err(len(lines), 'no scenarios; add "## Scenarios" with "### 1. <name>"')
    return errors


def rejection(errors: list[str]) -> str:
    count = len({e.split(':')[0] for e in errors})
    return (f'Rejected: {count} plan(s) do not follow {TEMPLATE}. Fix these and run again:\n'
            + '\n'.join(f'  {e}' for e in errors))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    plans = resolve_plans(args) if args else all_plans()
    if not plans:
        print('No plans found.', file=sys.stderr)
        sys.exit(1)
    errors = [e for p in plans for e in validate_plan(p)]
    if errors:
        print(rejection(errors), file=sys.stderr)
        sys.exit(1)
    print(f'OK: {len(plans)} plan(s) follow {TEMPLATE}\n' + '\n'.join(f'  {p}' for p in plans))


if __name__ == '__main__':
    main()

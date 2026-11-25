"""Shared helpers: find plans and read the URL from each plan's header.

  python3 scripts/plans.py --json   # config + every plan (read by playwright.config.ts)
"""
from __future__ import annotations

import json
import os
import re
import sys

with open('agentic.config.json', encoding='utf-8') as _f:
    config: dict = json.load(_f)


def read(path: str) -> str:
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def url_for(plan_path: str) -> str:
    """URL priority: BASE_URL env  >  "**URL:**" line in the plan  >  defaultUrl in agentic.config.json"""
    if os.environ.get('BASE_URL'):
        return os.environ['BASE_URL']
    m = re.search(r'^\*\*URL:\*\*\s*(\S+)', read(plan_path), re.M | re.I)
    return (m and m.group(1)) or config.get('defaultUrl') or ''


def slug(plan_path: str) -> str:
    """plans/login.md -> "login";  plans/QA-42/billing-tab.md -> "qa-42-billing-tab" """
    s = os.path.relpath(plan_path, config['plansDir']).replace(os.sep, '/')
    s = re.sub(r'\.md$', '', s, flags=re.I).lower()
    return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', s))


def is_plan(f: str) -> bool:
    return f.endswith('.md') and not re.split(r'[\\/]', f)[-1].startswith('_')


def plans_in(d: str) -> list[str]:
    """Plans inside a folder (recursive), skipping files/folders that start with "_"."""
    if not os.path.exists(d):
        return []
    found: list[str] = []
    for f in sorted(os.listdir(d)):
        if f.startswith('_'):
            continue
        p = os.path.normpath(os.path.join(d, f))
        if os.path.isdir(p):
            found += plans_in(p)
        elif is_plan(p):
            found.append(p)
    return sorted(found)


def all_plans() -> list[str]:
    return plans_in(config['plansDir'])


def resolve_plans(args: list[str]) -> list[str]:
    """Expand CLI args (files and/or folders) into a list of plan files."""
    found: list[str] = []
    for a in args:
        if os.path.isdir(a):
            found += plans_in(a)
        elif is_plan(a) and os.path.exists(a):
            found.append(a)
    return list(dict.fromkeys(found))


if __name__ == '__main__' and '--json' in sys.argv:
    plans = [{'plan': p, 'name': slug(p), 'url': url_for(p)} for p in all_plans()]
    json.dump({'config': config, 'plans': plans}, sys.stdout)

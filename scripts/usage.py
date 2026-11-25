#!/usr/bin/env python3
"""Token/cost log for agent runs. run_plan.py appends one line per plan per execution.

  npm run usage                         # every execution, newest last
  npm run usage -- --last 5             # last 5 executions
  npm run usage -- --plan ir-1020-todo  # one plan only
"""
from __future__ import annotations

import json
import os
import sys

USAGE_LOG = 'reports/agent-usage.jsonl'


def tokens_from(result: dict | None) -> dict:
    """Token counts from a Claude Code `result` event (summed over all models, incl. subagents)."""
    result = result or {}
    models = list((result.get('modelUsage') or {}).values())
    if models:
        def total(k: str) -> int:
            return sum(m.get(k) or 0 for m in models)
        return {'input': total('inputTokens'), 'output': total('outputTokens'),
                'cacheWrite': total('cacheCreationInputTokens'), 'cacheRead': total('cacheReadInputTokens')}
    u = result.get('usage') or {}
    return {'input': u.get('input_tokens') or 0, 'output': u.get('output_tokens') or 0,
            'cacheWrite': u.get('cache_creation_input_tokens') or 0, 'cacheRead': u.get('cache_read_input_tokens') or 0}


def append_usage(entry: dict) -> None:
    os.makedirs(os.path.dirname(USAGE_LOG), exist_ok=True)
    with open(USAGE_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')


def read_usage() -> list[dict]:
    if not os.path.exists(USAGE_LOG):
        return []
    with open(USAGE_LOG, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def total_tokens(e: dict) -> int:
    return e['input'] + e['output'] + e['cacheWrite'] + e['cacheRead']


def num(n: float) -> str:
    return f'{n:,}'


def usd(n: float) -> str:
    return f'${n:.4f}'


def secs(ms: float) -> str:
    return f'{int(ms / 1000 + 0.5)}s'


def table(rows: list[dict]) -> None:
    cols = list(rows[0])
    width = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]

    def line(r: dict) -> str:
        return '  '.join(str(r[c]).ljust(w) for c, w in zip(cols, width))
    print(line({c: c for c in cols}))
    print('  '.join('-' * w for w in width))
    for r in rows:
        print(line(r))


def print_usage(entries: list[dict]) -> None:
    """Print one row per plan plus a total row for the given entries."""
    if not entries:
        print('No agent usage recorded.')
        return
    rows = [{
        'plan': e['name'], 'status': 'ok' if e['ok'] else 'error', 'turns': e['turns'],
        'input': num(e['input']), 'output': num(e['output']), 'cache write': num(e['cacheWrite']),
        'cache read': num(e['cacheRead']), 'total tokens': num(total_tokens(e)), 'cost': usd(e['costUsd']),
        'time': secs(e['durationMs']),
    } for e in entries]
    if len(entries) > 1:
        def s(k: str) -> float:
            return sum(e[k] for e in entries)
        rows.append({'plan': 'TOTAL', 'status': '', 'turns': s('turns'), 'input': num(s('input')),
                     'output': num(s('output')), 'cache write': num(s('cacheWrite')), 'cache read': num(s('cacheRead')),
                     'total tokens': num(sum(total_tokens(e) for e in entries)), 'cost': usd(s('costUsd')),
                     'time': secs(s('durationMs'))})
    table(rows)
    for e in entries:
        if e.get('error'):
            print(f"  ! {e['name']}: {e['error']}")


def main() -> None:
    args = sys.argv[1:]

    def opt(k: str) -> str | None:
        return args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None
    entries = read_usage()
    if opt('--plan'):
        entries = [e for e in entries if e['name'] == opt('--plan')]
    runs = list(dict.fromkeys(e['run'] for e in entries))
    shown = runs[-int(opt('--last')):] if opt('--last') else runs
    if not shown:
        print(f'No agent usage recorded in {USAGE_LOG}.')
    for run in shown:
        print(f'\nExecution {run}')
        print_usage([e for e in entries if e['run'] == run])


if __name__ == '__main__':
    main()

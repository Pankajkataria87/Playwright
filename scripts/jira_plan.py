#!/usr/bin/env python3
"""Fetch a plan from a Jira issue. Jira is the source; plans/<KEY>.md is a local copy (gitignored).

  npm run jira KAN-1              # fetch only
  npm run plan KAN-1              # fetch, validate, PII-check, generate, run (see run_plan.py)

The plan is the issue description's code block, written in the plans/_template.md format.
Site: "jiraBaseUrl" in agentic.config.json (or JIRA_BASE_URL).
Credentials: JIRA_EMAIL and JIRA_API_TOKEN, from the environment or .env.local (gitignored).
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
from plans import config  # noqa: E402

KEY_RE = re.compile(r'^[A-Z][A-Z0-9]+-\d+$')
TOKEN_URL = 'https://id.atlassian.com/manage-profile/security/api-tokens'


class JiraError(Exception):
    pass


class JiraRejected(JiraError):
    """The issue was read, but its plan may not be automated (status, no plan code block)."""


def is_key(arg: str) -> bool:
    return bool(KEY_RE.match(arg))


def env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    if os.path.exists('.env.local'):
        with open('.env.local', encoding='utf-8') as f:
            for line in f:
                k, _, v = line.strip().partition('=')
                if k.strip().removeprefix('export ').strip() == name:
                    return v.strip().strip('"\'')
    return ''


def site() -> str:
    return (env('JIRA_BASE_URL') or config.get('jiraBaseUrl') or '').rstrip('/')


def jira_api(key: str, method: str, path: str, data: bytes | None = None, headers: dict | None = None,
             timeout: int = 30) -> dict | list:
    """Call the Jira Cloud REST API v3 (path relative to /rest/api/3) with JIRA_EMAIL / JIRA_API_TOKEN."""
    base = site()
    email, token = env('JIRA_EMAIL'), env('JIRA_API_TOKEN')
    if not base:
        raise JiraError('No Jira site: set "jiraBaseUrl" in agentic.config.json or JIRA_BASE_URL.')
    if not (email and token):
        raise JiraError('Missing JIRA_EMAIL / JIRA_API_TOKEN (environment or .env.local).\n'
                        f'Create a token at {TOKEN_URL}')
    auth = base64.b64encode(f'{email}:{token}'.encode()).decode()
    req = urllib.request.Request(f'{base}/rest/api/3{path}', data=data, method=method,
                                 headers={'Accept': 'application/json', 'Authorization': f'Basic {auth}',
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        hint = {401: 'check JIRA_EMAIL / JIRA_API_TOKEN', 403: 'no permission',
                404: 'issue does not exist or you cannot see it',
                413: 'attachment too large for your Jira site'}.get(e.code, '')
        raise JiraError(f'Jira {key}: HTTP {e.code} {hint}'.rstrip()) from None
    except urllib.error.URLError as e:
        raise JiraError(f'Jira {key}: cannot reach {base} ({e.reason})') from None


def fetch_issue(key: str) -> dict:
    return jira_api(key, 'GET', f'/issue/{key}?fields=summary,description,updated,status')


def required_status() -> str:
    """Only issues in this status are automated ("jiraRequiredStatus"; JIRA_REQUIRED_STATUS overrides; empty = any)."""
    return env('JIRA_REQUIRED_STATUS') or config.get('jiraRequiredStatus', '')


def check_status(key: str, fields: dict) -> None:
    want, status = required_status(), ((fields.get('status') or {}).get('name') or '')
    if want and status.casefold() != want.casefold():
        raise JiraRejected(f'Rejected: Jira {key} is in status "{status}"; only issues in "{want}" can be automated.\n'
                        f'Move {key} to "{want}" in Jira, then run again.')


def text_of(node: dict) -> str:
    if node.get('type') == 'text':
        return node.get('text', '')
    if node.get('type') == 'hardBreak':
        return '\n'
    return ''.join(text_of(c) for c in node.get('content') or [])


def plan_from(key: str, description: dict | None) -> str:
    blocks = [b for b in (description or {}).get('content') or [] if b.get('type') == 'codeBlock']
    if not blocks:
        raise JiraRejected(f'Rejected: Jira {key}: the description has no code block. '
                        'Paste the plan (plans/_template.md format) into a code block in the description.')
    text = re.sub(r'^```\w*\n|\n```\s*$', '', text_of(blocks[0]).strip())
    return text.rstrip() + '\n'


def fetch_plan(key: str) -> str:
    """Fetch KEY's plan into plans/<KEY>.md and return that path."""
    issue = fetch_issue(key)
    fields = issue.get('fields') or {}
    path = os.path.join(config['plansDir'], f'{key}.md')
    try:
        check_status(key, fields)
    except JiraError:
        if os.path.exists(path):
            os.remove(path)  # stale copy would keep the project runnable via plain `npx playwright test`
        raise
    text = plan_from(key, fields.get('description'))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Jira {key} \"{fields.get('summary', '')}\" (updated {fields.get('updated', '?')}) → {path}")
    return path


if __name__ == '__main__':
    keys = sys.argv[1:]
    if not keys or not all(is_key(k) for k in keys):
        print('Usage: npm run jira <KEY>...   e.g. npm run jira KAN-1', file=sys.stderr)
        sys.exit(1)
    try:
        for k in keys:
            fetch_plan(k)
    except JiraError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
"""Post the last Playwright run's results to the Jira issue the plan came from.

  npm run jira-report KAN-1                   # results of project kan-1 from the last run
  npm run jira-report KAN-1 -- --project=x    # another project name
  npm run plan KAN-1                          # does this automatically after the final run (--no-jira-report to skip)

Adds one comment (summary + per-scenario table) and attaches the zipped HTML report, plus the
screenshots/videos Playwright recorded (failed tests first; capped by MAX_FILES / MAX_BYTES).
Reads test-results/results.json (json reporter in playwright.config.ts). No AI is involved.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import socket
import sys
import uuid
from datetime import datetime, timezone

sys.dont_write_bytecode = True
from jira_plan import JiraError, is_key, jira_api, site  # noqa: E402
from plans import config  # noqa: E402

RESULTS = 'test-results/results.json'
HTML_REPORT = 'playwright-report'
OUT_DIR = 'reports/jira'
MAX_FILES = 20
MAX_BYTES = 50 * 1024 * 1024
ANSI = re.compile(r'\x1b\[[0-9;]*m')
LABEL = {'passed': 'pass', 'failed': 'FAIL', 'flaky': 'flaky', 'skipped': 'skipped'}


def outcome(test: dict) -> str:
    status = test.get('status')
    if status == 'unexpected':
        return 'failed'
    if status == 'flaky':
        return 'flaky'
    if status == 'skipped' or test.get('expectedStatus') == 'skipped':
        return 'skipped'
    return 'passed'


def collect(results: dict, project: str) -> list[dict]:
    """One row per test title in `project`, merging repeats (--repeat-each) into one row."""
    rows: dict[str, dict] = {}

    def walk(suite: dict, path: list[str]) -> None:
        for spec in suite.get('specs') or []:
            for t in spec.get('tests') or []:
                if t.get('projectName') != project:
                    continue
                row = rows.setdefault(spec['title'], {'title': spec['title'], 'group': ' › '.join(path),
                                                      'counts': {}, 'error': '', 'files': [], 'ms': 0})
                o = outcome(t)
                row['counts'][o] = row['counts'].get(o, 0) + 1
                for r in t.get('results') or []:
                    row['ms'] += r.get('duration') or 0
                    err = (r.get('error') or {}).get('message') or ''
                    if err and not row['error']:
                        row['error'] = ANSI.sub('', err).strip().splitlines()[0][:200]
                    for a in r.get('attachments') or []:
                        if a.get('path') and (a.get('contentType') or '').split('/')[0] in ('image', 'video'):
                            row['files'].append({'path': a['path'], 'failed': o == 'failed', 'title': spec['title']})
        for child in suite.get('suites') or []:
            walk(child, path + [child.get('title', '')])

    for s in results.get('suites') or []:
        walk(s, [])
    return list(rows.values())


def row_result(row: dict) -> str:
    c = row['counts']
    for k in ('failed', 'flaky', 'passed', 'skipped'):
        if c.get(k):
            total = sum(c.values())
            return LABEL[k] if total == 1 else f"{LABEL[k]} ({c[k]}/{total})"
    return '?'


def safe_name(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '-', s).strip('-')[:60]


def pick_files(rows: list[dict], key: str) -> list[tuple[str, str]]:
    """(path on disk, upload name); failed tests' evidence first."""
    files = sorted((f for r in rows for f in r['files'] if os.path.exists(f['path'])), key=lambda f: not f['failed'])
    picked, size, seen = [], 0, set()
    for f in files:
        n = os.path.getsize(f['path'])
        if len(picked) >= MAX_FILES or size + n > MAX_BYTES or f['path'] in seen:
            continue
        seen.add(f['path'])
        size += n
        ext = os.path.splitext(f['path'])[1]
        picked.append((f['path'], f"{key}-{safe_name(f['title'])}-{len(picked) + 1}{ext}"))
    return picked


def zip_report(key: str, stamp: str) -> str | None:
    if not os.path.isdir(HTML_REPORT):
        return None
    os.makedirs(OUT_DIR, exist_ok=True)
    return shutil.make_archive(os.path.join(OUT_DIR, f'{key}-playwright-report-{stamp}'), 'zip', HTML_REPORT)


def upload(key: str, files: list[tuple[str, str]]) -> list[str]:
    """POST /issue/{key}/attachments (multipart, X-Atlassian-Token: no-check)."""
    if not files:
        return []
    boundary = uuid.uuid4().hex
    body = bytearray()
    for path, name in files:
        ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                 f'Content-Type: {ctype}\r\n\r\n').encode()
        with open(path, 'rb') as f:
            body += f.read()
        body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    res = jira_api(key, 'POST', f'/issue/{key}/attachments', bytes(body),
                   {'X-Atlassian-Token': 'no-check', 'Content-Type': f'multipart/form-data; boundary={boundary}'},
                   timeout=300)
    return [a.get('filename', '') for a in res] if isinstance(res, list) else [n for _, n in files]


def text(s: str, bold: bool = False) -> dict:
    node = {'type': 'text', 'text': s}
    if bold:
        node['marks'] = [{'type': 'strong'}]
    return node


def para(*nodes: dict) -> dict:
    return {'type': 'paragraph', 'content': [n for n in nodes if n.get('text')]}


def cell(s: str, header: bool = False) -> dict:
    return {'type': 'tableHeader' if header else 'tableCell', 'content': [para(text(s, header))]}


def comment_body(project: str, rows: list[dict], stats: dict, url: str, attached: list[str]) -> dict:
    totals: dict[str, int] = {}
    for r in rows:
        for k, v in r['counts'].items():
            totals[k] = totals.get(k, 0) + v
    failed = totals.get('failed', 0)
    verdict = 'FAILED' if failed else 'PASSED'
    summary = ', '.join(f'{v} {k}' for k, v in totals.items()) or 'no tests'
    secs = (stats.get('duration') or 0) / 1000
    started = stats.get('startTime', '')
    header = ['#', 'Scenario', 'Result', 'Notes']
    table = {'type': 'table', 'attrs': {'isNumberColumnEnabled': False, 'layout': 'default'},
             'content': [{'type': 'tableRow', 'content': [cell(h, True) for h in header]}]}
    for i, r in enumerate(rows, 1):
        notes = r['error'] if r['counts'].get('failed') or r['counts'].get('flaky') else ''
        table['content'].append({'type': 'tableRow', 'content': [
            cell(str(i)), cell(r['title']), cell(row_result(r)), cell(notes)]})
    content = [
        {'type': 'heading', 'attrs': {'level': 3},
         'content': [text(f'Playwright results: {verdict} ({summary}, {secs:.1f}s)')]},
        para(text('Project: ', True), text(project), text('   URL: ', True), text(url or '-'),
             text('   Run: ', True), text(started), text('   Host: ', True), text(socket.gethostname())),
        table,
    ]
    if attached:
        content.append(para(text('Attached: ', True), text(', '.join(attached))))
    content.append(para(text('Posted automatically by agentic-playwright (scripts/jira_report.py).')))
    return {'type': 'doc', 'version': 1, 'content': content}


def post_report(key: str, project: str, url: str = '') -> str:
    """Comment + attachments on `key` for `project` from the last run. Returns a one-line summary."""
    if not os.path.exists(RESULTS):
        raise JiraError(f'Jira {key}: no {RESULTS}; run the tests first.')
    with open(RESULTS, encoding='utf-8') as f:
        results = json.load(f)
    rows = collect(results, project)
    if not rows:
        raise JiraError(f'Jira {key}: the last run has no results for project "{project}".')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    files = pick_files(rows, key)
    report = zip_report(key, stamp)
    if report:
        files.insert(0, (report, os.path.basename(report)))
    attached = upload(key, files)
    res = jira_api(key, 'POST', f'/issue/{key}/comment',
                   json.dumps({'body': comment_body(project, rows, results.get('stats') or {}, url, attached)}).encode(),
                   {'Content-Type': 'application/json'})
    link = f"{site()}/browse/{key}?focusedCommentId={res.get('id', '')}" if isinstance(res, dict) else key
    return f'Jira {key}: results comment + {len(attached)} attachment(s) posted → {link}'


def post_rejection(key: str, message: str) -> str:
    """Comment on `key` why `npm run plan` rejected it (status, template, PII; PII values are already masked)."""
    lines = [ln.replace(f"{config['plansDir']}/{key}.md:", 'plan line ') for ln in message.strip().splitlines()]
    body = {'type': 'doc', 'version': 1, 'content': [
        {'type': 'heading', 'attrs': {'level': 3}, 'content': [text('Automation rejected: tests were not generated or run')]},
        para(text(lines[0])),
        *([{'type': 'codeBlock', 'content': [text('\n'.join(lines[1:]))]}] if len(lines) > 1 else []),
        para(text('Run: ', True), text(datetime.now(timezone.utc).isoformat(timespec='seconds')),
             text('   Host: ', True), text(socket.gethostname())),
        para(text('Posted automatically by agentic-playwright (scripts/jira_report.py).')),
    ]}
    res = jira_api(key, 'POST', f'/issue/{key}/comment', json.dumps({'body': body}).encode(),
                   {'Content-Type': 'application/json'})
    link = f"{site()}/browse/{key}?focusedCommentId={res.get('id', '')}" if isinstance(res, dict) else key
    return f'Jira {key}: rejection posted → {link}'


if __name__ == '__main__':
    args = sys.argv[1:]
    keys = [a for a in args if is_key(a)]
    proj = next((a.split('=', 1)[1] for a in args if a.startswith('--project=')), '')
    if len(keys) != 1:
        print('Usage: npm run jira-report <KEY> [-- --project=<name>]   e.g. npm run jira-report KAN-1', file=sys.stderr)
        sys.exit(1)
    try:
        print(post_report(keys[0], proj or keys[0].lower()))
    except JiraError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

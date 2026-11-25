#!/usr/bin/env python3
"""Deterministic PII detector (regex + checksums, no AI). Used by the pii-guard skill,
the Claude Code hooks (scripts/hooks/pii_guard.py) and `npm run plan`.

  npm run pii -- plans/ README.md     # files and/or folders
  echo "some text" | npm run pii      # stdin
"""
from __future__ import annotations

import json
import os
import re
import sys

PII_MESSAGE = 'Request contains PII data, hence may not proceed.'

A = re.ASCII
TEST_DOMAINS = re.compile(r'(^|\.)(example\.(com|org|net)|example|test|invalid|localhost)$', re.I)
# Well-known public test card numbers (Stripe / Visa / Mastercard / Amex docs).
TEST_CARDS = {'4242424242424242', '4111111111111111', '4000056655665556', '5555555555554444', '5105105105105100', '378282246310005'}


def digits(s: str) -> str:
    return re.sub(r'\D', '', s, flags=A)


def luhn(s: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(s)):
        d = int(c)
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def iban_ok(s: str) -> bool:
    t = s.replace(' ', '')
    return int(re.sub(r'[A-Z]', lambda m: str(ord(m.group()) - 55), t[4:] + t[:4])) % 97 == 1


VD = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
      [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
VP = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
      [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]


def verhoeff(s: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(s)):
        c = VD[c][VP[i % 8][int(ch)]]
    return c == 0


def _card(m: str) -> bool:
    d = digits(m)
    return d[:1] in '3456' and d != '' and luhn(d) and d not in TEST_CARDS


# Order matters: earlier detectors claim their text first, so one value is reported once.
DETECTORS = [
    ('card number', re.compile(r'\b\d(?:[ -]?\d){12,18}\b', A), _card),
    ('IBAN', re.compile(r'\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b', A), iban_ok),
    ('Aadhaar', re.compile(r'\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b', A), lambda m: verhoeff(digits(m))),
    ('SSN', re.compile(r'\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b', A), None),
    ('PAN', re.compile(r'\b[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]\b', A), None),
    ('email', re.compile(r'[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}', A), lambda m: not TEST_DOMAINS.search(m.split('@')[1])),
    ('phone', re.compile(r'\+\d{1,3}[ .-]?(?:\(?\d{1,4}\)?[ .-]?){1,4}\d{2,4}\b', A), lambda m: 8 <= len(digits(m)) <= 15),
    ('phone', re.compile(r'(?:\(\d{3}\) ?|\b\d{3}[ .-])\d{3}[ .-]\d{4}\b', A), None),
    ('phone', re.compile(r'\b[6-9]\d{9}\b', A), None),
]


def allowlist() -> list[str]:
    try:
        with open('agentic.config.json', encoding='utf-8') as f:
            return json.load(f).get('piiAllowlist') or []
    except (OSError, ValueError):
        return []


def mask(kind: str, v: str) -> str:
    """Never echo the full value back (that would leak it into logs and the agent)."""
    if kind == 'email':
        return f"{v[:2]}***@{v.split('@')[1]}"
    return '***' + re.sub(r'[\s-]', '', v)[-4:]


def find_pii(text: str, allow: list[str] | None = None) -> list[dict]:
    """Returns [{type, value (masked), line}]; empty means no PII found."""
    allow = allowlist() if allow is None else allow
    hits: list[dict] = []
    taken: list[tuple[int, int]] = []
    for kind, rx, check in DETECTORS:
        for m in rx.finditer(text):
            start, end = m.span()
            if any(start < b and end > a for a, b in taken):
                continue
            if (check and not check(m.group())) or m.group() in allow:
                continue
            taken.append((start, end))
            hits.append({'type': kind, 'value': mask(kind, m.group()), 'line': text.count('\n', 0, start) + 1})
    return sorted(hits, key=lambda h: h['line'])


def pii_message(hits: list[dict]) -> str:
    return (f'{PII_MESSAGE}\n'
            + '\n'.join(f"  {h.get('where', 'text')}:{h['line']}  {h['type']}  {h['value']}" for h in hits)
            + '\nRemove it or use test data (e.g. user@example.com). Approved exceptions go in "piiAllowlist" in agentic.config.json.\n')


TEXT_FILE = re.compile(r'\.(md|txt|json|ts|tsx|js|mjs|cjs|jsx|py|ya?ml|csv|html|xml)$', re.I)
SKIP = {'node_modules', '.git', 'playwright-report', 'test-results', 'reports', '__pycache__'}


def walk(p: str) -> list[str]:
    if os.path.isdir(p):
        return [f for name in sorted(os.listdir(p)) if name not in SKIP for f in walk(os.path.join(p, name))]
    return [p] if TEXT_FILE.search(p) else []


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        sources = []
        for f in (f for a in args if os.path.exists(a) for f in walk(a)):
            with open(f, encoding='utf-8', errors='replace') as fh:
                sources.append((f, fh.read()))
    else:
        sources = [('stdin', sys.stdin.read())]
    hits = [{**h, 'where': where} for where, text in sources for h in find_pii(text)]
    if hits:
        sys.stderr.write(pii_message(hits))
        sys.exit(1)
    print(f'No PII found ({len(sources)} source(s) checked).')


if __name__ == '__main__':
    main()

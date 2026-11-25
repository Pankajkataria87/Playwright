---
name: pii-guard
description: Stops PII (emails, phone numbers, SSNs, card numbers, IBAN, Aadhaar, PAN) from being passed to an LLM. Any request, plan, ticket or file that contains PII is rejected with "Request contains PII data, hence may not proceed." Use before processing a plan, a Jira ticket, a file or user-supplied text, and whenever a request may contain personal data.
---

# PII guard

The check is deterministic: `scripts/pii.py` (regex + checksums, no AI). The same text always gives the same result.

## Rule
If a check reports PII, stop. Reply exactly:

> Request contains PII data, hence may not proceed.

Then list what the check printed (type and location, masked values only). Do not redact, rewrite,
summarise or continue the task, and never repeat the full PII value.

## When to check
- Before reading or processing plans or files: `npm run pii -- <files or folders>` (exit 1 = PII).
- Before passing user or Jira text to another agent, tool or file: `npm run pii` with the text on stdin.
- `npm run plan` checks every selected plan itself and rejects the run (no agent is called).

## Enforced automatically in Claude Code (this repo only)
`.claude/settings.json` runs `scripts/hooks/pii_guard.py`:

| Hook | Rejects |
|------|---------|
| `UserPromptSubmit` | A prompt containing PII, before it reaches the model. |
| `PreToolUse` (all tools) | A tool call whose input contains PII, and a `Read` of a file containing PII. |

## What is detected
| Type | How |
|------|-----|
| Email | Any address, except test domains (`example.com/.org/.net`, `*.example`, `*.test`, `*.invalid`, `localhost`) |
| Phone | `+<country code> <number>`, US style `(NNN) NNN-NNNN` / `NNN-NNN-NNNN`, Indian 10-digit mobiles starting 6-9 |
| Card number | 13-19 digits passing the Luhn check (public test cards like 4242 4242 4242 4242 allowed) |
| IBAN | Country code + mod-97 checksum |
| SSN | `NNN-NN-NNNN` format (invalid ranges excluded) |
| Aadhaar | 12 digits passing the Verhoeff checksum |
| PAN | 5 letters, 4 digits, 1 letter (4th letter = holder type) |

Approved exceptions: add the exact string to `"piiAllowlist": []` in `agentic.config.json`.

## Limits
- Names and postal addresses are not detected (no reliable deterministic rule).
- Tool **output** (e.g. text on a live web page seen by the browser tools) is not checked before the model sees it.
- Outside Claude Code (Devin, Cursor), only this skill's instructions and `npm run plan` enforce it; the
  request text itself has already reached that agent's model by the time it can check.

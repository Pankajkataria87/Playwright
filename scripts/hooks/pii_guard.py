#!/usr/bin/env python3
"""Claude Code hook (registered in .claude/settings.json) for the pii-guard skill.
  UserPromptSubmit: rejects a prompt that contains PII before it reaches the model.
  PreToolUse: rejects a tool call whose input contains PII, and a Read of a file containing PII
  (the file's content would otherwise be sent to the model).
Exit 2 = block; stderr is shown to the user (prompt) or the agent (tool).
"""
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pii import find_pii, pii_message  # noqa: E402


def strings(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        v = list(v.values())
    return [s for x in v for s in strings(x)] if isinstance(v, list) else []


ev = json.loads(sys.stdin.read() or '{}')
sources = []
if ev.get('hook_event_name') == 'UserPromptSubmit':
    sources.append(('prompt', ev.get('prompt') or ''))
else:
    tool_input = ev.get('tool_input') or {}
    sources.append((f"{ev.get('tool_name')} input", '\n'.join(strings(tool_input))))
    path = tool_input.get('file_path') if isinstance(tool_input, dict) else None
    if ev.get('tool_name') == 'Read' and path:
        try:
            if os.path.getsize(path) < 2_000_000:
                with open(path, encoding='utf-8', errors='replace') as f:
                    sources.append((path, f.read()))
        except OSError:
            pass

hits = [{**h, 'where': where} for where, text in sources for h in find_pii(text)]
if hits:
    sys.stderr.write(pii_message(hits))
    sys.exit(2)

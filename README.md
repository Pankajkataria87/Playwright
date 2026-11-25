# agentic-playwright

A base library for AI-generated Playwright tests. **No app-specific code.**
You write a Markdown plan with a URL, steps and expected results; an agent writes and runs the tests.

## Layout
```
agentic.config.json      # defaults: browser, folders, optional defaultUrl
playwright.config.ts     # auto-creates one project per plan, using that plan's URL
plans/
└── _template.md         # QA template: plans that deviate from it are rejected
prompts/agent.md         # instructions for any agent (Claude Code, Devin, Copilot)
scripts/run_plan.py      # plan → agent → tests → run → report
tests/
├── seed.spec.ts         # generic: opens whatever URL is configured
└── generated/           # ← everything the agent writes goes here, one folder per plan
```

## Setup (once)
Requires Node.js and Python 3 (`python3`; the helper scripts and Claude hooks are Python).
```bash
npm install
npx playwright install --with-deps chromium
npm run agents:init      # optional: Playwright generator/healer for Claude Code
```

## Use
1. Copy `plans/_template.md` → `plans/login.md`, set `**URL:**`, write steps + expected results.
2. Generate and run:
   ```bash
   npm run plan plans/login.md                  # Claude Code (local)
   npm run plan plans/login.md -- --print       # prompt to paste into Devin / any agent
   ```
3. Re-run later without the agent:
   ```bash
   npm run plan plans/login.md -- --run-only
   npx playwright test --project=login --headed
   npm run report
   ```

## Plans from Jira
Put the plan, in the `plans/_template.md` format, in a code block in the Jira issue's description. Then:
```bash
npm run plan KAN-1                 # fetch → template + PII checks → generate → run
npm run plan KAN-1 -- --run-only   # fetch and run the existing tests (CI)
npm run jira KAN-1                 # fetch only
npm run jira-report KAN-1          # post the last run's results to KAN-1 again
```
Every run fetches the latest description into `plans/KAN-1.md`, a gitignored local copy, so Jira stays the source.
Tests go to `tests/generated/kan-1/` (project `kan-1`).

Only issues in status **Ready for Automation** are run (`"jiraRequiredStatus"` in `agentic.config.json`; set it to `""` to allow any status).
Any other status rejects the whole run before the plan is saved, so nothing is generated, run or posted, and an old `plans/KAN-1.md` copy is deleted:
`Rejected: Jira KAN-1 is in status "To Do"; only issues in "Ready for Automation" can be automated.`

When `npm run plan KAN-1` rejects a run, it also comments the reason on KAN-1: wrong status, no plan code block,
template deviations (with plan line numbers) or PII (masked values only, e.g. `***1111`).
`-- --no-jira-report` skips this comment too.

After the final run, `npm run plan KAN-1` posts the results back to KAN-1, pass or fail:
- **Comment:** verdict, counts, duration, URL, and one row per scenario (pass / FAIL / flaky / skipped, first error line for failures).
- **Attachments:** the zipped HTML report (open `index.html` after unzipping), plus any screenshots and videos
  from the run, failed tests first, up to 20 files / 50 MB. A copy of the zip stays in `reports/jira/` (gitignored).

Add `-- --no-jira-report` to skip posting. A Jira error while posting is printed but doesn't change the test exit code.

Setup: the site is `jiraBaseUrl` in `agentic.config.json`. Put your credentials in `.env.local` (gitignored):
```
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=<token from https://id.atlassian.com/manage-profile/security/api-tokens>
```

## Multiple plans
Add more `.md` files to `plans/`, flat or grouped in folders (e.g. one folder per JIRA story).
Each plan can have its own URL. Files/folders starting with `_` are ignored (drafts, templates).
```
plans/
├── login.md                 → project "login"
└── QA-42/
    ├── billing-tab.md       → project "qa-42-billing-tab"
    └── security-tab.md      → project "qa-42-security-tab"
```
```bash
npm run plan plans/login.md plans/QA-42/billing-tab.md   # pick plans
npm run plan plans/QA-42/                                # a whole folder
npm run plan -- --all                                    # everything
npm run plan plans/QA-42/ -- --print                     # one combined prompt for Devin
npx playwright test --project=qa-42-billing-tab          # run one plan's tests
```

## Configuring the URL
Priority: `BASE_URL` env var  >  `**URL:**` in the plan  >  `defaultUrl` in `agentic.config.json`.
```bash
BASE_URL=https://staging.myapp.com npm run plan plans/login.md   # same plan, other environment
```

## Plan template and validation
Every plan must follow `plans/_template.md`. A plan that deviates is **rejected** before anything runs.
The check is a plain script (`scripts/validate_plan.py`), no AI involved, so the same plan always gives the same result.

```bash
npm run validate                     # every plan
npm run validate plans/IR-1020/      # a folder or file
```
```
Rejected: 1 plan(s) do not follow plans/_template.md. Fix these and run again:
  plans/IR-1020/login.md:4  missing or empty "**Starting state:**" in the header
```

Rules:
- First line `# <Feature name>`. Header lines: only `**URL:**` (one http/https URL) and `**Starting state:**` (not empty).
- Optional `## Field checks` before the scenarios: header row exactly `| Field | Input | Expected |`, every row 3 filled cells.
- Scenarios under `## Scenarios` (or other `##` group headings), titled `### 1. <name>`, numbered 1, 2, 3… with no gaps.
- Each scenario: `**Steps:**` with numbered steps (1., 2., …), then `**Expected:**` with `- ` bullets. Nothing else.
- No `<placeholder>` left. Text in backticks and HTML comments are ignored.

Where it is enforced:

| Where | What happens |
|-------|--------------|
| `npm run plan` (also `--print`, `--run-only`) | The whole execution is rejected if any selected plan is invalid. |
| Claude Code `PreToolUse` hook (`.claude/settings.json` → `scripts/hooks/pre_tool_use.py`) | Blocks the agent (exit 2) from reading an invalid plan, writing tests into its folder, running `npx playwright test` on it, or writing a new invalid plan. |
| Devin (skill) | Step 2 runs `npm run plan -- --print`, which rejects. |

Running `npx playwright test` yourself is not blocked; run `npm run validate` first (e.g. as a CI step).

## PII guard
Plans, prompts and files containing PII are rejected with **"Request contains PII data, hence may not proceed."**
The check is a deterministic script (`scripts/pii.py`); the rules are in `.agents/skills/pii-guard/SKILL.md`.

```bash
npm run pii -- plans/                 # files and/or folders; exit 1 if PII is found
echo "<any text>" | npm run pii      # stdin
```

| Where | What is rejected |
|-------|------------------|
| `npm run plan` | The whole run, if any selected plan contains PII (no agent is called). |
| Claude Code `UserPromptSubmit` hook | A prompt containing PII, before it reaches the model. |
| Claude Code `PreToolUse` hook | A tool call with PII in its input, or a `Read` of a file containing PII. |
| Devin (skills) | playwright-plan runs `npm run pii` first and stops. |

Detected: emails (test domains like `example.com` allowed), phone numbers, card numbers (Luhn), IBAN, SSN, Aadhaar, PAN.
Not detected: names and postal addresses. Approved exceptions: `"piiAllowlist": []` in `agentic.config.json`.

## Reports, screenshots and traces
`npm run report` opens the HTML report from the last run (also: `test-results/results.xml` JUnit, `test-results/results.json`).
What it contains depends on `use` in `playwright.config.ts`:

| Setting (default) | When you get it |
|-------------------|-----------------|
| `screenshot: 'only-on-failure'` | A screenshot is attached **only to failed tests**. A fully green run has none. |
| `trace: 'on-first-retry'` | A trace (step-by-step screenshots + DOM snapshots) is recorded **only when a failed test is retried**. Retries are 2 in CI (`CI=true`) and 0 locally, so local runs record no traces. |

To get screenshots/traces for passing tests too:
```bash
npx playwright test --project=login --trace=on   # one run: full trace for every test
npm run report                                   # open a test → "Traces" to step through it
```
Or make it permanent by setting `use: { trace: 'on', screenshot: 'on' }` in `playwright.config.ts`
(bigger, slower reports). Tests run headless by default; add `--headed` to watch the browser, or `--ui` for UI mode.

Video is **off** by default. Turn it on with the `VIDEO` env var (`on`, `retain-on-failure` or `on-first-retry`):
```bash
VIDEO=on npx playwright test --project=login   # a .webm per test, shown in the HTML report
VIDEO=retain-on-failure npx playwright test     # keep videos only for failed tests
```

## Token usage per execution
`npm run plan` (Claude Code) records the tokens and cost of every agent run, one line per plan,
in `reports/agent-usage.jsonl`, and prints a table for that execution at the end:
```
plan          status  turns  input  output  cache write  cache read  total tokens  cost     time
ir-1020-todo  ok      24     1,204  9,876   45,210       612,000     668,290       $0.4120  182s
```
- **input / output**: new prompt tokens and generated tokens.
- **cache write / cache read**: prompt tokens written to / served from Claude's prompt cache (cache reads are billed much cheaper).
- **cost**: `total_cost_usd` as reported by Claude Code.

History:
```bash
npm run usage                          # every execution, grouped, with totals
npm run usage -- --last 3              # last 3 executions
npm run usage -- --plan ir-1020-todo   # one plan only
```
`--run-only` uses no agent, so nothing is logged. **Devin** runs are billed in ACUs, not tokens:
the skill reports the session's ACUs in its reply and PR, and the session page shows them too.

## What gets generated
```
tests/generated/login/
├── login.spec.ts
└── pages/LoginPage.ts
```
Delete a plan's folder to regenerate from scratch.

## Running in Devin (Skills)
The repo includes a Devin skill at `.agents/skills/playwright-plan/SKILL.md`.
Once the repo is connected in Devin, start a session and type:
```
@skills:playwright-plan plans/todomvc.md
@skills:playwright-plan plans/QA-42/
@skills:playwright-plan --all
```
Devin sets up the machine, generates tests per `prompts/agent.md`, runs them, opens a PR
and replies with a results table. Edit the SKILL.md and push to change how it works.

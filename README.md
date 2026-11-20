# agentic-playwright

A base library for AI-generated Playwright tests. **No app-specific code.**
You write a Markdown plan with a URL, steps and expected results; an agent writes and runs the tests.

## Layout
```
agentic.config.json      # defaults: browser, folders, optional defaultUrl
playwright.config.ts     # auto-creates one project per plan, using that plan's URL
plans/
└── _example.md          # template: URL + steps + expected results
prompts/agent.md         # instructions for any agent (Claude Code, Devin, Copilot)
scripts/run-plan.mjs     # plan → agent → tests → run → report
tests/
├── seed.spec.ts         # generic: opens whatever URL is configured
└── generated/           # ← everything the agent writes goes here, one folder per plan
```

## Setup (once)
```bash
npm install
npx playwright install --with-deps chromium
npm run agents:init      # optional: Playwright generator/healer for Claude Code
```

## Use
1. Copy `plans/_example.md` → `plans/login.md`, set `**URL:**`, write steps + expected results.
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

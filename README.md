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

## What gets generated
```
tests/generated/login/
├── login.spec.ts
└── pages/LoginPage.ts
```
Delete a plan's folder to regenerate from scratch.

---
name: playwright-plan
description: Turn Markdown test plans (plans/*.md with URL, steps and expected results) into Playwright tests, run them, fix flaky locators and report results. Use when asked to automate, generate or run tests for a plan file or plans folder.
---

# Generate and run Playwright tests from Markdown plans

Plans to process: **$ARGUMENTS**
(a plan file like `plans/todomvc.md`, a folder like `plans/QA-42/`, or `--all`.
If empty, ask which plan to use.)

## 1. Setup
```bash
npm ci
npx playwright install --with-deps chromium
```

## 2. Resolve the plans
Run:
```bash
npm run plan $ARGUMENTS -- --print
```
It prints, for each plan: the plan file, its **name**, its **URL** and its **output folder**.
Use exactly those values below. If it reports a missing URL, stop and tell the user.

## 3. Check each URL opens
For each distinct URL:
```bash
BASE_URL=<url> npx playwright test --project=seed
```
If the seed fails, stop and report why. Don't generate tests against a site that doesn't load.

## 4. Generate tests: follow `prompts/agent.md` for every plan
Process plans one after another, so later plans can reuse page objects from earlier ones.
Key rules (full details in `prompts/agent.md`):
- Explore the live site with the browser first; use real locators, never guessed ones.
- Write only inside the plan's output folder: `<name>.spec.ts` + `pages/*.ts`.
- One `test()` per scenario, titled with the scenario number; tag every test `@<name>`.
- Locators in page objects only: getByRole / getByLabel / getByPlaceholder / getByTestId.
- Use relative `page.goto('/')`. Never hard-code the URL (playwright.config.ts sets it per plan).
- No `waitForTimeout`, no `test.only`.

## 5. Verify each plan
```bash
npx playwright test --project=<name> --repeat-each=3
```
- On failure: fix locators or waits only. **Never weaken or delete an assertion.**
- If the app really behaves differently from the plan, mark that test `test.fixme()` with a one-line reason.
- `npx tsc --noEmit -p .` must pass.

## 6. Finish
1. Final run of all processed plans:
   `npx playwright test --project=<name1> --project=<name2> ...`
2. Open one PR titled `Automated tests: <plan names>`.
   Commit only `tests/generated/**` (and `plans/**` if you were asked to add a plan).
3. Reply with one table per plan:

| # | Scenario | Result (pass / fail / fixme) | Notes |
|---|----------|------------------------------|-------|

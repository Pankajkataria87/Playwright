# Agent instructions: turn a Markdown test plan into Playwright tests

Works with any agent (Playwright generator/healer via Claude Code, Devin, Copilot).
You will be given a plan file: `plans/<name>.md`.

## Inputs
- **URL**: from the plan's `**URL:**` line (or BASE_URL env). Never hard-code it in tests;
  use `page.goto('')` for the plan URL itself and relative paths without a leading slash
  (`page.goto('settings')`) for sub-pages. A leading `/` drops the URL's path
  (e.g. `https://x.com/app` + `/` → `https://x.com/`). playwright.config.ts sets baseURL per plan.
- **Seed**: `tests/seed.spec.ts`. Run it first:
  `BASE_URL=<url> npx playwright test --project=seed`. If it fails, stop and report why.

## Output (only write inside this folder)
`tests/generated/<name>/`
- `<name>.spec.ts`: the tests
- `pages/*.ts`: page objects you create for this site (one class per screen/area)

If another folder in `tests/generated/` targets the **same URL host**, reuse its `pages/`
by importing them, rather than duplicating.

## Rules
1. Explore the live site first to find real locators. Don't guess.
2. One `test()` per scenario; title starts with the scenario number from the plan.
3. Field-check tables → one data-driven loop (`for (const row of rows) test(...)`).
4. Tag every test with `@<name>`.
5. Locators: getByRole / getByLabel / getByPlaceholder / getByTestId. No CSS/XPath unless unavoidable.
   Put locators in page objects, not in the spec.
6. No `waitForTimeout`, no `test.only`.
7. Each test must be independent and start from the plan's Starting state.

## Verify
- `npx playwright test --project=<name> --repeat-each=3`
- On failure: fix locators/waits only. **Never weaken or delete an assertion.**
  If the app really behaves differently from the plan, use `test.fixme()` with a one-line reason.
- `npx tsc --noEmit -p .` passes.

## Report back
A table: scenario | result (pass / fail / fixme) | notes (bugs found, assumptions).

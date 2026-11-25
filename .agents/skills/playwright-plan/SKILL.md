---
name: playwright-plan
description: Turn Markdown test plans (plans/*.md with URL, steps and expected results) into Playwright tests, run them, run the security checks, then open one PR with functional results and security findings. Use when asked to automate, generate or run tests for a plan file or plans folder.
---

# Generate and run Playwright tests from Markdown plans

Plans to process: **$ARGUMENTS**
(a Jira key like `KAN-1`, a plan file like `plans/todomvc.md`, a folder like `plans/QA-42/`, or `--all`.
If empty, ask which plan to use.)

## 1. Setup
```bash
npm ci
npx playwright install --with-deps chromium
```

## 2. Resolve the plans
First follow `.agents/skills/pii-guard/SKILL.md`: run `npm run pii -- <the plans>`. If it reports PII, reply
"Request contains PII data, hence may not proceed." with its list, and stop.
For a Jira key, skip that: `npm run plan <KEY> -- --print` below fetches the plan and runs the same PII check.
Don't read the issue with Jira tools first; that would send unchecked text to the model.

Run:
```bash
npm run plan $ARGUMENTS -- --print
```
It prints, for each plan: the plan file, its **name**, its **URL** and its **output folder**.
Use exactly those values below. If it reports a missing URL, stop and tell the user.
If it prints `Rejected: ... do not follow plans/_template.md`, stop and give the user the listed
deviations. Don't fix the plan yourself: QA owns it and must follow the template.
If it prints `Rejected: Jira <KEY> is in status ...`, stop and tell the user. Don't change the issue's status yourself.

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
- Use `page.goto('')` for the plan URL (a leading `/` drops its path). Never hard-code the URL (playwright.config.ts sets it per plan).
- No `waitForTimeout`, no `test.only`.

## 5. Verify each plan
```bash
npx playwright test --project=<name> --repeat-each=3
```
- On failure: fix locators or waits only. **Never weaken or delete an assertion.**
- If the app really behaves differently from the plan, mark that test `test.fixme()` with a one-line reason.
- `npx tsc --noEmit -p .` must pass.

## 6. Security checks (before any PR)
Read `.agents/skills/playwright-security/SKILL.md` and follow its sections **0 to 4** for the
same plans (authorisation gate, ground rules, setup, write checks, run).
**Skip its section 5**: there is one PR for everything, created in step 7 below.
- If a plan's host is not in `securityAllowedHosts`, skip security for that plan only,
  and say so in the final reply. Do not add hosts to the list yourself.
- Security findings are expected results, not test bugs: never weaken those assertions.

## 7. Finish
1. Final run of all processed plans (functional + security):
   `npx playwright test --project=<name1> --project=<name2> ...`
2. Decide the PR type:
   - Any **[HIGH]** security finding → open the PR as a **draft** and start its description with
     `⚠️ HIGH security findings – review before merging`.
   - Otherwise → open a normal PR.
3. One PR titled `Automated tests: <plan names>`.
   Commit only `tests/generated/**` (and `plans/**` if you were asked to add a plan; never the gitignored Jira copies `plans/<KEY>.md`).
   Put both tables below in the PR description.
4. For each plan that came from a Jira key, post the results back to that issue:
   `npm run jira-report <KEY>` (run it right after the final run; it reads `test-results/results.json`).
   Don't post with Jira tools yourself. If it fails, say so in the reply.
5. Reply with, per plan:

**Functional results**
| # | Scenario | Result (pass / fail / fixme) | Notes |
|---|----------|------------------------------|-------|

**Security findings** (sorted HIGH → INFO; or "skipped: host not authorised")
| Severity | Check | Result (pass / FINDING / n/a) | Evidence | Suggested fix |
|----------|-------|-------------------------------|----------|---------------|

**Agent usage**: the ACUs this session used, from your session insights if available
(Devin is billed in ACUs, not tokens; don't convert ACUs to dollars). Put it in the PR description too.

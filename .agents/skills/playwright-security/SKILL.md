---
name: playwright-security
description: Run safe, non-destructive security checks (headers, cookies, HTTPS, CSP, clickjacking, CORS, output escaping, access control, information leaks) against a web app from a Markdown plan, as Playwright tests, and report findings by severity. Use when asked for security testing of a plan, URL or plans folder.
---

# Security checks for web apps (Playwright)

Plans to check: **$ARGUMENTS**
(a plan file like `plans/todomvc.md`, a folder like `plans/QA-42/`, or `--all`.
If empty, ask which plan to use.)

## 0. Authorisation gate: do this first, no exceptions
1. Run `npm run plan $ARGUMENTS -- --print` to get each plan's **name** and **URL**.
2. Read `securityAllowedHosts` in `agentic.config.json`.
3. For every plan, the URL's host must be listed there (exact host, e.g. `staging.myapp.com`).
   - If any host is missing: **stop**. Tell the user which hosts need adding and that they must
     only add hosts they own or are authorised to test. Do not run anything against those hosts.
4. Never test production unless the host is listed AND the user confirmed it in this session.

## 1. Ground rules: what this skill must NOT do
- No exploitation, no payloads designed to execute code, steal data or bypass auth.
- No brute force, credential stuffing, fuzzing loops or high request volumes (stay under ~1 req/sec).
- No denial-of-service, no load testing.
- No creating, changing or deleting real data beyond what the plan's own scenarios do.
- No scanning hosts, ports or paths outside the plan's URL.
- If you find a likely serious issue, **stop probing it**, record it and move on.

## 2. Setup
```bash
npm ci
npx playwright install --with-deps chromium
BASE_URL=<url> npx playwright test --project=seed   # must pass before continuing
```

## 3. Write the checks
Write to `tests/generated/<name>/security.spec.ts` (same folder as the plan's functional tests,
so it runs under the existing `--project=<name>`).
- Tag every test `@security` and `@<name>`, and put the severity in the title:
  `test('[HIGH] Session cookie is HttpOnly', ...)`.
- Use relative URLs (`page.goto('/')`, `request.get('/')`). Never hard-code the host.
- Reuse page objects from `tests/generated/<name>/pages/` where they exist.
- Checks that don't apply (e.g. no login, no forms) → `test.skip(true, '<reason>')`. Don't delete them.

### Checklist (one test per item, adapt to the app)

**Transport**
- [HIGH] Site is served over HTTPS; `http://` redirects to `https://`.
- [MEDIUM] `Strict-Transport-Security` present with `max-age` ≥ 15552000.
- [MEDIUM] No mixed content: listen to `page.on('request')` and fail on any `http://` subresource.

**Security headers** (main document response)
- [MEDIUM] `Content-Security-Policy` present; flag `unsafe-inline` / `unsafe-eval` / `*` in script-src as LOW.
- [MEDIUM] Clickjacking protection: `X-Frame-Options: DENY|SAMEORIGIN` or CSP `frame-ancestors`.
- [LOW] `X-Content-Type-Options: nosniff`.
- [LOW] `Referrer-Policy` present and not `unsafe-url`.
- [LOW] `Permissions-Policy` present.
- [INFO] `Server` / `X-Powered-By` don't reveal software versions.

**Cookies** (`context.cookies()` after loading, and after login if the plan has one)
- [HIGH] Session/auth cookies are `HttpOnly` and `Secure`.
- [MEDIUM] Session/auth cookies have `SameSite=Lax` or `Strict`.

**CORS** (`request` fixture, send `Origin: https://evil.example`)
- [HIGH] Response does not reflect that origin in `Access-Control-Allow-Origin` together with
  `Access-Control-Allow-Credentials: true`.
- [MEDIUM] `Access-Control-Allow-Origin: *` not set on authenticated endpoints.

**Output escaping** (only on inputs the plan already uses; harmless marker, never a script)
- [HIGH] Enter the marker `"><i data-sec-probe>probe</i>` into each text input the plan uses.
  After submitting, assert `page.locator('[data-sec-probe]')` has count 0, i.e. the text is shown
  as text, not turned into HTML. Clean up any item the probe created if the plan supports deletion.

**Access control** (only if the plan has a login)
- [HIGH] Logged out (fresh context, no storage state), each protected route from the plan
  redirects to login or returns 401/403. It does not render protected content.
- [MEDIUM] After logout, pressing Back or reloading a protected page does not show protected data.

**Information leaks**
- [MEDIUM] No secrets in page source or JS bundles visible to the browser: scan responses for
  patterns like `api[_-]?key`, `secret`, `password\s*[:=]`, `AKIA[0-9A-Z]{16}`, private keys.
- [LOW] Requesting a non-existent path (`/__sec_probe_404`) returns 404 without stack traces,
  framework debug pages or file paths.
- [LOW] No sensitive data (tokens, emails, passwords) written to `console` or `localStorage`.

**Forms**
- [MEDIUM] Password fields use `type="password"` and `autocomplete` of `current-password`/`new-password`.
- [LOW] Forms that change state send a CSRF token or rely on SameSite cookies (record which).

## 4. Run
```bash
npx playwright test --project=<name> --grep @security
npx tsc --noEmit -p .
```
- A failing check is a **finding**, not a broken test. Do not weaken assertions to make it pass.
- Only fix a test if the *test itself* is wrong (bad locator, wrong route).
- Known/accepted findings: `test.fail()` with a one-line reason so they stay visible in the report.

## 5. Report
1. Open one PR titled `Security checks: <plan names>` committing only
   `tests/generated/**/security.spec.ts` (and page-object additions if any).
2. Reply with a findings table per plan, sorted HIGH → INFO:

| Severity | Check | Result (pass / FINDING / n/a) | Evidence (header value, cookie, URL) | Suggested fix |
|----------|-------|-------------------------------|--------------------------------------|---------------|

3. End with: "These are automated baseline checks, not a penetration test. For deeper coverage,
   run OWASP ZAP baseline scan and a manual review."

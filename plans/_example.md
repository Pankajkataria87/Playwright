# <Feature or screen name>

**URL:** https://your-app.example.com
**Starting state:** <what is true before every scenario, e.g. "logged out, empty cart">

<!--
How to use:
1. Copy this file to plans/<name>.md (no leading underscore).
2. Set the URL. That's the only configuration.
3. Run:  npm run plan plans/<name>.md
-->

## Field checks (optional: becomes one data-driven test)
| Field | Input | Expected |
|-------|-------|----------|
| Email | not-an-email | error "Enter a valid email" |
| Email | user@example.com | accepted |

## Scenarios

### 1. <Scenario name>
**Steps:**
1. <action>
2. <action>

**Expected:**
- <observable result>
- <observable result>

### 2. <Scenario name>
**Steps:**
1. ...

**Expected:**
- ...

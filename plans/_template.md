# <Feature or screen name>

**URL:** <https://your-app.example.com/page>
**Starting state:** <what is true before every scenario, e.g. "logged out, empty cart">

<!--
QA plan template. A plan that deviates from it is rejected before anything runs
(`npm run validate` lists every deviation with its line number).
1. Copy to plans/<JIRA-KEY>/<feature>.md (no leading "_") and replace every <...>.
2. Header: only "# Title", "**URL:**" (one http/https URL) and "**Starting state:**".
3. "## Field checks" is optional (becomes one data-driven test); delete it if unused.
   Keep its header row exactly as is; every row needs 3 filled cells.
4. Scenarios go under "## Scenarios" (or other "##" group headings) as
   "### 1. <name>", "### 2. <name>" ... numbered with no gaps.
5. Each scenario: "**Steps:**" with numbered steps (1., 2., ...), then "**Expected:**"
   with "- " bullets of observable results. Nothing else inside a scenario.
6. HTML comments like this one are ignored. Never put real passwords or secrets in a plan.
-->

## Field checks
| Field | Input | Expected |
|-------|-------|----------|
| <field> | <input> | <expected result> |

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
1. <action>

**Expected:**
- <observable result>

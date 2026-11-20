// Generic seed: opens the configured URL. Works for any site.
// The agents run it (with BASE_URL set) to learn how to reach the app.
import { test, expect } from '@playwright/test';

test('seed', async ({ page, baseURL }) => {
  test.skip(!baseURL, 'No URL: set BASE_URL, a **URL:** line in the plan, or defaultUrl in agentic.config.json');
  const res = await page.goto('/');
  expect(res?.ok(), `Could not open ${baseURL}`).toBeTruthy();
});

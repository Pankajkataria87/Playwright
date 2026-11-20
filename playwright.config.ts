import { defineConfig, devices } from '@playwright/test';
// @ts-ignore – plain JS helper shared with the CLI
import { allPlans, urlFor, slug, config } from './scripts/plans.mjs';

const browser = ({ chromium: 'Desktop Chrome', firefox: 'Desktop Firefox', webkit: 'Desktop Safari' } as const)[
  (config.browser as 'chromium' | 'firefox' | 'webkit') ?? 'chromium'
];

// One Playwright project per plan, each with the URL from that plan's header.
// Add a plan → it gets its own project automatically. Nothing to register.
const planProjects = (allPlans() as string[]).map(plan => ({
  name: slug(plan),
  testDir: `${config.outputDir}/${slug(plan)}`,
  use: { ...devices[browser], baseURL: urlFor(plan) },
}));

export default defineConfig({
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
    ['junit', { outputFile: 'test-results/results.xml' }],
    ['json', { outputFile: 'test-results/results.json' }],
  ],
  use: { trace: 'on-first-retry', screenshot: 'only-on-failure' },
  projects: [
    // Seed: used by the agents to open whatever URL a plan points at.
    { name: 'seed', testMatch: /seed\.spec\.ts/, testDir: 'tests',
      use: { ...devices[browser], baseURL: process.env.BASE_URL || config.defaultUrl || undefined } },
    ...planProjects,
  ],
});

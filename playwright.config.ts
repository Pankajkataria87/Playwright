import { execFileSync } from 'node:child_process';
import { defineConfig, devices } from '@playwright/test';

// Plan discovery lives in scripts/plans.py, shared with the CLI and the hooks.
const { config, plans } = JSON.parse(
  execFileSync('python3', ['scripts/plans.py', '--json'], { encoding: 'utf8' }),
) as {
  config: { browser?: string; defaultUrl?: string; outputDir: string };
  plans: { plan: string; name: string; url: string }[];
};

const browser = ({ chromium: 'Desktop Chrome', firefox: 'Desktop Firefox', webkit: 'Desktop Safari' } as const)[
  (config.browser as 'chromium' | 'firefox' | 'webkit') ?? 'chromium'
];

// One Playwright project per plan, each with the URL from that plan's header.
// Add a plan → it gets its own project automatically. Nothing to register.
const planProjects = plans.map(p => ({
  name: p.name,
  testDir: `${config.outputDir}/${p.name}`,
  use: { ...devices[browser], baseURL: p.url },
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
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // VIDEO=on | retain-on-failure | on-first-retry; off by default.
    video: (process.env.VIDEO || 'off') as 'on' | 'off' | 'retain-on-failure' | 'on-first-retry',
  },
  projects: [
    // Seed: used by the agents to open whatever URL a plan points at.
    { name: 'seed', testMatch: /seed\.spec\.ts/, testDir: 'tests',
      use: { ...devices[browser], baseURL: process.env.BASE_URL || config.defaultUrl || undefined } },
    ...planProjects,
  ],
});

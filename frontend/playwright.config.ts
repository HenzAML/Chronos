import { defineConfig } from '@playwright/test'
import { API_PORT, DB_URL, PY, WEB_PORT } from './e2e/env.ts'

// Own database, own ports: the dev servers and dev data are never touched.
export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/global-setup.ts',
  workers: 1,               // the tests share one database
  timeout: 120_000,         // a solve may take up to 30s
  expect: { timeout: 60_000 },
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
    // E2E_BROWSER=msedge or chrome uses the installed browser, for machines
    // where Windows blocks Playwright's own unsigned download.
    channel: process.env.E2E_BROWSER,
  },
  webServer: [
    {
      command: `"${PY}" -m flask --app wsgi run --port ${API_PORT}`,
      cwd: '../backend',
      env: { DATABASE_URL: DB_URL },
      port: API_PORT,       // not a url: the database is created after the servers start
      reuseExistingServer: false,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      env: { API_TARGET: `http://127.0.0.1:${API_PORT}` },
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
    },
  ],
})

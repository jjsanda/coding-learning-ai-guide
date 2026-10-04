import { defineConfig } from '@playwright/test'

// Captures documentation screenshots from a running demo stack.
// Point BASE_URL at the web app (default: the docker-compose web service).
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8080',
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  },
})

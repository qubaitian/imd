import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:18741",
    headless: true,
    channel: "chromium",
  },
  webServer: {
    command: "../.venv/bin/python ../tests/browser_server.py",
    gracefulShutdown: { signal: "SIGINT", timeout: 5000 },
    url: "http://127.0.0.1:18741",
    reuseExistingServer: false,
    timeout: 30000,
  },
});

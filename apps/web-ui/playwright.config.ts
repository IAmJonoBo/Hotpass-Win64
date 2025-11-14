import { defineConfig, devices } from "@playwright/test";

const CI = !!process.env.CI;

export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  fullyParallel: false,
  expect: {
    timeout: 5000,
  },
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  webServer: {
    command: "pnpm run dev -- --host 0.0.0.0 --port 4173",
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
    trace: "on-first-retry",
  },
  workers: CI ? 2 : undefined,
  projects: [
    {
      name: "chromium-desktop-dark",
      use: {
        ...devices["Desktop Chrome"],
        colorScheme: "dark",
        storageState: "tests/storage-states/dark.json",
      },
    },
    {
      name: "chromium-desktop-light",
      use: {
        ...devices["Desktop Chrome"],
        colorScheme: "light",
        storageState: "tests/storage-states/light.json",
      },
    },
  ],
});

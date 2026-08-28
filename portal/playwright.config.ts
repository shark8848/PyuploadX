import { defineConfig, devices } from "@playwright/test";

const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8000";
const PORTAL_URL = process.env.E2E_PORTAL_URL || "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: PORTAL_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000",
      url: `${API_URL}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      cwd: "..",
      env: {
        ...process.env,
        UPLOAD_API_KEYS: '["e2e-key"]',
        UPLOAD_DATABASE_URL: "sqlite+aiosqlite:////tmp/pyuploadx-e2e.db",
        UPLOAD_REDIS__ENABLED: "false",
        UPLOAD_STORAGE__BACKEND: "local",
        UPLOAD_STORAGE__LOCAL__ROOT_PATH: "/tmp/pyuploadx-e2e-storage",
        UPLOAD_STORAGE__LOCAL__MULTIPART_PATH: "/tmp/pyuploadx-e2e-storage/.multipart",
        UPLOAD_CLUSTER__ENABLED: "false",
        UPLOAD_UPLOADS__MULTIPART__MINIMUM_PART_SIZE_BYTES: "1",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      url: PORTAL_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { ...process.env, UPLOAD_API_URL: API_URL },
    },
  ],
});

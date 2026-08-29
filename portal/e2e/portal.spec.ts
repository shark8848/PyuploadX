/**
 * Portal E2E (docs 29.6): login/error display, file and directory upload,
 * lifecycle selection, and queue restore after a page refresh.
 *
 * Notes:
 * - /v1/client-config is public; auth is enforced on upload endpoints.
 * - The UI is gated by a login page: the API key is verified against
 *   GET /v1/files before entering the app (token persisted in localStorage).
 * - Fresh uploads keep the File blob in memory (no dialog). After a page
 *   refresh the blob is gone, so the queue shows a "重新选择" button and the
 *   user re-picks the original file (docs 18.4).
 */
import { expect, test, type Page } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const API_KEY = "e2e-key";

interface Payload {
  name: string;
  mimeType?: string;
  buffer: Buffer;
}

let dirFixture: string;
test.beforeAll(async () => {
  dirFixture = path.join(os.tmpdir(), "pyuploadx-e2e-dir");
  await mkdir(path.join(dirFixture, "assets", "sub"), { recursive: true });
  await writeFile(path.join(dirFixture, "assets", "logo.svg"), "<svg/>");
  await writeFile(path.join(dirFixture, "assets", "sub", "data.json"), "{}");
});

async function login(page: Page, key: string = API_KEY): Promise<void> {
  await page.goto("/");
  // 登录页在鉴权探测完成后才渲染；等待其出现，若 nginx 已注入 token 则直接进入。
  const input = page.getByPlaceholder("请输入 API Key");
  try {
    await input.waitFor({ state: "visible", timeout: 10_000 });
    await input.fill(key);
    await page.locator(".ant-btn-primary").click();
  } catch {
    // 已通过注入的 token 免登录进入。
  }
  // 缺省首页为文件浏览（docs 18.2）。
  await expect(page.getByRole("heading", { name: "文件浏览" })).toBeVisible();
  await expect(page.locator(".file-nav")).toBeVisible();
}

async function gotoUpload(page: Page): Promise<void> {
  await page.getByRole("menuitem", { name: "上传" }).click();
  await expect(page.getByRole("heading", { name: "文件上传" })).toBeVisible();
}

async function uploadFile(page: Page, payload: Payload): Promise<void> {
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles([{ name: payload.name, mimeType: payload.mimeType, buffer: payload.buffer }]);
  await expect(page.locator(".queue-item.completed")).toHaveCount(1, { timeout: 30_000 });
}

test("错误 API Key 登录被拒绝并显示错误", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("请输入 API Key").fill("wrong-key");
  await page.locator(".ant-btn-primary").click();
  await expect(page.getByText("API Key 无效，请检查后重试")).toBeVisible();
  await expect(page.getByRole("heading", { name: "PyUploadX" })).toBeVisible();
});

test("正确 API Key 加载客户端配置", async ({ page }) => {
  await login(page);
  await expect(page.locator(".file-nav")).toBeVisible();
  await expect(page.locator(".ant-select")).toHaveCount(2);
});

test("上传单个文件并完成", async ({ page }) => {
  await login(page);
  await gotoUpload(page);
  const completed = page.waitForResponse(
    (response) =>
      response.url().match(/\/v1\/uploads\/[^/]+\/complete$/)?.length === 1 &&
      response.request().method() === "POST" &&
      response.status() === 200,
  );
  await uploadFile(page, { name: "hello.txt", buffer: Buffer.from("hello e2e") });
  await expect(page.locator(".queue-name", { hasText: "hello.txt" })).toBeVisible();
  await expect(page.getByText("已完成")).toBeVisible();
  await expect(page.getByRole("link", { name: "下载" })).toBeVisible();
  expect((await completed).status()).toBe(200);
});

test("目录上传保留相对路径", async ({ page }) => {
  await login(page);
  await gotoUpload(page);
  await page.locator('input[webkitdirectory]').setInputFiles([
    { name: "assets/logo.svg", mimeType: "image/svg+xml", buffer: Buffer.from("<svg/>") },
    { name: "assets/sub/data.json", mimeType: "application/json", buffer: Buffer.from("{}") },
  ]);
  await expect(page.locator(".queue-item.completed")).toHaveCount(2, { timeout: 30_000 });
  await expect(page.locator(".queue-meta", { hasText: "assets/logo.svg" })).toBeVisible();
  await expect(page.locator(".queue-meta", { hasText: "assets/sub/data.json" })).toBeVisible();
});

test("选择生命周期后上传返回生效策略", async ({ page }) => {
  await login(page);
  await gotoUpload(page);
  const modeSelect = page.locator('span:has-text("生命周期：") .ant-select').first();
  await expect(modeSelect.locator(".ant-select-content")).toHaveText("定时过期（TTL）");
  const upload = page.waitForResponse(
    (response) =>
      response.url().match(/\/v1\/uploads\/[^/]+\/complete$/)?.length === 1 &&
      response.request().method() === "POST" &&
      response.status() === 200,
  );
  await uploadFile(page, { name: "ttl.txt", buffer: Buffer.from("ttl") });
  const body = await (await upload).json();
  expect(body.lifecycle_mode).toBe("ttl");
  expect(body.lifecycle_action).toBe("delete");
});

test("刷新页面后队列恢复并完成", async ({ page }) => {
  await login(page);
  await gotoUpload(page);
  const file: Payload = { name: "restore.txt", mimeType: "text/plain", buffer: Buffer.from("restore me") };
  // 放慢建会话请求，让刷新发生时任务仍处于上传中（尚未拿到 uploadId）。
  await page.route("**/v1/uploads", async (route) => {
    if (route.request().method() === "POST") {
      await new Promise((resolve) => setTimeout(resolve, 4000));
    }
    await route.continue();
  });
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles([file]);
  await expect(page.locator(".queue-item").first()).toBeVisible();
  await page.reload();
  await gotoUpload(page);
  // IndexedDB 恢复：任务重新出现，blob 丢失后显示“重新选择”按钮。
  await expect(page.locator(".queue-name", { hasText: "restore.txt" })).toBeVisible();
  await expect(page.getByRole("button", { name: "重新选择" })).toBeVisible();
  page.once("filechooser", (chooser) => {
    void chooser.setFiles([file]);
  });
  await page.getByRole("button", { name: "重新选择" }).click();
  await expect(page.locator(".queue-item.completed")).toHaveCount(1, { timeout: 30_000 });
});

test("新建桶在侧栏头部，设置/退出在左下角", async ({ page }) => {
  await login(page);
  await expect(page.locator(".file-nav-header")).toContainText("新建桶");
  await expect(page.locator(".file-nav-footer")).toBeVisible();
  await expect(page.locator(".file-nav-footer").getByRole("button", { name: "设置" })).toBeVisible();
  await expect(page.locator(".file-nav-footer").getByRole("button", { name: "退出" })).toBeVisible();
});

test("中英文与明暗主题切换", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "EN" }).click();
  await expect(page.getByRole("heading", { name: "Files" })).toBeVisible();
  await page.getByRole("button", { name: "中文" }).click();
  await expect(page.getByRole("heading", { name: "文件浏览" })).toBeVisible();
  await page.locator(".file-nav-footer").getByRole("button", { name: /主题/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.locator(".file-nav-footer").getByRole("button", { name: /主题/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("新建存储桶并出现在导航树", async ({ page }) => {
  await login(page);
  const name = `e2e-${Date.now().toString(36)}`;
  await page.getByRole("button", { name: "新建桶" }).click();
  await page.getByRole("dialog").locator("input").fill(name);
  await page.getByRole("button", { name: /创\s*建/ }).click();
  await expect(page.getByText(`存储桶 ${name} 创建成功`)).toBeVisible();
  await expect(page.locator(".file-nav", { hasText: name })).toBeVisible();
});

test("存储设置弹窗展示默认桶与有效期", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "设置" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("默认存储桶");
  await expect(dialog).toContainText("下载链接默认有效期");
  await page.getByRole("button", { name: /取\s*消/ }).click();
  await expect(dialog).not.toBeVisible();
});

import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };
const url = "http://localhost:8123/a?x=1#part";
const source = `# Links\n\nVisit [the page](${url}) or ${url}.\n\n\`\`\`python\naddress = "${url}"\n\`\`\`\n\n\`\`\`out\n('${url}', '/tmp/test')\n\`\`\`\n`;

test.beforeEach(async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  await request.put("/api/document", { headers, data: { source, revision: current.revision } });
  await page.goto("/#token=browser-test");
  await expect(page.getByRole("heading", { name: "Links", exact: true })).toBeVisible();
});

for (const location of ["preview", "markdown editor", "code preview", "code editor", "output", "source"]) {
  test(`Cmd click opens a URL from ${location} without changing the document`, async ({ page, request, context }) => {
    const calls = [];
    await page.route("**/api/browser/open", async route => {
      calls.push(route.request().postDataJSON());
      await route.fulfill({ json: { action: "focused" } });
    });
    let target;
    if (location === "preview") target = page.getByRole("link", { name: "the page" });
    if (location === "code preview") target = page.locator(".code-preview [data-imd-url]");
    if (location === "output") target = page.locator(".output-body [data-imd-url]");
    if (location === "markdown editor") {
      await page.locator(".prose-block").filter({ hasText: "Visit" }).click({ position: { x: 4, y: 4 } });
      target = page.locator(".markdown-edit [data-imd-url]").first();
    }
    if (location === "code editor") {
      await page.locator(".code-preview").click();
      target = page.locator(".cm-content [data-imd-url]");
    }
    if (location === "source") {
      await page.getByRole("button", { name: "Source", exact: true }).click();
      target = page.locator(".cm-content [data-imd-url]").first();
    }
    await target.click({ modifiers: ["Meta"] });
    await expect.poll(() => calls).toEqual([{ url }]);
    expect(context.pages()).toHaveLength(1);
    const saved = await (await request.get("/api/document", { headers })).json();
    expect(saved.source).toBe(source);
    if (location === "code preview") await expect(page.locator(".code-preview")).toBeVisible();
  });
}

test("ordinary click edits code and automation failure shows an error", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/browser/open", async route => {
    calls++;
    await route.fulfill({ status: 503, json: { detail: "Allow Chrome in Automation." } });
  });
  await page.locator(".code-preview [data-imd-url]").click();
  await expect(page.getByRole("textbox", { name: "Code editor" })).toBeVisible();
  expect(calls).toBe(0);
  await page.locator(".cm-content [data-imd-url]").click({ modifiers: ["Meta"] });
  await expect(page.getByRole("alert")).toContainText("Allow Chrome in Automation.");
  expect(calls).toBe(1);
});

test("code links stay complete across syntax colors", async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  const targetUrl = "http://127.0.0.1:8123/path?x=1#part";
  await request.put("/api/document", { headers, data: {
    source: `\`\`\`python\n${targetUrl}\n\`\`\`\n`, revision: current.revision,
  } });
  await page.reload();
  const calls = [];
  await page.route("**/api/browser/open", async route => {
    calls.push(route.request().postDataJSON());
    await route.fulfill({ json: { action: "focused" } });
  });
  await page.locator(".code-preview [data-imd-url]").first().click({ modifiers: ["Meta"] });
  await expect.poll(() => calls).toEqual([{ url: targetUrl }]);
});

test("live terminal links include wrapped lines and require Cmd", async ({ page, request }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const current = await (await request.get("/api/document", { headers })).json();
  const targetUrl = `http://localhost:8123/${"a".repeat(110)}`;
  await request.put("/api/document", { headers, data: {
    source: `\`\`\`python\n!printf '${targetUrl}\\n'; read value\n\`\`\`\n`, revision: current.revision,
  } });
  await page.reload();
  const calls = [];
  await page.route("**/api/browser/open", async route => {
    calls.push(route.request().postDataJSON());
    await route.fulfill({ json: { action: "focused" } });
  });
  await page.getByRole("button", { name: "Run current block" }).click();
  const row = page.locator(".xterm-rows > div").first();
  const screen = page.locator(".xterm-screen");
  await expect(row).toContainText("http://localhost:8123/");
  await screen.click({ position: { x: 25, y: 7 } });
  expect(calls).toHaveLength(0);
  await page.mouse.move(0, 0);
  await screen.hover({ position: { x: 40, y: 7 } });
  expect(errors).toEqual([]);
  await expect(page.locator(".xterm-cursor-pointer")).toHaveCount(1);
  await screen.click({ position: { x: 40, y: 7 }, modifiers: ["Meta"] });
  await expect.poll(() => calls).toEqual([{ url: targetUrl }]);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByRole("button", { name: "Run current block" })).toBeEnabled();
});

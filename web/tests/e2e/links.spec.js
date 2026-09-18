import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };
const source = "# Link test\n\n[Website](https://example.com)\n\n[File](./other.md)\n\n```python\ninput('Ready: ')\n```\n";

async function readDocument(request) {
  return (await request.get("/api/document", { headers })).json();
}

async function writeDocument(request, source) {
  const current = await readDocument(request);
  const response = await request.put("/api/document", {
    headers,
    data: { source, revision: current.revision },
  });
  expect(response.ok()).toBeTruthy();
}

test.beforeEach(async ({ page, request }) => {
  await writeDocument(request, source);
  await page.goto("/#token=browser-test");
  await expect(page.getByRole("heading", { name: "Link test" })).toBeVisible();
});

for (const [name, endpoint] of [["Website", "browser"], ["File", "paths"]]) {
  test(`blocks the ${name} link during execution and permits it after execution`, async ({ page }) => {
    const calls = [];
    await page.route(`**/api/${endpoint}/open`, async (route) => {
      calls.push(route.request().postDataJSON());
      await route.fulfill({ json: { action: "opened" } });
    });
    await page.getByRole("button", { name: "Run current block" }).click();
    await expect(page.getByRole("button", { name: "Stop", exact: true })).toBeEnabled();
    await page.getByRole("link", { name, exact: true }).click({ modifiers: ["Meta"] });
    try {
      await expect(page.getByRole("alert")).toHaveText("Wait for execution to finish before opening a link.");
      expect(calls).toHaveLength(0);
    } finally {
      await page.getByRole("button", { name: "Stop", exact: true }).click();
      await expect(page.getByTestId("save-status")).toHaveText("Saved");
    }
    await page.getByRole("link", { name, exact: true }).click({ modifiers: ["Meta"] });
    await expect.poll(() => calls.length).toBe(1);
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
}

test("saves the editor draft before opening a link", async ({ page, request }) => {
  const savedSources = [];
  await page.route("**/api/browser/open", async (route) => {
    savedSources.push((await readDocument(request)).source);
    await route.fulfill({ json: { action: "opened" } });
  });
  await page.getByRole("button", { name: "Source", exact: true }).click();
  const editor = page.locator(".cm-content");
  const draft = source + "\nDraft content\n";
  await editor.fill(draft);
  await editor.locator('[data-imd-url="https://example.com"]').click({ modifiers: ["Meta"] });
  await expect.poll(() => savedSources).toEqual([draft]);
});

test("keeps the file and blocks the link when saving conflicts", async ({ page, request }) => {
  const calls = [];
  await page.route("**/api/browser/open", async (route) => {
    calls.push(route.request().postDataJSON());
    await route.fulfill({ json: { action: "opened" } });
  });
  await page.getByRole("button", { name: "Source", exact: true }).click();
  const editor = page.locator(".cm-content");
  await editor.fill(source + "\nBrowser draft\n");
  const external = source + "\nExternal change\n";
  await writeDocument(request, external);
  await editor.locator('[data-imd-url="https://example.com"]').click({ modifiers: ["Meta"] });
  await expect(page.getByRole("alert")).toContainText("The file changed in another program.");
  expect(calls).toHaveLength(0);
  expect((await readDocument(request)).source).toBe(external);
});

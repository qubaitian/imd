import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };

async function openDocument(page, request, source) {
  const current = await (await request.get("/api/document", { headers })).json();
  await request.put("/api/document", { headers, data: { source, revision: current.revision } });
  await page.goto("/#token=browser-test");
}

test("plain output keeps its text, links, copy, and delete controls", async ({ page, request, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const text = "# Log\n  a   b\n```python\nprint(42)\n```\nhttps://example.com\n";
  const source = `\`\`\`python\nprint(${JSON.stringify(text)}, end='')\n\`\`\`\n`;
  await openDocument(page, request, source);
  await page.getByRole("button", { name: "Run current block" }).click();
  const output = page.locator(".output-block");
  await expect(output.locator("pre code")).toHaveText(text);
  await expect(output.getByRole("heading")).toHaveCount(0);
  await expect(output.getByRole("button", { name: "Run current block" })).toHaveCount(0);
  await output.locator("pre code").click();
  await expect(output.locator(".cm-editor")).toHaveCount(0);
  await output.getByRole("button", { name: "Copy output" }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(text);
  const links = [];
  await page.route("**/api/browser/open", async route => {
    links.push(route.request().postDataJSON().url);
    await route.fulfill({ json: { action: "opened" } });
  });
  await output.locator('[data-imd-url="https://example.com"]').click({ modifiers: ["Meta"] });
  await expect.poll(() => links).toEqual(["https://example.com"]);
  await page.reload();
  await expect(output.locator("pre code")).toHaveText(text);
  await output.getByRole("button", { name: "Delete output block" }).click();
  await expect(output).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run current block" })).toHaveCount(1);
  const saved = await (await request.get("/api/document", { headers })).json();
  expect(saved.source).not.toContain("imd:output");
});

test("Markdown output still renders headings and runs nested code", async ({ page, request }) => {
  const report = "# Report\n\n```python\nprint(7)\n```\n";
  const source = `\`\`\`\`shell\nprintf '%s' '${report}'\n\`\`\`\`\n`;
  await openDocument(page, request, source);
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.getByRole("heading", { name: "Report" })).toBeVisible();
  await page.locator(".output-block").getByRole("button", { name: "Run current block" }).click();
  await expect(page.locator(".output-block .output-block pre code")).toHaveText("7\n");
  await page.getByRole("button", { name: "Run current block" }).first().click();
  await expect(page.locator(".output-block .output-block")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Report" })).toBeVisible();
});

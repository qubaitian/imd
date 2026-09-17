import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };
const child = "## Child result\n\n```python\nprint('**Leaf result**')\n```";
const output = `# Generated\n\n\`\`\`python\nprint(${JSON.stringify(child)})\n\`\`\``;
const source = `\`\`\`python\nprint(${JSON.stringify(output)})\n\`\`\`\n\nKeep this.\n`;

async function read(request) {
  return (await request.get("/api/document", { headers })).json();
}

test.beforeEach(async ({ page, request }) => {
  const current = await read(request);
  await request.put("/api/document", { headers, data: { source, revision: current.revision } });
  await page.goto("/#token=browser-test");
});

test("runs Markdown output recursively and replaces each output region", async ({ page, request }, testInfo) => {
  const run = page.getByRole("button", { name: "Run current block" });
  await run.first().click();
  await expect(page.getByRole("heading", { name: "Generated", exact: true })).toBeVisible();
  await expect(run).toHaveCount(2);
  await run.nth(1).click();
  await expect(page.getByRole("heading", { name: "Child result", exact: true })).toBeVisible();
  await expect(run).toHaveCount(3);
  await run.nth(2).click();
  await expect(page.locator(".output-body strong")).toHaveText("Leaf result");
  await page.screenshot({ path: testInfo.outputPath("nested-output.png"), fullPage: true });
  const saved = await read(request);
  expect(saved.blocks.filter(block => block.kind === "output")).toHaveLength(3);
  await page.reload();
  await expect(page.locator(".output-body strong")).toHaveText("Leaf result");
  await run.nth(1).click();
  await expect(page.locator(".output-body strong")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Generated", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Child result", exact: true })).toBeVisible();
  await run.first().click();
  await expect(page.getByRole("heading", { name: "Child result", exact: true })).toHaveCount(0);
  await expect(run).toHaveCount(2);
  await expect(page.getByText("Keep this.", { exact: true })).toBeVisible();
});

test("deletes nested output and code without damaging the parent markers", async ({ page, request }) => {
  const run = page.getByRole("button", { name: "Run current block" });
  const del = page.getByRole("button", { name: "Delete output block", exact: true });
  await run.first().click();
  await expect(run).toHaveCount(2);
  await run.nth(1).click();
  await expect(run).toHaveCount(3);
  await del.nth(1).click();
  await expect(del).toHaveCount(1);
  await expect(run).toHaveCount(2);
  await run.nth(1).click();
  await expect(run).toHaveCount(3);
  await page.getByRole("button", { name: "Delete code block", exact: true }).nth(1).click();
  await expect(run).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Generated", exact: true })).toBeVisible();
  expect((await read(request)).blocks.filter(block => block.kind === "output")).toHaveLength(1);
  await del.first().click();
  await expect(del).toHaveCount(0);
  await expect(run).toHaveCount(1);
  expect((await read(request)).source).not.toContain("<!-- imd:output:");
  await expect(page.getByText("Keep this.", { exact: true })).toBeVisible();
});

test("runs a code block inside output from Source view", async ({ page, request }) => {
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.getByRole("heading", { name: "Generated", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Source", exact: true }).click();
  const editor = page.getByRole("textbox", { name: "Markdown editor" });
  await editor.locator(".cm-line").filter({ hasText: /^print\("## Child result/ }).click();
  await editor.press("Shift+Enter");
  await expect.poll(async () => (await read(request)).blocks.filter(block => block.kind === "output").length).toBe(2);
  await page.getByRole("button", { name: "Document", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Child result", exact: true })).toBeVisible();
});

test("keeps live output as text and renders Markdown when input completes", async ({ page, request }) => {
  const current = await read(request);
  const live = "```python\nprint('# Pending')\ninput('Continue: ')\nprint('**Done**')\n```\n";
  await request.put("/api/document", { headers, data: { source: live, revision: current.revision } });
  await page.reload();
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.locator(".live-output pre")).toContainText("# Pending");
  await expect(page.getByRole("heading", { name: "Pending", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Delete code block", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Delete output block", exact: true })).toBeDisabled();
  await page.getByRole("textbox", { name: "Command input" }).fill("yes");
  await page.getByRole("textbox", { name: "Command input" }).press("Enter");
  await expect(page.getByRole("heading", { name: "Pending", exact: true })).toBeVisible();
  await expect(page.locator(".output-body strong")).toHaveText("Done");
  await expect(page.locator(".live-output")).toHaveCount(0);
});

test("treats an out fence as runnable code", async ({ page, request }) => {
  const current = await read(request);
  const legacy = "```out\nprint('## Ordinary code')\n```\n";
  await request.put("/api/document", { headers, data: { source: legacy, revision: current.revision } });
  await page.reload();
  await expect(page.getByRole("button", { name: "Delete output block", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.getByRole("heading", { name: "Ordinary code", exact: true })).toBeVisible();
  expect((await read(request)).source).toContain("```out\n");
});

test("edits a nested code block and saves its marked result", async ({ page, request }) => {
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.getByRole("heading", { name: "Generated", exact: true })).toBeVisible();
  await page.locator(".output-body .code-preview").click();
  const editor = page.getByRole("textbox", { name: "Code editor" });
  await editor.fill("print('## Edited result')");
  await editor.press("Shift+Enter");
  await expect(page.getByRole("heading", { name: "Edited result", exact: true })).toBeVisible();
  await expect(editor).toHaveText("print('## Edited result')");
  const saved = await read(request);
  expect(saved.blocks.filter(block => block.kind === "output")).toHaveLength(2);
  expect(saved.blocks.filter(block => block.kind === "code")[1].code).toBe("print('## Edited result')\n");
});

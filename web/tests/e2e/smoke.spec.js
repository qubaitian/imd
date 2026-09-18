import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };
const source = "# Smoke test\n\n```python\nprint(1 + 1)\n```\n";

test("opens the document and runs one code block", async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  await request.put("/api/document", {
    headers,
    data: { source, revision: current.revision },
  });
  await page.goto("/#token=browser-test");
  await expect(page.getByRole("heading", { name: "Smoke test" })).toBeVisible();
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.locator(".output-body")).toHaveText("2");
});

test("keeps session routes and tokens separate on one origin", async ({ page, request }) => {
  for (const number of [1, 2]) {
    const auth = { Authorization: `Bearer browser-${number}` };
    const current = await (await request.get(`/${number}/api/document`, { headers: auth })).json();
    await request.put(`/${number}/api/document`, {
      headers: auth,
      data: { source: `# Session ${number}\n\n\`\`\`python\nprint(${number} + 2)\n\`\`\`\n`, revision: current.revision },
    });
    await page.goto(`/${number}/#token=browser-${number}`);
    await expect(page.getByRole("heading", { name: `Session ${number}` })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/${number}/$`));
  }
  await page.goto("/1/");
  await expect(page.getByRole("heading", { name: "Session 1" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Session 1" })).toBeVisible();
  await page.getByRole("button", { name: "Run current block" }).click();
  await expect(page.locator(".output-body")).toHaveText("3");
  await page.goto("/2/");
  await expect(page.getByRole("heading", { name: "Session 2" })).toBeVisible();
  await expect(page.locator(".output-body")).toHaveCount(0);
});

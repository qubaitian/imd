import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };
const source = "# Smoke test\n\n```python\n1 + 1\n```\n";

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

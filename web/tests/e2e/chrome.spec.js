import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };

test("shows the absolute path in the title and hides the old chrome", async ({
  page,
  request,
}) => {
  const session = await (
    await request.get("/api/session", { headers })
  ).json();
  const path = session.documents[0].path;
  const current = await (await request.get("/api/document", { headers })).json();
  await request.put("/api/document", {
    headers,
    data: { source: "# Chrome\n\nParagraph.\n", revision: current.revision },
  });
  await page.goto("/#token=browser-test");
  await expect(page.getByRole("heading", { name: "Chrome" })).toBeVisible();
  await expect(page.locator(".breadcrumb-path")).toHaveAttribute("title", path);
  expect(await page.locator(".breadcrumb-path").textContent()).toBe(path);
  await expect(page.getByText("Local", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "＋ Text" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "＋ Code" })).toHaveCount(0);
  await expect(page.locator(".statusbar")).toHaveCount(0);
  await expect(page).toHaveTitle("document.md · IMD");
  await page.getByRole("button", { name: "Source", exact: true }).click();
  await expect(page.locator(".source-title")).toHaveCount(0);
  await expect(page.locator(".cm-content")).toBeVisible();
});

test("keeps empty-file start buttons", async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  await request.put("/api/document", {
    headers,
    data: { source: "", revision: current.revision },
  });
  await page.goto("/#token=browser-test");
  await expect(page.getByRole("button", { name: /Write Markdown/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add a code block" })).toBeVisible();
  await expect(page.getByRole("button", { name: "＋ Text" })).toHaveCount(0);
});

import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-panels" };
const session = "/panels";
const panel = (page, name) => page.locator(".session-layout > .app-shell").filter({
  has: page.locator(".breadcrumb", { hasText: name }),
});
const names = (page) => page.locator(".session-layout > .app-shell .breadcrumb-path");
let documents;

function expectedPaths(order) {
  const lookup = Object.fromEntries(
    documents.map((item) => [item.path.split("/").pop(), item.path]),
  );
  return order.map((name) => lookup[name]);
}

async function expectPanelPaths(page, order) {
  await expect.poll(async () =>
    names(page).evaluateAll((elements) =>
      elements.map((element) => element.getAttribute("title") || element.textContent),
    ),
  ).toEqual(expectedPaths(order));
}

async function drag(page, from, to, side = "left", release = true) {
  const handle = await from.locator(".breadcrumb").boundingBox();
  const target = await to.boundingBox();
  await page.mouse.move(handle.x + 15, handle.y + handle.height / 2);
  await page.mouse.down();
  await page.mouse.move(side === "left" ? target.x + 4 : target.x + target.width - 4, handle.y + handle.height / 2, { steps: 12 });
  if (release) await page.mouse.up();
}

test.use({ viewport: { width: 1800, height: 800 } });

test.beforeEach(async ({ page, request }) => {
  documents = (await (await request.get(session + "/api/session", { headers })).json()).documents;
  if (!documents.some((item) => item.path.endsWith("notes.txt"))) {
    await request.post(session + "/api/paths/open", { headers, data: { path: "notes.txt" } });
    documents = (await (await request.get(session + "/api/session", { headers })).json()).documents;
  }
  for (const item of documents.filter((item) => !item.readonly)) {
    const url = session + item.base + "/api/document";
    const current = await (await request.get(url, { headers })).json();
    const name = item.path.split("/").pop();
    await request.put(url, { headers, data: {
      source: `# ${name}\n\n[Open A](./a.md)\n\n\`\`\`python\nimport time\ntime.sleep(2)\nprint('Finished')\n\`\`\`\n\n` + "Paragraph.\n\n".repeat(60),
      revision: current.revision,
    } });
  }
  const sorted = documents.toSorted((a, b) => a.path.localeCompare(b.path));
  await request.put(session + "/api/session/order", { headers, data: { ids: sorted.map((item) => item.id) } });
  await page.goto(session + "/#token=browser-panels");
  await expect(panel(page, "a.md").getByRole("heading", { name: "a.md", exact: true })).toBeVisible();
});

test("shows the absolute path and hides the status bar on every panel", async ({ page }) => {
  await expectPanelPaths(page, ["a.md", "b.md", "c.md", "notes.txt"]);
  await expect(page.locator(".statusbar")).toHaveCount(0);
  await expect(page.getByText("Local", { exact: true })).toHaveCount(0);
});

test("moves panels across neighbors and restores session order on reload", async ({ page, request }) => {
  await panel(page, "c.md").locator(".document-scroll").evaluate((element) => { element.scrollTo({ top: 300, behavior: "instant" }); });
  const scroll = await panel(page, "c.md").locator(".document-scroll").evaluate((element) => element.scrollTop);
  await drag(page, panel(page, "c.md"), panel(page, "a.md"));
  await expectPanelPaths(page, ["c.md", "a.md", "b.md", "notes.txt"]);
  expect(await panel(page, "c.md").locator(".document-scroll").evaluate((element) => element.scrollTop)).toBe(scroll);
  await expect.poll(async () => (await (await request.get(session + "/api/session", { headers })).json()).documents.map((item) => item.path.split("/").pop()))
    .toEqual(["c.md", "a.md", "b.md", "notes.txt"]);
  await page.reload();
  await expectPanelPaths(page, ["c.md", "a.md", "b.md", "notes.txt"]);
  await drag(page, panel(page, "c.md"), panel(page, "notes.txt"), "right");
  await expectPanelPaths(page, ["a.md", "b.md", "notes.txt", "c.md"]);
  await expect(page).toHaveTitle("a.md | b.md | notes.txt | c.md · IMD");
  await drag(page, panel(page, "notes.txt"), panel(page, "a.md"));
  await expectPanelPaths(page, ["notes.txt", "a.md", "b.md", "c.md"]);
});

test("keeps the editor draft and scroll position when a panel moves", async ({ page }) => {
  const a = panel(page, "a.md");
  const b = panel(page, "b.md");
  await a.getByRole("button", { name: "Source", exact: true }).click();
  await a.locator(".cm-content").fill("# Unsaved draft\n");
  await b.locator(".document-scroll").evaluate((element) => { element.scrollTo({ top: 300, behavior: "instant" }); });
  const scroll = await b.locator(".document-scroll").evaluate((element) => element.scrollTop);
  await a.locator(".cm-content").evaluate((element) => { window.panelEditor = element; });
  await drag(page, a, panel(page, "c.md"), "right");
  await expectPanelPaths(page, ["b.md", "c.md", "a.md", "notes.txt"]);
  await expect(a.locator(".cm-content")).toHaveText("# Unsaved draft");
  expect(await a.locator(".cm-content").evaluate((element) => element === window.panelEditor)).toBe(true);
  expect(await b.locator(".document-scroll").evaluate((element) => element.scrollTop)).toBe(scroll);
});

test("keeps running code connected while the panel moves", async ({ page }) => {
  const a = panel(page, "a.md");
  await a.getByRole("button", { name: "Run current block" }).click();
  await expect(a.getByRole("button", { name: "Stop", exact: true })).toBeEnabled();
  await drag(page, a, panel(page, "c.md"), "right");
  await expectPanelPaths(page, ["b.md", "c.md", "a.md", "notes.txt"]);
  await expect(a.getByTestId("save-status")).toHaveText("Running");
  await expect(a.getByRole("button", { name: "Stop", exact: true })).toBeEnabled();
  await expect(a.getByTestId("save-status")).toHaveText("Saved", { timeout: 15000 });
  await expect(a.locator(".output-body pre code")).toHaveText("Finished");
});

test("cancels a drag and keeps title bar buttons clickable", async ({ page }) => {
  await drag(page, panel(page, "notes.txt"), panel(page, "a.md"), "left", false);
  await page.keyboard.press("Escape");
  await page.mouse.up();
  await expectPanelPaths(page, ["a.md", "b.md", "c.md", "notes.txt"]);
  await panel(page, "a.md").getByRole("button", { name: "Source", exact: true }).click();
  await expect(panel(page, "a.md").locator(".cm-content")).toBeVisible();
});

test("reports a failed order save and keeps the original order", async ({ page }) => {
  await page.route("**/api/session/order", (route) => route.fulfill({ status: 503, json: { detail: "Cannot save panel order." } }));
  await drag(page, panel(page, "notes.txt"), panel(page, "a.md"));
  await expect(page.getByRole("alert")).toHaveText("Cannot save panel order.");
  await expectPanelPaths(page, ["a.md", "b.md", "c.md", "notes.txt"]);
});

test("moves repeated file panels without exchanging their drafts", async ({ page }) => {
  await panel(page, "a.md").getByRole("link", { name: "Open A" }).click({ modifiers: ["Meta"] });
  await expect(panel(page, "a.md")).toHaveCount(2);
  const repeated = panel(page, "a.md").nth(1);
  await repeated.getByRole("button", { name: "Source", exact: true }).click();
  await repeated.locator(".cm-content").fill("# Separate draft\n");
  await drag(page, repeated, panel(page, "b.md"));
  await expectPanelPaths(page, ["a.md", "a.md", "b.md", "c.md", "notes.txt"]);
  await expect(panel(page, "a.md").nth(1).locator(".cm-content")).toHaveText("# Separate draft");
  await expect(panel(page, "a.md").first().locator(".cm-content")).toHaveCount(0);
});

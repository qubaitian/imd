import { test, expect } from "@playwright/test";

const headers = { Authorization: "Bearer browser-test" };
const path = "./notes.md";
const source = `# Paths\n\nOpen [notes](${path}) or ${path}.\n\n\`\`\`python\nfile = "${path}"\n\`\`\`\n\n<!-- imd:output:begin fixture -->\n\n('${path}',)\n\n<!-- imd:output:end fixture -->\n`;

test.beforeEach(async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  await request.put("/api/document", { headers, data: { source, revision: current.revision } });
  await page.goto("/#token=browser-test");
  await expect(page.getByRole("heading", { name: "Paths", exact: true })).toBeVisible();
});

for (const location of ["preview", "markdown editor", "code preview", "code editor", "output", "source"]) {
  test(`Cmd click opens a local path from ${location}`, async ({ page, request, context }) => {
    const calls = [];
    await page.route("**/api/paths/open", route => {
      calls.push(route.request().postDataJSON());
      return route.fulfill({ json: { action: "focused" } });
    });
    let target;
    if (location === "preview") target = page.getByRole("link", { name: "notes", exact: true });
    if (location === "code preview") target = page.locator(".code-preview [data-imd-path]");
    if (location === "output") target = page.locator(".output-body [data-imd-path]");
    if (location === "markdown editor") {
      await page.locator(".prose-block").filter({ hasText: "Open" }).click({ position: { x: 4, y: 4 } });
      target = page.locator(".markdown-edit [data-imd-path]").first();
    }
    if (location === "code editor") {
      await page.locator(".code-preview").click();
      target = page.locator(".cm-content [data-imd-path]");
    }
    if (location === "source") {
      await page.getByRole("button", { name: "Source", exact: true }).click();
      target = page.locator(".cm-content [data-imd-path]").first();
    }
    await target.click({ modifiers: ["Meta"] });
    await expect.poll(() => calls).toEqual([{ path }]);
    expect(context.pages()).toHaveLength(1);
    expect((await (await request.get("/api/document", { headers })).json()).source).toBe(source);
  });
}

test("file clicks append equal panels and text stays read-only", async ({ page }) => {
  await page.route("**/api/paths/open", route => route.fulfill({ json: {
    document: { path: "/tmp/notes.txt", base: "/test-text", readonly: true },
  } }));
  await page.route("**/test-text/api/document", route => route.fulfill({ json: {
    path: "/tmp/notes.txt", name: "notes.txt", source: "<script>unsafe</script>\n./next.md\n", readonly: true,
  } }));
  const target = page.getByRole("link", { name: "notes", exact: true });
  await target.click({ modifiers: ["Meta"] });
  await expect(page.locator(".session-layout > .app-shell")).toHaveCount(2);
  await target.click({ modifiers: ["Meta"] });
  const panels = page.locator(".session-layout > .app-shell");
  await expect(panels).toHaveCount(3);
  const widths = await panels.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().width));
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThan(2);
  await expect(panels.nth(1)).toContainText("<script>unsafe</script>");
  await expect(panels.nth(1).locator("[contenteditable=true], textarea, script")).toHaveCount(0);
  await expect(panels.nth(1).getByRole("button", { name: "Run current block" })).toHaveCount(0);
  await expect(panels.nth(1).locator("[data-imd-path]")).toHaveText("./next.md");
});

test("path errors show in the document without adding panels", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/paths/open", route => {
    calls++;
    return route.fulfill({ status: 404, json: { detail: "The path does not exist." } });
  });
  await page.locator(".code-preview [data-imd-path]").click();
  await expect(page.getByRole("textbox", { name: "Code editor" })).toBeVisible();
  expect(calls).toBe(0);
  await page.locator(".cm-content [data-imd-path]").click({ modifiers: ["Meta"] });
  await expect(page.getByRole("alert")).toContainText("The path does not exist.");
  await expect(page.locator(".session-layout > .app-shell")).toHaveCount(1);
});

test("path detection preserves HTTP links and supports quoted spaces", async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  const paths = ["/Users/example/项目/file.md", "../other", "web/src/App.svelte", "README.md", "./my folder/a.md"];
  await request.put("/api/document", { headers, data: {
    source: `<!-- imd:output:begin fixture -->\n\n${paths.map(value => `'${value}'`).join("\n")}\nhttp://localhost:8123/a.md\nwww.example.com\nplain words\n\n<!-- imd:output:end fixture -->\n`,
    revision: current.revision,
  } });
  await page.reload();
  await expect(page.locator(".output-body [data-imd-path]")).toHaveText(paths);
  await expect(page.locator(".output-body :is(a[href], [data-imd-url])")).toHaveText("http://localhost:8123/a.md");
});

test("Markdown panels save edits and open further paths", async ({ page, request }) => {
  const value = "# Child\n\n./another.md\n";
  const parsed = await (await request.post("/api/parse", { headers, data: { source: value } })).json();
  let doc = { path: "/tmp/child.md", name: "child.md", source: value, revision: "first", blocks: parsed.blocks };
  const calls = [];
  await page.route("**/api/paths/open", route => {
    calls.push(route.request().postDataJSON());
    return route.fulfill({ json: { document: { path: doc.path, base: "/test-md", readonly: false } } });
  });
  await page.route("**/test-md/api/document", async route => {
    if (route.request().method() === "PUT") {
      const { source } = route.request().postDataJSON();
      const parsed = await (await request.post("/api/parse", { headers, data: { source } })).json();
      doc = { ...doc, source, blocks: parsed.blocks, revision: "second" };
    }
    await route.fulfill({ json: doc });
  });
  await page.getByRole("link", { name: "notes", exact: true }).click({ modifiers: ["Meta"] });
  const child = page.locator(".session-layout > .app-shell").nth(1);
  await expect(child.getByRole("heading", { name: "Child", exact: true })).toBeVisible();
  await child.locator("[data-imd-path]").click({ modifiers: ["Meta"] });
  await expect(page.locator(".session-layout > .app-shell")).toHaveCount(3);
  expect(calls).toEqual([{ path }, { path: "./another.md" }]);
  await child.getByRole("button", { name: "Source", exact: true }).click();
  const editor = child.getByRole("textbox", { name: "Markdown editor" });
  await editor.fill("# Edited child\n");
  await editor.press("Meta+s");
  await expect.poll(() => doc.source).toBe("# Edited child\n");
  await expect(child.getByTestId("save-status")).toHaveText("Saved");
  await expect(page.getByRole("heading", { name: "Paths", exact: true })).toBeVisible();
});

test("live terminal path links include wrapped lines and require Cmd", async ({ page, request }) => {
  const current = await (await request.get("/api/document", { headers })).json();
  const targetPath = `/tmp/${"a".repeat(110)}/notes.md`;
  await request.put("/api/document", { headers, data: {
    source: `\`\`\`python\n!printf '${targetPath}\\n'; read value\n\`\`\`\n`, revision: current.revision,
  } });
  await page.reload();
  const calls = [];
  await page.route("**/api/paths/open", route => {
    calls.push(route.request().postDataJSON());
    return route.fulfill({ json: { action: "focused" } });
  });
  await page.getByRole("button", { name: "Run current block" }).click();
  const screen = page.locator(".xterm-screen");
  await expect(page.locator(".xterm-rows > div").first()).toContainText("/tmp/");
  await screen.click({ position: { x: 25, y: 7 } });
  expect(calls).toHaveLength(0);
  await page.mouse.move(0, 0);
  await screen.hover({ position: { x: 40, y: 7 } });
  await expect(page.locator(".xterm-cursor-pointer")).toHaveCount(1);
  await screen.click({ position: { x: 40, y: 7 }, modifiers: ["Meta"] });
  await expect.poll(() => calls).toEqual([{ path: targetPath }]);
  await expect(page.locator(".session-layout > .app-shell")).toHaveCount(1);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByRole("button", { name: "Run current block" })).toBeEnabled();
});

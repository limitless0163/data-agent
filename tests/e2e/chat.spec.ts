import { expect, test } from "../../frontend/tests/e2e-fixtures";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("question travels through Next proxy, FastAPI, graph, SQL and renders results", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page).toHaveTitle("掌柜问数");
  await page.getByRole("textbox").fill("华东销售额");
  await page.getByRole("button", { name: "发送" }).click();
  const table = page.getByRole("table");
  await expect(table.getByRole("columnheader")).toHaveText(["地区", "销售额"]);
  await expect(table.getByRole("cell")).toHaveText(["华东", "30.5"]);
  await expect(page.getByText("生成SQL", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
  await page.getByRole("textbox").fill("测试校正");
  await page.getByRole("textbox").press("Enter");
  await expect(page.getByText("校正SQL", { exact: true })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(2);
  expect(errors).toEqual([]);
});

test("model failure shows error and a subsequent request succeeds", async ({ page }) => {
  await page.getByRole("textbox").fill("模型故障");
  await page.getByRole("textbox").press("Enter");
  await expect(page.getByText("测试模型不可用", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
  await page.getByRole("textbox").fill("华东销售额");
  await page.getByRole("textbox").press("Enter");
  await expect(page.getByRole("table").getByRole("cell")).toHaveText(["华东", "30.5"]);
});

test("empty query results are rendered without crashing", async ({ page }) => {
  await page.getByRole("textbox").fill("空结果");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByRole("table")).toBeAttached();
  await expect(page.getByRole("cell")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
});

test("proxy preserves FastAPI invalid input and SSE HTTP contract", async ({ request }) => {
  for (const data of [{}, { query: null }, { query: 42 }]) {
    const invalid = await request.post("/api/query", { data });
    expect(invalid.status()).toBe(422);
    expect((await invalid.json()).detail).toBeTruthy();
  }
  const response = await request.post("/api/query", { data: { query: "华东销售额" } });
  expect(response.headers()["content-type"]).toContain("text/event-stream");
  expect(response.headers()["cache-control"]).toBe("no-cache, no-transform");
  const frames = (await response.text()).trim().split("\n\n").map(frame => JSON.parse(frame.slice(6)));
  expect(frames.at(-1)).toEqual({ type: "result", data: [{ 地区: "华东", 销售额: 30.5 }] });
  expect(frames.some(event => event.type === "progress" && event.status === "running")).toBe(true);
});

test("concurrent clients keep request state and data separate", async ({ browser }) => {
  const first = await browser.newContext();
  const second = await browser.newContext();
  try {
    const pages = await Promise.all([first.newPage(), second.newPage()]);
    await Promise.all(pages.map(page => page.goto("http://127.0.0.1:3100")));
    await pages[0].getByRole("textbox").fill("华东销售额");
    await pages[1].getByRole("textbox").fill("模型故障");
    await Promise.all(pages.map(page => page.getByRole("textbox").press("Enter")));
    await expect(pages[0].getByRole("table")).toBeVisible();
    await expect(pages[1].getByText("测试模型不可用", { exact: true })).toBeVisible();
    await expect(pages[0].getByText("测试模型不可用", { exact: true })).toHaveCount(0);
    await expect(pages[1].getByRole("table")).toHaveCount(0);
  } finally {
    await first.close();
    await second.close();
  }
});


test("HTTP failure restores the form and allows retry", async ({ page }) => {
  await page.route("**/api/query", route => route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ message: "后端服务不可用" }) }), { times: 1 });
  await page.getByRole("textbox").fill("华东销售额");
  await page.getByRole("textbox").press("Enter");
  await expect(page.getByText("请求失败 (502)", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
  await page.getByRole("textbox").fill("华东销售额");
  await page.getByRole("textbox").press("Enter");
  await expect(page.getByRole("table")).toBeVisible();
});

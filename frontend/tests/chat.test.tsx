// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ChatPage from "../src/features/chat/ChatPage";
import { queryStream } from "../src/services/query";
import type { QueryEvent } from "../src/types/query";

vi.mock("../src/services/query", () => ({ queryStream: vi.fn() }));
afterEach(cleanup);
function events(...values: QueryEvent[]) {
  vi.mocked(queryStream).mockImplementation(async function* () { yield* values; });
}
const input = () => screen.getByRole("textbox", { name: "请输入你的问题" });
async function submit(question = "华东销售额") {
  const user = userEvent.setup();
  await user.type(input(), question);
  await user.click(screen.getByRole("button", { name: "发送" }));
}

describe("chat form and request state", () => {
  it("does not send empty or whitespace-only questions", async () => {
    render(<ChatPage />);
    await userEvent.click(screen.getByRole("button", { name: "发送" }));
    await submit("   ");
    expect(queryStream).not.toHaveBeenCalled();
  });
  it("updates the same progress step and renders typed and null table cells", async () => {
    events({ type: "progress", step: "生成SQL", status: "running" },
      { type: "progress", step: "生成SQL", status: "success" },
      { type: "result", data: [{ 地区: "华东", 金额: 0, 备注: null, 有效: false }] });
    const { container } = render(<ChatPage />);
    await submit();
    expect(queryStream).toHaveBeenCalledWith("华东销售额");
    expect(screen.getByText("华东销售额")).toBeInTheDocument();
    expect(input()).toHaveValue("");
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("columnheader").map(cell => cell.textContent)).toEqual(["地区", "金额", "备注", "有效"]);
    expect(within(table).getAllByRole("cell").map(cell => cell.textContent)).toEqual(["华东", "0", "", "false"]);
    expect(screen.getAllByText("生成SQL")).toHaveLength(1);
    expect(container.querySelector(".dot.success")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
  });
  it("shows an empty result without crashing", async () => {
    events({ type: "result", data: [] });
    render(<ChatPage />); await submit();
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.queryAllByRole("cell")).toHaveLength(0);
  });
  it("guards duplicate submissions and preserves the next input while busy", async () => {
    let finish!: () => void;
    const blocked = new Promise<void>(resolve => { finish = resolve; });
    vi.mocked(queryStream).mockImplementation(async function* () { await blocked; yield { type: "result", data: [] }; });
    render(<ChatPage />); await submit("第一问");
    expect(screen.getByRole("button", { name: "执行中..." })).toBeDisabled();
    await userEvent.type(input(), "第二问{Enter}{Enter}");
    expect(queryStream).toHaveBeenCalledTimes(1);
    expect(input()).toHaveValue("第二问");
    await act(async () => { finish(); });
    await waitFor(() => expect(screen.getByRole("button", { name: "发送" })).toBeEnabled());
    events({ type: "result", data: [{ 次数: 2 }] });
    await userEvent.type(input(), "{Enter}");
    expect(await screen.findByText("第二问")).toBeInTheDocument();
    expect(queryStream).toHaveBeenCalledTimes(2);
    expect(screen.getAllByRole("table")).toHaveLength(2);
  });
  it("does not submit Enter while a Chinese IME composition is active", async () => {
    events(); render(<ChatPage />);
    fireEvent.change(input(), { target: { value: "中文" } });
    fireEvent.keyDown(input(), { key: "Enter", isComposing: true, keyCode: 229 });
    expect(queryStream).not.toHaveBeenCalled();
    fireEvent.keyDown(input(), { key: "Enter" });
    await waitFor(() => expect(queryStream).toHaveBeenCalledWith("中文"));
  });
  it("displays SSE errors and permits a fresh question", async () => {
    events({ type: "progress", step: "执行SQL", status: "error" }, { type: "error", message: "查询失败" }, { type: "error" });
    const { container } = render(<ChatPage />); await submit();
    expect(await screen.findByText("查询失败")).toBeInTheDocument();
    expect(screen.getByText("发生错误")).toBeInTheDocument();
    expect(container.querySelector(".dot.error")).toBeInTheDocument();
    events({ type: "result", data: [{ 订单数: 3 }] }); await submit("重试");
    expect(await screen.findByText("3")).toBeInTheDocument();
  });
  it.each([new Error("连接断开"), "unknown"])("recovers after a thrown failure %s", async failure => {
    vi.mocked(queryStream).mockImplementation(async function* () { throw failure; });
    render(<ChatPage />); await submit();
    expect(await screen.findByText(failure instanceof Error ? failure.message : "请求失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
  });
  it("scrolls the message container as messages arrive", async () => {
    events({ type: "result", data: [] });
    const { container } = render(<ChatPage />);
    const messages = container.querySelector(".messages")!;
    Object.defineProperty(messages, "scrollHeight", { configurable: true, value: 400 });
    await submit(); await screen.findByRole("table");
    expect(messages.scrollTop).toBe(400);
  });
});

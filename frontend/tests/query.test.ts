import { describe, expect, it, vi } from "vitest";
import { queryStream } from "../src/services/query";

const encoder = new TextEncoder();
function mockStream(chunks: Uint8Array[]) {
  const cancel = vi.fn();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) { for (const chunk of chunks) controller.enqueue(chunk); controller.close(); },
    cancel,
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
  return { stream, cancel };
}
async function collect() {
  const events = [];
  for await (const event of queryStream("华东销售额")) events.push(event);
  return events;
}

describe("queryStream", () => {
  it("posts JSON and decodes Chinese across byte boundaries and CRLF frames", async () => {
    const bytes = encoder.encode('data: {"type":"progress","step":"生成SQL","status":"running"}\r\n\r\ndata: {"type":"result","data":[{"销售额":"12.30"}]}\n\n');
    const { stream } = mockStream(Array.from(bytes, byte => Uint8Array.of(byte)));
    expect(await collect()).toEqual([
      { type: "progress", step: "生成SQL", status: "running" },
      { type: "result", data: [{ 销售额: "12.30" }] },
    ]);
    expect(fetch).toHaveBeenCalledWith("/api/query", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: "华东销售额" }),
    });
    expect(stream.locked).toBe(false);
  });
  it("ignores comments and malformed JSON, then continues with errors and empty results", async () => {
    mockStream([encoder.encode(': heartbeat\n\ndata: broken\n\ndata: {"type":"error","message":"失败"}\n\ndata: {"type":"result","data":[]}\n\n')]);
    expect(await collect()).toEqual([{ type: "error", message: "失败" }, { type: "result", data: [] }]);
  });
  it("ignores valid JSON that does not match the event contract", async () => {
    mockStream([encoder.encode('data: null\n\ndata: {}\n\ndata: {"type":"progress","status":"unknown","step":"错误"}\n\ndata: {"type":"progress","status":["running"],"step":"错误"}\n\ndata: {"type":"result","data":[null]}\n\ndata: {"type":"result","data":[]}\n\n')]);
    expect(await collect()).toEqual([{ type: "result", data: [] }]);
  });
  it.each([422, 502])("rejects HTTP %s before reading a body", async status => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("error", { status })));
    await expect(collect()).rejects.toThrow(`请求失败 (${status})`);
  });
  it("reports a missing body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null)));
    await expect(collect()).rejects.toThrow("服务器未返回流");
  });
  it("propagates network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(collect()).rejects.toThrow("offline");
  });
  it("releases the reader after a stream failure", async () => {
    const stream = new ReadableStream({ start(controller) { controller.error(new Error("disconnected")); } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
    await expect(collect()).rejects.toThrow("disconnected");
    expect(stream.locked).toBe(false);
  });
  it("cancels the source when the consumer stops early", async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream({ start(controller) { controller.enqueue(encoder.encode('data: {"type":"result","data":[]}\n\n')); }, cancel });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
    for await (const event of queryStream("test")) { expect(event.type).toBe("result"); break; }
    expect(cancel).toHaveBeenCalledOnce();
    expect(stream.locked).toBe(false);
  });
});

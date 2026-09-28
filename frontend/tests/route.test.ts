import { describe, expect, it, vi } from "vitest";
import { POST } from "../src/app/api/query/route";

function request(body = '{"query":"订单数"}') {
  return new Request("http://frontend/api/query", { method: "POST", body });
}
describe("SSE proxy", () => {
  it("passes through streaming body, status, headers and cancellation", async () => {
    vi.stubEnv("API_BASE_URL", "http://test-backend:8000");
    const stream = new ReadableStream<Uint8Array>();
    const upstream = new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(upstream));
    const req = request();
    const response = await POST(req);
    expect(response.body).toBe(upstream.body);
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream");
    expect(response.headers.get("cache-control")).toBe("no-cache, no-transform");
    expect(fetch).toHaveBeenCalledWith("http://test-backend:8000/api/query", {
      method: "POST", headers: { "Content-Type": "application/json", "Cache-Control": "no-cache" },
      body: '{"query":"订单数"}', cache: "no-store", signal: req.signal,
    });
  });
  it("uses the local default and preserves validation errors", async () => {
    vi.stubEnv("API_BASE_URL", undefined);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "invalid" }, { status: 422 })));
    const response = await POST(request("{}"));
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe("http://localhost:8000/api/query");
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ detail: "invalid" });
    expect(response.headers.get("content-type")).toContain("application/json");
  });
  it("provides SSE content type when upstream omits it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null)));
    expect((await POST(request())).headers.get("content-type")).toBe("text/event-stream; charset=utf-8");
  });
  it("maps connection errors to the public 502 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret connection string")));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ message: "后端服务不可用" });
  });
});

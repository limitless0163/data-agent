export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const upstream = await fetch(`${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Cache-Control": "no-cache" },
      body: await request.text(),
      cache: "no-store",
      // 将客户端取消信号传给上游，停止对应的后端请求。
      signal: request.signal,
    });

    // 直接透传响应流，避免缓冲完整结果后才显示进度。
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") ?? "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
      },
    });
  } catch {
    return Response.json({ message: "后端服务不可用" }, { status: 502 });
  }
}

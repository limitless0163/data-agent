import type { QueryEvent } from "../types/query";

export async function* queryStream(query: string): AsyncGenerator<QueryEvent> {
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) throw new Error(`请求失败 (${response.status})`);
  if (!response.body) throw new Error("服务器未返回流");

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() ?? "";

      for (const event of events) {
        const data = event.split(/\r?\n/).find((line) => line.startsWith("data:"));
        if (!data) continue;
        try {
          yield JSON.parse(data.slice(5).trim()) as QueryEvent;
        } catch {
          // Ignore malformed events and keep reading the stream.
        }
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}

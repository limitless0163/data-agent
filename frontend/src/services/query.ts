import type { QueryEvent } from "../types/query";

function isQueryEvent(value: unknown): value is QueryEvent {
  if (!value || typeof value !== "object") return false;
  const event = value as Record<string, unknown>;
  if (event.type === "progress") {
    return typeof event.step === "string" && typeof event.status === "string" && ["running", "success", "error"].includes(event.status);
  }
  if (event.type === "result") {
    return Array.isArray(event.data) && event.data.every(row => row !== null && typeof row === "object" && !Array.isArray(row));
  }
  return event.type === "error" && (event.message === undefined || typeof event.message === "string");
}

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
  let completed = false;

  try {
    while (true) {
      const { value, done } = await reader.read();
      completed = done;
      buffer += decoder.decode(value, { stream: !done });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() ?? "";

      for (const event of events) {
        const data = event.split(/\r?\n/).find((line) => line.startsWith("data:"));
        if (!data) continue;
        try {
          const parsed: unknown = JSON.parse(data.slice(5).trim());
          if (isQueryEvent(parsed)) yield parsed;
        } catch {
          // Ignore malformed events and keep reading the stream.
        }
      }
      if (done) break;
    }
  } finally {
    try {
      if (!completed) await reader.cancel();
    } finally {
      reader.releaseLock();
    }
  }
}

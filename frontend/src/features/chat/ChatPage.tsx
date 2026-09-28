"use client";

import { useEffect, useRef, useState } from "react";
import { queryStream } from "../../services/query";
import type { ChatMessage } from "../../types/query";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEl = useRef<HTMLDivElement>(null);
  const nextId = useRef(0);
  const busy = useRef(false);

  useEffect(() => {
    const el = messagesEl.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  async function sendQuestion() {
    if (!question.trim() || busy.current) return;

    const query = question;
    const userId = ++nextId.current;
    const stepId = ++nextId.current;
    busy.current = true;
    setQuestion("");
    setLoading(true);
    setMessages((current) => [
      ...current,
      { id: userId, role: "user", type: "text", content: query },
      { id: stepId, role: "assistant", type: "steps", steps: [] },
    ]);

    try {
      for await (const event of queryStream(query)) {
        if (event.type === "progress") {
          setMessages((current) => current.map((message) => {
            if (message.id !== stepId || message.type !== "steps") return message;
            const exists = message.steps.some((step) => step.text === event.step);
            return {
              ...message,
              steps: exists
                ? message.steps.map((step) => step.text === event.step ? { ...step, status: event.status } : step)
                : [...message.steps, { text: event.step, status: event.status }],
            };
          }));
        } else if (event.type === "result" && Array.isArray(event.data)) {
          const id = ++nextId.current;
          setMessages((current) => [...current, {
            id,
            role: "assistant",
            type: "table",
            columns: Object.keys(event.data[0] ?? {}),
            rows: event.data,
          }]);
        } else if (event.type === "error") {
          const id = ++nextId.current;
          setMessages((current) => [...current, {
            id,
            role: "assistant",
            type: "error",
            content: event.message || "发生错误",
          }]);
        }
      }
    } catch (error) {
      const id = ++nextId.current;
      setMessages((current) => [...current, {
        id,
        role: "assistant",
        type: "error",
        content: error instanceof Error ? error.message : "请求失败",
      }]);
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }

  return (
    <div className="chat-page">
      <div ref={messagesEl} className="messages">
        {messages.map((message) => (
          <div key={message.id} className={`message-row ${message.role}`}>
            {message.role === "assistant" && <div className="avatar">🤖</div>}
            <div className="bubble">
              {message.type === "text" && <div>{message.content}</div>}
              {message.type === "steps" && <div className="steps">
                {message.steps.map((step) => <div key={step.text} className="step">
                  <span className={`dot ${step.status}`} /><span>{step.text}</span>
                </div>)}
              </div>}
              {message.type === "table" && <div className="table-wrap">
                <table className="result-table">
                  <thead><tr>{message.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>{message.rows.map((row, index) => <tr key={index}>
                    {message.columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
                  </tr>)}</tbody>
                </table>
              </div>}
              {message.type === "error" && <div className="error-text">{message.content}</div>}
            </div>
            {message.role === "user" && <div className="avatar">🧑</div>}
          </div>
        ))}
        <div className="messages-bottom-spacer" />
      </div>
      <div className="input-wrapper">
        <div className="input-box">
          <input value={question} onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Enter" && !event.nativeEvent.isComposing && event.keyCode !== 229) void sendQuestion(); }}
            placeholder="请输入你的问题..." aria-label="请输入你的问题" />
          <button onClick={() => void sendQuestion()} disabled={loading}>{loading ? "执行中..." : "发送"}</button>
        </div>
      </div>
    </div>
  );
}

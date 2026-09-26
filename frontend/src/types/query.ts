export type StepStatus = "running" | "success" | "error";

export type QueryEvent =
  | { type: "progress"; step: string; status: StepStatus }
  | { type: "result"; data: Record<string, unknown>[] }
  | { type: "error"; message?: string };

export type ChatMessage =
  | { id: number; role: "user"; type: "text"; content: string }
  | { id: number; role: "assistant"; type: "steps"; steps: { text: string; status: StepStatus }[] }
  | { id: number; role: "assistant"; type: "table"; columns: string[]; rows: Record<string, unknown>[] }
  | { id: number; role: "assistant"; type: "error"; content: string };

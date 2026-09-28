import { beforeEach, vi } from "vitest";

// 未配置 fetch 模拟时立即失败，避免测试请求真实后端。
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("Unexpected network request"))));
});

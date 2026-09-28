import { beforeEach, vi } from "vitest";

// A forgotten fetch mock must fail rather than contact a real backend.
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("Unexpected network request"))));
});

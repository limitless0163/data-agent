import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["./tests/setup.ts"],
    restoreMocks: true,
    clearMocks: true,
    unstubGlobals: true,
    unstubEnvs: true,
    coverage: {
      provider: "v8",
      include: ["src/services/**/*.ts", "src/features/**/*.tsx", "src/app/api/**/*.ts"],
      reporter: ["text", "html", "lcov"],
      thresholds: { lines: 85, statements: 85, functions: 85, branches: 80 },
    },
  },
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("includes field names in FastAPI validation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              {
                loc: ["body", "weight"],
                msg: "Input should be greater than 0",
                type: "greater_than",
              },
            ],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(apiRequest("/api/sections/7/categories")).rejects.toThrow(
      "weight: Input should be greater than 0",
    );
  });

  it("joins multiple validation errors without losing their field paths", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [
              { loc: ["body", "name"], msg: "Name is required", type: "missing" },
              { loc: ["body", "weight"], msg: "Weight is invalid", type: "value_error" },
            ],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(apiRequest("/api/sections/7/categories")).rejects.toThrow(
      "name: Name is required; weight: Weight is invalid",
    );
  });
});

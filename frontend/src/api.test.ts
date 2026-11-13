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

  it("does not add a JSON content type to requests without a body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/health");

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(options.headers).has("Content-Type")).toBe(false);
  });

  it("keeps the JSON content type for requests with a JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "student@example.test" }),
    });

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(options.headers).get("Content-Type")).toBe("application/json");
  });
});

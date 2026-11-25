import { describe, expect, it } from "vitest";
import { apiRequest } from "./api";
import { loadAdminData } from "./adminData";

function controlledRequest(
  respond: (path: string) => unknown | Promise<unknown>,
) {
  return (async <T>(path: string) =>
    (await respond(path)) as T) as typeof apiRequest;
}

describe("loadAdminData", () => {
  it("loads only accounts for the users scope", async () => {
    const paths: string[] = [];
    const request = controlledRequest(async (path) => {
      paths.push(path);
      return [];
    });

    const patch = await loadAdminData("users", request);

    expect(paths).toEqual(["/api/users?limit=200&offset=0"]);
    expect(patch.users).toEqual([]);
    expect(patch.sections).toBeUndefined();
  });

  it("loads sections and accounts once for the sections scope", async () => {
    const paths: string[] = [];
    const request = controlledRequest(async (path) => {
      paths.push(path);
      return [];
    });

    const patch = await loadAdminData("sections", request);

    expect(paths).toHaveLength(2);
    expect(paths).toContain("/api/sections");
    expect(patch.sections).toEqual([]);
    expect(patch.users).toEqual([]);
  });

  it("loads calendar data for the calendar scope", async () => {
    const paths: string[] = [];
    const request = controlledRequest(async (path) => {
      paths.push(path);
      if (path === "/api/academic-years") {
        return [{ id: 4, name: "2026", start_date: "", end_date: "" }];
      }
      return [];
    });

    const patch = await loadAdminData("calendar", request);

    expect(paths).toEqual([
      "/api/academic-years",
      "/api/academic-years/4/terms",
    ]);
    expect(patch.years).toHaveLength(1);
    expect(patch.courses).toBeUndefined();
  });
});

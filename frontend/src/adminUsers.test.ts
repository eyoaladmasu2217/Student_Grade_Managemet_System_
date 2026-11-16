import { describe, expect, it } from "vitest";
import { User } from "./api";
import { loadAllUsers } from "./adminUsers";

function user(id: number): User {
  return {
    id,
    email: `user${id}@example.test`,
    full_name: `User ${id}`,
    role: "student",
  };
}

describe("loadAllUsers", () => {
  it("loads every page instead of truncating account lists at 200", async () => {
    const firstPage = Array.from({ length: 200 }, (_, index) => user(index + 1));
    const secondPage = [user(201)];
    const calls: string[] = [];
    const request = async (path: string) => {
      calls.push(path);
      return path.endsWith("offset=0") ? firstPage : secondPage;
    };

    expect(await loadAllUsers(request)).toEqual([...firstPage, ...secondPage]);
    expect(calls).toEqual([
      "/api/users?limit=200&offset=0",
      "/api/users?limit=200&offset=200",
    ]);
  });
});

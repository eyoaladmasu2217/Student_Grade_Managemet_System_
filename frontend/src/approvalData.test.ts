import { describe, expect, it } from "vitest";
import { apiRequest, Section } from "./api";
import { loadApprovalData, reviewGradeChange } from "./approvalData";

function controlledRequest(
  respond: (path: string, init?: RequestInit) => unknown | Promise<unknown>,
) {
  return (async <T>(path: string, init?: RequestInit) =>
    (await respond(path, init)) as T) as typeof apiRequest;
}

const sections: Section[] = [
  {
    id: 7,
    course_id: 3,
    course_code: "CS101",
    course_title: "Programming",
    term_id: 2,
    term_name: "Term I",
    academic_year_name: "2026",
    academic_year_id: 1,
    instructor_id: 4,
    instructor_name: "Instructor One",
    section_code: "A",
  },
  {
    id: 8,
    course_id: 4,
    course_code: "MATH101",
    course_title: "Calculus",
    term_id: 2,
    term_name: "Term I",
    academic_year_name: "2026",
    academic_year_id: 1,
    instructor_id: 5,
    instructor_name: "Instructor Two",
    section_code: "B",
  },
];

describe("approvalData", () => {
  it("loads pending requests and combines audit trails newest first", async () => {
    const paths: string[] = [];
    const request = controlledRequest(async (path) => {
      paths.push(path);
      if (path === "/api/grade-change-requests?status=pending") return [{ id: 12 }];
      if (path === "/api/sections/7/audit-trail") {
        return [
          { id: 3, occurred_at: "2026-01-03T10:00:00Z" },
          { id: 1, occurred_at: "2026-01-01T10:00:00Z" },
        ];
      }
      return [{ id: 2, occurred_at: "2026-01-02T10:00:00Z" }];
    });

    const result = await loadApprovalData(sections, request);

    expect(paths).toEqual([
      "/api/grade-change-requests?status=pending",
      "/api/sections/7/audit-trail",
      "/api/sections/8/audit-trail",
    ]);
    expect(result.requests).toEqual([{ id: 12 }]);
    expect(result.auditTrail.map((event) => event.id)).toEqual([3, 2, 1]);
  });

  it("posts review decisions with the review note", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const request = controlledRequest(async (path, init) => {
      calls.push({ path, init });
      return { id: 12, status: "approved" };
    });

    const result = await reviewGradeChange(12, "approve", "Verified score", request);

    expect(result.status).toBe("approved");
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe("/api/grade-change-requests/12/approve");
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      note: "Verified score",
    });
  });
});

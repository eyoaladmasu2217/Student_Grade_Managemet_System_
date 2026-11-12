import { describe, expect, it } from "vitest";
import { apiRequest, Gradebook } from "./api";
import { createInstructorGradebookWorkflow } from "./instructorGradebookWorkflow";

function controlledRequest(
  respond: (path: string, init: RequestInit) => unknown | Promise<unknown>,
) {
  return (async <T>(path: string, init: RequestInit = {}) =>
    await respond(path, init) as T) as typeof apiRequest;
}

function gradebook(gradesReleased = false): Gradebook {
  return {
    section_id: 7,
    grades_released: gradesReleased,
    released_at: gradesReleased ? "2026-01-01T00:00:00Z" : null,
    assessments: [],
    students: [],
  };
}

describe("instructor gradebook workflow", () => {
  it("loads the selected section and exposes its loading lifecycle", async () => {
    const request = controlledRequest(async (path) => {
      if (path.endsWith("/gradebook")) return gradebook();
      return [];
    });
    const workflow = createInstructorGradebookWorkflow(request);

    const loading = workflow.selectSection("7");
    expect(workflow.getSnapshot().loading).toBe(true);
    await loading;

    expect(workflow.getSnapshot()).toMatchObject({
      sectionId: "7",
      gradebook: gradebook(),
      categories: [],
      roster: [],
      corrections: [],
      loading: false,
      error: "",
    });
  });

  it("refreshes selected-section data after a successful write", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    let categoryLoads = 0;
    const request = controlledRequest(async (path, init) => {
      calls.push({ path, init });
      if (path.endsWith("/gradebook")) return gradebook();
      if (path.endsWith("/categories") && init.method !== "POST") {
        categoryLoads += 1;
        return categoryLoads === 1
          ? []
          : [{ id: 3, section_id: 7, name: "Exams", weight: 40 }];
      }
      return {};
    });
    const workflow = createInstructorGradebookWorkflow(request);
    await workflow.selectSection("7");

    expect(await workflow.createCategory("Exams", 40)).toBe(true);

    const write = calls.find(
      (call) =>
        call.path === "/api/sections/7/categories" &&
        call.init.method === "POST",
    );
    expect(write?.init.method).toBe("POST");
    expect(JSON.parse(String(write?.init.body))).toEqual({ name: "Exams", weight: 40 });
    expect(calls.filter((call) => call.path.endsWith("/gradebook"))).toHaveLength(2);
    expect(workflow.getSnapshot().categories).toEqual([
      { id: 3, section_id: 7, name: "Exams", weight: 40 },
    ]);
    expect(workflow.getSnapshot()).toMatchObject({
      message: "Assessment category created.",
      working: false,
      loading: false,
    });
  });

  it("reports write failures without refreshing the section", async () => {
    const calls: string[] = [];
    const request = controlledRequest(async (path) => {
      calls.push(path);
      if (path === "/api/sections/7/categories") throw new Error("Category could not be saved.");
      if (path.endsWith("/gradebook")) return gradebook();
      return [];
    });
    const workflow = createInstructorGradebookWorkflow(request);
    await workflow.selectSection("7");

    expect(await workflow.createCategory("Exams", 40)).toBe(false);
    expect(calls.filter((path) => path.endsWith("/gradebook"))).toHaveLength(1);
    expect(workflow.getSnapshot()).toMatchObject({
      error: "Category could not be saved.",
      working: false,
      message: "",
    });
  });

  it("records released-score corrections through the correction endpoint", async () => {
    const calls: Array<{ path: string; init: RequestInit }> = [];
    const request = controlledRequest(async (path, init) => {
      calls.push({ path, init });
      if (path.endsWith("/gradebook")) return gradebook(true);
      return [];
    });
    const workflow = createInstructorGradebookWorkflow(request);
    await workflow.selectSection("7");

    expect(
      await workflow.saveScore(12, 31, 82.5, "Correcting a grading error"),
    ).toBe(true);

    const correction = calls.find((call) =>
      call.path === "/api/assessments/12/scores/31/correction",
    );
    expect(correction?.init.method).toBe("PUT");
    expect(JSON.parse(String(correction?.init.body))).toEqual({
      points: 82.5,
      reason: "Correcting a grading error",
    });
    expect(calls.filter((call) => call.path.endsWith("/corrections"))).toHaveLength(2);
    expect(workflow.getSnapshot().fieldErrors["score:12:31"]).toBe("");
  });
});

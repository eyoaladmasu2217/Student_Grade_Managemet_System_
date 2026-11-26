import { describe, expect, it, vi } from "vitest";
import { GradeBand, SimulationAssessment, SimulationCategory, apiRequest } from "./api";
import {
  letterForPercentage,
  projectGrade,
  scoreNeededForTarget,
} from "./gradeSimulator";
import { loadSimulationSections, loadWhatIfSimulation } from "./whatIfData";

const categories: SimulationCategory[] = [
  { id: 1, name: "Exams", weight: 60 },
  { id: 2, name: "Project", weight: 40 },
];

const assessments: SimulationAssessment[] = [
  { id: 10, category_id: 1, title: "Midterm", max_points: 50, due_date: null, points: 40 },
  { id: 11, category_id: 1, title: "Final", max_points: 50, due_date: null, points: null },
  { id: 12, category_id: 2, title: "Project", max_points: 100, due_date: null, points: null },
];

const bands: GradeBand[] = [
  { code: "A", minimum_percentage: 90 },
  { code: "B", minimum_percentage: 80 },
  { code: "F", minimum_percentage: 0 },
];

describe("projectGrade", () => {
  it("averages only graded categories before the scenario is complete", () => {
    const result = projectGrade(categories, assessments);

    expect(result.weighted_points).toBe(48);
    expect(result.graded_weight).toBe(60);
    expect(result.current_percentage).toBe(80);
    expect(result.projected_percentage).toBeNull();
    expect(result.complete).toBe(false);
  });

  it("projects a final percentage when every assessment has a score", () => {
    const result = projectGrade(categories, assessments, { 11: 45, 12: 88 });

    expect(result.weighted_points).toBe(86.2);
    expect(result.projected_percentage).toBe(86.2);
    expect(result.complete).toBe(true);
  });

  it("clamps hypothetical scores to the assessment maximum", () => {
    const result = projectGrade(categories, assessments, { 10: 200 });

    expect(result.weighted_points).toBe(60);
  });

  it("treats an explicitly empty score as ungraded", () => {
    const result = projectGrade(categories, assessments, { 10: null });

    expect(result.current_percentage).toBeNull();
    expect(result.projected_percentage).toBeNull();
  });
});

describe("scoreNeededForTarget", () => {
  it("calculates the minimum points required on one assessment", () => {
    const result = scoreNeededForTarget(categories, assessments, 12, 90, { 11: 45 });

    expect(result.reason).toBe("ok");
    expect(result.required_points).toBe(97.5);
    expect(result.required_percentage).toBe(97.5);
    expect(result.attainable).toBe(true);
  });

  it("reports the best attainable grade when the target is out of reach", () => {
    const result = scoreNeededForTarget(categories, assessments, 12, 95, { 11: 45 });

    expect(result.reason).toBe("unreachable");
    expect(result.required_points).toBeNull();
    expect(result.maximum_percentage).toBe(91);
  });

  it("rejects invalid targets and incomplete category weights", () => {
    expect(scoreNeededForTarget(categories, assessments, 12, 101).reason).toBe(
      "invalid-target",
    );
    expect(
      scoreNeededForTarget([{ id: 1, name: "Exams", weight: 50 }], assessments, 10, 90)
        .reason,
    ).toBe("weights-incomplete");
  });
});

describe("letterForPercentage", () => {
  it("finds the highest band covering the percentage", () => {
    expect(letterForPercentage(bands, 90)).toBe("A");
    expect(letterForPercentage(bands, 86.2)).toBe("B");
    expect(letterForPercentage(bands, 40)).toBe("F");
    expect(letterForPercentage(bands, null)).toBe("—");
  });
});

describe("what-if loaders", () => {
  it("loads enrolled sections and a section simulation", async () => {
    const paths: string[] = [];
    const request = vi.fn(async (path: string) => {
      paths.push(path);
      return path.includes("mine") ? [] : { section_id: 7 };
    }) as unknown as typeof apiRequest;

    await loadSimulationSections(request);
    await loadWhatIfSimulation(7, request);

    expect(paths).toEqual(["/api/enrollments/mine", "/api/sections/7/what-if"]);
  });
});

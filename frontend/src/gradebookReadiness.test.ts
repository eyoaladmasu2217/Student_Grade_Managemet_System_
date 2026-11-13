import { describe, expect, it } from "vitest";
import { Gradebook } from "./api";
import { getGradeReleaseReadiness } from "./gradebookReadiness";

function gradebook(
  students: Gradebook["students"],
  gradesReleased = false,
): Gradebook {
  return {
    section_id: 7,
    grades_released: gradesReleased,
    released_at: gradesReleased ? "2026-01-01T00:00:00Z" : null,
    assessments: [],
    students,
  };
}

function student(isComplete: boolean): Gradebook["students"][number] {
  return {
    student_id: isComplete ? 1 : 2,
    student_name: "Student",
    student_email: "student@example.test",
    scores: {},
    weighted_points: 0,
    graded_weight: 0,
    current_percentage: null,
    final_percentage: null,
    letter_grade: null,
    is_complete: isComplete,
  };
}

describe("grade release readiness", () => {
  it("requires at least one enrolled student", () => {
    expect(getGradeReleaseReadiness(gradebook([]))).toMatchObject({
      canRelease: false,
      completeStudents: 0,
      totalStudents: 0,
      message: "Enroll active students before releasing grades.",
    });
  });

  it("reports incomplete student gradebooks before release", () => {
    expect(
      getGradeReleaseReadiness(gradebook([student(true), student(false)])),
    ).toMatchObject({
      canRelease: false,
      completeStudents: 1,
      totalStudents: 2,
      message:
        "1 of 2 student gradebooks are complete. Finish missing scores and ensure category weights total 100%.",
    });
  });

  it("allows release only when every student's gradebook is complete", () => {
    expect(
      getGradeReleaseReadiness(gradebook([student(true), student(true)])),
    ).toMatchObject({
      canRelease: true,
      completeStudents: 2,
      totalStudents: 2,
      message: "All 2 student gradebooks are complete and ready for release.",
    });
  });

  it("does not mark an already released gradebook as releasable", () => {
    expect(
      getGradeReleaseReadiness(gradebook([student(true)], true)).canRelease,
    ).toBe(false);
  });
});

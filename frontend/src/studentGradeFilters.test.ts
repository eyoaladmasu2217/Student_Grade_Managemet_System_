import { describe, expect, it } from "vitest";
import { ReleasedGrade } from "./api";
import { filterReleasedGrades } from "./studentGradeFilters";

const grades: ReleasedGrade[] = [
  {
    section_id: 1,
    term_id: 10,
    course_code: "CS101",
    course_title: "Introduction to Computing",
    section_code: "A",
    term_name: "Fall 2026",
    percentage: 92,
    letter_grade: "A",
    released_at: "2026-10-01T00:00:00Z",
  },
  {
    section_id: 2,
    term_id: 11,
    course_code: "MATH201",
    course_title: "Calculus II",
    section_code: "B",
    term_name: "Spring 2026",
    percentage: 84,
    letter_grade: "B",
    released_at: "2026-10-02T00:00:00Z",
  },
  {
    section_id: 3,
    term_id: 10,
    course_code: "ENG102",
    course_title: "Academic Writing",
    section_code: "C",
    term_name: "Fall 2026",
    percentage: 77,
    letter_grade: "C",
    released_at: "2026-10-03T00:00:00Z",
  },
];

describe("filterReleasedGrades", () => {
  it("returns all grades when no search or term is selected", () => {
    expect(filterReleasedGrades(grades, "", null)).toEqual(grades);
  });

  it("keeps the original grade objects when no filter is applied", () => {
    const result = filterReleasedGrades(grades, "", null);
    expect(result).toHaveLength(grades.length);
    result.forEach((grade, index) => expect(grade).toBe(grades[index]));
  });

  it("searches course details and term names without case sensitivity", () => {
    expect(filterReleasedGrades(grades, "cAlCuLuS", null)).toEqual([grades[1]]);
    expect(filterReleasedGrades(grades, "fall 2026", null)).toEqual([
      grades[0],
      grades[2],
    ]);
  });

  it("matches the selected term and combines it with the search", () => {
    expect(filterReleasedGrades(grades, "", 10)).toEqual([grades[0], grades[2]]);
    expect(filterReleasedGrades(grades, "writing", 10)).toEqual([grades[2]]);
    expect(filterReleasedGrades(grades, "writing", 11)).toEqual([]);
  });

  it("ignores surrounding whitespace in the search", () => {
    expect(filterReleasedGrades(grades, "  cs101  ", null)).toEqual([grades[0]]);
  });
});

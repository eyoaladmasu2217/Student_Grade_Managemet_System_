import { ReleasedGrade } from "./api";

export function filterReleasedGrades(
  grades: ReleasedGrade[],
  search: string,
  termId: number | null,
): ReleasedGrade[] {
  const query = search.trim().toLocaleLowerCase();

  return grades.filter((grade) => {
    const matchesTerm = termId === null || grade.term_id === termId;
    const searchableText = [
      grade.course_code,
      grade.course_title,
      grade.section_code,
      grade.term_name,
    ]
      .join(" ")
      .toLocaleLowerCase();

    return matchesTerm && (!query || searchableText.includes(query));
  });
}

import { ReleasedGrade } from "./api";

export function filterReleasedGrades(
  grades: ReleasedGrade[],
  search: string,
  termId: number | null,
): ReleasedGrade[] {
  const query = search.trim().toLocaleLowerCase();

  return grades.filter((grade) => {
    if (termId !== null && grade.term_id !== termId) {
      return false;
    }
    if (!query) {
      return true;
    }
    const searchableText = [
      grade.course_code,
      grade.course_title,
      grade.section_code,
      grade.term_name,
    ]
      .join(" ")
      .toLocaleLowerCase();

    return searchableText.includes(query);
  });
}

import { Gradebook } from "./api";

export interface GradeReleaseReadiness {
  canRelease: boolean;
  completeStudents: number;
  totalStudents: number;
  message: string;
}

export function getGradeReleaseReadiness(
  gradebook: Gradebook | null,
): GradeReleaseReadiness {
  if (!gradebook) {
    return {
      canRelease: false,
      completeStudents: 0,
      totalStudents: 0,
      message: "Loading gradebook readiness.",
    };
  }

  const totalStudents = gradebook.students.length;
  const completeStudents = gradebook.students.filter(
    (student) => student.is_complete,
  ).length;

  if (gradebook.grades_released) {
    return {
      canRelease: false,
      completeStudents,
      totalStudents,
      message: "Grades have already been released.",
    };
  }

  if (totalStudents === 0) {
    return {
      canRelease: false,
      completeStudents: 0,
      totalStudents,
      message: "Enroll active students before releasing grades.",
    };
  }

  if (completeStudents < totalStudents) {
    return {
      canRelease: false,
      completeStudents,
      totalStudents,
      message: `${completeStudents} of ${totalStudents} student gradebooks are complete. Finish missing scores and ensure category weights total 100%.`,
    };
  }

  return {
    canRelease: true,
    completeStudents,
    totalStudents,
    message: `All ${totalStudents} student gradebooks are complete and ready for release.`,
  };
}

export type UserRole = "admin" | "instructor" | "student";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface AcademicYear {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
}

export interface Term {
  id: number;
  academic_year_id: number;
  name: string;
  start_date: string;
  end_date: string;
}

export interface Course {
  id: number;
  code: string;
  title: string;
  description: string;
}

export interface Section {
  id: number;
  course_id: number;
  course_code: string;
  course_title: string;
  term_id: number;
  term_name: string;
  academic_year_id: number;
  instructor_id: number;
  instructor_name: string;
  section_code: string;
}

export interface GradeBand {
  code: string;
  minimum_percentage: number;
}

export interface Enrollment {
  id: number;
  section_id: number;
  student_id: number;
  student_name: string;
  student_email: string;
  status: "active" | "withdrawn";
}

export interface Category {
  id: number;
  section_id: number;
  name: string;
  weight: number;
}

export interface Assessment {
  id: number;
  category_id: number;
  category_name: string;
  category_weight: number;
  title: string;
  max_points: number;
  due_date: string | null;
}

export interface GradebookStudent {
  student_id: number;
  student_name: string;
  student_email: string;
  scores: Record<string, number>;
  weighted_points: number;
  graded_weight: number;
  current_percentage: number | null;
  final_percentage: number | null;
  letter_grade: string | null;
  is_complete: boolean;
}

export interface Gradebook {
  section_id: number;
  grades_released: boolean;
  released_at: string | null;
  assessments: Assessment[];
  students: GradebookStudent[];
}

export interface ReleasedGrade {
  section_id: number;
  course_code: string;
  course_title: string;
  section_code: string;
  term_name: string;
  percentage: number;
  letter_grade: string;
  released_at: string;
}

export interface GradeCorrection {
  id: number;
  section_id: number;
  student_id: number;
  student_name: string;
  assessment_id: number;
  assessment_title: string;
  previous_points: number;
  new_points: number;
  previous_percentage: number;
  new_percentage: number;
  previous_letter_grade: string;
  new_letter_grade: string;
  changed_by: number;
  changed_by_name: string;
  reason: string;
  changed_at: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function messageFromPayload(payload: unknown): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return "The request could not be completed.";
  }

  const detail = payload.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (
    typeof detail === "object" &&
    detail !== null &&
    "message" in detail &&
    typeof detail.message === "string"
  ) {
    return detail.message;
  }
  return "The request could not be completed. Check the submitted information.";
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(messageFromPayload(payload), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

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

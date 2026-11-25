import {
  AcademicYear,
  apiRequest,
  Course,
  GradeBand,
  Section,
  Term,
  User,
} from "./api";
import { loadAllUsers } from "./adminUsers";

export interface AdminData {
  years: AcademicYear[];
  terms: Term[];
  courses: Course[];
  users: User[];
  sections: Section[];
  gradeBands: GradeBand[];
}

export const emptyAdminData: AdminData = {
  years: [],
  terms: [],
  courses: [],
  users: [],
  sections: [],
  gradeBands: [],
};

export type AdminRefreshScope =
  | "all"
  | "calendar"
  | "users"
  | "catalog"
  | "sections"
  | "scale";

type Request = typeof apiRequest;

export async function loadAdminData(
  scope: AdminRefreshScope = "all",
  request: Request = apiRequest,
): Promise<Partial<AdminData>> {
  const loadUsers = () => loadAllUsers((path) => request<User[]>(path));

  if (scope === "users") {
    return { users: await loadUsers() };
  }
  if (scope === "catalog") {
    return { courses: await request<Course[]>("/api/courses") };
  }
  if (scope === "scale") {
    return { gradeBands: await request<GradeBand[]>("/api/grade-scale") };
  }
  if (scope === "sections") {
    const [sections, users] = await Promise.all([
      request<Section[]>("/api/sections"),
      loadUsers(),
    ]);
    return { sections, users };
  }
  if (scope === "calendar") {
    const years = await request<AcademicYear[]>("/api/academic-years");
    const termLists = await Promise.all(
      years.map((year) => request<Term[]>(`/api/academic-years/${year.id}/terms`)),
    );
    return { years, terms: termLists.flat() };
  }

  const [years, courses, users, sections, gradeBands] = await Promise.all([
    request<AcademicYear[]>("/api/academic-years"),
    request<Course[]>("/api/courses"),
    loadUsers(),
    request<Section[]>("/api/sections"),
    request<GradeBand[]>("/api/grade-scale"),
  ]);
  const termLists = await Promise.all(
    years.map((year) => request<Term[]>(`/api/academic-years/${year.id}/terms`)),
  );
  return {
    years,
    terms: termLists.flat(),
    courses,
    users,
    sections,
    gradeBands,
  };
}

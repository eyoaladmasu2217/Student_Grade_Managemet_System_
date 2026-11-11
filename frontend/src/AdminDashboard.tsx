import { FormEvent, useEffect, useState } from "react";
import {
  AcademicYear,
  apiRequest,
  Course,
  GradeBand,
  jsonBody,
  Section,
  Term,
  User,
} from "./api";

interface AdminData {
  years: AcademicYear[];
  terms: Term[];
  courses: Course[];
  users: User[];
  sections: Section[];
  gradeBands: GradeBand[];
}

const emptyData: AdminData = {
  years: [],
  terms: [],
  courses: [],
  users: [],
  sections: [],
  gradeBands: [],
};

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

export default function AdminDashboard() {
  const [data, setData] = useState(emptyData);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [years, courses, users, sections, gradeBands] = await Promise.all([
          apiRequest<AcademicYear[]>("/api/academic-years"),
          apiRequest<Course[]>("/api/courses"),
          apiRequest<User[]>("/api/users?limit=200"),
          apiRequest<Section[]>("/api/sections"),
          apiRequest<GradeBand[]>("/api/grade-scale"),
        ]);
        const termLists = await Promise.all(
          years.map((year) =>
            apiRequest<Term[]>(`/api/academic-years/${year.id}/terms`),
          ),
        );
        if (active) {
          setData({
            years,
            terms: termLists.flat(),
            courses,
            users,
            sections,
            gradeBands,
          });
          setError("");
        }
      } catch (loadError) {
        if (active) {
          setError(messageOf(loadError));
        }
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [refreshKey]);

  async function save(
    event: FormEvent<HTMLFormElement>,
    action: () => Promise<unknown>,
    successMessage: string,
  ) {
    event.preventDefault();
    setError("");
    setMessage("");
    setWorking(true);
    try {
      await action();
      setMessage(successMessage);
      setRefreshKey((key) => key + 1);
    } catch (saveError) {
      setError(messageOf(saveError));
    } finally {
      setWorking(false);
    }
  }

  async function createYear(event: FormEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") ?? ""),
      start_date: String(form.get("start_date") ?? ""),
      end_date: String(form.get("end_date") ?? ""),
    };
    await save(
      event,
      () => apiRequest("/api/academic-years", { method: "POST", body: jsonBody(payload) }),
      "Academic year created.",
    );
  }

  async function createTerm(event: FormEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    const yearId = Number(form.get("academic_year_id"));
    const payload = {
      name: String(form.get("name") ?? ""),
      start_date: String(form.get("start_date") ?? ""),
      end_date: String(form.get("end_date") ?? ""),
    };
    await save(
      event,
      () =>
        apiRequest(`/api/academic-years/${yearId}/terms`, {
          method: "POST",
          body: jsonBody(payload),
        }),
      "Academic term created.",
    );
  }

  async function createUser(event: FormEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    const payload = {
      full_name: String(form.get("full_name") ?? ""),
      email: String(form.get("email") ?? ""),
      password: String(form.get("password") ?? ""),
      role: String(form.get("role") ?? "student"),
    };
    await save(
      event,
      () => apiRequest("/api/users", { method: "POST", body: jsonBody(payload) }),
      "Account created.",
    );
  }

  async function createCourse(event: FormEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    const payload = {
      code: String(form.get("code") ?? ""),
      title: String(form.get("title") ?? ""),
      description: String(form.get("description") ?? ""),
    };
    await save(
      event,
      () => apiRequest("/api/courses", { method: "POST", body: jsonBody(payload) }),
      "Course created.",
    );
  }

  async function createSection(event: FormEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    const courseId = Number(form.get("course_id"));
    const payload = {
      term_id: Number(form.get("term_id")),
      instructor_id: Number(form.get("instructor_id")),
      section_code: String(form.get("section_code") ?? ""),
    };
    await save(
      event,
      () =>
        apiRequest(`/api/courses/${courseId}/sections`, {
          method: "POST",
          body: jsonBody(payload),
        }),
      "Course section created.",
    );
  }

  async function enrollStudent(event: FormEvent<HTMLFormElement>) {
    const form = new FormData(event.currentTarget);
    const sectionId = Number(form.get("section_id"));
    const payload = { student_id: Number(form.get("student_id")) };
    await save(
      event,
      () =>
        apiRequest(`/api/sections/${sectionId}/enrollments`, {
          method: "POST",
          body: jsonBody(payload),
        }),
      "Student enrolled.",
    );
  }

  async function saveGradeScale(event: FormEvent<HTMLFormElement>) {
    await save(
      event,
      () =>
        apiRequest("/api/grade-scale", {
          method: "PUT",
          body: jsonBody({ bands: data.gradeBands }),
        }),
      "Grade scale saved.",
    );
  }

  function updateBand(index: number, patch: Partial<GradeBand>) {
    setData((current) => ({
      ...current,
      gradeBands: current.gradeBands.map((band, bandIndex) =>
        bandIndex === index ? { ...band, ...patch } : band,
      ),
    }));
  }

  const students = data.users.filter((user) => user.role === "student");
  const instructors = data.users.filter((user) => user.role === "instructor");
  const yearById = new Map(data.years.map((year) => [year.id, year.name]));

  return (
    <section className="dashboard-layout" aria-labelledby="admin-title">
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">ADMINISTRATION</p>
          <h1 id="admin-title">Academic setup</h1>
          <p className="welcome-copy">
            Manage the calendar, accounts, course sections, enrollment, and grade scale.
          </p>
        </div>
        <span className="term-pill">{data.sections.length} sections</span>
      </div>

      {error && <p className="form-error dashboard-message" role="alert">{error}</p>}
      {message && <p className="success-message dashboard-message" role="status">{message}</p>}

      <div className="dashboard-grid">
        <article className="panel">
          <h2>Academic years</h2>
          <form className="form-grid" onSubmit={createYear}>
            <label>
              Name
              <input name="name" placeholder="2026–2027" required maxLength={80} />
            </label>
            <label>
              Starts
              <input name="start_date" type="date" required />
            </label>
            <label>
              Ends
              <input name="end_date" type="date" required />
            </label>
            <button className="primary-button" disabled={working}>Add academic year</button>
          </form>
          <ul className="record-list">
            {data.years.map((year) => (
              <li key={year.id}>
                <strong>{year.name}</strong>
                <span>{year.start_date} — {year.end_date}</span>
              </li>
            ))}
            {data.years.length === 0 && <li className="empty-state">No academic years yet.</li>}
          </ul>
        </article>

        <article className="panel">
          <h2>Academic terms</h2>
          <form className="form-grid" onSubmit={createTerm}>
            <label>
              Academic year
              <select name="academic_year_id" required disabled={data.years.length === 0}>
                <option value="">Select a year</option>
                {data.years.map((year) => (
                  <option key={year.id} value={year.id}>{year.name}</option>
                ))}
              </select>
            </label>
            <label>
              Term name
              <input name="name" placeholder="Fall" required maxLength={80} />
            </label>
            <label>
              Starts
              <input name="start_date" type="date" required />
            </label>
            <label>
              Ends
              <input name="end_date" type="date" required />
            </label>
            <button className="primary-button" disabled={working || data.years.length === 0}>
              Add term
            </button>
          </form>
          <ul className="record-list">
            {data.terms.map((term) => (
              <li key={term.id}>
                <strong>{term.name} · {yearById.get(term.academic_year_id)}</strong>
                <span>{term.start_date} — {term.end_date}</span>
              </li>
            ))}
            {data.terms.length === 0 && <li className="empty-state">No terms yet.</li>}
          </ul>
        </article>

        <article className="panel">
          <h2>Accounts</h2>
          <form className="form-grid" onSubmit={createUser}>
            <label>
              Full name
              <input name="full_name" required maxLength={160} />
            </label>
            <label>
              College email
              <input name="email" type="email" required />
            </label>
            <label>
              Temporary password
              <input name="password" type="password" required minLength={12} maxLength={128} />
            </label>
            <label>
              Role
              <select name="role" defaultValue="student">
                <option value="student">Student</option>
                <option value="instructor">Instructor</option>
                <option value="admin">Academic administrator</option>
              </select>
            </label>
            <button className="primary-button" disabled={working}>Create account</button>
          </form>
          <p className="panel-note">
          Accounts are not self-registered. Deliver account credentials to each user securely.
          </p>
          <ul className="record-list">
            {data.users.slice(0, 5).map((user) => (
              <li key={user.id}>
                <strong>{user.full_name}</strong>
                <span>{user.role} · {user.email}</span>
              </li>
            ))}
            {data.users.length === 0 &&             <li className="empty-state">No accounts yet.</li>}
          </ul>
        </article>

        <article className="panel">
          <h2>Courses and sections</h2>
          <form className="form-grid" onSubmit={createCourse}>
            <label>
              Course code
              <input name="code" required maxLength={24} placeholder="CS101" />
            </label>
            <label>
              Course title
              <input name="title" required maxLength={160} />
            </label>
            <label className="full-width">
              Description
              <textarea name="description" rows={2} maxLength={2000} />
            </label>
            <button className="primary-button" disabled={working}>Add course</button>
          </form>
          <form className="form-grid nested-form" onSubmit={createSection}>
            <label>
              Course
              <select name="course_id" required disabled={data.courses.length === 0}>
                <option value="">Select a course</option>
                {data.courses.map((course) => (
                  <option key={course.id} value={course.id}>{course.code} · {course.title}</option>
                ))}
              </select>
            </label>
            <label>
              Term
              <select name="term_id" required disabled={data.terms.length === 0}>
                <option value="">Select a term</option>
                {data.terms.map((term) => (
                  <option key={term.id} value={term.id}>
                    {yearById.get(term.academic_year_id)} · {term.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Instructor
              <select name="instructor_id" required disabled={instructors.length === 0}>
                <option value="">Assign instructor</option>
                {instructors.map((instructor) => (
                  <option key={instructor.id} value={instructor.id}>{instructor.full_name}</option>
                ))}
              </select>
            </label>
            <label>
              Section code
              <input name="section_code" required maxLength={32} placeholder="A" />
            </label>
            <button
              className="primary-button"
              disabled={working || data.courses.length === 0 || data.terms.length === 0 || instructors.length === 0}
            >
              Add section
            </button>
          </form>
          <ul className="record-list">
            {data.sections.slice(0, 6).map((section) => (
              <li key={section.id}>
                <strong>{section.course_code} · Section {section.section_code}</strong>
                <span>{section.term_name} · {section.instructor_name}</span>
              </li>
            ))}
            {data.sections.length === 0 && <li className="empty-state">No sections yet.</li>}
          </ul>
        </article>

        <article className="panel">
          <h2>Student enrollment</h2>
          <form className="form-grid" onSubmit={enrollStudent}>
            <label>
              Section
              <select name="section_id" required disabled={data.sections.length === 0}>
                <option value="">Select a section</option>
                {data.sections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.course_code} · {section.section_code} · {section.term_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Student
              <select name="student_id" required disabled={students.length === 0}>
                <option value="">Select a student</option>
                {students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.full_name} · {student.email}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="primary-button"
              disabled={working || data.sections.length === 0 || students.length === 0}
            >
              Enroll student
            </button>
          </form>
        </article>

        <article className="panel">
          <h2>Letter-grade scale</h2>
          <p className="panel-note">Set the minimum percentage required for each grade.</p>
          <form className="form-grid" onSubmit={saveGradeScale}>
            <div className="grade-band-editor">
              {data.gradeBands.map((band, index) => (
                <div className="grade-band-row" key={index}>
                  <label>
                    Grade
                    <input
                      value={band.code}
                      maxLength={8}
                      onChange={(event) => updateBand(index, { code: event.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Minimum %
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={band.minimum_percentage}
                      onChange={(event) =>
                        updateBand(index, { minimum_percentage: Number(event.target.value) })
                      }
                      required
                    />
                  </label>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() =>
                      setData((current) => ({
                        ...current,
                        gradeBands: current.gradeBands.filter((_, bandIndex) => bandIndex !== index),
                      }))
                    }
                    aria-label={`Remove grade band ${band.code}`}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <div className="button-row">
              <button
                className="secondary-button"
                type="button"
                onClick={() =>
                  setData((current) => ({
                    ...current,
                    gradeBands: [...current.gradeBands, { code: "", minimum_percentage: 0 }],
                  }))
                }
              >
                Add grade band
              </button>
              <button className="primary-button" disabled={working}>Save grade scale</button>
            </div>
          </form>
        </article>
      </div>
    </section>
  );
}

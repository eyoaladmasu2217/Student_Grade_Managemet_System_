import { useEffect, useState } from "react";
import { apiRequest, ReleasedGrade } from "./api";
import { clampPercentage, gradeTone } from "./gradeDisplay";
import { filterReleasedGrades } from "./studentGradeFilters";

export default function StudentDashboard() {
  const [grades, setGrades] = useState<ReleasedGrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedTerm, setSelectedTerm] = useState("all");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest<ReleasedGrade[]>("/api/enrollments/mine/grades")
      .then((result) => {
        if (active) setGrades(result);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load released grades.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const average =
    grades.length > 0
      ? grades.reduce((sum, grade) => sum + grade.percentage, 0) / grades.length
      : 0;
  const best = grades.reduce<ReleasedGrade | null>(
    (top, grade) => (!top || grade.percentage > top.percentage ? grade : top),
    null,
  );
  const termCount = new Set(grades.map((grade) => grade.term_id)).size;
  const terms = Array.from(
    new Map(grades.map((grade) => [grade.term_id, grade.term_name])).entries(),
  );
  const visibleGrades = filterReleasedGrades(
    grades,
    search,
    selectedTerm === "all" ? null : Number(selectedTerm),
  );
  const stats = [
    { label: "Released grades", value: grades.length, hint: "Published results" },
    { label: "Average", value: `${average.toFixed(1)}%`, hint: "Across released courses" },
    {
      label: "Strongest result",
      value: best ? `${best.percentage}%` : "—",
      hint: best ? `${best.course_code} · ${best.letter_grade}` : "No results yet",
    },
    { label: "Terms", value: termCount, hint: "With released grades" },
  ];

  return (
    <section
      className="dashboard-layout"
      aria-labelledby="student-title"
      aria-busy={loading}
    >
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">STUDENT WORKSPACE</p>
          <h1 id="student-title">My course grades</h1>
          <p className="welcome-copy">
            Only grades released by your instructors appear here.
          </p>
        </div>
        <span className="term-pill">
          {grades.length} released {grades.length === 1 ? "grade" : "grades"}
        </span>
      </div>

      {!loading && !error && grades.length > 0 && (
        <div className="stat-grid">
          {stats.map((stat, index) => (
            <article
              className={`stat-card ${index === 0 ? "stat-card--accent" : ""}`}
              key={stat.label}
            >
              <span className="stat-label">{stat.label}</span>
              <strong className="stat-value">{stat.value}</strong>
              <span className="stat-hint">{stat.hint}</span>
            </article>
          ))}
        </div>
      )}

      {!loading && !error && grades.length > 0 && (
        <div className="student-grade-filters">
          <label>
            Search grades
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Course, section, or term"
            />
          </label>
          <label>
            Filter by term
            <select
              value={selectedTerm}
              onChange={(event) => setSelectedTerm(event.target.value)}
            >
              <option value="all">All terms</option>
              {terms.map(([termId, termName]) => (
                <option key={termId} value={termId}>
                  {termName}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {error ? (
        <div className="dashboard-message">
          <p className="form-error" role="alert">{error}</p>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
          >
            Try again
          </button>
        </div>
      ) : loading ? (
        <>
          <div className="student-grade-grid" aria-hidden="true">
            <span className="skeleton skeleton-grade-card" />
            <span className="skeleton skeleton-grade-card" />
            <span className="skeleton skeleton-grade-card" />
          </div>
          <p className="visually-hidden" role="status" aria-live="polite">
            Loading your grades...
          </p>
        </>
      ) : grades.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No released grades yet</h2>
          <p>Your released course results will appear here.</p>
        </section>
      ) : visibleGrades.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No matching grades</h2>
          <p>Try a different search or term filter.</p>
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setSearch("");
              setSelectedTerm("all");
            }}
          >
            Clear filters
          </button>
        </section>
      ) : (
        <div className="student-grade-grid">
          {visibleGrades.map((grade) => {
            const tone = gradeTone(grade.letter_grade);
            return (
              <article className="student-grade-card" key={grade.section_id}>
                <div>
                  <p className="eyebrow">{grade.term_name}</p>
                  <h2>{grade.course_code}</h2>
                  <p className="student-course-title">{grade.course_title}</p>
                  <span className="section-caption">Section {grade.section_code}</span>
                </div>
                <div
                  className={`grade-result grade-result--${tone}`}
                  role="group"
                  aria-label={`Final grade ${grade.letter_grade}, ${grade.percentage} percent`}
                >
                  <strong>{grade.letter_grade}</strong>
                  <span>{grade.percentage}%</span>
                </div>
                <div
                  className={`grade-meter grade-meter--${tone}`}
                  aria-hidden="true"
                >
                  <span style={{ width: `${clampPercentage(grade.percentage)}%` }} />
                </div>
                <p className="released-caption">
                  Released {new Date(grade.released_at).toLocaleDateString()}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

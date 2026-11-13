import { useEffect, useState } from "react";
import { apiRequest, ReleasedGrade } from "./api";

export default function StudentDashboard() {
  const [grades, setGrades] = useState<ReleasedGrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

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
        <p className="empty-state" role="status" aria-live="polite">
          Loading your grades...
        </p>
      ) : grades.length === 0 ? (
        <section className="panel empty-panel">
          <h2>No released grades yet</h2>
          <p>Your released course results will appear here.</p>
        </section>
      ) : (
        <div className="student-grade-grid">
          {grades.map((grade) => (
            <article className="student-grade-card" key={grade.section_id}>
              <div>
                <p className="eyebrow">{grade.term_name}</p>
                <h2>{grade.course_code}</h2>
                <p className="student-course-title">{grade.course_title}</p>
                <span className="section-caption">Section {grade.section_code}</span>
              </div>
              <div className="grade-result">
                <strong>{grade.letter_grade}</strong>
                <span>{grade.percentage}%</span>
              </div>
              <p className="released-caption">
                Released {new Date(grade.released_at).toLocaleDateString()}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

import { useEffect, useState } from "react";

type ApiStatus = "checking" | "online" | "offline";

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    let active = true;

    fetch("/api/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Health check failed: ${response.status}`);
        }
        return response.json() as Promise<{ status: string }>;
      })
      .then((result) => {
        if (active) {
          setApiStatus(result.status === "ok" ? "online" : "offline");
        }
      })
      .catch(() => {
        if (active) {
          setApiStatus("offline");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const statusText = {
    checking: "Checking API",
    online: "API connected",
    offline: "API unavailable",
  }[apiStatus];

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="BITS College gradebook home">
          <span className="brand-mark" aria-hidden="true">B</span>
          <span>
            <strong>BITS College</strong>
            <small>Academic services</small>
          </span>
        </a>
        <span className={`api-status api-status--${apiStatus}`}>
          <span className="status-dot" aria-hidden="true" />
          {statusText}
        </span>
      </header>

      <section className="welcome">
        <p className="eyebrow">STUDENT GRADE MANAGEMENT</p>
        <h1>Every course. Every learner. One clear picture.</h1>
        <p className="welcome-copy">
          A focused workspace for course sections, assessments, and student
          results at BITS College.
        </p>
      </section>

      <section className="workspace" aria-labelledby="workspace-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h2 id="workspace-title">Grade management</h2>
          </div>
          <span className="term-pill">Academic workspace</span>
        </div>
        <div className="feature-grid">
          <article className="feature-card">
            <span className="card-icon card-icon--blue" aria-hidden="true">01</span>
            <h3>Academic structure</h3>
            <p>Set up academic years, terms, courses, and sections.</p>
            <span className="card-state">Foundation in progress</span>
          </article>
          <article className="feature-card">
            <span className="card-icon card-icon--green" aria-hidden="true">02</span>
            <h3>Course gradebooks</h3>
            <p>Organize assessments and weighted grading for each section.</p>
            <span className="card-state">Foundation in progress</span>
          </article>
          <article className="feature-card">
            <span className="card-icon card-icon--amber" aria-hidden="true">03</span>
            <h3>Student results</h3>
            <p>Release final grades and keep a clear history of corrections.</p>
            <span className="card-state">Foundation in progress</span>
          </article>
        </div>
      </section>

      <footer className="page-footer">
        <span>Built for BITS College</span>
        <span>Student Grade Management System</span>
      </footer>
    </main>
  );
}

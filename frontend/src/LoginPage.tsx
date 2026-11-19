import { FormEvent, useState } from "react";
import { apiRequest, jsonBody, User } from "./api";

interface LoginPageProps {
  onLogin: (user: User) => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const user = await apiRequest<User>("/api/auth/login", {
        method: "POST",
        body: jsonBody({ email, password }),
      });
      onLogin(user);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to sign in. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <a className="skip-link" href="#login-main">
        Skip to sign in
      </a>
      <main className="login-layout">
        <aside className="login-showcase">
          <div className="showcase-aurora" aria-hidden="true" />
          <div className="showcase-topline">
            <span className="showcase-badge">BITS College gradebook</span>
            <span className="showcase-term">2026 academic year</span>
          </div>
          <div className="showcase-copy">
            <h2>Clarity for every course, every term.</h2>
            <p>
              A single workspace for academic administrators, instructors, and
              students to keep results accurate and easy to understand.
            </p>
          </div>
          <ul className="showcase-list">
            <li>
              <span className="showcase-icon" aria-hidden="true">01</span>
              <div>
                <strong>Release with confidence</strong>
                <span>Grades stay in draft until every score and weight checks out.</span>
              </div>
            </li>
            <li>
              <span className="showcase-icon" aria-hidden="true">02</span>
              <div>
                <strong>See progress at a glance</strong>
                <span>Students follow released results without chasing paperwork.</span>
              </div>
            </li>
            <li>
              <span className="showcase-icon" aria-hidden="true">03</span>
              <div>
                <strong>Every correction on record</strong>
                <span>Changes require a reason and stay visible in the audit trail.</span>
              </div>
            </li>
          </ul>
          <p className="showcase-footer">
            Academic services · BITS College
          </p>
        </aside>

        <section id="login-main" className="login-card" aria-labelledby="login-title" tabIndex={-1}>
          <a className="brand login-brand" href="/" aria-label="BITS College home">
            <span className="brand-mark" aria-hidden="true">B</span>
            <span className="brand-copy">
              <strong>BITS College</strong>
              <small>Academic services</small>
            </span>
          </a>
          <p className="eyebrow">STUDENT GRADE MANAGEMENT</p>
          <h1 id="login-title">Welcome back</h1>
          <p className="login-description">
            Sign in with your academic account to continue.
          </p>
          <form className="form-stack" onSubmit={submit}>
            <label>
              College email
              <input
                type="email"
                name="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-button" type="submit" disabled={submitting}>
              {submitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
          <p className="login-footnote">
            Accounts are created by an academic administrator.
          </p>
        </section>
      </main>
    </>
  );
}

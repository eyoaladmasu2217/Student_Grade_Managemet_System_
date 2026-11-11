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
    <main className="login-layout">
      <section className="login-card" aria-labelledby="login-title">
        <a className="brand login-brand" href="/" aria-label="BITS College home">
          <span className="brand-mark" aria-hidden="true">B</span>
          <span>
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
  );
}

import { useEffect, useState } from "react";
import { ApiError, apiRequest, User } from "./api";
import LoginPage from "./LoginPage";

type SessionState = "loading" | "signed-out" | "signed-in" | "unavailable";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest<User>("/api/auth/me")
      .then((currentUser) => {
        if (active) {
          setUser(currentUser);
          setSessionState("signed-in");
        }
      })
      .catch((requestError: unknown) => {
        if (!active) {
          return;
        }
        if (requestError instanceof ApiError && requestError.status === 401) {
          setSessionState("signed-out");
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The API could not be reached.",
        );
        setSessionState("unavailable");
      });

    return () => {
      active = false;
    };
  }, []);

  async function signOut() {
    try {
      await apiRequest<void>("/api/auth/logout", { method: "POST" });
      setUser(null);
      setSessionState("signed-out");
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to sign out. Try again.",
      );
    }
  }

  if (sessionState === "loading") {
    return <main className="loading-screen" aria-live="polite">Loading your workspace...</main>;
  }

  if (sessionState === "unavailable") {
    return (
      <main className="loading-screen">
        <section className="notice-card">
          <p className="eyebrow">CONNECTION ISSUE</p>
          <h1>We could not load your workspace.</h1>
          <p>{error}</p>
          <button className="secondary-button" onClick={() => window.location.reload()}>
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (!user) {
    return <LoginPage onLogin={(signedInUser) => {
      setUser(signedInUser);
      setSessionState("signed-in");
    }} />;
  }

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
        <div className="account-menu">
          <span className="account-details">
            <strong>{user.full_name}</strong>
            <small>{user.role.replace("_", " ")}</small>
          </span>
          <button className="secondary-button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      {error && <p className="form-error global-error" role="alert">{error}</p>}
      <section className="welcome">
        <p className="eyebrow">STUDENT GRADE MANAGEMENT</p>
        <h1>Every course. Every learner. One clear picture.</h1>
        <p className="welcome-copy">
          A focused workspace for course sections, assessments, and student
          results at BITS College.
        </p>
      </section>
      <section className="workspace">
        <p className="eyebrow">SIGNED IN AS {user.role.toUpperCase()}</p>
        <h2>Your academic workspace is ready</h2>
        <p className="welcome-copy">
          The grade management features for your role are being connected.
        </p>
      </section>
    </main>
  );
}

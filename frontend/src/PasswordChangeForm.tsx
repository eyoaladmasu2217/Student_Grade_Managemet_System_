import { FormEvent, useState } from "react";
import { apiRequest, jsonBody } from "./api";

interface PasswordChangeFormProps {
  onComplete: () => void;
  onCancel: () => void;
}

export default function PasswordChangeForm({
  onComplete,
  onCancel,
}: PasswordChangeFormProps) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const currentPassword = String(form.get("current_password") ?? "");
    const newPassword = String(form.get("new_password") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");
    if (newPassword !== confirmation) {
      setError("New password and confirmation do not match.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await apiRequest("/api/auth/change-password", {
        method: "POST",
        body: jsonBody({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      onComplete();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to update the password.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel password-panel" aria-labelledby="password-title">
      <div className="panel-title-row">
        <h2 id="password-title">Change password</h2>
        <button className="text-button" type="button" onClick={onCancel}>Cancel</button>
      </div>
      <form className="password-form" onSubmit={submit}>
        <label>
          Current password
          <input name="current_password" type="password" autoComplete="current-password" required />
        </label>
        <label>
          New password
          <input
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
          />
        </label>
        <label>
          Confirm new password
          <input
            name="confirmation"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={128}
            required
          />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="button-row">
          <button className="primary-button" type="submit" disabled={saving}>
            {saving ? "Updating..." : "Update password"}
          </button>
          <button className="secondary-button" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

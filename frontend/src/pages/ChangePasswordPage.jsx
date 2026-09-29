import { useState } from "react";

import { changePassword } from "../api/authApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

// `required` is the first-login case: the user can't continue until they pick a new password.
function ChangePasswordPage({ required = false }) {
  const { token, markPasswordChanged, logout } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    if (next !== confirm) {
      setState("error");
      setError("The new passwords don't match.");
      return;
    }
    setState("saving");
    setError(null);
    try {
      await changePassword(token, current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setState("success");
      markPasswordChanged();
    } catch (err) {
      setState("error");
      setError(err instanceof ApiError ? err.message : "Couldn't change your password. Try again.");
    }
  }

  return (
    <div className={required ? "flex min-h-screen items-center justify-center bg-slate-50 px-4" : ""}>
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">{required ? "Choose your own password" : "Change password"}</h2>
          {required && <p className="mt-1 text-sm text-slate-500">You signed in with a password from college. Pick a new one only you know.</p>}
        </div>
        <div>
          <label htmlFor="current-password" className="block text-sm font-medium text-slate-700">
            {required ? "Password from college" : "Current password"}
          </label>
          <input id="current-password" type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="new-password" className="block text-sm font-medium text-slate-700">
            New password (at least 8 characters)
          </label>
          <input id="new-password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="confirm-password" className="block text-sm font-medium text-slate-700">
            Repeat new password
          </label>
          <input id="confirm-password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={INPUT_CLASS} />
        </div>
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        {state === "success" && !required && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Password changed.</p>}
        <button
          type="submit"
          disabled={state === "saving"}
          className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {state === "saving" ? "Saving…" : "Save new password"}
        </button>
        {required && (
          <button type="button" onClick={logout} className="w-full text-center text-sm font-medium text-slate-500 hover:underline">
            Log out
          </button>
        )}
      </form>
    </div>
  );
}

export default ChangePasswordPage;

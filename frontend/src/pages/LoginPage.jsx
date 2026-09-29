import { useState } from "react";

import DeveloperCredit from "../components/DeveloperCredit";
import InstallBanner from "../components/InstallBanner";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const MODE_KEY = "school_management_login_mode";
const COLLEGE_CODE_KEY = "college_login_code";

function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Only a convenience.
  }
}

function readSaved(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

const MODES = ["student", "parent", "staff"];

// Install links / QR codes open "/?as=student", "/?as=parent" or "/?as=staff" (as=admin is the staff tab too),
// optionally with "&college=CODE" to fill in the college code for students.
// The tab is remembered, because the installed app later starts without the link.
function initialMode() {
  const params = new URLSearchParams(window.location.search);
  const as = { admin: "staff" }[params.get("as")] ?? params.get("as");
  if (params.get("college")) remember(COLLEGE_CODE_KEY, params.get("college"));
  if (MODES.includes(as)) {
    remember(MODE_KEY, as);
    return as;
  }
  const saved = readSaved(MODE_KEY);
  return MODES.includes(saved) ? saved : "staff";
}

// The platform (super admin) signs in only at /superadmin, which no page links to.
function isPlatformPage() {
  return window.location.pathname.replace(/\/+$/, "").toLowerCase() === "/superadmin";
}

function PlatformLoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await login({ email, password, portal: "platform" });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.code === "too_many_attempts"
            ? err.message
            : "Incorrect email or password."
          : "Couldn't reach the server. Check your connection and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900 px-4 py-8">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-lg">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Platform administration</p>
        <h1 className="mt-1 text-xl font-bold text-slate-900">Super admin sign in</h1>
        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label htmlFor="platform-email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input id="platform-email" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} className={INPUT_CLASS} />
          </div>
          <div>
            <label htmlFor="platform-password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input id="platform-password" type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={INPUT_CLASS} />
          </div>
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <button type="submit" disabled={isSubmitting} className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
      <DeveloperCredit />
    </div>
  );
}

function LoginPage() {
  return isPlatformPage() ? <PlatformLoginPage /> : <SchoolLoginPage />;
}

function SchoolLoginPage() {
  const { login } = useAuth();
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [collegeCode, setCollegeCode] = useState(() => readSaved(COLLEGE_CODE_KEY) ?? "");
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      if (mode === "parent") {
        await login({ phone: phone.trim(), password, portal: "school" });
      } else if (mode === "student") {
        remember(COLLEGE_CODE_KEY, collegeCode.trim());
        await login({ college_code: collegeCode.trim(), roll_number: rollNumber.trim(), password, portal: "school" });
      } else {
        await login({ email, password, portal: "school" });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (["too_many_attempts", "school_inactive", "school_suspended", "student_login_closed"].includes(err.code)) {
          setError(err.message);
        } else {
          setError(
            { parent: "Incorrect mobile number or password.", student: "Incorrect college code, roll number or password." }[mode] ??
              "Incorrect email or password.",
          );
        }
      } else {
        setError("Couldn't reach the server. Check your connection and try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function switchMode(next) {
    setMode(next);
    remember(MODE_KEY, next);
    setError(null);
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-4 py-8">
      <div className="w-full max-w-sm">
        <InstallBanner />
      </div>
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">College management platform</p>
        <h1 className="mt-1 text-xl font-bold text-slate-900">Sign in</h1>

        <div role="tablist" aria-label="Sign in as" className="mt-5 grid grid-cols-3 rounded-lg bg-slate-100 p-1 text-sm font-semibold">
          {[
            { id: "student", label: "Student" },
            { id: "parent", label: "Parent" },
            { id: "staff", label: "Faculty / Admin" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={mode === tab.id}
              onClick={() => switchMode(tab.id)}
              className={`rounded-md px-3 py-1.5 transition-colors ${mode === tab.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          {mode === "student" && (
            <div className="grid grid-cols-5 gap-3">
              <div className="col-span-2">
                <label htmlFor="college-code" className="block text-sm font-medium text-slate-700">
                  College code
                </label>
                <input
                  id="college-code"
                  required
                  autoCapitalize="characters"
                  placeholder="e.g. ANVCOL"
                  value={collegeCode}
                  onChange={(event) => setCollegeCode(event.target.value)}
                  className={`${INPUT_CLASS} uppercase`}
                />
              </div>
              <div className="col-span-3">
                <label htmlFor="roll-number" className="block text-sm font-medium text-slate-700">
                  Roll number
                </label>
                <input
                  id="roll-number"
                  required
                  autoComplete="username"
                  autoCapitalize="characters"
                  placeholder="e.g. 23A91A0501"
                  value={rollNumber}
                  onChange={(event) => setRollNumber(event.target.value)}
                  className={`${INPUT_CLASS} uppercase`}
                />
              </div>
            </div>
          )}
          {mode === "parent" && (
            <div>
              <label htmlFor="parent-phone" className="block text-sm font-medium text-slate-700">
                Mobile number
              </label>
              <input
                id="parent-phone"
                type="tel"
                required
                autoComplete="username"
                inputMode="tel"
                placeholder="10-digit mobile number"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                className={INPUT_CLASS}
              />
            </div>
          )}
          {mode === "staff" && (
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className={INPUT_CLASS}
              />
            </div>
          )}

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={INPUT_CLASS}
            />
          </div>

          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
          {mode === "staff" && <p className="text-center text-xs text-slate-400">College admins, faculty and staff sign in here with their email.</p>}
          {mode === "student" && (
            <p className="text-center text-xs text-slate-400">
              Your first password comes from the college office. See your attendance, results with SGPA / CGPA, fees, assignments, timetable and notices.
            </p>
          )}
          {mode === "parent" && (
            <p className="text-center text-xs text-slate-400">
              Use the mobile number the college has for you. Your first password comes from the college. Everything for your child is here: attendance, results, fees,
              assignments and notices.
            </p>
          )}
        </form>
      </div>
      <DeveloperCredit />
    </div>
  );
}

export default LoginPage;

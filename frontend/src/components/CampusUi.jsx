import { useCallback, useEffect, useState } from "react";

import { fetchStudents } from "../api/studentsApi";
import { ApiError } from "../lib/apiClient";

// Small shared pieces for the campus pages (library, hostel, transport, placements).

export const INPUT =
  "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
export const PRIMARY = "rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60";
export const SECONDARY = "rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100";
export const DANGER = "rounded-lg px-3 py-1.5 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50";

export function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

export function rupees(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN")}`;
}

/** Loads data with a loading / error state; returns [data, reload, state]. */
export function useLoad(loader, deps) {
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const load = useCallback(loader, deps);
  const reload = useCallback(async () => {
    try {
      setData(await load());
      setState("ready");
    } catch (err) {
      setState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [load]);
  useEffect(() => {
    reload();
  }, [reload]);
  return [data, reload, state];
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2 self-start">{children}</div>}
    </div>
  );
}

export function LoadState({ state, onRetry, what }) {
  if (state === "loading") return <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "forbidden")
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center text-sm font-semibold text-amber-800">
        This module isn&apos;t switched on for your college, or you don&apos;t have access.
      </div>
    );
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
      <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load {what}.</p>
      <button type="button" onClick={onRetry} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white">
        Retry
      </button>
    </div>
  );
}

export function Stat({ label, value, tone = "slate" }) {
  const tones = { slate: "text-slate-900", rose: "text-rose-700", emerald: "text-emerald-700" };
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`text-xl font-bold ${tones[tone]}`}>{value}</p>
    </div>
  );
}

export function Field({ id, label, children, className = "" }) {
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
    </div>
  );
}

export function Notice({ message, error }) {
  if (!message && !error) return null;
  return error ? (
    <p className="rounded-lg bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">{error}</p>
  ) : (
    <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{message}</p>
  );
}

/** Search-as-you-type student chooser; calls onChange(student) with the chosen student. */
export function StudentPicker({ token, id, value, onChange }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    const timer = setTimeout(() => {
      fetchStudents(token, { q: q.trim() })
        .then((list) => setResults(list.slice(0, 8)))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [token, q]);

  if (value) {
    return (
      <div className="mt-1 flex items-center justify-between rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm">
        <span>
          <span className="font-semibold text-slate-800">{value.full_name}</span>{" "}
          <span className="text-slate-500">
            {value.admission_number} · {value.class?.name} - {value.class?.section}
          </span>
        </span>
        <button type="button" onClick={() => onChange(null)} className="text-xs font-semibold text-slate-500 hover:text-rose-600">
          Change
        </button>
      </div>
    );
  }
  return (
    <div className="relative">
      <input id={id} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a name or roll number" className={INPUT} autoComplete="off" />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          {results.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => {
                  onChange(s);
                  setQ("");
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <span className="font-semibold text-slate-800">{s.full_name}</span>{" "}
                <span className="text-slate-500">
                  {s.admission_number} · {s.class?.name} - {s.class?.section}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

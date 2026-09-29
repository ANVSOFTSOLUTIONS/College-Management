import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const AREAS = [
  ["", "Everything"],
  ["marks", "Marks & exams"],
  ["fees", "Fees"],
  ["attendance", "Attendance"],
  ["students", "Students & certificates"],
  ["staff", "Staff & payroll"],
  ["admissions", "Admissions"],
  ["settings", "Settings"],
];
const INPUT = "mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

function when(iso) {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

// Who changed what, and when: marks, fees, attendance edits, certificates, salaries, admissions, settings.
function ActivityLogPage() {
  const { token, user } = useAuth();
  const [filters, setFilters] = useState({ area: "", start: "", end: "", q: "" });
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState([]);
  const [open, setOpen] = useState(null);
  const [state, setState] = useState("loading");

  const load = useCallback(async () => {
    setState("loading");
    try {
      setEntries(
        await apiRequest("/audit-log", {
          token,
          params: { area: filters.area || undefined, start: filters.start || undefined, end: filters.end || undefined, q: filters.q || undefined },
        }),
      );
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, filters]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Activity log</h2>
        <p className="mt-1 text-sm text-slate-500">
          Who changed what, and when: marks, fees, attendance edits, certificates, salaries, admissions and settings
          {user.role === "super_admin" ? ", across all colleges." : ". Entries can't be edited or deleted."}
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-slate-700">
          Area
          <select value={filters.area} onChange={(e) => setFilters({ ...filters, area: e.target.value })} className={INPUT}>
            {AREAS.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          From
          <input type="date" value={filters.start} onChange={(e) => setFilters({ ...filters, start: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          To
          <input type="date" value={filters.end} onChange={(e) => setFilters({ ...filters, end: e.target.value })} className={INPUT} />
        </label>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFilters({ ...filters, q: query.trim() });
          }}
          className="flex items-end gap-2"
        >
          <label className="text-sm font-medium text-slate-700">
            Search
            <input value={query} maxLength={100} onChange={(e) => setQuery(e.target.value)} placeholder="Student, teacher, receipt…" className={INPUT} />
          </label>
          <button type="submit" className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white">
            Search
          </button>
        </form>
      </div>

      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && (
        <p className="text-sm font-semibold text-rose-700">
          Couldn&apos;t load the activity log.{" "}
          <button type="button" onClick={load} className="underline">
            Try again
          </button>
        </p>
      )}
      {state === "ready" &&
        (entries.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">Nothing recorded for this selection yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {entries.map((e) => (
              <li key={e.id} className="px-4 py-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-900">{e.summary}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {when(e.created_at)} · <span className="font-medium text-slate-700">{e.user_name}</span> ({e.user_role.replace("_", " ")}) · {e.area}
                    </p>
                  </div>
                  {Array.isArray(e.details) && e.details.length > 0 && (
                    <button type="button" onClick={() => setOpen(open === e.id ? null : e.id)} className="shrink-0 text-xs font-semibold text-emerald-700 hover:underline" aria-expanded={open === e.id}>
                      {open === e.id ? "Hide" : `All ${e.details.length}`}
                    </button>
                  )}
                </div>
                {open === e.id && (
                  <ul className="mt-2 grid gap-1 rounded-lg bg-slate-50 p-3 text-xs sm:grid-cols-2">
                    {e.details.map((d, i) => (
                      <li key={i}>
                        {d.student ?? d.student_id}: <span className="text-slate-500">{d.from}</span> → <span className="font-semibold">{d.to}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}

export default ActivityLogPage;

import { useCallback, useEffect, useState } from "react";

import { fetchMyPunches, punchIn, punchOut } from "../api/staffApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

export function formatTime(iso) {
  return iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }) : "—";
}

export function formatWorked(minutes) {
  if (minutes === null || minutes === undefined) return "—";
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <p className="text-4xl font-bold tabular-nums text-slate-900">
      {now.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", second: "2-digit" })}
    </p>
  );
}

function PunchPage() {
  const { token } = useAuth();
  const [state, setState] = useState("loading");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchMyPunches(token));
      setState("ready");
    } catch (err) {
      setState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action(token);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't record the punch. Check your connection.");
    } finally {
      setBusy(false);
    }
  }

  if (state === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "forbidden") return <p className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center text-sm font-semibold text-amber-800">Punch in/out is for teaching staff.</p>;
  if (state === "error") {
    return (
      <p className="text-sm font-semibold text-rose-700">
        Couldn&apos;t load your punches.{" "}
        <button type="button" onClick={load} className="underline">
          Retry
        </button>
      </p>
    );
  }

  const { today } = data;
  const punchedIn = Boolean(today.punch_in_at);
  const punchedOut = Boolean(today.punch_out_at);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Punch In / Out</h2>
        <p className="mt-1 text-sm text-slate-500">
          College starts at {data.day_starts_at}; punching in more than {data.late_grace_minutes} minutes after that counts as late.
        </p>
      </div>

      <section className="flex flex-col items-center gap-4 rounded-2xl border border-slate-200 bg-white p-6 text-center">
        <Clock />
        <p className="text-sm text-slate-500">{new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}</p>
        {!punchedIn && (
          <button type="button" disabled={busy} onClick={() => run(punchIn)} className="w-full max-w-xs rounded-2xl bg-emerald-600 py-4 text-lg font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-60">
            {busy ? "Punching in…" : "Punch In"}
          </button>
        )}
        {punchedIn && !punchedOut && (
          <button type="button" disabled={busy} onClick={() => window.confirm("Punch out for today?") && run(punchOut)} className="w-full max-w-xs rounded-2xl bg-slate-800 py-4 text-lg font-bold text-white shadow-sm hover:bg-slate-900 disabled:opacity-60">
            {busy ? "Punching out…" : "Punch Out"}
          </button>
        )}
        <div className="grid w-full max-w-sm grid-cols-3 gap-3 text-sm">
          <div className="rounded-xl bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">In</p>
            <p className={`font-semibold ${today.is_late ? "text-rose-700" : "text-slate-900"}`}>{formatTime(today.punch_in_at)}</p>
            {today.is_late && <p className="text-xs font-semibold text-rose-600">Late</p>}
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Out</p>
            <p className="font-semibold text-slate-900">{formatTime(today.punch_out_at)}</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Worked</p>
            <p className="font-semibold text-slate-900">{formatWorked(today.worked_minutes)}</p>
          </div>
        </div>
        {punchedOut && <p className="text-sm font-medium text-emerald-700">Done for today. See you tomorrow!</p>}
        {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      </section>

      <section className="space-y-3">
        <h3 className="text-lg font-semibold text-slate-900">Last 30 days</h3>
        {data.recent.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No earlier punches.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm">
            {data.recent.map((p) => (
              <li key={p.date} className="flex items-center justify-between px-4 py-2">
                <span className="text-slate-700">{new Date(p.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}</span>
                <span className="text-slate-600">
                  <span className={p.is_late ? "font-semibold text-rose-700" : ""}>{formatTime(p.punch_in_at)}</span> – {formatTime(p.punch_out_at)} · {formatWorked(p.worked_minutes)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default PunchPage;

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchPunchesForDay, fetchSchoolSettings, saveSchoolSettings } from "../api/staffApi";
import { fetchStaffAttendance, submitStaffAttendance } from "../api/staffAttendanceApi";
import { formatTime, formatWorked } from "./PunchPage";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const STATUS_OPTIONS = [
  { value: "present", label: "Present", selectedClass: "bg-emerald-600 text-white" },
  { value: "absent", label: "Absent", selectedClass: "bg-rose-600 text-white" },
  { value: "late", label: "Late", selectedClass: "bg-amber-500 text-white" },
  { value: "leave", label: "Leave", selectedClass: "bg-sky-600 text-white" },
];

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function SchoolTimings({ token }) {
  const [settings, setSettings] = useState(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSchoolSettings(token).then(setSettings).catch(() => {});
  }, [token]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      setSettings(await saveSchoolSettings(token, settings));
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
  }

  if (!settings) return null;
  return editing ? (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 text-sm">
      <label className="flex flex-col text-xs font-medium text-slate-600">
        College starts
        <input type="time" required value={settings.day_starts_at} onChange={(e) => setSettings({ ...settings, day_starts_at: e.target.value })} className="mt-1 rounded-lg border border-slate-300 px-2 py-1.5" />
      </label>
      <label className="flex flex-col text-xs font-medium text-slate-600">
        Late after (minutes)
        <input type="number" min="0" max="240" required value={settings.late_grace_minutes} onChange={(e) => setSettings({ ...settings, late_grace_minutes: Number(e.target.value) })} className="mt-1 w-24 rounded-lg border border-slate-300 px-2 py-1.5" />
      </label>
      <button type="submit" className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white">
        Save
      </button>
      {error && <span className="text-xs text-rose-600">{error}</span>}
    </form>
  ) : (
    <p className="text-xs text-slate-500">
      College starts {settings.day_starts_at}; punch-ins more than {settings.late_grace_minutes} min later are late.{" "}
      <button type="button" onClick={() => setEditing(true)} className="font-semibold text-emerald-700 hover:underline">
        Change
      </button>
    </p>
  );
}

function PunchLog({ token, date }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    setRows(null);
    fetchPunchesForDay(token, date).then(setRows).catch(() => setRows([]));
  }, [token, date]);
  if (rows === null) return <div className="h-24 animate-pulse rounded-xl bg-slate-100" />;
  const came = rows.filter((r) => r.punch).length;
  const late = rows.filter((r) => r.punch?.is_late).length;
  return (
    <section className="space-y-2">
      <h3 className="text-lg font-semibold text-slate-900">Punch log</h3>
      <p className="text-sm text-slate-500">
        {came} of {rows.length} punched in{late > 0 && <span className="font-semibold text-rose-700"> · {late} late</span>}
      </p>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Teacher</th>
              <th className="px-4 py-2">In</th>
              <th className="px-4 py-2">Out</th>
              <th className="px-4 py-2">Worked</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={r.teacher_id}>
                <td className="px-4 py-2">
                  <p className="font-semibold text-slate-800">{r.full_name}</p>
                  <p className="text-xs text-slate-400">{r.department}</p>
                </td>
                <td className={`px-4 py-2 ${r.punch?.is_late ? "font-semibold text-rose-700" : "text-slate-700"}`}>
                  {r.punch ? formatTime(r.punch.punch_in_at) : r.on_leave ? <span className="text-sky-700">On leave</span> : <span className="text-slate-400">Not in</span>}
                  {r.punch?.is_late && <span className="ml-1 text-xs">(late)</span>}
                </td>
                <td className="px-4 py-2 text-slate-700">{r.punch ? formatTime(r.punch.punch_out_at) : "—"}</td>
                <td className="px-4 py-2 text-slate-700">{r.punch ? formatWorked(r.punch.worked_minutes) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StaffAttendancePage() {
  const { token } = useAuth();

  const [date, setDate] = useState(todayIsoDate);
  const [loadState, setLoadState] = useState("loading");
  const [loadError, setLoadError] = useState(null);
  const [entries, setEntries] = useState([]);
  const [draftStatus, setDraftStatus] = useState({});

  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState(null);

  const loadAttendance = useCallback(async () => {
    setLoadState("loading");
    setSaveState("idle");
    try {
      const result = await fetchStaffAttendance(token, date);
      setEntries(result.entries);
      setDraftStatus(
        Object.fromEntries(result.entries.filter((entry) => entry.status).map((entry) => [entry.teacher_id, entry.status])),
      );
      setLoadState("ready");
    } catch (err) {
      setLoadError(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
      setLoadState("error");
    }
  }, [token, date]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const summary = useMemo(() => {
    const counts = Object.fromEntries(STATUS_OPTIONS.map((option) => [option.value, 0]));
    Object.values(draftStatus).forEach((status) => {
      counts[status] += 1;
    });
    return counts;
  }, [draftStatus]);

  function setStatus(teacherId, status) {
    setDraftStatus((prev) => ({ ...prev, [teacherId]: status }));
  }

  function markAllPresent() {
    setDraftStatus(Object.fromEntries(entries.map((entry) => [entry.teacher_id, "present"])));
  }

  async function handleSave() {
    const records = Object.entries(draftStatus).map(([teacher_id, status]) => ({ teacher_id, status }));
    if (records.length === 0) {
      setSaveState("error");
      setSaveError("Mark at least one teacher before saving.");
      return;
    }

    setSaveState("saving");
    setSaveError(null);
    try {
      await submitStaffAttendance(token, date, records);
      await loadAttendance();
      setSaveState("success");
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof ApiError ? err.message : "Couldn't save attendance. Try again.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Teacher Attendance</h2>
        <p className="mt-1 text-sm text-slate-500">Teachers punch in and out from their own login; you can also mark attendance here.</p>
        <div className="mt-2">
          <SchoolTimings token={token} />
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="date"
          value={date}
          onChange={(event) => setDate(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 sm:w-auto"
        />

        {loadState === "ready" && entries.length > 0 && (
          <button
            type="button"
            onClick={markAllPresent}
            className="self-start rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100 sm:self-auto"
          >
            Mark all present
          </button>
        )}
      </div>

      <PunchLog token={token} date={date} />

      {loadState === "loading" && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="flex items-center gap-4 border-b border-slate-100 px-4 py-4 last:border-b-0">
              <div className="h-3 w-1/3 flex-1 animate-pulse rounded bg-slate-200" />
              <div className="h-6 w-48 animate-pulse rounded-full bg-slate-100" />
            </div>
          ))}
        </div>
      )}

      {loadState === "error" && loadError === "forbidden" && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-amber-800">Only college admins can manage teacher attendance.</p>
        </div>
      )}

      {loadState === "error" && loadError !== "forbidden" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load teacher attendance.</p>
          <button
            type="button"
            onClick={loadAttendance}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            Retry
          </button>
        </div>
      )}

      {loadState === "ready" && entries.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-600">No teachers in this college yet.</p>
        </div>
      )}

      {loadState === "ready" && entries.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {STATUS_OPTIONS.map((option) => (
              <div key={option.value} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{option.label}</p>
                <p className="mt-1 text-2xl font-bold text-slate-900">{summary[option.value]}</p>
              </div>
            ))}
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Teacher</th>
                  <th className="px-4 py-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {entries.map((entry) => (
                  <tr key={entry.teacher_id}>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-800">{entry.full_name}</p>
                      <p className="text-xs text-slate-400">{entry.department}</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1.5">
                        {STATUS_OPTIONS.map((option) => {
                          const isSelected = draftStatus[entry.teacher_id] === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setStatus(entry.teacher_id, option.value)}
                              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                                isSelected ? option.selectedClass : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                              }`}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saveState === "saving"}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saveState === "saving" ? "Saving…" : "Save attendance"}
            </button>
            {saveState === "success" && <span className="text-sm font-medium text-emerald-700">Saved.</span>}
            {saveState === "error" && <span className="text-sm font-medium text-rose-600">{saveError}</span>}
          </div>
        </>
      )}
    </div>
  );
}

export default StaffAttendancePage;

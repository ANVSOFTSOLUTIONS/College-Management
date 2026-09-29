import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchAttendance, fetchMyClasses, submitAttendance } from "../api/attendanceApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const STATUS_OPTIONS = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
];

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function AttendancePage() {
  const { token } = useAuth();

  const [classesState, setClassesState] = useState("loading");
  const [classes, setClasses] = useState([]);
  const [selectedClassId, setSelectedClassId] = useState(null);
  const [date, setDate] = useState(todayIsoDate);

  const [attendanceState, setAttendanceState] = useState("idle");
  const [entries, setEntries] = useState([]);
  const [draftStatus, setDraftStatus] = useState({});

  const [saveState, setSaveState] = useState("idle");
  const [saveError, setSaveError] = useState(null);

  const loadClasses = useCallback(async () => {
    setClassesState("loading");
    try {
      const result = await fetchMyClasses(token);
      setClasses(result);
      setSelectedClassId((current) => current ?? result[0]?.id ?? null);
      setClassesState("ready");
    } catch {
      setClassesState("error");
    }
  }, [token]);

  useEffect(() => {
    loadClasses();
  }, [loadClasses]);

  const loadAttendance = useCallback(async () => {
    if (!selectedClassId) return;
    setAttendanceState("loading");
    setSaveState("idle");
    try {
      const result = await fetchAttendance(token, selectedClassId, date);
      setEntries(result.entries);
      setDraftStatus(
        Object.fromEntries(result.entries.filter((entry) => entry.status).map((entry) => [entry.student_id, entry.status])),
      );
      setAttendanceState("ready");
    } catch {
      setAttendanceState("error");
    }
  }, [token, selectedClassId, date]);

  useEffect(() => {
    loadAttendance();
  }, [loadAttendance]);

  const selectedClass = useMemo(
    () => classes.find((classItem) => classItem.id === selectedClassId) ?? null,
    [classes, selectedClassId],
  );

  function setStatus(studentId, status) {
    setDraftStatus((prev) => ({ ...prev, [studentId]: status }));
  }

  function markAllPresent() {
    setDraftStatus(Object.fromEntries(entries.map((entry) => [entry.student_id, "present"])));
  }

  async function handleSave() {
    const records = Object.entries(draftStatus).map(([student_id, status]) => ({ student_id, status }));
    if (records.length === 0) {
      setSaveState("error");
      setSaveError("Mark at least one student before saving.");
      return;
    }

    setSaveState("saving");
    setSaveError(null);
    try {
      await submitAttendance(token, selectedClassId, date, records);
      await loadAttendance();
      setSaveState("success");
    } catch (err) {
      setSaveState("error");
      setSaveError(err instanceof ApiError ? err.message : "Couldn't save attendance. Try again.");
    }
  }

  if (classesState === "loading") {
    return (
      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-6">
        <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-1/4 animate-pulse rounded bg-slate-100" />
      </div>
    );
  }

  if (classesState === "error") {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load your classes.</p>
        <button
          type="button"
          onClick={loadClasses}
          className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (classes.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-600">You&apos;re not assigned to any class yet.</p>
        <p className="mt-1 text-sm text-slate-400">Ask a college admin to assign you to a class.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Student Attendance</h2>
        <p className="mt-1 text-sm text-slate-500">Mark and review daily student attendance.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          {classes.length > 1 ? (
            <select
              value={selectedClassId ?? ""}
              onChange={(event) => setSelectedClassId(event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            >
              {classes.map((classItem) => (
                <option key={classItem.id} value={classItem.id}>
                  {classItem.name} - {classItem.section}
                </option>
              ))}
            </select>
          ) : (
            selectedClass && (
              <p className="text-sm font-semibold text-slate-700">
                {selectedClass.name} - {selectedClass.section}
              </p>
            )
          )}

          <input
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>

        {attendanceState === "ready" && entries.length > 0 && (
          <button
            type="button"
            onClick={markAllPresent}
            className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
          >
            Mark all present
          </button>
        )}
      </div>

      {attendanceState === "loading" && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="flex items-center gap-4 border-b border-slate-100 px-4 py-4 last:border-b-0">
              <div className="h-3 w-1/3 flex-1 animate-pulse rounded bg-slate-200" />
              <div className="h-6 w-40 animate-pulse rounded-full bg-slate-100" />
            </div>
          ))}
        </div>
      )}

      {attendanceState === "error" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load attendance for this class.</p>
          <button
            type="button"
            onClick={loadAttendance}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            Retry
          </button>
        </div>
      )}

      {attendanceState === "ready" && entries.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-600">No students in this class yet.</p>
        </div>
      )}

      {attendanceState === "ready" && entries.length > 0 && (
        <>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Student</th>
                  <th className="px-4 py-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {entries.map((entry) => (
                  <tr key={entry.student_id}>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-800">{entry.full_name}</p>
                      <p className="text-xs text-slate-400">
                        {entry.admission_number}
                        {entry.on_leave && <span className="ml-2 rounded-full bg-sky-50 px-2 py-0.5 font-semibold text-sky-700">On leave</span>}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1.5">
                        {STATUS_OPTIONS.map((option) => {
                          const isSelected = draftStatus[entry.student_id] === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setStatus(entry.student_id, option.value)}
                              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                                isSelected
                                  ? option.value === "present"
                                    ? "bg-emerald-600 text-white"
                                    : option.value === "absent"
                                      ? "bg-rose-600 text-white"
                                      : "bg-amber-500 text-white"
                                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
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

export default AttendancePage;

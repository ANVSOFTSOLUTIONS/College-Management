import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../lib/apiClient";
import { errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";

const NEXT = { present: "absent", absent: "late", late: "present" };
const COLORS = { present: "bg-emerald-600", absent: "bg-rose-600", late: "bg-amber-500" };

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function MarkTab({ token, subjects }) {
  const [pick, setPick] = useState(subjects[0] ? `${subjects[0].class_id}|${subjects[0].subject_id}` : "");
  const [day, setDay] = useState(today());
  const [period, setPeriod] = useState(1);
  const [marks, setMarks] = useState({});
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [classId, subjectId] = pick.split("|");
  const [sheet, reload, state] = useLoad(
    () => (pick ? apiRequest("/subject-attendance/sheet", { token, params: { class_id: classId, subject_id: subjectId, day, period } }) : Promise.resolve(null)),
    [token, pick, day, period],
  );

  useEffect(() => {
    if (sheet) setMarks(Object.fromEntries(sheet.rows.map((r) => [r.student_id, r.status ?? "present"])));
  }, [sheet]);

  async function save() {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      await apiRequest("/subject-attendance", {
        method: "POST",
        token,
        body: { class_id: classId, subject_id: subjectId, date: day, period: Number(period), records: sheet.rows.map((r) => ({ student_id: r.student_id, status: marks[r.student_id] })) },
      });
      setMessage(`Saved: ${sheet.subject_name}, ${day}, period ${period}.`);
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save attendance."));
    } finally {
      setSaving(false);
    }
  }

  if (!subjects.length) return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">You don&apos;t teach any subject yet.</p>;
  const counts = Object.values(marks).reduce((c, s) => ({ ...c, [s]: (c[s] ?? 0) + 1 }), {});
  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-4">
        <label className="text-sm font-medium text-slate-700 sm:col-span-2">
          Batch & subject
          <select value={pick} onChange={(e) => setPick(e.target.value)} className={INPUT}>
            {subjects.map((s) => (
              <option key={`${s.class_id}|${s.subject_id}`} value={`${s.class_id}|${s.subject_id}`}>
                {s.class_name} - {s.section} · {s.subject_name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Date
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Period / hour
          <select value={period} onChange={(e) => setPeriod(Number(e.target.value))} className={INPUT}>
            {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                Period {n}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Notice message={message} error={error} />
      {state !== "ready" || !sheet ? (
        <LoadState state={state} onRetry={reload} what="the attendance sheet" />
      ) : (
        <>
          <p className="text-sm text-slate-500">
            {sheet.marked ? "Already marked — you're editing it. " : ""}Click a student to switch present → absent → late. Present {counts.present ?? 0} · Absent{" "}
            {counts.absent ?? 0} · Late {counts.late ?? 0}
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {sheet.rows.map((r) => {
              const s = marks[r.student_id] ?? "present";
              return (
                <button
                  key={r.student_id}
                  type="button"
                  onClick={() => setMarks({ ...marks, [r.student_id]: NEXT[s] })}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-left hover:bg-slate-50"
                >
                  <span>
                    <span className="block font-semibold text-slate-800">{r.full_name}</span>
                    <span className="text-xs text-slate-400">{r.admission_number}</span>
                  </span>
                  <span className={`rounded-full px-3 py-1 text-xs font-bold capitalize text-white ${COLORS[s]}`}>{s}</span>
                </button>
              );
            })}
          </div>
          {sheet.rows.length > 0 && (
            <button type="button" disabled={saving} onClick={save} className={PRIMARY}>
              {saving ? "Saving…" : sheet.marked ? "Update attendance" : "Save attendance"}
            </button>
          )}
        </>
      )}
    </div>
  );
}

function SummaryTab({ token, subjects }) {
  const batches = useMemo(() => [...new Map(subjects.map((s) => [s.class_id, s])).values()], [subjects]);
  const [classId, setClassId] = useState(batches[0]?.class_id ?? "");
  const [rows, reload, state] = useLoad(
    () => (classId ? apiRequest("/subject-attendance/summary", { token, params: { class_id: classId } }) : Promise.resolve([])),
    [token, classId],
  );
  const subjectNames = useMemo(() => [...new Set((rows ?? []).flatMap((r) => r.subjects.map((s) => s.subject_name)))].sort(), [rows]);

  if (!batches.length) return null;
  return (
    <div className="space-y-4">
      <select aria-label="Batch" value={classId} onChange={(e) => setClassId(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
        {batches.map((b) => (
          <option key={b.class_id} value={b.class_id}>
            {b.class_name} - {b.section}
          </option>
        ))}
      </select>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="the summary" />
      ) : subjectNames.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No subject attendance marked yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Student</th>
                {subjectNames.map((n) => (
                  <th key={n} className="px-4 py-3">
                    {n}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.student_id}>
                  <td className="px-4 py-3">
                    <p className="font-semibold text-slate-800">{r.full_name}</p>
                    <p className="text-xs text-slate-400">{r.admission_number}</p>
                  </td>
                  {subjectNames.map((n) => {
                    const s = r.subjects.find((x) => x.subject_name === n);
                    return (
                      <td key={n} className={`px-4 py-3 ${s?.short ? "font-bold text-rose-700" : "text-slate-700"}`}>
                        {s ? `${s.percent}%` : "—"}
                        {s && <span className="block text-[11px] font-normal text-slate-400">{s.attended}/{s.held}</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-slate-500">Red: below 75% — usually not allowed to write that subject&apos;s semester exam.</p>
    </div>
  );
}

function SubjectAttendancePage() {
  const { token } = useAuth();
  const [tab, setTab] = useState("mark");
  const [subjects, reload, state] = useLoad(() => apiRequest("/subject-attendance/my-subjects", { token }), [token]);

  return (
    <div className="space-y-6">
      <PageHeader title="Subject attendance" subtitle="Attendance per subject and period, and each student's percentage per subject (75% rule)." />
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1 text-sm font-semibold sm:w-fit">
        {[
          ["mark", "Mark attendance"],
          ["summary", "Summary"],
        ].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={`rounded-md px-4 py-1.5 ${tab === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>
            {label}
          </button>
        ))}
      </div>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="your subjects" />
      ) : tab === "mark" ? (
        <MarkTab token={token} subjects={subjects} />
      ) : (
        <SummaryTab token={token} subjects={subjects} />
      )}
    </div>
  );
}

export default SubjectAttendancePage;

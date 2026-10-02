import { useEffect, useState } from "react";

import { errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, Stat, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

function SemesterPromotionPage() {
  const { token } = useAuth();
  const [classes, , classesState] = useLoad(() => apiRequest("/classes", { token }), [token]);
  const [classId, setClassId] = useState("");
  const [rules, setRules] = useState({ max_backlogs: "", min_attendance: "75" });
  const params = {
    class_id: classId,
    ...(rules.max_backlogs !== "" && { max_backlogs: rules.max_backlogs }),
    ...(rules.min_attendance !== "" && { min_attendance: rules.min_attendance }),
  };
  const [plan, reload, state] = useLoad(() => (classId ? apiRequest("/promotion/semester/plan", { token, params }) : Promise.resolve(null)), [token, classId, rules.max_backlogs, rules.min_attendance]);
  const [detain, setDetain] = useState([]);
  const [target, setTarget] = useState("");
  const [action, setAction] = useState("promote");
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!classId && classes?.length) setClassId((classes.find((c) => c.semester) ?? classes[0]).id);
  }, [classes, classId]);

  useEffect(() => {
    // Students breaking the rules start ticked for detention.
    setDetain(plan ? plan.students.filter((s) => !s.eligible).map((s) => s.id) : []);
    setTarget(plan?.detain_targets[0]?.class_id ?? "");
  }, [plan]);

  async function run() {
    const what = action === "graduate" ? "pass out" : `move to semester ${plan.semester + 1}`;
    if (!window.confirm(`${plan.students.length - detain.length} students will ${what}; ${detain.length} detained. Continue?`)) return;
    setRunning(true);
    setMessage(null);
    setError(null);
    try {
      const r = await apiRequest("/promotion/semester", {
        method: "POST",
        token,
        body: { class_id: classId, action, detain, detain_to_class_id: detain.length ? target : null },
      });
      setMessage(
        action === "graduate"
          ? `${r.graduated} students passed out, ${r.detained} detained.`
          : `${r.promoted} students moved to semester ${r.to_semester}, ${r.detained} detained. ${r.subjects_added} semester ${r.to_semester} subjects added; assign their faculty in Batches & Subjects.`,
      );
      setClassId(action === "graduate" ? "" : classId);
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't promote the batch."));
    } finally {
      setRunning(false);
    }
  }

  const toggle = (id) => setDetain(detain.includes(id) ? detain.filter((x) => x !== id) : [...detain, id]);
  return (
    <div className="space-y-6">
      <PageHeader title="Promote to next semester" subtitle="Check backlogs and attendance, detain students who break the rules, and move the batch up a semester." />
      {classesState !== "ready" ? (
        <LoadState state={classesState} what="batches" />
      ) : (
        <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <label className="text-sm font-medium text-slate-700">
            Batch
            <select value={classId} onChange={(e) => setClassId(e.target.value)} className={INPUT}>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} - {c.section} · {c.semester ? `Sem ${c.semester}` : "no semester"} ({c.academic_year})
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Max backlogs allowed
            <input type="number" min="0" placeholder="No limit" value={rules.max_backlogs} onChange={(e) => setRules({ ...rules, max_backlogs: e.target.value })} className={INPUT} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Min attendance %
            <input type="number" min="0" max="100" placeholder="No limit" value={rules.min_attendance} onChange={(e) => setRules({ ...rules, min_attendance: e.target.value })} className={INPUT} />
          </label>
        </div>
      )}
      <Notice message={message} error={error} />
      {classId && state !== "ready" && <LoadState state={state} onRetry={reload} what="the batch" />}
      {plan && state === "ready" && (
        <>
          {plan.semester === null && (
            <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">This batch has no semester set. Edit it in Batches & Subjects first.</p>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Students" value={plan.students.length} />
            <Stat label="Eligible" value={plan.students.filter((s) => s.eligible).length} tone="emerald" />
            <Stat label="Detained (ticked)" value={detain.length} tone="rose" />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Detain</th>
                  <th className="px-3 py-2">Student</th>
                  <th className="px-3 py-2 text-center">Backlogs</th>
                  <th className="px-3 py-2 text-center">Attendance</th>
                  <th className="px-3 py-2">Rule check</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {plan.students.map((s) => (
                  <tr key={s.id} className={detain.includes(s.id) ? "bg-rose-50/60" : ""}>
                    <td className="px-3 py-2">
                      <input type="checkbox" aria-label={`Detain ${s.full_name}`} checked={detain.includes(s.id)} onChange={() => toggle(s.id)} className="rounded border-slate-300 text-rose-600" />
                    </td>
                    <td className="px-3 py-2">
                      <p className="font-medium text-slate-900">{s.full_name}</p>
                      <p className="text-xs text-slate-500">{s.admission_number}</p>
                    </td>
                    <td className={`px-3 py-2 text-center font-semibold ${s.backlogs ? "text-rose-700" : "text-slate-600"}`}>{s.backlogs}</td>
                    <td className="px-3 py-2 text-center text-slate-700">{s.attendance === null ? "—" : `${s.attendance}%`}</td>
                    <td className="px-3 py-2 text-xs">
                      {s.eligible ? <span className="font-semibold text-emerald-700">OK</span> : <span className="font-semibold text-rose-700">{s.reasons.join("; ")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {plan.semester !== null && (
            <div className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3 sm:items-end">
              <label className="text-sm font-medium text-slate-700">
                Action
                <select value={action} onChange={(e) => setAction(e.target.value)} className={INPUT}>
                  <option value="promote">Move to semester {plan.semester + 1}</option>
                  <option value="graduate">Pass out (final semester)</option>
                </select>
              </label>
              {detain.length > 0 && (
                <label className="text-sm font-medium text-slate-700">
                  Detained students join
                  <select value={target} onChange={(e) => setTarget(e.target.value)} className={INPUT}>
                    {plan.detain_targets.length === 0 && <option value="">No other semester {plan.semester} batch — create one first</option>}
                    {plan.detain_targets.map((t) => (
                      <option key={t.class_id} value={t.class_id}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <button type="button" disabled={running || (detain.length > 0 && !target)} onClick={run} className={PRIMARY}>
                {running ? "Working…" : action === "graduate" ? "Pass out batch" : `Promote to semester ${plan.semester + 1}`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default SemesterPromotionPage;

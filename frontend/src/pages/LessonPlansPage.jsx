import { useEffect, useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

function bar(percent) {
  return (
    <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-slate-100">
      <span className={`block h-full rounded-full ${percent >= 75 ? "bg-emerald-500" : percent >= 40 ? "bg-amber-500" : "bg-rose-500"}`} style={{ width: `${percent ?? 0}%` }} />
    </span>
  );
}

function Plan({ token, row, onChange }) {
  const [plan, reload, state] = useLoad(() => apiRequest("/lesson-plans", { token, params: { class_id: row.class_id, subject_id: row.subject_id } }), [token, row.class_id, row.subject_id]);
  const [text, setText] = useState("");
  const [unit, setUnit] = useState(1);
  const [error, setError] = useState(null);

  async function act(path, options) {
    setError(null);
    try {
      await apiRequest(path, { token, ...options });
      reload();
      onChange();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  async function add() {
    const topics = text
      .split("\n")
      .map((t) => t.trim())
      .filter(Boolean)
      .map((title) => ({ unit: Number(unit), title }));
    if (!topics.length) return;
    await act("/lesson-plans", { method: "POST", body: { class_id: row.class_id, subject_id: row.subject_id, topics } });
    setText("");
  }

  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="the lesson plan" />;
  const units = [...new Set(plan.topics.map((t) => t.unit))];
  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="font-semibold text-slate-900">
        {row.subject_name} · {row.batch} · {plan.done}/{plan.total} topics ({plan.percent ?? 0}%)
      </h3>
      {units.map((u) => (
        <div key={u}>
          <p className="text-xs font-bold uppercase text-slate-500">Unit {u}</p>
          <ul className="mt-1 divide-y divide-slate-100">
            {plan.topics
              .filter((t) => t.unit === u)
              .map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                  <input type="checkbox" aria-label={`Done: ${t.title}`} checked={Boolean(t.completed_on)} onChange={(e) => act(`/lesson-plans/topics/${t.id}`, { method: "PUT", body: { completed: e.target.checked } })} className="rounded border-slate-300 text-emerald-600" />
                  <span className={`flex-1 ${t.completed_on ? "text-slate-400 line-through" : "text-slate-800"}`}>{t.title}</span>
                  {t.completed_on && <span className="text-xs text-emerald-700">done {t.completed_on}</span>}
                  {!t.completed_on && (
                    <input type="date" aria-label="Planned date" value={t.planned_date ?? ""} onChange={(e) => act(`/lesson-plans/topics/${t.id}`, { method: "PUT", body: { planned_date: e.target.value || null } })} className={`rounded border px-2 py-0.5 text-xs ${t.overdue ? "border-rose-300 text-rose-700" : "border-slate-300"}`} />
                  )}
                  <button type="button" onClick={() => act(`/lesson-plans/topics/${t.id}`, { method: "DELETE" })} className={DANGER}>
                    ✕
                  </button>
                </li>
              ))}
          </ul>
        </div>
      ))}
      <div className="grid gap-2 sm:grid-cols-[6rem_1fr_auto] sm:items-end">
        <label className="text-sm font-medium text-slate-700">
          Unit
          <input type="number" min="1" max="20" value={unit} onChange={(e) => setUnit(e.target.value)} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Topics (one per line)
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={"Normalization\nTransactions"} className={INPUT} />
        </label>
        <button type="button" onClick={add} className={PRIMARY}>
          Add topics
        </button>
      </div>
      <Notice error={error} />
    </div>
  );
}

function LessonPlansPage() {
  const { token } = useAuth();
  const [rows, reload, state] = useLoad(() => apiRequest("/lesson-plans/progress", { token }), [token]);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selected && rows?.length) setSelected(`${rows[0].class_id}|${rows[0].subject_id}`);
  }, [rows, selected]);

  const current = rows?.find((r) => `${r.class_id}|${r.subject_id}` === selected);
  return (
    <div className="space-y-6">
      <PageHeader title="Lesson plans & syllabus" subtitle="Unit-wise topics per subject, ticked off as they're taught. Students see each subject's coverage in the app." />
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="lesson plans" />
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No subjects assigned to batches yet.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <ul className="divide-y divide-slate-100 self-start rounded-xl border border-slate-200 bg-white">
            {rows.map((r) => {
              const key = `${r.class_id}|${r.subject_id}`;
              return (
                <li key={key}>
                  <button type="button" onClick={() => setSelected(key)} className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${selected === key ? "bg-emerald-50" : ""}`}>
                    <div className="flex justify-between gap-2 text-sm">
                      <span className="font-medium text-slate-900">{r.subject_name}</span>
                      <span className="font-semibold text-slate-700">{r.total ? `${r.percent}%` : "no plan"}</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      {r.batch} · {r.teacher_name}
                      {r.overdue > 0 && <span className="font-semibold text-rose-700"> · {r.overdue} behind schedule</span>}
                    </p>
                    {r.total > 0 && bar(r.percent)}
                  </button>
                </li>
              );
            })}
          </ul>
          {current && <Plan key={selected} token={token} row={current} onChange={reload} />}
        </div>
      )}
    </div>
  );
}

export default LessonPlansPage;

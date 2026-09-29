import { useState } from "react";

import { REMARK_CATEGORIES, createRemark, deleteRemark } from "../api/teachingApi";
import { ApiError } from "../lib/apiClient";

const CATEGORY_STYLES = {
  missed_exam: "bg-rose-50 text-rose-700",
  absent_class: "bg-rose-50 text-rose-700",
  homework: "bg-amber-50 text-amber-700",
  behaviour: "bg-amber-50 text-amber-700",
  appreciation: "bg-emerald-50 text-emerald-700",
  other: "bg-slate-100 text-slate-600",
};
export const ALERT_STATUS_LABELS = {
  sent: "SMS sent to parent",
  failed: "SMS failed",
  not_sent: "Parent alert recorded (SMS off)",
};

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

export function RemarkForm({ token, student, subjects, onSaved, onCancel }) {
  const [category, setCategory] = useState(REMARK_CATEGORIES[0].id);
  const [subjectId, setSubjectId] = useState(subjects.length === 1 ? subjects[0].id : "");
  const [note, setNote] = useState("");
  const [remarkDate, setRemarkDate] = useState(todayIsoDate);
  const [notifyParent, setNotifyParent] = useState(REMARK_CATEGORIES[0].alertByDefault);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  function chooseCategory(id) {
    setCategory(id);
    setNotifyParent(REMARK_CATEGORIES.find((c) => c.id === id).alertByDefault);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      const saved = await createRemark(token, {
        student_id: student.id,
        category,
        subject_id: subjectId || null,
        note,
        remark_date: remarkDate,
        notify_parent: notifyParent,
      });
      onSaved(saved);
    } catch (err) {
      setState("error");
      setError(err instanceof ApiError ? err.message : "Couldn't save the remark.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50/40 p-4">
      <p className="text-sm font-semibold text-slate-800">Remark for {student.full_name}</p>
      <div className="flex flex-wrap gap-1.5">
        {REMARK_CATEGORIES.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => chooseCategory(c.id)}
            className={`rounded-full px-3 py-1 text-xs font-semibold ${category === c.id ? "bg-emerald-600 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-100"}`}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {subjects.length > 0 && (
          <div>
            <label htmlFor={`remark-subject-${student.id}`} className="block text-xs font-medium text-slate-600">
              Subject
            </label>
            <select
              id={`remark-subject-${student.id}`}
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="">— None —</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label htmlFor={`remark-date-${student.id}`} className="block text-xs font-medium text-slate-600">
            Date
          </label>
          <input
            id={`remark-date-${student.id}`}
            type="date"
            required
            value={remarkDate}
            onChange={(e) => setRemarkDate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          />
        </div>
        <div className={subjects.length > 0 ? "" : "sm:col-span-2"}>
          <label htmlFor={`remark-note-${student.id}`} className="block text-xs font-medium text-slate-600">
            Note
          </label>
          <input
            id={`remark-note-${student.id}`}
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Unit test 2"
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={notifyParent} onChange={(e) => setNotifyParent(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
        Tell the parent (SMS to primary contact)
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Save remark"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

export function RemarksList({ token, remarks, showStudent = true, onDeleted, emptyText = "No remarks yet." }) {
  const [error, setError] = useState(null);

  async function handleDelete(remark) {
    if (!window.confirm("Delete this remark?")) return;
    setError(null);
    try {
      await deleteRemark(token, remark.id);
      onDeleted?.(remark.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete the remark.");
    }
  }

  if (remarks.length === 0) {
    return <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">{emptyText}</p>;
  }

  return (
    <div className="space-y-2">
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {remarks.map((remark) => (
          <li key={remark.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 text-sm">
              <p className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${CATEGORY_STYLES[remark.category]}`}>{remark.category_label}</span>
                {showStudent && (
                  <span className="font-semibold text-slate-800">
                    {remark.student_name} <span className="font-normal text-slate-400">{remark.admission_number}</span>
                  </span>
                )}
                {remark.subject_name && <span className="text-xs text-slate-500">· {remark.subject_name}</span>}
              </p>
              {remark.note && <p className="mt-1 text-slate-700">{remark.note}</p>}
              <p className="mt-1 text-xs text-slate-400">
                {new Date(remark.remark_date).toLocaleDateString()} · {remark.author_name}
                {remark.alert_status && ` · ${ALERT_STATUS_LABELS[remark.alert_status]}`}
              </p>
            </div>
            {remark.can_delete && (
              <button
                type="button"
                onClick={() => handleDelete(remark)}
                className="self-start rounded-lg px-3 py-1 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50"
              >
                Delete
              </button>
            )}
          </li>
        ))}
      </ul>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
    </div>
  );
}

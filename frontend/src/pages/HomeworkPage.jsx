import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteHomework, fetchHomework, fetchPostingOptions, homeworkAttachment, saveHomework, uploadHomeworkAttachment } from "../api/boardApi";
import { fetchChildren } from "../api/parentApi";
import { openBlob } from "../components/StudentFiles";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const OLDER_DAYS = 60;

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

// Local calendar date as YYYY-MM-DD.
function isoDay(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toLocaleDateString("en-CA");
}

function dueLabel(iso) {
  if (iso === isoDay(0)) return "Due today";
  if (iso === isoDay(1)) return "Due tomorrow";
  const text = new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  return iso < isoDay(0) ? `Was due ${text}` : `Due ${text}`;
}

function HomeworkForm({ token, options, item, defaultClassId, onSaved, onCancel }) {
  const firstClass = options.find((c) => c.id === defaultClassId) ?? options[0];
  const [form, setForm] = useState(() =>
    item
      ? { class_id: item.class_id, subject_id: item.subject_id, title: item.title, details: item.details, due_on: item.due_on, assigned_on: item.assigned_on }
      : { class_id: firstClass?.id ?? "", subject_id: firstClass?.subjects[0]?.id ?? "", title: "", details: "", due_on: isoDay(1) },
  );
  const [file, setFile] = useState(null);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);
  const subjects = options.find((c) => c.id === form.class_id)?.subjects ?? [];

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      let saved = await saveHomework(token, form, item?.id);
      if (file) saved = await uploadHomeworkAttachment(token, saved.id, file);
      onSaved(saved);
    } catch (err) {
      setState("idle");
      setError(errorMessage(err, "Couldn't save the homework."));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-emerald-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">{item ? "Edit homework" : "Give homework"}</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="hw-class" className="block text-sm font-medium text-slate-700">
            Class
          </label>
          <select
            id="hw-class"
            value={form.class_id}
            onChange={(e) => {
              const next = options.find((c) => c.id === e.target.value);
              setForm({ ...form, class_id: e.target.value, subject_id: next?.subjects[0]?.id ?? "" });
            }}
            className={INPUT}
          >
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} - {c.section}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="hw-subject" className="block text-sm font-medium text-slate-700">
            Subject
          </label>
          <select id="hw-subject" required value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className={INPUT}>
            {subjects.length === 0 && <option value="">No subjects set for this class</option>}
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="hw-due" className="block text-sm font-medium text-slate-700">
            Due on
          </label>
          <input id="hw-due" type="date" required min={item ? undefined : isoDay(0)} value={form.due_on} onChange={(e) => setForm({ ...form, due_on: e.target.value })} className={INPUT} />
        </div>
      </div>
      <div>
        <label htmlFor="hw-title" className="block text-sm font-medium text-slate-700">
          Homework
        </label>
        <input id="hw-title" required minLength={3} maxLength={150} placeholder="e.g. Exercise 4.2, questions 1–10" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={INPUT} />
      </div>
      <div>
        <label htmlFor="hw-details" className="block text-sm font-medium text-slate-700">
          Details <span className="font-normal text-slate-400">(optional)</span>
        </label>
        <textarea id="hw-details" rows={3} maxLength={5000} value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} className={INPUT} />
      </div>
      <div>
        <label htmlFor="hw-file" className="block text-sm font-medium text-slate-700">
          Worksheet <span className="font-normal text-slate-400">(PDF or photo, optional)</span>
        </label>
        <input id="hw-file" type="file" accept=".pdf,image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1 w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:font-semibold" />
        {item?.attachment_name && !file && <p className="mt-1 text-xs text-slate-500">Current: {item.attachment_name}. Choose a file to replace it.</p>}
      </div>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={state === "saving" || !form.subject_id} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : item ? "Save changes" : "Give homework"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
          Cancel
        </button>
      </div>
    </form>
  );
}

function HomeworkCard({ item, token, showClass, onEdit, onDeleted }) {
  const [error, setError] = useState(null);

  async function handleDelete() {
    if (!window.confirm(`Delete "${item.title}"?`)) return;
    try {
      await deleteHomework(token, item.id);
      onDeleted(item.id);
    } catch (err) {
      setError(errorMessage(err, "Couldn't delete."));
    }
  }

  async function handleOpen() {
    setError(null);
    try {
      await openBlob(() => homeworkAttachment(token, item.id));
    } catch (err) {
      setError(errorMessage(err, "Couldn't open the file."));
    }
  }

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
            {item.subject_name}
            {showClass && <span className="font-normal normal-case tracking-normal text-slate-500"> · {item.class_name} - {item.section}</span>}
          </p>
          <p className="font-semibold text-slate-900">{item.title}</p>
          {item.details && <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{item.details}</p>}
          <p className="mt-1 text-xs text-slate-400">{item.posted_by_name && `Given by ${item.posted_by_name}`}</p>
        </div>
        {item.can_edit && (
          <div className="flex gap-3 text-sm">
            <button type="button" onClick={() => onEdit(item)} className="font-semibold text-emerald-700 hover:underline">
              Edit
            </button>
            <button type="button" onClick={handleDelete} className="font-semibold text-rose-700 hover:underline">
              Delete
            </button>
          </div>
        )}
      </div>
      {item.attachment_name && (
        <button type="button" onClick={handleOpen} className="mt-2 inline-flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-200">
          📎 {item.attachment_name}
        </button>
      )}
      {error && <p className="mt-1 text-sm text-rose-700">{error}</p>}
    </li>
  );
}

function HomeworkPage() {
  const { token, user } = useAuth();
  const isStaff = user.role === "admin" || user.role === "teacher";
  const [state, setState] = useState("loading");
  const [items, setItems] = useState([]);
  const [options, setOptions] = useState([]);
  const [children, setChildren] = useState([]);
  const [childId, setChildId] = useState(null);
  const [classId, setClassId] = useState("");
  const [older, setOlder] = useState(false);
  const [editing, setEditing] = useState(null);

  // Parents pick a child first; staff load the classes they can post to.
  useEffect(() => {
    if (["parent", "student"].includes(user.role)) {
      fetchChildren(token)
        .then((list) => {
          setChildren(list);
          setChildId(list[0]?.student_id ?? "");
        })
        .catch(() => setState("error"));
    } else if (isStaff) {
      fetchPostingOptions(token)
        .then(setOptions)
        .catch(() => setOptions([]));
    }
  }, [token, user.role, isStaff]);

  const load = useCallback(async () => {
    if (["parent", "student"].includes(user.role) && childId === null) return;
    if (["parent", "student"].includes(user.role) && !childId) {
      setItems([]);
      setState("ready");
      return;
    }
    setState("loading");
    try {
      setItems(
        await fetchHomework(token, {
          class_id: classId || undefined,
          student_id: childId || undefined,
          since: older ? isoDay(-OLDER_DAYS) : undefined,
        }),
      );
      setState("ready");
    } catch (err) {
      setState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token, user.role, childId, classId, older]);

  useEffect(() => {
    load();
  }, [load]);

  const groups = useMemo(() => {
    const byDay = new Map();
    items.forEach((item) => byDay.set(item.due_on, [...(byDay.get(item.due_on) ?? []), item]));
    // Upcoming first (soonest at the top), then past days (most recent first).
    const today = isoDay(0);
    const days = [...byDay.keys()];
    const upcoming = days.filter((d) => d >= today).sort();
    const past = days.filter((d) => d < today).sort().reverse();
    return [...upcoming, ...past].map((day) => ({ day, items: byDay.get(day) }));
  }, [items]);

  const showClass = isStaff || children.length > 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Homework</h2>
          <p className="mt-1 text-sm text-slate-500">
            {isStaff ? "Give homework to your classes. Students and parents are notified." : "Homework from your teachers."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {["parent", "student"].includes(user.role) && children.length > 1 && (
            <select aria-label="Child" value={childId ?? ""} onChange={(e) => setChildId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              {children.map((c) => (
                <option key={c.student_id} value={c.student_id}>
                  {c.full_name} ({c.class_name} - {c.section})
                </option>
              ))}
            </select>
          )}
          {isStaff && options.length > 1 && (
            <select aria-label="Class" value={classId} onChange={(e) => setClassId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="">All my classes</option>
              {options.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} - {c.section}
                </option>
              ))}
            </select>
          )}
          {isStaff && options.length > 0 && editing === null && (
            <button type="button" onClick={() => setEditing("new")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
              + Give homework
            </button>
          )}
        </div>
      </div>

      {editing !== null && (
        <HomeworkForm
          key={editing === "new" ? "new" : editing.id}
          token={token}
          options={options}
          item={editing === "new" ? null : editing}
          defaultClassId={classId}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && (
        <p className="text-sm font-semibold text-rose-700">
          Couldn&apos;t load homework.{" "}
          <button type="button" onClick={load} className="underline">
            Try again
          </button>
        </p>
      )}
      {state === "forbidden" && <p className="text-sm font-semibold text-rose-700">You don&apos;t have access to homework.</p>}
      {state === "ready" && ["parent", "student"].includes(user.role) && children.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No children are linked to your account.</p>
      )}
      {state === "ready" && !(["parent", "student"].includes(user.role) && children.length === 0) && (
        <>
          {groups.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
              {isStaff && options.length === 0 ? "You don't teach any class yet." : "No homework right now. 🎉"}
            </p>
          ) : (
            <div className="space-y-5">
              {groups.map(({ day, items: dayItems }) => (
                <section key={day}>
                  <h3 className={`mb-2 text-sm font-semibold ${day < isoDay(0) ? "text-slate-400" : "text-slate-700"}`}>{dueLabel(day)}</h3>
                  <ul className={`divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white ${day < isoDay(0) ? "opacity-70" : ""}`}>
                    {dayItems.map((item) => (
                      <HomeworkCard
                        key={item.id}
                        item={item}
                        token={token}
                        showClass={showClass}
                        onEdit={(it) => {
                          setEditing(it);
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                        onDeleted={(id) => setItems((list) => list.filter((x) => x.id !== id))}
                      />
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
          {!older && (
            <button type="button" onClick={() => setOlder(true)} className="text-sm font-semibold text-emerald-700 hover:underline">
              Show older homework
            </button>
          )}
        </>
      )}
    </div>
  );
}

export default HomeworkPage;

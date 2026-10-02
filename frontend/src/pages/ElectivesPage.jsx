import { useEffect, useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const EMPTY_OPTION = { subject_id: "", teacher_id: "", seats: 60 };

function NewSlot({ token, classId, subjects, teachers, onCreated }) {
  const [name, setName] = useState("");
  const [options, setOptions] = useState([{ ...EMPTY_OPTION }, { ...EMPTY_OPTION }]);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function setOption(i, change) {
    setOptions(options.map((o, j) => (j === i ? { ...o, ...change } : o)));
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiRequest("/electives", {
        method: "POST",
        token,
        body: { class_id: classId, name, options: options.map((o) => ({ ...o, seats: Number(o.seats) })) },
      });
      setName("");
      setOptions([{ ...EMPTY_OPTION }, { ...EMPTY_OPTION }]);
      onCreated();
    } catch (err) {
      setError(errorMessage(err, "Couldn't create the elective slot."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="font-semibold text-slate-900">New elective slot</h3>
      <label className="block text-sm font-medium text-slate-700">
        Slot name
        <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Professional Elective I" className={INPUT} />
      </label>
      {options.map((o, i) => (
        <div key={i} className="grid gap-2 sm:grid-cols-[2fr_2fr_1fr_auto] sm:items-end">
          <label className="text-sm font-medium text-slate-700">
            Subject {i + 1}
            <select required value={o.subject_id} onChange={(e) => setOption(i, { subject_id: e.target.value })} className={INPUT}>
              <option value="">Choose…</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.code ? ` (${s.code})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Faculty
            <select required value={o.teacher_id} onChange={(e) => setOption(i, { teacher_id: e.target.value })} className={INPUT}>
              <option value="">Choose…</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Seats
            <input type="number" min="1" required value={o.seats} onChange={(e) => setOption(i, { seats: e.target.value })} className={INPUT} />
          </label>
          <button type="button" disabled={options.length <= 2} onClick={() => setOptions(options.filter((_, j) => j !== i))} className={DANGER}>
            Remove
          </button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setOptions([...options, { ...EMPTY_OPTION }])} className={SECONDARY}>
          + Add subject
        </button>
        <button type="submit" disabled={saving} className={PRIMARY}>
          {saving ? "Saving…" : "Create slot"}
        </button>
      </div>
      <Notice error={error} />
    </form>
  );
}

function Slot({ token, group, onChange }) {
  const [error, setError] = useState(null);

  async function act(path, options) {
    setError(null);
    try {
      await apiRequest(path, { token, ...options });
      onChange();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-900">{group.name}</h3>
          <p className={`text-xs font-semibold ${group.is_open ? "text-emerald-700" : "text-slate-500"}`}>
            {group.is_open ? "Open: students can choose in the app" : "Closed"} · {group.not_chosen.length} not chosen yet
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => act(`/electives/${group.id}/open`, { method: "PUT", body: { is_open: !group.is_open } })} className={SECONDARY}>
            {group.is_open ? "Close choices" : "Reopen"}
          </button>
          <button type="button" onClick={() => window.confirm(`Delete ${group.name}? Students' choices are removed.`) && act(`/electives/${group.id}`, { method: "DELETE" })} className={DANGER}>
            Delete
          </button>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {group.options.map((o) => (
          <div key={o.id} className="rounded-lg border border-slate-200 p-3">
            <div className="flex justify-between gap-2">
              <p className="font-medium text-slate-800">{o.subject_name}</p>
              <span className={`text-xs font-bold ${o.taken >= o.seats ? "text-rose-700" : "text-emerald-700"}`}>
                {o.taken}/{o.seats}
              </span>
            </div>
            <p className="text-xs text-slate-500">{o.teacher_name ?? "No faculty"}</p>
            <ul className="mt-2 space-y-0.5 text-sm text-slate-700">
              {o.students.map((s) => (
                <li key={s.student_id} className="flex justify-between">
                  <span>
                    {s.full_name} <span className="text-xs text-slate-400">{s.admission_number}</span>
                  </span>
                  <button type="button" onClick={() => act(`/electives/${group.id}/assign`, { method: "PUT", body: { student_id: s.student_id } })} className="text-xs text-rose-600 hover:underline">
                    remove
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {group.not_chosen.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <p className="mb-2 text-xs font-semibold text-amber-900">Not chosen yet: assign here if needed</p>
          <ul className="grid gap-1 text-sm sm:grid-cols-2">
            {group.not_chosen.map((s) => (
              <li key={s.student_id} className="flex items-center justify-between gap-2">
                <span>
                  {s.full_name} <span className="text-xs text-slate-400">{s.admission_number}</span>
                </span>
                <select
                  aria-label={`Assign ${s.full_name}`}
                  value=""
                  onChange={(e) => act(`/electives/${group.id}/assign`, { method: "PUT", body: { student_id: s.student_id, option_id: e.target.value } })}
                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                >
                  <option value="">Assign…</option>
                  {group.options.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.subject_name}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        </div>
      )}
      <Notice error={error} />
    </div>
  );
}

function ElectivesPage() {
  const { token } = useAuth();
  const [classId, setClassId] = useState("");
  const [base, , baseState] = useLoad(
    async () => {
      const [classes, subjects, teachers] = await Promise.all([
        apiRequest("/classes", { token }),
        apiRequest("/subjects", { token }),
        apiRequest("/teachers", { token }),
      ]);
      return { classes, subjects, teachers };
    },
    [token],
  );
  const [groups, reload, state] = useLoad(() => (classId ? apiRequest("/electives", { token, params: { class_id: classId } }) : Promise.resolve([])), [token, classId]);

  useEffect(() => {
    if (!classId && base?.classes?.length) setClassId(base.classes[0].id);
  }, [base, classId]);

  return (
    <div className="space-y-6">
      <PageHeader title="Electives" subtitle="Offer elective subjects with seats; students choose in the app, first come first served." />
      {baseState !== "ready" ? (
        <LoadState state={baseState} what="batches" />
      ) : (
        <>
          <label className="block max-w-md text-sm font-medium text-slate-700">
            Batch
            <select value={classId} onChange={(e) => setClassId(e.target.value)} className={INPUT}>
              {base.classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} - {c.section}
                  {c.semester ? ` · Sem ${c.semester}` : ""} ({c.academic_year})
                </option>
              ))}
            </select>
          </label>
          {state !== "ready" ? (
            <LoadState state={state} onRetry={reload} what="electives" />
          ) : (
            groups.map((g) => <Slot key={g.id} token={token} group={g} onChange={reload} />)
          )}
          {classId && <NewSlot token={token} classId={classId} subjects={base.subjects} teachers={base.teachers} onCreated={reload} />}
        </>
      )}
    </div>
  );
}

export default ElectivesPage;

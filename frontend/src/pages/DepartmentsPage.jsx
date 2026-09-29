import { useCallback, useEffect, useState } from "react";

import { createDepartment, deleteDepartment, fetchDepartments, fetchTeachers, updateDepartment } from "../api/academicsApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

const EMPTY_FORM = { name: "", code: "", hod_teacher_id: "" };

function DepartmentForm({ token, department, faculty, onSaved, onCancel }) {
  const isEdit = Boolean(department);
  const [form, setForm] = useState(() =>
    department ? { name: department.name, code: department.code, hod_teacher_id: department.hod?.id ?? "" } : EMPTY_FORM,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const body = { ...form, hod_teacher_id: form.hod_teacher_id || null };
    try {
      onSaved(isEdit ? await updateDepartment(token, department.id, body) : await createDepartment(token, body));
    } catch (err) {
      setSaving(false);
      setError(err instanceof ApiError ? err.message : "Couldn't save the department.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">{isEdit ? `Edit ${department.name}` : "Add department"}</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label htmlFor="dept-name" className="block text-sm font-medium text-slate-700">
            Name
          </label>
          <input
            id="dept-name"
            required
            maxLength={150}
            placeholder="e.g. Computer Science & Engineering"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={INPUT_CLASS}
          />
        </div>
        <div>
          <label htmlFor="dept-code" className="block text-sm font-medium text-slate-700">
            Code
          </label>
          <input
            id="dept-code"
            required
            maxLength={20}
            placeholder="e.g. CSE"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
            className={`${INPUT_CLASS} uppercase`}
          />
        </div>
        <div className="sm:col-span-3">
          <label htmlFor="dept-hod" className="block text-sm font-medium text-slate-700">
            Head of department (HOD)
          </label>
          <select id="dept-hod" value={form.hod_teacher_id} onChange={(e) => setForm({ ...form, hod_teacher_id: e.target.value })} className={INPUT_CLASS}>
            <option value="">Not assigned</option>
            {faculty.map((f) => (
              <option key={f.id} value={f.id}>
                {f.full_name}
                {f.designation ? ` — ${f.designation}` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Saving…" : isEdit ? "Save changes" : "Add department"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function DepartmentsPage() {
  const { token } = useAuth();
  const [loadState, setLoadState] = useState("loading");
  const [departments, setDepartments] = useState([]);
  const [faculty, setFaculty] = useState([]);
  const [editing, setEditing] = useState(null); // null | "new" | department
  const [notice, setNotice] = useState(null);
  const [rowError, setRowError] = useState(null);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const [depts, teachers] = await Promise.all([fetchDepartments(token), fetchTeachers(token)]);
      setDepartments(depts);
      setFaculty(teachers.filter((t) => t.status === "active"));
      setLoadState("ready");
    } catch (err) {
      setLoadState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSaved(saved) {
    setNotice(editing === "new" ? `${saved.name} added.` : "Changes saved.");
    setEditing(null);
    await load();
  }

  async function handleDelete(department) {
    setRowError(null);
    if (!window.confirm(`Delete the ${department.name} department?`)) return;
    try {
      await deleteDepartment(token, department.id);
      await load();
    } catch (err) {
      setRowError({ id: department.id, message: err instanceof ApiError ? err.message : "Couldn't delete this department." });
    }
  }

  if (loadState === "forbidden") {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-amber-800">Only college admins can manage departments.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Departments</h2>
          <p className="mt-1 text-sm text-slate-500">Departments, their heads, and how many faculty, batches and students each has.</p>
        </div>
        {editing === null && loadState === "ready" && (
          <button
            type="button"
            onClick={() => {
              setNotice(null);
              setEditing("new");
            }}
            className="self-start rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
          >
            Add department
          </button>
        )}
      </div>

      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}

      {editing !== null && (
        <DepartmentForm
          key={editing === "new" ? "new" : editing.id}
          token={token}
          department={editing === "new" ? null : editing}
          faculty={faculty}
          onSaved={handleSaved}
          onCancel={() => setEditing(null)}
        />
      )}

      {loadState === "loading" && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-6">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-slate-100" />
        </div>
      )}

      {loadState === "error" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load departments.</p>
          <button type="button" onClick={load} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
            Retry
          </button>
        </div>
      )}

      {loadState === "ready" && departments.length === 0 && editing === null && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-600">No departments yet.</p>
          <p className="mt-1 text-sm text-slate-400">Add departments such as CSE, ECE, MBA, then link faculty, batches and subjects to them.</p>
        </div>
      )}

      {loadState === "ready" && departments.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {departments.map((d) => (
            <div key={d.id} className="flex flex-col rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">{d.code}</p>
                  <h3 className="mt-0.5 font-semibold text-slate-900">{d.name}</h3>
                </div>
              </div>
              <p className="mt-2 text-sm text-slate-500">HOD: {d.hod ? <span className="font-medium text-slate-700">{d.hod.full_name}</span> : "Not assigned"}</p>
              <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
                {[
                  ["Faculty", d.faculty_count],
                  ["Batches", d.class_count],
                  ["Students", d.student_count],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 py-2">
                    <dt className="text-xs text-slate-500">{label}</dt>
                    <dd className="text-lg font-bold text-slate-900">{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setNotice(null);
                    setEditing(d);
                  }}
                  className="rounded-lg px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(d)}
                  className="rounded-lg px-3 py-1 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50"
                >
                  Delete
                </button>
              </div>
              {rowError?.id === d.id && <p className="mt-2 text-right text-xs font-medium text-rose-600">{rowError.message}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default DepartmentsPage;

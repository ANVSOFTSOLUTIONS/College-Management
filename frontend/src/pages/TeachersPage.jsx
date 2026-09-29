import { useCallback, useEffect, useState } from "react";

import { createTeacher, fetchDepartments, fetchTeachers, removeTeacher, updateTeacher } from "../api/academicsApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

const EMPTY_FORM = {
  full_name: "",
  email: "",
  phone: "",
  department: "",
  department_id: "",
  designation: "",
  qualification: "",
  employee_code: "",
  joined_on: "",
  password: "",
};

function toForm(teacher) {
  return {
    full_name: teacher.full_name,
    email: teacher.email,
    phone: teacher.phone,
    department: teacher.department,
    department_id: teacher.department_id ?? "",
    designation: teacher.designation ?? "",
    qualification: teacher.qualification,
    employee_code: teacher.employee_code ?? "",
    joined_on: teacher.joined_on ?? "",
    password: "",
  };
}

function Field({ id, label, children }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
    </div>
  );
}

function TeacherForm({ token, teacher, departments, onSaved, onCancel }) {
  const isEdit = Boolean(teacher);
  const [form, setForm] = useState(() => (teacher ? toForm(teacher) : EMPTY_FORM));
  const [saveState, setSaveState] = useState("idle");
  const [error, setError] = useState(null);

  function setField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaveState("saving");
    setError(null);
    const body = {
      ...form,
      department: form.department || "General",
      department_id: form.department_id || null,
      employee_code: form.employee_code || null,
      joined_on: form.joined_on || null,
    };
    if (isEdit && !body.password) delete body.password;
    try {
      const saved = isEdit ? await updateTeacher(token, teacher.id, body) : await createTeacher(token, body);
      onSaved(saved);
    } catch (err) {
      setSaveState("error");
      setError(err instanceof ApiError ? err.message : "Couldn't save this faculty member.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">{isEdit ? `Edit ${teacher.full_name}` : "Add faculty"}</h3>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="teacher-name" label="Full name">
          <input id="teacher-name" required value={form.full_name} onChange={(e) => setField("full_name", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="teacher-email" label="Email (login)">
          <input id="teacher-email" type="email" required value={form.email} onChange={(e) => setField("email", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="teacher-phone" label="Phone">
          <input id="teacher-phone" type="tel" value={form.phone} onChange={(e) => setField("phone", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="teacher-department" label="Department">
          {departments.length ? (
            <select
              id="teacher-department"
              value={form.department_id}
              onChange={(e) => setField("department_id", e.target.value)}
              className={INPUT_CLASS}
            >
              <option value="">Not in a department</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          ) : (
            <input id="teacher-department" placeholder="e.g. Mathematics" value={form.department} onChange={(e) => setField("department", e.target.value)} className={INPUT_CLASS} />
          )}
        </Field>
        <Field id="teacher-designation" label="Designation">
          <input
            id="teacher-designation"
            list="designations"
            placeholder="e.g. Assistant Professor"
            value={form.designation}
            onChange={(e) => setField("designation", e.target.value)}
            className={INPUT_CLASS}
          />
          <datalist id="designations">
            {["Professor", "Associate Professor", "Assistant Professor", "Lecturer", "Lab Assistant", "Principal", "Dean"].map((d) => (
              <option key={d} value={d} />
            ))}
          </datalist>
        </Field>
        <Field id="teacher-qualification" label="Qualification">
          <input id="teacher-qualification" placeholder="e.g. M.Tech, Ph.D" value={form.qualification} onChange={(e) => setField("qualification", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="teacher-code" label="Employee code">
          <input id="teacher-code" value={form.employee_code} onChange={(e) => setField("employee_code", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="teacher-joined" label="Joined on">
          <input id="teacher-joined" type="date" value={form.joined_on} onChange={(e) => setField("joined_on", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="teacher-password" label={isEdit ? "New password (leave blank to keep)" : "Login password"}>
          <input
            id="teacher-password"
            type="password"
            required={!isEdit}
            minLength={8}
            maxLength={72}
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => setField("password", e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={saveState === "saving"}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saveState === "saving" ? "Saving…" : isEdit ? "Save changes" : "Add faculty"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function TeachersPage() {
  const { token } = useAuth();
  const [loadState, setLoadState] = useState("loading");
  const [teachers, setTeachers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [editing, setEditing] = useState(null); // null | "new" | teacher
  const [notice, setNotice] = useState(null);
  const [rowError, setRowError] = useState(null);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const [list, depts] = await Promise.all([fetchTeachers(token), fetchDepartments(token)]);
      setTeachers(list);
      setDepartments(depts);
      setLoadState("ready");
    } catch (err) {
      setLoadState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSaved(saved) {
    setNotice(editing === "new" ? `${saved.full_name} added. They can log in with their email and password.` : "Changes saved.");
    setEditing(null);
    await load();
  }

  async function handleToggleActive(teacher) {
    setRowError(null);
    setNotice(null);
    if (teacher.status === "active" && !window.confirm(`Remove ${teacher.full_name}? They will no longer be able to log in.`)) return;
    try {
      if (teacher.status === "active") await removeTeacher(token, teacher.id);
      else await updateTeacher(token, teacher.id, { status: "active" });
      await load();
    } catch (err) {
      setRowError({ id: teacher.id, message: err instanceof ApiError ? err.message : "Couldn't update this faculty member." });
    }
  }

  if (loadState === "forbidden") {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-amber-800">Only college admins can manage faculty.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Faculty</h2>
          <p className="mt-1 text-sm text-slate-500">Add, edit, or remove faculty and see their departments, batches and subjects.</p>
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
            Add faculty
          </button>
        )}
      </div>

      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}

      {editing !== null && (
        <TeacherForm
          key={editing === "new" ? "new" : editing.id}
          token={token}
          teacher={editing === "new" ? null : editing}
          departments={departments}
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
          <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load faculty.</p>
          <button type="button" onClick={load} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
            Retry
          </button>
        </div>
      )}

      {loadState === "ready" && teachers.length === 0 && editing === null && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-600">No faculty yet.</p>
          <p className="mt-1 text-sm text-slate-400">Add your first faculty member to give them a login.</p>
        </div>
      )}

      {loadState === "ready" && teachers.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Faculty</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Class teacher / mentor of</th>
                <th className="px-4 py-3">Subjects</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {teachers.map((teacher) => (
                <tr key={teacher.id} className={teacher.status === "inactive" ? "bg-slate-50 text-slate-400" : ""}>
                  <td className="px-4 py-3 align-top">
                    <p className="font-semibold text-slate-800">
                      {teacher.full_name}
                      {teacher.status === "inactive" && (
                        <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-600">Removed</span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500">
                      {[teacher.designation, teacher.department, teacher.employee_code, teacher.qualification].filter(Boolean).join(" · ")}
                    </p>
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-slate-600">
                    <p>{teacher.email}</p>
                    {teacher.phone && <p>{teacher.phone}</p>}
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-slate-600">
                    {teacher.class_teacher_of.length ? teacher.class_teacher_of.map((c) => `${c.name} - ${c.section}`).join(", ") : "—"}
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-slate-600">
                    {teacher.subjects.length
                      ? teacher.subjects.map((s) => `${s.subject_name} (${s.class_name}-${s.section})`).join(", ")
                      : "—"}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setNotice(null);
                          setEditing(teacher);
                        }}
                        className="rounded-lg px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleActive(teacher)}
                        className={`rounded-lg px-3 py-1 text-xs font-semibold ring-1 ring-inset ${
                          teacher.status === "active"
                            ? "text-rose-600 ring-rose-200 hover:bg-rose-50"
                            : "text-emerald-700 ring-emerald-200 hover:bg-emerald-50"
                        }`}
                      >
                        {teacher.status === "active" ? "Remove" : "Restore"}
                      </button>
                    </div>
                    {rowError?.id === teacher.id && <p className="mt-2 text-right text-xs font-medium text-rose-600">{rowError.message}</p>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default TeachersPage;

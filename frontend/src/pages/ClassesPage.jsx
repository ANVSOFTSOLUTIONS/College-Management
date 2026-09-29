import { useCallback, useEffect, useState } from "react";

import {
  assignSubjectTeacher,
  createClass,
  createSubject,
  deleteClass,
  deleteSubject,
  fetchClassDetail,
  fetchClasses,
  fetchDepartments,
  fetchSubjects,
  fetchTeachers,
  unassignSubject,
  updateClass,
} from "../api/academicsApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function currentAcademicYear() {
  const now = new Date();
  const start = now.getMonth() >= 5 ? now.getFullYear() : now.getFullYear() - 1; // Indian colleges start in June-August
  return `${start}-${String(start + 1).slice(2)}`;
}

const SUBJECT_TYPES = { theory: "Theory", lab: "Lab / practical", project: "Project", elective: "Elective" };
const SEMESTERS = Array.from({ length: 10 }, (_, i) => i + 1);

function semesterLabel(semester) {
  return semester ? `Sem ${semester}` : null;
}

const EMPTY_SUBJECT = { name: "", code: "", credits: "3", subject_type: "theory", department_id: "", semester: "" };

function SubjectsPanel({ token, subjects, departments, onChanged }) {
  const [form, setForm] = useState(EMPTY_SUBJECT);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function handleAdd(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createSubject(token, {
        ...form,
        credits: Number(form.credits || 0),
        department_id: form.department_id || null,
        semester: form.semester ? Number(form.semester) : null,
      });
      setForm({ ...EMPTY_SUBJECT, department_id: form.department_id, semester: form.semester });
      await onChanged();
    } catch (err) {
      setError(errorMessage(err, "Couldn't add the subject."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(subject) {
    if (!window.confirm(`Delete ${subject.name}? It will be unassigned from every batch.`)) return;
    setError(null);
    try {
      await deleteSubject(token, subject.id);
      await onChanged();
    } catch (err) {
      setError(errorMessage(err, "Couldn't delete the subject."));
    }
  }

  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">Subjects</h3>
      {subjects.length === 0 ? (
        <p className="text-sm text-slate-500">No subjects yet. Add the subjects your college teaches.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {subjects.map((subject) => (
            <span key={subject.id} className="inline-flex items-center gap-2 rounded-full bg-slate-100 py-1 pl-3 pr-1 text-sm text-slate-700">
              {subject.name}
              {subject.code && <span className="text-xs text-slate-400">{subject.code}</span>}
              <span className="text-xs text-emerald-700">
                {[`${subject.credits} cr`, subject.subject_type !== "theory" && SUBJECT_TYPES[subject.subject_type], semesterLabel(subject.semester)]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              <button
                type="button"
                onClick={() => handleDelete(subject)}
                aria-label={`Delete ${subject.name}`}
                className="rounded-full px-2 text-slate-400 hover:bg-rose-100 hover:text-rose-600"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <form onSubmit={handleAdd} className="grid gap-2 sm:grid-cols-6 sm:items-end">
        <div className="sm:col-span-2">
          <label htmlFor="subject-name" className="block text-sm font-medium text-slate-700">
            Subject name
          </label>
          <input
            id="subject-name"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Data Structures"
            className={INPUT_CLASS}
          />
        </div>
        <div>
          <label htmlFor="subject-code" className="block text-sm font-medium text-slate-700">
            Code
          </label>
          <input id="subject-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="CS301" className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="subject-credits" className="block text-sm font-medium text-slate-700">
            Credits
          </label>
          <input
            id="subject-credits"
            type="number"
            min="0"
            max="20"
            step="0.5"
            value={form.credits}
            onChange={(e) => setForm({ ...form, credits: e.target.value })}
            className={INPUT_CLASS}
          />
        </div>
        <div>
          <label htmlFor="subject-type" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select id="subject-type" value={form.subject_type} onChange={(e) => setForm({ ...form, subject_type: e.target.value })} className={INPUT_CLASS}>
            {Object.entries(SUBJECT_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="subject-semester" className="block text-sm font-medium text-slate-700">
            Semester
          </label>
          <select id="subject-semester" value={form.semester} onChange={(e) => setForm({ ...form, semester: e.target.value })} className={INPUT_CLASS}>
            <option value="">Any</option>
            {SEMESTERS.map((n) => (
              <option key={n} value={n}>
                Sem {n}
              </option>
            ))}
          </select>
        </div>
        {departments.length > 0 && (
          <div className="sm:col-span-2">
            <label htmlFor="subject-department" className="block text-sm font-medium text-slate-700">
              Department
            </label>
            <select id="subject-department" value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })} className={INPUT_CLASS}>
              <option value="">Common to all</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          Add subject
        </button>
      </form>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
    </section>
  );
}

function ClassForm({ token, teachers, departments, initial, onSaved, onCancel }) {
  const isEdit = Boolean(initial);
  const [form, setForm] = useState(() => ({
    name: initial?.name ?? "",
    section: initial?.section ?? "",
    academic_year: initial?.academic_year ?? currentAcademicYear(),
    class_teacher_id: initial?.class_teacher.id ?? teachers[0]?.id ?? "",
    department_id: initial?.department_id ?? "",
    program: initial?.program ?? "",
    semester: initial?.semester ? String(initial.semester) : "",
    regulation: initial?.regulation ?? "",
  }));
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function setField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = { ...form, department_id: form.department_id || null, semester: form.semester ? Number(form.semester) : null };
      const saved = isEdit ? await updateClass(token, initial.id, body) : await createClass(token, body);
      onSaved(saved);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the batch."));
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-4">
        <div>
          <label htmlFor="class-department" className="block text-sm font-medium text-slate-700">
            Department
          </label>
          <select id="class-department" value={form.department_id} onChange={(e) => setField("department_id", e.target.value)} className={INPUT_CLASS}>
            <option value="">—</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.code})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="class-program" className="block text-sm font-medium text-slate-700">
            Program
          </label>
          <input
            id="class-program"
            list="programs"
            placeholder="e.g. B.Tech"
            value={form.program}
            onChange={(e) => setField("program", e.target.value)}
            className={INPUT_CLASS}
          />
          <datalist id="programs">
            {["B.Tech", "M.Tech", "B.Sc", "M.Sc", "B.Com", "BBA", "MBA", "BCA", "MCA", "B.Pharm", "Diploma", "Intermediate (MPC)", "Intermediate (BiPC)"].map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </div>
        <div>
          <label htmlFor="class-name" className="block text-sm font-medium text-slate-700">
            Batch name
          </label>
          <input id="class-name" required placeholder="e.g. B.Tech CSE" value={form.name} onChange={(e) => setField("name", e.target.value)} className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="class-section" className="block text-sm font-medium text-slate-700">
            Section
          </label>
          <input id="class-section" required placeholder="A" value={form.section} onChange={(e) => setField("section", e.target.value)} className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="class-year" className="block text-sm font-medium text-slate-700">
            Academic year
          </label>
          <input id="class-year" required placeholder="2026-27" value={form.academic_year} onChange={(e) => setField("academic_year", e.target.value)} className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="class-semester" className="block text-sm font-medium text-slate-700">
            Semester
          </label>
          <select id="class-semester" value={form.semester} onChange={(e) => setField("semester", e.target.value)} className={INPUT_CLASS}>
            <option value="">— (yearly)</option>
            {SEMESTERS.map((n) => (
              <option key={n} value={n}>
                Semester {n}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="class-regulation" className="block text-sm font-medium text-slate-700">
            Regulation
          </label>
          <input id="class-regulation" placeholder="e.g. R23" value={form.regulation} onChange={(e) => setField("regulation", e.target.value)} className={INPUT_CLASS} />
        </div>
        <div>
          <label htmlFor="class-teacher" className="block text-sm font-medium text-slate-700">
            Class teacher / mentor
          </label>
          <select id="class-teacher" required value={form.class_teacher_id} onChange={(e) => setField("class_teacher_id", e.target.value)} className={INPUT_CLASS}>
            {teachers.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.full_name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {saving ? "Saving…" : isEdit ? "Save batch" : "Create batch"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function ClassDetailPanel({ token, classId, subjects, teachers, departments, onChanged, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loadState, setLoadState] = useState("loading");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      setDetail(await fetchClassDetail(token, classId));
      setLoadState("ready");
    } catch {
      setLoadState("error");
    }
  }, [token, classId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAssign(subjectId, teacherId) {
    setError(null);
    try {
      const updated = teacherId
        ? await assignSubjectTeacher(token, classId, subjectId, teacherId)
        : await unassignSubject(token, classId, subjectId);
      setDetail(updated);
      onChanged();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update the subject's faculty."));
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete ${detail.name} - ${detail.section}?`)) return;
    setError(null);
    try {
      await deleteClass(token, classId);
      onChanged();
      onClose();
    } catch (err) {
      setError(errorMessage(err, "Couldn't delete the batch."));
    }
  }

  if (loadState === "loading") {
    return <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  }
  if (loadState === "error") {
    return (
      <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-5 py-4">
        <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load this batch.</p>
        <button type="button" onClick={load} className="rounded-lg bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white">
          Retry
        </button>
      </div>
    );
  }

  const teacherBySubject = Object.fromEntries(detail.subjects.map((s) => [s.subject_id, s.teacher.id]));

  return (
    <section className="space-y-4 rounded-xl border border-emerald-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            {detail.name} - {detail.section} <span className="text-sm font-normal text-slate-400">({detail.academic_year})</span>
          </h3>
          <p className="text-sm text-slate-500">
            {[detail.department_name, detail.program, semesterLabel(detail.semester), detail.regulation].filter(Boolean).join(" · ")}
          </p>
          <p className="text-sm text-slate-500">
            Class teacher: <span className="font-semibold text-slate-700">{detail.class_teacher.full_name}</span> · {detail.student_count} student(s) ·{" "}
            {detail.subjects.reduce((sum, s) => sum + s.credits, 0)} credits
          </p>
        </div>
        <div className="flex gap-2">
          {!editing && (
            <button type="button" onClick={() => setEditing(true)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100">
              Edit batch
            </button>
          )}
          <button type="button" onClick={handleDelete} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50">
            Delete
          </button>
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-100">
            Close
          </button>
        </div>
      </div>

      {editing && (
        <ClassForm
          token={token}
          teachers={teachers}
          departments={departments}
          initial={detail}
          onSaved={(saved) => {
            setDetail(saved);
            setEditing(false);
            onChanged();
          }}
          onCancel={() => setEditing(false)}
        />
      )}

      <div>
        <h4 className="text-sm font-semibold text-slate-700">Subjects &amp; faculty</h4>
        {subjects.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">Add subjects above first, then assign a faculty member to each.</p>
        ) : (
          <div className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200">
            {subjects
              .filter(
                (subject) =>
                  subject.id in teacherBySubject ||
                  ((!subject.semester || !detail.semester || subject.semester === detail.semester) &&
                    (!subject.department_id || !detail.department_id || subject.department_id === detail.department_id)),
              )
              .map((subject) => (
              <div key={subject.id} className="flex flex-col gap-2 px-4 py-2 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-sm font-medium text-slate-700">
                  {subject.name} <span className="text-xs font-normal text-slate-400">{subject.credits} cr</span>
                </span>
                <select
                  aria-label={`Faculty for ${subject.name}`}
                  value={teacherBySubject[subject.id] ?? ""}
                  onChange={(e) => handleAssign(subject.id, e.target.value)}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm sm:w-64"
                >
                  <option value="">— Not assigned —</option>
                  {teachers.map((teacher) => (
                    <option key={teacher.id} value={teacher.id}>
                      {teacher.full_name}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        )}
      </div>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
    </section>
  );
}

function ClassesPage() {
  const { token } = useAuth();
  const [loadState, setLoadState] = useState("loading");
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    try {
      const [classList, subjectList, teacherList, departmentList] = await Promise.all([
        fetchClasses(token),
        fetchSubjects(token),
        fetchTeachers(token),
        fetchDepartments(token),
      ]);
      setClasses(classList);
      setDepartments(departmentList);
      setSubjects(subjectList);
      setTeachers(teacherList.filter((t) => t.status === "active"));
      setLoadState("ready");
    } catch (err) {
      setLoadState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loadState === "loading") {
    return (
      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-6">
        <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-1/4 animate-pulse rounded bg-slate-100" />
      </div>
    );
  }
  if (loadState === "forbidden") {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-amber-800">Only college admins can manage batches and subjects.</p>
      </div>
    );
  }
  if (loadState === "error") {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load batches and subjects.</p>
        <button type="button" onClick={load} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Batches &amp; Subjects</h2>
        <p className="mt-1 text-sm text-slate-500">
          Set up subjects with credits, batches (program, semester, section) with their mentor, and which faculty teaches each subject.
        </p>
      </div>

      <SubjectsPanel token={token} subjects={subjects} departments={departments} onChanged={load} />

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold text-slate-900">Batches</h3>
          <div className="flex flex-wrap items-center gap-2">
            {departments.length > 0 && (
              <select
                aria-label="Filter by department"
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">All departments</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code}
                  </option>
                ))}
              </select>
            )}
            {!creating && teachers.length > 0 && (
              <button type="button" onClick={() => setCreating(true)} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
                Add batch
              </button>
            )}
          </div>
        </div>

        {teachers.length === 0 && <p className="text-sm text-amber-700">Add faculty first — every batch needs a class teacher / mentor.</p>}

        {creating && (
          <ClassForm
            token={token}
            teachers={teachers}
            departments={departments}
            onSaved={async (saved) => {
              setCreating(false);
              await load();
              setSelectedId(saved.id);
            }}
            onCancel={() => setCreating(false)}
          />
        )}

        {classes.length === 0 && !creating ? (
          <p className="text-sm text-slate-500">No batches yet.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {classes.filter((c) => !departmentFilter || c.department_id === departmentFilter).map((classItem) => (
              <button
                key={classItem.id}
                type="button"
                onClick={() => setSelectedId(classItem.id)}
                className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                  selectedId === classItem.id ? "border-emerald-500 bg-emerald-50" : "border-slate-200 hover:bg-slate-50"
                }`}
              >
                <p className="font-semibold text-slate-800">
                  {classItem.name} - {classItem.section}
                </p>
                <p className="text-xs text-slate-500">
                  {[classItem.department_name, classItem.program, semesterLabel(classItem.semester), classItem.regulation].filter(Boolean).join(" · ")}
                </p>
                <p className="text-xs text-slate-500">
                  {classItem.class_teacher_name} · {classItem.student_count} student(s) · {classItem.academic_year}
                </p>
              </button>
            ))}
          </div>
        )}
      </section>

      {selectedId && (
        <ClassDetailPanel
          key={selectedId}
          token={token}
          classId={selectedId}
          subjects={subjects}
          teachers={teachers}
          departments={departments}
          onChanged={load}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}

export default ClassesPage;

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchMyClasses } from "../api/attendanceApi";
import {
  createExam,
  deleteExam,
  fetchClassResults,
  fetchClassBacklogs,
  fetchExams,
  fetchMarkSheet,
  fetchMyPapers,
  fetchReportCard,
  saveMarks,
  setExamPublished,
  updatePaper,
} from "../api/examsApi";
import { fetchTeachingClasses } from "../api/teachingApi";
import { printReportCard } from "../components/ReportCard";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const SMALL = "rounded-lg px-3 py-1 text-xs font-semibold ring-1 ring-inset";

function errorMessage(err, fallback) {
  return err instanceof ApiError || err instanceof Error ? err.message || fallback : fallback;
}

function Loading() {
  return <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />;
}

// --- Marks entry --------------------------------------------------------------

function MarkSheetEditor({ token, paperId, onBack }) {
  const [state, setState] = useState("loading");
  const [sheet, setSheet] = useState(null);
  const [draft, setDraft] = useState({});
  const [saveState, setSaveState] = useState("idle");
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const result = await fetchMarkSheet(token, paperId);
      setSheet(result);
      setDraft(Object.fromEntries(result.rows.map((r) => [r.student_id, { marks: r.marks === null ? "" : String(r.marks), absent: r.is_absent }])));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, paperId]);

  useEffect(() => {
    load();
  }, [load]);

  function set(studentId, change) {
    setSaveState("idle");
    setDraft((prev) => ({ ...prev, [studentId]: { ...prev[studentId], ...change } }));
  }

  async function handleSave() {
    const max = sheet.paper.max_marks;
    const bad = sheet.rows.find((r) => {
      const d = draft[r.student_id];
      return !d.absent && d.marks !== "" && (Number(d.marks) < 0 || Number(d.marks) > max || Number.isNaN(Number(d.marks)));
    });
    if (bad) {
      setSaveState("error");
      setError(`${bad.full_name}: marks must be between 0 and ${max}.`);
      return;
    }
    setSaveState("saving");
    setError(null);
    try {
      const entries = sheet.rows.map((r) => {
        const d = draft[r.student_id];
        return { student_id: r.student_id, is_absent: d.absent, marks: d.absent || d.marks === "" ? null : d.marks };
      });
      const result = await saveMarks(token, paperId, entries);
      setSheet(result);
      setSaveState("saved");
    } catch (err) {
      setSaveState("error");
      setError(errorMessage(err, "Couldn't save marks."));
    }
  }

  if (state === "loading") return <Loading />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load the mark sheet.</p>;

  const { paper } = sheet;
  const entered = Object.values(draft).filter((d) => d.absent || d.marks !== "").length;
  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-emerald-700 hover:underline">
        ← All papers
      </button>
      <div>
        <h3 className="text-lg font-semibold text-slate-900">
          {paper.subject_name} · {paper.class_name} - {paper.section}
        </h3>
        <p className="text-sm text-slate-500">
          {paper.exam_name} · Max {paper.max_marks} · Pass {paper.pass_marks} · {entered}/{sheet.rows.length} entered
        </p>
      </div>
      {!paper.can_enter_marks && <p className="rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-900">Results are published, so marks are locked.</p>}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Student</th>
              <th className="px-4 py-3">Marks (of {paper.max_marks})</th>
              <th className="px-4 py-3">Absent</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sheet.rows.map((row) => {
              const d = draft[row.student_id];
              const fail = !d.absent && d.marks !== "" && Number(d.marks) < paper.pass_marks;
              return (
                <tr key={row.student_id}>
                  <td className="px-4 py-2">
                    <p className="font-semibold text-slate-800">{row.full_name}</p>
                    <p className="text-xs text-slate-400">{row.admission_number}</p>
                  </td>
                  <td className="px-4 py-2">
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      max={paper.max_marks}
                      step="0.5"
                      aria-label={`Marks for ${row.full_name}`}
                      disabled={d.absent || !paper.can_enter_marks}
                      value={d.marks}
                      onChange={(e) => set(row.student_id, { marks: e.target.value })}
                      className={`w-24 rounded-lg border px-3 py-1.5 text-sm disabled:bg-slate-100 ${fail ? "border-rose-300 text-rose-700" : "border-slate-300"}`}
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      type="checkbox"
                      aria-label={`${row.full_name} absent`}
                      disabled={!paper.can_enter_marks}
                      checked={d.absent}
                      onChange={(e) => set(row.student_id, { absent: e.target.checked, marks: e.target.checked ? "" : d.marks })}
                      className="h-4 w-4 rounded border-slate-300 text-rose-600"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {paper.can_enter_marks && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={handleSave} disabled={saveState === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {saveState === "saving" ? "Saving…" : "Save marks"}
          </button>
          {saveState === "saved" && <span className="text-sm font-medium text-emerald-700">Saved. Parents of absent students were alerted.</span>}
          {saveState === "error" && <span className="text-sm font-medium text-rose-600">{error}</span>}
        </div>
      )}
    </div>
  );
}

function EnterMarksTab({ token }) {
  const [state, setState] = useState("loading");
  const [papers, setPapers] = useState([]);
  const [paperId, setPaperId] = useState(null);

  const load = useCallback(async () => {
    try {
      setPapers(await fetchMyPapers(token));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    if (!paperId) load();
  }, [load, paperId]);

  if (paperId) return <MarkSheetEditor token={token} paperId={paperId} onBack={() => setPaperId(null)} />;
  if (state === "loading") return <Loading />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load your papers.</p>;
  if (papers.length === 0) {
    return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No exams waiting for your marks.</p>;
  }
  return (
    <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
      {papers.map((p) => (
        <li key={p.id}>
          <button type="button" onClick={() => setPaperId(p.id)} className="flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between">
            <span>
              <span className="font-semibold text-slate-800">
                {p.subject_name} · {p.class_name} - {p.section}
              </span>
              <span className="block text-xs text-slate-500">{p.exam_name}</span>
            </span>
            <span className={`text-xs font-semibold ${p.entered === p.students ? "text-emerald-700" : "text-amber-700"}`}>
              {p.entered}/{p.students} entered
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// --- Results ------------------------------------------------------------------

function ResultsTab({ token, exams, classes }) {
  const [examId, setExamId] = useState(exams[0]?.id ?? "");
  const exam = exams.find((e) => e.id === examId);
  const examClasses = useMemo(() => {
    const ids = new Set((exam?.papers ?? []).map((p) => p.class_id));
    return classes.filter((c) => ids.has(c.id));
  }, [exam, classes]);
  const [classId, setClassId] = useState("");
  const [state, setState] = useState("idle");
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setClassId(examClasses[0]?.id ?? "");
  }, [examClasses]);

  useEffect(() => {
    if (!examId || !classId) return;
    setState("loading");
    fetchClassResults(token, examId, classId)
      .then((r) => {
        setResults(r);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token, examId, classId]);

  if (exams.length === 0) return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No exams yet.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <select aria-label="Exam" value={examId} onChange={(e) => setExamId(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          {exams.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name} {e.published ? "(published)" : ""}
            </option>
          ))}
        </select>
        <select aria-label="Class" value={classId} onChange={(e) => setClassId(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          {examClasses.length === 0 && <option value="">No classes you can view</option>}
          {examClasses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} - {c.section}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      {state === "loading" && <Loading />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load results.</p>}
      {state === "ready" && results && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-3">Rank</th>
                <th className="px-3 py-3">Student</th>
                {results.subjects.map((s) => (
                  <th key={s} className="px-3 py-3">
                    {s}
                  </th>
                ))}
                <th className="px-3 py-3">Total</th>
                <th className="px-3 py-3">%</th>
                <th className="px-3 py-3">SGPA</th>
                <th className="px-3 py-3">Credits</th>
                <th className="px-3 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[...results.students]
                .sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999) || a.full_name.localeCompare(b.full_name))
                .map((r) => (
                  <tr key={r.student_id}>
                    <td className="px-3 py-2 font-semibold text-slate-700">{r.rank ?? "—"}</td>
                    <td className="px-3 py-2">
                      <p className="font-semibold text-slate-800">{r.full_name}</p>
                      <p className="text-xs text-slate-400">{r.admission_number}</p>
                    </td>
                    {r.papers.map((p) => (
                      <td key={p.subject_name} className={`px-3 py-2 ${p.passed === false ? "font-semibold text-rose-700" : "text-slate-700"}`}>
                        {p.is_absent ? "AB" : p.marks ?? "—"}
                        {p.grade && !p.is_absent && <span className="ml-1 text-xs text-slate-400">{p.grade}</span>}
                      </td>
                    ))}
                    <td className="px-3 py-2 text-slate-700">{r.total}</td>
                    <td className="px-3 py-2 text-slate-700">{r.percentage ?? "—"}</td>
                    <td className={`px-3 py-2 font-semibold ${r.passed === false ? "text-rose-700" : "text-slate-800"}`}>{r.sgpa ?? (r.complete ? "" : "Pending")}</td>
                    <td className="px-3 py-2 text-slate-700">
                      {r.credits_earned}/{r.credits_total}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        onClick={() => printReportCard(() => fetchReportCard(token, examId, r.student_id)).catch((err) => setError(errorMessage(err, "Couldn't open the report card.")))}
                        className="text-xs font-semibold text-emerald-700 hover:underline"
                      >
                        Report card
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
            <tfoot className="bg-slate-50 text-xs text-slate-600">
              <tr>
                <td className="px-3 py-2" />
                <td className="px-3 py-2 font-semibold">Average · Highest · Passed</td>
                {results.subject_stats.map((s) => (
                  <td key={s.subject_name} className="px-3 py-2">
                    {s.average ?? "—"} · {s.highest ?? "—"} · {s.passed}/{s.appeared}
                  </td>
                ))}
                <td colSpan={5} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Exams (admin) ------------------------------------------------------------

function NewExamForm({ token, classes, exams, onCreated, onCancel }) {
  const [form, setForm] = useState({
    name: "",
    term_label: "",
    exam_type: "semester",
    academic_year: String(new Date().getFullYear()),
    start_date: "",
    end_date: "",
    max_marks: "100",
    pass_marks: "40",
    internal_exam_ids: [],
    internal_weight: "",
  });
  const internalExams = exams.filter((e) => e.exam_type === "internal");
  const [classIds, setClassIds] = useState([]);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (classIds.length === 0) {
      setError("Choose at least one batch.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const withInternals = form.exam_type === "semester" && form.internal_exam_ids.length > 0;
      onCreated(
        await createExam(token, {
          ...form,
          start_date: form.start_date || null,
          end_date: form.end_date || null,
          class_ids: classIds,
          internal_exam_ids: withInternals ? form.internal_exam_ids : [],
          internal_weight: withInternals ? Number(form.internal_weight || 0) : 0,
        }),
      );
    } catch (err) {
      setError(errorMessage(err, "Couldn't create the exam."));
      setSaving(false);
    }
  }

  const field = (key, label, props = {}) => (
    <div>
      <label htmlFor={`exam-${key}`} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input id={`exam-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">New exam</h3>
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2">{field("name", "Exam name", { required: true, maxLength: 150, placeholder: "e.g. Semester 3 End Exams" })}</div>
        <div>
          <label htmlFor="exam-type" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select id="exam-type" value={form.exam_type} onChange={(e) => setForm({ ...form, exam_type: e.target.value })} className={INPUT}>
            <option value="semester">Semester-end (counts for CGPA)</option>
            <option value="internal">Internal / mid exam</option>
            <option value="supplementary">Supplementary (backlogs only)</option>
          </select>
        </div>
        {field("term_label", "Semester / term", { maxLength: 50, placeholder: "e.g. Sem 3" })}
        {field("academic_year", "Academic year", { required: true, maxLength: 9 })}
        {field("start_date", "Starts", { type: "date" })}
        {field("end_date", "Ends", { type: "date" })}
        {field("max_marks", "Max marks per subject", { required: true, type: "number", min: "1", step: "0.5" })}
        {field("pass_marks", "Pass marks", { required: true, type: "number", min: "0", step: "0.5" })}
      </div>
      {form.exam_type === "semester" && internalExams.length > 0 && (
        <fieldset className="rounded-lg border border-slate-200 p-3">
          <legend className="px-1 text-sm font-medium text-slate-700">Internal marks (optional)</legend>
          <p className="text-xs text-slate-500">Add the average of these internal exams to the semester-end marks, e.g. internal 30 + semester 70 = 100.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {internalExams.map((e) => {
              const on = form.internal_exam_ids.includes(e.id);
              return (
                <label key={e.id} className={`flex cursor-pointer items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${on ? "bg-sky-600 text-white ring-sky-600" : "text-slate-600 ring-slate-300"}`}>
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={on}
                    onChange={() =>
                      setForm({ ...form, internal_exam_ids: on ? form.internal_exam_ids.filter((x) => x !== e.id) : [...form.internal_exam_ids, e.id] })
                    }
                  />
                  {e.name}
                </label>
              );
            })}
            {form.internal_exam_ids.length > 0 && (
              <label className="ml-2 flex items-center gap-2 text-sm text-slate-700">
                Internal carries
                <input
                  type="number"
                  min="1"
                  max="60"
                  required
                  value={form.internal_weight}
                  onChange={(e) => setForm({ ...form, internal_weight: e.target.value })}
                  className="w-20 rounded-lg border border-slate-300 px-2 py-1"
                  placeholder="30"
                />
                of 100 marks
              </label>
            )}
          </div>
        </fieldset>
      )}
      {form.exam_type === "supplementary" && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Only students with a backlog in a subject appear on its mark sheet. A pass replaces the failed grade in their CGPA.
        </p>
      )}
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Batches</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" onClick={() => setClassIds(classIds.length === classes.length ? [] : classes.map((c) => c.id))} className="rounded-full px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
            {classIds.length === classes.length ? "Clear" : "All batches"}
          </button>
          {classes.map((c) => (
            <label key={c.id} className={`flex cursor-pointer items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${classIds.includes(c.id) ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-600 ring-slate-300"}`}>
              <input type="checkbox" className="sr-only" checked={classIds.includes(c.id)} onChange={() => setClassIds((prev) => (prev.includes(c.id) ? prev.filter((x) => x !== c.id) : [...prev, c.id]))} />
              {c.name} - {c.section}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="text-xs text-slate-400">
        Each subject taught in these batches becomes a paper; change max/pass marks per paper afterwards. Grades use the 10-point scale (O, A+, A, B+, B, C, F)
        and subject credits give each student&apos;s SGPA.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {saving ? "Creating…" : "Create exam"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function ExamCard({ token, exam, onChanged }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState(null);
  const entered = exam.papers.reduce((n, p) => n + p.entered, 0);
  const expected = exam.papers.reduce((n, p) => n + p.students, 0);

  async function run(action, fallback) {
    setError(null);
    try {
      await action();
      await onChanged();
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  }

  return (
    <li className="px-4 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={() => setOpen(!open)} className="text-left">
          <p className="font-semibold text-slate-800">
            {exam.name}
            <span className="ml-2 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700">
              {{ internal: "Internal", supplementary: "Supplementary" }[exam.exam_type] ?? "Semester-end"}
              {exam.internal_weight > 0 && ` · internal ${exam.internal_weight} + external ${100 - exam.internal_weight}`}
            </span>
            <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${exam.published ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
              {exam.published ? "Published" : "Draft"}
            </span>
          </p>
          <p className="text-xs text-slate-500">
            {[exam.term_label, exam.academic_year].filter(Boolean).join(" · ")} · {exam.papers.length} papers · marks {entered}/{expected}
          </p>
        </button>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              (exam.published || entered >= expected || window.confirm(`Only ${entered} of ${expected} marks are entered. Publish anyway?`)) &&
              run(() => setExamPublished(token, exam.id, !exam.published), "Couldn't change publishing.")
            }
            className={`${SMALL} ${exam.published ? "text-amber-700 ring-amber-200 hover:bg-amber-50" : "bg-emerald-600 text-white ring-emerald-600 hover:bg-emerald-700"}`}
          >
            {exam.published ? "Unpublish" : "Publish results"}
          </button>
          <button type="button" onClick={() => window.confirm(`Delete ${exam.name}?`) && run(() => deleteExam(token, exam.id), "Couldn't delete the exam.")} className={`${SMALL} text-rose-600 ring-rose-200 hover:bg-rose-50`}>
            Delete
          </button>
        </div>
      </div>
      {error && <p className="mt-2 text-sm font-medium text-rose-600">{error}</p>}
      {open && (
        <table className="mt-3 min-w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 pr-3">Class</th>
              <th className="py-1 pr-3">Subject</th>
              <th className="py-1 pr-3">Teacher</th>
              <th className="py-1 pr-3">Max / pass</th>
              <th className="py-1 pr-3">Entered</th>
              <th className="py-1" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {exam.papers.map((p) =>
              editing?.id === p.id ? (
                <tr key={p.id}>
                  <td className="py-1.5 pr-3" colSpan={3}>
                    {p.class_name} - {p.section} · {p.subject_name}
                  </td>
                  <td className="py-1.5 pr-3" colSpan={2}>
                    <input aria-label="Max marks" type="number" min="1" step="0.5" value={editing.max_marks} onChange={(e) => setEditing({ ...editing, max_marks: e.target.value })} className="w-20 rounded border border-slate-300 px-2 py-1" /> /{" "}
                    <input aria-label="Pass marks" type="number" min="0" step="0.5" value={editing.pass_marks} onChange={(e) => setEditing({ ...editing, pass_marks: e.target.value })} className="w-20 rounded border border-slate-300 px-2 py-1" />
                  </td>
                  <td className="py-1.5">
                    <button
                      type="button"
                      onClick={() => run(async () => { await updatePaper(token, p.id, { max_marks: editing.max_marks, pass_marks: editing.pass_marks }); setEditing(null); }, "Couldn't update the paper.")}
                      className="font-semibold text-emerald-700 hover:underline"
                    >
                      Save
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={p.id}>
                  <td className="py-1.5 pr-3">
                    {p.class_name} - {p.section}
                  </td>
                  <td className="py-1.5 pr-3">{p.subject_name}</td>
                  <td className="py-1.5 pr-3">{p.teacher_name ?? "—"}</td>
                  <td className="py-1.5 pr-3">
                    {p.max_marks} / {p.pass_marks}
                  </td>
                  <td className={`py-1.5 pr-3 ${p.entered === p.students ? "text-emerald-700" : "text-amber-700"}`}>
                    {p.entered}/{p.students}
                  </td>
                  <td className="py-1.5">
                    {!exam.published && (
                      <button type="button" onClick={() => setEditing({ id: p.id, max_marks: String(p.max_marks), pass_marks: String(p.pass_marks) })} className="font-semibold text-slate-600 hover:underline">
                        Edit
                      </button>
                    )}
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </li>
  );
}

function ExamsTab({ token, exams, classes, reload }) {
  const [creating, setCreating] = useState(false);
  return (
    <div className="space-y-4">
      {!creating && (
        <button type="button" onClick={() => setCreating(true)} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
          New exam
        </button>
      )}
      {creating && (
        <NewExamForm
          token={token}
          classes={classes}
          exams={exams}
          onCreated={async () => {
            setCreating(false);
            await reload();
          }}
          onCancel={() => setCreating(false)}
        />
      )}
      {exams.length === 0 && !creating ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No exams yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {exams.map((exam) => (
            <ExamCard key={exam.id} token={token} exam={exam} onChanged={reload} />
          ))}
        </ul>
      )}
    </div>
  );
}

function BacklogsTab({ token, classes }) {
  const [classId, setClassId] = useState(classes[0]?.id ?? "");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!classId) return;
    setRows(null);
    setError(null);
    fetchClassBacklogs(token, classId)
      .then(setRows)
      .catch((err) => setError(errorMessage(err, "Couldn't load backlogs.")));
  }, [token, classId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <select aria-label="Batch" value={classId} onChange={(e) => setClassId(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} - {c.section}
            </option>
          ))}
        </select>
        <p className="text-sm text-slate-500">Subjects whose latest semester-end or supplementary result is F or AB (published results only).</p>
      </div>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      {!rows && !error && <Loading />}
      {rows && rows.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No backlogs in this batch. 🎉</p>
      )}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Backlog subjects</th>
                <th className="px-4 py-3 text-right">Count</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.student_id}>
                  <td className="px-4 py-3">
                    <p className="font-semibold text-slate-800">{r.full_name}</p>
                    <p className="text-xs text-slate-400">{r.admission_number}</p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      {r.backlogs.map((b) => (
                        <span key={b.subject_name} className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700" title={b.exam_name}>
                          {b.subject_name} ({b.grade})
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-rose-700">{r.backlogs.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// --- Page ---------------------------------------------------------------------

function ExamsPage() {
  const { token, user } = useAuth();
  const isAdmin = user.role === "admin";
  const [state, setState] = useState("loading");
  const [exams, setExams] = useState([]);
  const [resultClasses, setResultClasses] = useState([]);
  const [tab, setTab] = useState(isAdmin ? "exams" : "marks");

  const load = useCallback(async () => {
    try {
      const [examList, classList] = await Promise.all([
        fetchExams(token),
        isAdmin ? fetchMyClasses(token) : fetchTeachingClasses(token).then((list) => list.filter((c) => c.is_class_teacher)),
      ]);
      setExams(examList);
      setResultClasses(classList);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, isAdmin]);

  useEffect(() => {
    load();
  }, [load]);

  const tabs = [
    ...(isAdmin ? [{ id: "exams", label: "Exams" }] : []),
    { id: "marks", label: "Enter marks" },
    ...(isAdmin || resultClasses.length ? [{ id: "results", label: isAdmin ? "Results" : "Class results" }] : []),
    ...(isAdmin || resultClasses.length ? [{ id: "backlogs", label: "Backlogs" }] : []),
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Exams &amp; Marks</h2>
        <p className="mt-1 text-sm text-slate-500">
          {isAdmin ? "Create exams, follow marks entry, and publish results to students and parents." : "Enter marks for your subjects. Marking a student absent alerts their parent."}
        </p>
      </div>
      <div role="tablist" className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1 text-sm font-semibold">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className={`shrink-0 rounded-md px-4 py-1.5 ${tab === t.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
            {t.label}
          </button>
        ))}
      </div>
      {state === "loading" && <Loading />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load exams.</p>}
      {state === "ready" && tab === "exams" && <ExamsTab token={token} exams={exams} classes={resultClasses} reload={load} />}
      {state === "ready" && tab === "marks" && <EnterMarksTab token={token} />}
      {state === "ready" && tab === "results" && <ResultsTab token={token} exams={exams} classes={resultClasses} />}
      {state === "ready" && tab === "backlogs" && <BacklogsTab token={token} classes={resultClasses} />}
    </div>
  );
}

export default ExamsPage;

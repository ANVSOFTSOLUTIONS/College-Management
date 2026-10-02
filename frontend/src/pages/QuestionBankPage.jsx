import { useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiBlob, apiRequest, apiUpload } from "../lib/apiClient";

function QuestionBankPage() {
  const { token, user } = useAuth();
  const [subjects] = useLoad(() => apiRequest("/subjects", { token }), [token]);
  const [subjectId, setSubjectId] = useState("");
  const [papers, reload, state] = useLoad(() => apiRequest("/question-papers", { token, params: { subject_id: subjectId || null } }), [token, subjectId]);
  const [form, setForm] = useState({ subject_id: "", title: "", exam_year: "", regulation: "" });
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function upload(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(form).forEach(([k, v]) => formData.append(k, v));
      formData.append("file", file);
      await apiUpload("/question-papers", { token, formData });
      setMessage("Uploaded. Students of batches with this subject can see it in the app.");
      setForm({ ...form, title: "" });
      setFile(null);
      e.target.reset();
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't upload. Use a PDF or image."));
    } finally {
      setSaving(false);
    }
  }

  async function open(paper) {
    try {
      const blob = await apiBlob(`/question-papers/${paper.id}/file`, { token });
      window.open(URL.createObjectURL(blob), "_blank", "noopener");
    } catch {
      setError("Couldn't open the file.");
    }
  }

  async function remove(paper) {
    if (!window.confirm(`Delete ${paper.title}?`)) return;
    try {
      await apiRequest(`/question-papers/${paper.id}`, { method: "DELETE", token });
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't delete."));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Question bank" subtitle="Previous and model question papers per subject. Students see papers of their batch's subjects in the app." />
      <form onSubmit={upload} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-6 md:items-end">
        <label className="text-sm font-medium text-slate-700 md:col-span-2">
          Subject
          <select required value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className={INPUT}>
            <option value="">Choose…</option>
            {(subjects ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.code ? ` (${s.code})` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700 md:col-span-2">
          Title
          <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Sem 3 regular, Nov 2025" className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Year
          <input value={form.exam_year} onChange={(e) => setForm({ ...form, exam_year: e.target.value })} placeholder="2025" className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Regulation
          <input value={form.regulation} onChange={(e) => setForm({ ...form, regulation: e.target.value })} placeholder="R23" className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700 md:col-span-4">
          File (PDF or image)
          <input required type="file" accept="application/pdf,image/*" onChange={(e) => setFile(e.target.files[0] ?? null)} className={INPUT} />
        </label>
        <button type="submit" disabled={saving || !file} className={`${PRIMARY} md:col-span-2`}>
          {saving ? "Uploading…" : "Upload paper"}
        </button>
      </form>
      <Notice message={message} error={error} />
      <select aria-label="Filter by subject" value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
        <option value="">All subjects</option>
        {(subjects ?? []).map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="question papers" />
      ) : papers.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No papers uploaded yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {papers.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <div>
                <p className="font-medium text-slate-900">{p.title}</p>
                <p className="text-xs text-slate-500">
                  {p.subject_name} {p.exam_year && `· ${p.exam_year}`} {p.regulation && `· ${p.regulation}`} · by {p.uploaded_by_name ?? "—"}
                </p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => open(p)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
                  Open
                </button>
                {(user.role === "admin" || p.uploaded_by_name === user.full_name) && (
                  <button type="button" onClick={() => remove(p)} className={DANGER}>
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default QuestionBankPage;

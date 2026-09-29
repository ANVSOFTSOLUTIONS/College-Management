import { useState } from "react";

import { ADMISSION_DOC_TYPES } from "../api/admissionsApi";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const EMPTY = {
  student_name: "", date_of_birth: "", gender: "", class_applied: "", previous_school: "", address: "",
  father_name: "", father_phone: "", mother_name: "", mother_phone: "", email: "", message: "", website: "",
};
export const MAX_DOCUMENTS = 5;

function Field({ id, label, optional, children }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label} {optional && <span className="font-normal text-slate-400">(optional)</span>}
      </label>
      {children}
    </div>
  );
}

// The admission form, shared by the public apply page and the office's walk-in entry.
// onSubmit(body, documents) where documents is [{ doc_type, file }].
function AdmissionForm({ classes, submitLabel, busy, error, onSubmit, onCancel }) {
  const [form, setForm] = useState(EMPTY);
  const [documents, setDocuments] = useState([]);
  const [docType, setDocType] = useState("birth_certificate");
  const [localError, setLocalError] = useState(null);

  const text = (key, props = {}) => (
    <input id={`adm-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
  );

  function handleSubmit(event) {
    event.preventDefault();
    if (!form.father_name.trim() && !form.mother_name.trim()) {
      setLocalError("Give the father's or mother's name.");
      return;
    }
    if (!form.father_phone.trim() && !form.mother_phone.trim()) {
      setLocalError("Give at least one parent's mobile number.");
      return;
    }
    setLocalError(null);
    onSubmit({ ...form, date_of_birth: form.date_of_birth || null }, documents);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <fieldset className="space-y-4">
        <legend className="text-base font-semibold text-slate-900">Child</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="adm-student_name" label="Child's full name">
            {text("student_name", { required: true, minLength: 2, maxLength: 200 })}
          </Field>
          <Field id="adm-class_applied" label="Class applying for">
            <select id="adm-class_applied" required value={form.class_applied} onChange={(e) => setForm({ ...form, class_applied: e.target.value })} className={INPUT}>
              <option value="">Choose a class</option>
              {classes.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>
          <Field id="adm-date_of_birth" label="Date of birth">
            {text("date_of_birth", { type: "date", required: true, max: new Date().toLocaleDateString("en-CA") })}
          </Field>
          <Field id="adm-gender" label="Gender">
            <select id="adm-gender" value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} className={INPUT}>
              <option value="">—</option>
              <option value="female">Girl</option>
              <option value="male">Boy</option>
              <option value="other">Other</option>
            </select>
          </Field>
          <Field id="adm-previous_school" label="Previous school / college" optional>
            {text("previous_school", { maxLength: 200 })}
          </Field>
          <Field id="adm-address" label="Address" optional>
            {text("address", { maxLength: 500 })}
          </Field>
        </div>
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="text-base font-semibold text-slate-900">Parents</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="adm-father_name" label="Father's name">
            {text("father_name", { maxLength: 200 })}
          </Field>
          <Field id="adm-father_phone" label="Father's mobile">
            {text("father_phone", { type: "tel", inputMode: "numeric", maxLength: 20, placeholder: "10-digit mobile" })}
          </Field>
          <Field id="adm-mother_name" label="Mother's name">
            {text("mother_name", { maxLength: 200 })}
          </Field>
          <Field id="adm-mother_phone" label="Mother's mobile">
            {text("mother_phone", { type: "tel", inputMode: "numeric", maxLength: 20, placeholder: "10-digit mobile" })}
          </Field>
          <Field id="adm-email" label="Email" optional>
            {text("email", { type: "email", maxLength: 255 })}
          </Field>
        </div>
        <p className="text-xs text-slate-500">At least one parent&apos;s name and mobile number is needed. The college will call you on it.</p>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-base font-semibold text-slate-900">
          Documents <span className="text-sm font-normal text-slate-400">(optional, PDF or photo, up to {MAX_DOCUMENTS})</span>
        </legend>
        {documents.length > 0 && (
          <ul className="space-y-1 text-sm">
            {documents.map((d, i) => (
              <li key={i} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-1.5">
                <span className="min-w-0 truncate">
                  <span className="font-medium">{ADMISSION_DOC_TYPES.find((t) => t.id === d.doc_type)?.label}</span> · {d.file.name}
                </span>
                <button type="button" onClick={() => setDocuments(documents.filter((_, j) => j !== i))} className="shrink-0 text-rose-700 hover:underline">
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        {documents.length < MAX_DOCUMENTS && (
          <div className="flex flex-wrap items-center gap-2">
            <select aria-label="Document type" value={docType} onChange={(e) => setDocType(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              {ADMISSION_DOC_TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
            <label className="cursor-pointer rounded-lg px-3 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
              + Attach file
              <input
                type="file"
                accept={docType === "photo" ? "image/jpeg,image/png,image/webp" : ".pdf,image/jpeg,image/png,image/webp"}
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) setDocuments([...documents, { doc_type: docType, file }]);
                  e.target.value = "";
                }}
              />
            </label>
          </div>
        )}
      </fieldset>

      <Field id="adm-message" label="Anything the college should know" optional>
        <textarea id="adm-message" rows={3} maxLength={1000} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className={INPUT} />
      </Field>
      {/* Hidden from people; bots that fill every field give themselves away. */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} className="hidden" />

      {(localError || error) && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{localError || error}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={busy} className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {busy ? "Sending…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

export default AdmissionForm;

import { useCallback, useEffect, useState } from "react";

import { fetchMyClasses } from "../api/attendanceApi";
import {
  createStudent,
  disableStudentLogin,
  enableClassStudentLogins,
  enableStudentLogin,
  fetchStudent,
  fetchStudents,
  markStudentLeft,
  updateStudent,
} from "../api/studentsApi";
import { StudentDocuments, StudentPhoto } from "../components/StudentFiles";
import { RemarksList } from "../components/Remarks";
import StudentImport from "../components/StudentImport";
import { fetchRemarks } from "../api/teachingApi";
import { enableClassParentLogins, enableParentLogin } from "../api/parentApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const RELATIONS = [
  { id: "father", label: "Father" },
  { id: "mother", label: "Mother" },
  { id: "guardian", label: "Guardian" },
];
const EMPTY_GUARDIAN = { full_name: "", phone: "", email: "", occupation: "", relation_label: "" };
const QUOTAS = ["Convener", "Management", "NRI", "Lateral entry", "Spot admission"];
const SOCIAL_CATEGORIES = ["OC", "BC-A", "BC-B", "BC-C", "BC-D", "BC-E", "SC", "ST", "EWS"];

function studentSlip(credentials) {
  return {
    id: credentials.student_id,
    title: credentials.full_name,
    tab: "Student",
    lines: [
      ["College code", credentials.school_code],
      ["Roll number", credentials.admission_number],
      ["Password", credentials.password],
    ],
  };
}

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function Field({ id, label, children, wide }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
    </div>
  );
}

function emptyForm(classId) {
  return {
    admission_number: "",
    full_name: "",
    class_id: classId ?? "",
    date_of_birth: "",
    gender: "",
    blood_group: "",
    admission_date: "",
    address: "",
    email: "",
    phone: "",
    quota: "",
    social_category: "",
    father: null,
    mother: null,
    guardian: null,
    primary_contact: "",
  };
}

function detailToForm(detail) {
  const form = {
    admission_number: detail.admission_number,
    full_name: detail.full_name,
    class_id: detail.class.id,
    date_of_birth: detail.date_of_birth ?? "",
    gender: detail.gender,
    blood_group: detail.blood_group,
    admission_date: detail.admission_date ?? "",
    address: detail.address,
    email: detail.email ?? "",
    phone: detail.phone ?? "",
    quota: detail.quota ?? "",
    social_category: detail.social_category ?? "",
    father: null,
    mother: null,
    guardian: null,
    primary_contact: detail.primary_contact,
  };
  detail.guardians.forEach((g) => {
    form[g.relation] = {
      full_name: g.full_name,
      phone: g.phone,
      email: g.email,
      occupation: g.occupation,
      relation_label: g.relation_label,
    };
  });
  return form;
}

function GuardianFields({ relation, value, onChange, isPrimary, onMakePrimary }) {
  if (value === null) {
    return (
      <button
        type="button"
        onClick={() => onChange({ ...EMPTY_GUARDIAN })}
        className="w-full rounded-lg border border-dashed border-slate-300 px-4 py-3 text-left text-sm font-medium text-slate-500 hover:bg-slate-50"
      >
        + Add {relation.label.toLowerCase()} details
      </button>
    );
  }

  function set(field, fieldValue) {
    onChange({ ...value, [field]: fieldValue });
  }

  const prefix = `guardian-${relation.id}`;
  return (
    <fieldset className="space-y-3 rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between">
        <legend className="text-sm font-semibold text-slate-800">{relation.label}</legend>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-slate-600">
            <input type="radio" name="primary-contact" checked={isPrimary} onChange={onMakePrimary} className="text-emerald-600 focus:ring-emerald-500" />
            Primary contact
          </label>
          <button type="button" onClick={() => onChange(null)} className="text-xs font-semibold text-rose-600 hover:underline">
            Remove
          </button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id={`${prefix}-name`} label="Full name">
          <input id={`${prefix}-name`} required value={value.full_name} onChange={(e) => set("full_name", e.target.value)} className={INPUT_CLASS} />
        </Field>
        {relation.id === "guardian" && (
          <Field id={`${prefix}-relation`} label="Relation to student">
            <input id={`${prefix}-relation`} placeholder="e.g. Grandfather" value={value.relation_label} onChange={(e) => set("relation_label", e.target.value)} className={INPUT_CLASS} />
          </Field>
        )}
        <Field id={`${prefix}-phone`} label="Phone">
          <input id={`${prefix}-phone`} type="tel" value={value.phone} onChange={(e) => set("phone", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id={`${prefix}-email`} label="Email">
          <input id={`${prefix}-email`} type="email" value={value.email} onChange={(e) => set("email", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id={`${prefix}-occupation`} label="Occupation">
          <input id={`${prefix}-occupation`} value={value.occupation} onChange={(e) => set("occupation", e.target.value)} className={INPUT_CLASS} />
        </Field>
      </div>
    </fieldset>
  );
}

function LoginSlips({ slips, onClose }) {
  return (
    <section className="space-y-3 rounded-xl border border-emerald-200 bg-white p-5 print:border-0 print:p-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between print:hidden">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Login slips</h3>
          <p className="text-sm text-amber-700">Print or note these now — passwords are shown only once. Students choose their own at first sign-in.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => window.print()} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
            Print
          </button>
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
            Done
          </button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 print:grid-cols-2">
        {slips.map((slip) => (
          <div key={slip.id} className="break-inside-avoid rounded-lg border border-dashed border-slate-400 p-3 text-sm">
            <p className="font-semibold text-slate-900">{slip.title}</p>
            <p className="mt-1 text-slate-600">
              Website: <span className="font-mono">{window.location.host}</span> → {slip.tab}
            </p>
            {slip.lines.map(([label, value]) => (
              <p key={label} className="text-slate-600">
                {label}: <span className="font-mono font-semibold">{value}</span>
              </p>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function StudentRemarks({ token, studentId }) {
  const [state, setState] = useState("loading");
  const [remarks, setRemarks] = useState([]);

  useEffect(() => {
    fetchRemarks(token, { studentId })
      .then((result) => {
        setRemarks(result);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token, studentId]);

  if (state === "loading") return <div className="h-16 animate-pulse rounded-lg bg-slate-100" />;
  if (state === "error") return <p className="text-sm text-rose-600">Couldn&apos;t load remarks.</p>;
  return (
    <RemarksList
      token={token}
      remarks={remarks}
      showStudent={false}
      emptyText="No remarks from teachers yet."
      onDeleted={(id) => setRemarks((prev) => prev.filter((r) => r.id !== id))}
    />
  );
}

function ParentLoginSection({ token, detail, onDetailChange }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handle(reset) {
    if (reset && !window.confirm("Reset the parent's password? Their current password stops working for all their children.")) return;
    setBusy(true);
    setError(null);
    try {
      const created = await enableParentLogin(token, detail.id, reset);
      setResult(created);
      onDetailChange({ ...detail, parent_login_phone: created.phone });
    } catch (err) {
      setError(errorMessage(err, "Couldn't set up the parent login."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold text-slate-700">Parent login</h4>
      <p className="text-sm text-slate-600">
        {detail.parent_login_phone ? (
          <>
            <span className="font-semibold text-emerald-700">On.</span> The parent signs in with mobile <span className="font-mono">{detail.parent_login_phone}</span> to see
            attendance, messages, and fees.
          </>
        ) : (
          "Off. Uses the primary contact's mobile number; siblings share one parent login."
        )}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => handle(Boolean(detail.parent_login_phone))}
          className="rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60"
        >
          {detail.parent_login_phone ? "Reset parent password" : "Turn on parent login"}
        </button>
      </div>
      {result && (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {result.password ? (
            <>
              {result.parent_name}: mobile <span className="font-mono">{result.phone}</span>, password <span className="font-mono font-semibold">{result.password}</span> — note it now, it
              won&apos;t be shown again.
            </>
          ) : (
            <>Linked to {result.parent_name}&apos;s existing parent login ({result.phone}); they use their current password.</>
          )}
        </p>
      )}
      {error && <p className="mt-2 text-sm font-medium text-rose-600">{error}</p>}
    </div>
  );
}

function StudentLoginSection({ token, detail, onDetailChange }) {
  const [slip, setSlip] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleEnable() {
    if (detail.login_enabled && !window.confirm("Reset the student's password? Their current password stops working.")) return;
    setBusy(true);
    setError(null);
    try {
      setSlip(await enableStudentLogin(token, detail.id));
      onDetailChange({ ...detail, login_enabled: true });
    } catch (err) {
      setError(errorMessage(err, "Couldn't set up the student login."));
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    if (!window.confirm("Turn off this student's login? They won't be able to sign in until you turn it on again.")) return;
    setBusy(true);
    setError(null);
    try {
      await disableStudentLogin(token, detail.id);
      setSlip(null);
      onDetailChange({ ...detail, login_enabled: false });
    } catch (err) {
      setError(errorMessage(err, "Couldn't turn off the student login."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold text-slate-700">Student login</h4>
      <p className="text-sm text-slate-600">
        {detail.login_enabled ? (
          <>
            <span className="font-semibold text-emerald-700">On.</span> The student signs in with college code{" "}
            <span className="font-mono">{detail.school_code}</span> and roll number <span className="font-mono">{detail.admission_number}</span>.
          </>
        ) : (
          "Off. Turn it on to let the student see their attendance, results (SGPA / CGPA), fees, assignments and timetable."
        )}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={handleEnable}
          className="rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60"
        >
          {detail.login_enabled ? "Reset student password" : "Turn on student login"}
        </button>
        {detail.login_enabled && (
          <button
            type="button"
            disabled={busy}
            onClick={handleDisable}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50 disabled:opacity-60"
          >
            Turn off
          </button>
        )}
      </div>
      {slip && (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          College code <span className="font-mono">{slip.school_code}</span>, roll number <span className="font-mono">{slip.admission_number}</span>, password{" "}
          <span className="font-mono font-semibold">{slip.password}</span> — note it now, it won&apos;t be shown again.
        </p>
      )}
      {error && <p className="mt-2 text-sm font-medium text-rose-600">{error}</p>}
    </div>
  );
}

function StudentAccountPanel({ token, detail, onDetailChange, onDocumentsChanged }) {
  const base = `/students/${detail.id}`;

  return (
    <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
      <section className="grid gap-5 sm:grid-cols-2">
        <div>
          <h4 className="mb-3 text-sm font-semibold text-slate-700">Photo</h4>
          <StudentPhoto
            token={token}
            base={base}
            hasPhoto={detail.has_photo}
            name={detail.full_name}
            editable
            onUploaded={(updated) => onDetailChange(updated)}
          />
        </div>
        <p className="self-center text-sm text-slate-500">
          Students sign in with the college code and their roll number; parents with their mobile. Both can see results, fees and attendance, and upload
          the photo and documents.
        </p>
      </section>
      {detail.status === "active" && (
        <section className="grid gap-5 sm:grid-cols-2">
          <StudentLoginSection token={token} detail={detail} onDetailChange={onDetailChange} />
          <ParentLoginSection token={token} detail={detail} onDetailChange={onDetailChange} />
        </section>
      )}
      <section>
        <h4 className="mb-3 text-sm font-semibold text-slate-700">Documents</h4>
        <StudentDocuments token={token} base={base} studentId={detail.id} onChanged={onDocumentsChanged} />
      </section>
      <section>
        <h4 className="mb-3 text-sm font-semibold text-slate-700">Remarks from faculty</h4>
        <StudentRemarks token={token} studentId={detail.id} />
      </section>
    </div>
  );
}

function StudentForm({ token, classes, studentId, defaultClassId, isAdmin, onSaved, onCancel, onDocumentsChanged }) {
  const isEdit = Boolean(studentId);
  const [form, setForm] = useState(() => emptyForm(defaultClassId ?? classes[0]?.id));
  const [status, setStatus] = useState("active");
  const [detail, setDetail] = useState(null);
  const [loadState, setLoadState] = useState(isEdit ? "loading" : "ready");
  const [saveState, setSaveState] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isEdit) return;
    fetchStudent(token, studentId)
      .then((detail) => {
        setForm(detailToForm(detail));
        setStatus(detail.status);
        setDetail(detail);
        setLoadState("ready");
      })
      .catch(() => setLoadState("error"));
  }, [token, studentId, isEdit]);

  function setField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function setGuardian(relation, value) {
    setForm((prev) => {
      const next = { ...prev, [relation]: value };
      if (value && !prev.primary_contact) next.primary_contact = relation;
      if (!value && prev.primary_contact === relation) next.primary_contact = RELATIONS.find((r) => r.id !== relation && prev[r.id])?.id ?? "";
      return next;
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaveState("saving");
    setError(null);
    const body = { ...form, date_of_birth: form.date_of_birth || null, admission_date: form.admission_date || null };
    try {
      const saved = isEdit ? await updateStudent(token, studentId, body) : await createStudent(token, body);
      onSaved(saved, isEdit);
    } catch (err) {
      setSaveState("error");
      setError(errorMessage(err, "Couldn't save the student."));
    }
  }

  async function handleStatusChange() {
    const leaving = status === "active";
    if (leaving && !window.confirm(`Mark ${form.full_name} as left? They'll be removed from class lists and attendance.`)) return;
    setError(null);
    try {
      const saved = leaving ? await markStudentLeft(token, studentId) : await updateStudent(token, studentId, { status: "active" });
      onSaved(saved, true);
    } catch (err) {
      setError(errorMessage(err, "Couldn't update the student's status."));
    }
  }

  if (loadState === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (loadState === "error") {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-800">
        Couldn&apos;t load this student.{" "}
        <button type="button" onClick={onCancel} className="underline">
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
    <form onSubmit={handleSubmit} className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-lg font-semibold text-slate-900">{isEdit ? form.full_name : "Add student"}</h3>
        {isEdit && isAdmin && (
          <button
            type="button"
            onClick={handleStatusChange}
            className={`self-start rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ring-inset ${
              status === "active" ? "text-rose-600 ring-rose-200 hover:bg-rose-50" : "text-emerald-700 ring-emerald-200 hover:bg-emerald-50"
            }`}
          >
            {status === "active" ? "Mark as left" : "Restore student"}
          </button>
        )}
      </div>

      <section className="grid gap-3 sm:grid-cols-3">
        <Field id="student-admission" label="Roll number / Hall ticket no.">
          <input id="student-admission" required value={form.admission_number} onChange={(e) => setField("admission_number", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-name" label="Full name" wide>
          <input id="student-name" required value={form.full_name} onChange={(e) => setField("full_name", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-class" label="Batch">
          <select id="student-class" required value={form.class_id} onChange={(e) => setField("class_id", e.target.value)} className={INPUT_CLASS}>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} - {c.section}
              </option>
            ))}
          </select>
        </Field>
        <Field id="student-dob" label="Date of birth">
          <input id="student-dob" type="date" value={form.date_of_birth} onChange={(e) => setField("date_of_birth", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-gender" label="Gender">
          <select id="student-gender" value={form.gender} onChange={(e) => setField("gender", e.target.value)} className={INPUT_CLASS}>
            <option value="">—</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field id="student-blood" label="Blood group">
          <input id="student-blood" maxLength={5} placeholder="e.g. B+" value={form.blood_group} onChange={(e) => setField("blood_group", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-admitted" label="Admission date">
          <input id="student-admitted" type="date" value={form.admission_date} onChange={(e) => setField("admission_date", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-email" label="Student email">
          <input id="student-email" type="email" value={form.email} onChange={(e) => setField("email", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-phone" label="Student mobile">
          <input id="student-phone" type="tel" maxLength={15} value={form.phone} onChange={(e) => setField("phone", e.target.value)} className={INPUT_CLASS} />
        </Field>
        <Field id="student-quota" label="Admission quota">
          <input
            id="student-quota"
            list="quotas"
            maxLength={20}
            placeholder="e.g. Convener"
            value={form.quota}
            onChange={(e) => setField("quota", e.target.value)}
            className={INPUT_CLASS}
          />
          <datalist id="quotas">
            {QUOTAS.map((q) => (
              <option key={q} value={q} />
            ))}
          </datalist>
        </Field>
        <Field id="student-category" label="Social category">
          <select id="student-category" value={form.social_category} onChange={(e) => setField("social_category", e.target.value)} className={INPUT_CLASS}>
            <option value="">Not set</option>
            {SOCIAL_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field id="student-address" label="Address" wide>
          <input id="student-address" value={form.address} onChange={(e) => setField("address", e.target.value)} className={INPUT_CLASS} />
        </Field>
      </section>

      <section className="space-y-3">
        <h4 className="text-sm font-semibold text-slate-700">Parents &amp; guardian</h4>
        {RELATIONS.map((relation) => (
          <GuardianFields
            key={relation.id}
            relation={relation}
            value={form[relation.id]}
            onChange={(value) => setGuardian(relation.id, value)}
            isPrimary={form.primary_contact === relation.id}
            onMakePrimary={() => setField("primary_contact", relation.id)}
          />
        ))}
        <p className="text-xs text-slate-400">The primary contact receives alerts and fee reminders.</p>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={saveState === "saving"}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saveState === "saving" ? "Saving…" : isEdit ? "Save changes" : "Add student"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
    {isEdit && detail && (
      <StudentAccountPanel token={token} detail={detail} onDetailChange={setDetail} onDocumentsChanged={onDocumentsChanged} />
    )}
    </div>
  );
}

function StudentsPage() {
  const { token, user } = useAuth();
  const isAdmin = user.role === "admin";

  const [classesState, setClassesState] = useState("loading");
  const [classes, setClasses] = useState([]);
  const [classFilter, setClassFilter] = useState("");
  const [search, setSearch] = useState("");
  const [includeLeft, setIncludeLeft] = useState(false);

  const [listState, setListState] = useState("loading");
  const [students, setStudents] = useState([]);
  const [editing, setEditing] = useState(null); // null | "new" | student id
  const [notice, setNotice] = useState(null);
  const [slips, setSlips] = useState(null);
  const [importing, setImporting] = useState(false);
  const [bulkState, setBulkState] = useState("idle");
  const [studentBulkState, setStudentBulkState] = useState("idle");

  useEffect(() => {
    fetchMyClasses(token)
      .then((result) => {
        setClasses(result);
        setClassesState("ready");
      })
      .catch(() => setClassesState("error"));
  }, [token]);

  const loadStudents = useCallback(async () => {
    setListState("loading");
    try {
      setStudents(await fetchStudents(token, { classId: classFilter, q: search.trim(), includeLeft }));
      setListState("ready");
    } catch {
      setListState("error");
    }
  }, [token, classFilter, search, includeLeft]);

  useEffect(() => {
    const timer = setTimeout(loadStudents, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [loadStudents, search]);

  async function handleBulkParentLogins() {
    const selected = classes.find((c) => c.id === classFilter);
    if (!window.confirm(`Create parent logins for ${selected.name} - ${selected.section}? Uses each student's primary contact mobile.`)) return;
    setBulkState("working");
    setNotice(null);
    try {
      const result = await enableClassParentLogins(token, classFilter);
      const fresh = result.logins.filter((l) => l.password);
      const skipped = result.skipped_without_mobile.length ? ` Skipped (no mobile): ${result.skipped_without_mobile.join(", ")}.` : "";
      setNotice(`${result.logins.length} parent login(s) set up, ${result.logins.length - fresh.length} linked to existing accounts.${skipped}`);
      if (fresh.length) {
        setSlips(
          fresh.map((l) => ({
            id: l.student_id,
            title: `${l.parent_name} (parent of ${l.student_name})`,
            tab: "Parent",
            lines: [
              ["Mobile", l.phone],
              ["Password", l.password],
            ],
          })),
        );
      }
    } catch (err) {
      setNotice(errorMessage(err, "Couldn't create parent logins."));
    } finally {
      setBulkState("idle");
    }
  }

  async function handleBulkStudentLogins() {
    const selected = classes.find((c) => c.id === classFilter);
    if (!window.confirm(`Create student logins for everyone in ${selected.name} - ${selected.section} who doesn't have one yet?`)) return;
    setStudentBulkState("working");
    setNotice(null);
    try {
      const created = await enableClassStudentLogins(token, classFilter);
      setNotice(created.length ? `${created.length} student login(s) created. Print the slips below.` : "Every student in this batch already has a login.");
      if (created.length) setSlips(created.map(studentSlip));
      await loadStudents();
    } catch (err) {
      setNotice(errorMessage(err, "Couldn't create student logins."));
    } finally {
      setStudentBulkState("idle");
    }
  }

  async function handleSaved(saved, wasEdit) {
    setEditing(null);
    setNotice(wasEdit ? `${saved.full_name} updated.` : `${saved.full_name} added to ${saved.class.name} - ${saved.class.section}.`);
    await loadStudents();
  }

  if (classesState === "loading") {
    return <div className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  }
  if (classesState === "error") {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center text-sm font-semibold text-rose-800">
        Couldn&apos;t load batches. Refresh the page to try again.
      </div>
    );
  }
  if (classes.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-600">{isAdmin ? "Create a batch first." : "You're not class teacher / mentor of any batch yet."}</p>
        <p className="mt-1 text-sm text-slate-400">
          {isAdmin ? "Go to Batches & Subjects to add one." : "Only a batch's class teacher can manage its students."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Students</h2>
          <p className="mt-1 text-sm text-slate-500">
            {isAdmin ? "Every student, their logins and their parents' details." : "Students and parents of the batches you mentor."}
          </p>
        </div>
        {editing === null && (
          <div className="flex gap-2 self-start">
            {isAdmin && (
              <button
                type="button"
                onClick={() => setImporting(!importing)}
                className="rounded-lg px-4 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50"
              >
                Import from Excel
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setNotice(null);
                setEditing("new");
              }}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
            >
              Add student
            </button>
          </div>
        )}
      </div>

      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}

      {importing && (
        <StudentImport
          token={token}
          onClose={() => setImporting(false)}
          onImported={async (count) => {
            setImporting(false);
            setNotice(`${count} students imported. Next: choose the batch and create student and parent logins.`);
            await loadStudents();
          }}
        />
      )}

      {slips && <LoginSlips slips={slips} onClose={() => setSlips(null)} />}

      {editing !== null && (
        <StudentForm
          onDocumentsChanged={loadStudents}
          key={editing}
          token={token}
          classes={classes}
          studentId={editing === "new" ? null : editing}
          defaultClassId={classFilter || undefined}
          isAdmin={isAdmin}
          onSaved={handleSaved}
          onCancel={() => setEditing(null)}
        />
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          aria-label="Filter by batch"
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All {isAdmin ? "batches" : "my batches"}</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} - {c.section}
            </option>
          ))}
        </select>
        <input
          type="search"
          aria-label="Search students"
          placeholder="Search name or roll number"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        {classFilter && (
          <button
            type="button"
            onClick={handleBulkStudentLogins}
            disabled={studentBulkState === "working"}
            className="rounded-lg px-3 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60"
          >
            {studentBulkState === "working" ? "Creating…" : "Student logins for batch"}
          </button>
        )}
        {classFilter && (
          <button
            type="button"
            onClick={handleBulkParentLogins}
            disabled={bulkState === "working"}
            className="rounded-lg px-3 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60"
          >
            {bulkState === "working" ? "Creating…" : "Parent logins for batch"}
          </button>
        )}
        {isAdmin && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={includeLeft} onChange={(e) => setIncludeLeft(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
            Show students who left / passed out
          </label>
        )}
      </div>

      {listState === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}

      {listState === "error" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load students.</p>
          <button type="button" onClick={loadStudents} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
            Retry
          </button>
        </div>
      )}

      {listState === "ready" && students.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-600">{search ? "No students match your search." : "No students yet."}</p>
        </div>
      )}

      {listState === "ready" && students.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <p className="border-b border-slate-100 px-4 py-2 text-xs text-slate-500">{students.length} student(s)</p>
          <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Class</th>
                <th className="px-4 py-3">Primary contact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {students.map((student) => (
                <tr
                  key={student.id}
                  onClick={() => {
                    setNotice(null);
                    setEditing(student.id);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  className={`cursor-pointer hover:bg-slate-50 ${student.status !== "active" ? "text-slate-400" : ""}`}
                >
                  <td className="px-4 py-3">
                    <p className="font-semibold text-slate-800">
                      {student.full_name}
                      {student.status !== "active" && (
                        <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-600">
                          {student.status === "graduated" ? "Passed out" : "Left"}
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-slate-400">
                      {student.admission_number}
                    </p>
                    {student.pending_documents > 0 && (
                      <span className="mt-1 inline-block rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                        {student.pending_documents} document(s) to review
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {student.class.name} - {student.class.section}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {student.primary_contact_name ? (
                      <>
                        <p>{student.primary_contact_name}</p>
                        <p className="text-slate-400">{student.primary_contact_phone}</p>
                      </>
                    ) : (
                      "—"
                    )}
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

export default StudentsPage;

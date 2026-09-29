import QRCode from "qrcode";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  addApplicationDocument,
  applicationDocument,
  approveApplication,
  createWalkIn,
  fetchAdmissionSettings,
  fetchApplications,
  fetchNextAdmissionNumber,
  recordApplicationFee,
  rejectApplication,
  saveAdmissionSettings,
} from "../api/admissionsApi";
import { fetchPostingOptions } from "../api/boardApi";
import { formatRupees } from "../api/feesApi";
import AdmissionForm from "../components/AdmissionForm";
import { openBlob } from "../components/StudentFiles";
import { useAuth } from "../context/AuthContext";
import { ApiError, apiRequest } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const TABS = [
  ["new", "New"],
  ["approved", "Approved"],
  ["rejected", "Rejected"],
];

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function formatDate(iso) {
  return iso ? new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
}

function ShareCard({ token, code }) {
  const [open, setOpen] = useState(null);
  const [fee, setFee] = useState("");
  const [savedFee, setSavedFee] = useState(null);
  const [feeMessage, setFeeMessage] = useState(null);
  const [qr, setQr] = useState(null);
  const [copied, setCopied] = useState(false);
  const link = `${window.location.origin}/apply/${code}`;

  useEffect(() => {
    fetchAdmissionSettings(token)
      .then((s) => {
        setOpen(s.open);
        setSavedFee(s.admission_fee);
        setFee(s.admission_fee ? String(s.admission_fee) : "");
      })
      .catch(() => setOpen(null));
    QRCode.toDataURL(link, { width: 360, margin: 1, color: { dark: "#064e3b" } }).then(setQr).catch(() => {});
  }, [token, link]);

  async function toggle() {
    setOpen((await saveAdmissionSettings(token, { open: !open })).open);
  }

  async function saveFee(e) {
    e.preventDefault();
    setFeeMessage(null);
    try {
      const saved = await saveAdmissionSettings(token, { open, admission_fee: Number(fee) || 0 });
      setSavedFee(saved.admission_fee);
      setFeeMessage({ ok: true, text: saved.admission_fee ? "Saved." : "Saved: no application fee." });
    } catch (err) {
      setFeeMessage({ ok: false, text: errorMessage(err, "Couldn't save the fee.") });
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
      {qr && <img src={qr} alt="QR code for the admission form" className="h-28 w-28 self-center rounded-lg border border-slate-200" />}
      <div className="min-w-0 flex-1 space-y-2">
        <p className="font-semibold text-slate-900">Online admission form</p>
        <p className="break-all rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700">{link}</p>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => navigator.clipboard?.writeText(link).then(() => setCopied(true))}
            className="rounded-lg px-3 py-1.5 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50"
          >
            {copied ? "Copied ✓" : "Copy link"}
          </button>
          {qr && (
            <a href={qr} download={`admission-qr-${code}.png`} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
              Download QR
            </a>
          )}
          {open !== null && (
            <button
              type="button"
              onClick={toggle}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${open ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-slate-200 text-slate-700 hover:bg-slate-300"}`}
              aria-pressed={open}
            >
              {open ? "Admissions open · click to close" : "Admissions closed · click to open"}
            </button>
          )}
        </div>
        <p className="text-xs text-slate-500">Share it on WhatsApp or print the QR. It also shows as an &quot;Apply for admission&quot; button on your college website while admissions are open.</p>
        {open !== null && (
          <form onSubmit={saveFee} className="flex flex-wrap items-end gap-2 pt-1">
            <label className="text-sm font-medium text-slate-700">
              Application fee (₹)
              <input type="number" min="0" max="100000" step="1" value={fee} onChange={(e) => setFee(e.target.value)} placeholder="0 = no fee" className={`${INPUT} w-36`} />
            </label>
            <button type="submit" disabled={Number(fee || 0) === savedFee} className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">
              Save fee
            </button>
            {feeMessage && <span className={`text-sm ${feeMessage.ok ? "text-emerald-700" : "text-rose-700"}`}>{feeMessage.text}</span>}
            <p className="w-full text-xs text-slate-500">Parents pay online after applying once online payments are set up under Fees; otherwise at the office.</p>
          </form>
        )}
      </div>
    </section>
  );
}

function Detail({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900">{value}</dd>
    </div>
  );
}

function FeeBadge({ application: a }) {
  const styles = { pending: "bg-amber-100 text-amber-900", paid: "bg-emerald-100 text-emerald-800", waived: "bg-slate-100 text-slate-600" };
  const label = {
    pending: `Fee ${formatRupees(a.fee_amount)} due`,
    paid: `Fee paid${a.fee_method === "online" ? " online" : " at office"}`,
    waived: "Fee waived",
  }[a.fee_status];
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${styles[a.fee_status]}`}>{label}</span>;
}

// Shown once after approving: the parent's new login, to give to them.
function ParentLoginNotice({ approved, onClose }) {
  const login = approved.parent_login;
  return (
    <section role="status" className="space-y-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950">
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold">{approved.student_name} is admitted. Find them under Students.</p>
        <button type="button" onClick={onClose} aria-label="Dismiss" className="text-lg leading-none opacity-60 hover:opacity-100">
          ×
        </button>
      </div>
      {login?.password && (
        <>
          <p>
            Parent login for {login.parent_name}: mobile <span className="font-mono font-semibold">{login.phone}</span>, password{" "}
            <span className="rounded bg-white px-1.5 py-0.5 font-mono font-semibold">{login.password}</span>
          </p>
          <p className="text-xs text-emerald-800">Give these to the parent now; the password isn&apos;t shown again. They choose a new one when they first sign in.</p>
        </>
      )}
      {login && !login.password && <p>{login.parent_name} already has a parent login (mobile {login.phone}); this child was added to it.</p>}
      {approved.parent_login_note && <p className="text-amber-900">{approved.parent_login_note} You can make one from the student&apos;s page.</p>}
    </section>
  );
}

function ApplicationCard({ token, application, classes, onChanged }) {
  const [expanded, setExpanded] = useState(false);
  const [action, setAction] = useState(null); // "approve" | "reject"
  const matching = useMemo(() => classes.filter((c) => c.name === application.class_applied), [classes, application.class_applied]);
  const [approveForm, setApproveForm] = useState({ class_id: "", admission_number: "", admission_date: new Date().toLocaleDateString("en-CA") });
  const [note, setNote] = useState("");
  const [feeRef, setFeeRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function startApprove() {
    setAction("approve");
    setError(null);
    const { admission_number } = await fetchNextAdmissionNumber(token).catch(() => ({ admission_number: "" }));
    setApproveForm((f) => ({ ...f, class_id: matching[0]?.id ?? classes[0]?.id ?? "", admission_number }));
  }

  async function run(fn) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await fn());
      setAction(null);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
    setBusy(false);
  }

  const a = application;
  const phone = a.father_phone || a.mother_phone;
  return (
    <li className="rounded-xl border border-slate-200 bg-white">
      <button type="button" onClick={() => setExpanded(!expanded)} className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left" aria-expanded={expanded}>
        <span>
          <span className="font-semibold text-slate-900">{a.student_name}</span>
          <span className="text-slate-500"> · {a.class_applied}</span>
          <span className="block text-xs text-slate-500">
            {a.application_no} · {formatDate(a.created_at)} · {a.source === "office" ? "Walk-in" : "Online"}
            {a.documents.length > 0 && ` · 📎 ${a.documents.length}`}
          </span>
        </span>
        {a.fee_status !== "none" && <FeeBadge application={a} />}
        <span className="text-sm text-slate-600">{a.father_name || a.mother_name}</span>
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-slate-100 px-4 py-4">
          <dl className="grid gap-3 sm:grid-cols-3">
            <Detail label="Date of birth" value={formatDate(a.date_of_birth)} />
            <Detail label="Gender" value={{ male: "Boy", female: "Girl", other: "Other" }[a.gender]} />
            <Detail label="Previous college" value={a.previous_school} />
            <Detail label="Father" value={[a.father_name, a.father_phone].filter(Boolean).join(" · ")} />
            <Detail label="Mother" value={[a.mother_name, a.mother_phone].filter(Boolean).join(" · ")} />
            <Detail label="Email" value={a.email} />
            <Detail label="Address" value={a.address} />
          </dl>
          {a.message && <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">“{a.message}”</p>}
          {phone && (
            <a href={`tel:${phone}`} className="inline-block rounded-lg px-3 py-1.5 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
              📞 Call {phone}
            </a>
          )}

          <div className="flex flex-wrap gap-2">
            {a.documents.map((d) => (
              <button key={d.id} type="button" onClick={() => openBlob(() => applicationDocument(token, a.id, d.id)).catch(() => setError("Couldn't open the file."))} className="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-200">
                📎 {d.doc_type_label}
              </button>
            ))}
            {a.status === "new" && a.documents.length < 5 && (
              <label className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
                + Add document
                <input type="file" accept=".pdf,image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) run(() => addApplicationDocument(token, a.id, "other", file)); }} />
              </label>
            )}
          </div>

          {a.fee_status === "pending" && (
            <form onSubmit={(e) => { e.preventDefault(); run(() => recordApplicationFee(token, a.id, "paid", feeRef.trim())); }} className="flex flex-wrap items-end gap-2 rounded-lg bg-amber-50 p-3">
              <p className="w-full text-sm font-medium text-amber-900">Application fee of {formatRupees(a.fee_amount)} not paid yet.</p>
              <label className="text-sm font-medium text-slate-700">
                Office receipt no. (optional)
                <input value={feeRef} maxLength={100} onChange={(e) => setFeeRef(e.target.value)} className={`${INPUT} w-44`} />
              </label>
              <button type="submit" disabled={busy} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
                Paid at office
              </button>
              <button type="button" disabled={busy} onClick={() => run(() => recordApplicationFee(token, a.id, "waived"))} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-white disabled:opacity-60">
                Waive
              </button>
            </form>
          )}
          {a.status === "approved" && <p className="text-sm text-emerald-800">Admitted{a.reviewed_by_name ? ` by ${a.reviewed_by_name}` : ""}. The student is under Students.</p>}
          {a.status === "rejected" && <p className="text-sm text-rose-800">Rejected: {a.review_note}</p>}

          {a.status === "new" && action === null && (
            <div className="flex gap-2">
              <button type="button" onClick={startApprove} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
                Approve &amp; admit
              </button>
              <button type="button" onClick={() => setAction("reject")} className="rounded-lg px-4 py-2 text-sm font-semibold text-rose-700 ring-1 ring-inset ring-rose-200 hover:bg-rose-50">
                Reject
              </button>
            </div>
          )}

          {action === "approve" && (
            <form onSubmit={(e) => { e.preventDefault(); run(() => approveApplication(token, a.id, { ...approveForm, admission_number: approveForm.admission_number.trim() || null })); }} className="grid gap-3 rounded-lg bg-emerald-50/60 p-3 sm:grid-cols-4">
              <label className="text-sm font-medium text-slate-700 sm:col-span-2">
                Class
                <select required value={approveForm.class_id} onChange={(e) => setApproveForm({ ...approveForm, class_id: e.target.value })} className={INPUT}>
                  {[...matching, ...classes.filter((c) => c.name !== a.class_applied)].map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} - {c.section}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">
                Admission no.
                <input value={approveForm.admission_number} maxLength={50} onChange={(e) => setApproveForm({ ...approveForm, admission_number: e.target.value })} className={INPUT} placeholder="Next number" />
              </label>
              <label className="text-sm font-medium text-slate-700">
                Admission date
                <input type="date" value={approveForm.admission_date} onChange={(e) => setApproveForm({ ...approveForm, admission_date: e.target.value })} className={INPUT} />
              </label>
              <div className="flex gap-2 sm:col-span-4">
                <button type="submit" disabled={busy} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
                  {busy ? "Admitting…" : "Admit student"}
                </button>
                <button type="button" onClick={() => setAction(null)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
                  Cancel
                </button>
              </div>
            </form>
          )}

          {action === "reject" && (
            <form onSubmit={(e) => { e.preventDefault(); run(() => rejectApplication(token, a.id, note)); }} className="space-y-2 rounded-lg bg-rose-50/60 p-3">
              <label className="block text-sm font-medium text-slate-700">
                Reason
                <input required minLength={3} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. No seats in this class" className={INPUT} />
              </label>
              <div className="flex gap-2">
                <button type="submit" disabled={busy} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-60">
                  Reject
                </button>
                <button type="button" onClick={() => setAction(null)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
                  Cancel
                </button>
              </div>
            </form>
          )}
          {error && <p className="text-sm font-medium text-rose-700">{error}</p>}
        </div>
      )}
    </li>
  );
}

function AdmissionsPage() {
  const { token } = useAuth();
  const [school, setSchool] = useState(null);
  const [classes, setClasses] = useState([]);
  const [tab, setTab] = useState("new");
  const [applications, setApplications] = useState([]);
  const [state, setState] = useState("loading");
  const [walkIn, setWalkIn] = useState(null); // null | "form" | "saving"
  const [walkInError, setWalkInError] = useState(null);
  const [flash, setFlash] = useState(null);
  const [admitted, setAdmitted] = useState(null);

  useEffect(() => {
    apiRequest("/auth/me", { token }).then((me) => setSchool(me.school)).catch(() => {});
    fetchPostingOptions(token).then(setClasses).catch(() => setClasses([]));
  }, [token]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setApplications(await fetchApplications(token));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const counts = Object.fromEntries(TABS.map(([id]) => [id, applications.filter((a) => a.status === id).length]));
  const shown = applications.filter((a) => a.status === tab);
  const classNames = [...new Set(classes.map((c) => c.name))];

  async function handleWalkIn(body, documents) {
    setWalkIn("saving");
    setWalkInError(null);
    try {
      let created = await createWalkIn(token, body);
      for (const doc of documents) created = await addApplicationDocument(token, created.id, doc.doc_type, doc.file);
      setApplications((list) => [created, ...list]);
      setTab("new");
      setWalkIn(null);
    } catch (err) {
      setWalkInError(errorMessage(err, "Couldn't save the enquiry."));
      setWalkIn("form");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Admissions</h2>
          <p className="mt-1 text-sm text-slate-500">Parents apply online; approving an application admits the student with their parents and documents.</p>
        </div>
        {walkIn === null && (
          <button type="button" onClick={() => setWalkIn("form")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
            + Add walk-in enquiry
          </button>
        )}
      </div>

      {school && <ShareCard token={token} code={school.code} />}

      {walkIn !== null && (
        <section className="rounded-xl border border-emerald-200 bg-white p-5">
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Walk-in enquiry</h3>
          <AdmissionForm classes={classNames} submitLabel="Save enquiry" busy={walkIn === "saving"} error={walkInError} onSubmit={handleWalkIn} onCancel={() => setWalkIn(null)} />
        </section>
      )}

      {admitted && <ParentLoginNotice approved={admitted} onClose={() => setAdmitted(null)} />}

      {flash && (
        <p role="status" className={`flex items-center justify-between gap-3 rounded-lg px-4 py-2 text-sm font-medium ${flash.ok ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-700"}`}>
          {flash.text}
          <button type="button" onClick={() => setFlash(null)} aria-label="Dismiss" className="text-lg leading-none opacity-60 hover:opacity-100">
            ×
          </button>
        </p>
      )}

      <div className="flex gap-2" role="tablist">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200"}`}
          >
            {label} {counts[id] > 0 && <span className="ml-1 rounded-full bg-white/20 px-1.5 text-xs">{counts[id]}</span>}
          </button>
        ))}
      </div>

      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load applications.</p>}
      {state === "ready" &&
        (shown.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
            {tab === "new" ? "No new applications. Share the form link above with parents." : `No ${tab} applications.`}
          </p>
        ) : (
          <ul className="space-y-3">
            {shown.map((a) => (
              <ApplicationCard
                key={a.id}
                token={token}
                application={a}
                classes={classes}
                onChanged={(updated) => {
                  setApplications((list) => list.map((x) => (x.id === updated.id ? updated : x)));
                  // Only the approve response carries parent_login / parent_login_note.
                  if (updated.status === "approved" && (updated.parent_login || updated.parent_login_note)) {
                    setFlash(null);
                    setAdmitted(updated);
                  }
                  if (updated.status === "rejected" && a.status === "new") setFlash({ ok: false, text: `${updated.student_name}'s application was rejected.` });
                }}
              />
            ))}
          </ul>
        ))}
    </div>
  );
}

export default AdmissionsPage;

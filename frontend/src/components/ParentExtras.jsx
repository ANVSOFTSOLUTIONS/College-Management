import { useCallback, useEffect, useState } from "react";

import { formatRupees } from "../api/feesApi";
import { applyChildLeave, cancelLeaveRequest, fetchMyLeaveRequests, reportOfflinePayment } from "../api/parentApi";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const OFFLINE_METHODS = [
  { id: "upi", label: "UPI (PhonePe, GPay, Paytm…)" },
  { id: "bank_transfer", label: "Bank transfer" },
  { id: "cash", label: "Cash at the college office" },
  { id: "cheque", label: "Cheque" },
];
const CLAIM_STATUS = {
  submitted: ["Waiting for college to check", "bg-amber-50 text-amber-800"],
  approved: ["Confirmed", "bg-emerald-50 text-emerald-700"],
  rejected: ["Not confirmed", "bg-rose-50 text-rose-700"],
};

function errorMessage(err, fallback) {
  return err instanceof ApiError || err instanceof Error ? err.message || fallback : fallback;
}

function today() {
  return new Date().toLocaleDateString("en-CA");
}

// "I paid another way": the parent reports a payment; the office checks and confirms it.
export function OfflinePaymentForm({ token, studentId, line, instructions, onSent, onCancel }) {
  const [form, setForm] = useState({ amount: String(line.balance), method: "upi", paidOn: today(), reference: "", note: "" });
  const [proof, setProof] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const needsProof = form.method === "upi" || form.method === "bank_transfer";

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSent(await reportOfflinePayment(token, studentId, line.id, { ...form, proof }));
    } catch (err) {
      setError(errorMessage(err, "Couldn't send. Please try again."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-lg bg-slate-50 p-3">
      {instructions ? (
        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">How to pay the college</p>
          <p className="whitespace-pre-line">{instructions}</p>
        </div>
      ) : (
        <p className="text-xs text-slate-500">Pay at the college office, or ask the college for its UPI ID / bank details.</p>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm font-medium text-slate-700">
          Amount paid (₹)
          <input type="number" required min="1" max={line.balance} step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Paid by
          <select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} className={INPUT}>
            {OFFLINE_METHODS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Date paid
          <input type="date" required max={today()} value={form.paidOn} onChange={(e) => setForm({ ...form, paidOn: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          {form.method === "cheque" ? "Cheque number" : form.method === "cash" ? "Office receipt no. (if any)" : "Transaction / UTR number"}
          <input maxLength={100} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2">
          Screenshot or photo of receipt {needsProof ? "(or give the transaction number)" : "(optional)"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(e) => setProof(e.target.files?.[0] ?? null)}
            className="mt-1 w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2 file:text-sm file:font-semibold"
          />
        </label>
      </div>
      <label className="block text-sm font-medium text-slate-700">
        Note (optional)
        <input maxLength={300} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className={INPUT} />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {busy ? "Sending…" : "Send to college"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
      <p className="text-xs text-slate-500">The college checks its account and confirms. Your receipt then appears here.</p>
    </form>
  );
}

export function OfflinePaymentList({ payments }) {
  if (payments.length === 0) return null;
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold text-slate-700">Payments you reported</h4>
      <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm">
        {payments.map((p) => {
          const [label, style] = CLAIM_STATUS[p.status];
          return (
            <li key={p.id} className="flex flex-col gap-1 px-4 py-2 sm:flex-row sm:items-center sm:justify-between">
              <span>
                {formatRupees(p.amount)} · {p.fee_name} · {p.method_label} · {new Date(p.paid_on).toLocaleDateString("en-IN")}
                {p.reference && ` · Ref ${p.reference}`}
                {p.status === "rejected" && p.review_note && <span className="block text-xs text-rose-700">College says: {p.review_note}</span>}
              </span>
              <span className={`self-start rounded-full px-2.5 py-0.5 text-xs font-semibold ${style}`}>
                {label}
                {p.receipt_number && ` · ${p.receipt_number}`}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const LEAVE_TYPES = [
  ["sick", "Sick"],
  ["family", "Family function"],
  ["casual", "Personal"],
  ["other", "Other"],
];
const LEAVE_STATUS = {
  pending: "bg-amber-50 text-amber-800",
  approved: "bg-emerald-50 text-emerald-700",
  rejected: "bg-rose-50 text-rose-700",
  cancelled: "bg-slate-100 text-slate-500",
};

// Leave for the child; the class teacher approves it and the attendance sheet shows it.
export function ChildLeave({ token, child }) {
  const [leaves, setLeaves] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ leave_type: "sick", from_date: today(), to_date: today(), reason: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const all = await fetchMyLeaveRequests(token);
      setLeaves(all.filter((l) => l.student_id === child.student_id));
    } catch {
      setLeaves([]);
    }
  }, [token, child.student_id]);

  useEffect(() => {
    load();
  }, [load]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await applyChildLeave(token, { ...form, student_id: child.student_id });
      setOpen(false);
      setForm({ leave_type: "sick", from_date: today(), to_date: today(), reason: "" });
      await load();
    } catch (err) {
      setError(errorMessage(err, "Couldn't send the leave request."));
    }
    setBusy(false);
  }

  async function cancel(leave) {
    if (!window.confirm("Cancel this leave request?")) return;
    try {
      await cancelLeaveRequest(token, leave.id);
      await load();
    } catch (err) {
      setError(errorMessage(err, "Couldn't cancel."));
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-slate-900">Leave</h3>
        {!open && (
          <button type="button" onClick={() => setOpen(true)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700">
            Apply leave for {child.full_name.split(" ")[0]}
          </button>
        )}
      </div>
      {open && (
        <form onSubmit={submit} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <label className="text-sm font-medium text-slate-700">
            Reason type
            <select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })} className={INPUT}>
              {LEAVE_TYPES.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            From
            <input type="date" required value={form.from_date} onChange={(e) => setForm({ ...form, from_date: e.target.value, to_date: e.target.value > form.to_date ? e.target.value : form.to_date })} className={INPUT} />
          </label>
          <label className="text-sm font-medium text-slate-700">
            To
            <input type="date" required min={form.from_date} value={form.to_date} onChange={(e) => setForm({ ...form, to_date: e.target.value })} className={INPUT} />
          </label>
          <label className="text-sm font-medium text-slate-700 sm:col-span-3">
            Details for the class teacher
            <input required minLength={3} maxLength={500} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Fever, doctor advised rest" className={INPUT} />
          </label>
          <div className="flex flex-wrap items-center gap-2 sm:col-span-3">
            <button type="submit" disabled={busy} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
              {busy ? "Sending…" : "Send to class teacher"}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
              Cancel
            </button>
          </div>
        </form>
      )}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      {leaves === null && <div className="h-12 animate-pulse rounded-xl bg-slate-100" />}
      {leaves?.length === 0 && !open && <p className="text-sm text-slate-500">No leave requests.</p>}
      {leaves?.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm">
          {leaves.map((l) => (
            <li key={l.id} className="flex flex-col gap-1 px-4 py-2 sm:flex-row sm:items-center sm:justify-between">
              <span>
                {l.leave_type_label} · {new Date(l.from_date).toLocaleDateString("en-IN")}
                {l.days > 1 && ` to ${new Date(l.to_date).toLocaleDateString("en-IN")} (${l.days} days)`}
                <span className="block text-xs text-slate-500">{l.reason}</span>
                {l.review_note && <span className="block text-xs text-slate-600">Teacher: {l.review_note}</span>}
              </span>
              <span className="flex items-center gap-2">
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${LEAVE_STATUS[l.status]}`}>{l.status}</span>
                {l.can_cancel && (
                  <button type="button" onClick={() => cancel(l)} className="text-xs font-semibold text-rose-600 hover:underline">
                    Cancel
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

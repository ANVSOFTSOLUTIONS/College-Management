import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import { ApiError, apiRequest } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const PURPOSES = [
  ["subscription", "Monthly subscription"],
  ["pro_templates", "Pro templates"],
  ["setup", "Setup"],
  ["other", "Other"],
];
const METHODS = [
  ["bank", "Bank transfer"],
  ["upi", "UPI"],
  ["cash", "Cash"],
  ["cheque", "Cheque"],
];

function rupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function monthLabel(month, long = false) {
  return new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", long ? { month: "long", year: "numeric" } : { month: "short" });
}

function Tile({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

// Earnings per month: one series, one colour; hover or tap a bar for its figures.
function EarningsChart({ months }) {
  const [active, setActive] = useState(null);
  const shown = months[active ?? months.length - 1];
  const max = Math.max(1, ...months.map((m) => m.amount));
  return (
    <div>
      <p className="mb-3 text-sm text-slate-600" aria-live="polite">
        <span className="font-semibold text-slate-900">{monthLabel(shown.month, true)}</span> · {rupees(shown.amount)} received
        {shown.new_schools > 0 && ` · ${shown.new_schools} new college${shown.new_schools === 1 ? "" : "s"}`}
      </p>
      <div className="flex h-40 items-end gap-1.5 border-b border-slate-300" onMouseLeave={() => setActive(null)}>
        {months.map((m, i) => (
          <button
            key={m.month}
            type="button"
            aria-label={`${monthLabel(m.month, true)}: ${rupees(m.amount)}`}
            onMouseEnter={() => setActive(i)}
            onFocus={() => setActive(i)}
            onClick={() => setActive(i)}
            className="flex h-full flex-1 items-end justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <span
              className={`w-full max-w-9 rounded-t ${i === (active ?? months.length - 1) ? "bg-emerald-700" : "bg-emerald-500"}`}
              style={{ height: m.amount ? `${Math.max((m.amount / max) * 100, 2)}%` : "3px", opacity: m.amount ? 1 : 0.25 }}
            />
          </button>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5">
        {months.map((m) => (
          <span key={m.month} className="flex-1 text-center text-[10px] text-slate-500">
            {monthLabel(m.month)}
          </span>
        ))}
      </div>
    </div>
  );
}

function RecordPayment({ token, schools, onSaved }) {
  const empty = { school_id: "", amount: "", paid_on: new Date().toLocaleDateString("en-CA"), purpose: "subscription", method: "bank", note: "" };
  const [form, setForm] = useState(empty);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      await apiRequest("/super-admin/payments", { method: "POST", token, body: form });
      setForm({ ...empty, school_id: form.school_id });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save the payment.");
    }
    setState("idle");
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-6">
      <h3 className="font-semibold text-slate-900 sm:col-span-6">Record a payment from a college</h3>
      <label className="text-sm font-medium text-slate-700 sm:col-span-2">
        College
        <select required value={form.school_id} onChange={(e) => setForm({ ...form, school_id: e.target.value })} className={INPUT}>
          <option value="">Choose</option>
          {schools.map((s) => (
            <option key={s.school_id} value={s.school_id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-700">
        Amount (₹)
        <input required type="number" min="1" step="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className={INPUT} />
      </label>
      <label className="text-sm font-medium text-slate-700">
        For
        <select value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} className={INPUT}>
          {PURPOSES.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-700">
        Paid on
        <input required type="date" max={new Date().toLocaleDateString("en-CA")} value={form.paid_on} onChange={(e) => setForm({ ...form, paid_on: e.target.value })} className={INPUT} />
      </label>
      <label className="text-sm font-medium text-slate-700">
        By
        <select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })} className={INPUT}>
          {METHODS.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-medium text-slate-700 sm:col-span-4">
        Note <span className="font-normal text-slate-400">(optional)</span>
        <input maxLength={200} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="e.g. September subscription, UTR 1234" className={INPUT} />
      </label>
      <div className="flex items-end sm:col-span-2">
        <button type="submit" disabled={state === "saving"} className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Record payment"}
        </button>
      </div>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 sm:col-span-6">{error}</p>}
      <p className="text-xs text-slate-500 sm:col-span-6">For Pro templates, also switch on &quot;Pro templates&quot; for the college under Colleges.</p>
    </form>
  );
}

function SuperAdminOverviewPage() {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [payments, setPayments] = useState([]);
  const [state, setState] = useState("loading");

  const load = useCallback(async () => {
    try {
      const [analytics, list] = await Promise.all([apiRequest("/super-admin/analytics", { token }), apiRequest("/super-admin/payments", { token })]);
      setData(analytics);
      setPayments(list);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete(payment) {
    if (!window.confirm(`Delete ${rupees(payment.amount)} from ${payment.school_name}?`)) return;
    await apiRequest(`/super-admin/payments/${payment.id}`, { method: "DELETE", token }).catch(() => {});
    load();
  }

  if (state === "loading") return <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error")
    return (
      <p className="text-sm font-semibold text-rose-700">
        Couldn&apos;t load the overview.{" "}
        <button type="button" onClick={load} className="underline">
          Try again
        </button>
      </p>
    );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Overview</h2>
        <p className="mt-1 text-sm text-slate-500">Colleges on the platform and what they have paid.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Colleges" value={data.schools_total} sub={`${data.schools_active} paying · ${data.schools_trial} trial · ${data.schools_suspended} suspended`} />
        <Tile label="Students" value={data.students_total.toLocaleString("en-IN")} sub={`${data.teachers_total} teachers`} />
        <Tile label="Monthly recurring" value={rupees(data.monthly_recurring)} sub={`${data.pro_schools} college${data.pro_schools === 1 ? "" : "s"} on Pro templates`} />
        <Tile label="Received this month" value={rupees(data.earned_this_month)} sub={`${rupees(data.earned_this_year)} this year · ${rupees(data.earned_total)} all time`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
          <h3 className="mb-3 font-semibold text-slate-900">Money received, last 12 months</h3>
          <EarningsChart months={data.by_month} />
        </section>
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-3 font-semibold text-slate-900">By type (all time)</h3>
          <ul className="space-y-2 text-sm">
            {PURPOSES.map(([id, label]) => (
              <li key={id} className="flex justify-between gap-3">
                <span className="text-slate-600">{label}</span>
                <span className="font-semibold text-slate-900">{rupees(data.by_purpose[id] ?? 0)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <RecordPayment token={token} schools={data.schools} onSaved={load} />

      <section>
        <h3 className="mb-2 font-semibold text-slate-900">Colleges</h3>
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">College</th>
                <th className="px-3 py-2">Billing</th>
                <th className="px-3 py-2 text-right">Students</th>
                <th className="px-3 py-2 text-right">Teachers</th>
                <th className="px-3 py-2 text-right">Monthly fee</th>
                <th className="px-3 py-2 text-right">Paid so far</th>
                <th className="px-3 py-2">Last paid</th>
                <th className="px-3 py-2">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.schools.map((s) => (
                <tr key={s.school_id} className={s.status !== "active" ? "text-slate-400" : ""}>
                  <td className="px-3 py-2">
                    <span className="font-medium text-slate-900">{s.name}</span> <span className="text-xs text-slate-400">{s.code}</span>
                    {s.pro_templates && <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-800">Pro</span>}
                  </td>
                  <td className="px-3 py-2 capitalize">{s.status === "active" ? s.billing_status : "inactive"}</td>
                  <td className="px-3 py-2 text-right">{s.students}</td>
                  <td className="px-3 py-2 text-right">{s.teachers}</td>
                  <td className="px-3 py-2 text-right">{rupees(s.monthly_fee)}</td>
                  <td className="px-3 py-2 text-right font-semibold">{rupees(s.paid_total)}</td>
                  <td className="whitespace-nowrap px-3 py-2">{s.last_paid_on ? new Date(`${s.last_paid_on}T00:00:00`).toLocaleDateString("en-IN") : "—"}</td>
                  <td className="whitespace-nowrap px-3 py-2">{new Date(`${s.joined_on}T00:00:00`).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="mb-2 font-semibold text-slate-900">Payments received</h3>
        {payments.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-8 text-center text-sm text-slate-500">No payments recorded yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {payments.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
                <span>
                  <span className="font-semibold text-slate-900">{rupees(p.amount)}</span> · {p.school_name} · {p.purpose_label}
                  <span className="block text-xs text-slate-500">
                    {new Date(`${p.paid_on}T00:00:00`).toLocaleDateString("en-IN")} · {METHODS.find(([id]) => id === p.method)?.[1]}
                    {p.note && ` · ${p.note}`}
                  </span>
                </span>
                <button type="button" onClick={() => handleDelete(p)} className="text-xs font-semibold text-rose-700 hover:underline">
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default SuperAdminOverviewPage;

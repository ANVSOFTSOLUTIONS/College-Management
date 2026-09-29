import { useCallback, useEffect, useState } from "react";

import { formatRupees } from "../api/feesApi";
import {
  PAYMENT_MODES,
  adjustPayslip,
  fetchMyPayslips,
  fetchPayrollMonth,
  fetchPayslip,
  fetchSalaries,
  generatePayroll,
  payPayslip,
  revertPayslip,
  saveSalary,
} from "../api/payrollApi";
import { PrintPortal, SchoolHeader } from "../components/PrintPortal";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function monthLabel(month) {
  return new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

function previousMonth() {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return d.toLocaleDateString("en-CA").slice(0, 7);
}

// --- Payslip document -----------------------------------------------------------------

function Payslip({ slip }) {
  const rows = (items) =>
    items.map(([label, value]) => (
      <tr key={label}>
        <td className="py-1 pr-3 text-slate-600">{label}</td>
        <td className="py-1 text-right font-medium">{value}</td>
      </tr>
    ));
  return (
    <div className="print-page bg-white p-[12mm] text-slate-900 shadow-lg" style={{ width: "190mm" }}>
      <div className="border-b-2 border-slate-800 pb-4">
        <SchoolHeader school={slip.school} />
      </div>
      <h1 className="mt-5 text-center text-lg font-bold uppercase tracking-[0.15em]">Payslip for {monthLabel(slip.month)}</h1>

      <table className="mt-5 w-full text-sm">
        <tbody>
          <tr>
            <td className="py-1 text-slate-600">Employee</td>
            <td className="py-1 font-semibold">{slip.full_name}</td>
            <td className="py-1 text-slate-600">Employee code</td>
            <td className="py-1 font-semibold">{slip.employee_code || "—"}</td>
          </tr>
          <tr>
            <td className="py-1 text-slate-600">Department</td>
            <td className="py-1 font-semibold">{slip.department || "—"}</td>
            <td className="py-1 text-slate-600">Working days</td>
            <td className="py-1 font-semibold">{slip.working_days}</td>
          </tr>
          <tr>
            <td className="py-1 text-slate-600">Present / leave</td>
            <td className="py-1 font-semibold">
              {slip.days_present} / {slip.days_leave}
            </td>
            <td className="py-1 text-slate-600">Loss-of-pay days</td>
            <td className="py-1 font-semibold">{slip.lop_days}</td>
          </tr>
        </tbody>
      </table>

      <div className="mt-5 grid grid-cols-2 gap-6 text-sm">
        <div>
          <p className="border-b border-slate-300 pb-1 font-semibold uppercase tracking-wide text-slate-500">Earnings</p>
          <table className="w-full">
            <tbody>
              {rows([
                ["Basic", formatRupees(slip.basic)],
                ["Allowances", formatRupees(slip.allowances)],
              ])}
              <tr className="border-t border-slate-200">
                <td className="py-1 font-semibold">Gross</td>
                <td className="py-1 text-right font-semibold">{formatRupees(slip.gross)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div>
          <p className="border-b border-slate-300 pb-1 font-semibold uppercase tracking-wide text-slate-500">Deductions</p>
          <table className="w-full">
            <tbody>
              {rows([
                [`Loss of pay (${slip.lop_days} days)`, formatRupees(slip.lop_amount)],
                ["Other deductions", formatRupees(slip.deductions)],
              ])}
              <tr className="border-t border-slate-200">
                <td className="py-1 font-semibold">Total</td>
                <td className="py-1 text-right font-semibold">{formatRupees(slip.lop_amount + slip.deductions)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-6 rounded-lg bg-slate-100 px-4 py-3">
        <p className="flex justify-between text-base font-bold">
          <span>Net pay</span>
          <span>{formatRupees(slip.net)}</span>
        </p>
        <p className="mt-1 text-sm text-slate-600">{slip.net_in_words}</p>
      </div>
      <p className="mt-4 text-sm text-slate-600">
        {slip.status === "paid" ? `Paid on ${new Date(`${slip.paid_on}T00:00:00`).toLocaleDateString("en-IN")} by ${slip.payment_mode_label.toLowerCase()}.` : "Draft: not paid yet."}
        {slip.note && ` ${slip.note}`}
      </p>
      <p className="mt-10 text-center text-xs text-slate-400">This is a computer-generated payslip.</p>
    </div>
  );
}

function usePrintSlip(token) {
  const [printing, setPrinting] = useState(null);
  const [error, setError] = useState(null);
  async function open(slipId) {
    setError(null);
    try {
      setPrinting(await fetchPayslip(token, slipId));
    } catch (err) {
      setError(errorMessage(err, "Couldn't open the payslip."));
    }
  }
  const portal = printing && (
    <PrintPortal title={`Payslip · ${printing.full_name} · ${monthLabel(printing.month)}`} onClose={() => setPrinting(null)}>
      <Payslip slip={printing} />
    </PrintPortal>
  );
  return { open, portal, error };
}

// --- Admin: monthly payroll ----------------------------------------------------------------

function SlipRow({ token, slip, onChanged, onPrint }) {
  const [lop, setLop] = useState(String(slip.lop_days));
  const [mode, setMode] = useState("bank");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await action());
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
    setBusy(false);
  }

  const draft = slip.status === "draft";
  return (
    <tr className="align-top">
      <td className="px-3 py-2">
        <p className="font-medium text-slate-900">{slip.full_name}</p>
        <p className="text-xs text-slate-500">
          {slip.days_present} present · {slip.days_leave} leave · {slip.days_absent} absent
          {slip.days_unmarked > 0 && <span className="font-semibold text-amber-700"> · {slip.days_unmarked} not marked</span>}
        </p>
        {error && <p className="text-xs font-medium text-rose-700">{error}</p>}
      </td>
      <td className="px-3 py-2 text-right">{formatRupees(slip.gross)}</td>
      <td className="px-3 py-2">
        {draft ? (
          <input
            aria-label={`Loss-of-pay days for ${slip.full_name}`}
            type="number"
            min="0"
            max={slip.working_days}
            step="0.5"
            value={lop}
            disabled={busy}
            onChange={(e) => setLop(e.target.value)}
            onBlur={() => lop !== String(slip.lop_days) && run(() => adjustPayslip(token, slip.id, { lop_days: lop || "0", note: slip.note }))}
            className={`${INPUT} w-20`}
          />
        ) : (
          <span>{slip.lop_days}</span>
        )}
        <p className="text-xs text-slate-500">of {slip.working_days} days</p>
      </td>
      <td className="px-3 py-2 text-right text-slate-600">{formatRupees(slip.lop_amount + slip.deductions)}</td>
      <td className="px-3 py-2 text-right font-semibold text-slate-900">{formatRupees(slip.net)}</td>
      <td className="px-3 py-2">
        {draft ? (
          <div className="flex flex-wrap items-center gap-2">
            <select aria-label="Payment mode" value={mode} onChange={(e) => setMode(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
              {PAYMENT_MODES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <button type="button" disabled={busy} onClick={() => run(() => payPayslip(token, slip.id, { payment_mode: mode }))} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
              Mark paid
            </button>
          </div>
        ) : (
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
            Paid · {slip.payment_mode_label}
          </span>
        )}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-right text-sm">
        <button type="button" onClick={() => onPrint(slip.id)} className="font-semibold text-emerald-700 hover:underline">
          Payslip
        </button>
        {!draft && (
          <button type="button" disabled={busy} onClick={() => window.confirm(`Revert ${slip.full_name}'s payslip to draft?`) && run(() => revertPayslip(token, slip.id))} className="ml-3 font-semibold text-slate-500 hover:underline">
            Revert
          </button>
        )}
      </td>
    </tr>
  );
}

function MonthlyPayroll({ token }) {
  const [month, setMonth] = useState(previousMonth);
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const print = usePrintSlip(token);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setData(await fetchPayrollMonth(token, `${month}-01`));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, month]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleGenerate() {
    setState("generating");
    setError(null);
    try {
      setData(await generatePayroll(token, `${month}-01`));
    } catch (err) {
      setError(errorMessage(err, "Couldn't make the payslips."));
    }
    setState("ready");
  }

  function replace(slip) {
    setData((d) => {
      const slips = d.slips.map((s) => (s.id === slip.id ? slip : s));
      const net = slips.reduce((sum, s) => sum + s.net, 0);
      const paid = slips.filter((s) => s.status === "paid").reduce((sum, s) => sum + s.net, 0);
      return { ...d, slips, total_net: Math.round(net * 100) / 100, total_paid: Math.round(paid * 100) / 100 };
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-slate-700">
          Month
          <input type="month" value={month} max={new Date().toLocaleDateString("en-CA").slice(0, 7)} onChange={(e) => e.target.value && setMonth(e.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </label>
        <button type="button" disabled={state === "generating"} onClick={handleGenerate} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "generating" ? "Working…" : data?.slips.length ? "Refresh drafts from attendance" : `Make payslips for ${monthLabel(month)}`}
        </button>
      </div>
      <p className="text-xs text-slate-500">Working days are Monday–Saturday minus holidays. Present, late and approved leave are paid; days marked absent are loss of pay, which you can change before paying.</p>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
      {print.error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{print.error}</p>}
      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load payroll.</p>}
      {(state === "ready" || state === "generating") && data && (
        <>
          {data.without_salary.length > 0 && (
            <p className="rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-900">
              No salary set for {data.without_salary.join(", ")}. Set it under Salaries to include them.
            </p>
          )}
          {data.slips.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No payslips for {monthLabel(month)} yet.</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-3 text-sm">
                <span className="rounded-lg bg-slate-100 px-3 py-1.5">
                  Total net pay: <span className="font-semibold">{formatRupees(data.total_net)}</span>
                </span>
                <span className="rounded-lg bg-emerald-50 px-3 py-1.5 text-emerald-800">
                  Paid: <span className="font-semibold">{formatRupees(data.total_paid)}</span>
                </span>
              </div>
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Teacher</th>
                      <th className="px-3 py-2 text-right">Gross</th>
                      <th className="px-3 py-2">LOP days</th>
                      <th className="px-3 py-2 text-right">Deductions</th>
                      <th className="px-3 py-2 text-right">Net pay</th>
                      <th className="px-3 py-2">Payment</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.slips.map((slip) => (
                      <SlipRow key={`${slip.id}-${slip.status}-${slip.lop_days}`} token={token} slip={slip} onChanged={replace} onPrint={print.open} />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
      {print.portal}
    </div>
  );
}

// --- Admin: salaries -----------------------------------------------------------------------

function SalaryRow({ token, row, onSaved }) {
  const [form, setForm] = useState({ basic: row.basic ?? "", allowances: row.allowances ?? 0, deductions: row.deductions ?? 0 });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSave() {
    setState("saving");
    setError(null);
    try {
      onSaved(await saveSalary(token, row.teacher_id, { basic: String(form.basic || 0), allowances: String(form.allowances || 0), deductions: String(form.deductions || 0) }));
      setState("saved");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
      setState("idle");
    }
  }

  const input = (key, label) => (
    <input aria-label={`${label} for ${row.full_name}`} type="number" min="0" step="1" value={form[key]} onChange={(e) => { setForm({ ...form, [key]: e.target.value }); setState("idle"); }} className={`${INPUT} w-28`} />
  );
  return (
    <tr>
      <td className="px-3 py-2">
        <p className="font-medium text-slate-900">{row.full_name}</p>
        <p className="text-xs text-slate-500">{row.department}</p>
        {error && <p className="text-xs font-medium text-rose-700">{error}</p>}
      </td>
      <td className="px-3 py-2">{input("basic", "Basic")}</td>
      <td className="px-3 py-2">{input("allowances", "Allowances")}</td>
      <td className="px-3 py-2">{input("deductions", "Deductions")}</td>
      <td className="px-3 py-2 text-right font-semibold">{formatRupees(Number(form.basic || 0) + Number(form.allowances || 0))}</td>
      <td className="px-3 py-2 text-right">
        <button type="button" disabled={state === "saving" || form.basic === ""} onClick={handleSave} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-50">
          {state === "saving" ? "Saving…" : state === "saved" ? "Saved ✓" : "Save"}
        </button>
      </td>
    </tr>
  );
}

function Salaries({ token }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchSalaries(token).then(setRows).catch(() => setError(true));
  }, [token]);

  if (error) return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load salaries.</p>;
  if (!rows) return <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (rows.length === 0) return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">Add teachers first.</p>;
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">Monthly amounts. Deductions are fixed each month (for example PF); loss of pay for absent days is worked out on the payslip.</p>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Teacher</th>
              <th className="px-3 py-2">Basic (₹)</th>
              <th className="px-3 py-2">Allowances (₹)</th>
              <th className="px-3 py-2">Deductions (₹)</th>
              <th className="px-3 py-2 text-right">Gross</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <SalaryRow key={row.teacher_id} token={token} row={row} onSaved={(saved) => setRows((list) => list.map((r) => (r.teacher_id === saved.teacher_id ? saved : r)))} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- Teacher: my payslips ------------------------------------------------------------------

export function MyPayslipsPage() {
  const { token } = useAuth();
  const [slips, setSlips] = useState(null);
  const [error, setError] = useState(false);
  const print = usePrintSlip(token);

  useEffect(() => {
    fetchMyPayslips(token).then(setSlips).catch(() => setError(true));
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">My payslips</h2>
        <p className="mt-1 text-sm text-slate-500">Your salary for each month, once the college marks it paid.</p>
      </div>
      {error && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load your payslips.</p>}
      {!slips && !error && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {print.error && <p className="text-sm font-semibold text-rose-700">{print.error}</p>}
      {slips && slips.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No payslips yet.</p>}
      {slips && slips.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {slips.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="font-semibold text-slate-900">{monthLabel(s.month)}</p>
                <p className="text-xs text-slate-500">
                  Paid {new Date(`${s.paid_on}T00:00:00`).toLocaleDateString("en-IN")} · {s.payment_mode_label}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-bold text-slate-900">{formatRupees(s.net)}</span>
                <button type="button" onClick={() => print.open(s.id)} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
                  View / print
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {print.portal}
    </div>
  );
}

function PayrollPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState("monthly");
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Payroll</h2>
        <p className="mt-1 text-sm text-slate-500">Set each teacher&apos;s salary once; each month, make payslips from attendance and mark them paid.</p>
      </div>
      <div className="flex gap-2" role="tablist">
        {[
          ["monthly", "Monthly payroll"],
          ["salaries", "Salaries"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "monthly" ? <MonthlyPayroll token={token} /> : <Salaries token={token} />}
    </div>
  );
}

export default PayrollPage;

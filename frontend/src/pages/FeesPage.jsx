import { useCallback, useEffect, useState } from "react";

import { fetchMyClasses } from "../api/attendanceApi";
import {
  FEE_CATEGORIES,
  PAYMENT_METHODS,
  addStudentsToFee,
  approveFeeClaim,
  cancelPayment,
  createFeeItems,
  deleteFeeItem,
  feeCategoryLabel,
  fetchClaimProof,
  fetchFeeClaims,
  fetchFeeItems,
  fetchFeeReport,
  fetchOfflineInstructions,
  fetchPaymentSettings,
  fetchReceipt,
  fetchStudentFees,
  formatRupees,
  recordPayment,
  rejectFeeClaim,
  removeStudentFee,
  saveOfflineInstructions,
  sendFeeReminders,
  setDiscount,
  syncFeeItem,
  updateFeeItem,
} from "../api/feesApi";
import { fetchStudents } from "../api/studentsApi";
import { FeeLines, FeeTotals } from "../components/FeeAccount";
import OnlinePaymentSettings from "../components/OnlinePaymentSettings";
import { openReceipt } from "../components/Receipt";
import { openBlob } from "../components/StudentFiles";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const SMALL_BUTTON = "rounded-lg px-3 py-1 text-xs font-semibold ring-1 ring-inset";

function errorMessage(err, fallback) {
  return err instanceof ApiError || err instanceof Error ? err.message || fallback : fallback;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// --- Collect ----------------------------------------------------------------------

function PaymentForm({ token, line, onSaved, onCancel }) {
  const [amount, setAmount] = useState(String(line.balance));
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(todayIso);
  const [notes, setNotes] = useState("");
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      const payment = await recordPayment(token, { student_fee_id: line.id, amount, method, reference, paid_on: paidOn, notes });
      onSaved(payment);
    } catch (err) {
      setState("error");
      setError(errorMessage(err, "Couldn't record the payment."));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 space-y-3 rounded-lg border border-emerald-200 bg-emerald-50/40 p-3">
      <div className="grid gap-3 sm:grid-cols-4">
        <div>
          <label htmlFor={`pay-amount-${line.id}`} className="block text-xs font-medium text-slate-600">
            Amount (₹)
          </label>
          <input id={`pay-amount-${line.id}`} type="number" min="0.01" step="0.01" max={line.balance} required value={amount} onChange={(e) => setAmount(e.target.value)} className={INPUT} />
        </div>
        <div>
          <label htmlFor={`pay-method-${line.id}`} className="block text-xs font-medium text-slate-600">
            Paid by
          </label>
          <select id={`pay-method-${line.id}`} value={method} onChange={(e) => setMethod(e.target.value)} className={INPUT}>
            {PAYMENT_METHODS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`pay-ref-${line.id}`} className="block text-xs font-medium text-slate-600">
            Reference {method === "cash" ? "(optional)" : "(UPI / cheque no.)"}
          </label>
          <input id={`pay-ref-${line.id}`} maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} className={INPUT} />
        </div>
        <div>
          <label htmlFor={`pay-date-${line.id}`} className="block text-xs font-medium text-slate-600">
            Date
          </label>
          <input id={`pay-date-${line.id}`} type="date" required value={paidOn} onChange={(e) => setPaidOn(e.target.value)} className={INPUT} />
        </div>
      </div>
      <input aria-label="Notes" maxLength={300} placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} className={INPUT} />
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Save & print receipt"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function DiscountForm({ token, line, onSaved, onCancel }) {
  const [discount, setDiscountValue] = useState(String(line.discount));
  const [note, setNote] = useState(line.discount_note);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      onSaved(await setDiscount(token, line.id, discount, note));
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the concession."));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:flex-row sm:items-end">
      <div>
        <label htmlFor={`disc-${line.id}`} className="block text-xs font-medium text-slate-600">
          Concession (₹)
        </label>
        <input id={`disc-${line.id}`} type="number" min="0" step="0.01" required value={discount} onChange={(e) => setDiscountValue(e.target.value)} className={INPUT} />
      </div>
      <div className="flex-1">
        <label htmlFor={`disc-note-${line.id}`} className="block text-xs font-medium text-slate-600">
          Reason
        </label>
        <input id={`disc-note-${line.id}`} maxLength={200} placeholder="e.g. Sibling concession" value={note} onChange={(e) => setNote(e.target.value)} className={INPUT} />
      </div>
      <button type="submit" className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-900">
        Save
      </button>
      <button type="button" onClick={onCancel} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
        Cancel
      </button>
      {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
    </form>
  );
}

function StudentFeesPanel({ token, studentId }) {
  const [state, setState] = useState("loading");
  const [account, setAccount] = useState(null);
  const [open, setOpen] = useState(null); // { lineId, kind: "pay" | "discount" }
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setAccount(await fetchStudentFees(token, studentId));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, studentId]);

  useEffect(() => {
    setState("loading");
    setOpen(null);
    setNotice(null);
    load();
  }, [load]);

  function printReceipt(paymentId) {
    setError(null);
    openReceipt(() => fetchReceipt(token, paymentId)).catch((err) => setError(errorMessage(err, "Couldn't open the receipt.")));
  }

  async function handleCancel(payment) {
    const reason = window.prompt(`Cancel receipt ${payment.receipt_number}? Type the reason:`);
    if (!reason) return;
    setError(null);
    try {
      await cancelPayment(token, payment.id, reason);
      await load();
    } catch (err) {
      setError(errorMessage(err, "Couldn't cancel the payment."));
    }
  }

  async function handleRemove(line) {
    if (!window.confirm(`Take ${line.name} off ${account.full_name}? (e.g. no longer uses the bus)`)) return;
    setError(null);
    try {
      setAccount(await removeStudentFee(token, line.id));
      setNotice(`${line.name} removed.`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't remove the fee."));
    }
  }

  if (state === "loading") return <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load this student&apos;s fees.</p>;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">{account.full_name}</h3>
        <p className="text-sm text-slate-500">
          {account.admission_number} · {account.class_name} - {account.section}
        </p>
      </div>
      <FeeTotals account={account} />
      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      <FeeLines
        account={account}
        renderLineActions={(line) =>
          line.balance > 0 && (
            <>
              <button type="button" onClick={() => setOpen({ lineId: line.id, kind: "pay" })} className={`${SMALL_BUTTON} bg-emerald-600 text-white ring-emerald-600 hover:bg-emerald-700`}>
                Record payment
              </button>
              <button type="button" onClick={() => setOpen({ lineId: line.id, kind: "discount" })} className={`${SMALL_BUTTON} text-slate-600 ring-slate-300 hover:bg-slate-100`}>
                Concession
              </button>
              {line.paid === 0 && !line.payments.some((p) => p.status === "success" || p.status === "pending") && (
                <button type="button" onClick={() => handleRemove(line)} className={`${SMALL_BUTTON} text-rose-600 ring-rose-200 hover:bg-rose-50`}>
                  Remove
                </button>
              )}
            </>
          )
        }
        renderLineExtra={(line) =>
          open?.lineId === line.id &&
          (open.kind === "pay" ? (
            <PaymentForm
              token={token}
              line={line}
              onSaved={async (payment) => {
                setOpen(null);
                setNotice(`Received ${formatRupees(payment.amount)} — receipt ${payment.receipt_number}.`);
                printReceipt(payment.id);
                await load();
              }}
              onCancel={() => setOpen(null)}
            />
          ) : (
            <DiscountForm
              token={token}
              line={line}
              onSaved={(updated) => {
                setOpen(null);
                setAccount(updated);
                setNotice("Concession saved.");
              }}
              onCancel={() => setOpen(null)}
            />
          ))
        }
        renderPaymentActions={(payment) =>
          payment.receipt_number && (
            <>
              <button type="button" onClick={() => printReceipt(payment.id)} className="font-semibold text-emerald-700 hover:underline">
                Receipt
              </button>
              {payment.status === "success" && (
                <button type="button" onClick={() => handleCancel(payment)} className="font-semibold text-rose-600 hover:underline">
                  Cancel
                </button>
              )}
            </>
          )
        }
      />
    </div>
  );
}

function CollectTab({ token, studentId, onPickStudent }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    const timer = setTimeout(() => {
      fetchStudents(token, { q: query.trim() })
        .then((list) => setResults(list.slice(0, 8)))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [token, query]);

  return (
    <div className="space-y-5">
      <div className="relative max-w-md">
        <input
          type="search"
          aria-label="Find a student"
          placeholder="Find a student by name or admission number"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        {results.length > 0 && (
          <ul className="absolute z-10 mt-1 w-full divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white shadow-lg">
            {results.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => {
                    onPickStudent(s.id);
                    setQuery("");
                    setResults([]);
                  }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                >
                  <span className="font-semibold text-slate-800">{s.full_name}</span>{" "}
                  <span className="text-slate-400">
                    {s.admission_number} · {s.class.name} - {s.class.section}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {studentId ? (
        <StudentFeesPanel token={token} studentId={studentId} />
      ) : (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
          Search for a student to see their fees and record a payment. Or pick one from the Dues tab.
        </p>
      )}
    </div>
  );
}

// --- Dues -------------------------------------------------------------------------

function DuesTab({ token, classes, onPickStudent }) {
  const [classId, setClassId] = useState("");
  const [onlyWithDues, setOnlyWithDues] = useState(true);
  const [state, setState] = useState("loading");
  const [report, setReport] = useState(null);
  const [onlyOverdue, setOnlyOverdue] = useState(true);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setReport(await fetchFeeReport(token, { classId: classId || undefined, onlyWithDues }));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, classId, onlyWithDues]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleReminders() {
    setNotice(null);
    setError(null);
    try {
      const result = await sendFeeReminders(token, { classId, onlyOverdue });
      setNotice(
        result.students_with_dues === 0
          ? "No students need a reminder."
          : `${result.alerts_created} reminder(s) recorded for ${result.students_with_dues} student(s)${result.alerts_created < result.students_with_dues ? " (some were already reminded today)" : ""}. See Parent Alerts.`,
      );
    } catch (err) {
      setError(errorMessage(err, "Couldn't send reminders."));
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select aria-label="Filter by class" value={classId} onChange={(e) => setClassId(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="">All classes</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} - {c.section}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={onlyWithDues} onChange={(e) => setOnlyWithDues(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
          Only students with dues
        </label>
      </div>

      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && (
        <p className="text-sm font-semibold text-rose-700">
          Couldn&apos;t load the report.{" "}
          <button type="button" onClick={load} className="underline">
            Retry
          </button>
        </p>
      )}
      {state === "ready" && (
        <>
          <FeeTotals account={{ total: report.total, paid: report.collected, balance: report.balance, overdue: report.overdue }} />
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={onlyOverdue} onChange={(e) => setOnlyOverdue(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
              Remind only overdue fees
            </label>
            <button type="button" onClick={handleReminders} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
              Send fee reminders to parents
            </button>
          </div>
          {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
          {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
          {report.students.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
              {onlyWithDues ? "No pending fees. 🎉" : "No fees yet."}
            </p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Student</th>
                    <th className="px-4 py-3 text-right">Paid</th>
                    <th className="px-4 py-3 text-right">Balance</th>
                    <th className="px-4 py-3 text-right">Overdue</th>
                    <th className="px-4 py-3">Next due</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {report.students.map((s) => (
                    <tr key={s.student_id} onClick={() => onPickStudent(s.student_id)} className="cursor-pointer hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <p className="font-semibold text-slate-800">{s.full_name}</p>
                        <p className="text-xs text-slate-400">
                          {s.admission_number} · {s.class_name} - {s.section}
                          {s.primary_contact_phone && ` · ${s.primary_contact_phone}`}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600">{formatRupees(s.paid)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-800">{formatRupees(s.balance)}</td>
                      <td className={`px-4 py-3 text-right ${s.overdue > 0 ? "font-semibold text-rose-700" : "text-slate-400"}`}>{formatRupees(s.overdue)}</td>
                      <td className="px-4 py-3 text-slate-600">{s.next_due_date ? new Date(s.next_due_date).toLocaleDateString("en-IN") : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// --- Fee structure ----------------------------------------------------------------

// Picks students class by class (e.g. the bus users); the choice is kept across classes.
function StudentPicker({ token, classes, selected, onChange, onlyClassId }) {
  const [classId, setClassId] = useState(onlyClassId ?? "");
  const [students, setStudents] = useState(null);

  useEffect(() => {
    if (!classId) {
      setStudents(null);
      return;
    }
    setStudents(null);
    fetchStudents(token, { classId })
      .then((rows) => setStudents(rows.filter((s) => s.status === "active")))
      .catch(() => setStudents([]));
  }, [token, classId]);

  function toggle(id) {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  }

  return (
    <div className="space-y-2 rounded-lg bg-slate-50 p-3">
      {!onlyClassId && (
        <label className="block text-sm font-medium text-slate-700">
          Class
          <select value={classId} onChange={(e) => setClassId(e.target.value)} className={`${INPUT} sm:w-64`}>
            <option value="">Choose a class…</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} - {c.section}
              </option>
            ))}
          </select>
        </label>
      )}
      {classId && students === null && <div className="h-16 animate-pulse rounded-lg bg-white" />}
      {students?.length === 0 && <p className="text-sm text-slate-500">No students in this class.</p>}
      {students?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {students.map((s) => (
            <label key={s.id} className={`flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${selected.includes(s.id) ? "bg-emerald-600 text-white ring-emerald-600" : "bg-white text-slate-600 ring-slate-300"}`}>
              <input type="checkbox" className="sr-only" checked={selected.includes(s.id)} onChange={() => toggle(s.id)} />
              {s.full_name} <span className="opacity-70">{s.admission_number}</span>
            </label>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-500">{selected.length} student(s) chosen{onlyClassId ? "" : " (you can choose from several classes)"}.</p>
    </div>
  );
}

function NewFeeForm({ token, classes, onCreated, onCancel }) {
  const [form, setForm] = useState({ name: "", category: "tuition", term_label: "", academic_year: String(new Date().getFullYear()), amount: "", due_date: "" });
  const [who, setWho] = useState("classes"); // classes | students
  const [classIds, setClassIds] = useState([]);
  const [studentIds, setStudentIds] = useState([]);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  function toggle(id) {
    setClassIds((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));
  }

  function pickCategory(category) {
    setForm({ ...form, category });
    // Transport usually is for the bus users only.
    if (category === "transport") setWho("students");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (who === "classes" ? classIds.length === 0 : studentIds.length === 0) {
      setError(who === "classes" ? "Choose at least one class." : "Choose at least one student.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onCreated(await createFeeItems(token, who === "classes" ? { ...form, class_ids: classIds } : { ...form, student_ids: studentIds }));
    } catch (err) {
      setError(errorMessage(err, "Couldn't create the fee."));
      setSaving(false);
    }
  }

  const field = (key, label, props = {}) => (
    <div>
      <label htmlFor={`fee-${key}`} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input id={`fee-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">New fee</h3>
      <div className="grid gap-3 sm:grid-cols-5">
        <div>
          <label htmlFor="fee-category" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select id="fee-category" value={form.category} onChange={(e) => pickCategory(e.target.value)} className={INPUT}>
            {FEE_CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-2">{field("name", "Fee name", { required: true, maxLength: 150, placeholder: "e.g. Tuition fee" })}</div>
        {field("term_label", "Term", { maxLength: 50, placeholder: "e.g. Term 1" })}
        {field("academic_year", "Academic year", { required: true, maxLength: 9 })}
        {field("amount", "Amount per student (₹)", { required: true, type: "number", min: "1", step: "0.01" })}
        {field("due_date", "Due date", { required: true, type: "date" })}
      </div>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Who pays this fee">
        {[
          ["classes", "Whole classes"],
          ["students", "Only chosen students"],
        ].map(([id, label]) => (
          <button key={id} type="button" role="radio" aria-checked={who === id} onClick={() => setWho(id)} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${who === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-300"}`}>
            {label}
          </button>
        ))}
      </div>
      {who === "students" && <StudentPicker token={token} classes={classes} selected={studentIds} onChange={setStudentIds} />}
      <fieldset hidden={who !== "classes"}>
        <legend className="text-sm font-medium text-slate-700">Classes</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" onClick={() => setClassIds(classIds.length === classes.length ? [] : classes.map((c) => c.id))} className="rounded-full px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
            {classIds.length === classes.length ? "Clear" : "All classes"}
          </button>
          {classes.map((c) => (
            <label key={c.id} className={`flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${classIds.includes(c.id) ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-600 ring-slate-300"}`}>
              <input type="checkbox" className="sr-only" checked={classIds.includes(c.id)} onChange={() => toggle(c.id)} />
              {c.name} - {c.section}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="text-xs text-slate-400">
        {who === "classes" ? "Every current student in these classes is billed right away." : "Only the chosen students are billed. You can add more students to the fee later."}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {saving ? "Creating…" : "Create fee"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
          Cancel
        </button>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function StructureTab({ token, classes }) {
  const [state, setState] = useState("loading");
  const [items, setItems] = useState([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(null); // { id, classId, studentIds } for a chosen-students fee
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [online, setOnline] = useState(null);

  const load = useCallback(async () => {
    try {
      setItems(await fetchFeeItems(token));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
    fetchPaymentSettings(token).then(setOnline).catch(() => setOnline(null));
  }, [load, token]);

  async function run(action, success, fallback) {
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      await load();
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  }

  async function handleEdit(event) {
    event.preventDefault();
    const body = { name: editing.name, due_date: editing.due_date, amount: editing.amount };
    await run(() => updateFeeItem(token, editing.id, body), "Fee updated.", "Couldn't update the fee.");
    setEditing(null);
  }

  return (
    <div className="space-y-5">
      {online && <OnlinePaymentSettings token={token} settings={online} onSaved={setOnline} />}
      {!creating && (
        <button type="button" onClick={() => setCreating(true)} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
          New fee
        </button>
      )}
      {creating && (
        <NewFeeForm
          token={token}
          classes={classes}
          onCreated={async (created) => {
            setCreating(false);
            setNotice(`Created for ${created.length} class(es), ${created.reduce((n, i) => n + i.student_count, 0)} student(s) billed.`);
            await load();
          }}
          onCancel={() => setCreating(false)}
        />
      )}
      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      {state === "loading" && <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load fees.</p>}
      {state === "ready" && items.length === 0 && !creating && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No fees yet. Create your first one, e.g. Term 1 tuition.</p>
      )}
      {state === "ready" && items.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {items.map((item) => (
            <li key={item.id} className="px-4 py-3">
              {editing?.id === item.id ? (
                <form onSubmit={handleEdit} className="grid gap-2 sm:grid-cols-4 sm:items-end">
                  <input aria-label="Fee name" required value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className={INPUT} />
                  <input aria-label="Amount" type="number" min="1" step="0.01" required value={editing.amount} onChange={(e) => setEditing({ ...editing, amount: e.target.value })} className={INPUT} />
                  <input aria-label="Due date" type="date" required value={editing.due_date} onChange={(e) => setEditing({ ...editing, due_date: e.target.value })} className={INPUT} />
                  <div className="flex gap-2">
                    <button type="submit" className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">
                      Save
                    </button>
                    <button type="button" onClick={() => setEditing(null)} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-semibold text-slate-800">
                      {item.name} <span className="font-normal text-slate-500">· {item.class_name} - {item.section}</span>{" "}
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{feeCategoryLabel(item.category)}</span>
                      {item.applies_to === "selected" && <span className="ml-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">Chosen students</span>}
                    </p>
                    <p className="text-xs text-slate-500">
                      {[item.term_label, item.academic_year].filter(Boolean).join(" · ")} · {formatRupees(item.amount)} per student · Due{" "}
                      {new Date(item.due_date).toLocaleDateString("en-IN")} · {item.student_count} students · Collected {formatRupees(item.collected)} · Pending{" "}
                      {formatRupees(item.pending)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => setEditing({ id: item.id, name: item.name, amount: String(item.amount), due_date: item.due_date })} className={`${SMALL_BUTTON} text-slate-600 ring-slate-300 hover:bg-slate-100`}>
                      Edit
                    </button>
                    {item.applies_to === "selected" ? (
                      <button type="button" onClick={() => setAdding(adding?.id === item.id ? null : { id: item.id, classId: item.class_id, studentIds: [] })} className={`${SMALL_BUTTON} text-emerald-700 ring-emerald-200 hover:bg-emerald-50`}>
                        Add students
                      </button>
                    ) : (
                      <button type="button" onClick={() => run(() => syncFeeItem(token, item.id), "New students in the class were billed.", "Couldn't add new students.")} className={`${SMALL_BUTTON} text-emerald-700 ring-emerald-200 hover:bg-emerald-50`}>
                        Bill new students
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => window.confirm(`Delete ${item.name} for ${item.class_name} - ${item.section}?`) && run(() => deleteFeeItem(token, item.id), "Fee deleted.", "Couldn't delete the fee.")}
                      className={`${SMALL_BUTTON} text-rose-600 ring-rose-200 hover:bg-rose-50`}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
              {adding?.id === item.id && (
                <div className="mt-3 space-y-2">
                  <StudentPicker token={token} classes={classes} onlyClassId={item.class_id} selected={adding.studentIds} onChange={(studentIds) => setAdding({ ...adding, studentIds })} />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={adding.studentIds.length === 0}
                      onClick={async () => {
                        await run(() => addStudentsToFee(token, item.id, adding.studentIds), "Students added to the fee.", "Couldn't add the students.");
                        setAdding(null);
                      }}
                      className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                    >
                      Add {adding.studentIds.length || ""} student(s)
                    </button>
                    <button type="button" onClick={() => setAdding(null)} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-600 hover:bg-slate-100">
                      Cancel
                    </button>
                  </div>
                  <p className="text-xs text-slate-500">Students who already have this fee are skipped. To take it off a student, open them under Collect fees.</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --- Page -------------------------------------------------------------------------

const TABS = [
  { id: "collect", label: "Collect fees" },
  { id: "dues", label: "Dues & reminders" },
  { id: "structure", label: "Fee structure" },
  { id: "offline", label: "Offline payments" },
];

function FeesPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState("collect");
  const [studentId, setStudentId] = useState(null);
  const [classes, setClasses] = useState([]);

  useEffect(() => {
    fetchMyClasses(token).then(setClasses).catch(() => setClasses([]));
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Fees</h2>
        <p className="mt-1 text-sm text-slate-500">Set fees per class and term, record payments with receipts, and remind parents about dues.</p>
      </div>
      <div role="tablist" className="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1 text-sm font-semibold">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`shrink-0 rounded-md px-4 py-1.5 ${tab === t.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "collect" && <CollectTab token={token} studentId={studentId} onPickStudent={setStudentId} />}
      {tab === "dues" && (
        <DuesTab
          token={token}
          classes={classes}
          onPickStudent={(id) => {
            setStudentId(id);
            setTab("collect");
          }}
        />
      )}
      {tab === "structure" && <StructureTab token={token} classes={classes} />}
      {tab === "offline" && <OfflineTab token={token} />}
    </div>
  );
}

// --- Offline payments reported by parents --------------------------------------------

const CLAIM_TABS = [
  ["submitted", "To check"],
  ["approved", "Confirmed"],
  ["rejected", "Not confirmed"],
];

function OfflineInstructionsCard({ token }) {
  const [text, setText] = useState(null);
  const [saved, setSaved] = useState("");
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchOfflineInstructions(token)
      .then((r) => {
        setText(r.text);
        setSaved(r.text);
      })
      .catch(() => setText(""));
  }, [token]);

  async function save(event) {
    event.preventDefault();
    setMessage(null);
    try {
      const r = await saveOfflineInstructions(token, text);
      setSaved(r.text);
      setMessage({ ok: true, text: "Saved. Parents see this when they pay offline." });
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err, "Couldn't save.") });
    }
  }

  if (text === null) return <div className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  return (
    <form onSubmit={save} className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
      <label htmlFor="offline-instructions" className="block font-semibold text-slate-900">
        How parents can pay you directly
      </label>
      <textarea
        id="offline-instructions"
        rows={3}
        maxLength={500}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"e.g. UPI: college@okaxis\nBank: SBI, A/c 1234567890, IFSC SBIN0001234\nOffice: Mon–Sat, 9 am to 1 pm"}
        className={INPUT}
      />
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" disabled={text === saved} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
          Save
        </button>
        {message && <span className={`text-sm ${message.ok ? "text-emerald-700" : "text-rose-700"}`}>{message.text}</span>}
      </div>
    </form>
  );
}

function ClaimRow({ token, claim, onChanged }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
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

  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="text-sm">
          <p className="font-semibold text-slate-900">
            {formatRupees(claim.amount)} · {claim.student_name} <span className="font-normal text-slate-500">({claim.admission_number}, {claim.class_name})</span>
          </p>
          <p className="text-slate-600">
            {claim.fee_name} · {claim.method_label} · paid {new Date(claim.paid_on).toLocaleDateString("en-IN")}
            {claim.reference && (
              <>
                {" "}
                · Ref <span className="font-mono">{claim.reference}</span>
              </>
            )}
          </p>
          <p className="text-xs text-slate-500">
            Reported by {claim.parent_name || "parent"} on {new Date(claim.created_at).toLocaleString("en-IN")}
            {claim.note && ` · “${claim.note}”`}
          </p>
          {claim.status === "approved" && <p className="text-xs font-semibold text-emerald-700">Confirmed · receipt {claim.receipt_number}</p>}
          {claim.status === "rejected" && <p className="text-xs font-semibold text-rose-700">Not confirmed: {claim.review_note}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {claim.has_proof && (
            <button type="button" onClick={() => openBlob(() => fetchClaimProof(token, claim.id)).catch(() => setError("Couldn't open the screenshot."))} className={`${SMALL_BUTTON} text-slate-600 ring-slate-300 hover:bg-slate-100`}>
              View screenshot
            </button>
          )}
          {claim.status === "submitted" && !rejecting && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => window.confirm(`Is ${formatRupees(claim.amount)} in the college's account / cash box? This records it and issues a receipt.`) && run(() => approveFeeClaim(token, claim.id))}
                className={`${SMALL_BUTTON} bg-emerald-600 text-white ring-emerald-600 hover:bg-emerald-700 disabled:opacity-60`}
              >
                Confirm &amp; give receipt
              </button>
              <button type="button" disabled={busy} onClick={() => setRejecting(true)} className={`${SMALL_BUTTON} text-rose-600 ring-rose-200 hover:bg-rose-50`}>
                Not received
              </button>
            </>
          )}
        </div>
      </div>
      {rejecting && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(() => rejectFeeClaim(token, claim.id, note));
          }}
          className="flex flex-col gap-2 sm:flex-row"
        >
          <input required minLength={3} maxLength={300} autoFocus value={note} onChange={(e) => setNote(e.target.value)} placeholder="Tell the parent why, e.g. No such UPI payment received" className={`${INPUT} mt-0 flex-1`} />
          <button type="submit" disabled={busy} className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-semibold text-white">
            Send
          </button>
          <button type="button" onClick={() => setRejecting(false)} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
            Cancel
          </button>
        </form>
      )}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
    </li>
  );
}

function OfflineTab({ token }) {
  const [status, setStatus] = useState("submitted");
  const [claims, setClaims] = useState(null);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setError(false);
    setClaims(null);
    try {
      setClaims(await fetchFeeClaims(token, status));
    } catch {
      setError(true);
    }
  }, [token, status]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <OfflineInstructionsCard token={token} />
      <p className="text-sm text-slate-500">Parents who paid by UPI, bank transfer, cash or cheque report it here. Check your account, then confirm to give a receipt.</p>
      <div className="flex gap-2">
        {CLAIM_TABS.map(([id, label]) => (
          <button key={id} type="button" onClick={() => setStatus(id)} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${status === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-300"}`}>
            {label}
          </button>
        ))}
      </div>
      {error && (
        <p className="text-sm font-semibold text-rose-700">
          Couldn&apos;t load.{" "}
          <button type="button" onClick={load} className="underline">
            Retry
          </button>
        </p>
      )}
      {!error && claims === null && <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {claims?.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
          {status === "submitted" ? "Nothing to check." : "None yet."}
        </p>
      )}
      {claims?.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {claims.map((claim) => (
            <ClaimRow key={claim.id} token={token} claim={claim} onChanged={(updated) => setClaims((list) => list.map((c) => (c.id === updated.id ? updated : c)))} />
          ))}
        </ul>
      )}
    </div>
  );
}

export default FeesPage;

import { useCallback, useEffect, useState } from "react";

import { fetchChildResults } from "../api/examsApi";
import { formatRupees } from "../api/feesApi";
import {
  confirmOnlinePayment,
  confirmPayAll,
  fetchChildOverview,
  fetchChildPhoto,
  fetchChildReceipt,
  fetchChildren,
  startOnlinePayment,
  startPayAll,
} from "../api/parentApi";
import CampusCards from "../components/CampusCards";
import { FeeLines, FeeTotals } from "../components/FeeAccount";
import { ChildLeave, OfflinePaymentForm, OfflinePaymentList } from "../components/ParentExtras";
import { StudentDocuments, StudentPhoto } from "../components/StudentFiles";
import { openReceipt } from "../components/Receipt";
import { ReportCardView, printReportCard } from "../components/ReportCard";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";
import { openCheckout } from "../lib/payments";

const ATTENDANCE_STYLES = { present: "bg-emerald-500", absent: "bg-rose-500", late: "bg-amber-400" };

function errorMessage(err, fallback) {
  return err instanceof ApiError || err instanceof Error ? err.message || fallback : fallback;
}

function ChildAvatar({ token, child, size = "h-12 w-12" }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!child.has_photo) return undefined;
    let objectUrl = null;
    fetchChildPhoto(token, child.student_id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {});
    return () => objectUrl && URL.revokeObjectURL(objectUrl);
  }, [token, child.student_id, child.has_photo]);
  const initials = child.full_name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return url ? (
    <img src={url} alt="" className={`${size} rounded-full object-cover`} />
  ) : (
    <div className={`${size} flex items-center justify-center rounded-full bg-emerald-100 font-bold text-emerald-700`}>{initials}</div>
  );
}

function ChildResults({ token, studentId }) {
  const [results, setResults] = useState(null);
  useEffect(() => {
    fetchChildResults(token, studentId)
      .then(setResults)
      .catch(() => setResults([]));
  }, [token, studentId]);
  if (results === null) return <div className="h-20 animate-pulse rounded-xl bg-slate-100" />;
  if (results.length === 0) return <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No results published yet.</p>;
  return results.map((r) => <ReportCardView key={r.exam_id} card={r.report_card} onPrint={() => printReportCard(() => Promise.resolve(r.report_card))} />);
}

function ChildDetail({ token, studentId }) {
  const [state, setState] = useState("loading");
  const [overview, setOverview] = useState(null);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [payingAll, setPayingAll] = useState(false);
  const [offline, setOffline] = useState(null); // the fee line whose "paid offline" form is open

  const load = useCallback(async () => {
    try {
      setOverview(await fetchChildOverview(token, studentId));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, studentId]);

  useEffect(() => {
    setState("loading");
    load();
  }, [load]);

  async function handlePay(line) {
    setError(null);
    setNotice(null);
    try {
      const order = await startOnlinePayment(token, studentId, line.id);
      // The payment page opens over the app; when it closes, the college's server checks with the payment gateway.
      const failed = await openCheckout(order);
      if (failed) {
        setError(failed);
        return;
      }
      try {
        const receipt = await confirmOnlinePayment(token, studentId, order.payment_id);
        setNotice(`Paid ${formatRupees(receipt.amount)}. Receipt ${receipt.receipt_number}.`);
        await load();
      } catch (err) {
        setError(errorMessage(err, "We couldn't confirm the payment yet. If money was taken, the receipt will appear here shortly."));
      }
    } catch (err) {
      setError(errorMessage(err, "Couldn't start the payment."));
    }
  }

  async function handlePayAll() {
    setError(null);
    setNotice(null);
    setPayingAll(true);
    try {
      const order = await startPayAll(token, studentId);
      const failed = await openCheckout(order);
      if (failed) {
        setError(failed);
        return;
      }
      try {
        const { receipts } = await confirmPayAll(token, studentId, order.payment_id);
        setNotice(`Paid ${formatRupees(order.amount)} for ${receipts.length} fees. Receipts ${receipts.map((r) => r.receipt_number).join(", ")}.`);
        await load();
      } catch (err) {
        setError(errorMessage(err, "We couldn't confirm the payment yet. If money was taken, the receipts will appear here shortly."));
      }
    } catch (err) {
      setError(errorMessage(err, "Couldn't start the payment."));
    } finally {
      setPayingAll(false);
    }
  }

  if (state === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") {
    return (
      <p className="text-sm font-semibold text-rose-700">
        Couldn&apos;t load details.{" "}
        <button type="button" onClick={load} className="underline">
          Retry
        </button>
      </p>
    );
  }

  const { child } = overview;
  return (
    <div className="space-y-6">
      <section className="grid grid-cols-3 gap-3">
        {[
          { label: "Present", value: overview.present, style: "text-emerald-700" },
          { label: "Absent", value: overview.absent, style: "text-rose-700" },
          { label: "Late", value: overview.late, style: "text-amber-700" },
        ].map((card) => (
          <div key={card.label} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{card.label}</p>
            <p className={`mt-1 text-2xl font-bold ${card.style}`}>{card.value}</p>
            <p className="text-xs text-slate-400">last 30 days</p>
          </div>
        ))}
      </section>
      {overview.recent_attendance.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="Recent attendance">
          {overview.recent_attendance.map((day) => (
            <span key={day.date} title={`${new Date(day.date).toLocaleDateString("en-IN")}: ${day.status}`} className={`h-3 w-6 rounded-full ${ATTENDANCE_STYLES[day.status]}`} />
          ))}
        </div>
      )}

      <section className="space-y-3">
        <h3 className="text-lg font-semibold text-slate-900">Exam results</h3>
        <ChildResults token={token} studentId={studentId} />
      </section>

      <section className="space-y-3">
        <h3 className="text-lg font-semibold text-slate-900">Fees</h3>
        <FeeTotals account={overview.fees} />
        {!overview.online_payment_enabled && overview.fees.balance > 0 && (
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
            Online payment isn&apos;t switched on by the college yet. Pay the college directly (cash, UPI or bank), then tap &quot;Paid offline? Tell college&quot; on the fee.
            Your receipt appears here once the college confirms.
          </p>
        )}
        {overview.online_payment_enabled && overview.fees.lines.filter((l) => l.balance > 0).length > 1 && (
          <div className="flex flex-col gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-emerald-900">
              Pay all {overview.fees.lines.filter((l) => l.balance > 0).length} due fees together. You get a receipt for each.
            </p>
            <button type="button" onClick={handlePayAll} disabled={payingAll} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
              {payingAll ? "Opening payment…" : `Pay all ${formatRupees(overview.fees.balance)}`}
            </button>
          </div>
        )}
        {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
        {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
        <FeeLines
          account={overview.fees}
          renderLineActions={(line) =>
            line.balance > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => handlePay(line)}
                  disabled={!overview.online_payment_enabled}
                  title={overview.online_payment_enabled ? undefined : "The college hasn't switched on online payment yet"}
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  Pay {formatRupees(line.balance)} online
                </button>
                <button
                  type="button"
                  onClick={() => setOffline(offline === line.id ? null : line.id)}
                  className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
                >
                  Paid offline? Tell college
                </button>
              </>
            )
          }
          renderLineExtra={(line) =>
            offline === line.id && (
              <OfflinePaymentForm
                token={token}
                studentId={studentId}
                line={line}
                instructions={overview.offline_instructions}
                onCancel={() => setOffline(null)}
                onSent={async () => {
                  setOffline(null);
                  setNotice("Sent to the college. They will check and confirm; the receipt then appears here.");
                  await load();
                }}
              />
            )
          }
          renderPaymentActions={(payment) =>
            payment.receipt_number &&
            payment.status === "success" && (
              <button
                type="button"
                onClick={() => openReceipt(() => fetchChildReceipt(token, child.student_id, payment.id)).catch((err) => setError(errorMessage(err, "Couldn't open the receipt.")))}
                className="font-semibold text-emerald-700 hover:underline"
              >
                Receipt
              </button>
            )
          }
        />
        <OfflinePaymentList payments={overview.offline_payments} />
      </section>

      <CampusCards token={token} studentId={child.student_id} />
      <ChildLeave token={token} child={child} />

      <section className="space-y-3">
        <h3 className="text-lg font-semibold text-slate-900">Photo &amp; documents</h3>
        <p className="text-sm text-slate-500">Upload {child.full_name.split(" ")[0]}&apos;s photo and documents (birth certificate, Aadhaar, TC…). The college checks each one.</p>
        <StudentPhoto token={token} base={`/me/parent/children/${studentId}`} hasPhoto={child.has_photo} name={child.full_name} editable onUploaded={load} />
        <StudentDocuments token={token} base={`/me/parent/children/${studentId}`} />
      </section>

      <section className="space-y-3">
        <h3 className="text-lg font-semibold text-slate-900">Messages from college</h3>
        {overview.alerts.length === 0 && overview.remarks.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No messages yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm">
            {overview.remarks.map((remark, index) => (
              <li key={`r${index}`} className="px-4 py-3">
                <p className="font-semibold text-slate-800">
                  {remark.category_label}
                  {remark.subject_name && <span className="font-normal text-slate-500"> · {remark.subject_name}</span>}
                </p>
                {remark.note && <p className="text-slate-700">{remark.note}</p>}
                <p className="text-xs text-slate-400">
                  {new Date(remark.remark_date).toLocaleDateString("en-IN")} · {remark.author_name}
                </p>
              </li>
            ))}
            {overview.alerts
              .filter((a) => a.kind !== "remark")
              .map((alert, index) => (
                <li key={`a${index}`} className="px-4 py-3">
                  <p className="text-slate-700">{alert.message}</p>
                  <p className="text-xs text-slate-400">{new Date(alert.created_at).toLocaleString("en-IN")}</p>
                </li>
              ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ParentPortalPage() {
  const { token } = useAuth();
  const [state, setState] = useState("loading");
  const [children, setChildren] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    try {
      const result = await fetchChildren(token);
      setChildren(result);
      setSelectedId((current) => current ?? result[0]?.student_id ?? null);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (state === "loading") return <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load the student details.</p>
        <button type="button" onClick={load} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white">
          Retry
        </button>
      </div>
    );
  }
  if (children.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-600">No student record is linked to this login yet.</p>
        <p className="mt-1 text-sm text-slate-400">Ask the college office to link your record to this login.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-3 overflow-x-auto pb-1">
        {children.map((child) => (
          <button
            key={child.student_id}
            type="button"
            onClick={() => setSelectedId(child.student_id)}
            className={`flex shrink-0 items-center gap-3 rounded-xl border px-4 py-3 text-left ${selectedId === child.student_id ? "border-emerald-500 bg-emerald-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <ChildAvatar token={token} child={child} />
            <span>
              <span className="block font-semibold text-slate-800">{child.full_name}</span>
              <span className="block text-xs text-slate-500">
                {child.class_name} - {child.section} · {child.school_name}
              </span>
              {child.balance > 0 && (
                <span className={`block text-xs font-semibold ${child.overdue > 0 ? "text-rose-600" : "text-amber-700"}`}>Fees due {formatRupees(child.balance)}</span>
              )}
            </span>
          </button>
        ))}
      </div>
      {selectedId && <ChildDetail key={selectedId} token={token} studentId={selectedId} />}
    </div>
  );
}

export default ParentPortalPage;

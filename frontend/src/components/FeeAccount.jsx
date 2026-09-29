import { feeCategoryLabel, formatRupees } from "../api/feesApi";

const STATUS_STYLES = {
  paid: "bg-emerald-50 text-emerald-700",
  partial: "bg-amber-50 text-amber-700",
  due: "bg-slate-100 text-slate-600",
  overdue: "bg-rose-50 text-rose-700",
};
const STATUS_LABELS = { paid: "Paid", partial: "Part paid", due: "Due", overdue: "Overdue" };
const PAYMENT_STATUS = { success: "", pending: "Pending", failed: "Failed", cancelled: "Cancelled" };

export function FeeTotals({ account }) {
  const cards = [
    { label: "Total fees", value: account.total },
    { label: "Paid", value: account.paid },
    { label: "Balance", value: account.balance },
    { label: "Overdue", value: account.overdue, alert: account.overdue > 0 },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className={`rounded-xl border px-4 py-3 ${card.alert ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-white"}`}>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{card.label}</p>
          <p className={`mt-1 text-lg font-bold ${card.alert ? "text-rose-700" : "text-slate-900"}`}>{formatRupees(card.value)}</p>
        </div>
      ))}
    </div>
  );
}

// One student's fee lines. `renderLineActions(line)` and `renderPaymentActions(payment, line)`
// let the admin page and the parent portal add their own buttons.
export function FeeLines({ account, renderLineActions, renderPaymentActions, renderLineExtra }) {
  if (account.lines.length === 0) {
    return <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No fees yet.</p>;
  }
  return (
    <ul className="space-y-3">
      {account.lines.map((line) => (
        <li key={line.id} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-semibold text-slate-800">
                {line.name}
                <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[line.status]}`}>{STATUS_LABELS[line.status]}</span>
              </p>
              <p className="text-xs text-slate-500">
                <span className="font-medium text-slate-600">{feeCategoryLabel(line.category)}</span> ·{" "}
                {[line.term_label, line.academic_year].filter(Boolean).join(" · ")} · Due {new Date(line.due_date).toLocaleDateString("en-IN")}
              </p>
              <p className="mt-1 text-sm text-slate-700">
                {formatRupees(line.amount)}
                {line.discount > 0 && (
                  <span className="text-emerald-700">
                    {" "}
                    − {formatRupees(line.discount)} concession{line.discount_note && ` (${line.discount_note})`}
                  </span>
                )}{" "}
                · Paid {formatRupees(line.paid)} · <span className="font-semibold">Balance {formatRupees(line.balance)}</span>
              </p>
            </div>
            {renderLineActions && <div className="flex flex-wrap gap-2">{renderLineActions(line)}</div>}
          </div>
          {renderLineExtra?.(line)}
          {line.payments.length > 0 && (
            <ul className="mt-3 divide-y divide-slate-100 rounded-lg bg-slate-50 text-xs">
              {line.payments.map((payment) => (
                <li key={payment.id} className="flex flex-col gap-1 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                  <span className={payment.status === "success" ? "text-slate-700" : "text-slate-400 line-through"}>
                    {formatRupees(payment.amount)} · {payment.method.replace("_", " ")} · {new Date(payment.paid_on).toLocaleDateString("en-IN")}
                    {payment.receipt_number && ` · ${payment.receipt_number}`}
                    {payment.reference && ` · Ref ${payment.reference}`}
                  </span>
                  <span className="flex items-center gap-2">
                    {PAYMENT_STATUS[payment.status] && <span className="font-semibold text-slate-500">{PAYMENT_STATUS[payment.status]}</span>}
                    {payment.cancel_reason && <span className="text-rose-600">({payment.cancel_reason})</span>}
                    {renderPaymentActions?.(payment, line)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

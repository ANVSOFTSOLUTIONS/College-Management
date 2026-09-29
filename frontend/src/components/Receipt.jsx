import { PAYMENT_METHODS, formatRupees } from "../api/feesApi";

const METHOD_LABELS = { ...Object.fromEntries(PAYMENT_METHODS.map((m) => [m.id, m.label])), online: "Online" };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function receiptHtml(receipt) {
  const rows = [
    ["Receipt no.", receipt.receipt_number],
    ["Date", new Date(receipt.paid_on).toLocaleDateString("en-IN")],
    ["Student", `${receipt.student_name} (${receipt.admission_number})`],
    ["Class", `${receipt.class_name} - ${receipt.section}`],
    ["Fee", [receipt.fee_name, receipt.term_label, receipt.academic_year].filter(Boolean).join(" · ")],
    ["Paid by", METHOD_LABELS[receipt.method] ?? receipt.method],
    ...(receipt.reference ? [["Reference", receipt.reference]] : []),
    ["Amount paid", formatRupees(receipt.amount)],
    ["Balance on this fee", formatRupees(receipt.balance_after)],
    ...(receipt.received_by_name ? [["Received by", receipt.received_by_name]] : []),
  ];
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(receipt.receipt_number)}</title>
<style>
  body { font-family: system-ui, sans-serif; color: #0f172a; margin: 32px; }
  .box { max-width: 560px; margin: auto; border: 1px solid #cbd5e1; border-radius: 12px; padding: 24px; }
  h1 { font-size: 20px; margin: 0; } .muted { color: #64748b; font-size: 13px; margin: 2px 0; }
  h2 { font-size: 14px; letter-spacing: .08em; text-transform: uppercase; color: #047857; margin: 20px 0 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  td { padding: 6px 0; border-bottom: 1px solid #e2e8f0; } td:first-child { color: #64748b; width: 45%; }
  .cancelled { color: #be123c; font-weight: 700; } .foot { margin-top: 24px; font-size: 12px; color: #64748b; }
  @media print { body { margin: 0; } .box { border: 0; } }
</style></head><body><div class="box">
  <h1>${escapeHtml(receipt.school_name)}</h1>
  ${receipt.school_address ? `<p class="muted">${escapeHtml(receipt.school_address)}</p>` : ""}
  ${receipt.school_phone ? `<p class="muted">Phone: ${escapeHtml(receipt.school_phone)}</p>` : ""}
  <h2>Fee receipt</h2>
  ${receipt.status === "cancelled" ? '<p class="cancelled">This payment was cancelled.</p>' : ""}
  <table>${rows.map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td></tr>`).join("")}</table>
  <p class="foot">This is a computer-generated receipt.</p>
</div><script>window.onload = () => window.print();</script></body></html>`;
  return html;
}

// Opens the receipt in its own window for printing. The window opens before the
// receipt loads so pop-up blockers see it as part of the click.
export async function openReceipt(loadReceipt) {
  const win = window.open("", "_blank");
  try {
    const receipt = await loadReceipt();
    if (!win) throw new Error("Allow pop-ups for this site to print receipts.");
    win.document.write(receiptHtml(receipt));
    win.document.close();
  } catch (err) {
    win?.close();
    throw err;
  }
}

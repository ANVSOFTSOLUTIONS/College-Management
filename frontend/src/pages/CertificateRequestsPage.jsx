import { useState } from "react";

import { DANGER, errorMessage, LoadState, Notice, PageHeader, PRIMARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const TONE = { pending: "bg-amber-100 text-amber-800", issued: "bg-emerald-100 text-emerald-800", rejected: "bg-rose-100 text-rose-700" };

function CertificateRequestsPage() {
  const { token } = useAuth();
  const [status, setStatus] = useState("pending");
  const [rows, reload, state] = useLoad(() => apiRequest("/certificate-requests", { token, params: { status: status || null } }), [token, status]);
  const [notes, setNotes] = useState({});
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function decide(r, action) {
    setError(null);
    setMessage(null);
    try {
      const done = await apiRequest(`/certificate-requests/${r.id}/${action}`, { method: "POST", token, body: { note: notes[r.id] ?? "" } });
      setMessage(action === "approve" ? `${done.title} ${done.serial_no} issued for ${r.full_name}. Print it from ID cards & certificates.` : `Request from ${r.full_name} rejected.`);
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Certificate requests" subtitle="Bonafide and TC requests from the student app. Approving issues the certificate with the next serial number." />
      <div className="flex gap-2">
        {[["pending", "Pending"], ["issued", "Issued"], ["rejected", "Rejected"], ["", "All"]].map(([v, l]) => (
          <button key={l} type="button" onClick={() => setStatus(v)} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ring-1 ring-inset ${status === v ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-700 ring-slate-300"}`}>
            {l}
          </button>
        ))}
      </div>
      <Notice message={message} error={error} />
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="requests" />
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No requests.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-semibold text-slate-900">
                  {r.title} · {r.full_name} <span className="text-xs font-normal text-slate-500">({r.admission_number}, {r.batch})</span>
                </p>
                <p className="text-sm text-slate-600">Purpose: {r.purpose}</p>
                <p className="text-xs text-slate-400">
                  {new Date(r.created_at).toLocaleString("en-IN")}
                  {r.serial_no ? ` · ${r.serial_no}` : ""}
                  {r.note ? ` · ${r.note}` : ""}
                </p>
              </div>
              {r.status === "pending" ? (
                <div className="flex flex-wrap items-center gap-2">
                  <input aria-label="Note" placeholder="Note (needed to reject)" value={notes[r.id] ?? ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} className="w-56 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
                  <button type="button" onClick={() => decide(r, "approve")} className={PRIMARY}>
                    Approve & issue
                  </button>
                  <button type="button" onClick={() => decide(r, "reject")} className={DANGER}>
                    Reject
                  </button>
                </div>
              ) : (
                <span className={`self-start rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${TONE[r.status]}`}>{r.status}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default CertificateRequestsPage;

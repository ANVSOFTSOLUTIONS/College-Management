import { useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const TONE = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-sky-100 text-sky-800",
  out: "bg-violet-100 text-violet-800",
  returned: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-700",
  cancelled: "bg-slate-100 text-slate-600",
};

function when(value) {
  return value ? new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—";
}

function PassesTab({ token }) {
  const [filter, setFilter] = useState("active");
  const [passes, reload, state] = useLoad(() => apiRequest("/gate/passes", { token, params: { status: filter } }), [token, filter]);
  const [notes, setNotes] = useState({});
  const [error, setError] = useState(null);

  async function act(path, body) {
    setError(null);
    try {
      await apiRequest(path, { method: "POST", token, body });
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {[["active", "Active"], ["returned", "Returned"], ["rejected", "Rejected"]].map(([v, l]) => (
          <button key={v} type="button" onClick={() => setFilter(v)} className={`rounded-lg px-3 py-1.5 text-sm font-semibold ring-1 ring-inset ${filter === v ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-700 ring-slate-300"}`}>
            {l}
          </button>
        ))}
      </div>
      <Notice error={error} />
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="gate passes" />
      ) : passes.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No gate passes.</p>
      ) : (
        <ul className="space-y-3">
          {passes.map((p) => (
            <li key={p.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-semibold text-slate-900">
                  {p.full_name} <span className="text-xs font-normal text-slate-500">({p.admission_number}, {p.batch}{p.hostel ? `, ${p.hostel}` : ""})</span>
                </p>
                <p className="text-sm text-slate-700">{p.reason}</p>
                <p className="text-xs text-slate-500">
                  {when(p.leave_at)} → {when(p.return_by)}
                  {p.went_out_at && ` · out ${when(p.went_out_at)}`}
                  {p.returned_at && ` · back ${when(p.returned_at)}`}
                  {p.note && ` · ${p.note}`}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {p.late && <span className="rounded-full bg-rose-600 px-2 py-0.5 text-xs font-bold text-white">LATE</span>}
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${TONE[p.status]}`}>{p.status}</span>
                {p.status === "pending" && (
                  <>
                    <input aria-label="Note" placeholder="Note (needed to reject)" value={notes[p.id] ?? ""} onChange={(e) => setNotes({ ...notes, [p.id]: e.target.value })} className="w-48 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
                    <button type="button" onClick={() => act(`/gate/passes/${p.id}/decide`, { approve: true, note: notes[p.id] ?? "" })} className={PRIMARY}>
                      Approve
                    </button>
                    <button type="button" onClick={() => act(`/gate/passes/${p.id}/decide`, { approve: false, note: notes[p.id] ?? "" })} className={DANGER}>
                      Reject
                    </button>
                  </>
                )}
                {p.status === "approved" && (
                  <button type="button" onClick={() => act(`/gate/passes/${p.id}/out`)} className={PRIMARY}>
                    Mark out
                  </button>
                )}
                {p.status === "out" && (
                  <button type="button" onClick={() => act(`/gate/passes/${p.id}/returned`)} className={PRIMARY}>
                    Mark returned
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const VISITOR = { name: "", phone: "", purpose: "", to_meet: "", id_proof: "", vehicle_no: "" };

function VisitorsTab({ token }) {
  const [insideOnly, setInsideOnly] = useState(true);
  const [visitors, reload, state] = useLoad(() => apiRequest("/gate/visitors", { token, params: { inside_only: insideOnly } }), [token, insideOnly]);
  const [form, setForm] = useState(VISITOR);
  const [error, setError] = useState(null);

  async function add(e) {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest("/gate/visitors", { method: "POST", token, body: form });
      setForm(VISITOR);
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={add} className="grid gap-2 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-4 md:items-end">
        {[["name", "Visitor name", true], ["phone", "Mobile"], ["purpose", "Purpose", true], ["to_meet", "To meet"], ["id_proof", "ID proof"], ["vehicle_no", "Vehicle no."]].map(([k, l, req]) => (
          <label key={k} className="text-sm font-medium text-slate-700">
            {l}
            <input required={Boolean(req)} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className={INPUT} />
          </label>
        ))}
        <button type="submit" className={`${PRIMARY} md:col-span-2`}>
          Check in visitor
        </button>
      </form>
      <Notice error={error} />
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={insideOnly} onChange={(e) => setInsideOnly(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
        Only visitors still inside (untick for today's full list)
      </label>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="visitors" />
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {visitors.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">No visitors.</li>}
          {visitors.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <div>
                <p className="font-medium text-slate-900">
                  {v.name} {v.phone && <span className="text-xs text-slate-500">{v.phone}</span>}
                </p>
                <p className="text-xs text-slate-500">
                  {v.purpose}
                  {v.to_meet && ` · meeting ${v.to_meet}`}
                  {v.vehicle_no && ` · ${v.vehicle_no}`} · in {when(v.in_at)}
                  {v.out_at && ` · out ${when(v.out_at)}`}
                </p>
              </div>
              {!v.out_at && (
                <button type="button" onClick={() => apiRequest(`/gate/visitors/${v.id}/out`, { method: "POST", token }).then(reload)} className={SECONDARY}>
                  Check out
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function GatePage() {
  const { token } = useAuth();
  const [tab, setTab] = useState("passes");
  return (
    <div className="space-y-6">
      <PageHeader title="Gate passes & visitors" subtitle="Students request gate passes in the app; approve, mark out and back in here. Parents are notified at each step." />
      <div className="inline-flex rounded-lg bg-slate-100 p-1 text-sm font-semibold">
        {[["passes", "Gate passes"], ["visitors", "Visitor register"]].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={`rounded-md px-4 py-1.5 ${tab === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>
            {label}
          </button>
        ))}
      </div>
      {tab === "passes" ? <PassesTab token={token} /> : <VisitorsTab token={token} />}
    </div>
  );
}

export default GatePage;

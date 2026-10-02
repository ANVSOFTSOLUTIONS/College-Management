import { useState } from "react";

import { errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, Stat, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const STATUS_STYLE = {
  open: "bg-amber-100 text-amber-800",
  in_progress: "bg-sky-100 text-sky-800",
  resolved: "bg-emerald-100 text-emerald-800",
  closed: "bg-slate-100 text-slate-600",
};
const STATUS_LABEL = { open: "Open", in_progress: "In progress", resolved: "Resolved", closed: "Closed" };
const CATEGORIES = ["academic", "examination", "fees", "hostel", "transport", "infrastructure", "ragging", "harassment", "other"];

function when(value) {
  return new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function Ticket({ token, id, onChange }) {
  const [ticket, reload, state] = useLoad(() => apiRequest(`/grievances/${id}`, { token }), [token, id]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function act(path, options) {
    setBusy(true);
    setError(null);
    try {
      await apiRequest(path, { token, ...options });
      setMessage("");
      reload();
      onChange();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    } finally {
      setBusy(false);
    }
  }

  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="the grievance" />;
  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-slate-500">
            {ticket.ticket_number} · {ticket.category_label} · {when(ticket.created_at)}
          </p>
          <h3 className="text-lg font-bold text-slate-900">{ticket.subject}</h3>
          <p className="text-sm text-slate-600">
            {ticket.raised_by} ({ticket.raised_by_role === "teacher" ? "faculty" : ticket.raised_by_role})
            {ticket.student_name && ticket.raised_by_role === "parent" ? ` · about ${ticket.student_name}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {ticket.priority === "high" && <span className="rounded-full bg-rose-600 px-2 py-0.5 text-xs font-bold text-white">URGENT</span>}
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[ticket.status]}`}>{STATUS_LABEL[ticket.status]}</span>
        </div>
      </div>
      <p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-800">{ticket.description}</p>
      <ul className="space-y-2">
        {ticket.replies.map((r) => (
          <li key={r.id} className={`rounded-lg p-3 text-sm ${r.from_office ? "ml-8 bg-emerald-50" : "mr-8 bg-slate-100"}`}>
            <p className="text-xs font-semibold text-slate-500">
              {r.from_office ? `Office${r.author_name ? ` · ${r.author_name}` : ""}` : r.author_name} · {when(r.created_at)}
            </p>
            <p className="whitespace-pre-wrap text-slate-800">{r.message}</p>
          </li>
        ))}
      </ul>
      <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} placeholder="Reply to the student / parent / faculty…" className={INPUT} />
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={busy || !message.trim()} onClick={() => act(`/grievances/${id}/replies`, { method: "POST", body: { message } })} className={PRIMARY}>
          Send reply
        </button>
        {ticket.status !== "resolved" && (
          <button type="button" disabled={busy} onClick={() => act(`/grievances/${id}/status`, { method: "PUT", body: { status: "resolved", note: message || null } })} className={SECONDARY}>
            Mark resolved{message.trim() ? " with this note" : ""}
          </button>
        )}
        {ticket.status !== "closed" && (
          <button type="button" disabled={busy} onClick={() => act(`/grievances/${id}/status`, { method: "PUT", body: { status: "closed", note: message || null } })} className={SECONDARY}>
            Close
          </button>
        )}
        {(ticket.status === "resolved" || ticket.status === "closed") && (
          <button type="button" disabled={busy} onClick={() => act(`/grievances/${id}/status`, { method: "PUT", body: { status: "open" } })} className={SECONDARY}>
            Reopen
          </button>
        )}
      </div>
      <Notice error={error} />
    </div>
  );
}

function GrievancesPage() {
  const { token } = useAuth();
  const [filters, setFilters] = useState({ status: "", category: "" });
  const [list, reload, state] = useLoad(
    () => apiRequest("/grievances", { token, params: { status: filters.status || null, category: filters.category || null } }),
    [token, filters.status, filters.category],
  );
  const [summary, reloadSummary] = useLoad(() => apiRequest("/grievances/summary", { token }), [token]);
  const [selected, setSelected] = useState(null);
  const refresh = () => {
    reload();
    reloadSummary();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Grievances" subtitle="Complaints raised by students, parents and faculty from the app. Ragging and harassment are marked urgent." />
      {summary && (
        <div className="grid gap-3 sm:grid-cols-5">
          <Stat label="Urgent, pending" value={summary.high_priority_open} tone={summary.high_priority_open ? "rose" : "slate"} />
          <Stat label="Open" value={summary.open} />
          <Stat label="In progress" value={summary.in_progress} />
          <Stat label="Resolved" value={summary.resolved} tone="emerald" />
          <Stat label="Closed" value={summary.closed} />
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        <select aria-label="Status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        <select aria-label="Category" value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm capitalize">
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="grievances" />
      ) : list.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No grievances.</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <ul className="divide-y divide-slate-100 self-start rounded-xl border border-slate-200 bg-white">
            {list.map((g) => (
              <li key={g.id}>
                <button type="button" onClick={() => setSelected(g.id)} className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${selected === g.id ? "bg-emerald-50" : ""}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-slate-500">
                      {g.ticket_number} · {g.category_label}
                    </span>
                    <span className="flex gap-1">
                      {g.priority === "high" && <span className="rounded-full bg-rose-600 px-2 py-0.5 text-[10px] font-bold text-white">URGENT</span>}
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_STYLE[g.status]}`}>{STATUS_LABEL[g.status]}</span>
                    </span>
                  </div>
                  <p className="truncate font-medium text-slate-900">{g.subject}</p>
                  <p className="text-xs text-slate-500">
                    {g.raised_by} · {when(g.created_at)}
                  </p>
                </button>
              </li>
            ))}
          </ul>
          {selected ? (
            <Ticket key={selected} token={token} id={selected} onChange={refresh} />
          ) : (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">Choose a grievance to read and reply.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default GrievancesPage;

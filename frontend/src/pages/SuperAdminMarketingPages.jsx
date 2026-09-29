import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import { ApiError, apiRequest } from "../lib/apiClient";

const STATUSES = [
  { id: "new", label: "New", style: "bg-amber-50 text-amber-700" },
  { id: "contacted", label: "Contacted", style: "bg-sky-50 text-sky-700" },
  { id: "converted", label: "Converted", style: "bg-emerald-50 text-emerald-700" },
  { id: "closed", label: "Closed", style: "bg-slate-100 text-slate-500" },
];

function LeadRow({ token, lead, onSaved }) {
  const [notes, setNotes] = useState(lead.notes);
  const [error, setError] = useState(null);

  async function save(changes) {
    setError(null);
    try {
      onSaved(await apiRequest(`/super-admin/leads/${lead.id}`, { method: "PATCH", token, body: changes }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
  }

  const phone = lead.phone.replace(/\D/g, "");
  const whatsapp = phone.length === 10 ? `91${phone}` : phone;
  return (
    <li className="space-y-2 px-4 py-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-semibold text-slate-900">
            {lead.institution} <span className="font-normal text-slate-500">· {lead.name}</span>
          </p>
          <p className="text-xs text-slate-500">
            {[lead.city, lead.students && `${lead.students} students`, new Date(lead.created_at).toLocaleString("en-IN")].filter(Boolean).join(" · ")}
          </p>
          {lead.message && <p className="mt-1 text-sm text-slate-700">“{lead.message}”</p>}
          <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
            <a href={`tel:${lead.phone.replace(/\s/g, "")}`} className="rounded-lg bg-slate-100 px-3 py-1.5 hover:bg-slate-200">
              📞 {lead.phone}
            </a>
            <a href={`https://wa.me/${whatsapp}`} target="_blank" rel="noreferrer" className="rounded-lg bg-[#25D366]/15 px-3 py-1.5 text-emerald-800 hover:bg-[#25D366]/25">
              WhatsApp
            </a>
            {lead.email && (
              <a href={`mailto:${lead.email}`} className="rounded-lg bg-slate-100 px-3 py-1.5 hover:bg-slate-200">
                ✉ {lead.email}
              </a>
            )}
          </div>
        </div>
        <select aria-label="Status" value={lead.status} onChange={(e) => save({ status: e.target.value })} className={`self-start rounded-lg border-0 px-3 py-1.5 text-xs font-bold ${STATUSES.find((s) => s.id === lead.status).style}`}>
          {STATUSES.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-2">
        <input aria-label="Notes" placeholder="Follow-up notes" value={notes} onChange={(e) => setNotes(e.target.value)} className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
        {notes !== lead.notes && (
          <button type="button" onClick={() => save({ notes })} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white">
            Save
          </button>
        )}
      </div>
      {error && <p className="text-xs text-rose-600">{error}</p>}
    </li>
  );
}

export function LeadsPage() {
  const { token } = useAuth();
  const [state, setState] = useState("loading");
  const [leads, setLeads] = useState([]);
  const [filter, setFilter] = useState("all");

  const load = useCallback(async () => {
    try {
      setLeads(await apiRequest("/super-admin/leads", { token }));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const shown = filter === "all" ? leads : leads.filter((l) => l.status === filter);
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Demo requests</h2>
        <p className="mt-1 text-sm text-slate-500">From the "Book a demo" form on your landing page.</p>
      </div>
      <div className="flex flex-wrap gap-2 text-sm">
        {[{ id: "all", label: "All" }, ...STATUSES].map((s) => (
          <button key={s.id} type="button" onClick={() => setFilter(s.id)} className={`rounded-full px-3 py-1 font-semibold ${filter === s.id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>
            {s.label} ({s.id === "all" ? leads.length : leads.filter((l) => l.status === s.id).length})
          </button>
        ))}
      </div>
      {state === "loading" && <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load leads.</p>}
      {state === "ready" && shown.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No demo requests yet. Share your landing page link to get some!</p>
      )}
      {state === "ready" && shown.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {shown.map((lead) => (
            <LeadRow key={lead.id} token={token} lead={lead} onSaved={(updated) => setLeads((prev) => prev.map((l) => (l.id === updated.id ? updated : l)))} />
          ))}
        </ul>
      )}
    </div>
  );
}

export function LandingSettingsPage() {
  const { token } = useAuth();
  const [form, setForm] = useState(null);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    apiRequest("/super-admin/platform-settings", { token })
      .then(setForm)
      .catch(() => setError("Couldn't load settings."));
  }, [token]);

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      setForm(await apiRequest("/super-admin/platform-settings", { method: "PUT", token, body: form }));
      setState("saved");
    } catch (err) {
      setState("error");
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
  }

  if (!form) return error ? <p className="text-sm text-rose-700">{error}</p> : <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  const landing = window.location.origin + "/";
  return (
    <div className="max-w-xl space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Landing page</h2>
        <p className="mt-1 text-sm text-slate-500">
          Your marketing page is live at{" "}
          <a href={landing} target="_blank" rel="noreferrer" className="font-semibold text-emerald-700 hover:underline">
            {landing}
          </a>
          . Contact details below appear on it; leave any blank to hide it.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        {[
          ["whatsapp_number", "WhatsApp number (with country code, e.g. 919876543210)", "tel"],
          ["phone", "Phone number", "tel"],
          ["email", "Email", "email"],
        ].map(([key, label, type]) => (
          <div key={key}>
            <label htmlFor={`ps-${key}`} className="block text-sm font-medium text-slate-700">
              {label}
            </label>
            <input
              id={`ps-${key}`}
              type={type}
              value={form[key]}
              onChange={(e) => {
                setForm({ ...form, [key]: e.target.value });
                setState("idle");
              }}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        ))}
        <div className="flex items-center gap-3">
          <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {state === "saving" ? "Saving…" : "Save"}
          </button>
          {state === "saved" && <span className="text-sm font-medium text-emerald-700">Saved — live on the landing page.</span>}
          {error && <span className="text-sm text-rose-600">{error}</span>}
        </div>
      </form>
    </div>
  );
}

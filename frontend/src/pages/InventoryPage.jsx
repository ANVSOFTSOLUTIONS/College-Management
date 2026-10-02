import { useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const KINDS = [
  ["in", "Received (add stock)"],
  ["issue", "Issue to someone"],
  ["return", "Returned"],
  ["out", "Used up"],
  ["damaged", "Damaged / written off"],
];
const BLANK = { name: "", category: "", location: "", unit: "nos", quantity: 0, min_quantity: 0, notes: "" };

function Movement({ token, item, onDone }) {
  const [form, setForm] = useState({ kind: "in", quantity: 1, person: "", note: "" });
  const [history, reload] = useLoad(() => apiRequest(`/inventory/items/${item.id}/movements`, { token }), [token, item.id]);
  const [error, setError] = useState(null);

  async function save(e) {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest(`/inventory/items/${item.id}/movements`, { method: "POST", token, body: { ...form, quantity: Number(form.quantity) } });
      setForm({ ...form, quantity: 1, person: "", note: "" });
      reload();
      onDone();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <div className="space-y-3 bg-slate-50 p-4">
      <form onSubmit={save} className="grid gap-2 md:grid-cols-5 md:items-end">
        <select aria-label="Movement" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className={INPUT}>
          {KINDS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        <input aria-label="Quantity" type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} className={INPUT} />
        <input aria-label="Person" placeholder={form.kind === "issue" ? "Issued to (required)" : "Person (optional)"} value={form.person} onChange={(e) => setForm({ ...form, person: e.target.value })} className={INPUT} />
        <input aria-label="Note" placeholder="Note / bill no." value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className={INPUT} />
        <button type="submit" className={PRIMARY}>
          Save
        </button>
      </form>
      <Notice error={error} />
      <ul className="max-h-48 space-y-1 overflow-y-auto text-xs text-slate-600">
        {(history ?? []).map((h) => (
          <li key={h.id}>
            {new Date(h.created_at).toLocaleString("en-IN")} · <b>{KINDS.find(([v]) => v === h.kind)?.[1] ?? h.kind}</b> {h.quantity} {item.unit}
            {h.person && ` · ${h.person}`}
            {h.note && ` · ${h.note}`}
            {h.by_name && ` · by ${h.by_name}`}
          </li>
        ))}
      </ul>
    </div>
  );
}

function InventoryPage() {
  const { token } = useAuth();
  const [filters, setFilters] = useState({ q: "", low_only: false });
  const [items, reload, state] = useLoad(() => apiRequest("/inventory/items", { token, params: { q: filters.q || null, low_only: filters.low_only } }), [token, filters.q, filters.low_only]);
  const [form, setForm] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState(null);

  async function save(e) {
    e.preventDefault();
    setError(null);
    try {
      if (form.id) {
        const { name, category, location, unit, min_quantity, notes } = form;
        await apiRequest(`/inventory/items/${form.id}`, { method: "PUT", token, body: { name, category, location, unit, min_quantity: Number(min_quantity), notes } });
      } else {
        await apiRequest("/inventory/items", { method: "POST", token, body: { ...form, quantity: Number(form.quantity), min_quantity: Number(form.min_quantity) } });
      }
      setForm(null);
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  async function remove(item) {
    if (!window.confirm(`Delete ${item.name} and its history?`)) return;
    await apiRequest(`/inventory/items/${item.id}`, { method: "DELETE", token });
    reload();
  }

  const field = (key, label, props = {}) => (
    <label className="text-sm font-medium text-slate-700">
      {label}
      <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </label>
  );
  return (
    <div className="space-y-6">
      <PageHeader title="Inventory" subtitle="Lab equipment, furniture, sports goods and consumables, with issue / return history and low-stock alerts.">
        <button type="button" onClick={() => setForm({ ...BLANK })} className={PRIMARY}>
          + Add item
        </button>
      </PageHeader>
      {form && (
        <form onSubmit={save} className="grid gap-3 rounded-xl border border-emerald-200 bg-emerald-50/40 p-4 md:grid-cols-4">
          {field("name", "Item", { required: true })}
          {field("category", "Category", { placeholder: "Lab, Sports, Furniture…" })}
          {field("location", "Location", { placeholder: "Chemistry lab" })}
          {field("unit", "Unit", { required: true })}
          {!form.id && field("quantity", "Opening stock", { type: "number", min: 0 })}
          {field("min_quantity", "Alert when at or below", { type: "number", min: 0 })}
          <div className="md:col-span-2">{field("notes", "Notes")}</div>
          <div className="flex gap-2 md:col-span-4">
            <button type="submit" className={PRIMARY}>
              Save
            </button>
            <button type="button" onClick={() => setForm(null)} className={SECONDARY}>
              Cancel
            </button>
          </div>
        </form>
      )}
      <Notice error={error} />
      <div className="flex flex-wrap items-center gap-3">
        <input aria-label="Search" placeholder="Search item or location" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={filters.low_only} onChange={(e) => setFilters({ ...filters, low_only: e.target.checked })} className="rounded border-slate-300 text-rose-600" />
          Low stock only
        </label>
      </div>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="inventory" />
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No items.</p>
      ) : (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {items.map((i) => (
            <li key={i.id}>
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <div>
                  <p className="font-medium text-slate-900">
                    {i.name} {i.low_stock && <span className="ml-1 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">LOW STOCK</span>}
                  </p>
                  <p className="text-xs text-slate-500">{[i.category, i.location].filter(Boolean).join(" · ")}</p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span>
                    Stock <b>{i.quantity}</b> {i.unit}
                  </span>
                  <span className="text-slate-500">
                    issued {i.issued} · available <b className="text-emerald-700">{i.available}</b>
                  </span>
                  <button type="button" onClick={() => setOpen(open === i.id ? null : i.id)} className={SECONDARY}>
                    Stock in / out
                  </button>
                  <button type="button" onClick={() => setForm({ ...i })} className={SECONDARY}>
                    Edit
                  </button>
                  <button type="button" onClick={() => remove(i)} className={DANGER}>
                    Delete
                  </button>
                </div>
              </div>
              {open === i.id && <Movement token={token} item={i} onDone={reload} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default InventoryPage;

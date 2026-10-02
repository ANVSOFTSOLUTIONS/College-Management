import { useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const STATUSES = {
  unknown: "Not known",
  employed: "Employed",
  higher_studies: "Higher studies",
  self_employed: "Self-employed / business",
  competitive_exams: "Preparing for exams",
  other: "Other",
};
const BLANK = { full_name: "", admission_number: "", passing_year: "", program: "", email: "", phone: "", status: "unknown", organisation: "", designation: "", location: "", notes: "" };

function Editor({ token, initial, onDone }) {
  const [form, setForm] = useState({ ...BLANK, ...initial });
  const [error, setError] = useState(null);
  const field = (key, label, props = {}) => (
    <label className="text-sm font-medium text-slate-700">
      {label}
      <input value={form[key] ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </label>
  );

  async function save(e) {
    e.preventDefault();
    setError(null);
    const body = Object.fromEntries(Object.keys(BLANK).map((k) => [k, form[k] ?? ""]));
    try {
      await apiRequest(initial.id ? `/alumni/${initial.id}` : "/alumni", { method: initial.id ? "PUT" : "POST", token, body });
      onDone();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <form onSubmit={save} className="grid gap-3 rounded-xl border border-emerald-200 bg-emerald-50/40 p-4 md:grid-cols-4">
      {field("full_name", "Name", { required: true })}
      {field("admission_number", "Roll no.")}
      {field("passing_year", "Passing year", { required: true })}
      {field("program", "Programme")}
      <label className="text-sm font-medium text-slate-700">
        Now
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className={INPUT}>
          {Object.entries(STATUSES).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      {field("organisation", "Company / university")}
      {field("designation", "Role / course")}
      {field("location", "City")}
      {field("email", "Email", { type: "email" })}
      {field("phone", "Mobile", { maxLength: 15 })}
      <div className="md:col-span-2">{field("notes", "Notes")}</div>
      <div className="flex gap-2 md:col-span-4">
        <button type="submit" className={PRIMARY}>
          Save
        </button>
        <button type="button" onClick={onDone} className={SECONDARY}>
          Cancel
        </button>
      </div>
      <div className="md:col-span-4">
        <Notice error={error} />
      </div>
    </form>
  );
}

function AlumniPage() {
  const { token } = useAuth();
  const [filters, setFilters] = useState({ passing_year: "", status: "", q: "" });
  const [rows, reload, state] = useLoad(
    () => apiRequest("/alumni", { token, params: { passing_year: filters.passing_year || null, status: filters.status || null, q: filters.q || null } }),
    [token, filters.passing_year, filters.status, filters.q],
  );
  const [summary, reloadSummary] = useLoad(() => apiRequest("/alumni/summary", { token }), [token]);
  const [editing, setEditing] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const refresh = () => {
    setEditing(null);
    reload();
    reloadSummary();
  };

  async function importGraduated() {
    setError(null);
    try {
      const r = await apiRequest("/alumni/import-graduated", { method: "POST", token });
      setMessage(r.added ? `${r.added} passed-out students added.` : "Everyone who passed out is already in the list.");
      refresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't import."));
    }
  }

  async function remove(a) {
    if (!window.confirm(`Remove ${a.full_name} from alumni?`)) return;
    await apiRequest(`/alumni/${a.id}`, { method: "DELETE", token });
    refresh();
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Alumni" subtitle="Passed-out students and what they do now. Feeds the NAAC report (criterion 5.4).">
        <button type="button" onClick={importGraduated} className={SECONDARY}>
          Add passed-out students
        </button>
        <button type="button" onClick={() => setEditing({})} className={PRIMARY}>
          + Add alumnus
        </button>
      </PageHeader>
      {summary?.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {summary.map((s) => (
            <div key={s.passing_year} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm">
              <p className="font-semibold text-slate-900">
                {s.passing_year} · {s.total} alumni
              </p>
              <p className="text-xs text-slate-500">
                {s.employed} employed · {s.higher_studies} higher studies · {s.self_employed} self-employed · {s.unknown} not known
              </p>
            </div>
          ))}
        </div>
      )}
      <Notice message={message} error={error} />
      {editing && <Editor token={token} initial={editing} onDone={refresh} />}
      <div className="flex flex-wrap gap-3">
        <input aria-label="Search" placeholder="Search name, company, roll no." value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input aria-label="Passing year" placeholder="Year" value={filters.passing_year} onChange={(e) => setFilters({ ...filters, passing_year: e.target.value })} className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select aria-label="Status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="">Everyone</option>
          {Object.entries(STATUSES).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="alumni" />
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No alumni yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Batch</th>
                <th className="px-3 py-2">Now</th>
                <th className="px-3 py-2">Contact</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((a) => (
                <tr key={a.id}>
                  <td className="px-3 py-2">
                    <p className="font-medium text-slate-900">{a.full_name}</p>
                    <p className="text-xs text-slate-500">{a.admission_number}</p>
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {a.passing_year} · {a.program}
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    <p className="font-medium">{a.status_label}</p>
                    <p className="text-xs text-slate-500">{[a.designation, a.organisation, a.location].filter(Boolean).join(", ")}</p>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">
                    {a.phone}
                    {a.phone && a.email && <br />}
                    {a.email}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button type="button" onClick={() => setEditing(a)} className={SECONDARY}>
                      Edit
                    </button>{" "}
                    <button type="button" onClick={() => remove(a)} className={DANGER}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default AlumniPage;

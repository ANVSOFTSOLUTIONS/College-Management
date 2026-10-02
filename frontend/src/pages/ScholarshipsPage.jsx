import { useState } from "react";

import { errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, rupees, StudentPicker, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

const STATUSES = ["applied", "verified", "sanctioned", "disbursed", "rejected"];
const TONE = {
  applied: "bg-slate-100 text-slate-700",
  verified: "bg-sky-100 text-sky-800",
  sanctioned: "bg-amber-100 text-amber-800",
  disbursed: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-700",
};
const SCHEMES = ["Vidya Deevena (fee reimbursement)", "Vasathi Deevena (hostel & food)", "Post-matric scholarship (SC/ST/BC)", "Minority scholarship", "Merit scholarship"];

function thisYear() {
  const d = new Date();
  const start = d.getMonth() >= 5 ? d.getFullYear() : d.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

function AddForm({ token, onSaved }) {
  const [student, setStudent] = useState(null);
  const [form, setForm] = useState({ scheme: SCHEMES[0], academic_year: thisYear(), application_no: "", amount_sanctioned: "" });
  const [error, setError] = useState(null);

  async function save(e) {
    e.preventDefault();
    setError(null);
    try {
      await apiRequest("/scholarships", { method: "POST", token, body: { ...form, student_id: student.id, amount_sanctioned: form.amount_sanctioned || "0" } });
      setStudent(null);
      setForm({ ...form, application_no: "", amount_sanctioned: "" });
      onSaved();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  return (
    <form onSubmit={save} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-6 md:items-end">
      <div className="md:col-span-2">
        <p className="text-sm font-medium text-slate-700">Student</p>
        {student ? (
          <p className="mt-1 rounded-lg bg-emerald-50 px-3 py-2 text-sm">
            {student.full_name} ({student.admission_number}){" "}
            <button type="button" onClick={() => setStudent(null)} className="text-xs text-rose-600">
              change
            </button>
          </p>
        ) : (
          <StudentPicker token={token} id="scholarship-student" onChange={setStudent} />
        )}
      </div>
      <label className="text-sm font-medium text-slate-700 md:col-span-2">
        Scheme
        <input list="schemes" required value={form.scheme} onChange={(e) => setForm({ ...form, scheme: e.target.value })} className={INPUT} />
        <datalist id="schemes">
          {SCHEMES.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </label>
      <label className="text-sm font-medium text-slate-700">
        Year
        <input required value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className={INPUT} />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Application no.
        <input value={form.application_no} onChange={(e) => setForm({ ...form, application_no: e.target.value })} className={INPUT} />
      </label>
      <label className="text-sm font-medium text-slate-700">
        Sanctioned ₹
        <input type="number" min="0" value={form.amount_sanctioned} onChange={(e) => setForm({ ...form, amount_sanctioned: e.target.value })} className={INPUT} />
      </label>
      <button type="submit" disabled={!student} className={PRIMARY}>
        Add
      </button>
      <div className="md:col-span-6">
        <Notice error={error} />
      </div>
    </form>
  );
}

function ScholarshipsPage() {
  const { token } = useAuth();
  const [filters, setFilters] = useState({ academic_year: thisYear(), status: "" });
  const params = { academic_year: filters.academic_year || null, status: filters.status || null };
  const [rows, reload, state] = useLoad(() => apiRequest("/scholarships", { token, params }), [token, filters.academic_year, filters.status]);
  const [summary, reloadSummary] = useLoad(() => apiRequest("/scholarships/summary", { token, params: { academic_year: filters.academic_year || null } }), [token, filters.academic_year]);
  const [error, setError] = useState(null);

  async function update(id, body) {
    setError(null);
    try {
      await apiRequest(`/scholarships/${id}`, { method: "PUT", token, body });
      reload();
      reloadSummary();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  const refresh = () => {
    reload();
    reloadSummary();
  };
  return (
    <div className="space-y-6">
      <PageHeader title="Scholarships" subtitle="Track government scholarships per student: applied → verified → sanctioned → disbursed. Students see their status in the app." />
      {summary?.length > 0 && (
        <div className="grid gap-3 md:grid-cols-3">
          {summary.map((s) => (
            <div key={s.scheme} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <p className="text-sm font-semibold text-slate-900">{s.scheme}</p>
              <p className="text-xs text-slate-500">
                {s.students} students · {s.pending} pending
              </p>
              <p className="mt-1 text-sm">
                Sanctioned <b>{rupees(s.sanctioned)}</b> · Received <b className="text-emerald-700">{rupees(s.received)}</b>
              </p>
            </div>
          ))}
        </div>
      )}
      <AddForm token={token} onSaved={refresh} />
      <div className="flex flex-wrap gap-3">
        <input aria-label="Academic year" placeholder="Year" value={filters.academic_year} onChange={(e) => setFilters({ ...filters, academic_year: e.target.value })} className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select aria-label="Status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2 text-sm capitalize">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <Notice error={error} />
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="scholarships" />
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No scholarship records.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Student</th>
                <th className="px-3 py-2">Scheme</th>
                <th className="px-3 py-2">Application</th>
                <th className="px-3 py-2">Sanctioned ₹</th>
                <th className="px-3 py-2">Received ₹</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="px-3 py-2">
                    <p className="font-medium text-slate-900">{r.full_name}</p>
                    <p className="text-xs text-slate-500">
                      {r.admission_number} · {r.batch}
                    </p>
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {r.scheme}
                    <p className="text-xs text-slate-400">{r.academic_year}</p>
                  </td>
                  <td className="px-3 py-2 text-slate-700">{r.application_no || "—"}</td>
                  <td className="px-3 py-2">
                    <input aria-label="Sanctioned" type="number" min="0" defaultValue={r.amount_sanctioned} onBlur={(e) => Number(e.target.value) !== r.amount_sanctioned && update(r.id, { amount_sanctioned: e.target.value || "0" })} className="w-24 rounded border border-slate-300 px-2 py-1" />
                  </td>
                  <td className="px-3 py-2">
                    <input aria-label="Received" type="number" min="0" defaultValue={r.amount_received} onBlur={(e) => Number(e.target.value) !== r.amount_received && update(r.id, { amount_received: e.target.value || "0" })} className="w-24 rounded border border-slate-300 px-2 py-1" />
                  </td>
                  <td className="px-3 py-2">
                    <select aria-label="Status" value={r.status} onChange={(e) => update(r.id, { status: e.target.value })} className={`rounded px-2 py-1 text-xs font-semibold capitalize ${TONE[r.status]}`}>
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
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

export default ScholarshipsPage;

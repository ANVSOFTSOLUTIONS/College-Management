import { useState } from "react";

import { downloadExcel } from "../api/reportsApi";
import { LoadState, Notice, PageHeader, PRIMARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

function show(value) {
  return value === null || value === undefined || value === "" ? "—" : value;
}

function NaacPage() {
  const { token } = useAuth();
  const [report, reload, state] = useLoad(() => apiRequest("/reports/naac", { token }), [token]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      await downloadExcel(token, "/reports/naac.xlsx", {}, "naac-aishe-data.xlsx");
    } catch {
      setError("Couldn't download the Excel file.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="NAAC / AISHE data" subtitle="Numbers for accreditation and AISHE forms, built from your ERP data. Each table shows the NAAC criterion it supports.">
        <button type="button" onClick={download} disabled={busy || state !== "ready"} className={PRIMARY}>
          {busy ? "Preparing…" : "Download Excel"}
        </button>
      </PageHeader>
      <Notice error={error} />
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="the report" />
      ) : (
        <>
          <p className="text-sm text-slate-500">
            {report.college_name} · as of {report.generated_on} · current batches only. Set gender and social category on student records for complete AISHE numbers.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {report.metrics.map((m) => (
              <div key={m.label} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <p className="text-xs font-medium text-slate-500">{m.label}</p>
                <p className="text-xl font-bold text-slate-900">{show(m.value)}</p>
              </div>
            ))}
          </div>
          {report.tables.map((t) => (
            <section key={t.key} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <h3 className="font-semibold text-slate-900">{t.title}</h3>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">Criterion {t.criterion}</span>
              </div>
              {t.rows.length === 0 ? (
                <p className="px-4 py-6 text-sm text-slate-500">No data yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                      <tr>
                        {t.headers.map((h) => (
                          <th key={h} className="px-3 py-2">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {t.rows.map((row, i) => (
                        <tr key={i}>
                          {row.map((cell, j) => (
                            <td key={j} className={`px-3 py-2 ${j === 0 ? "font-medium text-slate-900" : "text-slate-700"}`}>
                              {show(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </>
      )}
    </div>
  );
}

export default NaacPage;

import { useRef, useState } from "react";

import { ApiError, apiBlob, apiUpload } from "../lib/apiClient";

async function downloadTemplate(token) {
  const blob = await apiBlob("/students/import/template", { token });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "students-import-template.xlsx";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function upload(token, file, { dryRun, skipInvalid }) {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload(`/students/import?dry_run=${dryRun}&skip_invalid=${skipInvalid}`, { token, formData });
}

// Excel bulk import: download template → upload → check every row → import.
function StudentImport({ token, onImported, onClose }) {
  const [file, setFile] = useState(null);
  const [check, setCheck] = useState(null);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  async function run(action) {
    setError(null);
    setState(action);
    try {
      if (action === "template") {
        await downloadTemplate(token);
      } else if (action === "checking") {
        setCheck(await upload(token, file, { dryRun: true, skipInvalid: false }));
      } else {
        const result = await upload(token, file, { dryRun: false, skipInvalid: check.invalid > 0 });
        onImported(result.imported);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setState("idle");
    }
  }

  const problems = check?.rows.filter((r) => r.errors.length) ?? [];
  return (
    <section className="space-y-4 rounded-xl border border-emerald-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Import students from Excel</h3>
          <p className="text-sm text-slate-500">Add a whole college at once, with parents&apos; details. Nothing is saved until you confirm.</p>
        </div>
        <button type="button" onClick={onClose} className="rounded-lg px-2 text-xl text-slate-400 hover:text-slate-700" aria-label="Close">
          ×
        </button>
      </div>

      <ol className="space-y-3 text-sm">
        <li className="flex flex-wrap items-center gap-3">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white">1</span>
          <button type="button" disabled={state !== "idle"} onClick={() => run("template")} className="rounded-lg px-3 py-1.5 font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60">
            {state === "template" ? "Downloading…" : "Download the Excel template"}
          </button>
          <span className="text-slate-500">It lists your classes; fill one student per row.</span>
        </li>
        <li className="flex flex-wrap items-center gap-3">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white">2</span>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setCheck(null);
            }}
            className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:font-semibold"
          />
          <button type="button" disabled={!file || state !== "idle"} onClick={() => run("checking")} className="rounded-lg bg-slate-900 px-3 py-1.5 font-semibold text-white disabled:opacity-50">
            {state === "checking" ? "Checking…" : "Check file"}
          </button>
        </li>
      </ol>

      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}

      {check && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-3 text-sm">
            <span className="rounded-lg bg-slate-100 px-3 py-1.5 font-semibold">{check.total} rows</span>
            <span className="rounded-lg bg-emerald-50 px-3 py-1.5 font-semibold text-emerald-700">✓ {check.valid} ready</span>
            {check.invalid > 0 && <span className="rounded-lg bg-rose-50 px-3 py-1.5 font-semibold text-rose-700">✗ {check.invalid} need fixing</span>}
          </div>
          {problems.length > 0 && (
            <div className="max-h-72 overflow-auto rounded-lg border border-rose-200">
              <table className="min-w-full text-left text-sm">
                <thead className="sticky top-0 bg-rose-50 text-xs font-semibold uppercase text-rose-800">
                  <tr>
                    <th className="px-3 py-2">Row</th>
                    <th className="px-3 py-2">Student</th>
                    <th className="px-3 py-2">Problem</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rose-100">
                  {problems.map((r) => (
                    <tr key={r.row}>
                      <td className="px-3 py-2 font-mono text-xs">{r.row}</td>
                      <td className="px-3 py-2">
                        {r.full_name || "—"} <span className="text-xs text-slate-400">{r.admission_number}</span>
                      </td>
                      <td className="px-3 py-2 text-rose-700">{r.errors.join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {check.valid > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" disabled={state !== "idle"} onClick={() => run("importing")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
                {state === "importing" ? "Importing…" : check.invalid ? `Import ${check.valid} students, skip ${check.invalid}` : `Import ${check.valid} students`}
              </button>
              {check.invalid > 0 && <span className="text-xs text-slate-500">Or fix the rows above in Excel and check the file again.</span>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default StudentImport;

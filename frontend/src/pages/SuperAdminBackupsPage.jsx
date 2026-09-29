import { useCallback, useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import { ApiError, apiBlob, apiRequest } from "../lib/apiClient";

function size(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

async function download(token, name) {
  const blob = await apiBlob(`/super-admin/backups/${encodeURIComponent(name)}`, { token });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function SuperAdminBackupsPage() {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState(null);

  const load = useCallback(async () => {
    try {
      setData(await apiRequest("/super-admin/backups", { token }));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function backUp(kind) {
    setBusy(kind);
    setMessage(null);
    try {
      const result = await apiRequest("/super-admin/backups", { method: "POST", token, params: { kind } });
      setMessage({ ok: true, text: `Backed up: ${result.created.map((b) => `${b.name} (${size(b.size_bytes)})`).join(", ")}.` });
      await load();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : "The backup failed." });
    }
    setBusy(null);
  }

  if (state === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load backups.</p>;

  const age = data.last_db_hours_ago;
  const stale = age === null || age > 36;
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Backups</h2>
        <p className="mt-1 text-sm text-slate-500">
          Every college&apos;s data: a database backup daily and uploaded files weekly, kept for two weeks. Download one now and then and keep it off this server.
        </p>
      </div>

      <div className={`rounded-xl border px-4 py-3 text-sm ${stale ? "border-rose-200 bg-rose-50 text-rose-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`} role="status">
        {age === null
          ? "No database backup yet. Back up now, and set up the daily schedule (docs/BACKUPS.md)."
          : stale
            ? `The last database backup is ${Math.round(age)} hours old. Check the daily schedule (docs/BACKUPS.md).`
            : `Last database backup: ${age < 1 ? "less than an hour" : `${Math.round(age)} hours`} ago.`}
      </div>

      <div className="flex flex-wrap gap-3">
        <button type="button" disabled={busy !== null} onClick={() => backUp("db")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {busy === "db" ? "Backing up…" : "Back up database now"}
        </button>
        <button type="button" disabled={busy !== null} onClick={() => backUp("files")} className="rounded-lg px-4 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60">
          {busy === "files" ? "Backing up…" : "Back up uploaded files now"}
        </button>
      </div>
      {message && <p className={`rounded-lg px-3 py-2 text-sm font-medium ${message.ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-700"}`}>{message.text}</p>}

      {data.backups.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No backups yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {data.backups.map((b) => (
            <li key={b.name} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
              <span>
                <span className="font-mono text-xs text-slate-800">{b.name}</span>
                <span className="block text-xs text-slate-500">
                  {b.kind === "db" ? "Database" : "Uploaded files"} · {size(b.size_bytes)} · {new Date(b.created_at).toLocaleString("en-IN")}
                </span>
              </span>
              <button type="button" onClick={() => download(token, b.name).catch(() => setMessage({ ok: false, text: "Download failed." }))} className="font-semibold text-emerald-700 hover:underline">
                Download
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-slate-400">Stored on the server in {data.directory}.</p>
    </div>
  );
}

export default SuperAdminBackupsPage;

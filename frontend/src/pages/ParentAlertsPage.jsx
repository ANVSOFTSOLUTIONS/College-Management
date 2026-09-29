import { useCallback, useEffect, useState } from "react";

import { fetchMyClasses } from "../api/attendanceApi";
import { fetchAlertSettings, fetchParentAlerts } from "../api/teachingApi";
import { ALERT_STATUS_LABELS } from "../components/Remarks";
import { useAuth } from "../context/AuthContext";

const STATUS_STYLES = {
  sent: "bg-emerald-50 text-emerald-700",
  failed: "bg-rose-50 text-rose-700",
  not_sent: "bg-slate-100 text-slate-600",
};

function ParentAlertsPage() {
  const { token, user } = useAuth();
  const [settings, setSettings] = useState(null);
  const [classes, setClasses] = useState([]);
  const [classFilter, setClassFilter] = useState("");
  const [state, setState] = useState("loading");
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    fetchAlertSettings(token).then(setSettings).catch(() => setSettings(null));
    fetchMyClasses(token).then(setClasses).catch(() => setClasses([]));
  }, [token]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setAlerts(await fetchParentAlerts(token, { classId: classFilter || undefined }));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, classFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Parent Alerts</h2>
        <p className="mt-1 text-sm text-slate-500">
          {user.role === "admin" ? "Every alert sent to parents." : "Alerts for the classes you are class teacher of."} Absences marked for today and remarks marked
          &quot;tell the parent&quot; create an alert to the student&apos;s primary contact.
        </p>
      </div>

      {settings && !settings.sms_enabled && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span className="font-semibold">SMS sending is off.</span> Alerts are recorded here but not sent yet. They start going out once the college&apos;s SMS
          provider is set up.
        </div>
      )}

      <select
        aria-label="Filter by class"
        value={classFilter}
        onChange={(e) => setClassFilter(e.target.value)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
      >
        <option value="">All classes</option>
        {classes.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} - {c.section}
          </option>
        ))}
      </select>

      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && (
        <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-800">
          Couldn&apos;t load alerts.
          <button type="button" onClick={load} className="underline">
            Retry
          </button>
        </div>
      )}
      {state === "ready" && alerts.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm font-semibold text-slate-600">No parent alerts yet.</div>
      )}
      {state === "ready" && alerts.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {alerts.map((alert) => (
            <li key={alert.id} className="space-y-1 px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-slate-800">{alert.student_name}</span>
                <span className="text-xs text-slate-400">
                  {alert.class_name} - {alert.section} · {alert.kind === "absence" ? "Absence" : "Remark"}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[alert.status]}`}>
                  {alert.status === "not_sent" ? "Not sent" : ALERT_STATUS_LABELS[alert.status]}
                </span>
              </div>
              <p className="text-slate-700">{alert.message}</p>
              <p className="text-xs text-slate-400">
                {new Date(alert.created_at).toLocaleString()} · To {alert.recipient_name || "—"} {alert.recipient_phone}
                {alert.status_detail && ` · ${alert.status_detail}`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ParentAlertsPage;

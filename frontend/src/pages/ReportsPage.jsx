import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchPostingOptions } from "../api/boardApi";
import { formatRupees } from "../api/feesApi";
import { downloadExcel, fetchFeeReport, fetchStaffAttendanceReport, fetchStudentAttendanceReport } from "../api/reportsApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const LOW = 75;

function localIso(d) {
  return d.toLocaleDateString("en-CA");
}

function Summary({ items }) {
  return (
    <div className="flex flex-wrap gap-3 text-sm">
      {items.map(([label, value, tone]) => (
        <span key={label} className={`rounded-lg px-3 py-1.5 ${tone ?? "bg-slate-100 text-slate-700"}`}>
          {label}: <span className="font-semibold">{value}</span>
        </span>
      ))}
    </div>
  );
}

function ExcelButton({ onClick }) {
  const [state, setState] = useState("idle");
  return (
    <button
      type="button"
      disabled={state === "busy"}
      onClick={async () => {
        setState("busy");
        try {
          await onClick();
          setState("idle");
        } catch {
          setState("error");
        }
      }}
      className="rounded-lg px-3 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50 disabled:opacity-60"
    >
      {state === "busy" ? "Preparing…" : state === "error" ? "Download failed, retry" : "⬇ Download Excel"}
    </button>
  );
}

function Table({ headers, rows, empty }) {
  if (rows.length === 0) return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">{empty}</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
          <tr>
            {headers.map(([label, align]) => (
              <th key={label} className={`whitespace-nowrap px-3 py-2 ${align === "right" ? "text-right" : ""}`}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{rows}</tbody>
      </table>
    </div>
  );
}

function StudentAttendanceReport({ token, isAdmin }) {
  const today = new Date();
  const [filters, setFilters] = useState({ start: localIso(new Date(today.getFullYear(), today.getMonth(), 1)), end: localIso(today), class_id: "" });
  const [classes, setClasses] = useState([]);
  const [lowOnly, setLowOnly] = useState(false);
  const [report, setReport] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isAdmin) fetchPostingOptions(token).then(setClasses).catch(() => setClasses([]));
  }, [token, isAdmin]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setReport(await fetchStudentAttendanceReport(token, { ...filters, class_id: filters.class_id || undefined }));
      setState("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load the report.");
      setState("error");
    }
  }, [token, filters]);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => (report?.rows ?? []).filter((r) => !lowOnly || (r.percent !== null && r.percent < LOW)), [report, lowOnly]);
  const lowCount = (report?.rows ?? []).filter((r) => r.percent !== null && r.percent < LOW).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-slate-700">
          From
          <input type="date" value={filters.start} max={filters.end} onChange={(e) => setFilters({ ...filters, start: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          To
          <input type="date" value={filters.end} min={filters.start} onChange={(e) => setFilters({ ...filters, end: e.target.value })} className={INPUT} />
        </label>
        {isAdmin && (
          <label className="text-sm font-medium text-slate-700">
            Class
            <select value={filters.class_id} onChange={(e) => setFilters({ ...filters, class_id: e.target.value })} className={INPUT}>
              <option value="">All classes</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} - {c.section}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
          <input type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
          Only below {LOW}%
        </label>
        <ExcelButton
          onClick={() =>
            downloadExcel(token, "/reports/student-attendance", { ...filters, format: "xlsx" }, `student-attendance-${filters.start}-to-${filters.end}.xlsx`)
          }
        />
      </div>
      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">{error}</p>}
      {state === "ready" && (
        <>
          <Summary
            items={[
              ["Days attendance taken", report.working_days],
              ["Average attendance", report.average_percent === null ? "—" : `${report.average_percent}%`],
              [`Students below ${LOW}%`, lowCount, lowCount ? "bg-rose-50 text-rose-800" : undefined],
            ]}
          />
          <Table
            empty={isAdmin ? "No students in this selection." : "You aren't a class teacher this year."}
            headers={[["Student"], ["Class"], ["Present", "right"], ["Late", "right"], ["Absent", "right"], ["Attendance", "right"]]}
            rows={rows.map((r) => (
              <tr key={r.student_id}>
                <td className="px-3 py-2">
                  <span className="font-medium text-slate-900">{r.full_name}</span> <span className="text-xs text-slate-400">{r.admission_number}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                  {r.class_name} - {r.section}
                </td>
                <td className="px-3 py-2 text-right">{r.present}</td>
                <td className="px-3 py-2 text-right">{r.late}</td>
                <td className="px-3 py-2 text-right">{r.absent}</td>
                <td className={`px-3 py-2 text-right font-semibold ${r.percent !== null && r.percent < LOW ? "text-rose-700" : "text-slate-900"}`}>
                  {r.percent === null ? "—" : `${r.percent}%`}
                </td>
              </tr>
            ))}
          />
        </>
      )}
    </div>
  );
}

function StaffAttendanceReport({ token }) {
  const [month, setMonth] = useState(() => localIso(new Date()).slice(0, 7));
  const [report, setReport] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    setState("loading");
    fetchStaffAttendanceReport(token, `${month}-01`)
      .then((data) => {
        setReport(data);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token, month]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-slate-700">
          Month
          <input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} className={INPUT} />
        </label>
        <ExcelButton onClick={() => downloadExcel(token, "/reports/staff-attendance", { month: `${month}-01`, format: "xlsx" }, `staff-attendance-${month}.xlsx`)} />
      </div>
      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load the report.</p>}
      {state === "ready" && (
        <Table
          empty="No teachers yet."
          headers={[["Teacher"], ["Department"], ["Present", "right"], ["Late", "right"], ["Leave", "right"], ["Absent", "right"]]}
          rows={report.rows.map((r) => (
            <tr key={r.teacher_id}>
              <td className="px-3 py-2 font-medium text-slate-900">{r.full_name}</td>
              <td className="px-3 py-2 text-slate-600">{r.department}</td>
              <td className="px-3 py-2 text-right">{r.present}</td>
              <td className={`px-3 py-2 text-right ${r.late ? "font-semibold text-amber-700" : ""}`}>{r.late}</td>
              <td className="px-3 py-2 text-right">{r.leave}</td>
              <td className={`px-3 py-2 text-right ${r.absent ? "font-semibold text-rose-700" : ""}`}>{r.absent}</td>
            </tr>
          ))}
        />
      )}
    </div>
  );
}

function FeeDuesReport({ token }) {
  const [onlyDues, setOnlyDues] = useState(true);
  const [report, setReport] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    setState("loading");
    fetchFeeReport(token, onlyDues)
      .then((data) => {
        setReport(data);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token, onlyDues]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={onlyDues} onChange={(e) => setOnlyDues(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
          Only students with dues
        </label>
        <ExcelButton onClick={() => downloadExcel(token, "/reports/fee-dues.xlsx", { only_with_dues: onlyDues }, "fee-dues.xlsx")} />
      </div>
      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load the report.</p>}
      {state === "ready" && (
        <>
          <Summary
            items={[
              ["Billed", formatRupees(report.total)],
              ["Collected", formatRupees(report.collected), "bg-emerald-50 text-emerald-800"],
              ["Balance", formatRupees(report.balance)],
              ["Overdue", formatRupees(report.overdue), report.overdue ? "bg-rose-50 text-rose-800" : undefined],
            ]}
          />
          <Table
            empty="No students with dues. 🎉"
            headers={[["Student"], ["Class"], ["Paid", "right"], ["Balance", "right"], ["Overdue", "right"], ["Contact"]]}
            rows={report.students.map((s) => (
              <tr key={s.student_id}>
                <td className="px-3 py-2">
                  <span className="font-medium text-slate-900">{s.full_name}</span> <span className="text-xs text-slate-400">{s.admission_number}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                  {s.class_name} - {s.section}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right">{formatRupees(s.paid)}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right font-semibold">{formatRupees(s.balance)}</td>
                <td className={`whitespace-nowrap px-3 py-2 text-right ${s.overdue ? "font-semibold text-rose-700" : ""}`}>{formatRupees(s.overdue)}</td>
                <td className="px-3 py-2 text-slate-600">{s.primary_contact_phone || "—"}</td>
              </tr>
            ))}
          />
        </>
      )}
    </div>
  );
}

function ReportsPage() {
  const { token, user } = useAuth();
  const isAdmin = user.role === "admin";
  const tabs = isAdmin
    ? [
        ["students", "Student attendance"],
        ["staff", "Staff attendance"],
        ["fees", "Fee dues"],
      ]
    : [["students", "Student attendance"]];
  const [tab, setTab] = useState("students");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Reports</h2>
        <p className="mt-1 text-sm text-slate-500">{isAdmin ? "See it on screen or download it as Excel." : "Your class's attendance, on screen or as Excel."}</p>
      </div>
      {tabs.length > 1 && (
        <div className="flex flex-wrap gap-2" role="tablist">
          {tabs.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200"}`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {tab === "students" && <StudentAttendanceReport token={token} isAdmin={isAdmin} />}
      {tab === "staff" && <StaffAttendanceReport token={token} />}
      {tab === "fees" && <FeeDuesReport token={token} />}
    </div>
  );
}

export default ReportsPage;

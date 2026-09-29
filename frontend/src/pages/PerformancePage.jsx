import { useEffect, useState } from "react";

import { fetchExamPerformance, fetchExams } from "../api/reportsApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

function Card({ title, children, className = "" }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-4 ${className}`}>
      <h3 className="mb-3 font-semibold text-slate-900">{title}</h3>
      {children}
    </section>
  );
}

// Horizontal bars, 0–100%: one series, one colour; the value sits beside each bar in ink.
function PercentBars({ items, empty }) {
  if (items.length === 0) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.label} className="grid grid-cols-[minmax(5rem,9rem)_1fr_3.5rem] items-center gap-3 text-sm" title={item.title}>
          <span className="truncate text-slate-700">{item.label}</span>
          <span className="h-3 rounded-full bg-slate-100" role="img" aria-label={`${item.label}: ${item.value === null ? "no marks yet" : `${item.value}%`}`}>
            {item.value !== null && <span className="block h-3 rounded-full bg-emerald-500" style={{ width: `${Math.max(item.value, 1)}%` }} />}
          </span>
          <span className="text-right font-semibold text-slate-900">{item.value === null ? "—" : `${item.value}%`}</span>
        </li>
      ))}
    </ul>
  );
}

function GradeBars({ grades }) {
  const entries = Object.entries(grades);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  const total = entries.reduce((sum, [, n]) => sum + n, 0);
  if (total === 0) return <p className="text-sm text-slate-500">No complete results yet.</p>;
  return (
    <div className="flex h-40 items-end gap-2" role="img" aria-label={entries.map(([g, n]) => `${g}: ${n}`).join(", ")}>
      {entries.map(([grade, count]) => (
        <div key={grade} className="flex h-full flex-1 flex-col items-center justify-end gap-1" title={`${grade}: ${count} student${count === 1 ? "" : "s"}`}>
          <span className="text-xs font-semibold text-slate-700">{count || ""}</span>
          <span className="w-full max-w-10 rounded-t bg-emerald-500" style={{ height: `${(count / max) * 100}%`, minHeight: count ? 4 : 0 }} />
          <span className="text-xs text-slate-500">{grade}</span>
        </div>
      ))}
    </div>
  );
}

function PerformancePage() {
  const { token, user } = useAuth();
  const [exams, setExams] = useState(null);
  const [examId, setExamId] = useState("");
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchExams(token)
      .then((list) => {
        setExams(list);
        setExamId(list[0]?.id ?? "");
        if (list.length === 0) setState("no-exams");
      })
      .catch(() => setState("error"));
  }, [token]);

  useEffect(() => {
    if (!examId) return;
    setState("loading");
    fetchExamPerformance(token, examId)
      .then((result) => {
        setData(result);
        setState("ready");
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Couldn't load performance.");
        setState("error");
      });
  }, [token, examId]);

  const appeared = data?.classes.reduce((s, c) => s + c.appeared, 0) ?? 0;
  const weighted = (key) => {
    const rows = (data?.classes ?? []).filter((c) => c[key] !== null && c.appeared);
    const n = rows.reduce((s, c) => s + c.appeared, 0);
    return n ? Math.round((rows.reduce((s, c) => s + c[key] * c.appeared, 0) / n) * 10) / 10 : null;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Performance</h2>
          <p className="mt-1 text-sm text-slate-500">
            {user.role === "admin" ? "How each class and subject did, and who needs help." : "How your class did, and who needs help."}
          </p>
        </div>
        {exams?.length > 0 && (
          <select aria-label="Exam" value={examId} onChange={(e) => setExamId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {exams.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} · {e.academic_year}
              </option>
            ))}
          </select>
        )}
      </div>

      {state === "loading" && <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">{error ?? "Couldn't load exams."}</p>}
      {state === "no-exams" && <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No exams yet. Create one under Exams &amp; Marks.</p>}

      {state === "ready" && (
        <>
          {!data.published && <p className="rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-900">Results aren&apos;t published yet, so these numbers may still change.</p>}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ["Students with full marks", appeared],
              ["Average", weighted("average_percent") === null ? "—" : `${weighted("average_percent")}%`],
              ["Passed", weighted("pass_percent") === null ? "—" : `${weighted("pass_percent")}%`],
              ["Need attention", data.needs_attention.length],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
                <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Class average">
              <PercentBars
                empty="No classes."
                items={data.classes.map((c) => ({
                  label: c.label,
                  value: c.average_percent,
                  title: `${c.label}: ${c.appeared}/${c.students} with full marks, ${c.pass_percent ?? "—"}% passed${c.topper ? `, topper ${c.topper}` : ""}`,
                }))}
              />
            </Card>
            <Card title="Subject average">
              <PercentBars
                empty="No marks yet."
                items={data.subjects.map((s) => ({ label: s.subject_name, value: s.average_percent, title: `${s.subject_name}: ${s.pass_percent ?? "—"}% passed of ${s.appeared}` }))}
              />
            </Card>
            <Card title="Grades">
              <GradeBars grades={data.grades} />
            </Card>
            <Card title="Toppers">
              {data.toppers.length === 0 ? (
                <p className="text-sm text-slate-500">No complete results yet.</p>
              ) : (
                <ol className="divide-y divide-slate-100 text-sm">
                  {data.toppers.map((t, i) => (
                    <li key={t.student_id} className="flex items-center gap-3 py-1.5">
                      <span className="w-5 text-right font-semibold text-slate-400">{i + 1}</span>
                      <span className="flex-1 font-medium text-slate-900">
                        {t.full_name} <span className="font-normal text-slate-500">· {t.class_label}</span>
                      </span>
                      <span className="font-semibold text-slate-900">{t.percentage}%</span>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>

          <Card title="Students who need attention">
            {data.needs_attention.length === 0 ? (
              <p className="text-sm text-emerald-700">Everyone passed every subject. 🎉</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="py-2 pr-3">Student</th>
                      <th className="py-2 pr-3">Class</th>
                      <th className="py-2 pr-3">Failed</th>
                      <th className="py-2 pr-3">Absent</th>
                      <th className="py-2 pr-3 text-right">Overall</th>
                      <th className="py-2 text-right">Attendance (90 days)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.needs_attention.map((a) => (
                      <tr key={a.student_id}>
                        <td className="py-2 pr-3">
                          <span className="font-medium text-slate-900">{a.full_name}</span> <span className="text-xs text-slate-400">{a.admission_number}</span>
                        </td>
                        <td className="whitespace-nowrap py-2 pr-3 text-slate-600">{a.class_label}</td>
                        <td className="py-2 pr-3 text-rose-700">{a.failed_subjects.join(", ") || "—"}</td>
                        <td className="py-2 pr-3 text-amber-700">{a.absent_subjects.join(", ") || "—"}</td>
                        <td className="py-2 pr-3 text-right">{a.percentage === null ? "—" : `${a.percentage}%`}</td>
                        <td className={`py-2 text-right ${a.attendance_percent !== null && a.attendance_percent < 75 ? "font-semibold text-rose-700" : ""}`}>
                          {a.attendance_percent === null ? "—" : `${a.attendance_percent}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

export default PerformancePage;

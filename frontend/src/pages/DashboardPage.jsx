import { useCallback, useEffect, useState } from "react";

import { formatRupees } from "../api/feesApi";
import { useAuth } from "../context/AuthContext";
import { ApiError, apiRequest } from "../lib/apiClient";
import { formatTime } from "./PunchPage";

function formatDay(iso, options) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", options);
}

function Tile({ label, value, sub, tone = "slate", onClick }) {
  const tones = { slate: "text-slate-900", emerald: "text-emerald-700", amber: "text-amber-700", rose: "text-rose-700" };
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={`rounded-xl border border-slate-200 bg-white p-4 text-left ${onClick ? "transition hover:border-emerald-300 hover:shadow-sm" : ""}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${tones[tone]}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </Tag>
  );
}

function Section({ title, action, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function LinkButton({ onClick, children }) {
  return (
    <button type="button" onClick={onClick} className="shrink-0 whitespace-nowrap text-sm font-semibold text-emerald-700 hover:underline">
      {children}
    </button>
  );
}

// Seven school days of attendance: one series, one colour, hover/tap for the exact figure.
function AttendanceTrend({ days }) {
  const [active, setActive] = useState(null);
  const shown = active ?? days.length - 1;
  const day = days[shown];
  return (
    <div>
      <p className="mb-3 text-sm text-slate-600" aria-live="polite">
        <span className="font-semibold text-slate-900">{formatDay(day.date, { weekday: "short", day: "numeric", month: "short" })}</span>
        {" · "}
        {day.percent === null ? "attendance not taken" : `${day.percent}% present · ${day.marked} class${day.marked === 1 ? "" : "es"} marked`}
      </p>
      <div className="relative h-36 border-b border-slate-300" onMouseLeave={() => setActive(null)}>
        {[50, 100].map((line) => (
          <div key={line} className="pointer-events-none absolute inset-x-0 border-t border-dashed border-slate-100" style={{ bottom: `${line}%` }}>
            <span className="absolute -top-2 right-0 bg-white pl-1 text-[10px] text-slate-400">{line}%</span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-end gap-2 pr-9">
          {days.map((d, i) => (
            <button
              key={d.date}
              type="button"
              aria-label={`${formatDay(d.date, { weekday: "long", day: "numeric", month: "long" })}: ${d.percent === null ? "not taken" : `${d.percent}% present`}`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onClick={() => setActive(i)}
              className="flex h-full flex-1 items-end justify-center rounded-t focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            >
              {d.percent === null ? (
                <span className="h-1 w-full max-w-10 rounded-t bg-slate-200" />
              ) : (
                <span
                  className={`w-full max-w-10 rounded-t transition-colors ${i === shown ? "bg-emerald-700" : "bg-emerald-500"}`}
                  style={{ height: `${Math.max(d.percent, 2)}%` }}
                />
              )}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-1 flex gap-2 pr-9">
        {days.map((d) => (
          <span key={d.date} className="flex-1 text-center text-[11px] text-slate-500">
            {formatDay(d.date, { weekday: "short" })}
          </span>
        ))}
      </div>
    </div>
  );
}

function HolidayBanner({ holiday, onNavigate }) {
  if (!holiday) return null;
  return (
    <button type="button" onClick={() => onNavigate("calendar")} className="w-full rounded-xl bg-rose-50 px-4 py-3 text-left text-sm text-rose-900 hover:bg-rose-100">
      🎉 <span className="font-semibold">Today is a holiday: {holiday}.</span> No attendance is expected.
    </button>
  );
}

function AdminDashboard({ data, onNavigate }) {
  const attendanceSub =
    data.classes_total === 0 ? "No classes yet" : `${data.classes_marked} of ${data.classes_total} classes marked`;
  return (
    <div className="space-y-6">
      <HolidayBanner holiday={data.holiday} onNavigate={onNavigate} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Students" value={data.students} sub={`${data.teachers} teachers`} onClick={() => onNavigate("students")} />
        <Tile
          label="Present today"
          value={data.classes_marked ? data.present + data.late : "—"}
          sub={data.classes_marked ? `${data.absent} absent · ${data.late} late · ${attendanceSub}` : attendanceSub}
          tone="emerald"
          onClick={() => onNavigate("attendance")}
        />
        <Tile
          label="Teachers in"
          value={`${data.staff_punched_in}/${data.teachers}`}
          sub={`${data.staff_late} late · ${data.staff_on_leave} on leave`}
          tone={data.staff_late ? "amber" : "slate"}
          onClick={() => onNavigate("staff-attendance")}
        />
        <Tile
          label="Fees today"
          value={formatRupees(data.fees_collected_today)}
          sub={`${formatRupees(data.fees_collected_month)} this month`}
          onClick={() => onNavigate("fees")}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Section title="Student attendance, last 7 working days">
            <AttendanceTrend days={data.trend} />
          </Section>
        </div>
        <div className="space-y-6 lg:col-span-2">
          <Section title="Needs your attention">
            <ul className="space-y-2 text-sm">
              <ActionRow count={data.pending_admissions} label="new admission application(s)" onClick={() => onNavigate("admissions")} />
              <ActionRow count={data.pending_leave} label="staff leave request(s) to approve" onClick={() => onNavigate("leave")} />
              <ActionRow count={data.pending_documents} label="student document(s) to review" onClick={() => onNavigate("students")} />
              <ActionRow count={data.fees_overdue > 0 ? formatRupees(data.fees_overdue) : 0} label="fees overdue" onClick={() => onNavigate("fees")} />
            </ul>
            {!data.pending_admissions && !data.pending_leave && !data.pending_documents && !data.fees_overdue && <p className="text-sm text-slate-500">All clear. Nothing waiting on you. 🎉</p>}
            <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">Total fees still to collect: {formatRupees(data.fees_outstanding)}</p>
          </Section>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Attendance not taken today" action={<LinkButton onClick={() => onNavigate("attendance")}>Open attendance</LinkButton>}>
          {data.classes_total === 0 ? (
            <p className="text-sm text-slate-500">Add classes to start taking attendance.</p>
          ) : data.holiday ? (
            <p className="text-sm text-slate-500">Holiday today.</p>
          ) : data.unmarked_classes.length === 0 ? (
            <p className="text-sm text-emerald-700">Every class has been marked today. ✓</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.unmarked_classes.map((c) => (
                <li key={c.class_id} className="flex justify-between gap-3 py-2">
                  <span className="font-medium text-slate-900">
                    {c.name} - {c.section}
                  </span>
                  <span className="text-slate-500">{c.class_teacher_name}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Exams in progress" action={<LinkButton onClick={() => onNavigate("exams")}>Open exams</LinkButton>}>
          {data.exams_in_progress.length === 0 ? (
            <p className="text-sm text-slate-500">No unpublished exams.</p>
          ) : (
            <ul className="space-y-3 text-sm">
              {data.exams_in_progress.map((e) => (
                <li key={e.exam_id}>
                  <Progress label={e.name} done={e.entered} total={e.expected} />
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}

function ActionRow({ count, label, onClick }) {
  if (!count) return null;
  return (
    <li>
      <button type="button" onClick={onClick} className="flex w-full items-center gap-3 rounded-lg bg-amber-50 px-3 py-2 text-left text-amber-900 hover:bg-amber-100">
        <span className="font-bold">{count}</span>
        <span className="flex-1">{label}</span>
        <span aria-hidden="true">→</span>
      </button>
    </li>
  );
}

function Progress({ label, done, total }) {
  const percent = total ? Math.round((done * 100) / total) : 0;
  return (
    <div>
      <div className="flex justify-between gap-3">
        <span className="font-medium text-slate-900">{label}</span>
        <span className="shrink-0 text-slate-500">
          {done}/{total} marks
        </span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-slate-100" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} marks entered`}>
        <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function TeacherDashboard({ data, onNavigate }) {
  const { punch } = data;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Punch in"
          value={punch.punch_in_at ? formatTime(punch.punch_in_at) : "Not yet"}
          sub={punch.punch_in_at ? (punch.is_late ? "Late" : "On time") : `College starts ${data.day_starts_at}`}
          tone={!punch.punch_in_at ? "amber" : punch.is_late ? "rose" : "emerald"}
          onClick={() => onNavigate("punch")}
        />
        <Tile label="Leave to review" value={data.pending_leave} sub="from your class" tone={data.pending_leave ? "amber" : "slate"} onClick={() => onNavigate("leave")} />
        <Tile label="Documents" value={data.pending_documents} sub="waiting for review" tone={data.pending_documents ? "amber" : "slate"} onClick={() => onNavigate("students")} />
        <Tile label="Marks to enter" value={data.marks_to_enter.length} sub="papers" tone={data.marks_to_enter.length ? "amber" : "slate"} onClick={() => onNavigate("exams")} />
      </div>

      <HolidayBanner holiday={data.holiday} onNavigate={onNavigate} />
      {!data.holiday && (
        <Section title="My periods today" action={<LinkButton onClick={() => onNavigate("timetable")}>Full week</LinkButton>}>
          {data.lessons_today.length === 0 ? (
            <p className="text-sm text-slate-500">No periods for you today.</p>
          ) : (
            <ol className="divide-y divide-slate-100 text-sm">
              {data.lessons_today.map((l) => (
                <li key={l.period} className="flex items-center gap-4 py-2">
                  <span className="w-24 shrink-0 text-xs text-slate-500">
                    <span className="font-semibold text-slate-700">{l.period}</span> · {l.start_time}
                  </span>
                  <span className="font-medium text-slate-900">{l.subject_name}</span>
                  <span className="text-slate-500">{l.class_label}</span>
                </li>
              ))}
            </ol>
          )}
        </Section>
      )}

      <Section title="My class today" action={<LinkButton onClick={() => onNavigate("attendance")}>Take attendance</LinkButton>}>
        {data.my_classes.length === 0 ? (
          <p className="text-sm text-slate-500">You aren&apos;t a class teacher this year.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {data.my_classes.map((c) => (
              <li key={c.class_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="font-medium text-slate-900">
                  {c.name} - {c.section} <span className="font-normal text-slate-500">· {c.students} students</span>
                </span>
                {c.marked ? (
                  <span className="text-slate-600">
                    <span className="font-semibold text-emerald-700">{c.present + c.late} present</span> · {c.absent} absent
                  </span>
                ) : (
                  <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800">Attendance not taken</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Marks still to enter" action={<LinkButton onClick={() => onNavigate("exams")}>Open exams</LinkButton>}>
        {data.marks_to_enter.length === 0 ? (
          <p className="text-sm text-slate-500">You&apos;re all caught up.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {data.marks_to_enter.map((p) => (
              <li key={p.paper_id}>
                <Progress label={p.label} done={p.entered} total={p.students} />
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function DashboardPage({ onNavigate }) {
  const { token, user } = useAuth();
  const [state, setState] = useState("loading");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      setData(await apiRequest(`/dashboard/${user.role === "admin" ? "admin" : "teacher"}`, { token }));
      setState("ready");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? "You don't have access to this dashboard." : "Couldn't load the dashboard.");
      setState("error");
    }
  }, [token, user.role]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, {user.full_name?.split(" ")[0]}</h2>
          <p className="text-sm text-slate-500">{data ? formatDay(data.date, { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : " "}</p>
        </div>
        {state === "ready" && (
          <button type="button" onClick={load} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
            Refresh
          </button>
        )}
      </div>

      {state === "loading" && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white" />
          ))}
        </div>
      )}
      {state === "error" && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}{" "}
          <button type="button" onClick={load} className="font-semibold underline">
            Try again
          </button>
        </div>
      )}
      {state === "ready" &&
        (user.role === "admin" ? <AdminDashboard data={data} onNavigate={onNavigate} /> : <TeacherDashboard data={data} onNavigate={onNavigate} />)}
    </div>
  );
}

export default DashboardPage;

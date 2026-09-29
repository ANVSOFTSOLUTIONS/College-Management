import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchPostingOptions } from "../api/boardApi";
import { fetchChildren } from "../api/parentApi";
import { WEEKDAYS, fetchClassTimetable, fetchMyTimetable, fetchPeriods, saveClassTimetable, savePeriods } from "../api/timetableApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function todayIndex() {
  const day = (new Date().getDay() + 6) % 7; // Monday = 0
  return day > 5 ? 0 : day;
}

function cellKey(weekday, periodId) {
  return `${weekday}:${periodId}`;
}

// Read-only week: a table on wide screens, one day at a time on phones.
function WeekView({ timetable, showClass }) {
  const [day, setDay] = useState(todayIndex);
  const cells = useMemo(() => new Map(timetable.cells.map((c) => [cellKey(c.weekday, c.period_id), c])), [timetable]);
  const usedDays = WEEKDAYS.map((_, i) => timetable.cells.some((c) => c.weekday === i));
  const days = WEEKDAYS.map((label, i) => ({ label, i })).filter(({ i }) => i < 5 || usedDays[i]);

  if (timetable.periods.length === 0) {
    return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">The college hasn&apos;t set up periods yet.</p>;
  }
  if (timetable.cells.length === 0) {
    return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No timetable yet.</p>;
  }

  const lesson = (c) =>
    c ? (
      <>
        <p className="font-semibold text-slate-900">{c.subject_name}</p>
        <p className="text-xs text-slate-500">{showClass ? c.class_label : c.teacher_name ?? "—"}</p>
      </>
    ) : (
      <span className="text-slate-300">—</span>
    );

  return (
    <>
      <div className="md:hidden">
        <div className="mb-3 flex gap-1 overflow-x-auto" role="tablist" aria-label="Day">
          {days.map(({ label, i }) => (
            <button
              key={label}
              type="button"
              role="tab"
              aria-selected={day === i}
              onClick={() => setDay(i)}
              className={`rounded-full px-3 py-1.5 text-sm font-semibold ${day === i ? "bg-emerald-600 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200"}`}
            >
              {label}
            </button>
          ))}
        </div>
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {timetable.periods.map((p) => (
            <li key={p.id} className={`flex gap-4 px-4 py-3 ${p.is_break ? "bg-slate-50" : ""}`}>
              <div className="w-20 shrink-0 text-xs text-slate-500">
                <p className="font-semibold text-slate-700">{p.label}</p>
                {p.start_time}–{p.end_time}
              </div>
              <div className="min-w-0 text-sm">{p.is_break ? <span className="text-slate-500">Break</span> : lesson(cells.get(cellKey(day, p.id)))}</div>
            </li>
          ))}
        </ul>
      </div>

      <div className="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white md:block">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Period</th>
              {days.map(({ label, i }) => (
                <th key={label} className={`px-3 py-2 ${i === todayIndex() ? "text-emerald-700" : ""}`}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {timetable.periods.map((p) => (
              <tr key={p.id} className={p.is_break ? "bg-slate-50" : ""}>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                  <p className="font-semibold text-slate-700">{p.label}</p>
                  {p.start_time}–{p.end_time}
                </td>
                {p.is_break ? (
                  <td colSpan={days.length} className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Break
                  </td>
                ) : (
                  days.map(({ i }) => (
                    <td key={i} className="px-3 py-2">
                      {lesson(cells.get(cellKey(i, p.id)))}
                    </td>
                  ))
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function ClassGridEditor({ token, cls }) {
  const [timetable, setTimetable] = useState(null);
  const [grid, setGrid] = useState({});
  const [state, setState] = useState("loading");
  const [message, setMessage] = useState(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const data = await fetchClassTimetable(token, cls.id);
      setTimetable(data);
      setGrid(Object.fromEntries(data.cells.map((c) => [cellKey(c.weekday, c.period_id), c.subject_id])));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, cls.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave() {
    setState("saving");
    setMessage(null);
    const cells = Object.entries(grid)
      .filter(([, subjectId]) => subjectId)
      .map(([key, subjectId]) => {
        const [weekday, periodId] = key.split(":");
        return { weekday: Number(weekday), period_id: periodId, subject_id: subjectId };
      });
    try {
      setTimetable(await saveClassTimetable(token, cls.id, cells));
      setMessage({ ok: true, text: "Timetable saved." });
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err, "Couldn't save the timetable.") });
    }
    setState("ready");
  }

  if (state === "loading") return <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load this timetable.</p>;
  if (timetable.periods.length === 0) return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">Set up the college&apos;s periods first (Periods tab).</p>;
  if (cls.subjects.length === 0) return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">Add subjects and teachers to {cls.name} - {cls.section} under Classes &amp; Subjects first.</p>;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Period</th>
              {WEEKDAYS.map((d) => (
                <th key={d} className="min-w-36 px-2 py-2">
                  {d}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {timetable.periods.map((p) => (
              <tr key={p.id} className={p.is_break ? "bg-slate-50" : ""}>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                  <p className="font-semibold text-slate-700">{p.label}</p>
                  {p.start_time}–{p.end_time}
                </td>
                {p.is_break ? (
                  <td colSpan={6} className="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Break
                  </td>
                ) : (
                  WEEKDAYS.map((d, i) => (
                    <td key={d} className="px-2 py-1.5">
                      <select
                        aria-label={`${d} ${p.label}`}
                        value={grid[cellKey(i, p.id)] ?? ""}
                        onChange={(e) => setGrid({ ...grid, [cellKey(i, p.id)]: e.target.value })}
                        className={INPUT}
                      >
                        <option value="">—</option>
                        {cls.subjects.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </td>
                  ))
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {message && <p className={`rounded-lg px-3 py-2 text-sm font-medium ${message.ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-700"}`}>{message.text}</p>}
      <button type="button" disabled={state === "saving"} onClick={handleSave} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
        {state === "saving" ? "Saving…" : `Save ${cls.name} - ${cls.section}`}
      </button>
      <p className="text-xs text-slate-500">Each subject&apos;s teacher comes from Classes &amp; Subjects. A teacher can&apos;t be in two classes in the same period.</p>
    </div>
  );
}

function PeriodsEditor({ token }) {
  const [rows, setRows] = useState(null);
  const [state, setState] = useState("loading");
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchPeriods(token)
      .then((list) => {
        setRows(list);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token]);

  function update(index, change) {
    setRows(rows.map((r, i) => (i === index ? { ...r, ...change } : r)));
  }

  function addRow() {
    const last = rows[rows.length - 1];
    const start = last?.end_time ?? "09:00";
    const [h, m] = start.split(":").map(Number);
    const endMinutes = h * 60 + m + 45;
    const end = `${String(Math.floor(endMinutes / 60) % 24).padStart(2, "0")}:${String(endMinutes % 60).padStart(2, "0")}`;
    setRows([...rows, { label: `P${rows.filter((r) => !r.is_break).length + 1}`, start_time: start, end_time: end, is_break: false }]);
  }

  async function handleSave() {
    setState("saving");
    setMessage(null);
    try {
      setRows(await savePeriods(token, rows));
      setMessage({ ok: true, text: "Periods saved." });
    } catch (err) {
      setMessage({ ok: false, text: errorMessage(err, "Couldn't save the periods.") });
    }
    setState("ready");
  }

  if (state === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load periods.</p>;

  return (
    <div className="max-w-2xl space-y-3">
      <p className="text-sm text-slate-500">The bell schedule is the same for every class. Removing a period, or making it a break, clears it from every timetable.</p>
      <ul className="space-y-2">
        {rows.map((r, i) => (
          <li key={r.id ?? `new-${i}`} className="grid grid-cols-[1fr_auto_auto] items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 sm:grid-cols-[8rem_auto_auto_auto_auto]">
            <input aria-label="Period name" value={r.label} maxLength={30} onChange={(e) => update(i, { label: e.target.value })} className={`${INPUT} col-span-3 sm:col-span-1`} />
            <input aria-label="Starts" type="time" value={r.start_time} onChange={(e) => update(i, { start_time: e.target.value })} className={INPUT} />
            <input aria-label="Ends" type="time" value={r.end_time} onChange={(e) => update(i, { end_time: e.target.value })} className={INPUT} />
            <label className="flex items-center gap-1.5 text-sm text-slate-600">
              <input type="checkbox" checked={r.is_break} onChange={(e) => update(i, { is_break: e.target.checked })} className="rounded border-slate-300 text-emerald-600" />
              Break
            </label>
            <button type="button" onClick={() => setRows(rows.filter((_, j) => j !== i))} className="text-sm font-semibold text-rose-700 hover:underline">
              Remove
            </button>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3">
        <button type="button" onClick={addRow} className="rounded-lg px-4 py-2 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
          + Add period
        </button>
        <button type="button" disabled={state === "saving"} onClick={handleSave} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Save periods"}
        </button>
      </div>
      {message && <p className={`rounded-lg px-3 py-2 text-sm font-medium ${message.ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-700"}`}>{message.text}</p>}
    </div>
  );
}

function AdminTimetable({ token }) {
  const [tab, setTab] = useState("classes");
  const [classes, setClasses] = useState(null);
  const [classId, setClassId] = useState("");

  useEffect(() => {
    if (tab !== "classes") return;
    fetchPostingOptions(token)
      .then((list) => {
        setClasses(list);
        setClassId((current) => current || list[0]?.id || "");
      })
      .catch(() => setClasses([]));
  }, [token, tab]);

  const cls = classes?.find((c) => c.id === classId);
  return (
    <div className="space-y-4">
      <div className="flex gap-2" role="tablist">
        {[
          ["classes", "Class timetables"],
          ["periods", "Periods"],
        ].map(([id, label]) => (
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
      {tab === "periods" ? (
        <PeriodsEditor token={token} />
      ) : classes === null ? (
        <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />
      ) : classes.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">Add classes first.</p>
      ) : (
        <>
          <select aria-label="Class" value={classId} onChange={(e) => setClassId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} - {c.section}
              </option>
            ))}
          </select>
          {cls && <ClassGridEditor key={cls.id} token={token} cls={cls} />}
        </>
      )}
    </div>
  );
}

function ReaderTimetable({ token, role }) {
  const [children, setChildren] = useState(null);
  const [childId, setChildId] = useState("");
  const [timetable, setTimetable] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    if (role !== "parent" && role !== "student") return;
    fetchChildren(token)
      .then((list) => {
        setChildren(list);
        setChildId(list[0]?.student_id ?? "");
      })
      .catch(() => setState("error"));
  }, [token, role]);

  useEffect(() => {
    if ((role === "parent" || role === "student") && !childId) {
      if (children) setState(children.length ? "loading" : "no-children");
      return;
    }
    setState("loading");
    fetchMyTimetable(token, childId)
      .then((data) => {
        setTimetable(data);
        setState("ready");
      })
      .catch((err) => setState(err instanceof ApiError && err.status === 404 ? "no-class" : "error"));
  }, [token, role, childId, children]);

  return (
    <div className="space-y-4">
      {(role === "parent" || role === "student") && children?.length > 1 && (
        <select aria-label="Child" value={childId} onChange={(e) => setChildId(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          {children.map((c) => (
            <option key={c.student_id} value={c.student_id}>
              {c.full_name} ({c.class_name} - {c.section})
            </option>
          ))}
        </select>
      )}
      {state === "loading" && <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load the timetable.</p>}
      {state === "no-children" && <p className="text-sm text-slate-500">No children are linked to your account.</p>}
      {state === "no-class" && <p className="text-sm text-slate-500">No class timetable found.</p>}
      {state === "ready" && (
        <>
          {role !== "teacher" && <p className="text-sm font-semibold text-slate-700">{timetable.title}</p>}
          <WeekView timetable={timetable} showClass={role === "teacher"} />
        </>
      )}
    </div>
  );
}

function TimetablePage() {
  const { token, user } = useAuth();
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">{user.role === "teacher" ? "My timetable" : "Timetable"}</h2>
        <p className="mt-1 text-sm text-slate-500">
          {user.role === "admin" ? "Set the college's periods once, then fill each class's week." : "Your weekly periods."}
        </p>
      </div>
      {user.role === "admin" ? <AdminTimetable token={token} /> : <ReaderTimetable token={token} role={user.role} />}
    </div>
  );
}

export default TimetablePage;

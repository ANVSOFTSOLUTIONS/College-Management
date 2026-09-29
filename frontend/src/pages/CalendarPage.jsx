import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteCalendarEntry, fetchCalendar, saveCalendarEntry } from "../api/timetableApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const KIND_STYLE = {
  holiday: { dot: "bg-rose-500", chip: "bg-rose-50 text-rose-800", label: "Holiday" },
  event: { dot: "bg-sky-500", chip: "bg-sky-50 text-sky-800", label: "Event" },
};

function iso(d) {
  return d.toLocaleDateString("en-CA");
}

function monthBounds(year, month) {
  return { first: new Date(year, month, 1), last: new Date(year, month + 1, 0) };
}

function rangeText(entry) {
  const fmt = (s) => new Date(`${s}T00:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
  return entry.start_date === entry.end_date ? fmt(entry.start_date) : `${fmt(entry.start_date)} – ${fmt(entry.end_date)} (${entry.days} days)`;
}

function EntryForm({ token, entry, defaultDate, onSaved, onCancel }) {
  const [form, setForm] = useState(
    entry
      ? { title: entry.title, kind: entry.kind, start_date: entry.start_date, end_date: entry.end_date, notes: entry.notes, notify: false }
      : { title: "", kind: "holiday", start_date: defaultDate, end_date: defaultDate, notes: "", notify: true },
  );
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      await saveCalendarEntry(token, form, entry?.id);
      onSaved();
    } catch (err) {
      setState("idle");
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-emerald-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">{entry ? "Edit" : "Add to calendar"}</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="cal-title" className="block text-sm font-medium text-slate-700">
            Title
          </label>
          <input id="cal-title" required minLength={2} maxLength={120} placeholder="e.g. Dussehra" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={INPUT} />
        </div>
        <div>
          <label htmlFor="cal-kind" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select id="cal-kind" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className={INPUT}>
            <option value="holiday">Holiday (school closed)</option>
            <option value="event">Event (school open)</option>
          </select>
        </div>
        <div>
          <label htmlFor="cal-start" className="block text-sm font-medium text-slate-700">
            From
          </label>
          <input
            id="cal-start"
            type="date"
            required
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value, end_date: e.target.value > form.end_date ? e.target.value : form.end_date })}
            className={INPUT}
          />
        </div>
        <div>
          <label htmlFor="cal-end" className="block text-sm font-medium text-slate-700">
            To
          </label>
          <input id="cal-end" type="date" required min={form.start_date} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className={INPUT} />
        </div>
      </div>
      <div>
        <label htmlFor="cal-notes" className="block text-sm font-medium text-slate-700">
          Note <span className="font-normal text-slate-400">(optional)</span>
        </label>
        <input id="cal-notes" maxLength={300} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className={INPUT} />
      </div>
      {!entry && (
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={form.notify} onChange={(e) => setForm({ ...form, notify: e.target.checked })} className="rounded border-slate-300 text-emerald-600" />
          Notify teachers, students and parents
        </label>
      )}
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
          Cancel
        </button>
      </div>
    </form>
  );
}

function CalendarPage() {
  const { token, user } = useAuth();
  const isAdmin = user.role === "admin";
  const now = new Date();
  const [view, setView] = useState({ year: now.getFullYear(), month: now.getMonth() });
  const [entries, setEntries] = useState([]);
  const [state, setState] = useState("loading");
  const [editing, setEditing] = useState(null);
  const [selected, setSelected] = useState(null);

  const { first, last } = monthBounds(view.year, view.month);
  const load = useCallback(async () => {
    setState("loading");
    try {
      const { first: f, last: l } = monthBounds(view.year, view.month);
      setEntries(await fetchCalendar(token, iso(f), iso(l)));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, view]);

  useEffect(() => {
    load();
  }, [load]);

  // Map each day of the month to the entries covering it.
  const byDay = useMemo(() => {
    const map = new Map();
    entries.forEach((e) => {
      for (let d = new Date(`${e.start_date}T00:00:00`); iso(d) <= e.end_date; d.setDate(d.getDate() + 1)) {
        map.set(iso(d), [...(map.get(iso(d)) ?? []), e]);
      }
    });
    return map;
  }, [entries]);

  const blanks = (first.getDay() + 6) % 7; // weeks start on Monday
  const days = Array.from({ length: last.getDate() }, (_, i) => new Date(view.year, view.month, i + 1));
  const today = iso(now);
  const shown = selected ? byDay.get(selected) ?? [] : entries;

  function move(delta) {
    const d = new Date(view.year, view.month + delta, 1);
    setView({ year: d.getFullYear(), month: d.getMonth() });
    setSelected(null);
  }

  async function handleDelete(entry) {
    if (!window.confirm(`Delete "${entry.title}"?`)) return;
    await deleteCalendarEntry(token, entry.id).catch(() => {});
    load();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Holiday calendar</h2>
          <p className="mt-1 text-sm text-slate-500">College holidays and events.</p>
        </div>
        {isAdmin && editing === null && (
          <button type="button" onClick={() => setEditing("new")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
            + Add holiday or event
          </button>
        )}
      </div>

      {editing !== null && (
        <EntryForm
          key={editing === "new" ? "new" : editing.id}
          token={token}
          entry={editing === "new" ? null : editing}
          defaultDate={selected ?? today}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <section className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <button type="button" onClick={() => move(-1)} aria-label="Previous month" className="rounded-lg px-3 py-1 text-lg text-slate-600 hover:bg-slate-100">
              ‹
            </button>
            <h3 className="font-semibold text-slate-900">{first.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}</h3>
            <button type="button" onClick={() => move(1)} aria-label="Next month" className="rounded-lg px-3 py-1 text-lg text-slate-600 hover:bg-slate-100">
              ›
            </button>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-500">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>
          <div className={`mt-1 grid grid-cols-7 gap-1 ${state === "loading" ? "opacity-50" : ""}`}>
            {Array.from({ length: blanks }, (_, i) => (
              <span key={`b${i}`} />
            ))}
            {days.map((d) => {
              const key = iso(d);
              const dayEntries = byDay.get(key) ?? [];
              const holiday = dayEntries.some((e) => e.kind === "holiday");
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSelected(selected === key ? null : key)}
                  aria-label={`${d.toLocaleDateString("en-IN", { day: "numeric", month: "long" })}${dayEntries.length ? `: ${dayEntries.map((e) => e.title).join(", ")}` : ""}`}
                  aria-pressed={selected === key}
                  className={`flex h-12 flex-col items-center justify-center rounded-lg text-sm ${
                    selected === key ? "ring-2 ring-emerald-500" : ""
                  } ${holiday ? "bg-rose-50 font-semibold text-rose-800" : d.getDay() === 0 ? "text-slate-400" : "text-slate-700 hover:bg-slate-50"} ${
                    key === today ? "underline decoration-2 underline-offset-4" : ""
                  }`}
                >
                  {d.getDate()}
                  <span className="mt-0.5 flex gap-0.5">
                    {dayEntries.slice(0, 3).map((e) => (
                      <span key={e.id} className={`h-1.5 w-1.5 rounded-full ${KIND_STYLE[e.kind].dot}`} />
                    ))}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-rose-500" /> Holiday
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-sky-500" /> Event
            </span>
          </div>
        </section>

        <section className="space-y-3 lg:col-span-2">
          <h3 className="font-semibold text-slate-900">
            {selected ? new Date(`${selected}T00:00:00`).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }) : "This month"}
          </h3>
          {state === "error" && <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load the calendar.</p>}
          {state !== "error" && shown.length === 0 && <p className="text-sm text-slate-500">{selected ? "Regular college day." : "No holidays or events this month."}</p>}
          <ul className="space-y-2">
            {shown.map((e) => (
              <li key={e.id} className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${KIND_STYLE[e.kind].chip}`}>{KIND_STYLE[e.kind].label}</span>
                    <p className="mt-1 font-semibold text-slate-900">{e.title}</p>
                    <p className="text-xs text-slate-500">{rangeText(e)}</p>
                    {e.notes && <p className="mt-1 text-sm text-slate-600">{e.notes}</p>}
                  </div>
                  {isAdmin && (
                    <div className="flex gap-2 text-sm">
                      <button type="button" onClick={() => setEditing(e)} className="font-semibold text-emerald-700 hover:underline">
                        Edit
                      </button>
                      <button type="button" onClick={() => handleDelete(e)} className="font-semibold text-rose-700 hover:underline">
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default CalendarPage;

import { useEffect, useState } from "react";

import { fetchChildCampus } from "../api/campusApi";
import { rupees } from "./CampusUi";

// Library loans, hostel room and bus route for one student, in the student and parent portals.
// A section is hidden when the college doesn't use that module or there's nothing to show.
function CampusCards({ token, studentId }) {
  const [data, setData] = useState({});

  useEffect(() => {
    let alive = true;
    const settle = (what) =>
      fetchChildCampus(token, studentId, what)
        .then((value) => alive && setData((prev) => ({ ...prev, [what]: value })))
        .catch(() => alive && setData((prev) => ({ ...prev, [what]: null })));
    ["library", "hostel", "transport", "subject-attendance", "backlogs"].forEach(settle);
    return () => {
      alive = false;
    };
  }, [token, studentId]);

  const loans = (data.library ?? []).filter((l) => !l.returned_on || (l.fine > 0 && !l.fine_paid));
  const { hostel, transport } = data;
  const subjects = data["subject-attendance"] ?? [];
  const backlogs = data.backlogs ?? [];
  if (!loans.length && !hostel && !transport && !subjects.length && !backlogs.length) return null;

  return (
    <section className="grid gap-4 sm:grid-cols-3">
      {subjects.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 sm:col-span-2">
          <h4 className="text-sm font-semibold text-slate-700">Subject-wise attendance</h4>
          <ul className="mt-2 space-y-2 text-sm">
            {subjects.map((s) => (
              <li key={s.subject_id}>
                <div className="flex justify-between">
                  <span className="font-medium text-slate-800">{s.subject_name}</span>
                  <span className={s.short ? "font-bold text-rose-700" : "font-semibold text-emerald-700"}>
                    {s.percent}% <span className="text-xs font-normal text-slate-400">({s.attended}/{s.held})</span>
                  </span>
                </div>
                <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <span className={`block h-full rounded-full ${s.short ? "bg-rose-500" : "bg-emerald-500"}`} style={{ width: `${Math.min(s.percent ?? 0, 100)}%` }} />
                </span>
              </li>
            ))}
          </ul>
          {subjects.some((s) => s.short) && <p className="mt-3 text-xs font-semibold text-rose-700">Below 75% in some subjects — may not be allowed to write those exams.</p>}
        </div>
      )}
      {backlogs.length > 0 && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <h4 className="text-sm font-semibold text-rose-800">Backlogs ({backlogs.length})</h4>
          <ul className="mt-2 space-y-1 text-sm">
            {backlogs.map((b) => (
              <li key={b.subject_name} className="flex justify-between">
                <span className="text-rose-900">{b.subject_name}</span>
                <span className="font-bold text-rose-700">{b.grade}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-rose-700">Clear them in the next supplementary exam.</p>
        </div>
      )}
      {loans.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-700">Library</h4>
          <ul className="mt-2 space-y-2 text-sm">
            {loans.map((l) => (
              <li key={l.id}>
                <p className="font-medium text-slate-800">{l.book_title}</p>
                <p className={`text-xs ${l.overdue_days ? "font-semibold text-rose-700" : "text-slate-500"}`}>
                  {l.returned_on ? `Fine due ${rupees(l.fine)}` : `Return by ${l.due_on}`}
                  {!l.returned_on && l.overdue_days > 0 && ` — ${l.overdue_days} days late, fine ${rupees(l.fine)}`}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {hostel && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-700">Hostel</h4>
          <p className="mt-2 font-medium text-slate-800">
            {hostel.hostel_name} · Room {hostel.room_number}
          </p>
          <p className="text-xs text-slate-500">Since {hostel.allocated_on}</p>
          {hostel.roommates.length > 0 && <p className="mt-1 text-xs text-slate-500">Roommates: {hostel.roommates.join(", ")}</p>}
          {hostel.warden_name && (
            <p className="mt-1 text-xs text-slate-500">
              Warden: {hostel.warden_name} {hostel.warden_phone && <a className="text-emerald-700" href={`tel:${hostel.warden_phone}`}>{hostel.warden_phone}</a>}
            </p>
          )}
        </div>
      )}
      {transport && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-700">College bus</h4>
          <p className="mt-2 font-medium text-slate-800">{transport.route_name}</p>
          {transport.stop_name && (
            <p className="text-xs text-slate-500">
              Boards at {transport.stop_name}
              {transport.pickup_time && ` at ${transport.pickup_time}`}
            </p>
          )}
          <p className="mt-1 text-xs text-slate-500">
            {[transport.vehicle_number, transport.driver_name].filter(Boolean).join(" · ")}{" "}
            {transport.driver_phone && <a className="text-emerald-700" href={`tel:${transport.driver_phone}`}>{transport.driver_phone}</a>}
          </p>
        </div>
      )}
    </section>
  );
}

export default CampusCards;

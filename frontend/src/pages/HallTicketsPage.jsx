import { useEffect, useState } from "react";

import { PrintPortal } from "../components/PrintPortal";
import {
  errorMessage,
  INPUT,
  LoadState,
  Notice,
  PageHeader,
  PRIMARY,
  SECONDARY,
  Stat,
  useLoad,
} from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

function Ticket({ sheet, s }) {
  return (
    <div className="print-avoid-break rounded-lg border-2 border-slate-800 p-4 text-sm">
      <div className="border-b border-slate-300 pb-2 text-center">
        <p className="text-base font-bold uppercase">{sheet.college_name}</p>
        <p className="font-semibold">Hall Ticket · {sheet.exam_name}</p>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1">
        <p>
          <span className="text-slate-500">Name:</span> <b>{s.full_name}</b>
        </p>
        <p>
          <span className="text-slate-500">Roll no:</span>{" "}
          <b>{s.admission_number}</b>
        </p>
        <p>
          <span className="text-slate-500">Batch:</span> {s.batch}
        </p>
        <p>
          <span className="text-slate-500">Room / Seat:</span>{" "}
          <b>{s.room ? `${s.room} / ${s.seat}` : "—"}</b>
        </p>
      </div>
      <table className="mt-2 w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-slate-400 text-left">
            <th className="py-1">Date</th>
            <th>Code</th>
            <th>Subject</th>
          </tr>
        </thead>
        <tbody>
          {s.papers.map((p) => (
            <tr key={p.subject_name} className="border-b border-slate-200">
              <td className="py-1">{p.exam_date ?? "—"}</td>
              <td>{p.subject_code}</td>
              <td>{p.subject_name}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-6 flex justify-between text-xs text-slate-500">
        <span>Student signature</span>
        <span>Principal / Controller of Examinations</span>
      </div>
    </div>
  );
}

function HallTicketsPage() {
  const { token } = useAuth();
  const [exams, , examsState] = useLoad(
    () => apiRequest("/exams", { token }),
    [token],
  );
  const [examId, setExamId] = useState("");
  const [sheet, setSheet] = useState(null);
  const [state, setState] = useState("idle");
  const [minimum, setMinimum] = useState("");
  const [rooms, setRooms] = useState([]);
  const [view, setView] = useState("list");
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (!examId && exams?.length)
      setExamId((exams.find((e) => !e.published) ?? exams[0]).id);
  }, [exams, examId]);

  function take(data) {
    setSheet(data);
    setMinimum(data.min_attendance ?? "");
    setRooms(data.rooms.map((r) => ({ name: r.name, capacity: r.capacity })));
  }

  useEffect(() => {
    if (!examId) return;
    setState("loading");
    apiRequest(`/exams/${examId}/hall-tickets`, { token })
      .then((data) => {
        take(data);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token, examId]);

  async function call(path, body, done) {
    setError(null);
    setMessage(null);
    try {
      take(
        await apiRequest(`/exams/${examId}/hall-tickets/${path}`, {
          method: "PUT",
          token,
          body,
        }),
      );
      if (done) setMessage(done);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  const eligible = sheet?.students.filter((s) => s.eligible) ?? [];
  return (
    <div className="space-y-6">
      <div className="no-print">
        <PageHeader
          title="Hall tickets & seating"
          subtitle="Attendance rule, condonation, exam rooms and seat numbers. Release to show hall tickets in the student app."
        />
      </div>
      {examsState !== "ready" ? (
        <LoadState state={examsState} what="exams" />
      ) : (
        <div className="no-print grid gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-4 md:items-end">
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Exam
            <select
              value={examId}
              onChange={(e) => setExamId(e.target.value)}
              className={INPUT}
            >
              {exams.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name} ({e.academic_year})
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Minimum attendance %
            <input
              type="number"
              min="0"
              max="100"
              placeholder="No rule"
              value={minimum}
              onChange={(e) => setMinimum(e.target.value)}
              className={INPUT}
            />
          </label>
          {sheet && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() =>
                  call(
                    "settings",
                    {
                      min_attendance: minimum === "" ? null : Number(minimum),
                      released: sheet.released,
                    },
                    "Saved.",
                  )
                }
                className={SECONDARY}
              >
                Save rule
              </button>
              <button
                type="button"
                onClick={() =>
                  call(
                    "settings",
                    {
                      min_attendance: minimum === "" ? null : Number(minimum),
                      released: !sheet.released,
                    },
                    sheet.released
                      ? "Hidden from the app."
                      : "Released to the app.",
                  )
                }
                className={PRIMARY}
              >
                {sheet.released ? "Unrelease" : "Release to app"}
              </button>
            </div>
          )}
        </div>
      )}
      <div className="no-print">
        <Notice message={message} error={error} />
      </div>
      {state === "loading" && <LoadState state="loading" />}
      {state === "error" && (
        <LoadState
          state="error"
          what="hall tickets"
          onRetry={() => setExamId(examId)}
        />
      )}
      {state === "ready" && sheet && (
        <>
          <div className="no-print grid gap-3 sm:grid-cols-4">
            <Stat label="Writing" value={sheet.students.length} />
            <Stat label="Eligible" value={eligible.length} tone="emerald" />
            <Stat
              label="Not eligible"
              value={sheet.students.length - eligible.length}
              tone="rose"
            />
            <Stat
              label="Without a seat"
              value={sheet.unseated}
              tone={sheet.unseated ? "rose" : "slate"}
            />
          </div>
          <div className="no-print space-y-2 rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="font-semibold text-slate-900">
              Exam rooms (filled in this order)
            </h3>
            {rooms.map((r, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <input
                  aria-label="Room"
                  value={r.name}
                  onChange={(e) =>
                    setRooms(
                      rooms.map((x, j) =>
                        j === i ? { ...x, name: e.target.value } : x,
                      ),
                    )
                  }
                  className="w-40 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                />
                <input
                  aria-label="Seats"
                  type="number"
                  min="1"
                  value={r.capacity}
                  onChange={(e) =>
                    setRooms(
                      rooms.map((x, j) =>
                        j === i ? { ...x, capacity: e.target.value } : x,
                      ),
                    )
                  }
                  className="w-24 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                />
                <span className="text-xs text-slate-500">
                  seats
                  {sheet.rooms[i] ? ` · ${sheet.rooms[i].seated} seated` : ""}
                </span>
                <button
                  type="button"
                  onClick={() => setRooms(rooms.filter((_, j) => j !== i))}
                  className="text-xs text-rose-600 hover:underline"
                >
                  remove
                </button>
              </div>
            ))}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() =>
                  setRooms([
                    ...rooms,
                    { name: `Room ${rooms.length + 1}`, capacity: 30 },
                  ])
                }
                className={SECONDARY}
              >
                + Add room
              </button>
              <button
                type="button"
                onClick={() =>
                  call(
                    "rooms",
                    rooms.map((r) => ({
                      name: r.name,
                      capacity: Number(r.capacity),
                    })),
                    "Rooms saved, seats assigned.",
                  )
                }
                className={PRIMARY}
              >
                Save rooms & assign seats
              </button>
            </div>
          </div>
          <div className="no-print flex flex-wrap gap-2">
            {[
              ["list", "Students"],
              ["tickets", "Print hall tickets"],
              ["seating", "Print seating chart"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setView(id)}
                className={`rounded-lg px-3 py-2 text-sm font-semibold ring-1 ring-inset ${view === id ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-700 ring-slate-300"}`}
              >
                {label}
              </button>
            ))}
          </div>
          {view === "list" && (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Student</th>
                    <th className="px-3 py-2">Batch</th>
                    <th className="px-3 py-2 text-center">Attendance</th>
                    <th className="px-3 py-2">Hall ticket</th>
                    <th className="px-3 py-2">Room / seat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sheet.students.map((s) => (
                    <tr key={s.student_id}>
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-900">
                          {s.full_name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {s.admission_number}
                        </p>
                      </td>
                      <td className="px-3 py-2 text-slate-700">{s.batch}</td>
                      <td className="px-3 py-2 text-center">
                        {s.attendance === null ? "—" : `${s.attendance}%`}
                      </td>
                      <td className="px-3 py-2">
                        <select
                          aria-label={`Hall ticket for ${s.full_name}`}
                          value={
                            s.override === null
                              ? "auto"
                              : s.override
                                ? "allow"
                                : "hold"
                          }
                          onChange={(e) =>
                            call("override", {
                              student_id: s.student_id,
                              allowed: { auto: null, allow: true, hold: false }[
                                e.target.value
                              ],
                            })
                          }
                          className={`rounded border px-2 py-1 text-xs font-semibold ${s.eligible ? "border-emerald-300 text-emerald-700" : "border-rose-300 text-rose-700"}`}
                        >
                          <option value="auto">
                            {s.override === null
                              ? s.eligible
                                ? "Eligible (rule)"
                                : "Short attendance"
                              : "By rule"}
                          </option>
                          <option value="allow">Allow (condoned)</option>
                          <option value="hold">Hold back</option>
                        </select>
                      </td>
                      <td className="px-3 py-2 text-slate-700">
                        {s.room ? `${s.room} · ${s.seat}` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {view === "tickets" && (
            <PrintPortal
              title={`Hall tickets · ${sheet.exam_name} · ${eligible.length} students`}
              onClose={() => setView("list")}
            >
              <div
                className="print-page grid grid-cols-2 gap-4 bg-white p-[8mm]"
                style={{ width: "190mm" }}
              >
                {eligible.map((s) => (
                  <Ticket key={s.student_id} sheet={sheet} s={s} />
                ))}
              </div>
            </PrintPortal>
          )}
          {view === "seating" && (
            <PrintPortal
              title={`Seating chart · ${sheet.exam_name}`}
              onClose={() => setView("list")}
            >
              {sheet.rooms.map((room) => (
                <div
                  key={room.name}
                  className="print-page print-break bg-white p-[8mm]"
                  style={{ width: "190mm" }}
                >
                  <h3 className="text-lg font-bold">
                    {sheet.exam_name} · {room.name}
                  </h3>
                  <table className="mt-2 w-full text-sm">
                    <thead className="text-left text-xs uppercase text-slate-500">
                      <tr>
                        <th className="py-1">Seat</th>
                        <th>Roll no</th>
                        <th>Name</th>
                        <th>Batch</th>
                        <th>Signature</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sheet.students
                        .filter((s) => s.room === room.name)
                        .sort((x, y) => x.seat - y.seat)
                        .map((s) => (
                          <tr
                            key={s.student_id}
                            className="border-t border-slate-200"
                          >
                            <td className="py-1.5 font-bold">{s.seat}</td>
                            <td>{s.admission_number}</td>
                            <td>{s.full_name}</td>
                            <td>{s.batch}</td>
                            <td className="w-40" />
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </PrintPortal>
          )}
        </>
      )}
    </div>
  );
}

export default HallTicketsPage;

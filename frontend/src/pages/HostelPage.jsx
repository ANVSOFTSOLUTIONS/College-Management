import { useState } from "react";

import { addRoom, allocateRoom, deleteHostel, deleteRoom, fetchHostels, saveHostel, vacateRoom } from "../api/campusApi";
import { DANGER, errorMessage, Field, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, Stat, StudentPicker, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";

const EMPTY_HOSTEL = { name: "", gender: "boys", warden_name: "", warden_phone: "" };
const GENDERS = { boys: "Boys", girls: "Girls", mixed: "Mixed" };

function HostelForm({ token, hostel, onDone }) {
  const [form, setForm] = useState(hostel ? { name: hostel.name, gender: hostel.gender, warden_name: hostel.warden_name, warden_phone: hostel.warden_phone } : EMPTY_HOSTEL);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    try {
      await saveHostel(token, form, hostel?.id);
      onDone(hostel ? "Hostel updated." : `${form.name} added. Now add its rooms.`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the hostel."));
    }
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-4">
      <Field id="hostel-name" label="Name">
        <input id="hostel-name" required maxLength={150} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={INPUT} placeholder="e.g. Boys Hostel A" />
      </Field>
      <Field id="hostel-gender" label="For">
        <select id="hostel-gender" value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} className={INPUT}>
          {Object.entries(GENDERS).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </Field>
      <Field id="hostel-warden" label="Warden">
        <input id="hostel-warden" maxLength={150} value={form.warden_name} onChange={(e) => setForm({ ...form, warden_name: e.target.value })} className={INPUT} />
      </Field>
      <Field id="hostel-phone" label="Warden phone">
        <input id="hostel-phone" type="tel" maxLength={20} value={form.warden_phone} onChange={(e) => setForm({ ...form, warden_phone: e.target.value })} className={INPUT} />
      </Field>
      <div className="flex items-center gap-3 sm:col-span-4">
        <button type="submit" className={PRIMARY}>
          {hostel ? "Save hostel" : "Add hostel"}
        </button>
        <button type="button" onClick={() => onDone(null)} className="text-sm font-semibold text-slate-500">
          Cancel
        </button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function RoomAdder({ token, hostel, onDone, onError }) {
  const [room, setRoom] = useState({ room_number: "", capacity: 3, room_type: "non-ac" });
  async function submit(event) {
    event.preventDefault();
    try {
      await addRoom(token, hostel.id, { ...room, capacity: Number(room.capacity) });
      setRoom({ ...room, room_number: "" });
      onDone(`Room ${room.room_number} added.`);
    } catch (err) {
      onError(errorMessage(err, "Couldn't add the room."));
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <input aria-label="Room number" required maxLength={20} placeholder="Room no." value={room.room_number} onChange={(e) => setRoom({ ...room, room_number: e.target.value })}
        className="w-28 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
      <input aria-label="Beds" type="number" min={1} max={20} value={room.capacity} onChange={(e) => setRoom({ ...room, capacity: e.target.value })}
        className="w-20 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
      <select aria-label="Room type" value={room.room_type} onChange={(e) => setRoom({ ...room, room_type: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">
        <option value="non-ac">Non-AC</option>
        <option value="ac">AC</option>
      </select>
      <button type="submit" className={SECONDARY}>
        + Room
      </button>
    </form>
  );
}

function HostelPage() {
  const { token } = useAuth();
  const [hostels, reload, state] = useLoad(() => fetchHostels(token), [token]);
  const [editing, setEditing] = useState(null); // null | "new" | hostel
  const [allocating, setAllocating] = useState(null); // room being filled
  const [student, setStudent] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  function done(msg) {
    setEditing(null);
    setError(null);
    if (msg) setMessage(msg);
    reload();
  }

  async function run(action, success, fallback, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return;
    setMessage(null);
    setError(null);
    try {
      await action();
      done(success);
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  }

  async function allocate() {
    await run(() => allocateRoom(token, { student_id: student.id, room_id: allocating.id }), `${student.full_name} allocated to room ${allocating.room_number}.`, "Couldn't allocate the room.");
    setAllocating(null);
    setStudent(null);
  }

  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="hostels" />;
  const capacity = hostels.reduce((n, h) => n + h.capacity, 0);
  const occupied = hostels.reduce((n, h) => n + h.occupied, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Hostel" subtitle="Hostels, rooms and beds, and who stays where. Charge hostel fees from Fees (type: Hostel).">
        <button type="button" onClick={() => setEditing("new")} className={PRIMARY}>
          Add hostel
        </button>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Hostels" value={hostels.length} />
        <Stat label="Beds" value={capacity} />
        <Stat label="Occupied" value={occupied} />
        <Stat label="Free beds" value={capacity - occupied} tone="emerald" />
      </div>

      <Notice message={message} error={error} />
      {editing && <HostelForm key={editing.id ?? "new"} token={token} hostel={editing === "new" ? null : editing} onDone={done} />}

      {allocating && (
        <div className="space-y-3 rounded-xl border border-emerald-200 bg-white p-5">
          <p className="text-sm font-semibold text-slate-800">
            Allocate a student to room {allocating.room_number} ({allocating.capacity - allocating.occupants.length} bed(s) free)
          </p>
          <StudentPicker token={token} id="hostel-student" value={student} onChange={setStudent} />
          <p className="text-xs text-slate-400">A student already in another room is moved here.</p>
          <div className="flex gap-3">
            <button type="button" disabled={!student} onClick={allocate} className={PRIMARY}>
              Allocate
            </button>
            <button type="button" onClick={() => { setAllocating(null); setStudent(null); }} className="text-sm font-semibold text-slate-500">
              Cancel
            </button>
          </div>
        </div>
      )}

      {hostels.length === 0 && !editing && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No hostels yet.</p>
      )}

      {hostels.map((h) => (
        <section key={h.id} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                {h.name} <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{GENDERS[h.gender]}</span>
              </h3>
              <p className="text-sm text-slate-500">
                {h.warden_name && `Warden: ${h.warden_name}${h.warden_phone ? ` (${h.warden_phone})` : ""} · `}
                {h.occupied}/{h.capacity} beds filled
              </p>
            </div>
            <div className="flex gap-2">
              <button type="button" className={SECONDARY} onClick={() => setEditing(h)}>
                Edit
              </button>
              <button type="button" className={DANGER} onClick={() => run(() => deleteHostel(token, h.id), "Hostel deleted.", "Couldn't delete the hostel.", `Delete ${h.name}?`)}>
                Delete
              </button>
            </div>
          </div>
          <RoomAdder token={token} hostel={h} onDone={done} onError={setError} />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {h.rooms.map((r) => {
              const free = r.capacity - r.occupants.length;
              return (
                <div key={r.id} className={`rounded-lg border p-3 ${free ? "border-slate-200" : "border-amber-200 bg-amber-50/40"}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-slate-800">
                      Room {r.room_number} <span className="text-xs font-normal uppercase text-slate-400">{r.room_type}</span>
                    </p>
                    <span className={`text-xs font-semibold ${free ? "text-emerald-700" : "text-amber-700"}`}>
                      {r.occupants.length}/{r.capacity}
                    </span>
                  </div>
                  <ul className="mt-2 space-y-1">
                    {r.occupants.map((o) => (
                      <li key={o.allocation_id} className="flex items-center justify-between text-sm">
                        <span>
                          {o.full_name} <span className="text-xs text-slate-400">{o.admission_number}</span>
                        </span>
                        <button type="button" className="text-xs font-semibold text-rose-600 hover:underline"
                          onClick={() => run(() => vacateRoom(token, o.allocation_id), `${o.full_name} vacated.`, "Couldn't vacate.", `Vacate ${o.full_name} from room ${r.room_number}?`)}>
                          Vacate
                        </button>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-2 flex gap-2">
                    {free > 0 && (
                      <button type="button" className={SECONDARY} onClick={() => { setAllocating(r); setStudent(null); }}>
                        + Student
                      </button>
                    )}
                    {r.occupants.length === 0 && (
                      <button type="button" className={DANGER} onClick={() => run(() => deleteRoom(token, r.id), "Room deleted.", "Couldn't delete the room.", `Delete room ${r.room_number}?`)}>
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

export default HostelPage;

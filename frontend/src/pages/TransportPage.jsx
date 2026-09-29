import { useState } from "react";

import { assignRoute, deleteRoute, fetchRoutes, saveRoute, unassignRoute } from "../api/campusApi";
import { DANGER, errorMessage, Field, INPUT, LoadState, Notice, PageHeader, PRIMARY, rupees, SECONDARY, Stat, StudentPicker, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";

const EMPTY_ROUTE = { name: "", vehicle_number: "", driver_name: "", driver_phone: "", seats: 50, annual_fare: 0, stops: [] };

function RouteForm({ token, route, onDone }) {
  const [form, setForm] = useState(() =>
    route ? { ...route, stops: route.stops.map(({ name, pickup_time }) => ({ name, pickup_time })) } : { ...EMPTY_ROUTE, stops: [{ name: "", pickup_time: "" }] },
  );
  const [error, setError] = useState(null);

  function setStop(index, key, value) {
    setForm({ ...form, stops: form.stops.map((s, i) => (i === index ? { ...s, [key]: value } : s)) });
  }

  async function submit(event) {
    event.preventDefault();
    try {
      const { name, vehicle_number, driver_name, driver_phone, seats, annual_fare } = form;
      await saveRoute(
        token,
        { name, vehicle_number, driver_name, driver_phone, seats: Number(seats), annual_fare: Number(annual_fare), stops: form.stops.filter((s) => s.name.trim()) },
        route?.id,
      );
      onDone(route ? "Route updated." : `${form.name} added.`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the route."));
    }
  }

  const input = (key, label, props = {}) => (
    <Field id={`route-${key}`} label={label}>
      <input id={`route-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </Field>
  );
  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {input("name", "Route name", { required: true, maxLength: 150, placeholder: "e.g. Route 1 - Kavali Town" })}
        {input("vehicle_number", "Bus number", { maxLength: 20, placeholder: "AP39 TA 1234" })}
        {input("seats", "Seats", { type: "number", min: 1, required: true })}
        {input("driver_name", "Driver", { maxLength: 150 })}
        {input("driver_phone", "Driver phone", { type: "tel", maxLength: 20 })}
        {input("annual_fare", "Annual fare (₹)", { type: "number", min: 0 })}
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-700">Stops, in pickup order</legend>
        {form.stops.map((stop, i) => (
          <div key={i} className="flex gap-2">
            <input aria-label={`Stop ${i + 1}`} placeholder={`Stop ${i + 1}`} value={stop.name} onChange={(e) => setStop(i, "name", e.target.value)}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
            <input aria-label={`Pickup time ${i + 1}`} type="time" value={stop.pickup_time} onChange={(e) => setStop(i, "pickup_time", e.target.value)}
              className="w-32 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
            <button type="button" aria-label="Remove stop" onClick={() => setForm({ ...form, stops: form.stops.filter((_, j) => j !== i) })}
              className="px-2 text-slate-400 hover:text-rose-600">
              ×
            </button>
          </div>
        ))}
        <button type="button" className={SECONDARY} onClick={() => setForm({ ...form, stops: [...form.stops, { name: "", pickup_time: "" }] })}>
          + Stop
        </button>
      </fieldset>
      <div className="flex items-center gap-3">
        <button type="submit" className={PRIMARY}>
          {route ? "Save route" : "Add route"}
        </button>
        <button type="button" onClick={() => onDone(null)} className="text-sm font-semibold text-slate-500">
          Cancel
        </button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function TransportPage() {
  const { token } = useAuth();
  const [routes, reload, state] = useLoad(() => fetchRoutes(token), [token]);
  const [editing, setEditing] = useState(null);
  const [assigning, setAssigning] = useState(null); // route
  const [student, setStudent] = useState(null);
  const [stopId, setStopId] = useState("");
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
      return true;
    } catch (err) {
      setError(errorMessage(err, fallback));
      return false;
    }
  }

  async function assign() {
    const ok = await run(() => assignRoute(token, { student_id: student.id, route_id: assigning.id, stop_id: stopId || null }), `${student.full_name} added to ${assigning.name}.`, "Couldn't assign the route.");
    if (ok) {
      setAssigning(null);
      setStudent(null);
      setStopId("");
    }
  }

  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="routes" />;
  const riders = routes.reduce((n, r) => n + r.riders.length, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Transport" subtitle="Bus routes, stops and riders. Charge bus fees from Fees (type: Transport).">
        <button type="button" onClick={() => setEditing("new")} className={PRIMARY}>
          Add route
        </button>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Routes" value={routes.length} />
        <Stat label="Riders" value={riders} />
        <Stat label="Free seats" value={routes.reduce((n, r) => n + r.seats, 0) - riders} tone="emerald" />
      </div>

      <Notice message={message} error={error} />
      {editing && <RouteForm key={editing.id ?? "new"} token={token} route={editing === "new" ? null : editing} onDone={done} />}

      {assigning && (
        <div className="grid gap-3 rounded-xl border border-emerald-200 bg-white p-5 sm:grid-cols-2">
          <p className="text-sm font-semibold text-slate-800 sm:col-span-2">Add a rider to {assigning.name}</p>
          <Field id="rider-student" label="Student">
            <StudentPicker token={token} id="rider-student" value={student} onChange={setStudent} />
          </Field>
          <Field id="rider-stop" label="Boarding stop">
            <select id="rider-stop" value={stopId} onChange={(e) => setStopId(e.target.value)} className={INPUT}>
              <option value="">—</option>
              {assigning.stops.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} {s.pickup_time && `(${s.pickup_time})`}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex gap-3 sm:col-span-2">
            <button type="button" disabled={!student} onClick={assign} className={PRIMARY}>
              Add rider
            </button>
            <button type="button" onClick={() => setAssigning(null)} className="text-sm font-semibold text-slate-500">
              Cancel
            </button>
          </div>
        </div>
      )}

      {routes.length === 0 && !editing && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No routes yet.</p>
      )}

      {routes.map((r) => (
        <section key={r.id} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">{r.name}</h3>
              <p className="text-sm text-slate-500">
                {[r.vehicle_number, r.driver_name && `Driver ${r.driver_name}${r.driver_phone ? ` (${r.driver_phone})` : ""}`, r.annual_fare > 0 && `${rupees(r.annual_fare)} / year`]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <p className="text-sm text-slate-500">
                {r.riders.length}/{r.seats} seats filled
              </p>
            </div>
            <div className="flex gap-2">
              {r.riders.length < r.seats && (
                <button type="button" className={SECONDARY} onClick={() => { setAssigning(r); setStudent(null); setStopId(""); }}>
                  + Rider
                </button>
              )}
              <button type="button" className={SECONDARY} onClick={() => setEditing(r)}>
                Edit
              </button>
              <button type="button" className={DANGER} onClick={() => run(() => deleteRoute(token, r.id), "Route deleted.", "Couldn't delete the route.", `Delete ${r.name}?`)}>
                Delete
              </button>
            </div>
          </div>
          {r.stops.length > 0 && (
            <ol className="flex flex-wrap gap-2 text-xs">
              {r.stops.map((s, i) => (
                <li key={s.id} className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                  {i + 1}. {s.name} {s.pickup_time && <span className="text-slate-400">{s.pickup_time}</span>}
                </li>
              ))}
            </ol>
          )}
          {r.riders.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {r.riders.map((x) => (
                <li key={x.student_id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>
                    {x.full_name} <span className="text-xs text-slate-400">{x.admission_number} · {x.class_name}</span>
                    {x.stop_name && <span className="ml-2 text-xs text-emerald-700">{x.stop_name}</span>}
                  </span>
                  <button type="button" className="text-xs font-semibold text-rose-600 hover:underline"
                    onClick={() => run(() => unassignRoute(token, x.student_id), `${x.full_name} removed from ${r.name}.`, "Couldn't remove the rider.", `Remove ${x.full_name} from this route?`)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}

export default TransportPage;

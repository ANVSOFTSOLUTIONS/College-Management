import { useState } from "react";

import { fetchDepartments } from "../api/academicsApi";
import {
  applyToDrive,
  deleteCompany,
  deleteDrive,
  fetchApplications,
  fetchCompanies,
  fetchDrives,
  fetchMyDrives,
  fetchPlacementStats,
  saveCompany,
  saveDrive,
  setApplicationStatus,
  withdrawFromDrive,
} from "../api/campusApi";
import { DANGER, errorMessage, Field, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, Stat, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";

const STATUS_STYLES = {
  applied: "bg-sky-50 text-sky-700",
  shortlisted: "bg-amber-50 text-amber-700",
  selected: "bg-emerald-50 text-emerald-700",
  rejected: "bg-rose-50 text-rose-700",
  open: "bg-emerald-50 text-emerald-700",
  closed: "bg-slate-100 text-slate-600",
  completed: "bg-slate-100 text-slate-600",
};

function Badge({ value }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${STATUS_STYLES[value] ?? "bg-slate-100 text-slate-600"}`}>{value}</span>;
}

function driveFacts(d) {
  return [
    d.package_lpa !== null && `${d.package_lpa} LPA`,
    d.location,
    d.drive_date && `Drive ${d.drive_date}`,
    d.last_date && `Apply by ${d.last_date}`,
    d.min_cgpa !== null && `CGPA ≥ ${d.min_cgpa}`,
    d.eligible_departments.length ? d.eligible_departments.join(", ") : "All departments",
  ]
    .filter(Boolean)
    .join(" · ");
}

function DriveForm({ token, drive, companies, departments, onDone }) {
  const [form, setForm] = useState(() => ({
    company_id: drive?.company_id ?? companies[0]?.id ?? "",
    role_title: drive?.role_title ?? "",
    package_lpa: drive?.package_lpa ?? "",
    location: drive?.location ?? "",
    drive_date: drive?.drive_date ?? "",
    last_date: drive?.last_date ?? "",
    min_cgpa: drive?.min_cgpa ?? "",
    eligible_department_ids: drive?.eligible_department_ids ?? [],
    description: drive?.description ?? "",
    status: drive?.status ?? "open",
  }));
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    try {
      await saveDrive(
        token,
        {
          ...form,
          package_lpa: form.package_lpa === "" ? null : Number(form.package_lpa),
          min_cgpa: form.min_cgpa === "" ? null : Number(form.min_cgpa),
          drive_date: form.drive_date || null,
          last_date: form.last_date || null,
        },
        drive?.id,
      );
      onDone(drive ? "Drive updated." : "Drive created. Eligible students can apply from their portal.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the drive."));
    }
  }

  const input = (key, label, props = {}) => (
    <Field id={`drive-${key}`} label={label}>
      <input id={`drive-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </Field>
  );
  const toggleDept = (id) =>
    setForm({
      ...form,
      eligible_department_ids: form.eligible_department_ids.includes(id) ? form.eligible_department_ids.filter((x) => x !== id) : [...form.eligible_department_ids, id],
    });

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <Field id="drive-company" label="Company">
          <select id="drive-company" required value={form.company_id} onChange={(e) => setForm({ ...form, company_id: e.target.value })} className={INPUT}>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <div className="sm:col-span-2">{input("role_title", "Role", { required: true, maxLength: 150, placeholder: "e.g. Systems Engineer" })}</div>
        {input("package_lpa", "Package (LPA)", { type: "number", min: 0, step: "0.1" })}
        {input("location", "Location", { maxLength: 150 })}
        {input("last_date", "Last date to apply", { type: "date" })}
        {input("drive_date", "Drive date", { type: "date" })}
        {input("min_cgpa", "Minimum CGPA", { type: "number", min: 0, max: 10, step: "0.1" })}
        <Field id="drive-status" label="Status">
          <select id="drive-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className={INPUT}>
            <option value="open">Open for applications</option>
            <option value="closed">Closed</option>
            <option value="completed">Completed</option>
          </select>
        </Field>
      </div>
      {departments.length > 0 && (
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Eligible departments (none chosen: all)</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {departments.map((d) => (
              <label key={d.id}
                className={`flex cursor-pointer items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${form.eligible_department_ids.includes(d.id) ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-600 ring-slate-300"}`}>
                <input type="checkbox" className="sr-only" checked={form.eligible_department_ids.includes(d.id)} onChange={() => toggleDept(d.id)} />
                {d.code}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <Field id="drive-description" label="Details (rounds, bond, documents to bring…)">
        <textarea id="drive-description" rows={3} maxLength={5000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className={INPUT} />
      </Field>
      <div className="flex items-center gap-3">
        <button type="submit" className={PRIMARY}>
          {drive ? "Save drive" : "Create drive"}
        </button>
        <button type="button" onClick={() => onDone(null)} className="text-sm font-semibold text-slate-500">
          Cancel
        </button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function Applicants({ token, drive, onChanged }) {
  const [apps, reload, state] = useLoad(() => fetchApplications(token, drive.id), [token, drive.id]);
  const [error, setError] = useState(null);

  async function change(app, status) {
    try {
      await setApplicationStatus(token, app.id, status);
      await reload();
      onChanged();
    } catch (err) {
      setError(errorMessage(err, "Couldn't update the application."));
    }
  }

  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="applications" />;
  if (apps.length === 0) return <p className="text-sm text-slate-500">No applications yet.</p>;
  return (
    <div className="overflow-x-auto">
      {error && <p className="mb-2 text-sm text-rose-600">{error}</p>}
      <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
        <thead className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="py-2 pr-4">Student</th>
            <th className="py-2 pr-4">Batch</th>
            <th className="py-2 pr-4">CGPA</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {apps.map((a) => (
            <tr key={a.id}>
              <td className="py-2 pr-4">
                <p className="font-medium text-slate-800">{a.full_name}</p>
                <p className="text-xs text-slate-400">{a.admission_number}</p>
              </td>
              <td className="py-2 pr-4 text-slate-600">
                {a.class_name} {a.department && `(${a.department})`}
              </td>
              <td className="py-2 pr-4 text-slate-700">{a.cgpa ?? "—"}</td>
              <td className="py-2 pr-4">
                <Badge value={a.status} />
              </td>
              <td className="py-2">
                <select aria-label={`Status of ${a.full_name}`} value={a.status} onChange={(e) => change(a, e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1 text-xs">
                  {["applied", "shortlisted", "selected", "rejected"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PlacementsPage() {
  const { token } = useAuth();
  const [stats, reloadStats] = useLoad(() => fetchPlacementStats(token), [token]);
  const [companies, reloadCompanies, companyState] = useLoad(() => fetchCompanies(token), [token]);
  const [drives, reloadDrives, driveState] = useLoad(() => fetchDrives(token), [token]);
  const [departments] = useLoad(() => fetchDepartments(token), [token]);
  const [editing, setEditing] = useState(null); // null | "new" | drive
  const [openDrive, setOpenDrive] = useState(null);
  const [company, setCompany] = useState({ name: "", industry: "", website: "" });
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  function refresh(msg) {
    setEditing(null);
    setError(null);
    if (msg) setMessage(msg);
    reloadStats();
    reloadCompanies();
    reloadDrives();
  }

  async function run(action, success, fallback, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return;
    setMessage(null);
    setError(null);
    try {
      await action();
      refresh(success);
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  }

  async function addCompany(event) {
    event.preventDefault();
    await run(() => saveCompany(token, company), `${company.name} added.`, "Couldn't add the company.");
    setCompany({ name: "", industry: "", website: "" });
  }

  if (companyState !== "ready" || driveState !== "ready") return <LoadState state={companyState === "ready" ? driveState : companyState} onRetry={() => refresh()} what="placements" />;

  return (
    <div className="space-y-6">
      <PageHeader title="Placements" subtitle="Training & placement cell: companies, recruitment drives, and who got placed.">
        {companies.length > 0 && (
          <button type="button" onClick={() => setEditing("new")} className={PRIMARY}>
            New drive
          </button>
        )}
      </PageHeader>

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Stat label="Companies" value={stats.companies} />
          <Stat label="Open drives" value={stats.open_drives} />
          <Stat label="Applications" value={stats.applications} />
          <Stat label="Students placed" value={stats.students_placed} tone="emerald" />
          <Stat label="Highest / average" value={stats.highest_package !== null ? `${stats.highest_package} / ${stats.average_package} LPA` : "—"} />
        </div>
      )}

      <Notice message={message} error={error} />
      {editing && (
        <DriveForm key={editing.id ?? "new"} token={token} drive={editing === "new" ? null : editing} companies={companies} departments={departments ?? []} onDone={refresh} />
      )}

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-slate-900">Drives</h3>
        {drives.length === 0 && <p className="text-sm text-slate-500">{companies.length ? "No drives yet." : "Add a company below first."}</p>}
        <ul className="divide-y divide-slate-100">
          {drives.map((d) => (
            <li key={d.id} className="py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <button type="button" onClick={() => setOpenDrive(openDrive === d.id ? null : d.id)} className="text-left">
                  <p className="font-semibold text-slate-800">
                    {d.company_name} — {d.role_title} <Badge value={d.status} />
                  </p>
                  <p className="text-xs text-slate-500">{driveFacts(d)}</p>
                  <p className="text-xs text-slate-500">
                    {d.applicants} applied · {d.shortlisted} shortlisted · <span className="font-semibold text-emerald-700">{d.selected} selected</span>
                  </p>
                </button>
                <div className="flex gap-2">
                  <button type="button" className={SECONDARY} onClick={() => setOpenDrive(openDrive === d.id ? null : d.id)}>
                    Applicants
                  </button>
                  <button type="button" className={SECONDARY} onClick={() => setEditing(d)}>
                    Edit
                  </button>
                  <button type="button" className={DANGER}
                    onClick={() => run(() => deleteDrive(token, d.id), "Drive deleted.", "Couldn't delete the drive.", `Delete this drive and its ${d.applicants} application(s)?`)}>
                    Delete
                  </button>
                </div>
              </div>
              {openDrive === d.id && (
                <div className="mt-3 rounded-lg bg-slate-50 p-3">
                  <Applicants token={token} drive={d} onChanged={() => { reloadStats(); reloadDrives(); }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-slate-900">Companies</h3>
        <form onSubmit={addCompany} className="flex flex-wrap items-end gap-2">
          <input aria-label="Company name" required maxLength={150} placeholder="Company name" value={company.name} onChange={(e) => setCompany({ ...company, name: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input aria-label="Industry" maxLength={100} placeholder="Industry (IT, Core, BFSI…)" value={company.industry} onChange={(e) => setCompany({ ...company, industry: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input aria-label="Website" maxLength={200} placeholder="Website" value={company.website} onChange={(e) => setCompany({ ...company, website: e.target.value })}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button type="submit" className={PRIMARY}>
            Add company
          </button>
        </form>
        <div className="flex flex-wrap gap-2">
          {companies.map((c) => (
            <span key={c.id} className="inline-flex items-center gap-2 rounded-full bg-slate-100 py-1 pl-3 pr-1 text-sm text-slate-700">
              {c.name}
              <span className="text-xs text-slate-400">
                {c.industry && `${c.industry} · `}
                {c.drives} drive(s) · {c.selected} placed
              </span>
              <button type="button" aria-label={`Delete ${c.name}`} className="rounded-full px-2 text-slate-400 hover:bg-rose-100 hover:text-rose-600"
                onClick={() => run(() => deleteCompany(token, c.id), `${c.name} deleted.`, "Couldn't delete the company.", `Delete ${c.name}?`)}>
                ×
              </button>
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}

export function MyPlacementsPage() {
  const { token } = useAuth();
  const [drives, reload, state] = useLoad(() => fetchMyDrives(token), [token]);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function run(action, success, fallback) {
    setMessage(null);
    setError(null);
    try {
      await action();
      setMessage(success);
      reload();
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  }

  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="placement drives" />;
  return (
    <div className="space-y-6">
      <PageHeader title="Placements" subtitle="Open recruitment drives, whether you're eligible, and your applications." />
      <Notice message={message} error={error} />
      {drives.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No open drives right now. Check back soon.</p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {drives.map((d) => (
          <div key={d.id} className="flex flex-col rounded-xl border border-slate-200 bg-white p-5">
            <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">{d.company_name}</p>
            <h3 className="mt-0.5 font-semibold text-slate-900">{d.role_title}</h3>
            <p className="mt-1 text-sm text-slate-500">{driveFacts(d)}</p>
            {d.description && <p className="mt-2 whitespace-pre-line text-sm text-slate-600">{d.description}</p>}
            <div className="mt-auto flex items-center justify-between gap-2 pt-4">
              {d.my_status ? (
                <>
                  <span className="text-sm">
                    Your application: <Badge value={d.my_status} />
                  </span>
                  {d.my_status === "applied" && (
                    <button type="button" className={DANGER} onClick={() => run(() => withdrawFromDrive(token, d.id), "Application withdrawn.", "Couldn't withdraw.")}>
                      Withdraw
                    </button>
                  )}
                </>
              ) : d.eligible ? (
                <button type="button" className={PRIMARY} onClick={() => run(() => applyToDrive(token, d.id), `Applied to ${d.company_name}.`, "Couldn't apply.")}>
                  Apply
                </button>
              ) : (
                <span className="text-sm text-slate-500">Not eligible: {d.reason}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default PlacementsPage;

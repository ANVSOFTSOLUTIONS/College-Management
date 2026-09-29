import { Fragment, useCallback, useEffect, useState } from "react";

import { createSchool, fetchSchools, updateSchool } from "../api/superAdminApi";
import { BILLING_STATUSES, MODULES, THEMES } from "../constants/schoolOptions";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const ALL_MODULE_IDS = MODULES.map((m) => m.id);

const EMPTY_CREATE_FORM = {
  name: "",
  code: "",
  subdomain: "",
  template: "",
  monthly_fee: 600,
  billing_status: "trial",
  admin_full_name: "",
  admin_email: "",
  admin_password: "",
  enabled_modules: ALL_MODULE_IDS,
};

function billingBadgeClass(status) {
  if (status === "active") return "bg-emerald-50 text-emerald-700";
  if (status === "suspended") return "bg-rose-50 text-rose-700";
  return "bg-amber-50 text-amber-700";
}

function ModuleCheckboxes({ value, onChange, idPrefix }) {
  function toggle(moduleId) {
    onChange(value.includes(moduleId) ? value.filter((m) => m !== moduleId) : [...value, moduleId]);
  }

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
      {MODULES.map((module) => (
        <label key={module.id} className="flex items-center gap-2 text-xs text-slate-600">
          <input
            id={`${idPrefix}-${module.id}`}
            type="checkbox"
            checked={value.includes(module.id)}
            onChange={() => toggle(module.id)}
            className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
          />
          {module.label}
        </label>
      ))}
    </div>
  );
}

function CreateSchoolForm({ token, onCreated, onCancel }) {
  const [form, setForm] = useState(EMPTY_CREATE_FORM);
  const [saveState, setSaveState] = useState("idle");
  const [error, setError] = useState(null);

  function setField(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaveState("saving");
    setError(null);
    try {
      const result = await createSchool(token, {
        ...form,
        subdomain: form.subdomain || undefined,
        template: form.template || undefined,
        monthly_fee: Number(form.monthly_fee),
      });
      setSaveState("idle");
      setForm(EMPTY_CREATE_FORM);
      onCreated(result);
    } catch (err) {
      setSaveState("error");
      setError(err instanceof ApiError ? err.message : "Couldn't create the college.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">New college</h3>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="school-name" className="block text-sm font-medium text-slate-700">
            College name
          </label>
          <input
            id="school-name"
            required
            value={form.name}
            onChange={(e) => setField("name", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        <div>
          <label htmlFor="school-code" className="block text-sm font-medium text-slate-700">
            Code
          </label>
          <input
            id="school-code"
            required
            placeholder="e.g. GREENWOOD"
            value={form.code}
            onChange={(e) => setField("code", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        <div>
          <label htmlFor="school-subdomain" className="block text-sm font-medium text-slate-700">
            Subdomain (optional)
          </label>
          <input
            id="school-subdomain"
            placeholder="defaults to lowercased code"
            value={form.subdomain}
            onChange={(e) => setField("subdomain", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        <div>
          <label htmlFor="school-template" className="block text-sm font-medium text-slate-700">
            Template
          </label>
          <select
            id="school-template"
            value={form.template}
            onChange={(e) => setField("template", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <option value="">Automatic</option>
            {THEMES.map((theme) => (
              <option key={theme.id} value={theme.id}>
                {theme.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="school-fee" className="block text-sm font-medium text-slate-700">
            Monthly fee (₹)
          </label>
          <input
            id="school-fee"
            type="number"
            min="0"
            value={form.monthly_fee}
            onChange={(e) => setField("monthly_fee", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        <div>
          <label htmlFor="school-billing" className="block text-sm font-medium text-slate-700">
            Billing status
          </label>
          <select
            id="school-billing"
            value={form.billing_status}
            onChange={(e) => setField("billing_status", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            {BILLING_STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
        <div>
          <label htmlFor="admin-name" className="block text-sm font-medium text-slate-700">
            Admin full name
          </label>
          <input
            id="admin-name"
            required
            value={form.admin_full_name}
            onChange={(e) => setField("admin_full_name", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        <div>
          <label htmlFor="admin-email" className="block text-sm font-medium text-slate-700">
            Admin email
          </label>
          <input
            id="admin-email"
            type="email"
            required
            value={form.admin_email}
            onChange={(e) => setField("admin_email", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
        <div>
          <label htmlFor="admin-password" className="block text-sm font-medium text-slate-700">
            Admin password
          </label>
          <input
            id="admin-password"
            type="text"
            required
            minLength={8}
            value={form.admin_password}
            onChange={(e) => setField("admin_password", e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          />
        </div>
      </div>

      <div className="border-t border-slate-100 pt-4">
        <p className="text-sm font-medium text-slate-700">Enabled modules</p>
        <div className="mt-2">
          <ModuleCheckboxes
            value={form.enabled_modules}
            onChange={(value) => setField("enabled_modules", value)}
            idPrefix="create"
          />
        </div>
      </div>

      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={saveState === "saving"}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saveState === "saving" ? "Creating…" : "Create college"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

const PAYMENT_GATEWAYS = [
  { id: "cashfree", name: "Cashfree" },
  { id: "razorpay", name: "Razorpay" },
  { id: "phonepe", name: "PhonePe" },
  { id: "demo", name: "Demo (test, no real money)" },
];

function EditSchoolPanel({ token, school, onClose, onSaved }) {
  const [draft, setDraft] = useState({
    template: school.template,
    subdomain: school.subdomain,
    monthly_fee: school.monthly_fee,
    billing_status: school.billing_status,
    status: school.status,
    enabled_modules: school.enabled_modules,
    pro_templates: school.pro_templates,
    payment_gateways: school.payment_gateways ?? [],
  });
  const [saveState, setSaveState] = useState("idle");
  const [error, setError] = useState(null);

  function setField(field, value) {
    setDraft((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    setSaveState("saving");
    setError(null);
    try {
      const updated = await updateSchool(token, school.id, { ...draft, monthly_fee: Number(draft.monthly_fee) });
      setSaveState("success");
      onSaved(updated);
    } catch (err) {
      setSaveState("error");
      setError(err instanceof ApiError ? err.message : "Couldn't save changes.");
    }
  }

  return (
    <tr>
      <td colSpan={7} className="bg-slate-50 px-4 py-4">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-slate-500">Subdomain</label>
              <input
                value={draft.subdomain}
                onChange={(e) => setField("subdomain", e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">Template</label>
              <select
                value={draft.template}
                onChange={(e) => setField("template", e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                {THEMES.map((theme) => (
                  <option key={theme.id} value={theme.id}>
                    {theme.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">Monthly fee (₹)</label>
              <input
                type="number"
                min="0"
                value={draft.monthly_fee}
                onChange={(e) => setField("monthly_fee", e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500">Billing status</label>
              <select
                value={draft.billing_status}
                onChange={(e) => setField("billing_status", e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                {BILLING_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500">Account status</label>
            <select
              value={draft.status}
              onChange={(e) => setField("status", e.target.value)}
              className="mt-1 w-40 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
            >
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </div>

          <label className="flex w-fit items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <input type="checkbox" checked={draft.pro_templates} onChange={(e) => setField("pro_templates", e.target.checked)} className="rounded border-amber-300 text-amber-600" />
            <span>
              <span className="font-semibold">Pro templates</span>: all 10 website templates (switch on once the college has paid)
            </span>
          </label>

          <fieldset>
            <legend className="text-xs font-medium text-slate-500">Online payment gateways the college can choose from</legend>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {PAYMENT_GATEWAYS.map((g) => (
                <label key={g.id} className="flex items-center gap-2 rounded-lg bg-white px-3 py-1.5 text-sm ring-1 ring-inset ring-slate-200">
                  <input
                    type="checkbox"
                    checked={draft.payment_gateways.includes(g.id)}
                    onChange={(e) =>
                      setField("payment_gateways", e.target.checked ? [...draft.payment_gateways, g.id] : draft.payment_gateways.filter((id) => id !== g.id))
                    }
                    className="rounded border-slate-300 text-emerald-600"
                  />
                  {g.name}
                </label>
              ))}
            </div>
            <p className="mt-1 text-xs text-slate-400">The college connects its own account for one of these; payments go straight to the college. None ticked = no online payments.</p>
          </fieldset>

          <div>
            <p className="text-xs font-medium text-slate-500">Enabled modules</p>
            <div className="mt-1.5">
              <ModuleCheckboxes
                value={draft.enabled_modules}
                onChange={(value) => setField("enabled_modules", value)}
                idPrefix={`edit-${school.id}`}
              />
            </div>
          </div>

          {error && <p className="text-sm text-rose-600">{error}</p>}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saveState === "saving"}
              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saveState === "saving" ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-200"
            >
              Close
            </button>
            {saveState === "success" && <span className="text-xs font-medium text-emerald-700">Saved.</span>}
          </div>
        </div>
      </td>
    </tr>
  );
}

function SuperAdminSchoolsPage() {
  const { token } = useAuth();
  const [status, setStatus] = useState("loading");
  const [schools, setSchools] = useState([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [createdNotice, setCreatedNotice] = useState(null);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const result = await fetchSchools(token);
      setSchools(result);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function handleCreated(result) {
    setShowCreateForm(false);
    setCreatedNotice(`Created ${result.school.name} — admin login: ${result.admin_email}`);
    setSchools((prev) => [...prev, result.school].sort((a, b) => a.name.localeCompare(b.name)));
  }

  function handleSaved(updated) {
    setSchools((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Colleges</h2>
          <p className="mt-1 text-sm text-slate-500">Create colleges, control module access, and manage billing.</p>
        </div>
        {!showCreateForm && (
          <button
            type="button"
            onClick={() => {
              setShowCreateForm(true);
              setCreatedNotice(null);
            }}
            className="w-fit rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
          >
            + New college
          </button>
        )}
      </div>

      {createdNotice && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{createdNotice}</p>
      )}

      {showCreateForm && (
        <CreateSchoolForm token={token} onCreated={handleCreated} onCancel={() => setShowCreateForm(false)} />
      )}

      {status === "loading" && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-6">
          <div className="h-4 w-1/3 animate-pulse rounded bg-slate-200" />
          <div className="h-4 w-1/4 animate-pulse rounded bg-slate-100" />
        </div>
      )}

      {status === "error" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
          <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load colleges.</p>
          <button
            type="button"
            onClick={load}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            Retry
          </button>
        </div>
      )}

      {status === "ready" && schools.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-sm font-semibold text-slate-600">No colleges yet.</p>
          <p className="mt-1 text-sm text-slate-400">Create the first one above.</p>
        </div>
      )}

      {status === "ready" && schools.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">College</th>
                <th className="px-4 py-3">Subdomain</th>
                <th className="px-4 py-3">Template</th>
                <th className="px-4 py-3">Modules</th>
                <th className="px-4 py-3">Fee</th>
                <th className="px-4 py-3">Billing</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {schools.map((school) => (
                <Fragment key={school.id}>
                  <tr>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-800">{school.name}</p>
                      <p className="text-xs text-slate-400">{school.code}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{school.subdomain}</td>
                    <td className="px-4 py-3 capitalize text-slate-600">
                      {school.template}
                      {school.pro_templates && <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-800">Pro</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{school.enabled_modules.length}</td>
                    <td className="px-4 py-3 text-slate-600">₹{school.monthly_fee}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${billingBadgeClass(school.billing_status)}`}
                      >
                        {school.billing_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setEditingId(editingId === school.id ? null : school.id)}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
                      >
                        {editingId === school.id ? "Cancel" : "Manage"}
                      </button>
                    </td>
                  </tr>
                  {editingId === school.id && (
                    <EditSchoolPanel
                      token={token}
                      school={school}
                      onClose={() => setEditingId(null)}
                      onSaved={(updated) => {
                        handleSaved(updated);
                      }}
                    />
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default SuperAdminSchoolsPage;

import { useState } from "react";

import { savePaymentSettings } from "../api/feesApi";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// What each gateway calls its keys, and where the college finds them.
const GATEWAYS = {
  cashfree: { name: "Cashfree", id: "App ID", secret: "Secret key", test: "Test (Cashfree sandbox)", where: "your Cashfree dashboard under Developers → API keys" },
  razorpay: { name: "Razorpay", id: "Key ID", secret: "Key secret", test: null, where: "your Razorpay dashboard under Account & Settings → API keys (test keys start with rzp_test_)" },
  demo: { name: "Demo gateway (test)", demo: true },
  phonepe: { name: "PhonePe", id: "Client ID", secret: "Client secret", test: "Test (PhonePe sandbox)", where: "your PhonePe Business dashboard under Developer settings" },
};

// The college's own payment gateway account: parents' online fee payments go straight to it.
function OnlinePaymentSettings({ token, settings, onSaved }) {
  const allowed = settings.allowed_providers ?? ["cashfree"];
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    provider: allowed.includes(settings.provider) ? settings.provider : allowed[0],
    key_id: settings.key_id,
    key_secret: "",
    client_version: settings.client_version ?? "",
    environment: settings.environment,
    enabled: settings.enabled,
  });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      const body = {
        provider: form.provider,
        key_id: form.key_id.trim(),
        client_version: form.client_version.trim(),
        environment: form.provider === "razorpay" ? "production" : form.environment,
        enabled: form.enabled,
      };
      if (form.key_secret.trim()) body.key_secret = form.key_secret.trim();
      onSaved(await savePaymentSettings(token, body));
      setForm((f) => ({ ...f, key_secret: "" }));
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
    setState("idle");
  }

  if (allowed.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
        <span className="font-semibold">Online payments: Off.</span> Parents pay at the office. To take payments online, ask ANV Soft Solutions to switch on a payment gateway for your college.
      </div>
    );
  }

  const current = GATEWAYS[settings.provider] ?? GATEWAYS.cashfree;
  const chosen = GATEWAYS[form.provider];
  const switching = form.provider !== settings.provider;
  const on = settings.enabled && allowed.includes(settings.provider);
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${on ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p>
          <span className="font-semibold">Online payments: {on ? `On (${current.name}${settings.environment === "sandbox" ? ", test mode" : ""})` : "Off"}.</span>{" "}
          {on ? `Parents can pay from their login; money goes to your college's ${current.name} account.` : "Parents pay at the office for now."}
        </p>
        {!editing && (
          <button type="button" onClick={() => setEditing(true)} className="rounded-lg px-3 py-1.5 font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-white">
            {settings.key_id ? "Payment gateway settings" : "Connect a payment gateway"}
          </button>
        )}
      </div>
      {editing && (
        <form onSubmit={handleSubmit} className="mt-3 space-y-3 border-t border-slate-200 pt-3 text-slate-800">
          {allowed.length > 1 && (
            <fieldset>
              <legend className="font-medium">Gateway</legend>
              <div className="mt-1 flex flex-wrap gap-2">
                {allowed.map((id) => (
                  <label
                    key={id}
                    className={`flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 ring-1 ring-inset ${form.provider === id ? "bg-white font-semibold ring-emerald-500" : "ring-slate-200 hover:bg-white"}`}
                  >
                    <input type="radio" name="gateway" value={id} checked={form.provider === id} onChange={() => setForm({ ...form, provider: id })} className="text-emerald-600" />
                    {GATEWAYS[id].name}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {chosen.demo && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
              For demos and testing only: parents see a pretend payment page and no money moves. No keys needed. Switch to a real gateway before taking real fees.
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {!chosen.demo && (
              <>
            <label className="block font-medium">
              {chosen.id}
              <input value={form.key_id} maxLength={100} onChange={(e) => setForm({ ...form, key_id: e.target.value })} className={INPUT} autoComplete="off" />
            </label>
            <label className="block font-medium">
              {chosen.secret}
              <input
                type="password"
                value={form.key_secret}
                maxLength={200}
                required={switching && !chosen.demo}
                onChange={(e) => setForm({ ...form, key_secret: e.target.value })}
                placeholder={settings.has_secret && !switching ? "Saved. Leave blank to keep it" : ""}
                className={INPUT}
                autoComplete="new-password"
              />
            </label>
              </>
            )}
            {form.provider === "phonepe" && (
              <label className="block font-medium">
                Client version
                <input value={form.client_version} maxLength={10} onChange={(e) => setForm({ ...form, client_version: e.target.value })} className={INPUT} autoComplete="off" />
              </label>
            )}
            {chosen.test && (
              <label className="block font-medium">
                Mode
                <select value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value })} className={INPUT}>
                  <option value="production">Live (real payments)</option>
                  <option value="sandbox">{chosen.test}</option>
                </select>
              </label>
            )}
            <label className="flex items-center gap-2 self-end pb-2 font-medium">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="rounded border-slate-300 text-emerald-600" />
              Let parents pay online
            </label>
          </div>
          {!chosen.demo && (
          <p className="text-xs text-slate-500">
            Find these in {chosen.where}. Also add this webhook URL there, so payments made when a parent closes the page still get recorded:{" "}
            <span className="break-all font-mono">
              {API_URL}/public/payments/{form.provider}/webhook
            </span>
          </p>
          )}
          {switching && settings.key_id && <p className="text-xs font-medium text-amber-700">Switching gateway: payments already started with {current.name} are finished by the office if they don&apos;t go through.</p>}
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 font-medium text-rose-700">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
              {state === "saving" ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setEditing(false)} className="rounded-lg px-4 py-2 font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-white">
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default OnlinePaymentSettings;

import { useCallback, useEffect, useState } from "react";

import { fetchPaymentSettings, savePaymentSettings } from "../api/feesApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// What each gateway calls its keys, and where the college finds them.
const GATEWAYS = {
  razorpay: {
    name: "Razorpay",
    blurb: "UPI, cards, netbanking and wallets.",
    id: "Key ID",
    secret: "Key secret",
    test: null,
    where: "Razorpay dashboard → Account & Settings → API keys. Test keys start with rzp_test_, live keys with rzp_live_.",
  },
  cashfree: {
    name: "Cashfree",
    blurb: "UPI, cards, netbanking and wallets.",
    id: "App ID",
    secret: "Secret key",
    test: "Test (Cashfree sandbox)",
    where: "Cashfree dashboard → Developers → API keys.",
  },
  phonepe: {
    name: "PhonePe",
    blurb: "PhonePe Payment Gateway: UPI, cards and netbanking.",
    id: "Client ID",
    secret: "Client secret",
    test: "Test (PhonePe sandbox)",
    where: "PhonePe Business dashboard → Developer settings (Client ID, Client version, Client secret).",
  },
  demo: { name: "Demo gateway", blurb: "For demos only. A pretend payment page; no money moves. No keys needed.", demo: true },
};
const ORDER = ["razorpay", "cashfree", "phonepe", "demo"];

function PaymentIntegrationPage() {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      const loaded = await fetchPaymentSettings(token);
      setSettings(loaded);
      setForm({
        provider: loaded.allowed_providers.includes(loaded.provider) ? loaded.provider : loaded.allowed_providers[0],
        key_id: loaded.key_id,
        key_secret: "",
        client_version: loaded.client_version ?? "",
        environment: loaded.environment,
        enabled: loaded.enabled,
      });
      setState("ready");
    } catch (err) {
      setState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function choose(provider) {
    setNotice(null);
    setError(null);
    const same = provider === settings.provider;
    setForm((f) => ({
      ...f,
      provider,
      key_id: same ? settings.key_id : "",
      key_secret: "",
      client_version: same ? settings.client_version ?? "" : "",
      environment: same ? settings.environment : "production",
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    setNotice(null);
    try {
      const body = {
        provider: form.provider,
        key_id: form.key_id.trim(),
        client_version: form.client_version.trim(),
        environment: GATEWAYS[form.provider].test ? form.environment : form.provider === "demo" ? "sandbox" : "production",
        enabled: form.enabled,
      };
      if (form.key_secret.trim()) body.key_secret = form.key_secret.trim();
      const saved = await savePaymentSettings(token, body);
      setSettings(saved);
      setForm((f) => ({ ...f, key_secret: "" }));
      setNotice(saved.enabled ? `Saved. Parents can now pay online with ${GATEWAYS[saved.provider].name}.` : "Saved. Online payment is off; parents pay at the office.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
    }
    setState("ready");
  }

  if (state === "loading") return <div className="h-64 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "forbidden") return <p className="text-sm font-semibold text-rose-700">Only the college admin can change payment settings.</p>;
  if (state === "error") {
    return (
      <p className="text-sm font-semibold text-rose-700">
        Couldn&apos;t load payment settings.{" "}
        <button type="button" onClick={load} className="underline">
          Retry
        </button>
      </p>
    );
  }

  const allowed = ORDER.filter((id) => settings.allowed_providers.includes(id));
  const live = settings.enabled && allowed.includes(settings.provider);
  const chosen = GATEWAYS[form.provider];
  const switching = form.provider !== settings.provider;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Payment integration</h2>
        <p className="mt-1 text-sm text-slate-500">
          Connect your college&apos;s own payment gateway account. Parents&apos; online fee payments go straight into your account; ANV Soft Solutions never holds the money.
        </p>
      </div>

      <div className={`rounded-xl border px-4 py-3 text-sm ${live ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
        <span className="font-semibold">Status: {live ? `Connected to ${GATEWAYS[settings.provider].name}${settings.environment === "sandbox" ? " (test mode)" : ""}` : "Online payment off"}.</span>{" "}
        {live ? "Parents see “Pay online” on every fee." : "Parents can still tell you about offline payments (cash, UPI, bank)."}
      </div>

      {allowed.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
          No payment gateway is switched on for your college yet. Ask ANV Soft Solutions to switch on Razorpay, Cashfree or PhonePe.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          <fieldset>
            <legend className="text-sm font-semibold text-slate-800">1. Choose your gateway</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              {allowed.map((id) => {
                const selected = form.provider === id;
                return (
                  <label
                    key={id}
                    className={`relative flex cursor-pointer flex-col gap-1 rounded-xl border-2 bg-white p-4 transition ${selected ? "border-emerald-500 shadow-sm" : "border-slate-200 hover:border-slate-300"}`}
                  >
                    <span className="flex items-center gap-2">
                      <input type="radio" name="gateway" value={id} checked={selected} onChange={() => choose(id)} className="h-4 w-4 text-emerald-600" />
                      <span className="font-semibold text-slate-900">{GATEWAYS[id].name}</span>
                    </span>
                    <span className="text-xs text-slate-500">{GATEWAYS[id].blurb}</span>
                    {live && settings.provider === id && <span className="w-fit rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">Connected</span>}
                  </label>
                );
              })}
            </div>
          </fieldset>

          <fieldset className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
            <legend className="px-1 text-sm font-semibold text-slate-800">2. {chosen.demo ? "Demo gateway" : `Your ${chosen.name} keys`}</legend>
            {chosen.demo ? (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                Parents see a pretend payment page and no money moves. Use it only to show how online payment works, then switch to a real gateway before taking real fees.
              </p>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm font-medium text-slate-700">
                    {chosen.id}
                    <input value={form.key_id} maxLength={100} required={form.enabled} onChange={(e) => setForm({ ...form, key_id: e.target.value })} className={INPUT} autoComplete="off" />
                  </label>
                  <label className="block text-sm font-medium text-slate-700">
                    {chosen.secret}
                    <input
                      type="password"
                      value={form.key_secret}
                      maxLength={200}
                      required={form.enabled && (switching || !settings.has_secret)}
                      onChange={(e) => setForm({ ...form, key_secret: e.target.value })}
                      placeholder={settings.has_secret && !switching ? "Saved. Leave blank to keep it" : ""}
                      className={INPUT}
                      autoComplete="new-password"
                    />
                  </label>
                  {form.provider === "phonepe" && (
                    <label className="block text-sm font-medium text-slate-700">
                      Client version
                      <input value={form.client_version} maxLength={10} required={form.enabled} onChange={(e) => setForm({ ...form, client_version: e.target.value })} className={INPUT} autoComplete="off" />
                    </label>
                  )}
                  {chosen.test && (
                    <label className="block text-sm font-medium text-slate-700">
                      Mode
                      <select value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value })} className={INPUT}>
                        <option value="production">Live (real payments)</option>
                        <option value="sandbox">{chosen.test}</option>
                      </select>
                    </label>
                  )}
                </div>
                <p className="text-xs text-slate-500">Where to find them: {chosen.where}</p>
                <p className="text-xs text-slate-500">
                  Also add this webhook URL in the {chosen.name} dashboard, so payments made when a parent closes the page still get recorded:{" "}
                  <span className="break-all font-mono text-slate-700">
                    {API_URL}/public/payments/{form.provider}/webhook
                  </span>
                </p>
              </>
            )}
          </fieldset>

          <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="h-4 w-4 rounded border-slate-300 text-emerald-600" />
            3. Let parents pay online
          </label>

          {switching && settings.key_id && (
            <p className="text-xs font-medium text-amber-700">
              Switching from {GATEWAYS[settings.provider]?.name}: a payment already started there that doesn&apos;t finish is settled at the office.
            </p>
          )}
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
          {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
          <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {state === "saving" ? "Saving…" : "Save"}
          </button>
        </form>
      )}
    </div>
  );
}

export default PaymentIntegrationPage;

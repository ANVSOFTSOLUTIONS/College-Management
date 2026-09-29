import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { confirmFeePayment, fetchAdmissionForm, startFeePayment, submitApplication, uploadApplicationDocument } from "../../api/admissionsApi";
import { formatRupees } from "../../api/feesApi";
import AdmissionForm from "../../components/AdmissionForm";
import DeveloperCredit from "../../components/DeveloperCredit";
import { ApiError } from "../../lib/apiClient";
import { openCheckout } from "../../lib/payments";
import { assetUrl } from "../../siteTemplates/SiteRenderer";

// The application fee after applying: pay online, or at the office when the college takes no online payments.
function FeeBox({ code, result, online }) {
  const [state, setState] = useState("due"); // due | paying | paid
  const [error, setError] = useState(null);

  async function pay() {
    setState("paying");
    setError(null);
    try {
      const order = await startFeePayment(code, result.id, result.upload_token);
      const failed = await openCheckout(order);
      if (failed) throw new Error(failed);
      await confirmFeePayment(code, result.id, result.upload_token);
      setState("paid");
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "The payment didn't go through.");
      setState("due");
    }
  }

  if (state === "paid") {
    return <p className="rounded-lg bg-emerald-50 px-4 py-3 font-semibold text-emerald-800">✅ Application fee of {formatRupees(result.fee_amount)} paid. Thank you.</p>;
  }
  return (
    <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-4 text-amber-950">
      <p className="font-semibold">Application fee: {formatRupees(result.fee_amount)}</p>
      {online ? (
        <>
          <button type="button" onClick={pay} disabled={state === "paying"} className="rounded-lg bg-emerald-600 px-5 py-2.5 font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {state === "paying" ? "Opening payment…" : `Pay ${formatRupees(result.fee_amount)} now`}
          </button>
          <p className="text-xs">UPI, card or net banking, paid straight to the college. You can also pay at the college office.</p>
        </>
      ) : (
        <p className="text-sm">Please pay it at the college office with your application number.</p>
      )}
      {error && <p className="text-sm font-medium text-rose-700">{error}</p>}
    </div>
  );
}

// Public admission form: /apply/:code (no login).
function ApplyPage() {
  const { code } = useParams();
  const [form, setForm] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchAdmissionForm(code)
      .then((data) => {
        setForm(data);
        setState("ready");
        document.title = `Admissions · ${data.school_name}`;
      })
      .catch((err) => setState(err instanceof ApiError && err.status === 404 ? "not-found" : "error"));
  }, [code]);

  async function handleSubmit(body, documents) {
    setState("sending");
    setError(null);
    try {
      const submitted = await submitApplication(code, body);
      // Documents go up one by one with the short-lived token; a failed one is reported, not fatal.
      const failed = [];
      for (const doc of documents) {
        try {
          await uploadApplicationDocument(code, submitted.id, submitted.upload_token, doc.doc_type, doc.file);
        } catch {
          failed.push(doc.file.name);
        }
      }
      setResult({ ...submitted, failed, name: body.student_name });
      setState("done");
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send the application. Check your connection and try again.");
      setState("ready");
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl space-y-6">
        {form && (
          <header className="flex items-center gap-3">
            {form.logo_url && <img src={assetUrl(form.logo_url)} alt="" className="h-14 w-14 rounded-full border bg-white object-contain p-1" />}
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-emerald-700">Admissions</p>
              <h1 className="text-2xl font-bold text-slate-900">{form.school_name}</h1>
            </div>
          </header>
        )}

        {state === "loading" && <div className="h-96 animate-pulse rounded-2xl border border-slate-200 bg-white" />}
        {state === "not-found" && <p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-600">This college isn&apos;t taking applications online.</p>}
        {state === "error" && <p className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center text-rose-800">Couldn&apos;t load the form. Please try again.</p>}

        {form && !form.open && state !== "done" && (
          <p className="rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center text-amber-900">Admissions are closed right now. Please contact the college office.</p>
        )}

        {form?.open && (state === "ready" || state === "sending") && (
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8">
            <p className="mb-6 text-sm text-slate-600">
              Fill in your child&apos;s details. The college will review your application and call you.
              {form.admission_fee > 0 && ` There is an application fee of ${formatRupees(form.admission_fee)}${form.online_payment ? ", which you can pay online after sending the form" : ", payable at the college office"}.`}
            </p>
            <AdmissionForm classes={form.classes} submitLabel="Send application" busy={state === "sending"} error={error} onSubmit={handleSubmit} />
          </section>
        )}

        {state === "done" && (
          <section className="space-y-4 rounded-2xl border border-emerald-200 bg-white p-8 text-center shadow-sm">
            <p className="text-4xl">✅</p>
            <h2 className="text-xl font-bold text-slate-900">Application received</h2>
            <p className="text-slate-600">
              {result.name}&apos;s application number is
            </p>
            <p className="text-2xl font-bold tracking-wide text-emerald-700">{result.application_no}</p>
            <p className="text-sm text-slate-500">Take a screenshot or note this number. The college will contact you on the mobile number you gave.</p>
            {result.fee_amount > 0 && <FeeBox code={code} result={result} online={form.online_payment} />}
            {result.failed.length > 0 && (
              <p className="rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-900">
                These files didn&apos;t upload: {result.failed.join(", ")}. Please bring them to the college office.
              </p>
            )}
          </section>
        )}
        <DeveloperCredit />
      </div>
    </div>
  );
}

export default ApplyPage;

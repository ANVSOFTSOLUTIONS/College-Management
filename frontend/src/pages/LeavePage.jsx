import { useCallback, useEffect, useState } from "react";

import { LEAVE_TYPES, applyLeave, cancelLeave, fetchLeaveInbox, fetchMyLeaves, reviewLeave } from "../api/staffApi";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const STATUS_STYLES = {
  pending: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700",
  rejected: "bg-rose-50 text-rose-700",
  cancelled: "bg-slate-100 text-slate-500",
};

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

function dateRange(leave) {
  const fmt = (d) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return leave.from_date === leave.to_date ? fmt(leave.from_date) : `${fmt(leave.from_date)} – ${fmt(leave.to_date)}`;
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function ApplyForm({ token, reviewerText, onApplied }) {
  const [form, setForm] = useState({ leave_type: "sick", from_date: todayIso(), to_date: todayIso(), reason: "" });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setState("saving");
    setError(null);
    try {
      await applyLeave(token, form);
      setForm({ leave_type: "sick", from_date: todayIso(), to_date: todayIso(), reason: "" });
      setState("idle");
      onApplied();
    } catch (err) {
      setState("error");
      setError(errorMessage(err, "Couldn't send the request."));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">Apply for leave</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="leave-type" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select id="leave-type" value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })} className={INPUT}>
            {LEAVE_TYPES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="leave-from" className="block text-sm font-medium text-slate-700">
            From
          </label>
          <input
            id="leave-from"
            type="date"
            required
            value={form.from_date}
            onChange={(e) => setForm({ ...form, from_date: e.target.value, to_date: e.target.value > form.to_date ? e.target.value : form.to_date })}
            className={INPUT}
          />
        </div>
        <div>
          <label htmlFor="leave-to" className="block text-sm font-medium text-slate-700">
            To
          </label>
          <input id="leave-to" type="date" required min={form.from_date} value={form.to_date} onChange={(e) => setForm({ ...form, to_date: e.target.value })} className={INPUT} />
        </div>
      </div>
      <div>
        <label htmlFor="leave-reason" className="block text-sm font-medium text-slate-700">
          Reason
        </label>
        <textarea id="leave-reason" required minLength={3} maxLength={500} rows={2} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className={INPUT} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Sending…" : "Send request"}
        </button>
        <span className="text-xs text-slate-400">{reviewerText}</span>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function LeaveItem({ leave, children, showApplicant }) {
  return (
    <li className="space-y-2 px-4 py-3 text-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-semibold text-slate-800">
            {showApplicant ? leave.applicant_name : leave.leave_type_label}
            <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[leave.status]}`}>{leave.status}</span>
          </p>
          <p className="text-xs text-slate-500">
            {showApplicant &&
              `${leave.applicant_kind === "student" ? `Student${leave.class_name ? ` · ${leave.class_name}` : ""}${leave.applied_by_parent ? " · from parent" : ""}` : "Teacher"} · ${leave.leave_type_label} · `}
            {dateRange(leave)} ({leave.days} day{leave.days > 1 ? "s" : ""})
          </p>
          <p className="mt-1 text-slate-700">{leave.reason}</p>
          {leave.reviewer_name && (
            <p className="mt-1 text-xs text-slate-500">
              {leave.status === "approved" ? "Approved" : "Rejected"} by {leave.reviewer_name}
              {leave.review_note && `: ${leave.review_note}`}
            </p>
          )}
        </div>
        {children}
      </div>
    </li>
  );
}

function ReviewButtons({ token, leave, onDone }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);

  async function decide(status) {
    setError(null);
    try {
      await reviewLeave(token, leave.id, status, note);
      onDone();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the decision."));
    }
  }

  if (rejecting) {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          decide("rejected");
        }}
        className="flex flex-col gap-2 sm:w-72"
      >
        <input autoFocus required aria-label="Reason for rejecting" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
        <div className="flex gap-2">
          <button type="submit" className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white">
            Reject
          </button>
          <button type="button" onClick={() => setRejecting(false)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100">
            Cancel
          </button>
        </div>
        {error && <p className="text-xs text-rose-600">{error}</p>}
      </form>
    );
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button type="button" onClick={() => decide("approved")} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700">
          Approve
        </button>
        <button type="button" onClick={() => setRejecting(true)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50">
          Reject
        </button>
      </div>
      {error && <p className="text-xs text-rose-600">{error}</p>}
    </div>
  );
}

function LeavePage() {
  const { token, user } = useAuth();
  const canApply = user.role === "teacher";
  const canReview = user.role === "admin" || user.role === "teacher";
  const [mine, setMine] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [state, setState] = useState("loading");
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      const [mineList, inboxList] = await Promise.all([canApply ? fetchMyLeaves(token) : [], canReview ? fetchLeaveInbox(token) : []]);
      setMine(mineList);
      setInbox(inboxList);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, canApply, canReview]);

  useEffect(() => {
    load();
  }, [load]);

  const pending = inbox.filter((l) => l.can_review);
  const handled = inbox.filter((l) => !l.can_review);
  const reviewerText = "Goes to the college admin.";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Leave</h2>
        <p className="mt-1 text-sm text-slate-500">
          {user.role === "admin"
            ? "Approve or reject leave requests from staff, and from parents for their children."
            : "Apply for your own leave, and handle leave requests parents send for students in your class."}
        </p>
      </div>
      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
      {state === "loading" && <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && (
        <p className="text-sm font-semibold text-rose-700">
          Couldn&apos;t load leave requests.{" "}
          <button type="button" onClick={load} className="underline">
            Retry
          </button>
        </p>
      )}
      {state === "ready" && (
        <>
          {canReview && (
            <section className="space-y-3">
              <h3 className="text-lg font-semibold text-slate-900">
                Waiting for you {pending.length > 0 && <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">{pending.length}</span>}
              </h3>
              {pending.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No requests waiting.</p>
              ) : (
                <ul className="divide-y divide-slate-100 rounded-xl border border-amber-200 bg-white">
                  {pending.map((leave) => (
                    <LeaveItem key={leave.id} leave={leave} showApplicant>
                      <ReviewButtons
                        token={token}
                        leave={leave}
                        onDone={() => {
                          setNotice(`Leave for ${leave.applicant_name} handled; they've been notified.`);
                          load();
                        }}
                      />
                    </LeaveItem>
                  ))}
                </ul>
              )}
            </section>
          )}

          {canApply && (
            <>
              <ApplyForm
                token={token}
                reviewerText={reviewerText}
                onApplied={() => {
                  setNotice("Request sent.");
                  load();
                }}
              />
              <section className="space-y-3">
                <h3 className="text-lg font-semibold text-slate-900">My requests</h3>
                {mine.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No leave requests yet.</p>
                ) : (
                  <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                    {mine.map((leave) => (
                      <LeaveItem key={leave.id} leave={leave}>
                        {leave.can_cancel && (
                          <button
                            type="button"
                            onClick={() => window.confirm("Cancel this request?") && cancelLeave(token, leave.id).then(load)}
                            className="self-start rounded-lg px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
                          >
                            Cancel
                          </button>
                        )}
                      </LeaveItem>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}

          {canReview && handled.length > 0 && (
            <section className="space-y-3">
              <h3 className="text-lg font-semibold text-slate-900">Earlier requests</h3>
              <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                {handled.map((leave) => (
                  <LeaveItem key={leave.id} leave={leave} showApplicant />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default LeavePage;

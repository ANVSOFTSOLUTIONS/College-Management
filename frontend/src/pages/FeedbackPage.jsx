import { Fragment, useState } from "react";

import { DANGER, errorMessage, INPUT, LoadState, Notice, PageHeader, PRIMARY, SECONDARY, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

function scoreTone(value) {
  if (value >= 4) return "text-emerald-700";
  if (value >= 3) return "text-amber-600";
  return "text-rose-700";
}

function Report({ token, round }) {
  const [report, reload, state] = useLoad(() => apiRequest(`/feedback/rounds/${round.id}/report`, { token }), [token, round.id, round.responses]);
  const [open, setOpen] = useState(null);
  if (state !== "ready") return <LoadState state={state} onRetry={reload} what="the report" />;
  if (!report.faculty.length) return <p className="text-sm text-slate-500">No responses yet.</p>;
  const sorted = [...report.faculty].sort((a, b) => b.overall - a.overall);
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">Faculty</th>
            <th className="px-3 py-2">Subject · Batch</th>
            {report.questions.map((q, i) => (
              <th key={q} title={q} className="px-2 py-2 text-center">
                Q{i + 1}
              </th>
            ))}
            <th className="px-3 py-2 text-center">Overall</th>
            <th className="px-3 py-2 text-center">Responses</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((f) => {
            const key = `${f.teacher_id}|${f.subject_name}|${f.class_name}|${f.section}`;
            return (
              <Fragment key={key}>
                <tr>
                  <td className="px-3 py-2">
                    <p className="font-medium text-slate-900">{f.teacher_name}</p>
                    <p className="text-xs text-slate-500">{f.department}</p>
                  </td>
                  <td className="px-3 py-2 text-slate-700">
                    {f.subject_name} · {f.class_name}-{f.section}
                  </td>
                  {f.averages.map((a, i) => (
                    <td key={i} className={`px-2 py-2 text-center font-semibold ${scoreTone(a)}`}>
                      {a.toFixed(1)}
                    </td>
                  ))}
                  <td className={`px-3 py-2 text-center text-base font-bold ${scoreTone(f.overall)}`}>{f.overall.toFixed(2)}</td>
                  <td className="px-3 py-2 text-center text-slate-600">
                    {f.responses}/{f.students}
                    {f.comments.length > 0 && (
                      <button type="button" onClick={() => setOpen(open === key ? null : key)} className="ml-2 text-xs font-semibold text-emerald-700 hover:underline">
                        {f.comments.length} comments
                      </button>
                    )}
                  </td>
                </tr>
                {open === key && (
                  <tr>
                    <td colSpan={report.questions.length + 4} className="bg-slate-50 px-6 py-3">
                      <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700">
                        {f.comments.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <ol className="space-y-0.5 border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
        {report.questions.map((q, i) => (
          <li key={q}>
            Q{i + 1}. {q}
          </li>
        ))}
      </ol>
    </div>
  );
}

function FeedbackPage() {
  const { token } = useAuth();
  const [rounds, reload, state] = useLoad(() => apiRequest("/feedback/rounds", { token }), [token]);
  const [title, setTitle] = useState("");
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  async function act(path, options) {
    setError(null);
    try {
      await apiRequest(path, { token, ...options });
      reload();
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
  }

  async function create(e) {
    e.preventDefault();
    await act("/feedback/rounds", { method: "POST", body: { title } });
    setTitle("");
  }

  const current = rounds?.find((r) => r.id === selected) ?? rounds?.[0];
  return (
    <div className="space-y-6">
      <PageHeader
        title="Faculty feedback"
        subtitle="Students rate each subject's faculty anonymously in the app. Faculty see their own scores after you close the round; HODs see their department."
      />
      <form onSubmit={create} className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-end">
        <label className="flex-1 text-sm font-medium text-slate-700">
          New feedback round
          <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Odd semester 2026" className={INPUT} />
        </label>
        <button type="submit" className={PRIMARY}>
          Open round
        </button>
      </form>
      <Notice error={error} />
      {state !== "ready" ? (
        <LoadState state={state} onRetry={reload} what="feedback rounds" />
      ) : rounds.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No feedback rounds yet.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {rounds.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelected(r.id)}
                className={`rounded-lg px-3 py-2 text-sm font-semibold ring-1 ring-inset ${r.id === current.id ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-700 ring-slate-300"}`}
              >
                {r.title} · {r.responses} {r.is_open ? "· open" : ""}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => act(`/feedback/rounds/${current.id}/open`, { method: "PUT", body: { is_open: !current.is_open } })} className={SECONDARY}>
              {current.is_open ? "Close round (faculty can then see scores)" : "Reopen round"}
            </button>
            <button type="button" onClick={() => window.confirm(`Delete ${current.title} and all its responses?`) && act(`/feedback/rounds/${current.id}`, { method: "DELETE" })} className={DANGER}>
              Delete
            </button>
          </div>
          <Report token={token} round={current} />
        </>
      )}
    </div>
  );
}

export default FeedbackPage;

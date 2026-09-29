import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../context/AuthContext";
import { ApiError, apiRequest } from "../lib/apiClient";

function PromotionPage() {
  const { token } = useAuth();
  const [state, setState] = useState("loading");
  const [plan, setPlan] = useState(null);
  const [toYear, setToYear] = useState("");
  const [moves, setMoves] = useState({});
  const [openClass, setOpenClass] = useState(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(
    async (fromYear) => {
      setState("loading");
      try {
        const data = await apiRequest("/promotion/plan", { token, params: { from_year: fromYear } });
        setPlan(data);
        setToYear(data.suggested_to_year ?? "");
        setMoves(
          Object.fromEntries(
            data.classes.map((c) => [
              c.class_id,
              { action: c.suggested_action, target_name: c.suggested_target_name ?? "", target_section: c.section, keep_back: [] },
            ]),
          ),
        );
        setState("ready");
      } catch {
        setState("error");
      }
    },
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  const classNames = useMemo(() => [...new Set((plan?.classes ?? []).map((c) => c.name))], [plan]);
  const totals = useMemo(() => {
    const t = { promote: 0, keep: 0, graduate: 0 };
    (plan?.classes ?? []).forEach((c) => {
      const m = moves[c.class_id];
      if (!m) return;
      t.keep += m.keep_back.length;
      t[m.action === "graduate" ? "graduate" : "promote"] += c.students.length - m.keep_back.length;
    });
    return t;
  }, [plan, moves]);

  function update(classId, change) {
    setMoves((prev) => ({ ...prev, [classId]: { ...prev[classId], ...change } }));
  }

  function toggleKeep(classId, studentId) {
    const keep = moves[classId].keep_back;
    update(classId, { keep_back: keep.includes(studentId) ? keep.filter((id) => id !== studentId) : [...keep, studentId] });
  }

  async function handleRun() {
    const missing = plan.classes.find((c) => moves[c.class_id].action === "promote" && !moves[c.class_id].target_name.trim());
    if (missing) {
      setError(`Choose where ${missing.name} - ${missing.section} goes.`);
      return;
    }
    if (!window.confirm(`Promote ${plan.from_year} → ${toYear}? ${totals.promote} promoted, ${totals.keep} kept back, ${totals.graduate} passing out. This can't be undone.`)) return;
    setRunning(true);
    setError(null);
    try {
      const body = {
        from_year: plan.from_year,
        to_year: toYear.trim(),
        classes: plan.classes.map((c) => ({ class_id: c.class_id, ...moves[c.class_id], target_name: moves[c.class_id].target_name.trim() || null })),
      };
      setResult(await apiRequest("/promotion", { method: "POST", token, body }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Promotion failed. Nothing was changed.");
    } finally {
      setRunning(false);
    }
  }

  if (state === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load classes.</p>;

  if (result) {
    return (
      <div className="mx-auto max-w-lg space-y-4 rounded-2xl border border-emerald-200 bg-white p-8 text-center">
        <p className="text-4xl">🎉</p>
        <h2 className="text-2xl font-bold text-slate-900">Welcome to {toYear}!</h2>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-xl bg-emerald-50 p-3">
            <p className="text-2xl font-bold text-emerald-700">{result.promoted}</p>promoted
          </div>
          <div className="rounded-xl bg-amber-50 p-3">
            <p className="text-2xl font-bold text-amber-700">{result.kept_back}</p>kept back
          </div>
          <div className="rounded-xl bg-sky-50 p-3">
            <p className="text-2xl font-bold text-sky-700">{result.graduated}</p>passed out
          </div>
        </div>
        <p className="text-sm text-slate-500">
          {result.classes_created} new class(es) were created with last year&apos;s class and subject teachers. Check them under Classes &amp; Subjects, then set this year&apos;s fees and exams.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Promote to next year</h2>
        <p className="mt-1 text-sm text-slate-500">
          At the end of the academic year, move every class up at once. Last year&apos;s classes, attendance, fees and report cards are kept.
        </p>
      </div>

      {plan.classes.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No classes to promote.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4">
            <label className="text-sm font-medium text-slate-700">
              From year
              <select value={plan.from_year} onChange={(e) => load(e.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm">
                {plan.years.map((y) => (
                  <option key={y}>{y}</option>
                ))}
              </select>
            </label>
            <span className="pb-2 text-xl text-slate-400">→</span>
            <label className="text-sm font-medium text-slate-700">
              New academic year
              <input value={toYear} onChange={(e) => setToYear(e.target.value)} className="mt-1 block w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            </label>
            <p className="pb-2 text-sm text-slate-500">
              <span className="font-semibold text-emerald-700">{totals.promote}</span> promoted · <span className="font-semibold text-amber-700">{totals.keep}</span> kept back ·{" "}
              <span className="font-semibold text-sky-700">{totals.graduate}</span> passing out
            </p>
          </div>

          {plan.already_promoted_to ? (
            <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {plan.from_year} was already promoted to {plan.already_promoted_to}.
            </p>
          ) : (
            <>
              <datalist id="class-names">
                {classNames.map((n) => (
                  <option key={n} value={n} />
                ))}
              </datalist>
              <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                {plan.classes.map((c) => {
                  const m = moves[c.class_id];
                  return (
                    <li key={c.class_id} className="space-y-3 px-4 py-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-48">
                          <p className="font-semibold text-slate-900">
                            {c.name} - {c.section}
                          </p>
                          <p className="text-xs text-slate-500">
                            {c.students.length} students · {c.class_teacher_name}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <select aria-label={`Action for ${c.name} ${c.section}`} value={m.action} onChange={(e) => update(c.class_id, { action: e.target.value })} className="rounded-lg border border-slate-300 px-3 py-2">
                            <option value="promote">Promote to</option>
                            <option value="graduate">Pass out (final class)</option>
                          </select>
                          {m.action === "promote" && (
                            <>
                              <input
                                aria-label="Next class"
                                list="class-names"
                                placeholder="Class"
                                value={m.target_name}
                                onChange={(e) => update(c.class_id, { target_name: e.target.value })}
                                className="w-32 rounded-lg border border-slate-300 px-3 py-2"
                              />
                              <input aria-label="Section" value={m.target_section} onChange={(e) => update(c.class_id, { target_section: e.target.value })} className="w-16 rounded-lg border border-slate-300 px-3 py-2" />
                            </>
                          )}
                          <button
                            type="button"
                            onClick={() => setOpenClass(openClass === c.class_id ? null : c.class_id)}
                            className="rounded-lg px-3 py-2 font-semibold text-amber-700 ring-1 ring-inset ring-amber-200 hover:bg-amber-50"
                          >
                            Keep back{m.keep_back.length ? ` (${m.keep_back.length})` : ""}
                          </button>
                        </div>
                      </div>
                      {openClass === c.class_id && (
                        <div className="rounded-lg bg-amber-50/60 p-3">
                          <p className="mb-2 text-xs text-amber-900">Tick students who stay in {c.name} next year.</p>
                          <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
                            {c.students.map((s) => (
                              <label key={s.id} className="flex items-center gap-2 text-sm">
                                <input type="checkbox" checked={m.keep_back.includes(s.id)} onChange={() => toggleKeep(c.class_id, s.id)} className="rounded border-slate-300 text-amber-600" />
                                {s.full_name} <span className="text-xs text-slate-400">{s.admission_number}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
              {error && <p className="rounded-lg bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">{error}</p>}
              <button type="button" disabled={running || !toYear.trim()} onClick={handleRun} className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
                {running ? "Promoting…" : `Promote ${plan.from_year} → ${toYear}`}
              </button>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default PromotionPage;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function score(paper) {
  if (paper.is_absent) return "Absent";
  if (paper.marks === null) return "—";
  return `${paper.marks} / ${paper.max_marks}`;
}

function outcome(result) {
  if (result.passed === null) return "Result pending";
  return result.passed ? "Passed" : "Needs improvement";
}

// On-screen report card (student and parent portals).
export function ReportCardView({ card, onPrint }) {
  const { result } = card;
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-semibold text-slate-900">{card.exam_name}</p>
          <p className="text-xs text-slate-500">
            {[card.term_label, card.academic_year].filter(Boolean).join(" · ")} · {card.class_name} - {card.section}
            {card.semester ? ` · Sem ${card.semester}` : ""}
          </p>
        </div>
        {onPrint && (
          <button type="button" onClick={onPrint} className="self-start rounded-lg px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
            Print report card
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-1 pr-4">Subject</th>
              <th className="py-1 pr-4">Credits</th>
              <th className="py-1 pr-4">Marks</th>
              <th className="py-1 pr-4">Grade</th>
              <th className="py-1">Points</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.papers.map((paper) => (
              <tr key={paper.subject_name}>
                <td className="py-1.5 pr-4 text-slate-800">{paper.subject_name}</td>
                <td className="py-1.5 pr-4 text-slate-600">{paper.credits}</td>
                <td className={`py-1.5 pr-4 ${paper.passed === false ? "font-semibold text-rose-700" : "text-slate-700"}`}>{score(paper)}</td>
                <td className="py-1.5 pr-4 font-semibold text-slate-700">{paper.grade ?? "—"}</td>
                <td className="py-1.5 text-slate-600">{paper.grade_point ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-slate-100 pt-3 text-sm">
        <span>
          Total <span className="font-semibold">{result.total} / {result.max_total}</span>
        </span>
        {result.percentage !== null && (
          <span>
            <span className="font-semibold">{result.percentage}%</span>
          </span>
        )}
        {result.sgpa !== null && result.sgpa !== undefined && (
          <span>
            SGPA <span className="font-semibold">{result.sgpa}</span>
          </span>
        )}
        {card.cgpa !== null && card.cgpa !== undefined && (
          <span>
            CGPA <span className="font-semibold">{card.cgpa}</span>
          </span>
        )}
        <span>
          Credits <span className="font-semibold">{result.credits_earned} / {result.credits_total}</span>
        </span>
        {result.rank && (
          <span>
            Rank <span className="font-semibold">{result.rank}</span> of {card.class_size}
          </span>
        )}
        <span className={result.passed === false ? "font-semibold text-rose-700" : result.passed ? "font-semibold text-emerald-700" : "text-slate-500"}>{outcome(result)}</span>
      </div>
    </div>
  );
}

function reportCardHtml(card) {
  const { result } = card;
  const rows = result.papers
    .map(
      (p) =>
        `<tr><td>${escapeHtml(p.subject_name)}</td><td>${p.credits}</td><td>${p.max_marks}</td><td>${escapeHtml(p.is_absent ? "AB" : p.marks ?? "—")}</td><td>${escapeHtml(p.grade ?? "—")}</td><td>${p.grade_point ?? "—"}</td></tr>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Report card - ${escapeHtml(result.full_name)}</title>
<style>
  body { font-family: system-ui, sans-serif; color: #0f172a; margin: 32px; }
  .box { max-width: 640px; margin: auto; border: 1px solid #cbd5e1; border-radius: 12px; padding: 28px; }
  h1 { font-size: 22px; margin: 0; text-align: center; } h2 { font-size: 14px; letter-spacing: .1em; text-transform: uppercase; color: #047857; text-align: center; margin: 6px 0 20px; }
  .meta { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; font-size: 14px; margin-bottom: 16px; } .meta span { color: #64748b; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; } th, td { border: 1px solid #e2e8f0; padding: 8px; text-align: left; } th { background: #f8fafc; }
  .summary { margin-top: 16px; font-size: 15px; } .sign { margin-top: 48px; display: flex; justify-content: space-between; font-size: 13px; color: #64748b; }
  @media print { body { margin: 0; } .box { border: 0; } }
</style></head><body><div class="box">
  <h1>${escapeHtml(card.school_name)}</h1>
  <h2>${card.exam_type === "internal" ? "Marks memo" : "Grade sheet"} · ${escapeHtml(card.exam_name)}</h2>
  <div class="meta">
    <div><span>Student:</span> ${escapeHtml(result.full_name)}</div><div><span>Roll no.:</span> ${escapeHtml(result.admission_number)}</div>
    <div><span>Batch:</span> ${escapeHtml(card.class_name)} - ${escapeHtml(card.section)}</div><div><span>Year:</span> ${escapeHtml([card.term_label, card.academic_year].filter(Boolean).join(" · "))}</div>
    ${card.department_name ? `<div><span>Department:</span> ${escapeHtml(card.department_name)}</div>` : ""}${card.semester ? `<div><span>Semester:</span> ${card.semester}${card.program ? ` (${escapeHtml(card.program)})` : ""}</div>` : ""}
  </div>
  <table><thead><tr><th>Subject</th><th>Credits</th><th>Max</th><th>Marks</th><th>Grade</th><th>Points</th></tr></thead><tbody>${rows}</tbody></table>
  <p class="summary"><b>Total:</b> ${result.total} / ${result.max_total}${result.percentage !== null ? ` &nbsp; <b>Percentage:</b> ${result.percentage}%` : ""}${result.sgpa !== null && result.sgpa !== undefined ? ` &nbsp; <b>SGPA:</b> ${result.sgpa}` : ""}${card.cgpa !== null && card.cgpa !== undefined ? ` &nbsp; <b>CGPA:</b> ${card.cgpa}` : ""} &nbsp; <b>Credits earned:</b> ${result.credits_earned} / ${result.credits_total}${result.rank ? ` &nbsp; <b>Rank:</b> ${result.rank} of ${card.class_size}` : ""}</p>
  <p style="font-size:12px;color:#64748b">Grades: O (10) ≥ 90% · A+ (9) ≥ 80 · A (8) ≥ 70 · B+ (7) ≥ 60 · B (6) ≥ 50 · C (5) ≥ 40 · F (0) below pass mark · AB absent</p>
  <p class="summary"><b>Result:</b> ${escapeHtml(outcome(result))}</p>
  <div class="sign"><span>Class teacher: ${escapeHtml(card.class_teacher_name)}</span><span>Controller of Examinations</span><span>Principal</span></div>
</div><script>window.onload = () => window.print();</script></body></html>`;
}

// Opens the window before loading so pop-up blockers treat it as part of the click.
export async function printReportCard(loadCard) {
  const win = window.open("", "_blank");
  try {
    const card = await loadCard();
    if (!win) throw new Error("Allow pop-ups for this site to print report cards.");
    win.document.write(reportCardHtml(card));
    win.document.close();
  } catch (err) {
    win?.close();
    throw err;
  }
}

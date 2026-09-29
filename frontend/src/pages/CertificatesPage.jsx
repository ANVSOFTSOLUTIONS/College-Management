import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { fetchPostingOptions } from "../api/boardApi";
import { formatRupees } from "../api/feesApi";
import { cancelCertificate, fetchIdCards, fetchRecentCertificates, fetchStudentPhoto, issueCertificate } from "../api/certificatesApi";
import { fetchStudents } from "../api/studentsApi";
import { PrintPortal, SchoolHeader } from "../components/PrintPortal";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const CARDS_PER_PAGE = 8;

function formatDate(iso) {
  return iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";
}

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

// --- ID cards ----------------------------------------------------------------------

function IdCard({ card, school, year, photoUrl, qrUrl }) {
  return (
    <div className="flex flex-col overflow-hidden rounded-[3mm] border border-slate-300 bg-white text-slate-900" style={{ width: "85.6mm", height: "54mm" }}>
      <div className="flex items-center justify-between gap-2 bg-emerald-800 px-[3mm] py-[1.5mm] text-white">
        <SchoolHeader school={school} compact />
        <span className="shrink-0 text-[8px] font-semibold opacity-90">{year}</span>
      </div>
      <div className="flex flex-1 gap-[3mm] px-[3mm] py-[2mm]">
        <div className="shrink-0 overflow-hidden rounded-[1.5mm] border border-slate-200 bg-slate-100" style={{ width: "20mm", height: "25mm" }}>
          {photoUrl ? <img src={photoUrl} alt="" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-[20px] font-bold text-slate-400">{card.full_name[0]}</div>}
        </div>
        <div className="min-w-0 flex-1 text-[8.5px] leading-[1.35]">
          <p className="truncate text-[11px] font-bold leading-tight">{card.full_name}</p>
          <p>
            <span className="text-slate-500">Class:</span> <span className="font-semibold">{card.class_label}</span>
          </p>
          <p>
            <span className="text-slate-500">Adm. No:</span> <span className="font-semibold">{card.admission_number}</span>
          </p>
          {card.date_of_birth && (
            <p>
              <span className="text-slate-500">DOB:</span> {formatDate(card.date_of_birth)}
            </p>
          )}
          {card.blood_group && (
            <p>
              <span className="text-slate-500">Blood:</span> <span className="font-semibold text-rose-700">{card.blood_group}</span>
            </p>
          )}
          {card.parent_phone && (
            <p className="truncate">
              <span className="text-slate-500">Parent:</span> {card.parent_phone}
            </p>
          )}
        </div>
        {qrUrl && <img src={qrUrl} alt="" className="self-end" style={{ width: "14mm", height: "14mm" }} />}
      </div>
      {school.phone && <p className="truncate bg-slate-100 px-[3mm] py-[0.8mm] text-[7px] text-slate-600">If found, please call {school.phone}</p>}
    </div>
  );
}

function IdCardsTab({ token }) {
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState("");
  const [sheet, setSheet] = useState(null);
  const [photos, setPhotos] = useState({});
  const [qrs, setQrs] = useState({});
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPostingOptions(token)
      .then((list) => {
        setClasses(list);
        setClassId(list[0]?.id ?? "");
      })
      .catch(() => setClasses([]));
  }, [token]);

  // Release photo object URLs when the preview closes.
  useEffect(() => () => Object.values(photos).forEach((url) => URL.revokeObjectURL(url)), [photos]);

  async function handlePrepare() {
    setState("loading");
    setError(null);
    try {
      const data = await fetchIdCards(token, classId);
      const qrEntries = await Promise.all(data.cards.map(async (c) => [c.student_id, await QRCode.toDataURL(c.qr_text, { margin: 0, width: 160 })]));
      // Photos are private, so they're fetched with the token, a few at a time.
      const photoEntries = [];
      const queue = data.cards.filter((c) => c.has_photo);
      await Promise.all(
        Array.from({ length: 4 }, async () => {
          while (queue.length) {
            const card = queue.shift();
            try {
              photoEntries.push([card.student_id, URL.createObjectURL(await fetchStudentPhoto(token, card.student_id))]);
            } catch {
              // A missing photo just shows the initial.
            }
          }
        }),
      );
      setQrs(Object.fromEntries(qrEntries));
      setPhotos(Object.fromEntries(photoEntries));
      setSheet(data);
      setState("ready");
    } catch (err) {
      setError(errorMessage(err, "Couldn't prepare the ID cards."));
      setState("idle");
    }
  }

  const pages = [];
  for (let i = 0; i < (sheet?.cards.length ?? 0); i += CARDS_PER_PAGE) pages.push(sheet.cards.slice(i, i + CARDS_PER_PAGE));

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">Standard card size (85.6 × 54 mm), 8 per A4 sheet. Each card has a QR code with the college code and admission number.</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-slate-700">
          Class
          <select value={classId} onChange={(e) => setClassId(e.target.value)} className={INPUT}>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} - {c.section}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={!classId || state === "loading"} onClick={handlePrepare} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "loading" ? "Preparing…" : "Prepare ID cards"}
        </button>
      </div>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
      {state === "ready" && (
        <PrintPortal
          title={`ID cards · ${sheet.cards[0]?.class_label ?? ""} · ${sheet.cards.length} students`}
          onClose={() => {
            setState("idle");
            setSheet(null);
            setPhotos({});
          }}
        >
          {sheet.cards.length === 0 ? (
            <p className="rounded-xl bg-white p-8 text-sm text-slate-500">No current students in this class.</p>
          ) : (
            pages.map((cards, index) => (
              <div key={index} className={`print-page grid grid-cols-2 content-start gap-[5mm] bg-white p-[8mm] shadow-lg ${index < pages.length - 1 ? "print-break" : ""}`} style={{ width: "190mm" }}>
                {cards.map((card) => (
                  <IdCard key={card.student_id} card={card} school={sheet.school} year={sheet.academic_year} photoUrl={photos[card.student_id]} qrUrl={qrs[card.student_id]} />
                ))}
              </div>
            ))
          )}
        </PrintPortal>
      )}
    </div>
  );
}

// --- Certificates ------------------------------------------------------------------

function pronouns(gender) {
  if (gender === "female") return { child: "daughter", possessive: "Her" };
  if (gender === "male") return { child: "son", possessive: "His" };
  return { child: "child", possessive: "Their" };
}

function CertificateDocument({ certificate }) {
  const d = certificate.details;
  const tcRows = [
    ["Name of the pupil", d.student_name],
    ["Admission number", d.admission_number],
    ["Father's name", d.father_name || "—"],
    ["Mother's name", d.mother_name || "—"],
    ["Date of birth (in figures)", formatDate(d.date_of_birth)],
    ["Date of birth (in words)", d.date_of_birth_words || "—"],
    ["Date of admission", formatDate(d.admission_date)],
    ["Class in which the pupil last studied", d.class_name],
    ["Academic year", d.academic_year],
    ["Whether qualified for promotion to a higher class", d.promotion || "—"],
    ["Total working days / days present", `${d.working_days} / ${d.days_present}`],
    ["Whether all dues to the college are paid", d.fees_due > 0 ? `No, ${formatRupees(d.fees_due)} due` : "Yes"],
    ["General conduct", d.conduct],
    ["Date of leaving the college", formatDate(d.leaving_date)],
    ["Reason for leaving", d.reason],
    ["Remarks", d.remarks || "—"],
  ];
  const p = pronouns(d.gender);
  const parent = d.father_name || d.mother_name || d.guardian_name;

  return (
    <div className="print-page relative bg-white p-[14mm] text-slate-900 shadow-lg" style={{ width: "190mm", minHeight: "265mm" }}>
      {certificate.cancelled && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="-rotate-30 rounded-lg border-8 border-rose-500/40 px-8 py-2 text-7xl font-black tracking-widest text-rose-500/40">CANCELLED</span>
        </div>
      )}
      <div className="border-b-2 border-slate-800 pb-4">
        <SchoolHeader school={certificate.school} />
      </div>
      <h1 className="mt-6 text-center text-xl font-bold uppercase tracking-[0.2em] underline underline-offset-8">{certificate.title}</h1>
      <div className="mt-6 flex justify-between text-sm">
        <span>
          No: <span className="font-semibold">{certificate.serial_no}</span>
        </span>
        <span>
          Date: <span className="font-semibold">{formatDate(certificate.issued_on)}</span>
        </span>
      </div>

      {certificate.kind === "tc" ? (
        <table className="mt-6 w-full text-[13px]">
          <tbody>
            {tcRows.map(([label, value], i) => (
              <tr key={label} className="align-top">
                <td className="w-8 py-1.5">{i + 1}.</td>
                <td className="w-[55%] py-1.5 pr-2">{label}</td>
                <td className="py-1.5">
                  : <span className="font-semibold">{value}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-10 text-justify text-[15px] leading-8">
          This is to certify that <span className="font-semibold">{d.student_name}</span> (Admission No. <span className="font-semibold">{d.admission_number}</span>)
          {parent && (
            <>
              , {p.child} of <span className="font-semibold">{parent}</span>
            </>
          )}
          , is a bonafide student of this college, studying in <span className="font-semibold">{d.class_name}</span> during the academic year{" "}
          <span className="font-semibold">{d.academic_year}</span>.
          {d.date_of_birth && (
            <>
              {" "}
              {p.possessive} date of birth as per our records is <span className="font-semibold">{formatDate(d.date_of_birth)}</span> ({d.date_of_birth_words}).
            </>
          )}
          {d.purpose && (
            <>
              {" "}
              This certificate is issued for the purpose of <span className="font-semibold">{d.purpose}</span>.
            </>
          )}
        </p>
      )}

      <div className="mt-24 grid grid-cols-3 gap-6 text-center text-sm">
        {(certificate.kind === "tc" ? ["Class teacher", "Checked by", "Principal"] : ["", "", "Principal"]).map((label, i) => (
          <div key={i}>{label && <p className="border-t border-slate-500 pt-1">{label}</p>}</div>
        ))}
      </div>
      <p className="mt-2 text-right text-xs text-slate-500">(Signature with college seal)</p>
    </div>
  );
}

function IssueForm({ token, student, kind, onIssued, onCancel }) {
  const [form, setForm] = useState({ leaving_date: new Date().toLocaleDateString("en-CA"), reason: "", conduct: "Good", promotion: "", remarks: "", purpose: "" });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    if (kind === "tc" && !window.confirm(`Issue a TC for ${student.full_name}? They will be marked as left and their login switched off.`)) return;
    setState("saving");
    setError(null);
    try {
      onIssued(await issueCertificate(token, student.id, kind === "tc" ? { kind, ...form, purpose: undefined } : { kind, purpose: form.purpose }));
    } catch (err) {
      setError(errorMessage(err, "Couldn't issue the certificate."));
      setState("idle");
    }
  }

  const field = (key, label, props = {}) => (
    <div>
      <label htmlFor={`cert-${key}`} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input id={`cert-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-emerald-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">
        {kind === "tc" ? "Transfer certificate" : "Bonafide certificate"} for {student.full_name}
      </h3>
      {kind === "tc" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {field("leaving_date", "Date of leaving", { type: "date", required: true, max: new Date().toLocaleDateString("en-CA") })}
          {field("reason", "Reason for leaving", { placeholder: "Parent's request", maxLength: 200 })}
          {field("promotion", "Qualified for promotion?", { placeholder: "e.g. Yes, to Grade 6", maxLength: 100 })}
          {field("conduct", "General conduct", { maxLength: 50 })}
          <div className="sm:col-span-2">{field("remarks", "Remarks (optional)", { maxLength: 300 })}</div>
        </div>
      ) : (
        field("purpose", "Purpose", { placeholder: "e.g. Bank account opening, scholarship", maxLength: 200 })
      )}
      <p className="text-xs text-slate-500">Name, parents, date of birth, class, attendance and fee dues are filled in from the student&apos;s records.</p>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Issuing…" : "Issue & print"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
          Cancel
        </button>
      </div>
    </form>
  );
}

function CertificatesTab({ token }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [student, setStudent] = useState(null);
  const [kind, setKind] = useState(null);
  const [recent, setRecent] = useState([]);
  const [printing, setPrinting] = useState(null);
  const [error, setError] = useState(null);

  function loadRecent() {
    fetchRecentCertificates(token).then(setRecent).catch(() => setRecent([]));
  }

  useEffect(loadRecent, [token]);

  async function handleSearch(event) {
    event.preventDefault();
    setError(null);
    try {
      setResults(await fetchStudents(token, { q: query.trim(), includeLeft: true }));
    } catch (err) {
      setError(errorMessage(err, "Search failed."));
    }
  }

  async function handleCancel(certificate) {
    const reason = window.prompt(`Why cancel ${certificate.serial_no}?`);
    if (!reason || reason.trim().length < 3) return;
    try {
      await cancelCertificate(token, certificate.id, reason.trim());
      loadRecent();
    } catch (err) {
      setError(errorMessage(err, "Couldn't cancel."));
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSearch} className="flex flex-wrap items-end gap-3">
        <label className="min-w-64 flex-1 text-sm font-medium text-slate-700 sm:flex-none">
          Find a student
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name or admission number" className={INPUT} />
        </label>
        <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
          Search
        </button>
      </form>
      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}

      {results && !student && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {results.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">No students found.</li>}
          {results.slice(0, 20).map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
              <span className="text-sm">
                <span className="font-medium text-slate-900">{s.full_name}</span> <span className="text-xs text-slate-400">{s.admission_number}</span>
                <span className="text-slate-500"> · {s.class?.name} - {s.class?.section}</span>
                {s.status !== "active" && <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{s.status}</span>}
              </span>
              <span className="flex gap-2">
                <button type="button" onClick={() => { setStudent(s); setKind("tc"); }} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-rose-700 ring-1 ring-inset ring-rose-200 hover:bg-rose-50">
                  Issue TC
                </button>
                {s.status === "active" && (
                  <button type="button" onClick={() => { setStudent(s); setKind("bonafide"); }} className="rounded-lg px-3 py-1.5 text-sm font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50">
                    Bonafide
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {student && (
        <IssueForm
          key={`${student.id}-${kind}`}
          token={token}
          student={student}
          kind={kind}
          onCancel={() => setStudent(null)}
          onIssued={(certificate) => {
            setStudent(null);
            setResults(null);
            setQuery("");
            loadRecent();
            setPrinting(certificate);
          }}
        />
      )}

      <section>
        <h3 className="mb-2 font-semibold text-slate-900">Recently issued</h3>
        {recent.length === 0 ? (
          <p className="text-sm text-slate-500">No certificates issued yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">No.</th>
                  <th className="px-3 py-2">Student</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Issued</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recent.map((c) => (
                  <tr key={c.id} className={c.cancelled ? "text-slate-400" : ""}>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{c.serial_no}</td>
                    <td className="px-3 py-2">
                      {c.details.student_name} <span className="text-xs text-slate-400">{c.details.admission_number}</span>
                    </td>
                    <td className="px-3 py-2">
                      {c.kind === "tc" ? "TC" : "Bonafide"}
                      {c.cancelled && <span className="ml-2 rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-700">Cancelled</span>}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">{formatDate(c.issued_on)}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-right">
                      <button type="button" onClick={() => setPrinting(c)} className="font-semibold text-emerald-700 hover:underline">
                        Print
                      </button>
                      {!c.cancelled && (
                        <button type="button" onClick={() => handleCancel(c)} className="ml-3 font-semibold text-rose-700 hover:underline">
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {printing && (
        <PrintPortal title={`${printing.title} · ${printing.serial_no}`} onClose={() => setPrinting(null)}>
          <CertificateDocument certificate={printing} />
        </PrintPortal>
      )}
    </div>
  );
}

function CertificatesPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState("id-cards");
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">ID cards &amp; certificates</h2>
        <p className="mt-1 text-sm text-slate-500">Print a whole class&apos;s ID cards, or issue a TC or bonafide certificate from the student&apos;s records.</p>
      </div>
      <div className="flex gap-2" role="tablist">
        {[
          ["id-cards", "ID cards"],
          ["certificates", "TC & bonafide"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === id ? "bg-slate-900 text-white" : "bg-white text-slate-600 ring-1 ring-inset ring-slate-200"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "id-cards" ? <IdCardsTab token={token} /> : <CertificatesTab token={token} />}
    </div>
  );
}

export default CertificatesPage;

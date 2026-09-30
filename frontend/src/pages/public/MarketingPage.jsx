import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../lib/apiClient";
import SiteRenderer from "../../siteTemplates/SiteRenderer";
import { SAMPLE_SITE } from "../../siteTemplates/sampleSite";
import { FREE_TEMPLATES, THEMES } from "../../siteTemplates/themes";

const PRODUCT = "ANV College ERP";

const MODULE_CHIPS = [
  "Admissions",
  "Departments & HOD",
  "SGPA / CGPA",
  "Attendance",
  "Fees & online payment",
  "Placements",
  "Library",
  "Hostel",
  "Transport",
  "Payroll",
  "Timetable",
  "Assignments",
  "Leave",
  "Certificates",
  "Notices",
  "College website",
];

const ROLES = [
  {
    id: "student",
    label: "Students",
    title: "Everything a student checks, in their pocket",
    points: ["Attendance % with a 75% warning", "Grades, SGPA and CGPA each semester", "Assignments, timetable and notices", "Apply to placement drives they're eligible for"],
  },
  {
    id: "parent",
    label: "Parents",
    title: "Peace of mind for every family",
    points: ["Absence alerts the same day", "Results, remarks and fee dues", "Hostel room, bus route and warden / driver contacts", "One login for all their children"],
  },
  {
    id: "faculty",
    label: "Faculty",
    title: "Less admin, more teaching",
    points: ["Punch in / out from the phone", "Tap-to-mark attendance for the whole batch", "Enter marks, post assignments, write remarks", "Approve students' leave and see payslips"],
  },
  {
    id: "hod",
    label: "HODs",
    title: "Your department, at a glance",
    points: ["Which faculty are in, late or on leave today", "Every batch's attendance, marked or not", "Students below 75%, before it's too late", "Approve department faculty leave in one tap"],
  },
];

const FAQS = [
  ["Is there a mobile app?", "Yes. Students, parents, faculty and HODs use one Android / iPhone app. Admins and the office use the web console. The college website comes with it."],
  ["Does it support SGPA, CGPA and credits?", "Yes. Subjects carry credits; grades follow the 10-point scale (O, A+, A, B+, B, C, F). SGPA is calculated per exam and CGPA across semester-end exams, printed on the grade sheet."],
  ["Can students pay fees online?", "Yes, through your college's own Cashfree, Razorpay or PhonePe account — money goes straight to you. The office can also record cash, UPI and cheque payments with receipts."],
  ["Can we run several colleges on it?", "Yes. It's built for groups and trusts: every college gets its own console, website and data, and switches on only the modules it needs."],
  ["Is our data kept separate and safe?", "Every college's data is kept separate, each person sees only what their role allows, payment keys are stored encrypted and backups run daily."],
];

function useFont() {
  useEffect(() => {
    const id = "marketing-font";
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap";
    document.head.appendChild(link);
  }, []);
}

function Logo({ light = false }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-sky-500 text-lg font-black text-slate-950 shadow-lg shadow-emerald-500/30">A</span>
      <span className={`text-lg font-extrabold tracking-tight ${light ? "text-white" : "text-slate-900"}`}>
        ANV <span className="bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">College ERP</span>
      </span>
    </span>
  );
}

function Check({ tone = "emerald" }) {
  const tones = { emerald: "bg-emerald-500 text-slate-950", white: "bg-white text-slate-900" };
  return <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-black ${tones[tone]}`}>✓</span>;
}

// --- Illustrations (sample data, drawn in HTML so they stay crisp) --------------------------

function ConsoleMockup() {
  return (
    <div className="w-[520px] overflow-hidden rounded-2xl bg-white text-left shadow-[0_50px_100px_-30px_rgba(0,0,0,0.6)] ring-1 ring-white/10">
      <div className="flex items-center gap-1.5 border-b border-slate-100 bg-slate-50 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
        <span className="ml-3 rounded-md bg-white px-3 py-0.5 text-[10px] text-slate-400 ring-1 ring-slate-200">college.anverp.in / dashboard</span>
      </div>
      <div className="flex">
        <div className="w-32 space-y-1 border-r border-slate-100 p-3 text-[10px] font-semibold text-slate-500">
          {["Dashboard", "Departments", "Batches", "Exams & SGPA", "Fees", "Placements", "Library", "Hostel"].map((x, i) => (
            <p key={x} className={`rounded-md px-2 py-1.5 ${i === 0 ? "bg-emerald-50 text-emerald-700" : ""}`}>
              {x}
            </p>
          ))}
        </div>
        <div className="flex-1 space-y-3 p-4">
          <div className="grid grid-cols-3 gap-2">
            {[
              ["Present today", "93.4%", "from-emerald-400 to-teal-500"],
              ["Fees collected", "₹42.6L", "from-sky-400 to-indigo-500"],
              ["Students placed", "612", "from-fuchsia-400 to-rose-500"],
            ].map(([l, v, g]) => (
              <div key={l} className="rounded-xl bg-slate-50 p-2.5">
                <p className="text-[9px] text-slate-500">{l}</p>
                <p className="text-base font-extrabold text-slate-900">{v}</p>
                <span className={`mt-1 block h-1 w-3/4 rounded-full bg-gradient-to-r ${g}`} />
              </div>
            ))}
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <p className="text-[10px] font-bold text-slate-700">Attendance by department</p>
            <div className="mt-2 space-y-1.5">
              {[
                ["CSE", 96],
                ["ECE", 91],
                ["MECH", 84],
                ["MBA", 89],
              ].map(([d, v]) => (
                <div key={d} className="flex items-center gap-2 text-[9px] text-slate-500">
                  <span className="w-8 font-bold">{d}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
                    <span className="block h-full rounded-full bg-gradient-to-r from-emerald-400 to-sky-500" style={{ width: `${v}%` }} />
                  </span>
                  <span className="w-7 text-right font-bold text-slate-700">{v}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const PHONE_SCREENS = {
  student: (
    <>
      <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">Hi, Aarav</p>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-2xl bg-white p-3 shadow-sm">
          <p className="text-[9px] text-slate-400">Attendance</p>
          <p className="text-lg font-extrabold text-emerald-600">91%</p>
        </div>
        <div className="rounded-2xl bg-white p-3 shadow-sm">
          <p className="text-[9px] text-slate-400">CGPA</p>
          <p className="text-lg font-extrabold text-indigo-600">9.14</p>
        </div>
      </div>
      <div className="rounded-2xl bg-white p-3 shadow-sm">
        <p className="text-[10px] font-bold text-slate-700">Semester 3 results</p>
        {[
          ["Data Structures", "O"],
          ["DBMS", "A+"],
          ["Discrete Maths", "A"],
        ].map(([s, g]) => (
          <p key={s} className="mt-1 flex justify-between text-[10px] text-slate-500">
            {s} <span className="font-bold text-emerald-600">{g}</span>
          </p>
        ))}
      </div>
      <div className="rounded-2xl bg-gradient-to-r from-indigo-500 to-fuchsia-500 p-3 text-white">
        <p className="text-[9px] opacity-80">Placement drive · You&apos;re eligible</p>
        <p className="text-sm font-extrabold">Infosys · 3.6 LPA</p>
        <p className="mt-1 inline-block rounded-full bg-white/25 px-2 py-0.5 text-[9px] font-bold">Apply</p>
      </div>
    </>
  ),
  parent: (
    <>
      <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">Meghana · B.Tech CSE</p>
      <div className="rounded-2xl bg-rose-50 p-3 ring-1 ring-rose-100">
        <p className="text-[10px] font-bold text-rose-700">🔔 Absent today, 2nd period</p>
        <p className="text-[9px] text-rose-500">Marked by Mr. Anil Kumar</p>
      </div>
      <div className="rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 p-3 text-white">
        <p className="text-[9px] opacity-90">Tuition fee due</p>
        <p className="text-lg font-extrabold">₹45,000</p>
        <p className="mt-1 inline-block rounded-full bg-white/25 px-2 py-0.5 text-[9px] font-bold">Pay online</p>
      </div>
      <div className="rounded-2xl bg-white p-3 shadow-sm">
        <p className="text-[10px] font-bold text-slate-700">Girls Hostel · Room 101</p>
        <p className="text-[9px] text-slate-400">Warden: Mrs. V. Sujatha · Call</p>
      </div>
      <div className="rounded-2xl bg-white p-3 shadow-sm">
        <p className="text-[10px] font-bold text-slate-700">Bus Route 1 · Trunk Road 07:50</p>
      </div>
    </>
  ),
  faculty: (
    <>
      <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">Attendance · CSE-A</p>
      {[
        ["Aarav Kumar", "Present", "bg-emerald-500"],
        ["Meghana Reddy", "Present", "bg-emerald-500"],
        ["Sai Charan", "Absent", "bg-rose-500"],
        ["Divya Sree", "Late", "bg-amber-500"],
      ].map(([n, s, c]) => (
        <div key={n} className="flex items-center justify-between rounded-xl bg-white px-3 py-2 shadow-sm">
          <span className="text-[10px] font-semibold text-slate-700">{n}</span>
          <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold text-white ${c}`}>{s}</span>
        </div>
      ))}
      <div className="rounded-xl bg-emerald-600 py-2 text-center text-[10px] font-bold text-white">Save attendance</div>
    </>
  ),
  hod: (
    <>
      <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">CSE department · today</p>
      <div className="grid grid-cols-3 gap-1.5 text-center">
        {[
          ["14/15", "Faculty in"],
          ["486", "Students"],
          ["7", "< 75%"],
        ].map(([v, l]) => (
          <div key={l} className="rounded-xl bg-white p-2 shadow-sm">
            <p className="text-sm font-extrabold text-slate-900">{v}</p>
            <p className="text-[8px] text-slate-400">{l}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl bg-amber-50 p-3 ring-1 ring-amber-100">
        <p className="text-[10px] font-bold text-amber-700">2 faculty leave requests ›</p>
      </div>
      <div className="rounded-2xl bg-white p-3 shadow-sm">
        {[
          ["B.Tech CSE Sem 3", "58 P · 2 A"],
          ["B.Tech CSE Sem 5", "Not marked"],
        ].map(([b, s]) => (
          <p key={b} className="mt-1 flex justify-between text-[9px] text-slate-500 first:mt-0">
            {b} <span className={`font-bold ${s === "Not marked" ? "text-rose-500" : "text-emerald-600"}`}>{s}</span>
          </p>
        ))}
      </div>
    </>
  ),
};

function Phone({ role = "student", className = "" }) {
  return (
    <div className={`relative w-[250px] rounded-[2.6rem] border-[10px] border-slate-900 bg-slate-100 shadow-[0_40px_90px_-20px_rgba(16,185,129,0.5)] ${className}`}>
      <div className="absolute left-1/2 top-2 z-10 h-5 w-24 -translate-x-1/2 rounded-full bg-slate-900" />
      <div key={role} className="space-y-2.5 px-3.5 pb-6 pt-10 text-left [animation:fade-up_.45s_ease-out]">
        {PHONE_SCREENS[role]}
      </div>
    </div>
  );
}

function TemplateCard({ theme }) {
  const free = FREE_TEMPLATES.includes(theme.id);
  return (
    <a href={`/templates/${theme.id}`} target="_blank" rel="noreferrer" className="group block overflow-hidden rounded-2xl bg-white shadow-md ring-1 ring-slate-200/70 transition duration-300 hover:-translate-y-1.5 hover:shadow-2xl">
      <div className="relative h-48 overflow-hidden bg-slate-100" aria-hidden="true">
        <div className="pointer-events-none absolute left-0 top-0 w-[1280px] origin-top-left scale-[0.28] select-none transition duration-700 group-hover:-translate-y-24">
          <SiteRenderer site={SAMPLE_SITE} templateId={theme.id} />
        </div>
        <span className={`absolute left-3 top-3 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider shadow ${free ? "bg-emerald-500 text-slate-950" : "bg-slate-900 text-white"}`}>
          {free ? "Free" : "Pro"}
        </span>
      </div>
      <div className="p-4">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full ring-2 ring-white" style={{ background: theme.colors.primary }} />
          <span className="-ml-1.5 h-3 w-3 rounded-full ring-2 ring-white" style={{ background: theme.colors.accent }} />
          <p className="font-bold text-slate-900">{theme.name}</p>
        </div>
        <p className="mt-1 text-xs font-semibold text-emerald-700">{theme.audience}</p>
        <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{theme.tagline}</p>
      </div>
    </a>
  );
}

function DemoForm({ contact }) {
  const [form, setForm] = useState({ name: "", institution: "", phone: "", email: "", city: "", students: "", message: "", website: "" });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);
  const input =
    "mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm transition focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-500/15";

  async function handleSubmit(event) {
    event.preventDefault();
    setState("sending");
    setError(null);
    try {
      await apiRequest("/public/demo-requests", { method: "POST", body: form });
      setState("sent");
    } catch (err) {
      setState("error");
      setError(err?.message || "Couldn't send. Please try again.");
    }
  }

  const field = (key, label, props = {}) => (
    <div>
      <label htmlFor={`demo-${key}`} className="text-sm font-semibold text-slate-700">
        {label}
      </label>
      <input id={`demo-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={input} {...props} />
    </div>
  );

  const whatsapp = contact?.whatsapp_number?.replace(/\D/g, "");
  return (
    <section id="demo" className="relative overflow-hidden bg-slate-950 py-28 text-white">
      <div className="absolute -left-40 top-0 h-[30rem] w-[30rem] rounded-full bg-emerald-500/25 blur-3xl" />
      <div className="absolute -right-20 bottom-0 h-[26rem] w-[26rem] rounded-full bg-indigo-500/25 blur-3xl" />
      <div className="relative mx-auto grid max-w-6xl gap-14 px-5 lg:grid-cols-2">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-400">Free demo · 30 minutes</p>
          <h2 className="mt-4 text-4xl font-extrabold leading-tight sm:text-5xl">See your college running on {PRODUCT}</h2>
          <p className="mt-5 text-lg text-slate-300">We&apos;ll show you departments, SGPA / CGPA, fees, placements, the mobile app and a website in your college&apos;s colours.</p>
          <ul className="mt-9 space-y-4 text-slate-200">
            {[
              "We load your departments, batches, subjects and faculty",
              "Students, parents and faculty get the app the same week",
              "Your new college website goes live with the design you pick",
            ].map((t) => (
              <li key={t} className="flex gap-3">
                <Check />
                {t}
              </li>
            ))}
          </ul>
          {(whatsapp || contact?.phone || contact?.email) && (
            <div className="mt-10 flex flex-wrap gap-3">
              {whatsapp && (
                <a
                  href={`https://wa.me/${whatsapp}?text=${encodeURIComponent(`Hi, I'd like a demo of ${PRODUCT}.`)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-xl bg-[#25D366] px-5 py-3 font-bold text-slate-950 hover:brightness-95"
                >
                  Chat on WhatsApp
                </a>
              )}
              {contact.phone && (
                <a href={`tel:${contact.phone.replace(/\s/g, "")}`} className="rounded-xl bg-white/10 px-5 py-3 font-bold ring-1 ring-white/20 hover:bg-white/15">
                  📞 {contact.phone}
                </a>
              )}
              {contact.email && (
                <a href={`mailto:${contact.email}`} className="rounded-xl bg-white/10 px-5 py-3 font-bold ring-1 ring-white/20 hover:bg-white/15">
                  ✉ {contact.email}
                </a>
              )}
            </div>
          )}
        </div>
        <div className="rounded-3xl bg-white p-6 text-slate-900 shadow-2xl ring-1 ring-white/10 sm:p-8">
          {state === "sent" ? (
            <div className="flex h-full flex-col items-center justify-center py-16 text-center">
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl">✓</span>
              <p className="mt-4 text-2xl font-extrabold">Thank you!</p>
              <p className="mt-2 text-slate-500">We&apos;ll call you shortly to set up your demo.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-xl font-extrabold">Book your free demo</p>
              <div className="grid gap-4 sm:grid-cols-2">
                {field("name", "Your name", { required: true, minLength: 2, autoComplete: "name" })}
                {field("phone", "Mobile number", { required: true, type: "tel", inputMode: "tel", autoComplete: "tel" })}
              </div>
              {field("institution", "College / group name", { required: true, minLength: 2 })}
              <div className="grid gap-4 sm:grid-cols-2">
                {field("city", "City")}
                <div>
                  <label htmlFor="demo-students" className="text-sm font-semibold text-slate-700">
                    Number of students
                  </label>
                  <select id="demo-students" value={form.students} onChange={(e) => setForm({ ...form, students: e.target.value })} className={input}>
                    <option value="">Select</option>
                    {["Under 500", "500–1000", "1000–2500", "2500–5000", "5000+"].map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                </div>
              </div>
              {field("email", "Email (optional)", { type: "email", autoComplete: "email" })}
              <div>
                <label htmlFor="demo-message" className="text-sm font-semibold text-slate-700">
                  What would you like to see? (optional)
                </label>
                <textarea id="demo-message" rows={3} maxLength={1000} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className={input} />
              </div>
              <input tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
              {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
              <button
                type="submit"
                disabled={state === "sending"}
                className="w-full rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 py-3.5 text-base font-bold text-white shadow-lg shadow-emerald-600/30 transition hover:brightness-105 disabled:opacity-60"
              >
                {state === "sending" ? "Sending…" : "Request a demo"}
              </button>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}

function MarketingPage() {
  useFont();
  const [contact, setContact] = useState(null);
  const [role, setRole] = useState("student");
  const [openFaq, setOpenFaq] = useState(0);
  const [templateFilter, setTemplateFilter] = useState("all");
  const [showAllTemplates, setShowAllTemplates] = useState(false);

  useEffect(() => {
    document.title = `${PRODUCT} — College management, mobile app and website`;
    apiRequest("/public/platform")
      .then(setContact)
      .catch(() => setContact(null));
  }, []);

  // Rotate the hero phone through the four roles until the visitor picks one below.
  const [heroRole, setHeroRole] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setHeroRole((i) => (i + 1) % ROLES.length), 3500);
    return () => clearInterval(timer);
  }, []);

  const whatsapp = contact?.whatsapp_number?.replace(/\D/g, "");
  const activeRole = ROLES.find((r) => r.id === role);
  const templates = useMemo(() => {
    const list = templateFilter === "free" ? THEMES.filter((t) => FREE_TEMPLATES.includes(t.id)) : templateFilter === "pro" ? THEMES.filter((t) => !FREE_TEMPLATES.includes(t.id)) : THEMES;
    return showAllTemplates || templateFilter !== "all" ? list : list.slice(0, 6);
  }, [templateFilter, showAllTemplates]);

  return (
    <div className="min-h-screen overflow-x-clip bg-white text-slate-900 antialiased" style={{ fontFamily: "'Plus Jakarta Sans', Inter, system-ui, sans-serif" }}>
      <style>
        {`@keyframes fade-up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
          @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
          @keyframes marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
          @keyframes glow { 0%, 100% { opacity: .55; } 50% { opacity: .9; } }
          @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }`}
      </style>

      <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <a href="/">
            <Logo light />
          </a>
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-300 md:flex">
            {[
              ["#platform", "Platform"],
              ["#app", "Mobile app"],
              ["#templates", "Websites"],
              ["#faq", "FAQ"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="transition hover:text-white">
                {label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <a href="/login" className="rounded-lg px-3 py-2 text-sm font-semibold text-white hover:bg-white/10">
              Sign in
            </a>
            <a href="#demo" className="rounded-lg bg-gradient-to-r from-emerald-400 to-teal-400 px-4 py-2 text-sm font-bold text-slate-950 shadow-lg shadow-emerald-500/25 hover:brightness-105">
              Book a demo
            </a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "56px 56px" }} />
        <div className="absolute -top-48 left-1/4 h-[36rem] w-[36rem] rounded-full bg-emerald-500/30 blur-3xl [animation:glow_7s_ease-in-out_infinite]" />
        <div className="absolute -right-32 top-24 h-[28rem] w-[28rem] rounded-full bg-indigo-500/30 blur-3xl [animation:glow_9s_ease-in-out_infinite]" />
        <div className="absolute bottom-0 left-0 h-72 w-72 rounded-full bg-sky-500/20 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-16 px-5 pb-20 pt-20 lg:grid-cols-[1.05fr_1fr] lg:pt-28">
          <div className="[animation:fade-up_.7s_ease-out]">
            <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 ring-1 ring-white/15">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> Built for engineering, degree, pharmacy & management colleges
            </p>
            <h1 className="mt-7 text-5xl font-extrabold leading-[1.02] tracking-tight sm:text-[4.1rem]">
              The smart way to run a{" "}
              <span className="bg-gradient-to-r from-emerald-300 via-teal-200 to-sky-300 bg-clip-text text-transparent">modern college</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">
              Departments, SGPA / CGPA, fees, placements, library, hostel and transport — in one secure platform, with a mobile app for students, parents, faculty and HODs, and a stunning
              college website.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a href="#demo" className="rounded-xl bg-gradient-to-r from-emerald-400 to-teal-400 px-6 py-3.5 text-base font-bold text-slate-950 shadow-xl shadow-emerald-500/30 transition hover:-translate-y-0.5">
                Book a free demo →
              </a>
              <a href="#templates" className="rounded-xl bg-white/10 px-6 py-3.5 text-base font-bold ring-1 ring-white/20 transition hover:bg-white/15">
                See 15 website designs
              </a>
            </div>
            <dl className="mt-12 grid max-w-lg grid-cols-3 gap-6 border-t border-white/10 pt-8">
              {[
                ["25+", "modules"],
                ["4", "roles in one app"],
                ["15", "website designs"],
              ].map(([v, l]) => (
                <div key={l}>
                  <dt className="text-3xl font-extrabold text-white">{v}</dt>
                  <dd className="mt-1 text-sm text-slate-400">{l}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="relative hidden h-[520px] lg:block">
            <div className="absolute -right-24 top-6">
              <ConsoleMockup />
            </div>
            <div className="absolute bottom-0 left-4 z-10 [animation:float_6s_ease-in-out_infinite]">
              <Phone role={ROLES[heroRole].id} />
              <p className="mt-3 text-center text-xs font-semibold text-slate-400">{ROLES[heroRole].label} app</p>
            </div>
          </div>
        </div>
        <div className="relative border-t border-white/10 bg-white/[0.03] py-4">
          <div className="flex w-max gap-3 [animation:marquee_40s_linear_infinite]">
            {[...MODULE_CHIPS, ...MODULE_CHIPS].map((m, i) => (
              <span key={`${m}-${i}`} className="whitespace-nowrap rounded-full bg-white/5 px-4 py-1.5 text-sm font-medium text-slate-300 ring-1 ring-white/10">
                {m}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Bento features */}
      <section id="platform" className="mx-auto max-w-6xl px-5 py-28">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-600">One platform</p>
          <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">Built for how colleges actually work</h2>
          <p className="mt-4 text-lg text-slate-500">Not a school system with the word &ldquo;college&rdquo; on it — credits, semesters, departments and placements are built in.</p>
        </div>
        <div className="mt-16 grid gap-5 md:grid-cols-6">
          <div className="group relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 to-violet-700 p-8 text-white md:col-span-4">
            <div className="absolute -right-10 -top-10 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
            <p className="text-sm font-bold uppercase tracking-widest text-indigo-200">Exams & grading</p>
            <h3 className="mt-2 text-3xl font-extrabold">SGPA & CGPA, calculated for you</h3>
            <p className="mt-3 max-w-md text-indigo-100">Credits per subject, the 10-point scale, internal and semester-end exams, failed papers flagged — and printable grade sheets.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              {[
                ["O", "10"],
                ["A+", "9"],
                ["A", "8"],
                ["B+", "7"],
                ["B", "6"],
                ["C", "5"],
              ].map(([g, p]) => (
                <span key={g} className="rounded-xl bg-white/15 px-4 py-2 text-center ring-1 ring-white/20 transition group-hover:bg-white/20">
                  <span className="block text-xl font-extrabold">{g}</span>
                  <span className="text-[11px] text-indigo-200">{p} pts</span>
                </span>
              ))}
            </div>
          </div>
          <div className="rounded-3xl bg-slate-950 p-8 text-white md:col-span-2">
            <p className="text-sm font-bold uppercase tracking-widest text-emerald-400">Placements</p>
            <h3 className="mt-2 text-2xl font-extrabold">Drives, eligibility, offers</h3>
            <p className="mt-3 text-slate-400">Minimum CGPA and departments per drive. Students apply from the app.</p>
            <p className="mt-6 bg-gradient-to-r from-emerald-300 to-sky-300 bg-clip-text text-5xl font-extrabold text-transparent">612</p>
            <p className="text-sm text-slate-400">students placed (sample)</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-8 md:col-span-2">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-2xl">🏛️</span>
            <h3 className="mt-4 text-xl font-extrabold">Departments & HOD</h3>
            <p className="mt-2 text-slate-500">Programs, semesters, regulations and batches. HODs see their department&apos;s day and approve faculty leave.</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-gradient-to-br from-amber-50 to-orange-50 p-8 md:col-span-2">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-2xl shadow-sm">💳</span>
            <h3 className="mt-4 text-xl font-extrabold">Fees & online payments</h3>
            <p className="mt-2 text-slate-600">Razorpay, Cashfree or PhonePe straight into your college account. Receipts, concessions and dues.</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-8 md:col-span-2">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-50 text-2xl">📚</span>
            <h3 className="mt-4 text-xl font-extrabold">Library, hostel & transport</h3>
            <p className="mt-2 text-slate-500">Book loans and fines, rooms and beds, bus routes and stops — students and parents see theirs in the app.</p>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-8 md:col-span-3">
            <div className="flex flex-wrap gap-2">
              {["Admissions & online applications", "Faculty punch in / out", "Payroll & payslips", "Timetable & calendar", "Certificates & ID cards", "Reports & activity log"].map((x) => (
                <span key={x} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700">
                  {x}
                </span>
              ))}
            </div>
            <h3 className="mt-5 text-xl font-extrabold">And everything the office needs</h3>
            <p className="mt-2 text-slate-500">One console for the principal and office, with an activity log and daily backups.</p>
          </div>
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-500 to-teal-600 p-8 text-white md:col-span-3">
            <div className="absolute -bottom-16 -right-16 h-56 w-56 rounded-full bg-white/15 blur-2xl" />
            <p className="text-sm font-bold uppercase tracking-widest text-emerald-100">For groups & trusts</p>
            <h3 className="mt-2 text-2xl font-extrabold">Many colleges, one platform</h3>
            <p className="mt-3 max-w-md text-emerald-50">Each college gets its own console, website and data. Switch modules on per college and grow at your pace.</p>
          </div>
        </div>
      </section>

      {/* Mobile app */}
      <section id="app" className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white py-28">
        <div className="mx-auto grid max-w-6xl items-center gap-16 px-5 lg:grid-cols-2">
          <div className="order-2 flex justify-center lg:order-1">
            <div className="relative">
              <div className="absolute inset-0 -z-10 translate-x-6 translate-y-6 rounded-[3rem] bg-gradient-to-br from-emerald-200 to-sky-200 blur-2xl" />
              <Phone role={role} />
            </div>
          </div>
          <div className="order-1 lg:order-2">
            <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-600">One mobile app, four experiences</p>
            <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">Everyone on campus, connected</h2>
            <div className="mt-8 flex flex-wrap gap-2">
              {ROLES.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setRole(r.id)}
                  className={`rounded-full px-5 py-2.5 text-sm font-bold transition ${role === r.id ? "bg-slate-900 text-white shadow-lg" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-slate-300"}`}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <div key={role} className="[animation:fade-up_.4s_ease-out]">
              <h3 className="mt-8 text-2xl font-extrabold">{activeRole.title}</h3>
              <ul className="mt-5 space-y-3">
                {activeRole.points.map((p) => (
                  <li key={p} className="flex items-start gap-3 text-slate-700">
                    <Check />
                    <span className="font-medium">{p}</span>
                  </li>
                ))}
              </ul>
            </div>
            <p className="mt-8 text-sm text-slate-500">Android & iPhone · Admins and the office use the web console.</p>
          </div>
        </div>
      </section>

      {/* Templates */}
      <section id="templates" className="py-28">
        <div className="mx-auto max-w-6xl px-5">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-600">Your college website, included</p>
              <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">15 designs made for colleges</h2>
              <p className="mt-4 text-lg text-slate-500">Programs, departments, placements, the principal&apos;s message and online admissions — updated from your console. Switch designs anytime.</p>
            </div>
            <div className="flex gap-2">
              {[
                ["all", "All"],
                ["free", "Free"],
                ["pro", "Pro"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTemplateFilter(id)}
                  className={`rounded-full px-4 py-2 text-sm font-bold transition ${templateFilter === id ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((theme) => (
              <TemplateCard key={theme.id} theme={theme} />
            ))}
          </div>
          {templateFilter === "all" && !showAllTemplates && (
            <div className="mt-10 text-center">
              <button type="button" onClick={() => setShowAllTemplates(true)} className="rounded-xl bg-slate-900 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-800">
                Show all {THEMES.length} designs
              </button>
            </div>
          )}
        </div>
      </section>

      {/* Steps */}
      <section className="bg-slate-950 py-28 text-white">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-400">Go live in a week</p>
            <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">We set it up. You run your college.</h2>
          </div>
          <div className="mt-16 grid gap-6 md:grid-cols-4">
            {[
              ["01", "Book a demo", "We learn your programs, fee structure and exam pattern."],
              ["02", "We load your data", "Departments, batches, subjects, faculty and students, imported for you."],
              ["03", "Launch the app", "Students, parents, faculty and HODs sign in with slips we print."],
              ["04", "Go live online", "Your website and online fee payment switch on."],
            ].map(([n, title, text]) => (
              <div key={n} className="relative rounded-3xl bg-white/5 p-7 ring-1 ring-white/10 transition hover:bg-white/10">
                <span className="bg-gradient-to-r from-emerald-300 to-sky-300 bg-clip-text text-4xl font-extrabold text-transparent">{n}</span>
                <h3 className="mt-4 text-lg font-bold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-3xl px-5 py-28">
        <h2 className="text-center text-4xl font-extrabold tracking-tight">Questions colleges ask us</h2>
        <div className="mt-12 space-y-3">
          {FAQS.map(([q, a], i) => (
            <div key={q} className={`rounded-2xl border transition ${openFaq === i ? "border-emerald-200 bg-emerald-50/40" : "border-slate-200"}`}>
              <button type="button" onClick={() => setOpenFaq(openFaq === i ? -1 : i)} className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left font-bold" aria-expanded={openFaq === i}>
                {q}
                <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-lg text-emerald-600 shadow-sm transition ${openFaq === i ? "rotate-45" : ""}`}>+</span>
              </button>
              {openFaq === i && <p className="px-6 pb-5 leading-relaxed text-slate-600">{a}</p>}
            </div>
          ))}
        </div>
      </section>

      <DemoForm contact={contact} />

      <footer className="bg-slate-950 text-slate-400">
        <div className="mx-auto grid max-w-6xl gap-10 border-t border-white/10 px-5 py-14 md:grid-cols-4">
          <div className="md:col-span-2">
            <Logo light />
            <p className="mt-4 max-w-sm text-sm leading-relaxed">College management, a mobile app for students, parents, faculty and HODs, and a beautiful college website — by ANV Soft Solutions.</p>
          </div>
          <div className="text-sm">
            <p className="mb-3 font-bold uppercase tracking-wider text-slate-300">Product</p>
            {[
              ["#platform", "Platform"],
              ["#app", "Mobile app"],
              ["#templates", "Website designs"],
              ["#faq", "FAQ"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="block py-1 hover:text-white">
                {label}
              </a>
            ))}
          </div>
          <div className="text-sm">
            <p className="mb-3 font-bold uppercase tracking-wider text-slate-300">Get started</p>
            <a href="#demo" className="block py-1 hover:text-white">
              Book a demo
            </a>
            <a href="/login" className="block py-1 hover:text-white">
              Sign in
            </a>
          </div>
        </div>
        <p className="border-t border-white/10 py-6 text-center text-xs">© {new Date().getFullYear()} ANV Soft Solutions Pvt Ltd · {PRODUCT} · 🔒 Secure software</p>
      </footer>

      {whatsapp && (
        <a
          href={`https://wa.me/${whatsapp}?text=${encodeURIComponent(`Hi, I'd like to know more about ${PRODUCT}.`)}`}
          target="_blank"
          rel="noreferrer"
          aria-label="Chat on WhatsApp"
          className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-[#25D366] text-white shadow-xl shadow-black/20 transition hover:scale-105"
        >
          <svg viewBox="0 0 24 24" className="h-7 w-7" fill="currentColor" aria-hidden="true">
            <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8s-.4-.1-.6.1-.7.8-.8 1-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.8-1.3a.5.5 0 0 0 0-.5l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 2.9 2.9 0 0 0-.9 2.2 5.1 5.1 0 0 0 1.1 2.7 11.6 11.6 0 0 0 4.4 3.9c1.6.7 2.3.8 3.1.6a2.6 2.6 0 0 0 1.7-1.2 2.1 2.1 0 0 0 .2-1.2c-.1-.1-.3-.2-.5-.3Z" />
          </svg>
        </a>
      )}
    </div>
  );
}

export default MarketingPage;

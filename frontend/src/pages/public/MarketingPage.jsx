import { useEffect, useState } from "react";

import { apiRequest } from "../../lib/apiClient";
import SiteRenderer from "../../siteTemplates/SiteRenderer";
import { SAMPLE_SITE } from "../../siteTemplates/sampleSite";
import { THEMES } from "../../siteTemplates/themes";

const PRODUCT = "ANV College ERP";

const FEATURES = [
  { icon: "🎓", title: "Students & parents", text: "Complete student records with father, mother and guardian contacts. Class teachers keep their own class up to date." },
  { icon: "✅", title: "Attendance with alerts", text: "Mark attendance in seconds on a phone. Parents are alerted when their child is absent." },
  { icon: "⏱️", title: "Staff punch in / out", text: "Teachers punch in from their own login. Late arrivals and hours worked show up for the admin." },
  { icon: "🗓️", title: "Leave management", text: "Teachers and parents apply for leave in the app; the right person approves with one tap." },
  { icon: "💰", title: "Fees & receipts", text: "Term-wise fees per class, concessions, printed receipts, dues reports and reminders." },
  { icon: "💳", title: "Online fee payment", text: "Parents pay from the app with Cashfree, Razorpay or PhonePe, straight into your college's own account." },
  { icon: "📝", title: "Exams & report cards", text: "Subject teachers enter marks; grades, ranks and printable report cards are automatic." },
  { icon: "🔔", title: "Notifications", text: "Leave decisions, class-teacher absences, exam results and fee reminders reach the right people." },
  { icon: "📄", title: "Documents & photos", text: "Parents upload their child's photo and certificates; the college verifies them. No paperwork piles." },
  { icon: "🌐", title: "College website", text: "A beautiful public website for your college with 10 designs to choose from. Updated from the app." },
  { icon: "📱", title: "Apps for everyone", text: "Installable apps for admins, teachers and parents. Share one QR code — no Play Store needed." },
  { icon: "🏫", title: "Made for colleges", text: "Nursery to Class 12: classes and sections, class teachers, subject teachers, terms and report cards." },
];

const ROLES = [
  { id: "admin", label: "Principal & office", points: ["See every class, teacher and student in one place", "Collect fees, print receipts, chase dues", "Approve staff leave and see who came late", "Publish exam results and update the website"] },
  { id: "teacher", label: "Teachers", points: ["Punch in and out from the phone", "Take attendance and enter marks in minutes", "Write remarks that reach parents", "Approve leave parents ask for their class"] },
  { id: "parent", label: "Parents", points: ["Attendance, remarks, homework and results for every child", "Pay fees online or report an offline payment, with receipts", "Upload documents and apply for leave for their child", "One login for all their children"] },
];

const FAQS = [
  ["Do parents and teachers need to download an app from the Play Store?", "No. They open a link or scan a QR code and tap Install — the app appears on their home screen like any other app, on Android and iPhone."],
  ["Can parents pay fees online?", "Yes, through Cashfree, Razorpay or PhonePe into your college's own account. Until online payment is switched on, the office records cash, UPI and cheque payments with receipts."],
  ["Do parents get SMS alerts?", "Alerts for absences, missed exams and fee dues are built in and appear in the app. SMS delivery is switched on once your SMS account is connected."],
  ["Is our data kept separate from other colleges?", "Yes. Every college's data is kept separate, and each person sees only what their role allows."],
];

function Logo({ light = false }) {
  return (
    <span className="flex items-center gap-2">
      <img src="/icons/icon-192.png" alt="" className="h-9 w-9 rounded-xl" />
      <span className={`text-lg font-extrabold tracking-tight ${light ? "text-white" : "text-slate-900"}`}>
        ANV <span className="text-emerald-500">College ERP</span>
      </span>
    </span>
  );
}

function PhoneMockup() {
  // Illustrative app screen (sample data), built in HTML so it stays crisp.
  return (
    <div className="relative mx-auto w-[260px] rotate-[4deg] rounded-[2.5rem] border-[10px] border-slate-900 bg-slate-50 shadow-[0_40px_80px_-20px_rgba(16,185,129,0.55)]">
      <div className="absolute left-1/2 top-2 h-5 w-24 -translate-x-1/2 rounded-full bg-slate-900" />
      <div className="space-y-3 px-4 pb-6 pt-10 text-left">
        <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-600">Parent portal</p>
        <div className="flex items-center gap-2 rounded-2xl bg-white p-3 shadow-sm">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-700">AR</span>
          <div>
            <p className="text-xs font-bold text-slate-800">Ananya · Class 5A</p>
            <p className="text-[10px] text-slate-400">Sample student</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          {[
            ["18", "Present", "text-emerald-600"],
            ["1", "Absent", "text-rose-600"],
            ["A2", "Grade", "text-indigo-600"],
          ].map(([v, l, c]) => (
            <div key={l} className="rounded-xl bg-white p-2 shadow-sm">
              <p className={`text-base font-extrabold ${c}`}>{v}</p>
              <p className="text-[9px] text-slate-400">{l}</p>
            </div>
          ))}
        </div>
        <div className="rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 p-3 text-white shadow-sm">
          <p className="text-[10px] font-semibold opacity-90">Term 1 fee due</p>
          <p className="text-lg font-extrabold">₹4,500</p>
          <p className="mt-1 inline-block rounded-full bg-white/25 px-2 py-0.5 text-[10px] font-bold">Pay now</p>
        </div>
        <div className="rounded-2xl bg-white p-3 shadow-sm">
          <p className="text-[10px] font-bold text-slate-700">🔔 Unit Test 1 results published</p>
          <p className="mt-1 text-[10px] text-slate-400">Report card ready to view</p>
        </div>
      </div>
    </div>
  );
}

function DashboardMockup() {
  return (
    <div className="w-[340px] -rotate-[3deg] rounded-2xl bg-white p-4 text-left shadow-2xl ring-1 ring-black/5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold text-slate-800">Today at college</p>
        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">Sample</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {[
          ["Students present", "94%", "bg-emerald-500"],
          ["Staff punched in", "22 / 24", "bg-sky-500"],
          ["Fees collected", "₹1.8L", "bg-amber-500"],
          ["Leave requests", "3", "bg-violet-500"],
        ].map(([label, value, bar]) => (
          <div key={label} className="rounded-xl bg-slate-50 p-3">
            <p className="text-[10px] text-slate-500">{label}</p>
            <p className="text-lg font-extrabold text-slate-900">{value}</p>
            <span className={`mt-1 block h-1 w-2/3 rounded-full ${bar}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

function TemplateCard({ theme }) {
  return (
    <a href={`/templates/${theme.id}`} target="_blank" rel="noreferrer" className="group block w-72 shrink-0 overflow-hidden rounded-2xl bg-white shadow-lg ring-1 ring-black/5 transition hover:-translate-y-1 hover:shadow-2xl">
      <div className="relative h-44 overflow-hidden" aria-hidden="true">
        <div className="pointer-events-none absolute left-0 top-0 w-[1280px] origin-top-left scale-[0.225] select-none">
          <SiteRenderer site={SAMPLE_SITE} templateId={theme.id} />
        </div>
      </div>
      <div className="p-4">
        <p className="font-bold text-slate-900">{theme.name}</p>
        <p className="mt-1 text-xs text-slate-500">{theme.tagline}</p>
        <p className="mt-3 text-xs font-semibold text-emerald-700 group-hover:underline">Live preview ↗</p>
      </div>
    </a>
  );
}

function DemoForm({ contact }) {
  const [form, setForm] = useState({ name: "", institution: "", phone: "", email: "", city: "", students: "", message: "", website: "" });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);
  const input = "mt-1 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30";

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
    <section id="demo" className="relative overflow-hidden bg-slate-950 py-24 text-white">
      <div className="absolute -left-40 top-0 h-96 w-96 rounded-full bg-emerald-500/30 blur-3xl" />
      <div className="absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-sky-500/20 blur-3xl" />
      <div className="relative mx-auto grid max-w-6xl gap-12 px-5 lg:grid-cols-2">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-400">Free demo</p>
          <h2 className="mt-3 text-4xl font-extrabold leading-tight sm:text-5xl">See {PRODUCT} running for your college</h2>
          <p className="mt-5 text-lg text-slate-300">Tell us a little about your institution and we&apos;ll walk you through it — attendance, fees, exams, apps and your new website.</p>
          <ul className="mt-8 space-y-3 text-slate-200">
            {["We set up your classes, teachers and students", "Your staff and parents get QR codes to install the app", "Your college website goes live with the design you pick"].map((t) => (
              <li key={t} className="flex gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-bold text-slate-950">✓</span>
                {t}
              </li>
            ))}
          </ul>
          {(whatsapp || contact?.phone || contact?.email) && (
            <div className="mt-10 flex flex-wrap gap-3">
              {whatsapp && (
                <a href={`https://wa.me/${whatsapp}?text=${encodeURIComponent(`Hi, I'd like a demo of ${PRODUCT}.`)}`} target="_blank" rel="noreferrer" className="rounded-xl bg-[#25D366] px-5 py-3 font-bold text-slate-950 hover:brightness-95">
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
        <div className="rounded-3xl bg-white p-6 text-slate-900 shadow-2xl sm:p-8">
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
              {field("institution", "College name", { required: true, minLength: 2 })}
              <div className="grid gap-4 sm:grid-cols-2">
                {field("city", "City")}
                <div>
                  <label htmlFor="demo-students" className="text-sm font-semibold text-slate-700">
                    Number of students
                  </label>
                  <select id="demo-students" value={form.students} onChange={(e) => setForm({ ...form, students: e.target.value })} className={input}>
                    <option value="">Select</option>
                    {["Under 200", "200–500", "500–1000", "1000–2000", "2000+"].map((o) => (
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
              <button type="submit" disabled={state === "sending"} className="w-full rounded-xl bg-emerald-600 py-3.5 text-base font-bold text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-700 disabled:opacity-60">
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
  const [contact, setContact] = useState(null);
  const [role, setRole] = useState("admin");
  const [openFaq, setOpenFaq] = useState(0);

  useEffect(() => {
    document.title = `${PRODUCT} — College management with apps for parents and teachers`;
    apiRequest("/public/platform")
      .then(setContact)
      .catch(() => setContact(null));
  }, []);

  const whatsapp = contact?.whatsapp_number?.replace(/\D/g, "");
  const activeRole = ROLES.find((r) => r.id === role);

  return (
    <div className="min-h-screen bg-white font-[Inter,system-ui,sans-serif] text-slate-900 antialiased">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <a href="/">
            <Logo light />
          </a>
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-300 md:flex">
            <a href="#features" className="hover:text-white">
              Features
            </a>
            <a href="#roles" className="hover:text-white">
              For everyone
            </a>
            <a href="#templates" className="hover:text-white">
              Website designs
            </a>
            <a href="#faq" className="hover:text-white">
              FAQ
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <a href="/login" className="rounded-lg px-3 py-2 text-sm font-semibold text-white hover:bg-white/10">
              Sign in
            </a>
            <a href="#demo" className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-emerald-400">
              Book a demo
            </a>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 opacity-[0.08]" style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "48px 48px" }} />
        <div className="absolute -top-40 left-1/3 h-[32rem] w-[32rem] rounded-full bg-emerald-500/30 blur-3xl" />
        <div className="absolute -right-20 top-40 h-80 w-80 rounded-full bg-sky-500/25 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-14 px-5 pb-24 pt-20 lg:grid-cols-2 lg:pt-28">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-emerald-300 ring-1 ring-white/15">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> For colleges, nursery to Class 12
            </p>
            <h1 className="mt-6 text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              Run your whole college from{" "}
              <span className="bg-gradient-to-r from-emerald-300 via-teal-300 to-sky-300 bg-clip-text text-transparent">one simple app</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-slate-300">
              Attendance, fees, exams, staff punch-in, leave and a beautiful college website — with apps for faculty, students and parents that install from a single QR code.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a href="#demo" className="rounded-xl bg-emerald-500 px-6 py-3.5 text-base font-bold text-slate-950 shadow-lg shadow-emerald-500/30 hover:bg-emerald-400">
                Book a free demo
              </a>
              <a href="#templates" className="rounded-xl bg-white/10 px-6 py-3.5 text-base font-bold ring-1 ring-white/20 hover:bg-white/15">
                See website designs
              </a>
            </div>
            <p className="mt-6 text-sm text-slate-400">Android & iPhone · Parents pay fees online · Your own college website</p>
          </div>
          <div className="relative hidden h-[460px] lg:block">
            <div className="absolute right-6 top-0">
              <PhoneMockup />
            </div>
            <div className="absolute bottom-6 left-0 z-10">
              <DashboardMockup />
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-5 py-24">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-600">Everything in one place</p>
          <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">Less paperwork. More teaching.</h2>
          <p className="mt-4 text-lg text-slate-500">Every part of the college day, connected — so the office, teachers and parents always see the same information.</p>
        </div>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="group rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-1 hover:border-emerald-200 hover:shadow-xl">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-2xl transition group-hover:scale-110">{f.icon}</span>
              <h3 className="mt-4 text-lg font-bold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="roles" className="bg-gradient-to-b from-emerald-50 to-white py-24">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-600">One app, four experiences</p>
            <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">Everyone gets exactly what they need</h2>
          </div>
          <div className="mx-auto mt-10 flex max-w-2xl flex-wrap justify-center gap-2">
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
          <div className="mx-auto mt-8 grid max-w-3xl gap-3 sm:grid-cols-2">
            {activeRole.points.map((p) => (
              <div key={p} className="flex items-start gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-xs font-bold text-white">✓</span>
                <span className="font-medium text-slate-700">{p}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="templates" className="overflow-hidden py-24">
        <div className="mx-auto max-w-6xl px-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-2xl">
              <p className="text-sm font-bold uppercase tracking-[0.25em] text-emerald-600">Your college website, included</p>
              <h2 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">10 stunning designs. Switch anytime.</h2>
              <p className="mt-4 text-lg text-slate-500">Pick a design, add your photos and news from the app, and your website is live — no web developer needed.</p>
            </div>
            <a href="#demo" className="shrink-0 rounded-xl bg-slate-900 px-5 py-3 text-sm font-bold text-white hover:bg-slate-800">
              Get your website
            </a>
          </div>
        </div>
        <div className="mt-12 flex gap-6 overflow-x-auto px-5 pb-6 [scrollbar-width:thin] sm:px-[max(1.25rem,calc((100vw-72rem)/2))]">
          {THEMES.map((theme) => (
            <TemplateCard key={theme.id} theme={theme} />
          ))}
        </div>
      </section>

      <section className="bg-slate-50 py-24">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-4xl font-extrabold tracking-tight sm:text-5xl">Live in three steps</h2>
          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {[
              ["1", "Book a demo", "We understand how your college works — classes, fees, exams and timings."],
              ["2", "We set you up", "Your classes, teachers, students and fee structure are added for you."],
              ["3", "Share the QR codes", "Print or WhatsApp the install QR codes to staff and parents. Done."],
            ].map(([n, title, text]) => (
              <div key={n} className="relative rounded-3xl bg-white p-8 shadow-sm ring-1 ring-slate-100">
                <span className="absolute -top-5 left-8 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500 text-lg font-extrabold text-slate-950 shadow-lg shadow-emerald-500/30">{n}</span>
                <h3 className="mt-3 text-xl font-bold">{title}</h3>
                <p className="mt-2 text-slate-500">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="faq" className="mx-auto max-w-3xl px-5 py-24">
        <h2 className="text-center text-4xl font-extrabold tracking-tight">Questions colleges ask us</h2>
        <div className="mt-10 divide-y divide-slate-200 rounded-2xl border border-slate-200">
          {FAQS.map(([q, a], i) => (
            <div key={q}>
              <button type="button" onClick={() => setOpenFaq(openFaq === i ? -1 : i)} className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left font-bold" aria-expanded={openFaq === i}>
                {q}
                <span className={`text-xl text-emerald-600 transition ${openFaq === i ? "rotate-45" : ""}`}>+</span>
              </button>
              {openFaq === i && <p className="px-6 pb-5 text-slate-600">{a}</p>}
            </div>
          ))}
        </div>
      </section>

      <DemoForm contact={contact} />

      <footer className="bg-slate-950 text-slate-400">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 border-t border-white/10 px-5 py-8 sm:flex-row">
          <Logo light />
          <p className="text-sm">© {new Date().getFullYear()} ANV Soft Solutions Pvt Ltd · {PRODUCT} · 🔒 Secure software</p>
          <a href="/login" className="text-sm font-semibold text-white hover:underline">
            Sign in →
          </a>
        </div>
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

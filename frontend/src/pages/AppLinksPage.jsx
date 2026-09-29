import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/apiClient";

// Students don't sign in; parents do everything for their children.
const AUDIENCES = [
  {
    id: "parent",
    title: "Parents",
    how: "Sign in with the mobile number the college has on record and the password from the college.",
    link: (origin) => `${origin}/?as=parent`,
  },
  {
    id: "staff",
    title: "Teachers",
    how: "Sign in with their email and password.",
    link: (origin) => `${origin}/?as=staff`,
  },
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function AudienceCard({ audience, url, qr, schoolName }) {
  const [copied, setCopied] = useState(false);
  const message = `${schoolName}: install our app on your phone. Open ${url} and tap "Install" (iPhone: Share → Add to Home Screen). ${audience.how}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy this link:", url);
    }
  }

  return (
    <section className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-white p-5 text-center">
      <h3 className="text-lg font-semibold text-slate-900">{audience.title}</h3>
      {qr ? <img src={qr} alt={`QR code for ${audience.title.toLowerCase()}`} className="h-48 w-48" /> : <div className="h-48 w-48 animate-pulse rounded bg-slate-100" />}
      <p className="break-all text-xs text-slate-500">{url}</p>
      <p className="text-xs text-slate-500">{audience.how}</p>
      <div className="flex flex-wrap justify-center gap-2">
        <button type="button" onClick={copy} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-100">
          {copied ? "Copied" : "Copy link"}
        </button>
        <a
          href={`https://wa.me/?text=${encodeURIComponent(message)}`}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
        >
          Share on WhatsApp
        </a>
        {qr && (
          <a href={qr} download={`${audience.id}-app-qr.png`} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-100">
            Download QR
          </a>
        )}
      </div>
    </section>
  );
}

function AppLinksPage() {
  const { token } = useAuth();
  const [state, setState] = useState("loading");
  const [school, setSchool] = useState(null);
  const [qrs, setQrs] = useState({});
  const origin = window.location.origin;

  useEffect(() => {
    apiRequest("/auth/me", { token })
      .then((me) => {
        setSchool(me.school);
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [token]);

  useEffect(() => {
    if (!school) return;
    AUDIENCES.forEach((audience) => {
      QRCode.toDataURL(audience.link(origin, school.code), { width: 480, margin: 1, color: { dark: "#064e3b" } })
        .then((dataUrl) => setQrs((prev) => ({ ...prev, [audience.id]: dataUrl })))
        .catch(() => {});
    });
  }, [school, origin]);

  function printPosters() {
    const win = window.open("", "_blank");
    if (!win) return;
    const posters = AUDIENCES.map(
      (a) => `<section><h1>${escapeHtml(school.name)}</h1><h2>App for ${escapeHtml(a.title)}</h2><img src="${qrs[a.id]}" alt="">
        <ol><li>Scan this QR code with your phone camera.</li><li>Tap <b>Install</b> (iPhone: Share → Add to Home Screen).</li><li>${escapeHtml(a.how)}</li></ol>
        <p class="link">${escapeHtml(a.link(origin, school.code))}</p></section>`,
    ).join("");
    win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>App QR codes</title><style>
      body { font-family: system-ui, sans-serif; margin: 0; color: #0f172a; }
      section { page-break-after: always; text-align: center; padding: 48px 32px; }
      h1 { margin: 0; font-size: 28px; } h2 { color: #047857; margin: 8px 0 24px; } img { width: 320px; height: 320px; }
      ol { text-align: left; max-width: 420px; margin: 24px auto; font-size: 18px; line-height: 1.6; } .link { color: #64748b; font-size: 13px; word-break: break-all; }
    </style></head><body>${posters}<script>window.onload = () => window.print();</script></body></html>`);
    win.document.close();
  }

  if (state === "loading") return <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error" || !school) return <p className="text-sm font-semibold text-rose-700">Couldn&apos;t load your college&apos;s details.</p>;

  const ready = AUDIENCES.every((a) => qrs[a.id]);
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">App &amp; QR codes</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Share these so parents and teachers install the app on their phones — no Play Store needed. Scanning opens the right sign-in screen, then
            they tap Install (on iPhone: Share → Add to Home Screen).
          </p>
        </div>
        <button type="button" disabled={!ready} onClick={printPosters} className="self-start rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          Print QR posters
        </button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {AUDIENCES.map((audience) => (
          <AudienceCard key={audience.id} audience={audience} url={audience.link(origin, school.code)} qr={qrs[audience.id]} schoolName={school.name} />
        ))}
      </div>
    </div>
  );
}

export default AppLinksPage;

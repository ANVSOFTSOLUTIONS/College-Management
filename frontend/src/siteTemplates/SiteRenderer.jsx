import { useEffect, useState } from "react";

import { themeFor } from "./themes";

const API_ORIGIN = (import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1").replace(/\/api\/v1\/?$/, "");

// Uploaded college images are served by the API server.
export function assetUrl(url) {
  if (!url) return url;
  return url.startsWith("/uploads/") ? `${API_ORIGIN}${url}` : url;
}

const loadedFonts = new Set();
function useThemeFonts(theme) {
  useEffect(() => {
    const families = theme.fonts.google.filter((f) => !loadedFonts.has(f));
    if (!families.length) return;
    families.forEach((f) => loadedFonts.add(f));
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?${families.map((f) => `family=${f}`).join("&")}&display=swap`;
    document.head.appendChild(link);
  }, [theme]);
}

function formatDate(iso, opts = { day: "numeric", month: "short", year: "numeric" }) {
  return new Date(iso).toLocaleDateString("en-IN", opts);
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z]/.test(w))
    .map((w) => w[0])
    .slice(0, 3)
    .join("")
    .toUpperCase();
}

function loginLinks(site) {
  return [
    { label: "Parents", href: "/?as=parent" },
    { label: "Students", href: `/?as=student&school=${encodeURIComponent(site.code)}` },
    { label: "Staff", href: "/?as=staff" },
  ];
}

const NAV_LINKS = [
  { id: "about", label: "About" },
  { id: "events", label: "Events" },
  { id: "gallery", label: "Gallery" },
  { id: "notices", label: "Notices" },
  { id: "contact", label: "Contact" },
];

function visibleLinks(site) {
  return NAV_LINKS.filter(
    (l) =>
      (l.id === "about" && site.about) ||
      (l.id === "events" && site.activities.length) ||
      (l.id === "gallery" && site.gallery.length) ||
      (l.id === "notices" && site.notices.length) ||
      l.id === "contact",
  );
}

// --- Small building blocks ---------------------------------------------------------

function Emblem({ site, theme, size = "h-12 w-12", ring = true }) {
  if (site.logo_url) {
    return <img src={assetUrl(site.logo_url)} alt={`${site.name} logo`} className={`${size} rounded-full bg-white object-contain p-1`} />;
  }
  return (
    <span
      className={`${size} inline-flex shrink-0 items-center justify-center rounded-full text-sm font-bold`}
      style={{ background: theme.colors.primary, color: theme.colors.onPrimary, boxShadow: ring ? `0 0 0 3px ${theme.colors.accent}` : "none", fontFamily: "var(--font-heading)" }}
    >
      {initials(site.name)}
    </span>
  );
}

function Button({ href, children, variant = "primary", className = "" }) {
  const styles = {
    primary: { background: "var(--c-primary)", color: "var(--c-on-primary)" },
    accent: { background: "var(--c-accent)", color: "#111827" },
    ghost: { background: "transparent", color: "inherit", boxShadow: "inset 0 0 0 2px currentColor" },
    light: { background: "#ffffff", color: "#111827" },
  };
  return (
    <a href={href} style={styles[variant]} className={`inline-flex items-center justify-center rounded-[var(--radius-btn)] px-5 py-2.5 text-sm font-semibold transition hover:opacity-90 ${className}`}>
      {children}
    </a>
  );
}

function LoginMenu({ site, variant = "primary" }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={variant === "primary" ? { background: "var(--c-primary)", color: "var(--c-on-primary)" } : { background: "#fff", color: "#111827" }}
        className="rounded-[var(--radius-btn)] px-4 py-2 text-sm font-semibold"
      >
        Login ▾
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-44 overflow-hidden rounded-xl bg-white text-sm text-slate-800 shadow-xl ring-1 ring-black/5">
          {loginLinks(site).map((l) => (
            <a key={l.label} href={l.href} className="block px-4 py-2.5 hover:bg-slate-50">
              {l.label} login
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function MobileMenu({ site, dark }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="md:hidden">
      <button type="button" aria-label="Menu" onClick={() => setOpen(!open)} className={`rounded-lg p-2 ${dark ? "text-white" : ""}`}>
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>
      {open && (
        <div className="absolute inset-x-3 top-full z-40 mt-2 rounded-2xl bg-white p-3 text-slate-800 shadow-2xl">
          {visibleLinks(site).map((l) => (
            <a key={l.id} href={`#${l.id}`} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2 font-medium hover:bg-slate-50">
              {l.label}
            </a>
          ))}
          <div className="mt-2 grid grid-cols-3 gap-2 border-t pt-3">
            {loginLinks(site).map((l) => (
              <a key={l.label} href={l.href} className="rounded-lg bg-slate-100 px-2 py-2 text-center text-xs font-semibold">
                {l.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Links({ site, className = "", linkClass = "" }) {
  return (
    <nav className={`hidden items-center gap-6 text-sm font-medium md:flex ${className}`}>
      {visibleLinks(site).map((l) => (
        <a key={l.id} href={`#${l.id}`} className={`transition hover:opacity-70 ${linkClass}`}>
          {l.label}
        </a>
      ))}
    </nav>
  );
}

// --- Navigation variants -------------------------------------------------------------

function Nav({ site, theme }) {
  const name = <span style={{ fontFamily: "var(--font-heading)" }} className="text-lg font-bold leading-tight">{site.name}</span>;
  switch (theme.nav) {
    case "none":
      return null;
    case "transparent":
      return (
        <header className="absolute inset-x-0 top-0 z-30">
          <div className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-5 text-white">
            <a href="#top" className="flex items-center gap-3">
              <Emblem site={site} theme={theme} size="h-11 w-11" />
              {name}
            </a>
            <Links site={site} linkClass="text-white/90" />
            <div className="hidden md:block">
              <LoginMenu site={site} variant="light" />
            </div>
            <MobileMenu site={site} dark />
          </div>
        </header>
      );
    case "centered":
      return (
        <header style={{ background: "var(--c-surface)" }} className="relative border-b border-[var(--c-border)]">
          <div style={{ background: "var(--c-primary)", color: "var(--c-on-primary)" }} className="text-xs">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-5 py-2">
              <span>
                {site.contact.phone && `☎ ${site.contact.phone}`} {site.contact.email && ` · ✉ ${site.contact.email}`}
              </span>
              <span className="hidden gap-4 sm:flex">
                {loginLinks(site).map((l) => (
                  <a key={l.label} href={l.href} className="hover:underline">
                    {l.label} login
                  </a>
                ))}
              </span>
            </div>
          </div>
          <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-5 py-6 text-center">
            <Emblem site={site} theme={theme} size="h-16 w-16" />
            <p style={{ fontFamily: "var(--font-heading)", color: "var(--c-primary)" }} className="text-2xl font-bold sm:text-3xl">
              {site.name}
            </p>
            <div className="mt-2 flex w-full items-center justify-center">
              <Links site={site} className="gap-8 uppercase tracking-[0.18em] text-[12px]" />
              <div className="absolute right-4 top-14">
                <MobileMenu site={site} />
              </div>
            </div>
          </div>
        </header>
      );
    case "pill":
      return (
        <header className="sticky top-3 z-30 px-3">
          <div className="relative mx-auto flex max-w-5xl items-center justify-between rounded-full bg-white/95 px-4 py-2 shadow-lg ring-1 ring-black/5 backdrop-blur">
            <a href="#top" className="flex items-center gap-2">
              <Emblem site={site} theme={theme} size="h-10 w-10" ring={false} />
              {name}
            </a>
            <Links site={site} />
            <div className="hidden md:block">
              <LoginMenu site={site} />
            </div>
            <MobileMenu site={site} />
          </div>
        </header>
      );
    case "glass":
      return (
        <header className="sticky top-0 z-30 border-b border-white/10 bg-[rgba(11,16,32,0.7)] backdrop-blur">
          <div className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
            <a href="#top" className="flex items-center gap-3">
              <Emblem site={site} theme={theme} size="h-10 w-10" />
              {name}
            </a>
            <Links site={site} linkClass="text-slate-300" />
            <div className="hidden md:block">
              <LoginMenu site={site} />
            </div>
            <MobileMenu site={site} dark />
          </div>
        </header>
      );
    case "editorial":
      return (
        <header style={{ background: "var(--c-bg)" }} className="relative">
          <div className="mx-auto max-w-6xl px-5 pt-6">
            <div className="flex items-center justify-between border-b-2 border-[var(--c-text)] pb-2 text-xs uppercase tracking-[0.2em]">
              <span>{formatDate(new Date().toISOString(), { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</span>
              <span className="hidden gap-4 sm:flex">
                {loginLinks(site).map((l) => (
                  <a key={l.label} href={l.href} className="hover:underline">
                    {l.label}
                  </a>
                ))}
              </span>
              <MobileMenu site={site} />
            </div>
            <p style={{ fontFamily: "var(--font-heading)" }} className="py-4 text-center text-4xl leading-none sm:text-6xl">
              {site.name}
            </p>
            <div className="flex justify-center border-y border-[var(--c-text)] py-2">
              <Links site={site} className="gap-8 text-xs uppercase tracking-[0.25em]" />
            </div>
          </div>
        </header>
      );
    default:
      return (
        <header style={{ background: "var(--c-surface)" }} className="sticky top-0 z-30 border-b border-[var(--c-border)]">
          <div className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
            <a href="#top" className="flex items-center gap-3">
              <Emblem site={site} theme={theme} size="h-10 w-10" ring={false} />
              {name}
            </a>
            <Links site={site} />
            <div className="hidden md:block">
              <LoginMenu site={site} />
            </div>
            <MobileMenu site={site} />
          </div>
        </header>
      );
  }
}

// --- Hero variants --------------------------------------------------------------------

function useSlides(count, ms = 5500) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (count < 2) return undefined;
    const timer = setInterval(() => setIndex((i) => (i + 1) % count), ms);
    return () => clearInterval(timer);
  }, [count, ms]);
  return [index, setIndex];
}

function FallbackArt({ theme, className = "" }) {
  // Used when a college hasn't uploaded banners yet.
  return (
    <div
      className={className}
      style={{
        background: `radial-gradient(circle at 20% 20%, ${theme.colors.accent}55, transparent 45%), radial-gradient(circle at 80% 70%, ${theme.colors.primary}aa, transparent 50%), linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.accent})`,
      }}
    />
  );
}

function heroCopy(site) {
  const first = site.banners[0]?.caption;
  return first || site.tagline || (site.about ? site.about.split(/\n|\. /)[0] : "Welcome to our college.");
}

function Hero({ site, theme }) {
  const banners = site.banners.map((b) => ({ ...b, url: assetUrl(b.url) }));
  const [index, setIndex] = useSlides(banners.length);
  const primaryCta = <Button href="#contact">Contact us</Button>;
  const parentCta = (variant = "ghost") => (
    <Button href="/?as=parent" variant={variant}>
      Parent login
    </Button>
  );

  switch (theme.hero) {
    case "slider":
    case "fullbleed": {
      const tall = theme.hero === "fullbleed" ? "min-h-[88vh]" : "min-h-[72vh]";
      return (
        <section id="top" className={`relative flex ${tall} items-end overflow-hidden text-white`}>
          {banners.length ? (
            banners.map((b, i) => (
              <img key={b.id} src={b.url} alt="" className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-1000 ${i === index ? "opacity-100" : "opacity-0"}`} />
            ))
          ) : (
            <FallbackArt theme={theme} className="absolute inset-0" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/30 to-black/10" />
          <div className="relative mx-auto w-full max-w-6xl px-5 pb-16 pt-40">
            <p className="mb-3 inline-block rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest" style={{ background: "var(--c-accent)", color: "#111827" }}>
              Welcome to {site.name}
            </p>
            <h1 style={{ fontFamily: "var(--font-heading)" }} className="max-w-3xl text-4xl font-bold leading-tight sm:text-6xl">
              {banners[index]?.caption || heroCopy(site)}
            </h1>
            <div className="mt-8 flex flex-wrap gap-3">
              {primaryCta}
              {parentCta("light")}
            </div>
            {banners.length > 1 && (
              <div className="mt-8 flex gap-2">
                {banners.map((b, i) => (
                  <button key={b.id} type="button" aria-label={`Slide ${i + 1}`} onClick={() => setIndex(i)} className={`h-1.5 rounded-full transition-all ${i === index ? "w-10 bg-white" : "w-4 bg-white/50"}`} />
                ))}
              </div>
            )}
          </div>
          {theme.decoration === "waves" && <Wave color="var(--c-bg)" />}
        </section>
      );
    }
    case "split":
      return (
        <section id="top" className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em]" style={{ color: "var(--c-accent)" }}>
              Welcome to
            </p>
            <h1 style={{ fontFamily: "var(--font-heading)" }} className="mt-3 text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              {site.name}
            </h1>
            <p className="mt-6 max-w-lg text-lg text-[var(--c-muted)]">{heroCopy(site)}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              {primaryCta}
              {parentCta()}
            </div>
          </div>
          <div className="relative">
            <div className="absolute -bottom-5 -right-5 h-full w-full rounded-[2rem]" style={{ background: "var(--c-accent)" }} />
            {banners[0] ? (
              <img src={banners[0].url} alt="" className="relative aspect-[4/3] w-full rounded-[2rem] object-cover shadow-2xl" />
            ) : (
              <FallbackArt theme={theme} className="relative aspect-[4/3] w-full rounded-[2rem]" />
            )}
          </div>
        </section>
      );
    case "centered":
      return (
        <section id="top" className="relative overflow-hidden text-center" style={{ background: "var(--c-primary)", color: "var(--c-on-primary)" }}>
          <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(currentColor 1px, transparent 1px)", backgroundSize: "18px 18px" }} />
          <div className={`relative mx-auto max-w-4xl px-5 pb-10 ${theme.nav === "transparent" ? "pt-32" : "pt-16"}`}>
            <div className="mb-6 flex justify-center">
              <Emblem site={site} theme={theme} size="h-24 w-24" />
            </div>
            <p className="text-xs uppercase tracking-[0.35em]" style={{ color: "var(--c-accent)" }}>
              ✦ Est. with pride ✦
            </p>
            <h1 style={{ fontFamily: "var(--font-heading)" }} className="mt-4 text-4xl font-bold sm:text-6xl">
              {site.name}
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg opacity-90">{heroCopy(site)}</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button href="#contact" variant="accent">
                Contact us
              </Button>
              {parentCta()}
            </div>
          </div>
          {banners[0] && (
            <div className="relative mx-auto max-w-5xl px-5">
              <img src={banners[0].url} alt="" className="aspect-[21/8] w-full translate-y-10 rounded-t-3xl object-cover shadow-2xl ring-4 ring-[var(--c-accent)]" />
            </div>
          )}
        </section>
      );
    case "gradient":
      return (
        <section id="top" className="relative overflow-hidden" style={{ background: theme.dark ? "var(--c-bg)" : `linear-gradient(120deg, ${theme.colors.primary}, ${theme.colors.accent})`, color: theme.dark ? "var(--c-text)" : "#fff" }}>
          {theme.dark && (
            <>
              <div className="absolute -left-20 top-10 h-72 w-72 rounded-full blur-3xl" style={{ background: `${theme.colors.accent}55` }} />
              <div className="absolute right-0 top-40 h-80 w-80 rounded-full blur-3xl" style={{ background: `${theme.colors.primary}44` }} />
              <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "44px 44px" }} />
            </>
          )}
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-32 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <h1 style={{ fontFamily: "var(--font-heading)" }} className="text-5xl font-bold leading-[1.05] sm:text-7xl">
                {theme.dark ? (
                  <span className="bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(90deg, ${theme.colors.primary}, ${theme.colors.accent})` }}>
                    {site.name}
                  </span>
                ) : (
                  site.name
                )}
              </h1>
              <p className="mt-6 max-w-xl text-lg opacity-90">{heroCopy(site)}</p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Button href="#contact" variant={theme.dark ? "primary" : "light"}>
                  Contact us
                </Button>
                {parentCta()}
              </div>
            </div>
            <div className="relative lg:col-span-2">
              {banners[0] ? (
                <img src={banners[0].url} alt="" className="aspect-[4/5] w-full rotate-2 rounded-3xl object-cover shadow-2xl ring-1 ring-white/20" style={theme.dark ? { boxShadow: `0 30px 80px -20px ${theme.colors.accent}` } : undefined} />
              ) : (
                <FallbackArt theme={theme} className="aspect-[4/5] w-full rotate-2 rounded-3xl" />
              )}
            </div>
          </div>
          {theme.decoration === "waves" && <Wave color="var(--c-bg)" />}
        </section>
      );
    case "playful":
      return (
        <section id="top" className="relative overflow-hidden px-5 pb-16 pt-10">
          <div className="absolute -left-16 top-24 h-64 w-64 rounded-full opacity-30" style={{ background: "var(--c-accent)" }} />
          <div className="absolute -right-10 top-0 h-72 w-72 rounded-full opacity-25" style={{ background: "var(--c-primary)" }} />
          <div className="absolute bottom-10 left-1/2 h-10 w-10 rotate-12 rounded-xl" style={{ background: "#facc15" }} />
          <div className="relative mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-2">
            <div>
              <p className="inline-block -rotate-2 rounded-2xl px-4 py-1 text-sm font-bold text-white" style={{ background: "var(--c-accent)" }}>
                Hello, little learners! ☺
              </p>
              <h1 style={{ fontFamily: "var(--font-heading)", color: "var(--c-primary)" }} className="mt-4 text-5xl font-extrabold leading-tight sm:text-6xl">
                {site.name}
              </h1>
              <p className="mt-4 max-w-md text-lg text-[var(--c-muted)]">{heroCopy(site)}</p>
              <div className="mt-8 flex flex-wrap gap-3">
                {primaryCta}
                <Button href="/?as=parent" variant="accent">
                  Parent login
                </Button>
              </div>
            </div>
            <div className="relative">
              {banners[0] ? (
                <img src={banners[0].url} alt="" className="aspect-square w-full object-cover shadow-xl" style={{ borderRadius: "58% 42% 38% 62% / 45% 55% 45% 55%", border: "10px solid #fff" }} />
              ) : (
                <FallbackArt theme={theme} className="aspect-square w-full" />
              )}
              <div className="absolute -bottom-3 left-6 rounded-2xl bg-white px-4 py-2 text-sm font-bold shadow-lg" style={{ color: "var(--c-primary)" }}>
                ★ Learning is fun here
              </div>
            </div>
          </div>
        </section>
      );
    case "editorial": {
      const [main, ...rest] = banners;
      return (
        <section id="top" className="mx-auto max-w-6xl px-5 py-10">
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              {main ? <img src={main.url} alt="" className="aspect-[16/10] w-full object-cover" /> : <FallbackArt theme={theme} className="aspect-[16/10] w-full" />}
              <h1 style={{ fontFamily: "var(--font-heading)" }} className="mt-5 text-4xl leading-tight sm:text-5xl">
                {heroCopy(site)}
              </h1>
            </div>
            <div className="space-y-6 border-t border-[var(--c-border)] pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
              {rest.slice(0, 2).map((b) => (
                <figure key={b.id}>
                  <img src={b.url} alt="" className="aspect-[4/3] w-full object-cover" />
                  <figcaption style={{ fontFamily: "var(--font-heading)" }} className="mt-2 text-xl leading-snug">
                    {b.caption}
                  </figcaption>
                </figure>
              ))}
              <div className="flex flex-wrap gap-3">
                {primaryCta}
                {parentCta()}
              </div>
            </div>
          </div>
        </section>
      );
    }
    case "sidebar":
      return (
        <section id="top" className="relative">
          {banners[0] ? <img src={banners[0].url} alt="" className="aspect-[16/9] w-full object-cover" /> : <FallbackArt theme={theme} className="aspect-[16/9] w-full" />}
          <div className="relative -mt-20 mx-6 bg-[var(--c-surface)] p-8 shadow-xl" style={{ borderLeft: "8px solid var(--c-accent)" }}>
            <h1 style={{ fontFamily: "var(--font-heading)" }} className="text-3xl font-extrabold sm:text-4xl">
              {heroCopy(site)}
            </h1>
          </div>
        </section>
      );
    default:
      return null;
  }
}

function Wave({ color }) {
  return (
    <svg className="absolute bottom-0 left-0 w-full" viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true" style={{ height: 60 }}>
      <path fill={color} d="M0,64 C240,96 480,16 720,32 C960,48 1200,96 1440,56 L1440,90 L0,90 Z" />
    </svg>
  );
}

// --- Sections ---------------------------------------------------------------------------

function SectionTitle({ theme, eyebrow, children, number }) {
  const heading = { fontFamily: "var(--font-heading)" };
  switch (theme.titles) {
    case "ornament":
      return (
        <div className="mb-10 text-center">
          <h2 style={{ ...heading, color: "var(--c-primary)" }} className="text-3xl font-bold sm:text-4xl">
            {children}
          </h2>
          <div className="mt-3 flex items-center justify-center gap-3" style={{ color: "var(--c-accent)" }}>
            <span className="h-px w-12 bg-current" />◆<span className="h-px w-12 bg-current" />
          </div>
        </div>
      );
    case "eyebrow":
      return (
        <div className="mb-10">
          <p className="text-xs font-bold uppercase tracking-[0.25em]" style={{ color: "var(--c-accent)" }}>
            {eyebrow}
          </p>
          <h2 style={heading} className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">
            {children}
          </h2>
        </div>
      );
    case "wiggle":
      return (
        <div className="mb-10 text-center">
          <h2 style={{ ...heading, color: "var(--c-primary)" }} className="inline-block text-4xl font-extrabold">
            {children}
            <svg viewBox="0 0 200 12" className="mt-1 h-3 w-full" aria-hidden="true">
              <path d="M2 8 Q 25 0 50 8 T 100 8 T 150 8 T 198 8" fill="none" stroke="var(--c-accent)" strokeWidth="4" strokeLinecap="round" />
            </svg>
          </h2>
        </div>
      );
    case "numbered":
      return (
        <div className="mb-10 flex items-baseline gap-4">
          <span className="font-mono text-sm font-bold" style={{ color: "var(--c-accent)" }}>
            {String(number).padStart(2, "0")} /
          </span>
          <h2 style={heading} className="text-3xl font-bold sm:text-4xl">
            {children}
          </h2>
        </div>
      );
    case "rule":
      return (
        <div className="mb-8 flex items-center gap-4">
          <h2 style={heading} className="shrink-0 text-3xl sm:text-4xl">
            {children}
          </h2>
          <span className="h-px flex-1 bg-[var(--c-text)] opacity-30" />
          <span className="text-xs uppercase tracking-[0.25em] text-[var(--c-muted)]">{eyebrow}</span>
        </div>
      );
    default:
      return (
        <div className="mb-10">
          <h2 style={{ ...heading, color: "var(--c-primary)" }} className="text-3xl font-bold sm:text-4xl">
            {children}
          </h2>
          <span className="mt-3 block h-1.5 w-16 rounded-full" style={{ background: "var(--c-accent)" }} />
        </div>
      );
  }
}

function cardClass(theme) {
  return {
    classic: "bg-[var(--c-surface)] border border-[var(--c-border)] rounded-md shadow-sm",
    flat: "bg-[var(--c-surface)] rounded-xl",
    bubbly: "bg-[var(--c-surface)] rounded-[2rem] shadow-md ring-4 ring-[var(--c-border)]",
    soft: "bg-[var(--c-surface)] rounded-2xl shadow-[0_10px_30px_-12px_rgba(0,0,0,0.18)]",
    glass: "bg-white/5 rounded-2xl ring-1 ring-white/10 backdrop-blur",
    sharp: "bg-[var(--c-surface)] border-2 border-[var(--c-text)]",
  }[theme.cards];
}

function NoticesTicker({ site }) {
  if (!site.notices.length) return null;
  const items = [...site.notices, ...site.notices];
  return (
    <div className="overflow-hidden border-y border-[var(--c-border)]" style={{ background: "var(--c-surface)" }}>
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-3 text-sm">
        <span className="shrink-0 rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wider" style={{ background: "var(--c-accent)", color: "#111827" }}>
          Latest
        </span>
        <div className="relative flex-1 overflow-hidden">
          <div className="flex w-max gap-12 whitespace-nowrap [animation:site-marquee_35s_linear_infinite] hover:[animation-play-state:paused]">
            {items.map((n, i) => (
              <span key={`${n.id}-${i}`}>
                <span className="text-[var(--c-muted)]">{formatDate(n.date, { day: "numeric", month: "short" })}</span> · {n.title}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function About({ site, theme, n }) {
  if (!site.about) return null;
  return (
    <section id="about" className="mx-auto max-w-6xl px-5 py-20">
      <SectionTitle theme={theme} eyebrow="Who we are" number={n}>
        About {site.name}
      </SectionTitle>
      <div className="grid gap-10 lg:grid-cols-3">
        <div className="space-y-4 text-lg leading-relaxed lg:col-span-2">
          {site.about.split(/\n+/).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
        <div className={`${cardClass(theme)} p-6`}>
          <p style={{ fontFamily: "var(--font-heading)" }} className="text-xl font-bold">
            Quick links
          </p>
          <ul className="mt-4 space-y-3 text-sm">
            {loginLinks(site).map((l) => (
              <li key={l.label}>
                <a href={l.href} className="flex items-center justify-between rounded-lg px-3 py-2 font-semibold transition hover:opacity-80" style={{ background: "color-mix(in srgb, var(--c-primary) 10%, transparent)" }}>
                  {l.label} login <span aria-hidden="true">→</span>
                </a>
              </li>
            ))}
            <li>
              <a href="#contact" className="flex items-center justify-between rounded-lg px-3 py-2 font-semibold transition hover:opacity-80" style={{ background: "color-mix(in srgb, var(--c-accent) 18%, transparent)" }}>
                Visit / contact us <span aria-hidden="true">→</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

function Events({ site, theme, n }) {
  if (!site.activities.length) return null;
  return (
    <section id="events" style={{ background: theme.dark ? "transparent" : "var(--c-surface)" }} className="py-20">
      <div className="mx-auto max-w-6xl px-5">
        <SectionTitle theme={theme} eyebrow="What's happening" number={n}>
          Events & activities
        </SectionTitle>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {site.activities.slice(0, 6).map((a) => (
            <article key={a.id} className={`${cardClass(theme)} flex gap-4 p-6`}>
              <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-[var(--radius-btn)] text-center" style={{ background: "var(--c-primary)", color: "var(--c-on-primary)" }}>
                <span className="text-2xl font-bold leading-none">{formatDate(a.date, { day: "numeric" })}</span>
                <span className="text-[11px] uppercase tracking-wider">{formatDate(a.date, { month: "short" })}</span>
              </div>
              <div>
                <h3 style={{ fontFamily: "var(--font-heading)" }} className="text-lg font-bold leading-snug">
                  {a.title}
                </h3>
                {a.description && <p className="mt-1 text-sm text-[var(--c-muted)]">{a.description}</p>}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function Gallery({ site, theme, n }) {
  const [open, setOpen] = useState(null);
  if (!site.gallery.length) return null;
  const images = site.gallery.map((g) => ({ ...g, url: assetUrl(g.url) }));
  const layouts = {
    grid: "grid grid-cols-2 gap-3 md:grid-cols-3",
    masonry: "columns-2 gap-3 md:columns-3 [&>*]:mb-3",
    polaroid: "grid grid-cols-2 gap-6 md:grid-cols-3",
    framed: "grid grid-cols-2 gap-5 md:grid-cols-3",
  };
  return (
    <section id="gallery" className="mx-auto max-w-6xl px-5 py-20">
      <SectionTitle theme={theme} eyebrow="Moments" number={n}>
        Gallery
      </SectionTitle>
      <div className={layouts[theme.gallery]}>
        {images.map((g, i) => {
          const tilt = theme.gallery === "polaroid" ? (i % 2 ? "rotate-2" : "-rotate-2") : "";
          const frame =
            theme.gallery === "polaroid"
              ? "bg-white p-3 pb-8 shadow-lg"
              : theme.gallery === "framed"
                ? "bg-[var(--c-surface)] p-2 ring-2 ring-[var(--c-accent)]"
                : "overflow-hidden rounded-[var(--radius-card)]";
          return (
            <button key={g.id} type="button" onClick={() => setOpen(g)} className={`group relative block w-full break-inside-avoid text-left transition hover:-translate-y-1 ${tilt} ${frame}`}>
              <img
                src={g.url}
                alt={g.caption || ""}
                loading="lazy"
                className={`w-full object-cover transition duration-500 group-hover:scale-105 ${theme.gallery === "masonry" ? "" : "aspect-square"}`}
              />
              {g.caption && (theme.gallery === "polaroid" ? <span className="mt-2 block text-center text-sm text-slate-600">{g.caption}</span> : null)}
            </button>
          );
        })}
      </div>
      {open && (
        <button type="button" onClick={() => setOpen(null)} className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-6" aria-label="Close">
          <figure className="max-h-full max-w-4xl">
            <img src={open.url} alt={open.caption || ""} className="max-h-[80vh] rounded-lg object-contain" />
            {open.caption && <figcaption className="mt-3 text-center text-white">{open.caption}</figcaption>}
          </figure>
        </button>
      )}
    </section>
  );
}

function Notices({ site, theme, n }) {
  if (!site.notices.length) return null;
  return (
    <section id="notices" className="mx-auto max-w-6xl px-5 py-20">
      <SectionTitle theme={theme} eyebrow="Notice board" number={n}>
        Notices
      </SectionTitle>
      <ul className={`${cardClass(theme)} divide-y divide-[var(--c-border)]`}>
        {site.notices.slice(0, 8).map((notice) => (
          <li key={notice.id} className="flex items-center gap-4 px-6 py-4">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: "var(--c-accent)" }} />
            <span className="flex-1 font-medium">{notice.title}</span>
            <span className="shrink-0 text-sm text-[var(--c-muted)]">{formatDate(notice.date)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Contact({ site, theme, n }) {
  const { address, phone, email, map_url: mapUrl } = site.contact;
  const embed = mapUrl && mapUrl.startsWith("https://www.google.com/maps/embed");
  const items = [
    address && { icon: "📍", label: "Address", value: address },
    phone && { icon: "📞", label: "Phone", value: phone, href: `tel:${phone.replace(/\s/g, "")}` },
    email && { icon: "✉️", label: "Email", value: email, href: `mailto:${email}` },
  ].filter(Boolean);
  return (
    <section id="contact" style={{ background: theme.dark ? "transparent" : "var(--c-surface)" }} className="py-20">
      <div className="mx-auto max-w-6xl px-5">
        <SectionTitle theme={theme} eyebrow="Get in touch" number={n}>
          Contact us
        </SectionTitle>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            {items.length ? (
              items.map((item) => (
                <div key={item.label} className={`${cardClass(theme)} flex items-start gap-4 p-5`}>
                  <span className="text-2xl" aria-hidden="true">
                    {item.icon}
                  </span>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-[var(--c-muted)]">{item.label}</p>
                    {item.href ? (
                      <a href={item.href} className="font-semibold hover:underline">
                        {item.value}
                      </a>
                    ) : (
                      <p className="font-semibold">{item.value}</p>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-[var(--c-muted)]">Contact details coming soon.</p>
            )}
            {mapUrl && !embed && (
              <Button href={mapUrl} variant="primary">
                Open in Google Maps
              </Button>
            )}
          </div>
          {embed ? (
            <iframe title="Map" src={mapUrl} className="h-80 w-full rounded-[var(--radius-card)] border-0" loading="lazy" referrerPolicy="no-referrer-when-downgrade" />
          ) : (
            <div className="flex h-80 flex-col items-center justify-center rounded-[var(--radius-card)] p-8 text-center" style={{ background: `linear-gradient(135deg, ${theme.colors.primary}, ${theme.colors.accent})`, color: "#fff" }}>
              <Emblem site={site} theme={theme} size="h-20 w-20" />
              <p style={{ fontFamily: "var(--font-heading)" }} className="mt-4 text-2xl font-bold">
                Visit {site.name}
              </p>
              <p className="mt-2 opacity-90">We&apos;d love to show you around.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function Footer({ site, theme }) {
  return (
    <footer style={{ background: theme.dark ? "#060913" : "var(--c-primary)", color: theme.dark ? "var(--c-muted)" : "var(--c-on-primary)" }}>
      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-12 sm:grid-cols-3">
        <div>
          <div className="flex items-center gap-3">
            <Emblem site={site} theme={theme} size="h-10 w-10" />
            <span style={{ fontFamily: "var(--font-heading)" }} className="text-lg font-bold">
              {site.name}
            </span>
          </div>
          {site.contact.address && <p className="mt-3 text-sm opacity-80">{site.contact.address}</p>}
        </div>
        <div className="text-sm">
          <p className="mb-2 font-semibold uppercase tracking-wider opacity-70">Explore</p>
          {visibleLinks(site).map((l) => (
            <a key={l.id} href={`#${l.id}`} className="block py-0.5 opacity-90 hover:opacity-100 hover:underline">
              {l.label}
            </a>
          ))}
        </div>
        <div className="text-sm">
          <p className="mb-2 font-semibold uppercase tracking-wider opacity-70">Login</p>
          {loginLinks(site).map((l) => (
            <a key={l.label} href={l.href} className="block py-0.5 opacity-90 hover:opacity-100 hover:underline">
              {l.label}
            </a>
          ))}
        </div>
      </div>
      <p className="border-t border-white/15 py-4 text-center text-xs opacity-70">
        © {new Date().getFullYear()} {site.name} · Powered by ANV College ERP · Developed by ANV Soft Solutions Pvt Ltd · 🔒 Secure
      </p>
    </footer>
  );
}

const RADIUS = { classic: "6px", flat: "12px", bubbly: "28px", soft: "18px", glass: "18px", sharp: "0px" };

// Readable text on a college's own colour: dark text on light colours, white on dark ones.
function textOn(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b) > 0.4 ? "#111827" : "#ffffff";
}

// The college admin's touches on top of the template: own colours.
function customise(theme, site) {
  if (!site.primary_color && !site.accent_color) return theme;
  const colors = { ...theme.colors };
  if (site.primary_color) Object.assign(colors, { primary: site.primary_color, onPrimary: textOn(site.primary_color) });
  if (site.accent_color) colors.accent = site.accent_color;
  return { ...theme, colors };
}

function SiteRenderer({ site: rawSite, templateId }) {
  // Sections the admin chose to hide render as if they were empty.
  const hidden = new Set(rawSite.hidden_sections ?? []);
  const site = {
    ...rawSite,
    about: hidden.has("about") ? "" : rawSite.about,
    activities: hidden.has("events") ? [] : rawSite.activities,
    gallery: hidden.has("gallery") ? [] : rawSite.gallery,
    notices: hidden.has("notices") ? [] : rawSite.notices,
  };
  const theme = customise(themeFor(templateId), rawSite);
  useThemeFonts(theme);
  const c = theme.colors;
  const style = {
    "--c-primary": c.primary,
    "--c-on-primary": c.onPrimary,
    "--c-accent": c.accent,
    "--c-bg": c.bg,
    "--c-surface": c.surface,
    "--c-text": c.text,
    "--c-muted": c.muted,
    "--c-border": c.border,
    "--font-heading": theme.fonts.heading,
    "--radius-card": RADIUS[theme.cards],
    "--radius-btn": theme.cards === "sharp" ? "0px" : theme.cards === "bubbly" ? "999px" : "10px",
    background: c.bg,
    color: c.text,
    fontFamily: theme.fonts.body,
  };
  const numbered = [site.about, site.activities.length, site.gallery.length, site.notices.length, true];
  let counter = 0;
  const n = (present) => (present ? ++counter : counter);
  const sections = (
    <>
      <NoticesTicker site={site} />
      <About site={site} theme={theme} n={n(numbered[0])} />
      <Events site={site} theme={theme} n={n(numbered[1])} />
      <Gallery site={site} theme={theme} n={n(numbered[2])} />
      <Notices site={site} theme={theme} n={n(numbered[3])} />
      <Contact site={site} theme={theme} n={n(numbered[4])} />
      <Footer site={site} theme={theme} />
    </>
  );
  const dots = theme.decoration === "dots" ? { backgroundImage: `radial-gradient(${c.border} 1.2px, transparent 1.2px)`, backgroundSize: "22px 22px" } : {};

  return (
    <div style={{ ...style, ...dots }} className="min-h-screen overflow-x-clip antialiased">
      {site.admissions_open && (
        <a
          href={`/apply/${encodeURIComponent(site.code)}`}
          style={{ background: "var(--c-primary)", color: "var(--c-on-primary)", borderRadius: "999px" }}
          className="fixed bottom-5 right-5 z-40 px-5 py-3 text-sm font-bold shadow-xl ring-4 ring-white/60 transition hover:scale-105"
        >
          🎓 Apply for admission
        </a>
      )}
      <style>{"@keyframes site-marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } } @media (prefers-reduced-motion: reduce) { [class*='site-marquee'] { animation: none !important; } }"}</style>
      {theme.hero === "sidebar" ? (
        <div className="lg:flex">
          <aside className="flex flex-col gap-6 p-8 lg:sticky lg:top-0 lg:h-screen lg:w-80 lg:shrink-0" style={{ background: "var(--c-primary)", color: "var(--c-on-primary)" }}>
            <Emblem site={site} theme={theme} size="h-16 w-16" />
            <p style={{ fontFamily: "var(--font-heading)" }} className="text-3xl font-extrabold leading-tight">
              {site.name}
            </p>
            <nav className="flex flex-wrap gap-x-4 gap-y-2 text-sm font-semibold lg:flex-col">
              {visibleLinks(site).map((l) => (
                <a key={l.id} href={`#${l.id}`} className="opacity-90 hover:opacity-100 hover:underline">
                  {l.label}
                </a>
              ))}
            </nav>
            <div className="mt-auto space-y-2">
              {loginLinks(site).map((l) => (
                <a key={l.label} href={l.href} className="block px-4 py-2 text-center text-sm font-bold" style={{ background: "var(--c-accent)", color: "#111827" }}>
                  {l.label} login
                </a>
              ))}
            </div>
          </aside>
          <main className="min-w-0 flex-1">
            <Hero site={site} theme={theme} />
            {sections}
          </main>
        </div>
      ) : (
        <div className="relative">
          <Nav site={site} theme={theme} />
          <Hero site={site} theme={theme} />
          {theme.hero === "centered" && <div className="h-10" />}
          {sections}
        </div>
      )}
    </div>
  );
}

export default SiteRenderer;

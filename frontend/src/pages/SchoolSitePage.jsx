import { useCallback, useEffect, useRef, useState } from "react";

import {
  addActivity,
  addNotice,
  chooseTemplate,
  customizeSite,
  saveCollegeInfo,
  deleteActivity,
  deleteBanner,
  deleteGalleryImage,
  deleteNotice,
  fetchMySite,
  saveAboutContact,
  uploadBanner,
  uploadGalleryImage,
  uploadLogo,
} from "../api/schoolSiteApi";
import SiteRenderer, { assetUrl } from "../siteTemplates/SiteRenderer";
import { SAMPLE_SITE } from "../siteTemplates/sampleSite";
import { FREE_TEMPLATES, THEMES, themeFor } from "../siteTemplates/themes";
import { useAuth } from "../context/AuthContext";
import { ApiError, apiRequest } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

// A live, scaled-down render of the template (1280px wide shown at 25%).
function TemplateThumbnail({ site, templateId }) {
  return (
    <div className="relative h-52 overflow-hidden rounded-t-xl bg-slate-100" aria-hidden="true">
      <div className="pointer-events-none absolute left-0 top-0 w-[1280px] origin-top-left scale-[0.25] select-none" style={{ height: 832 }}>
        <SiteRenderer site={site} templateId={templateId} />
      </div>
    </div>
  );
}

const SECTIONS = [
  ["highlights", "Highlights"],
  ["about", "About"],
  ["principal", "Principal's message"],
  ["programs", "Programs & departments"],
  ["placements", "Placements"],
  ["events", "Campus life"],
  ["gallery", "Gallery"],
  ["notices", "Notices"],
];

const EMPTY_PROGRAM = { name: "", level: "UG", duration: "", seats: "", description: "" };

// Year established, accreditation, highlight figures, programs offered and the principal's message.
function CollegeInfoCard({ token, site, onChanged }) {
  const [form, setForm] = useState(() => ({
    established: site.established ?? "",
    accreditation: site.accreditation ?? "",
    highlights: site.highlights?.length ? site.highlights : [{ value: "", label: "" }],
    programs: site.programs ?? [],
    principal_name: site.principal_name ?? "",
    principal_title: site.principal_title ?? "Principal",
    principal_message: site.principal_message ?? "",
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const setList = (key, index, field, value) =>
    setForm({ ...form, [key]: form[key].map((item, i) => (i === index ? { ...item, [field]: value } : item)) });
  const removeAt = (key, index) => setForm({ ...form, [key]: form[key].filter((_, i) => i !== index) });

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        ...form,
        highlights: form.highlights.filter((h) => h.value.trim() && h.label.trim()),
        programs: form.programs.filter((pr) => pr.name.trim()),
      };
      onChanged(await saveCollegeInfo(token, body), "College details saved.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the college details."));
    } finally {
      setSaving(false);
    }
  }

  const small = "rounded-lg border border-slate-300 px-3 py-2 text-sm";
  return (
    <Card title="College details" hint="Shown across every template: the accreditation strip, highlight figures, programs and the principal's message.">
      <div className="grid gap-3 sm:grid-cols-4">
        <label className="text-sm font-medium text-slate-700">
          Established
          <input value={form.established} maxLength={10} placeholder="1998" onChange={(e) => setForm({ ...form, established: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-3">
          Accreditation & affiliation
          <input
            value={form.accreditation}
            maxLength={300}
            placeholder="NAAC A+ | AICTE approved | Affiliated to JNTUA"
            onChange={(e) => setForm({ ...form, accreditation: e.target.value })}
            className={INPUT}
          />
        </label>
      </div>

      <div>
        <p className="text-sm font-medium text-slate-700">Highlight figures (up to 6)</p>
        <div className="mt-1 space-y-2">
          {form.highlights.map((h, i) => (
            <div key={i} className="flex gap-2">
              <input aria-label="Figure" placeholder="92%" maxLength={20} value={h.value} onChange={(e) => setList("highlights", i, "value", e.target.value)} className={`${small} w-28`} />
              <input aria-label="Label" placeholder="Placement record" maxLength={60} value={h.label} onChange={(e) => setList("highlights", i, "label", e.target.value)} className={`${small} flex-1`} />
              <button type="button" onClick={() => removeAt("highlights", i)} className="px-2 text-slate-400 hover:text-rose-600" aria-label="Remove">
                ×
              </button>
            </div>
          ))}
        </div>
        {form.highlights.length < 6 && (
          <button type="button" onClick={() => setForm({ ...form, highlights: [...form.highlights, { value: "", label: "" }] })} className="mt-2 text-sm font-semibold text-emerald-700">
            + Add figure
          </button>
        )}
      </div>

      <div>
        <p className="text-sm font-medium text-slate-700">Programs offered</p>
        <p className="text-xs text-slate-400">Your departments show automatically; list the courses you want to advertise here.</p>
        <div className="mt-2 space-y-3">
          {form.programs.map((pr, i) => (
            <div key={i} className="grid gap-2 rounded-lg border border-slate-200 p-3 sm:grid-cols-6">
              <input aria-label="Program name" placeholder="B.Tech Computer Science" maxLength={120} value={pr.name} onChange={(e) => setList("programs", i, "name", e.target.value)} className={`${small} sm:col-span-3`} />
              <select aria-label="Level" value={pr.level} onChange={(e) => setList("programs", i, "level", e.target.value)} className={small}>
                {["UG", "PG", "Diploma", "Ph.D", "Certificate", "Intermediate"].map((l) => (
                  <option key={l}>{l}</option>
                ))}
              </select>
              <input aria-label="Duration" placeholder="4 years" maxLength={40} value={pr.duration} onChange={(e) => setList("programs", i, "duration", e.target.value)} className={small} />
              <input aria-label="Seats" placeholder="Seats" maxLength={20} value={pr.seats} onChange={(e) => setList("programs", i, "seats", e.target.value)} className={small} />
              <input
                aria-label="Description"
                placeholder="One line about the program"
                maxLength={400}
                value={pr.description}
                onChange={(e) => setList("programs", i, "description", e.target.value)}
                className={`${small} sm:col-span-5`}
              />
              <button type="button" onClick={() => removeAt("programs", i)} className="text-sm font-semibold text-rose-600">
                Remove
              </button>
            </div>
          ))}
        </div>
        <button type="button" onClick={() => setForm({ ...form, programs: [...form.programs, { ...EMPTY_PROGRAM }] })} className="mt-2 text-sm font-semibold text-emerald-700">
          + Add program
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">
          Principal / Director name
          <input value={form.principal_name} maxLength={150} onChange={(e) => setForm({ ...form, principal_name: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Title
          <input value={form.principal_title} maxLength={100} placeholder="Principal" onChange={(e) => setForm({ ...form, principal_title: e.target.value })} className={INPUT} />
        </label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2">
          Message
          <textarea rows={4} maxLength={3000} value={form.principal_message} onChange={(e) => setForm({ ...form, principal_message: e.target.value })} className={INPUT} />
        </label>
      </div>
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      <button type="button" disabled={saving} onClick={save} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
        {saving ? "Saving…" : "Save college details"}
      </button>
    </Card>
  );
}

// Tagline, own colours on top of the template, and which sections show. Previewed live.
function CustomizeCard({ token, site, previewSite, onChanged }) {
  const theme = themeFor(site.template);
  const [form, setForm] = useState({
    tagline: site.tagline ?? "",
    primary_color: site.primary_color,
    accent_color: site.accent_color,
    hidden_sections: site.hidden_sections ?? [],
  });
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  async function handleSave() {
    setState("saving");
    setError(null);
    try {
      onChanged(await customizeSite(token, form), "Your website's look is saved.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save."));
    }
    setState("idle");
  }

  const colour = (key, label, fallback) => (
    <div>
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <input type="color" aria-label={label} value={form[key] ?? fallback} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="h-9 w-12 cursor-pointer rounded border border-slate-300" />
        {form[key] ? (
          <button type="button" onClick={() => setForm({ ...form, [key]: null })} className="text-xs font-semibold text-slate-500 hover:underline">
            Use template colour
          </button>
        ) : (
          <span className="text-xs text-slate-400">Template colour</span>
        )}
      </div>
    </div>
  );

  return (
    <section className="grid gap-5 rounded-xl border border-slate-200 bg-white p-5 lg:grid-cols-2">
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Customize {theme.name}</h3>
          <p className="text-sm text-slate-500">Logo, banners, photos and text are under Content. Here you set the colours and what shows.</p>
        </div>
        <label className="block text-sm font-medium text-slate-700">
          Tagline <span className="font-normal text-slate-400">(shown under your college name)</span>
          <input value={form.tagline} maxLength={200} placeholder="e.g. Autonomous institution | Excellence in engineering since 1998" onChange={(e) => setForm({ ...form, tagline: e.target.value })} className={INPUT} />
        </label>
        <div className="flex flex-wrap gap-6">
          {colour("primary_color", "Main colour", theme.colors.primary)}
          {colour("accent_color", "Highlight colour", theme.colors.accent)}
        </div>
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Sections to show</legend>
          <div className="mt-1 flex flex-wrap gap-4">
            {SECTIONS.map(([id, label]) => (
              <label key={id} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={!form.hidden_sections.includes(id)}
                  onChange={(e) =>
                    setForm({ ...form, hidden_sections: e.target.checked ? form.hidden_sections.filter((x) => x !== id) : [...form.hidden_sections, id] })
                  }
                  className="rounded border-slate-300 text-emerald-600"
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
        <button type="button" disabled={state === "saving"} onClick={handleSave} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Save look"}
        </button>
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-200">
        <TemplateThumbnail site={{ ...previewSite, ...form }} templateId={site.template} />
        <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">Live preview</p>
      </div>
    </section>
  );
}

function ProNotice({ onClose }) {
  const [contact, setContact] = useState(null);
  useEffect(() => {
    apiRequest("/public/platform").then(setContact).catch(() => setContact({}));
  }, []);
  const whatsapp = contact?.whatsapp_number?.replace(/\D/g, "");
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
      <p>
        <span className="font-semibold">This is a Pro template.</span> Contact ANV Soft Solutions to unlock all templates for your college.
      </p>
      <span className="flex flex-wrap gap-2">
        {whatsapp && (
          <a href={`https://wa.me/${whatsapp}?text=${encodeURIComponent("Hi, we'd like Pro templates for our college website.")}`} target="_blank" rel="noreferrer" className="rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white">
            WhatsApp
          </a>
        )}
        {contact?.phone && (
          <a href={`tel:${contact.phone}`} className="rounded-lg px-3 py-1.5 font-semibold ring-1 ring-inset ring-amber-300">
            📞 {contact.phone}
          </a>
        )}
        {contact?.email && (
          <a href={`mailto:${contact.email}`} className="rounded-lg px-3 py-1.5 font-semibold ring-1 ring-inset ring-amber-300">
            ✉ {contact.email}
          </a>
        )}
        <button type="button" onClick={onClose} aria-label="Close" className="px-2 text-lg leading-none opacity-60 hover:opacity-100">
          ×
        </button>
      </span>
    </div>
  );
}

function DesignTab({ token, site, onChanged }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [proNotice, setProNotice] = useState(false);
  // Thumbnails look best with photos; until the college adds banners, show sample photos with its name.
  const previewSite = site.banners.length ? site : { ...SAMPLE_SITE, name: site.name, code: site.code, logo_url: site.logo_url };

  async function choose(id) {
    setBusy(id);
    setError(null);
    try {
      onChanged(await chooseTemplate(token, id), `Your website now uses ${THEMES.find((t) => t.id === id).name}.`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't switch the template."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <CustomizeCard key={site.template} token={token} site={site} previewSite={previewSite} onChanged={onChanged} />
      <p className="text-sm text-slate-500">
        Pick a design. Your content stays the same; only the look changes. {site.pro_templates ? "All templates are unlocked for your college." : "Two templates are free; the others are Pro."}
      </p>
      {proNotice && <ProNotice onClose={() => setProNotice(false)} />}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {THEMES.map((theme) => {
          const current = site.template === theme.id;
          const pro = !FREE_TEMPLATES.includes(theme.id);
          const locked = pro && !site.pro_templates && !current;
          return (
            <article key={theme.id} className={`overflow-hidden rounded-xl border bg-white ${current ? "border-emerald-500 ring-2 ring-emerald-500" : "border-slate-200"}`}>
              <TemplateThumbnail site={previewSite} templateId={theme.id} />
              <div className="space-y-2 p-4">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold text-slate-900">
                    {theme.name} {pro && <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 align-middle text-[10px] font-bold uppercase tracking-wide text-amber-800">Pro</span>}
                  </h3>
                  <span className="flex gap-1" aria-hidden="true">
                    {[theme.colors.primary, theme.colors.accent, theme.colors.bg].map((color) => (
                      <span key={color} className="h-4 w-4 rounded-full ring-1 ring-black/10" style={{ background: color }} />
                    ))}
                  </span>
                </div>
                <p className="text-xs text-slate-500">{theme.tagline}</p>
                <p className="text-xs font-medium text-slate-400">Best for: {theme.audience}</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  {current ? (
                    <span className="rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">✓ In use</span>
                  ) : locked ? (
                    <button type="button" onClick={() => { setProNotice(true); window.scrollTo({ top: 0, behavior: "smooth" }); }} className="rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-200">
                      🔒 Unlock with Pro
                    </button>
                  ) : (
                    <button type="button" disabled={busy !== null} onClick={() => choose(theme.id)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
                      {busy === theme.id ? "Applying…" : "Use this template"}
                    </button>
                  )}
                  <a href={`/templates/${theme.id}?school=${encodeURIComponent(site.code)}`} target="_blank" rel="noreferrer" className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-100">
                    Preview ↗
                  </a>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function Card({ title, children, hint }) {
  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
        {hint && <p className="text-xs text-slate-500">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function ImageUploadButton({ label, onFile, busy }) {
  const ref = useRef(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onFile(file);
        }}
      />
      <button type="button" disabled={busy} onClick={() => ref.current?.click()} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
        {busy ? "Uploading…" : label}
      </button>
    </>
  );
}

function ContentTab({ token, site, onChanged }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [about, setAbout] = useState(site.about);
  const [contact, setContact] = useState(site.contact);
  const [bannerCaption, setBannerCaption] = useState("");
  const [galleryCaption, setGalleryCaption] = useState("");
  const [activity, setActivity] = useState({ title: "", date: "", description: "" });
  const [notice, setNotice] = useState({ title: "", date: new Date().toISOString().slice(0, 10) });

  async function run(key, action, message, fallback) {
    setBusy(key);
    setError(null);
    try {
      onChanged(await action(), message);
      return true;
    } catch (err) {
      setError(errorMessage(err, fallback));
      return false;
    } finally {
      setBusy(null);
    }
  }

  const remove = (key, action) => (
    <button type="button" onClick={() => window.confirm("Remove this?") && run(key, action, "Removed.", "Couldn't remove it.")} className="text-xs font-semibold text-rose-600 hover:underline">
      Remove
    </button>
  );

  return (
    <div className="space-y-5">
      {error && <p className="rounded-lg bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">{error}</p>}

      <CollegeInfoCard token={token} site={site} onChanged={onChanged} />

      <Card title="Logo" hint="Square PNG or JPG works best.">
        <div className="flex items-center gap-4">
          {site.logo_url ? <img src={assetUrl(site.logo_url)} alt="" className="h-16 w-16 rounded-full border object-contain p-1" /> : <div className="h-16 w-16 rounded-full bg-slate-100" />}
          <ImageUploadButton label={site.logo_url ? "Change logo" : "Upload logo"} busy={busy === "logo"} onFile={(file) => run("logo", () => uploadLogo(token, file), "Logo updated.", "Couldn't upload the logo.")} />
        </div>
      </Card>

      <Card title="Banner photos" hint="Wide photos (at least 1600px). The caption becomes the big headline on your home page.">
        <div className="grid gap-3 sm:grid-cols-3">
          {site.banners.map((b) => (
            <figure key={b.id} className="overflow-hidden rounded-lg border border-slate-200">
              <img src={assetUrl(b.url)} alt="" className="aspect-video w-full object-cover" />
              <figcaption className="flex items-center justify-between gap-2 p-2 text-xs">
                <span className="truncate">{b.caption}</span>
                {remove(`banner-${b.id}`, () => deleteBanner(token, b.id))}
              </figcaption>
            </figure>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input aria-label="Banner caption" placeholder="Caption, e.g. Admissions open for 2027" value={bannerCaption} onChange={(e) => setBannerCaption(e.target.value)} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <ImageUploadButton
            label="Add banner"
            busy={busy === "banner"}
            onFile={async (file) => (await run("banner", () => uploadBanner(token, file, bannerCaption), "Banner added.", "Couldn't upload the banner.")) && setBannerCaption("")}
          />
        </div>
      </Card>

      <Card title="About & contact">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run("about", () => saveAboutContact(token, about, contact), "Saved.", "Couldn't save.");
          }}
          className="space-y-3"
        >
          <div>
            <label htmlFor="site-about" className="block text-sm font-medium text-slate-700">
              About your college
            </label>
            <textarea id="site-about" rows={5} maxLength={4000} value={about} onChange={(e) => setAbout(e.target.value)} className={INPUT} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["address", "Address"],
              ["phone", "Phone"],
              ["email", "Email"],
              ["map_url", "Google Maps link (embed link shows a map)"],
            ].map(([key, label]) => (
              <div key={key}>
                <label htmlFor={`site-${key}`} className="block text-sm font-medium text-slate-700">
                  {label}
                </label>
                <input id={`site-${key}`} value={contact[key]} onChange={(e) => setContact({ ...contact, [key]: e.target.value })} className={INPUT} />
              </div>
            ))}
          </div>
          <button type="submit" disabled={busy === "about"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
            {busy === "about" ? "Saving…" : "Save"}
          </button>
        </form>
      </Card>

      <Card title="Gallery">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {site.gallery.map((g) => (
            <figure key={g.id} className="overflow-hidden rounded-lg border border-slate-200">
              <img src={assetUrl(g.url)} alt="" className="aspect-square w-full object-cover" />
              <figcaption className="flex items-center justify-between gap-2 p-2 text-xs">
                <span className="truncate">{g.caption}</span>
                {remove(`gallery-${g.id}`, () => deleteGalleryImage(token, g.id))}
              </figcaption>
            </figure>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input aria-label="Photo caption" placeholder="Caption, e.g. Sports day" value={galleryCaption} onChange={(e) => setGalleryCaption(e.target.value)} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <ImageUploadButton
            label="Add photo"
            busy={busy === "gallery"}
            onFile={async (file) => (await run("gallery", () => uploadGalleryImage(token, file, galleryCaption), "Photo added.", "Couldn't upload the photo.")) && setGalleryCaption("")}
          />
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Events & activities">
          <ul className="divide-y divide-slate-100 text-sm">
            {site.activities.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-semibold">{a.title}</span> <span className="text-slate-400">{new Date(a.date).toLocaleDateString("en-IN")}</span>
                </span>
                {remove(`activity-${a.id}`, () => deleteActivity(token, a.id))}
              </li>
            ))}
          </ul>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (await run("activity", () => addActivity(token, activity), "Event added.", "Couldn't add the event.")) setActivity({ title: "", date: "", description: "" });
            }}
            className="space-y-2"
          >
            <div className="grid grid-cols-3 gap-2">
              <input aria-label="Event title" required placeholder="Title" value={activity.title} onChange={(e) => setActivity({ ...activity, title: e.target.value })} className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <input aria-label="Event date" type="date" required value={activity.date} onChange={(e) => setActivity({ ...activity, date: e.target.value })} className="rounded-lg border border-slate-300 px-2 py-2 text-sm" />
            </div>
            <input aria-label="Event description" placeholder="Short description" value={activity.description} onChange={(e) => setActivity({ ...activity, description: e.target.value })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <button type="submit" disabled={busy === "activity"} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">
              Add event
            </button>
          </form>
        </Card>

        <Card title="Notices" hint="Shown in the scrolling 'Latest' bar and the notice board.">
          <ul className="divide-y divide-slate-100 text-sm">
            {site.notices.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-2 py-2">
                <span>
                  {n.title} <span className="text-slate-400">{new Date(n.date).toLocaleDateString("en-IN")}</span>
                </span>
                {remove(`notice-${n.id}`, () => deleteNotice(token, n.id))}
              </li>
            ))}
          </ul>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (await run("notice", () => addNotice(token, notice), "Notice added.", "Couldn't add the notice.")) setNotice({ ...notice, title: "" });
            }}
            className="grid grid-cols-3 gap-2"
          >
            <input aria-label="Notice" required placeholder="Notice text" value={notice.title} onChange={(e) => setNotice({ ...notice, title: e.target.value })} className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <input aria-label="Notice date" type="date" required value={notice.date} onChange={(e) => setNotice({ ...notice, date: e.target.value })} className="rounded-lg border border-slate-300 px-2 py-2 text-sm" />
            <button type="submit" disabled={busy === "notice"} className="col-span-3 justify-self-start rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">
              Add notice
            </button>
          </form>
        </Card>
      </div>
    </div>
  );
}

function SchoolSitePage() {
  const { token } = useAuth();
  const [state, setState] = useState("loading");
  const [site, setSite] = useState(null);
  const [tab, setTab] = useState("design");
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    try {
      setSite(await fetchMySite(token));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function onChanged(updated, message) {
    setSite(updated);
    setNotice(message);
  }

  if (state === "loading") return <div className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (state === "error") {
    return (
      <p className="text-sm font-semibold text-rose-700">
        Couldn&apos;t load your website.{" "}
        <button type="button" onClick={load} className="underline">
          Retry
        </button>
      </p>
    );
  }

  const liveUrl = `${window.location.origin}/site/${site.code.toLowerCase()}`;
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">College website</h2>
          <p className="mt-1 text-sm text-slate-500">
            Live at{" "}
            <a href={liveUrl} target="_blank" rel="noreferrer" className="font-semibold text-emerald-700 hover:underline">
              {liveUrl}
            </a>
          </p>
        </div>
        <a href={liveUrl} target="_blank" rel="noreferrer" className="self-start rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">
          View website ↗
        </a>
      </div>
      <div role="tablist" className="flex gap-1 rounded-lg bg-slate-100 p-1 text-sm font-semibold">
        {[
          ["design", `Design (${THEMES.length} templates)`],
          ["content", "Content"],
        ].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)} className={`rounded-md px-4 py-1.5 ${tab === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
            {label}
          </button>
        ))}
      </div>
      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}
      {tab === "design" ? <DesignTab token={token} site={site} onChanged={onChanged} /> : <ContentTab token={token} site={site} onChanged={onChanged} />}
    </div>
  );
}

export default SchoolSitePage;

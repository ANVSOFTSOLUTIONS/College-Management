import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { fetchPublicSite } from "../../api/schoolSiteApi";
import SiteRenderer from "../../siteTemplates/SiteRenderer";
import { SAMPLE_SITE } from "../../siteTemplates/sampleSite";
import { THEME_BY_ID } from "../../siteTemplates/themes";

function Centered({ children }) {
  return <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6 text-center">{children}</div>;
}

function Spinner() {
  return (
    <Centered>
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-emerald-600" />
    </Centered>
  );
}

// A college's public website: /site/:code (uses the college's chosen template).
export function PublicSitePage() {
  const { slug } = useParams();
  const [state, setState] = useState("loading");
  const [site, setSite] = useState(null);

  useEffect(() => {
    fetchPublicSite(slug)
      .then((result) => {
        setSite(result);
        document.title = result.name;
        setState("ready");
      })
      .catch(() => setState("error"));
  }, [slug]);

  if (state === "loading") return <Spinner />;
  if (state === "error") {
    return (
      <Centered>
        <div>
          <p className="text-xl font-bold text-slate-800">College not found</p>
          <p className="mt-2 text-slate-500">Check the link, or contact the college.</p>
        </div>
      </Centered>
    );
  }
  return <SiteRenderer site={site} templateId={site.template} />;
}

// Template preview: /templates/:id with sample content, or ?school=CODE for that college's content.
export function TemplatePreviewPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const school = params.get("school");
  const [site, setSite] = useState(school ? null : SAMPLE_SITE);

  useEffect(() => {
    if (!school) return;
    fetchPublicSite(school)
      .then(setSite)
      .catch(() => setSite(SAMPLE_SITE));
  }, [school]);

  if (!THEME_BY_ID[id]) {
    return (
      <Centered>
        <p className="text-xl font-bold text-slate-800">Template not found</p>
      </Centered>
    );
  }
  if (!site) return <Spinner />;
  return (
    <>
      <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900/90 px-4 py-2 text-xs font-semibold text-white shadow-xl backdrop-blur">
        Preview · {THEME_BY_ID[id].name}
      </div>
      <SiteRenderer site={site} templateId={id} />
    </>
  );
}

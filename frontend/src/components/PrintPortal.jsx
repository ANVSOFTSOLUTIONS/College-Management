import { useEffect } from "react";
import { createPortal } from "react-dom";

import { assetUrl } from "../siteTemplates/SiteRenderer";

// Full-screen preview with a Print button; only the document goes to paper.
export function PrintPortal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div className="print-portal">
      <div className="no-print sticky top-0 z-10 flex items-center justify-between gap-3 bg-slate-900 px-4 py-3 text-white">
        <p className="truncate font-semibold">{title}</p>
        <div className="flex shrink-0 gap-2">
          <button type="button" onClick={() => window.print()} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold hover:bg-emerald-400">
            🖨 Print
          </button>
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-semibold ring-1 ring-inset ring-white/30 hover:bg-white/10">
            Close
          </button>
        </div>
      </div>
      <div className="print-sheet flex flex-col items-center gap-6 p-4 sm:p-8">{children}</div>
    </div>,
    document.body,
  );
}

export function SchoolHeader({ school, compact = false }) {
  return (
    <div className={`flex items-center gap-3 ${compact ? "" : "justify-center text-center"}`}>
      {school.logo_url && <img src={assetUrl(school.logo_url)} alt="" className={compact ? "h-7 w-7 rounded-full bg-white object-contain p-0.5" : "h-16 w-16 object-contain"} />}
      <div className={compact ? "min-w-0" : ""}>
        <p className={compact ? "truncate text-[11px] font-bold leading-tight" : "text-2xl font-bold uppercase tracking-wide text-slate-900"}>{school.name}</p>
        {!compact && (school.address || school.phone) && (
          <p className="text-sm text-slate-600">
            {school.address}
            {school.address && school.phone && " · "}
            {school.phone && `Phone: ${school.phone}`}
          </p>
        )}
      </div>
    </div>
  );
}


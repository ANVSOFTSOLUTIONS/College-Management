import { useCallback, useEffect, useRef, useState } from "react";

import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "../api/staffApi";
import { useAuth } from "../context/AuthContext";
import { disablePush, enablePush, pushStatus } from "../lib/push";

const POLL_MS = 60_000;

function timeAgo(iso) {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Date(iso).toLocaleDateString("en-IN");
}

const PUSH_TEXT = {
  "needs-install": "On iPhone, add this app to your Home Screen first, then turn phone notifications on here.",
  unsupported: "This browser can't show phone notifications.",
  denied: "Notifications are blocked. Allow them for this site in your browser settings.",
};

// The switch for notifications that arrive on this phone/computer even when the app is closed.
function PushToggle({ token }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    pushStatus().then(setStatus).catch(() => setStatus("unsupported"));
  }, []);

  async function toggle() {
    setBusy(true);
    try {
      setStatus(status === "on" ? await disablePush(token) : await enablePush(token));
    } catch {
      setStatus(await pushStatus().catch(() => "unsupported"));
    }
    setBusy(false);
  }

  if (status === null) return null;
  return (
    <div className="border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs">
      {PUSH_TEXT[status] ? (
        <p className="text-slate-500">📱 {PUSH_TEXT[status]}</p>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <p className="text-slate-600">📱 Phone notifications {status === "on" ? "are on for this device." : "are off."}</p>
          <button
            type="button"
            disabled={busy}
            onClick={toggle}
            className={`shrink-0 rounded-lg px-3 py-1.5 font-semibold disabled:opacity-60 ${status === "on" ? "text-slate-600 ring-1 ring-inset ring-slate-300" : "bg-emerald-600 text-white"}`}
          >
            {busy ? "…" : status === "on" ? "Turn off" : "Turn on"}
          </button>
        </div>
      )}
    </div>
  );
}

function NotificationBell({ onOpenLink }) {
  const { token } = useAuth();
  const [data, setData] = useState({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);

  const load = useCallback(() => {
    fetchNotifications(token)
      .then(setData)
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    load();
    const timer = setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!open) return undefined;
    function onClick(event) {
      if (panelRef.current && !panelRef.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  async function openItem(item) {
    setOpen(false);
    if (!item.read) {
      setData((prev) => ({ unread: Math.max(0, prev.unread - 1), items: prev.items.map((i) => (i.id === item.id ? { ...i, read: true } : i)) }));
      markNotificationRead(token, item.id).catch(() => {});
    }
    if (item.link) onOpenLink?.(item.link);
  }

  async function readAll() {
    setData((prev) => ({ unread: 0, items: prev.items.map((i) => ({ ...i, read: true })) }));
    markAllNotificationsRead(token).catch(() => {});
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => {
          setOpen(!open);
          if (!open) load();
        }}
        aria-label={`Notifications${data.unread ? `, ${data.unread} unread` : ""}`}
        className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {data.unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 min-w-[1.1rem] rounded-full bg-rose-600 px-1 text-center text-[10px] font-bold leading-[1.1rem] text-white">
            {data.unread > 9 ? "9+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className="fixed inset-x-4 top-16 z-30 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-auto sm:mt-2 sm:w-80">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
            <p className="text-sm font-semibold text-slate-800">Notifications</p>
            {data.unread > 0 && (
              <button type="button" onClick={readAll} className="text-xs font-semibold text-emerald-700 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          {data.items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">No notifications yet.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
              {data.items.map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => openItem(item)} className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${item.read ? "" : "bg-emerald-50/60"}`}>
                    <p className={`text-sm ${item.read ? "text-slate-700" : "font-semibold text-slate-900"}`}>{item.title}</p>
                    {item.body && <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{item.body}</p>}
                    <p className="mt-1 text-[11px] text-slate-400">{timeAgo(item.created_at)}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <PushToggle token={token} />
        </div>
      )}
    </div>
  );
}

export default NotificationBell;

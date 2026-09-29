import { useCallback, useEffect, useState } from "react";

import {
  deleteNotice,
  fetchNotices,
  fetchPostingOptions,
  noticeAttachment,
  removeNoticeAttachment,
  saveNotice,
  uploadNoticeAttachment,
} from "../api/boardApi";
import { openBlob } from "../components/StudentFiles";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/apiClient";

const INPUT = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500";
const EMPTY = { title: "", body: "", class_ids: [], for_staff: false, for_students: true, for_parents: true, is_pinned: false, expires_on: "" };

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

export function formatDate(iso) {
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function Checkbox({ label, checked, onChange, disabled }) {
  return (
    <label className={`flex items-center gap-2 text-sm ${disabled ? "text-slate-400" : "text-slate-700"}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} className="rounded border-slate-300 text-emerald-600" />
      {label}
    </label>
  );
}

function NoticeForm({ token, isAdmin, classes, notice, onSaved, onCancel }) {
  const [form, setForm] = useState(() =>
    notice ? { ...EMPTY, ...notice, expires_on: notice.expires_on ?? "" } : { ...EMPTY, class_ids: isAdmin ? [] : classes.slice(0, 1).map((c) => c.id) },
  );
  const [wholeSchool, setWholeSchool] = useState(isAdmin && !(notice?.class_ids.length > 0));
  const [file, setFile] = useState(null);
  const [removeFile, setRemoveFile] = useState(false);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);

  function toggleClass(id, on) {
    setForm((f) => ({ ...f, class_ids: on ? [...f.class_ids, id] : f.class_ids.filter((c) => c !== id) }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const classIds = wholeSchool ? [] : form.class_ids;
    if (!wholeSchool && classIds.length === 0) {
      setError("Choose at least one class.");
      return;
    }
    setState("saving");
    setError(null);
    try {
      const body = {
        title: form.title,
        body: form.body,
        class_ids: classIds,
        for_staff: isAdmin && form.for_staff,
        for_students: form.for_students,
        for_parents: form.for_parents,
        is_pinned: isAdmin && form.is_pinned,
        expires_on: form.expires_on || null,
      };
      let saved = await saveNotice(token, body, notice?.id);
      if (file) saved = await uploadNoticeAttachment(token, saved.id, file);
      else if (removeFile) saved = await removeNoticeAttachment(token, saved.id);
      onSaved(saved);
    } catch (err) {
      setState("idle");
      setError(errorMessage(err, "Couldn't save the notice."));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-emerald-200 bg-white p-5">
      <h3 className="text-lg font-semibold text-slate-900">{notice ? "Edit notice" : "New notice"}</h3>
      <div>
        <label htmlFor="notice-title" className="block text-sm font-medium text-slate-700">
          Title
        </label>
        <input id="notice-title" required minLength={3} maxLength={150} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={INPUT} />
      </div>
      <div>
        <label htmlFor="notice-body" className="block text-sm font-medium text-slate-700">
          Message
        </label>
        <textarea id="notice-body" required rows={5} maxLength={5000} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className={INPUT} />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-700">Which classes</legend>
        {isAdmin && (
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" checked={wholeSchool} onChange={() => setWholeSchool(true)} className="text-emerald-600" /> Whole college
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={!wholeSchool} onChange={() => setWholeSchool(false)} className="text-emerald-600" /> Selected classes
            </label>
          </div>
        )}
        {!wholeSchool &&
          (classes.length === 0 ? (
            <p className="text-sm text-slate-500">You don&apos;t teach any class yet.</p>
          ) : (
            <div className="grid max-h-48 grid-cols-2 gap-1 overflow-y-auto rounded-lg bg-slate-50 p-3 sm:grid-cols-4">
              {classes.map((c) => (
                <Checkbox key={c.id} label={`${c.name} - ${c.section}`} checked={form.class_ids.includes(c.id)} onChange={(on) => toggleClass(c.id, on)} />
              ))}
            </div>
          ))}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-700">Who sees it</legend>
        <div className="flex flex-wrap gap-4">
          {isAdmin && <Checkbox label="Faculty" checked={form.for_staff} onChange={(on) => setForm({ ...form, for_staff: on })} />}
          <Checkbox label="Students" checked={form.for_students} onChange={(on) => setForm({ ...form, for_students: on })} />
          <Checkbox label="Parents" checked={form.for_parents} onChange={(on) => setForm({ ...form, for_parents: on })} />
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="notice-expires" className="block text-sm font-medium text-slate-700">
            Show until <span className="font-normal text-slate-400">(optional)</span>
          </label>
          <input id="notice-expires" type="date" value={form.expires_on} onChange={(e) => setForm({ ...form, expires_on: e.target.value })} className={INPUT} />
        </div>
        <div>
          <label htmlFor="notice-file" className="block text-sm font-medium text-slate-700">
            Attachment <span className="font-normal text-slate-400">(PDF or photo, optional)</span>
          </label>
          <input id="notice-file" type="file" accept=".pdf,image/jpeg,image/png,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1 w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:font-semibold" />
          {notice?.attachment_name && !file && (
            <Checkbox label={`Remove ${notice.attachment_name}`} checked={removeFile} onChange={setRemoveFile} />
          )}
        </div>
      </div>
      {isAdmin && <Checkbox label="Pin to the top" checked={form.is_pinned} onChange={(on) => setForm({ ...form, is_pinned: on })} />}

      {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={state === "saving"} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "saving" ? "Posting…" : notice ? "Save changes" : "Post notice"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
          Cancel
        </button>
      </div>
    </form>
  );
}

function audienceLabel(notice) {
  const who = [notice.for_staff && "Faculty", notice.for_students && "Students", notice.for_parents && "Parents"].filter(Boolean).join(", ");
  const where = notice.classes.length ? notice.classes.join(", ") : "Whole college";
  return `${where} · ${who}`;
}

function NoticeCard({ notice, token, isStaff, onEdit, onDeleted }) {
  const [error, setError] = useState(null);

  async function handleOpen() {
    setError(null);
    try {
      await openBlob(() => noticeAttachment(token, notice.id));
    } catch (err) {
      setError(errorMessage(err, "Couldn't open the file."));
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete "${notice.title}"?`)) return;
    try {
      await deleteNotice(token, notice.id);
      onDeleted(notice.id);
    } catch (err) {
      setError(errorMessage(err, "Couldn't delete the notice."));
    }
  }

  return (
    <article className={`rounded-xl border bg-white p-5 ${notice.is_pinned ? "border-amber-300" : "border-slate-200"} ${notice.is_expired ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {notice.is_pinned && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">📌 Pinned</span>}
            {notice.is_expired && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">Expired</span>}
            <h3 className="text-lg font-semibold text-slate-900">{notice.title}</h3>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            {formatDate(notice.created_at)}
            {notice.posted_by_name && ` · ${notice.posted_by_name}`}
            {isStaff && ` · ${audienceLabel(notice)}`}
            {notice.expires_on && ` · until ${formatDate(notice.expires_on)}`}
          </p>
        </div>
        {notice.can_edit && (
          <div className="flex gap-2 text-sm">
            <button type="button" onClick={() => onEdit(notice)} className="font-semibold text-emerald-700 hover:underline">
              Edit
            </button>
            <button type="button" onClick={handleDelete} className="font-semibold text-rose-700 hover:underline">
              Delete
            </button>
          </div>
        )}
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{notice.body}</p>
      {notice.attachment_name && (
        <button type="button" onClick={handleOpen} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-200">
          📎 {notice.attachment_name}
        </button>
      )}
      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}
    </article>
  );
}

function NoticesPage() {
  const { token, user } = useAuth();
  const isStaff = user.role === "admin" || user.role === "teacher";
  const isAdmin = user.role === "admin";
  const [state, setState] = useState("loading");
  const [notices, setNotices] = useState([]);
  const [classes, setClasses] = useState([]);
  const [showExpired, setShowExpired] = useState(false);
  const [editing, setEditing] = useState(null); // null, "new", or a notice

  const load = useCallback(async () => {
    setState("loading");
    try {
      const [list, options] = await Promise.all([fetchNotices(token, showExpired), isStaff ? fetchPostingOptions(token) : Promise.resolve([])]);
      setNotices(list);
      setClasses(options);
      setState("ready");
    } catch (err) {
      setState(err instanceof ApiError && err.status === 403 ? "forbidden" : "error");
    }
  }, [token, isStaff, showExpired]);

  useEffect(() => {
    load();
  }, [load]);

  const canPost = isAdmin || (user.role === "teacher" && classes.length > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Notice board</h2>
          <p className="mt-1 text-sm text-slate-500">
            {isAdmin
              ? "Post to the whole college or chosen classes. Everyone it's for gets a notification."
              : user.role === "teacher"
                ? "College notices, and notices for the classes you teach."
                : "Notices from your college."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isStaff && <Checkbox label="Show expired" checked={showExpired} onChange={setShowExpired} />}
          {canPost && editing === null && (
            <button type="button" onClick={() => setEditing("new")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
              + New notice
            </button>
          )}
        </div>
      </div>

      {editing !== null && (
        <NoticeForm
          key={editing === "new" ? "new" : editing.id}
          token={token}
          isAdmin={isAdmin}
          classes={classes}
          notice={editing === "new" ? null : editing}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      {state === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {state === "error" && (
        <p className="text-sm font-semibold text-rose-700">
          Couldn&apos;t load notices.{" "}
          <button type="button" onClick={load} className="underline">
            Try again
          </button>
        </p>
      )}
      {state === "forbidden" && <p className="text-sm font-semibold text-rose-700">You don&apos;t have access to notices.</p>}
      {state === "ready" &&
        (notices.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">No notices right now.</p>
        ) : (
          <div className="space-y-4">
            {notices.map((n) => (
              <NoticeCard
                key={n.id}
                notice={n}
                token={token}
                isStaff={isStaff}
                onEdit={(notice) => {
                  setEditing(notice);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                onDeleted={(id) => setNotices((list) => list.filter((x) => x.id !== id))}
              />
            ))}
          </div>
        ))}
    </div>
  );
}

export default NoticesPage;

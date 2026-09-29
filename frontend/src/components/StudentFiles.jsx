import { useCallback, useEffect, useRef, useState } from "react";

import {
  DOCUMENT_TYPES,
  deleteDocument,
  fetchDocumentFile,
  fetchDocuments,
  fetchPhoto,
  reviewDocument,
  uploadDocument,
  uploadPhoto,
} from "../api/studentPortalApi";
import { ApiError } from "../lib/apiClient";

function errorMessage(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

const STATUS_STYLES = {
  pending: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700",
  rejected: "bg-rose-50 text-rose-700",
};
const STATUS_LABELS = { pending: "Waiting for review", approved: "Approved", rejected: "Rejected" };

function formatSize(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export async function openBlob(loadBlob) {
  // Open the tab first so pop-up blockers treat it as part of the click.
  const tab = window.open("", "_blank");
  try {
    const url = URL.createObjectURL(await loadBlob());
    if (tab) tab.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    tab?.close();
    throw err;
  }
}

export function StudentPhoto({ token, base, hasPhoto, name, editable, onUploaded, size = "h-24 w-24" }) {
  const [url, setUrl] = useState(null);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!hasPhoto) {
      setUrl(null);
      return undefined;
    }
    let objectUrl = null;
    let cancelled = false;
    fetchPhoto(token, base)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => setUrl(null));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [token, base, hasPhoto, state]);

  async function handleFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setState("uploading");
    setError(null);
    try {
      const updated = await uploadPhoto(token, base, file);
      setState("idle");
      onUploaded?.(updated);
    } catch (err) {
      setState("idle");
      setError(errorMessage(err, "Couldn't upload the photo."));
    }
  }

  const initials = (name || "?")
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="flex items-center gap-4">
      {url ? (
        <img src={url} alt={`Photo of ${name}`} className={`${size} rounded-full object-cover ring-2 ring-slate-100`} />
      ) : (
        <div className={`${size} flex items-center justify-center rounded-full bg-emerald-100 text-xl font-bold text-emerald-700`}>{initials}</div>
      )}
      {editable && (
        <div className="space-y-1">
          <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFile} className="hidden" />
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={state === "uploading"}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-100 disabled:opacity-60"
          >
            {state === "uploading" ? "Uploading…" : hasPhoto ? "Change photo" : "Upload photo"}
          </button>
          <p className="text-xs text-slate-400">JPEG, PNG, or WEBP, up to 5MB.</p>
          {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
        </div>
      )}
    </div>
  );
}

function UploadDocumentForm({ token, base, onUploaded }) {
  const [docType, setDocType] = useState(DOCUMENT_TYPES[0].id);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [state, setState] = useState("idle");
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) return;
    setState("uploading");
    setError(null);
    try {
      await uploadDocument(token, base, { docType, title, file });
      setTitle("");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      setState("idle");
      onUploaded();
    } catch (err) {
      setState("idle");
      setError(errorMessage(err, "Couldn't upload the document."));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-dashed border-slate-300 p-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="doc-type" className="block text-sm font-medium text-slate-700">
            Document
          </label>
          <select id="doc-type" value={docType} onChange={(e) => setDocType(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
            {DOCUMENT_TYPES.map((type) => (
              <option key={type.id} value={type.id}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="doc-title" className="block text-sm font-medium text-slate-700">
            Note (optional)
          </label>
          <input id="doc-title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Class 5 marks memo" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label htmlFor="doc-file" className="block text-sm font-medium text-slate-700">
            File
          </label>
          <input
            id="doc-file"
            ref={fileRef}
            type="file"
            required
            accept="application/pdf,image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-semibold"
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!file || state === "uploading"}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {state === "uploading" ? "Uploading…" : "Upload"}
        </button>
        <span className="text-xs text-slate-400">PDF or image, up to 10MB.</span>
        {error && <span className="text-sm font-medium text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

// `studentId` set = staff view (can review and remove anything); unset = the student's own view.
export function StudentDocuments({ token, base, studentId, onChanged }) {
  const isStaff = Boolean(studentId);
  const [state, setState] = useState("loading");
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState(null);
  const [rejecting, setRejecting] = useState(null);
  const [rejectNote, setRejectNote] = useState("");

  const load = useCallback(async () => {
    try {
      setDocuments(await fetchDocuments(token, base));
      setState("ready");
    } catch {
      setState("error");
    }
  }, [token, base]);

  useEffect(() => {
    load();
  }, [load]);

  async function afterChange() {
    await load();
    onChanged?.();
  }

  async function run(action, fallback) {
    setError(null);
    try {
      await action();
      await afterChange();
    } catch (err) {
      setError(errorMessage(err, fallback));
    }
  }

  function handleView(document) {
    setError(null);
    openBlob(() => fetchDocumentFile(token, base, document.id)).catch((err) => setError(errorMessage(err, "Couldn't open the file.")));
  }

  function handleDelete(document) {
    if (!window.confirm(`Remove ${document.doc_type_label}?`)) return;
    run(() => deleteDocument(token, base, document.id), "Couldn't remove the document.");
  }

  function handleReject(event) {
    event.preventDefault();
    const document = rejecting;
    run(async () => {
      await reviewDocument(token, studentId, document.id, "rejected", rejectNote);
      setRejecting(null);
      setRejectNote("");
    }, "Couldn't reject the document.");
  }

  return (
    <div className="space-y-4">
      {state === "loading" && <div className="h-20 animate-pulse rounded-lg bg-slate-100" />}
      {state === "error" && (
        <div className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-800">
          Couldn&apos;t load documents.
          <button type="button" onClick={load} className="underline">
            Retry
          </button>
        </div>
      )}
      {state === "ready" && documents.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
          {isStaff ? "No documents uploaded yet." : "You haven't uploaded any documents yet."}
        </p>
      )}
      {state === "ready" && documents.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {documents.map((document) => {
            const studentCanRemove = document.status !== "approved";
            return (
              <li key={document.id} className="space-y-2 px-4 py-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-800">
                      {document.doc_type_label}
                      <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[document.status]}`}>{STATUS_LABELS[document.status]}</span>
                    </p>
                    <p className="truncate text-xs text-slate-400">
                      {[document.title, document.original_name, formatSize(document.size_bytes), new Date(document.uploaded_at).toLocaleDateString()].filter(Boolean).join(" · ")}
                    </p>
                    {document.status === "rejected" && document.review_note && (
                      <p className="mt-1 text-xs font-medium text-rose-600">Reason: {document.review_note}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => handleView(document)} className="rounded-lg px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100">
                      View
                    </button>
                    {isStaff && document.status !== "approved" && (
                      <button
                        type="button"
                        onClick={() => run(() => reviewDocument(token, studentId, document.id, "approved", ""), "Couldn't approve the document.")}
                        className="rounded-lg px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50"
                      >
                        Approve
                      </button>
                    )}
                    {isStaff && document.status !== "rejected" && (
                      <button
                        type="button"
                        onClick={() => {
                          setRejecting(document);
                          setRejectNote("");
                        }}
                        className="rounded-lg px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-200 hover:bg-amber-50"
                      >
                        Reject
                      </button>
                    )}
                    {(isStaff || studentCanRemove) && (
                      <button type="button" onClick={() => handleDelete(document)} className="rounded-lg px-3 py-1 text-xs font-semibold text-rose-600 ring-1 ring-inset ring-rose-200 hover:bg-rose-50">
                        Remove
                      </button>
                    )}
                  </div>
                </div>
                {rejecting?.id === document.id && (
                  <form onSubmit={handleReject} className="flex flex-col gap-2 sm:flex-row">
                    <input
                      required
                      autoFocus
                      aria-label="Reason for rejecting"
                      maxLength={300}
                      value={rejectNote}
                      onChange={(e) => setRejectNote(e.target.value)}
                      placeholder="Why? e.g. Scan is blurry, please upload again"
                      className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                    />
                    <button type="submit" className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700">
                      Reject
                    </button>
                    <button type="button" onClick={() => setRejecting(null)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-500 hover:bg-slate-100">
                      Cancel
                    </button>
                  </form>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
      <UploadDocumentForm token={token} base={base} onUploaded={afterChange} />
    </div>
  );
}

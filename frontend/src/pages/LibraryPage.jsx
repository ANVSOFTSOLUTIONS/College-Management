import { useState } from "react";

import { fetchTeachers } from "../api/academicsApi";
import {
  deleteBook,
  fetchBooks,
  fetchLibrarySettings,
  fetchLibrarySummary,
  fetchLoans,
  issueBook,
  loanAction,
  saveBook,
  saveLibrarySettings,
} from "../api/campusApi";
import { DANGER, errorMessage, Field, INPUT, LoadState, Notice, PageHeader, PRIMARY, rupees, SECONDARY, Stat, StudentPicker, useLoad } from "../components/CampusUi";
import { useAuth } from "../context/AuthContext";

const EMPTY_BOOK = { title: "", author: "", isbn: "", category: "", shelf: "", total_copies: 1 };
const TABS = [
  { id: "open", label: "On loan" },
  { id: "overdue", label: "Overdue" },
  { id: "fines", label: "Unpaid fines" },
  { id: "all", label: "History" },
  { id: "books", label: "Books" },
  { id: "settings", label: "Rules" },
];

function BookForm({ token, book, onDone }) {
  const [form, setForm] = useState(book ? { ...EMPTY_BOOK, ...book } : EMPTY_BOOK);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    try {
      const { title, author, isbn, category, shelf, total_copies } = form;
      await saveBook(token, { title, author, isbn, category, shelf, total_copies: Number(total_copies) }, book?.id);
      onDone(book ? "Book updated." : `${form.title} added.`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the book."));
    }
  }

  const input = (key, label, props = {}) => (
    <Field id={`book-${key}`} label={label}>
      <input id={`book-${key}`} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className={INPUT} {...props} />
    </Field>
  );
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-6">
      <div className="sm:col-span-3">{input("title", "Title", { required: true, maxLength: 250 })}</div>
      <div className="sm:col-span-3">{input("author", "Author", { maxLength: 200 })}</div>
      <div className="sm:col-span-2">{input("isbn", "ISBN", { maxLength: 20 })}</div>
      <div className="sm:col-span-2">{input("category", "Category / subject", { maxLength: 100, placeholder: "e.g. Computer Science" })}</div>
      {input("shelf", "Shelf", { maxLength: 50 })}
      {input("total_copies", "Copies", { type: "number", min: 1, required: true })}
      <div className="flex items-center gap-3 sm:col-span-6">
        <button type="submit" className={PRIMARY}>
          {book ? "Save book" : "Add book"}
        </button>
        <button type="button" onClick={() => onDone(null)} className="text-sm font-semibold text-slate-500">
          Cancel
        </button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function IssueForm({ token, onDone }) {
  const [borrowerType, setBorrowerType] = useState("student");
  const [student, setStudent] = useState(null);
  const [teacherId, setTeacherId] = useState("");
  const [bookQuery, setBookQuery] = useState("");
  const [bookId, setBookId] = useState("");
  const [error, setError] = useState(null);
  const [books] = useLoad(() => fetchBooks(token, bookQuery), [token, bookQuery]);
  const [teachers] = useLoad(() => fetchTeachers(token), [token]);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    try {
      const loan = await issueBook(token, {
        book_id: bookId,
        student_id: borrowerType === "student" ? student?.id : null,
        teacher_id: borrowerType === "faculty" ? teacherId : null,
      });
      onDone(`Issued "${loan.book_title}" to ${loan.borrower_name}, due ${loan.due_on}.`);
    } catch (err) {
      setError(errorMessage(err, "Couldn't issue the book."));
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl border border-emerald-200 bg-white p-5 sm:grid-cols-2">
      <Field id="issue-to" label="Issue to">
        <div className="mt-1 flex gap-2">
          {["student", "faculty"].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setBorrowerType(t)}
              className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${borrowerType === t ? "bg-emerald-600 text-white ring-emerald-600" : "text-slate-600 ring-slate-300"}`}
            >
              {t}
            </button>
          ))}
        </div>
        {borrowerType === "student" ? (
          <StudentPicker token={token} id="issue-student" value={student} onChange={setStudent} />
        ) : (
          <select id="issue-teacher" required value={teacherId} onChange={(e) => setTeacherId(e.target.value)} className={INPUT}>
            <option value="">Choose faculty…</option>
            {(teachers ?? [])
              .filter((t) => t.status === "active")
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name} {t.department ? `(${t.department})` : ""}
                </option>
              ))}
          </select>
        )}
      </Field>
      <Field id="issue-book-search" label="Book">
        <input id="issue-book-search" value={bookQuery} onChange={(e) => setBookQuery(e.target.value)} placeholder="Search title, author, ISBN" className={INPUT} />
        <select aria-label="Book" required value={bookId} onChange={(e) => setBookId(e.target.value)} className={INPUT}>
          <option value="">Choose a book…</option>
          {(books ?? []).map((b) => (
            <option key={b.id} value={b.id} disabled={b.available === 0}>
              {b.title} {b.author && `— ${b.author}`} ({b.available}/{b.total_copies} available)
            </option>
          ))}
        </select>
      </Field>
      <div className="flex items-center gap-3 sm:col-span-2">
        <button type="submit" className={PRIMARY} disabled={!bookId || (borrowerType === "student" ? !student : !teacherId)}>
          Issue book
        </button>
        <button type="button" onClick={() => onDone(null)} className="text-sm font-semibold text-slate-500">
          Cancel
        </button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function SettingsForm({ token, onSaved }) {
  const [settings, , state] = useLoad(() => fetchLibrarySettings(token), [token]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  if (state !== "ready") return <LoadState state={state} what="library rules" />;
  const values = form ?? settings;

  async function submit(event) {
    event.preventDefault();
    try {
      await saveLibrarySettings(token, { loan_days: Number(values.loan_days), fine_per_day: Number(values.fine_per_day), max_books: Number(values.max_books) });
      onSaved("Library rules saved.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't save the rules."));
    }
  }
  return (
    <form onSubmit={submit} className="grid max-w-xl gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-3">
      {[
        ["loan_days", "Loan period (days)", 1],
        ["fine_per_day", "Fine per late day (₹)", 0],
        ["max_books", "Books per borrower", 1],
      ].map(([key, label, min]) => (
        <Field key={key} id={`lib-${key}`} label={label}>
          <input id={`lib-${key}`} type="number" min={min} step={key === "fine_per_day" ? "0.5" : "1"} required value={values[key]}
            onChange={(e) => setForm({ ...values, [key]: e.target.value })} className={INPUT} />
        </Field>
      ))}
      <div className="flex items-center gap-3 sm:col-span-3">
        <button type="submit" className={PRIMARY}>
          Save rules
        </button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

function LibraryPage() {
  const { token } = useAuth();
  const [tab, setTab] = useState("open");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null); // null | "issue" | "new-book" | book
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [summary, reloadSummary] = useLoad(() => fetchLibrarySummary(token), [token]);
  const isLoanTab = ["open", "overdue", "fines", "all"].includes(tab);
  const [loans, reloadLoans, loanState] = useLoad(() => (isLoanTab ? fetchLoans(token, tab) : Promise.resolve([])), [token, tab]);
  const [books, reloadBooks, bookState] = useLoad(() => (tab === "books" ? fetchBooks(token, query) : Promise.resolve([])), [token, tab, query]);

  function done(msg) {
    setEditing(null);
    setError(null);
    if (msg) setMessage(msg);
    reloadSummary();
    reloadLoans();
    reloadBooks();
  }

  async function act(loan, action, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return;
    setError(null);
    try {
      const updated = await loanAction(token, loan.id, action);
      done(
        action === "return"
          ? `Returned "${updated.book_title}".${updated.fine ? ` Fine: ${rupees(updated.fine)}.` : ""}`
          : action === "renew"
            ? `Renewed until ${updated.due_on}.`
            : "Fine marked as paid.",
      );
    } catch (err) {
      setError(errorMessage(err, "Couldn't update the loan."));
    }
  }

  async function removeBook(book) {
    if (!window.confirm(`Delete "${book.title}"?`)) return;
    try {
      await deleteBook(token, book.id);
      done("Book deleted.");
    } catch (err) {
      setError(errorMessage(err, "Couldn't delete the book."));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Library" subtitle="Catalogue, issue and return, overdue books and fines.">
        <button type="button" onClick={() => setEditing("issue")} className={PRIMARY}>
          Issue book
        </button>
        <button type="button" onClick={() => { setTab("books"); setEditing("new-book"); }} className={SECONDARY}>
          Add book
        </button>
      </PageHeader>

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Stat label="Titles" value={summary.titles} />
          <Stat label="Copies" value={summary.copies} />
          <Stat label="On loan" value={summary.on_loan} />
          <Stat label="Overdue" value={summary.overdue} tone={summary.overdue ? "rose" : "slate"} />
          <Stat label="Unpaid fines" value={rupees(summary.unpaid_fines)} tone={summary.unpaid_fines ? "rose" : "slate"} />
        </div>
      )}

      <Notice message={message} error={error} />
      {editing === "issue" && <IssueForm token={token} onDone={done} />}
      {(editing === "new-book" || (editing && editing.id)) && <BookForm key={editing.id ?? "new"} token={token} book={editing.id ? editing : null} onDone={done} />}

      <nav className="flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button key={t.id} type="button" onClick={() => setTab(t.id)}
            className={`border-b-2 px-3 py-2 text-sm font-semibold ${tab === t.id ? "border-emerald-600 text-emerald-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "settings" && <SettingsForm token={token} onSaved={done} />}

      {isLoanTab &&
        (loanState !== "ready" ? (
          <LoadState state={loanState} onRetry={reloadLoans} what="loans" />
        ) : loans.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">Nothing here.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Book</th>
                  <th className="px-4 py-3">Borrower</th>
                  <th className="px-4 py-3">Issued</th>
                  <th className="px-4 py-3">Due / returned</th>
                  <th className="px-4 py-3">Fine</th>
                  <th className="px-4 py-3 text-right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loans.map((l) => (
                  <tr key={l.id}>
                    <td className="px-4 py-3 font-medium text-slate-800">{l.book_title}</td>
                    <td className="px-4 py-3">
                      <p className="text-slate-800">{l.borrower_name}</p>
                      <p className="text-xs text-slate-400">
                        {l.borrower_code} · {l.borrower_type}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{l.issued_on}</td>
                    <td className={`px-4 py-3 ${!l.returned_on && l.overdue_days ? "font-semibold text-rose-700" : "text-slate-600"}`}>
                      {l.returned_on ? `Returned ${l.returned_on}` : `Due ${l.due_on}`}
                      {!l.returned_on && l.overdue_days > 0 && ` (${l.overdue_days} days late)`}
                    </td>
                    <td className="px-4 py-3">
                      {l.fine > 0 ? (
                        <span className={l.fine_paid ? "text-emerald-700" : "font-semibold text-rose-700"}>
                          {rupees(l.fine)} {l.returned_on ? (l.fine_paid ? "paid" : "due") : "so far"}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {!l.returned_on && (
                          <>
                            <button type="button" className={SECONDARY} onClick={() => act(l, "return", l.fine ? `Return with a fine of ${rupees(l.fine)}?` : null)}>
                              Return
                            </button>
                            {l.overdue_days === 0 && (
                              <button type="button" className={SECONDARY} onClick={() => act(l, "renew")}>
                                Renew
                              </button>
                            )}
                          </>
                        )}
                        {l.returned_on && l.fine > 0 && !l.fine_paid && (
                          <button type="button" className={SECONDARY} onClick={() => act(l, "fine-paid", `Collected ${rupees(l.fine)} from ${l.borrower_name}?`)}>
                            Fine paid
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {tab === "books" && (
        <div className="space-y-3">
          <input type="search" aria-label="Search books" placeholder="Search title, author, ISBN or category" value={query} onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:max-w-md" />
          {bookState !== "ready" ? (
            <LoadState state={bookState} onRetry={reloadBooks} what="books" />
          ) : books.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-500">No books yet.</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Title</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Shelf</th>
                    <th className="px-4 py-3">Available</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {books.map((b) => (
                    <tr key={b.id}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-800">{b.title}</p>
                        <p className="text-xs text-slate-400">{[b.author, b.isbn].filter(Boolean).join(" · ")}</p>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{b.category || "—"}</td>
                      <td className="px-4 py-3 text-slate-600">{b.shelf || "—"}</td>
                      <td className={`px-4 py-3 font-semibold ${b.available ? "text-emerald-700" : "text-rose-700"}`}>
                        {b.available} / {b.total_copies}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <button type="button" className={SECONDARY} onClick={() => setEditing(b)}>
                            Edit
                          </button>
                          <button type="button" className={DANGER} onClick={() => removeBook(b)}>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LibraryPage;

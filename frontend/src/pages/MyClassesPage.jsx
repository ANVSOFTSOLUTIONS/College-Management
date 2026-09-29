import { useCallback, useEffect, useState } from "react";

import { fetchClassRoster, fetchRemarks, fetchTeachingClasses } from "../api/teachingApi";
import { RemarkForm, RemarksList } from "../components/Remarks";
import { useAuth } from "../context/AuthContext";

function MyClassesPage() {
  const { token } = useAuth();
  const [classesState, setClassesState] = useState("loading");
  const [classes, setClasses] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const [rosterState, setRosterState] = useState("idle");
  const [roster, setRoster] = useState([]);
  const [remarks, setRemarks] = useState([]);
  const [remarkFor, setRemarkFor] = useState(null);
  const [notice, setNotice] = useState(null);

  const loadClasses = useCallback(async () => {
    setClassesState("loading");
    try {
      const result = await fetchTeachingClasses(token);
      setClasses(result);
      setSelectedId((current) => current ?? result[0]?.id ?? null);
      setClassesState("ready");
    } catch {
      setClassesState("error");
    }
  }, [token]);

  useEffect(() => {
    loadClasses();
  }, [loadClasses]);

  const loadClass = useCallback(async () => {
    if (!selectedId) return;
    setRosterState("loading");
    setRemarkFor(null);
    try {
      const [students, classRemarks] = await Promise.all([fetchClassRoster(token, selectedId), fetchRemarks(token, { classId: selectedId })]);
      setRoster(students);
      setRemarks(classRemarks);
      setRosterState("ready");
    } catch {
      setRosterState("error");
    }
  }, [token, selectedId]);

  useEffect(() => {
    loadClass();
  }, [loadClass]);

  const selected = classes.find((c) => c.id === selectedId);

  if (classesState === "loading") return <div className="h-32 animate-pulse rounded-xl border border-slate-200 bg-white" />;
  if (classesState === "error") {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-6 py-12 text-center">
        <p className="text-sm font-semibold text-rose-800">Couldn&apos;t load your classes.</p>
        <button type="button" onClick={loadClasses} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white">
          Retry
        </button>
      </div>
    );
  }
  if (classes.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
        <p className="text-sm font-semibold text-slate-600">You don&apos;t teach any class yet.</p>
        <p className="mt-1 text-sm text-slate-400">An admin assigns class and subject teachers in Classes &amp; Subjects.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">My Classes</h2>
        <p className="mt-1 text-sm text-slate-500">Record remarks about students — a missed exam, homework, behaviour — and alert parents when needed.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {classes.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => {
              setNotice(null);
              setSelectedId(c.id);
            }}
            className={`rounded-lg border px-4 py-2 text-left text-sm ${selectedId === c.id ? "border-emerald-500 bg-emerald-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <span className="font-semibold text-slate-800">
              {c.name} - {c.section}
            </span>
            <span className="block text-xs text-slate-500">
              {c.is_class_teacher ? "Class teacher" : c.subjects.map((s) => s.name).join(", ") || "—"} · {c.student_count} students
            </span>
          </button>
        ))}
      </div>

      {notice && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-800">{notice}</p>}

      {rosterState === "loading" && <div className="h-40 animate-pulse rounded-xl border border-slate-200 bg-white" />}
      {rosterState === "error" && (
        <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-800">
          Couldn&apos;t load this class.
          <button type="button" onClick={loadClass} className="underline">
            Retry
          </button>
        </div>
      )}

      {rosterState === "ready" && selected && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="space-y-3">
            <h3 className="text-lg font-semibold text-slate-900">Students</h3>
            {roster.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">No students in this class yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                {roster.map((student) => (
                  <li key={student.id} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-800">{student.full_name}</p>
                        <p className="text-xs text-slate-400">{student.admission_number}</p>
                      </div>
                      {remarkFor?.id !== student.id && (
                        <button
                          type="button"
                          onClick={() => {
                            setNotice(null);
                            setRemarkFor(student);
                          }}
                          className="rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-50"
                        >
                          Add remark
                        </button>
                      )}
                    </div>
                    {remarkFor?.id === student.id && (
                      <div className="mt-3">
                        <RemarkForm
                          token={token}
                          student={student}
                          subjects={selected.subjects}
                          onSaved={(saved) => {
                            setRemarks((prev) => [saved, ...prev]);
                            setRemarkFor(null);
                            setNotice(`Remark saved for ${saved.student_name}.`);
                          }}
                          onCancel={() => setRemarkFor(null)}
                        />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="space-y-3">
            <h3 className="text-lg font-semibold text-slate-900">Recent remarks</h3>
            <RemarksList token={token} remarks={remarks} onDeleted={(id) => setRemarks((prev) => prev.filter((r) => r.id !== id))} />
          </section>
        </div>
      )}
    </div>
  );
}

export default MyClassesPage;

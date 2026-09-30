import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";

import { api, errorText } from "../api";
import { useApi, useAuth } from "../auth";
import { Badge, Button, Card, Chips, colors, H, Input, Loader, Message, Muted, Row, rupees, Screen, Stat } from "../ui";

// Faculty extras (leave approvals, payslips, remarks) and the HOD's department view.

function clock(iso) {
  return iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "";
}

const LEAVE_TONE = { approved: "green", rejected: "red", pending: "amber" };

/** Leave requests waiting for this faculty member: their students' (class teacher) and their department faculty's (HOD). */
export function LeaveInboxScreen() {
  const { token } = useAuth();
  const inbox = useApi("/leave/inbox");
  const [rejecting, setRejecting] = useState(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);

  async function review(leave, status, reason = "") {
    setError(null);
    try {
      await api(`/leave/${leave.id}/review`, { method: "POST", token, body: { status, note: reason } });
      setRejecting(null);
      inbox.reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  const items = inbox.data ?? [];
  const pending = items.filter((l) => l.status === "pending").length;
  return (
    <Screen title="Leave requests" subtitle={`${pending} waiting for you`} refreshing={inbox.loading} onRefresh={inbox.reload}>
      <Message error={error} />
      {rejecting && (
        <Card>
          <H>Reject {rejecting.applicant_name}&apos;s leave</H>
          <Input label="Reason (they will see it)" value={note} onChangeText={setNote} />
          <Row>
            <Button title="Reject" kind="danger" onPress={() => review(rejecting, "rejected", note.trim())} disabled={!note.trim()} style={{ flex: 1 }} />
            <Button title="Cancel" kind="secondary" onPress={() => setRejecting(null)} style={{ flex: 1 }} />
          </Row>
        </Card>
      )}
      <Loader loading={inbox.loading && !inbox.data} error={inbox.error} onRetry={inbox.reload} empty={items.length === 0 ? "No leave requests." : null}>
        {items.map((l) => (
          <Card key={l.id}>
            <Row style={{ justifyContent: "space-between" }}>
              <H>{l.applicant_name}</H>
              <Badge text={l.status} tone={LEAVE_TONE[l.status] ?? "slate"} />
            </Row>
            <Muted>
              {l.applicant_kind === "student" ? `${l.class_name ?? ""}${l.applied_by_parent ? " · by parent" : ""}` : "Faculty"} · {l.leave_type_label}
            </Muted>
            <Muted>
              {l.from_date} → {l.to_date} ({l.days} day{l.days === 1 ? "" : "s"})
            </Muted>
            <Text style={{ color: colors.text, marginTop: 4 }}>{l.reason}</Text>
            {l.review_note ? <Muted>Note: {l.review_note}</Muted> : null}
            {l.can_review && (
              <Row style={{ marginTop: 10 }}>
                <Button title="Approve" small onPress={() => review(l, "approved")} style={{ flex: 1 }} />
                <Button title="Reject" kind="danger" small onPress={() => { setRejecting(l); setNote(""); }} style={{ flex: 1 }} />
              </Row>
            )}
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

export function PayslipsScreen() {
  const slips = useApi("/payroll/mine");
  return (
    <Screen title="Payslips" refreshing={slips.loading} onRefresh={slips.reload}>
      <Loader loading={slips.loading && !slips.data} error={slips.error} onRetry={slips.reload} empty={slips.data?.length === 0 ? "No payslips yet." : null}>
        {(slips.data ?? []).map((s) => (
          <Card key={s.id}>
            <Row style={{ justifyContent: "space-between" }}>
              <H>{s.month}</H>
              <Badge text={s.status === "paid" ? `Paid ${s.paid_on ?? ""}` : s.status} tone={s.status === "paid" ? "green" : "amber"} />
            </Row>
            <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text, marginTop: 4 }}>{rupees(s.net)}</Text>
            <Muted>
              Gross {rupees(s.gross)} · deductions {rupees(s.deductions + s.lop_amount)}
            </Muted>
            <Muted>
              {s.days_present} present · {s.days_leave} leave · {s.lop_days} LOP of {s.working_days} working days
            </Muted>
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

const REMARK_CATEGORIES = [
  { value: "appreciation", label: "Appreciation" },
  { value: "absent_class", label: "Absent from class" },
  { value: "homework", label: "Assignment" },
  { value: "behaviour", label: "Behaviour" },
  { value: "missed_exam", label: "Missed exam" },
  { value: "other", label: "Other" },
];

export function RemarksScreen() {
  const { token } = useAuth();
  const classes = useApi("/teaching/classes");
  const [classId, setClassId] = useState(null);
  const roster = useApi(classId ? `/teaching/classes/${classId}/students` : null);
  const recent = useApi(classId ? "/remarks" : null, { class_id: classId });
  const [form, setForm] = useState({ student_id: null, category: "appreciation", note: "", subject_id: null, notify_parent: true });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!classId && classes.data?.length) setClassId(classes.data[0].id);
  }, [classes.data, classId]);

  const current = (classes.data ?? []).find((c) => c.id === classId);

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api("/remarks", { method: "POST", token, body: form });
      setMessage(form.notify_parent ? "Remark saved; the student and parent can see it." : "Remark saved.");
      setForm({ ...form, student_id: null, note: "" });
      recent.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="Remarks" subtitle="Note something about a student" refreshing={recent.loading} onRefresh={recent.reload}>
      <Loader loading={classes.loading} error={classes.error} onRetry={classes.reload} empty={classes.data?.length === 0 ? "You don't teach any batch yet." : null}>
        <Chips
          options={(classes.data ?? []).map((c) => ({ value: c.id, label: `${c.name} - ${c.section}` }))}
          value={classId}
          onChange={(v) => {
            setClassId(v);
            setForm({ ...form, student_id: null, subject_id: null });
          }}
        />
        <Card>
          <Muted>Student</Muted>
          <View style={{ height: 6 }} />
          <Chips options={(roster.data ?? []).map((s) => ({ value: s.id, label: s.full_name }))} value={form.student_id} onChange={(v) => setForm({ ...form, student_id: v })} />
          {current?.subjects?.length > 0 && (
            <>
              <View style={{ height: 10 }} />
              <Muted>Subject (optional)</Muted>
              <View style={{ height: 6 }} />
              <Chips
                options={current.subjects.map((s) => ({ value: s.id, label: s.name }))}
                value={form.subject_id}
                onChange={(v) => setForm({ ...form, subject_id: form.subject_id === v ? null : v })}
              />
            </>
          )}
          <View style={{ height: 10 }} />
          <Chips options={REMARK_CATEGORIES} value={form.category} onChange={(v) => setForm({ ...form, category: v })} />
          <View style={{ height: 10 }} />
          <Input label="Note" value={form.note} onChangeText={(v) => setForm({ ...form, note: v })} multiline style={{ minHeight: 60, textAlignVertical: "top" }} />
          <Pressable onPress={() => setForm({ ...form, notify_parent: !form.notify_parent })} style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <View style={{ width: 20, height: 20, borderRadius: 4, borderWidth: 2, borderColor: colors.brand, backgroundColor: form.notify_parent ? colors.brand : colors.white }} />
            <Text style={{ color: colors.text }}>Show to student and parent</Text>
          </Pressable>
          <Message text={message} error={error} />
          <Button title="Save remark" onPress={save} loading={busy} disabled={!form.student_id} />
        </Card>
        {(recent.data ?? []).slice(0, 20).map((r) => (
          <Card key={r.id}>
            <Row style={{ justifyContent: "space-between" }}>
              <H>{r.student_name}</H>
              <Badge text={r.category_label} tone={r.category === "appreciation" ? "green" : "amber"} />
            </Row>
            {r.note ? <Text style={{ color: colors.text }}>{r.note}</Text> : null}
            <Muted>
              {r.remark_date}
              {r.subject_name ? ` · ${r.subject_name}` : ""} · {r.author_name}
            </Muted>
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

const FACULTY_STATUS = { in: ["In", "green"], late: ["Late", "amber"], not_in: ["Not in", "red"], on_leave: ["On leave", "blue"] };

export function DepartmentScreen({ onOpenLeaves }) {
  const view = useApi("/hod/overview");
  const data = view.data;
  return (
    <Screen title="Department" subtitle={data ? `Today · ${data.date}` : null} refreshing={view.loading} onRefresh={view.reload}>
      <Loader loading={view.loading && !data} error={view.error} onRetry={view.reload}>
        {data && (
          <>
            {data.pending_leaves > 0 && (
              <Card onPress={onOpenLeaves} style={{ borderColor: "#fcd34d", backgroundColor: colors.warnSoft }}>
                <Text style={{ fontWeight: "700", color: colors.warn }}>
                  {data.pending_leaves} faculty leave request{data.pending_leaves === 1 ? "" : "s"} waiting for you ›
                </Text>
              </Card>
            )}
            {data.departments.map((d) => {
              const inToday = d.faculty.filter((f) => f.status === "in" || f.status === "late").length;
              return (
                <View key={d.id} style={{ gap: 12 }}>
                  <Text style={{ fontSize: 18, fontWeight: "800", color: colors.text }}>
                    {d.name} ({d.code})
                  </Text>
                  <Row>
                    <Stat label="Faculty in" value={`${inToday}/${d.faculty.length}`} />
                    <Stat label="Students" value={d.students} />
                    <Stat label="Below 75%" value={d.low_attendance.length} tone={d.low_attendance.length ? "red" : undefined} />
                  </Row>
                  <Card>
                    <H>Faculty today</H>
                    {d.faculty.map((f) => (
                      <Row key={f.teacher_id} style={{ justifyContent: "space-between", marginTop: 8 }}>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontWeight: "600", color: colors.text }}>{f.full_name}</Text>
                          <Muted>
                            {f.designation}
                            {f.punch_in_at ? ` · in at ${clock(f.punch_in_at)}` : ""}
                          </Muted>
                        </View>
                        <Badge text={FACULTY_STATUS[f.status][0]} tone={FACULTY_STATUS[f.status][1]} />
                      </Row>
                    ))}
                  </Card>
                  <Card>
                    <H>Batch attendance today</H>
                    {d.batches.length === 0 && <Muted>No batches yet.</Muted>}
                    {d.batches.map((b) => (
                      <Row key={b.class_id} style={{ justifyContent: "space-between", marginTop: 8 }}>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontWeight: "600", color: colors.text }}>
                            {b.name} - {b.section}
                          </Text>
                          <Muted>
                            {b.semester ? `Sem ${b.semester} · ` : ""}
                            {b.students} students
                          </Muted>
                        </View>
                        {b.marked ? <Badge text={`${b.present} P · ${b.absent} A`} tone={b.absent ? "amber" : "green"} /> : <Badge text="Not marked" tone="red" />}
                      </Row>
                    ))}
                  </Card>
                  {d.low_attendance.length > 0 && (
                    <Card>
                      <H>Attendance below 75% (last 30 days)</H>
                      {d.low_attendance.map((s) => (
                        <Row key={s.student_id} style={{ justifyContent: "space-between", marginTop: 8 }}>
                          <View style={{ flex: 1 }}>
                            <Text style={{ fontWeight: "600", color: colors.text }}>{s.full_name}</Text>
                            <Muted>
                              {s.admission_number} · {s.batch}
                            </Muted>
                          </View>
                          <Text style={{ fontWeight: "800", color: colors.danger }}>{s.percent}%</Text>
                        </Row>
                      ))}
                    </Card>
                  )}
                </View>
              );
            })}
          </>
        )}
      </Loader>
    </Screen>
  );
}

import { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { api, errorText } from "../api";
import { useApi, useAuth } from "../auth";
import { Badge, Button, Card, Chips, colors, H, Input, Loader, Message, Muted, Row, Screen, Stat, styles, today } from "../ui";

function clock(iso) {
  return iso ? new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "—";
}

export function PunchScreen() {
  const { token, user } = useAuth();
  const me = useApi("/staff-punch/me");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const t = me.data?.today;

  async function punch(direction) {
    setBusy(true);
    setError(null);
    try {
      await api(`/staff-punch/${direction}`, { method: "POST", token });
      me.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title={`Hi, ${user.full_name.split(" ")[0]}`} subtitle="Punch in when you reach college" refreshing={me.loading} onRefresh={me.reload}>
      <Loader loading={me.loading && !me.data} error={me.error} onRetry={me.reload}>
        {t && (
          <>
            <Card style={{ alignItems: "center", paddingVertical: 24 }}>
              <Muted>Today · college starts {me.data.day_starts_at}</Muted>
              <Row style={{ marginTop: 12, gap: 24 }}>
                <View style={{ alignItems: "center" }}>
                  <Muted>In</Muted>
                  <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text }}>{clock(t.punch_in_at)}</Text>
                </View>
                <View style={{ alignItems: "center" }}>
                  <Muted>Out</Muted>
                  <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text }}>{clock(t.punch_out_at)}</Text>
                </View>
              </Row>
              {t.is_late && <Badge text="Late" tone="amber" />}
              <View style={{ width: "100%", marginTop: 16 }}>
                {!t.punch_in_at ? (
                  <Button title="Punch in" onPress={() => punch("in")} loading={busy} />
                ) : !t.punch_out_at ? (
                  <Button title="Punch out" kind="secondary" onPress={() => punch("out")} loading={busy} />
                ) : (
                  <Muted style={{ textAlign: "center" }}>Done for today · {Math.round((t.worked_minutes ?? 0) / 6) / 10} hours</Muted>
                )}
              </View>
            </Card>
            <Message error={error} />
            <Card>
              <H>Recent days</H>
              {me.data.recent.map((d) => (
                <Row key={d.date} style={{ justifyContent: "space-between", marginTop: 8 }}>
                  <Text style={{ color: colors.text }}>{d.date}</Text>
                  <Muted>
                    {clock(d.punch_in_at)} – {clock(d.punch_out_at)}
                  </Muted>
                  {d.is_late ? <Badge text="Late" tone="amber" /> : <Badge text="On time" tone="green" />}
                </Row>
              ))}
            </Card>
          </>
        )}
      </Loader>
    </Screen>
  );
}

const NEXT_STATUS = { present: "absent", absent: "late", late: "present" };
const STATUS_COLORS = { present: colors.brand, absent: colors.danger, late: "#f59e0b" };

export function AttendanceScreen() {
  const { token } = useAuth();
  const classes = useApi("/classes");
  const [classId, setClassId] = useState(null);
  const [date, setDate] = useState(today());
  const sheet = useApi(classId ? `/classes/${classId}/attendance` : null, { date });
  const [marks, setMarks] = useState({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!classId && classes.data?.length) setClassId(classes.data[0].id);
  }, [classes.data, classId]);

  useEffect(() => {
    if (sheet.data) setMarks(Object.fromEntries(sheet.data.entries.map((e) => [e.student_id, e.status ?? (e.on_leave ? "absent" : "present")])));
  }, [sheet.data]);

  const entries = sheet.data?.entries ?? [];
  const counts = entries.reduce((c, e) => ({ ...c, [marks[e.student_id]]: (c[marks[e.student_id]] ?? 0) + 1 }), {});
  const alreadyMarked = entries.some((e) => e.status);

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api(`/classes/${classId}/attendance`, {
        method: "POST",
        token,
        body: { date, records: entries.map((e) => ({ student_id: e.student_id, status: marks[e.student_id] })) },
      });
      setMessage(`Attendance saved for ${date}. Parents of absent students are alerted.`);
      sheet.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="Attendance" subtitle="Tap a student to switch present → absent → late" refreshing={sheet.loading} onRefresh={sheet.reload}>
      <Loader loading={classes.loading} error={classes.error} onRetry={classes.reload} empty={classes.data?.length === 0 ? "You're not the class teacher of any batch." : null}>
        <Chips options={(classes.data ?? []).map((c) => ({ value: c.id, label: `${c.name} - ${c.section}` }))} value={classId} onChange={setClassId} />
        <Row>
          <View style={{ flex: 1 }}>
            <Input label="Date (YYYY-MM-DD)" value={date} onChangeText={setDate} />
          </View>
          <Button title="Today" kind="secondary" small onPress={() => setDate(today())} style={{ marginTop: 8 }} />
        </Row>
        <Row>
          <Stat label="Present" value={counts.present ?? 0} tone="green" />
          <Stat label="Absent" value={counts.absent ?? 0} tone="red" />
          <Stat label="Late" value={counts.late ?? 0} />
        </Row>
        <Loader loading={sheet.loading && !sheet.data} error={sheet.error} onRetry={sheet.reload}>
          <Card style={{ padding: 0 }}>
            {entries.map((e, i) => {
              const status = marks[e.student_id] ?? "present";
              return (
                <Pressable
                  key={e.student_id}
                  onPress={() => setMarks({ ...marks, [e.student_id]: NEXT_STATUS[status] })}
                  style={{ flexDirection: "row", alignItems: "center", padding: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontWeight: "600", color: colors.text }}>{e.full_name}</Text>
                    <Muted>
                      {e.admission_number}
                      {e.on_leave ? " · on approved leave" : ""}
                    </Muted>
                  </View>
                  <View style={{ backgroundColor: STATUS_COLORS[status], borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6, minWidth: 76, alignItems: "center" }}>
                    <Text style={{ color: colors.white, fontWeight: "700", textTransform: "capitalize" }}>{status}</Text>
                  </View>
                </Pressable>
              );
            })}
          </Card>
          <Message text={message} error={error} />
          {entries.length > 0 && <Button title={alreadyMarked ? "Update attendance" : "Save attendance"} onPress={save} loading={busy} />}
        </Loader>
      </Loader>
    </Screen>
  );
}

function MarkSheet({ paper, onBack }) {
  const { token } = useAuth();
  const sheet = useApi(`/exam-papers/${paper.id}/marks`);
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (sheet.data) {
      setValues(Object.fromEntries(sheet.data.rows.map((r) => [r.student_id, r.is_absent ? "AB" : r.marks === null ? "" : String(r.marks)])));
    }
  }, [sheet.data]);

  const locked = paper.published || !paper.can_enter_marks;

  async function save() {
    setError(null);
    setMessage(null);
    const entries = [];
    for (const r of sheet.data.rows) {
      const raw = (values[r.student_id] ?? "").trim().toUpperCase();
      if (raw === "AB") entries.push({ student_id: r.student_id, is_absent: true });
      else if (raw === "") entries.push({ student_id: r.student_id, marks: null });
      else {
        const n = Number(raw);
        if (Number.isNaN(n) || n < 0 || n > paper.max_marks) return setError(`${r.full_name}: enter 0 to ${paper.max_marks}, or AB for absent.`);
        entries.push({ student_id: r.student_id, marks: String(n) });
      }
    }
    setBusy(true);
    try {
      await api(`/exam-papers/${paper.id}/marks`, { method: "PUT", token, body: { entries } });
      setMessage("Marks saved.");
      sheet.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen
      title={paper.subject_name}
      subtitle={`${paper.exam_name} · ${paper.class_name} - ${paper.section} · max ${paper.max_marks}, pass ${paper.pass_marks}`}
      refreshing={sheet.loading}
      onRefresh={sheet.reload}
    >
      <Button title="← All papers" kind="secondary" small onPress={onBack} style={{ alignSelf: "flex-start" }} />
      {locked && <Message error={paper.published ? "Results are published, so marks are locked." : "Only the subject's faculty can enter these marks."} />}
      <Loader loading={sheet.loading && !sheet.data} error={sheet.error} onRetry={sheet.reload}>
        <Card style={{ padding: 0 }}>
          {(sheet.data?.rows ?? []).map((r, i) => {
            const raw = values[r.student_id] ?? "";
            const fail = raw !== "" && raw.toUpperCase() !== "AB" && Number(raw) < paper.pass_marks;
            return (
              <View key={r.student_id} style={{ flexDirection: "row", alignItems: "center", padding: 10, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "600", color: colors.text }}>{r.full_name}</Text>
                  <Muted>{r.admission_number}</Muted>
                </View>
                <TextInput
                  editable={!locked}
                  value={raw}
                  onChangeText={(v) => setValues({ ...values, [r.student_id]: v })}
                  keyboardType="default"
                  autoCapitalize="characters"
                  placeholder="—"
                  style={[styles.input, { width: 72, textAlign: "center", paddingVertical: 6 }, fail && { borderColor: colors.danger, color: colors.danger }]}
                />
              </View>
            );
          })}
        </Card>
        <Muted>Type marks, or AB for absent. Leave empty to clear.</Muted>
        <Message text={message} error={error} />
        {!locked && <Button title="Save marks" onPress={save} loading={busy} />}
      </Loader>
    </Screen>
  );
}

export function MarksScreen() {
  const papers = useApi("/exam-papers/mine");
  const [open, setOpen] = useState(null);
  if (open) return <MarkSheet paper={open} onBack={() => { setOpen(null); papers.reload(); }} />;
  return (
    <Screen title="Marks entry" subtitle="Papers of the subjects you teach" refreshing={papers.loading} onRefresh={papers.reload}>
      <Loader loading={papers.loading && !papers.data} error={papers.error} onRetry={papers.reload} empty={papers.data?.length === 0 ? "No exam papers for your subjects yet." : null}>
        {(papers.data ?? []).map((p) => (
          <Card key={p.id} onPress={() => setOpen(p)}>
            <Row style={{ justifyContent: "space-between" }}>
              <H>{p.subject_name}</H>
              {p.published ? <Badge text="Published" tone="green" /> : <Badge text={`${p.entered}/${p.students} entered`} tone={p.entered === p.students ? "green" : "amber"} />}
            </Row>
            <Muted>
              {p.exam_name} · {p.class_name} - {p.section}
            </Muted>
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

export function FacultyAssignmentsScreen() {
  const { token } = useAuth();
  const options = useApi("/homework/options");
  const list = useApi("/homework");
  const [form, setForm] = useState({ class_id: null, subject_id: null, title: "", details: "", due_on: today() });
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const classes = options.data ?? [];
  const subjects = classes.find((c) => c.id === form.class_id)?.subjects ?? [];

  async function post() {
    setBusy(true);
    setError(null);
    try {
      await api("/homework", { method: "POST", token, body: form });
      setAdding(false);
      setForm({ ...form, title: "", details: "" });
      list.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    try {
      await api(`/homework/${id}`, { method: "DELETE", token });
      list.reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Screen
      title="Assignments"
      refreshing={list.loading}
      onRefresh={list.reload}
      right={!adding && classes.length > 0 ? <Button title="+ New" small onPress={() => setAdding(true)} /> : null}
    >
      {adding && (
        <Card>
          <H>New assignment</H>
          <View style={{ height: 8 }} />
          <Chips options={classes.map((c) => ({ value: c.id, label: `${c.name} - ${c.section}` }))} value={form.class_id}
            onChange={(v) => setForm({ ...form, class_id: v, subject_id: null })} />
          {subjects.length > 0 && (
            <>
              <View style={{ height: 8 }} />
              <Chips options={subjects.map((s) => ({ value: s.id, label: s.name }))} value={form.subject_id} onChange={(v) => setForm({ ...form, subject_id: v })} />
            </>
          )}
          <View style={{ height: 12 }} />
          <Input label="Title" value={form.title} onChangeText={(v) => setForm({ ...form, title: v })} />
          <Input label="Details" value={form.details} onChangeText={(v) => setForm({ ...form, details: v })} multiline style={{ minHeight: 80, textAlignVertical: "top" }} />
          <Input label="Due date (YYYY-MM-DD)" value={form.due_on} onChangeText={(v) => setForm({ ...form, due_on: v })} />
          <Message error={error} />
          <Row style={{ marginTop: 8 }}>
            <Button title="Post" onPress={post} loading={busy} disabled={!form.class_id || !form.subject_id || form.title.trim().length < 3} style={{ flex: 1 }} />
            <Button title="Cancel" kind="secondary" onPress={() => setAdding(false)} style={{ flex: 1 }} />
          </Row>
        </Card>
      )}
      <Loader loading={list.loading && !list.data} error={list.error} onRetry={list.reload} empty={list.data?.length === 0 ? "No assignments posted yet." : null}>
        {(list.data ?? []).map((h) => (
          <Card key={h.id}>
            <Row style={{ justifyContent: "space-between" }}>
              <Text style={{ color: colors.brandDark, fontWeight: "700", fontSize: 12 }}>
                {h.subject_name.toUpperCase()} · {h.class_name} - {h.section}
              </Text>
              <Badge text={`Due ${h.due_on}`} tone="blue" />
            </Row>
            <H>{h.title}</H>
            {h.details ? <Text style={{ color: colors.text, marginTop: 4 }}>{h.details}</Text> : null}
            <Button title="Delete" kind="danger" small onPress={() => remove(h.id)} style={{ alignSelf: "flex-start", marginTop: 8 }} />
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

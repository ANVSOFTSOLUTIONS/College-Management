import { useState } from "react";
import { Linking, Pressable, Text, View } from "react-native";

import { api, errorText, WEB_URL } from "../api";
import { useApi, useAuth } from "../auth";
import { Badge, Button, Card, Chips, colors, H, Input, Loader, Message, Muted, Row, rupees, Screen, Stat, today } from "../ui";

// Screens for students and parents. A student's "children" list is just themselves.

const STATUS_TONE = { present: "green", absent: "red", late: "amber" };

export function ChildPicker({ children, childId, onChange }) {
  if (!children || children.length < 2) return null;
  return <Chips options={children.map((c) => ({ value: c.student_id, label: c.full_name.split(" ")[0] }))} value={childId} onChange={onChange} />;
}

export function HomeScreen({ childId, header }) {
  const { user } = useAuth();
  const overview = useApi(childId ? `/me/parent/children/${childId}` : null);
  const library = useApi(childId ? `/me/parent/children/${childId}/library` : null);
  const hostel = useApi(childId ? `/me/parent/children/${childId}/hostel` : null);
  const transport = useApi(childId ? `/me/parent/children/${childId}/transport` : null);
  const reloadAll = () => [overview, library, hostel, transport].forEach((q) => q.reload());
  const o = overview.data;
  const pct = o && o.attendance_days ? Math.round(((o.present + o.late) * 100) / o.attendance_days) : null;
  const openLoans = (library.data ?? []).filter((l) => !l.returned_on || (l.fine > 0 && !l.fine_paid));

  return (
    <Screen title={user.role === "student" ? `Hi, ${user.full_name.split(" ")[0]}` : "My children"} refreshing={overview.loading} onRefresh={reloadAll}>
      {header}
      <Loader loading={overview.loading && !o} error={overview.error} onRetry={overview.reload}>
        {o && (
          <>
            <Card>
              <H>{o.child.full_name}</H>
              <Muted>
                {o.child.admission_number} · {o.child.class_name} - {o.child.section}
              </Muted>
              <Muted>{o.child.school_name}</Muted>
            </Card>
            <Row>
              <Stat label="Attendance (30 days)" value={pct === null ? "—" : `${pct}%`} tone={pct !== null && pct < 75 ? "red" : "green"} />
              <Stat label="Fees due" value={rupees(o.fees.balance)} tone={o.fees.overdue > 0 ? "red" : undefined} />
            </Row>
            {pct !== null && pct < 75 && (
              <Message error="Attendance is below 75%. Most universities need 75% to write the semester exams." />
            )}
            {o.recent_attendance.length > 0 && (
              <Card>
                <H>Recent attendance</H>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                  {o.recent_attendance.map((d) => (
                    <View key={d.date} style={{ alignItems: "center", width: 40 }}>
                      <View style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: { present: colors.brand, absent: colors.danger, late: "#f59e0b" }[d.status] }} />
                      <Text style={{ fontSize: 10, color: colors.muted }}>{d.date.slice(8)}</Text>
                    </View>
                  ))}
                </View>
              </Card>
            )}
            {o.fees.lines.filter((l) => l.balance > 0).length > 0 && (
              <Card>
                <H>Fees to pay</H>
                {o.fees.lines
                  .filter((l) => l.balance > 0)
                  .map((l) => (
                    <Row key={l.id} style={{ justifyContent: "space-between", marginTop: 8 }}>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontWeight: "600", color: colors.text }}>{l.name}</Text>
                        <Muted>Due {l.due_date}</Muted>
                      </View>
                      <Text style={{ fontWeight: "700", color: l.status === "overdue" ? colors.danger : colors.text }}>{rupees(l.balance)}</Text>
                    </Row>
                  ))}
                {o.online_payment_enabled && WEB_URL ? (
                  <Button title="Pay online" style={{ marginTop: 12 }} onPress={() => Linking.openURL(`${WEB_URL}/?as=${user.role}`)} />
                ) : (
                  <Muted style={{ marginTop: 8 }}>Pay at the college office{o.online_payment_enabled ? " or on the college website" : ""}.</Muted>
                )}
              </Card>
            )}
            {hostel.data && (
              <Card>
                <H>Hostel</H>
                <Text style={{ marginTop: 4, color: colors.text }}>
                  {hostel.data.hostel_name} · Room {hostel.data.room_number}
                </Text>
                {hostel.data.roommates.length > 0 && <Muted>Roommates: {hostel.data.roommates.join(", ")}</Muted>}
                {hostel.data.warden_phone ? (
                  <Pressable onPress={() => Linking.openURL(`tel:${hostel.data.warden_phone}`)}>
                    <Text style={{ color: colors.brand, marginTop: 4 }}>Call warden {hostel.data.warden_name}</Text>
                  </Pressable>
                ) : null}
              </Card>
            )}
            {transport.data && (
              <Card>
                <H>College bus</H>
                <Text style={{ marginTop: 4, color: colors.text }}>{transport.data.route_name}</Text>
                {transport.data.stop_name && (
                  <Muted>
                    Boards at {transport.data.stop_name}
                    {transport.data.pickup_time ? ` · ${transport.data.pickup_time}` : ""}
                  </Muted>
                )}
                {transport.data.driver_phone ? (
                  <Pressable onPress={() => Linking.openURL(`tel:${transport.data.driver_phone}`)}>
                    <Text style={{ color: colors.brand, marginTop: 4 }}>Call driver {transport.data.driver_name}</Text>
                  </Pressable>
                ) : null}
              </Card>
            )}
            {openLoans.length > 0 && (
              <Card>
                <H>Library books</H>
                {openLoans.map((l) => (
                  <View key={l.id} style={{ marginTop: 8 }}>
                    <Text style={{ fontWeight: "600", color: colors.text }}>{l.book_title}</Text>
                    <Muted style={l.overdue_days ? { color: colors.danger } : undefined}>
                      {l.returned_on ? `Fine due ${rupees(l.fine)}` : `Return by ${l.due_on}${l.overdue_days ? ` · ${l.overdue_days} days late (${rupees(l.fine)})` : ""}`}
                    </Muted>
                  </View>
                ))}
              </Card>
            )}
            {o.remarks.length > 0 && (
              <Card>
                <H>Remarks from faculty</H>
                {o.remarks.slice(0, 5).map((r, i) => (
                  <View key={i} style={{ marginTop: 8 }}>
                    <Text style={{ fontWeight: "600", color: colors.text }}>
                      {r.category_label}
                      {r.subject_name ? ` · ${r.subject_name}` : ""}
                    </Text>
                    <Text style={{ color: colors.text }}>{r.note}</Text>
                    <Muted>
                      {r.author_name} · {r.remark_date}
                    </Muted>
                  </View>
                ))}
              </Card>
            )}
          </>
        )}
      </Loader>
    </Screen>
  );
}

export function ResultsScreen({ childId, header }) {
  const results = useApi(childId ? `/me/parent/children/${childId}/results` : null);
  return (
    <Screen title="Results" subtitle="Grades, SGPA and CGPA" refreshing={results.loading} onRefresh={results.reload}>
      {header}
      <Loader loading={results.loading && !results.data} error={results.error} onRetry={results.reload} empty={results.data?.length === 0 ? "No results published yet." : null}>
        {(results.data ?? []).map(({ exam_id, report_card: card }) => (
          <Card key={exam_id}>
            <Row style={{ justifyContent: "space-between" }}>
              <View style={{ flex: 1 }}>
                <H>{card.exam_name}</H>
                <Muted>{[card.term_label, card.academic_year, card.semester && `Sem ${card.semester}`].filter(Boolean).join(" · ")}</Muted>
              </View>
              <Badge text={card.exam_type === "internal" ? "Internal" : "Semester"} tone="blue" />
            </Row>
            {card.result.papers.map((p) => (
              <Row key={p.subject_name} style={{ justifyContent: "space-between", marginTop: 8 }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.text, fontWeight: "600" }}>{p.subject_name}</Text>
                  <Muted>
                    {p.credits} credits · {p.is_absent ? "Absent" : p.marks === null ? "—" : `${p.marks}/${p.max_marks}`}
                  </Muted>
                </View>
                <Badge text={p.grade ?? "—"} tone={p.passed === false ? "red" : "green"} />
              </Row>
            ))}
            <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}>
              <Stat label="SGPA" value={card.result.sgpa ?? "—"} />
              <Stat label="CGPA" value={card.cgpa ?? "—"} tone="green" />
              <Stat label="Credits" value={`${card.result.credits_earned}/${card.result.credits_total}`} />
            </View>
            {card.result.passed === false && <Muted style={{ color: colors.danger, marginTop: 8 }}>Backlog in one or more subjects.</Muted>}
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

export function AssignmentsScreen({ childId, header }) {
  const list = useApi(childId ? "/homework" : null, { student_id: childId });
  const now = today();
  return (
    <Screen title="Assignments" refreshing={list.loading} onRefresh={list.reload}>
      {header}
      <Loader loading={list.loading && !list.data} error={list.error} onRetry={list.reload} empty={list.data?.length === 0 ? "No assignments right now." : null}>
        {(list.data ?? []).map((h) => (
          <Card key={h.id}>
            <Row style={{ justifyContent: "space-between" }}>
              <Text style={{ color: colors.brandDark, fontWeight: "700", fontSize: 12 }}>{h.subject_name.toUpperCase()}</Text>
              <Badge text={h.due_on < now ? `Was due ${h.due_on}` : `Due ${h.due_on}`} tone={h.due_on < now ? "slate" : h.due_on === now ? "amber" : "blue"} />
            </Row>
            <H>{h.title}</H>
            {h.details ? <Text style={{ color: colors.text, marginTop: 4 }}>{h.details}</Text> : null}
            <Muted style={{ marginTop: 6 }}>
              {h.posted_by_name} · given {h.assigned_on}
            </Muted>
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

export function NoticesScreen({ header }) {
  const list = useApi("/notices");
  return (
    <Screen title="Notices" refreshing={list.loading} onRefresh={list.reload}>
      {header}
      <Loader loading={list.loading && !list.data} error={list.error} onRetry={list.reload} empty={list.data?.length === 0 ? "No notices." : null}>
        {(list.data ?? []).map((n) => (
          <Card key={n.id} style={n.is_pinned ? { borderColor: colors.brand } : undefined}>
            {n.is_pinned && <Badge text="Pinned" tone="green" />}
            <H>{n.title}</H>
            <Text style={{ color: colors.text, marginTop: 4 }}>{n.body}</Text>
            <Muted style={{ marginTop: 6 }}>
              {n.posted_by_name} · {n.created_at.slice(0, 10)}
            </Muted>
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function TimetableScreen({ childId, header }) {
  const tt = useApi("/timetable/mine", childId ? { student_id: childId } : undefined);
  const [day, setDay] = useState(Math.min(Math.max(new Date().getDay() - 1, 0), 5));
  const data = tt.data;
  return (
    <Screen title="Timetable" subtitle={data?.title} refreshing={tt.loading} onRefresh={tt.reload}>
      {header}
      <Chips options={DAYS.map((d, i) => ({ value: i, label: d }))} value={day} onChange={setDay} />
      <Loader loading={tt.loading && !data} error={tt.error} onRetry={tt.reload} empty={data && data.periods.length === 0 ? "The timetable isn't set up yet." : null}>
        {data?.periods.map((p) => {
          const cells = data.cells.filter((c) => c.weekday === day && c.period_id === p.id);
          return (
            <Card key={p.id} style={p.is_break ? { backgroundColor: "#f1f5f9" } : undefined}>
              <Row style={{ justifyContent: "space-between" }}>
                <Text style={{ fontWeight: "700", color: colors.text }}>{p.label}</Text>
                <Muted>
                  {p.start_time} – {p.end_time}
                </Muted>
              </Row>
              {p.is_break ? (
                <Muted>Break</Muted>
              ) : cells.length ? (
                cells.map((c, i) => (
                  <Muted key={i}>
                    {c.subject_name}
                    {c.teacher_name ? ` · ${c.teacher_name}` : ""}
                    {c.class_label && !childId ? ` · ${c.class_label}` : ""}
                  </Muted>
                ))
              ) : (
                <Muted>Free</Muted>
              )}
            </Card>
          );
        })}
      </Loader>
    </Screen>
  );
}

const LEAVE_TYPES = [
  { value: "sick", label: "Sick" },
  { value: "casual", label: "Casual" },
  { value: "family", label: "Family" },
  { value: "other", label: "Other" },
];

export function LeaveScreen({ childId, header }) {
  const { token } = useAuth();
  const mine = useApi("/leave/mine");
  const [form, setForm] = useState({ leave_type: "sick", from_date: today(), to_date: today(), reason: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function apply() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api("/leave", { method: "POST", token, body: { ...form, student_id: childId || null } });
      setMessage("Leave request sent.");
      setForm({ ...form, reason: "" });
      mine.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function cancel(id) {
    try {
      await api(`/leave/${id}/cancel`, { method: "POST", token });
      mine.reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Screen title="Leave" refreshing={mine.loading} onRefresh={mine.reload}>
      {header}
      <Card>
        <H>Apply for leave</H>
        <View style={{ height: 8 }} />
        <Chips options={LEAVE_TYPES} value={form.leave_type} onChange={(v) => setForm({ ...form, leave_type: v })} />
        <View style={{ height: 12 }} />
        <Row>
          <View style={{ flex: 1 }}>
            <Input label="From (YYYY-MM-DD)" value={form.from_date} onChangeText={(v) => setForm({ ...form, from_date: v })} />
          </View>
          <View style={{ flex: 1 }}>
            <Input label="To" value={form.to_date} onChangeText={(v) => setForm({ ...form, to_date: v })} />
          </View>
        </Row>
        <Input label="Reason" value={form.reason} onChangeText={(v) => setForm({ ...form, reason: v })} multiline style={{ minHeight: 70, textAlignVertical: "top" }} />
        <Message text={message} error={error} />
        <Button title="Send request" onPress={apply} loading={busy} disabled={form.reason.trim().length < 3} style={{ marginTop: 8 }} />
      </Card>
      <Loader loading={mine.loading && !mine.data} error={mine.error} onRetry={mine.reload}>
        {(mine.data ?? []).map((l) => (
          <Card key={l.id}>
            <Row style={{ justifyContent: "space-between" }}>
              <H>
                {l.leave_type_label} · {l.days} day{l.days === 1 ? "" : "s"}
              </H>
              <Badge text={l.status} tone={{ approved: "green", rejected: "red", pending: "amber" }[l.status] ?? "slate"} />
            </Row>
            <Muted>
              {l.from_date} → {l.to_date}
              {l.applicant_kind === "student" ? ` · ${l.applicant_name}` : ""}
            </Muted>
            <Text style={{ color: colors.text, marginTop: 4 }}>{l.reason}</Text>
            {l.review_note ? <Muted>Note: {l.review_note}</Muted> : null}
            {l.status === "pending" && <Button title="Cancel request" kind="danger" small onPress={() => cancel(l.id)} style={{ marginTop: 8, alignSelf: "flex-start" }} />}
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

export function PlacementsScreen() {
  const { token } = useAuth();
  const drives = useApi("/placements/my-drives");
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  async function act(drive, withdraw) {
    setError(null);
    setMessage(null);
    try {
      await api(`/placements/drives/${drive.id}/apply`, { method: withdraw ? "DELETE" : "POST", token });
      setMessage(withdraw ? "Application withdrawn." : `Applied to ${drive.company_name}.`);
      drives.reload();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Screen title="Placements" subtitle="Drives you can apply to" refreshing={drives.loading} onRefresh={drives.reload}>
      <Message text={message} error={error} />
      <Loader loading={drives.loading && !drives.data} error={drives.error} onRetry={drives.reload} empty={drives.data?.length === 0 ? "No open drives right now." : null}>
        {(drives.data ?? []).map((d) => (
          <Card key={d.id}>
            <Text style={{ color: colors.brandDark, fontWeight: "700", fontSize: 12 }}>{d.company_name.toUpperCase()}</Text>
            <H>{d.role_title}</H>
            <Muted>
              {[d.package_lpa !== null && `${d.package_lpa} LPA`, d.location, d.last_date && `Apply by ${d.last_date}`, d.min_cgpa !== null && `CGPA ≥ ${d.min_cgpa}`]
                .filter(Boolean)
                .join(" · ")}
            </Muted>
            {d.description ? <Text style={{ color: colors.text, marginTop: 6 }}>{d.description}</Text> : null}
            <View style={{ marginTop: 10 }}>
              {d.my_status ? (
                <Row style={{ justifyContent: "space-between" }}>
                  <Badge text={d.my_status} tone={{ selected: "green", rejected: "red", shortlisted: "amber" }[d.my_status] ?? "blue"} />
                  {d.my_status === "applied" && <Button title="Withdraw" kind="danger" small onPress={() => act(d, true)} />}
                </Row>
              ) : d.eligible ? (
                <Button title="Apply" onPress={() => act(d, false)} />
              ) : (
                <Muted style={{ color: colors.warn }}>Not eligible: {d.reason}</Muted>
              )}
            </View>
          </Card>
        ))}
      </Loader>
    </Screen>
  );
}

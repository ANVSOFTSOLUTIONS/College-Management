import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import { AuthProvider, useApi, useAuth } from "./src/auth";
import { AttendanceScreen, FacultyAssignmentsScreen, MarksScreen, PunchScreen } from "./src/screens/FacultyScreens";
import { ChangePasswordScreen, LoginScreen } from "./src/screens/LoginScreen";
import { DepartmentScreen, FeedbackScoresScreen, LeaveInboxScreen, PayslipsScreen, RemarksScreen, SubjectAttendanceScreen } from "./src/screens/StaffExtraScreens";
import {
  AssignmentsScreen,
  ChildPicker,
  ElectivesScreen,
  FeedbackScreen,
  GrievancesScreen,
  HallTicketScreen,
  ScholarshipsCertificatesScreen,
  HomeScreen,
  LeaveScreen,
  NoticesScreen,
  PlacementsScreen,
  ResultsScreen,
  TimetableScreen,
} from "./src/screens/PortalScreens";
import { Card, colors, H, Muted, Screen } from "./src/ui";

// Tabs per role; `module` hides a tab when the college has that module switched off.
const FACULTY_TABS = [
  { id: "department", label: "Dept", icon: "🏛", hodOnly: true },
  { id: "punch", label: "Punch", icon: "⏱" },
  { id: "attendance", label: "Attendance", icon: "✓" },
  { id: "marks", label: "Marks", icon: "✎", module: "exams" },
  { id: "assignments", label: "Assign", icon: "📚", module: "homework" },
  { id: "more", label: "More", icon: "☰" },
];
const PORTAL_TABS = [
  { id: "home", label: "Home", icon: "⌂" },
  { id: "results", label: "Results", icon: "★", module: "exams" },
  { id: "assignments", label: "Assign", icon: "📚", module: "homework" },
  { id: "notices", label: "Notices", icon: "📢", module: "notices" },
  { id: "more", label: "More", icon: "☰" },
];
const MORE_ITEMS = [
  { id: "subject-attendance", label: "Subject attendance", roles: ["teacher"] },
  { id: "leave-inbox", label: "Leave requests to approve", roles: ["teacher"] },
  { id: "feedback-scores", label: "Feedback from students", roles: ["teacher"] },
  { id: "electives", label: "Electives", roles: ["student", "parent"] },
  { id: "feedback", label: "Faculty feedback", roles: ["student"] },
  { id: "hall-tickets", label: "Hall tickets", roles: ["student", "parent"] },
  { id: "scholarships", label: "Scholarships & certificates", roles: ["student", "parent"] },
  { id: "grievances", label: "Grievances", roles: ["student", "parent", "teacher"] },
  { id: "remarks", label: "Student remarks", roles: ["teacher"] },
  { id: "timetable", label: "Timetable", module: "timetable", roles: ["student", "parent", "teacher"] },
  { id: "notices", label: "Notice board", module: "notices", roles: ["teacher"] },
  { id: "placements", label: "Placements", module: "placements", roles: ["student"] },
  { id: "payslips", label: "Payslips", module: "payroll", roles: ["teacher"] },
  { id: "leave", label: "My leave", roles: ["student", "parent", "teacher"] },
  { id: "password", label: "Change password", roles: ["student", "parent", "teacher"] },
];

function enabled(user, item) {
  // Parents have no college of their own (enabled_modules is null): show everything.
  if (item.hodOnly && !user.is_hod) return false;
  return !item.module || !user.enabled_modules || user.enabled_modules.includes(item.module);
}

function TabBar({ tabs, active, onChange }) {
  return (
    <View style={{ flexDirection: "row", borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.white }}>
      {tabs.map((t) => {
        const on = t.id === active;
        return (
          <Pressable key={t.id} onPress={() => onChange(t.id)} style={{ flex: 1, alignItems: "center", paddingVertical: 8 }}>
            <Text style={{ fontSize: 18, color: on ? colors.brand : "#94a3b8" }}>{t.icon}</Text>
            <Text style={{ fontSize: 11, fontWeight: on ? "700" : "500", color: on ? colors.brand : colors.muted }}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function MoreScreen({ onOpen }) {
  const { user, logout } = useAuth();
  const items = MORE_ITEMS.filter((i) => i.roles.includes(user.role) && enabled(user, i));
  return (
    <Screen title="More">
      <Card>
        <H>{user.full_name}</H>
        <Muted style={{ textTransform: "capitalize" }}>{user.role === "teacher" ? "Faculty" : user.role}</Muted>
      </Card>
      {items.map((i) => (
        <Card key={i.id} onPress={() => onOpen(i.id)}>
          <Text style={{ fontSize: 16, fontWeight: "600", color: colors.text }}>{i.label} ›</Text>
        </Card>
      ))}
      <Card onPress={logout}>
        <Text style={{ fontSize: 16, fontWeight: "600", color: colors.danger }}>Sign out</Text>
      </Card>
    </Screen>
  );
}

function Shell({ tabs, render }) {
  const { user } = useAuth();
  const visible = tabs.filter((t) => enabled(user, t));
  const [tab, setTab] = useState(visible[0].id);
  const [page, setPage] = useState(null); // a "More" page

  function change(id) {
    setTab(id);
    setPage(null);
  }
  const openMore = (id) => {
    setTab("more");
    setPage(id);
  };

  let body;
  if (tab === "more" && page) {
    body = (
      <View style={{ flex: 1 }}>
        <Pressable onPress={() => setPage(null)} style={{ paddingHorizontal: 16, paddingTop: 10 }}>
          <Text style={{ color: colors.brand, fontWeight: "700" }}>‹ More</Text>
        </Pressable>
        {render(page, openMore)}
      </View>
    );
  } else if (tab === "more") {
    body = <MoreScreen onOpen={setPage} />;
  } else {
    body = render(tab, openMore);
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ flex: 1 }}>{body}</View>
      <TabBar tabs={visible} active={tab} onChange={change} />
    </View>
  );
}

function FacultyApp() {
  return (
    <Shell
      tabs={FACULTY_TABS}
      render={(id, openMore) =>
        ({
          department: <DepartmentScreen onOpenLeaves={() => openMore("leave-inbox")} />,
          "leave-inbox": <LeaveInboxScreen />,
          "subject-attendance": <SubjectAttendanceScreen />,
          "feedback-scores": <FeedbackScoresScreen />,
          grievances: <GrievancesScreen />,
          remarks: <RemarksScreen />,
          payslips: <PayslipsScreen />,
          punch: <PunchScreen />,
          attendance: <AttendanceScreen />,
          marks: <MarksScreen />,
          assignments: <FacultyAssignmentsScreen />,
          timetable: <TimetableScreen />,
          notices: <NoticesScreen />,
          leave: <LeaveScreen />,
          password: <ChangePasswordScreen />,
        })[id]
      }
    />
  );
}

function PortalApp() {
  const children = useApi("/me/parent/children");
  const [childId, setChildId] = useState(null);

  useEffect(() => {
    if (!childId && children.data?.length) setChildId(children.data[0].student_id);
  }, [children.data, childId]);

  if (children.loading && !children.data) return <ActivityIndicator style={{ flex: 1 }} color={colors.brand} />;
  if (!children.data?.length) {
    return (
      <Screen title="Nothing linked yet" onRefresh={children.reload} refreshing={children.loading}>
        <Muted>Your login isn't linked to a student record yet. Please contact the college office.</Muted>
      </Screen>
    );
  }
  const header = <ChildPicker children={children.data} childId={childId} onChange={setChildId} />;
  return (
    <Shell
      tabs={PORTAL_TABS}
      render={(id) =>
        ({
          home: <HomeScreen childId={childId} header={header} />,
          results: <ResultsScreen childId={childId} header={header} />,
          assignments: <AssignmentsScreen childId={childId} header={header} />,
          notices: <NoticesScreen />,
          timetable: <TimetableScreen childId={childId} header={header} />,
          placements: <PlacementsScreen />,
          electives: <ElectivesScreen childId={childId} header={header} />,
          feedback: <FeedbackScreen childId={childId} />,
          grievances: <GrievancesScreen childId={childId} />,
          "hall-tickets": <HallTicketScreen childId={childId} header={header} />,
          scholarships: <ScholarshipsCertificatesScreen childId={childId} header={header} />,
          leave: <LeaveScreen childId={childId} header={header} />,
          password: <ChangePasswordScreen />,
        })[id]
      }
    />
  );
}

function Root() {
  const { ready, user, refresh } = useAuth();

  useEffect(() => {
    if (user) refresh();
    // Once per app start / sign-in.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  if (!ready) return <ActivityIndicator style={{ flex: 1 }} color={colors.brand} />;
  if (!user) return <LoginScreen />;
  if (user.must_change_password) return <ChangePasswordScreen required />;
  return user.role === "teacher" ? <FacultyApp key={user.id} /> : <PortalApp key={user.id} />;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.white }} edges={["top", "bottom"]}>
          <StatusBar style="dark" />
          <Root />
        </SafeAreaView>
      </AuthProvider>
    </SafeAreaProvider>
  );
}

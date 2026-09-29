import { useEffect, useMemo, useState } from "react";
import { Route, Routes, useSearchParams } from "react-router-dom";

import AppShell from "./components/AppShell";
import ComingSoon from "./components/ComingSoon";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ActivityLogPage from "./pages/ActivityLogPage";
import AdmissionsPage from "./pages/AdmissionsPage";
import AppLinksPage from "./pages/AppLinksPage";
import AttendancePage from "./pages/AttendancePage";
import CalendarPage from "./pages/CalendarPage";
import CertificatesPage from "./pages/CertificatesPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import ClassesPage from "./pages/ClassesPage";
import DashboardPage from "./pages/DashboardPage";
import DepartmentsPage from "./pages/DepartmentsPage";
import ExamsPage from "./pages/ExamsPage";
import FeesPage from "./pages/FeesPage";
import PaymentIntegrationPage from "./pages/PaymentIntegrationPage";
import HomeworkPage from "./pages/HomeworkPage";
import HostelPage from "./pages/HostelPage";
import LeavePage from "./pages/LeavePage";
import LibraryPage from "./pages/LibraryPage";
import LoginPage from "./pages/LoginPage";
import MyClassesPage from "./pages/MyClassesPage";
import NoticesPage from "./pages/NoticesPage";
import ParentAlertsPage from "./pages/ParentAlertsPage";
import ParentPortalPage from "./pages/ParentPortalPage";
import PayrollPage, { MyPayslipsPage } from "./pages/PayrollPage";
import PerformancePage from "./pages/PerformancePage";
import PlacementsPage, { MyPlacementsPage } from "./pages/PlacementsPage";
import PromotionPage from "./pages/PromotionPage";
import PunchPage from "./pages/PunchPage";
import ReportsPage from "./pages/ReportsPage";
import SchoolSitePage from "./pages/SchoolSitePage";
import StaffAttendancePage from "./pages/StaffAttendancePage";
import StudentsPage from "./pages/StudentsPage";
import SuperAdminBackupsPage from "./pages/SuperAdminBackupsPage";
import SuperAdminOverviewPage from "./pages/SuperAdminOverviewPage";
import SuperAdminSchoolsPage from "./pages/SuperAdminSchoolsPage";
import TeachersPage from "./pages/TeachersPage";
import TimetablePage from "./pages/TimetablePage";
import TransportPage from "./pages/TransportPage";
import ApplyPage from "./pages/public/ApplyPage";
import MarketingPage from "./pages/public/MarketingPage";
import { PublicSitePage, TemplatePreviewPage } from "./pages/public/PublicSitePage";
import { LandingSettingsPage, LeadsPage } from "./pages/SuperAdminMarketingPages";

const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const NAV_ITEMS = [
  { id: "punch", label: "Punch In / Out", roles: ["teacher"] },
  { id: "dashboard", label: "Dashboard", roles: ["admin", "teacher"], module: "dashboard" },
  { id: "admissions", label: "Admissions", roles: ["admin"], module: "admissions" },
  { id: "departments", label: "Departments", roles: ["admin"] },
  { id: "teachers", label: "Faculty", roles: ["admin"] },
  { id: "classes", label: "Batches & Subjects", roles: ["admin"] },
  { id: "promotion", label: "Promote to next semester", roles: ["admin"] },
  { id: "certificates", label: "ID cards & certificates", roles: ["admin"], module: "certificates" },
  { id: "students", label: "Students", roles: ["admin", "teacher"] },
  { id: "attendance", label: "Student Attendance", roles: ["admin", "teacher"] },
  { id: "staff-attendance", label: "Faculty Attendance", roles: ["admin"] },
  { id: "my-classes", label: "My Batches", roles: ["teacher"] },
  { id: "remarks", label: "Remarks", roles: ["admin"] },
  { id: "parent-alerts", label: "Parent Alerts", roles: ["admin", "teacher"] },
  { id: "exams", label: "Exams & Marks", roles: ["admin", "teacher"], module: "exams" },
  { id: "homework", label: "Assignments", roles: ["admin", "teacher", "parent", "student"], module: "homework" },
  { id: "notices", label: "Notice board", roles: ["admin", "teacher", "parent", "student"], module: "notices" },
  { id: "timetable", label: "Timetable", roles: ["admin", "teacher", "parent", "student"], module: "timetable" },
  { id: "calendar", label: "Academic calendar", roles: ["admin", "teacher", "parent", "student"], module: "timetable" },
  { id: "fees", label: "Fees", roles: ["admin"], module: "fees" },
  { id: "payment-integration", label: "Payment integration", roles: ["admin"], module: "fees" },
  { id: "library", label: "Library", roles: ["admin"], module: "library" },
  { id: "hostel", label: "Hostel", roles: ["admin"], module: "hostel" },
  { id: "transport", label: "Transport", roles: ["admin"], module: "transport" },
  { id: "placements", label: "Placements", roles: ["admin"], module: "placements" },
  { id: "my-placements", label: "Placements", roles: ["student"], module: "placements" },
  { id: "payroll", label: "Payroll", roles: ["admin"], module: "payroll" },
  { id: "my-payslips", label: "My payslips", roles: ["teacher"], module: "payroll" },
  { id: "school-site", label: "College Website", roles: ["admin"], module: "school-site" },
  { id: "reports", label: "Reports", roles: ["admin", "teacher"], module: "reports" },
  { id: "performance", label: "Performance", roles: ["admin", "teacher"], module: "performance" },
  { id: "app-links", label: "App & QR codes", roles: ["admin"] },
  { id: "activity", label: "Activity log", roles: ["admin"] },
  { id: "my-children", label: "My Children", roles: ["parent"] },
  { id: "my-portal", label: "My Portal", roles: ["student"] },
  { id: "leave", label: "Leave", roles: ["admin", "teacher"] },
  { id: "account", label: "Change password", roles: ["admin", "teacher", "parent", "student"] },
];

function AuthenticatedApp() {
  const { user, logout, refreshUser } = useAuth();
  // Items for modules the college has switched off are hidden (enabled_modules is null for parents).
  const navItems = useMemo(
    () =>
      NAV_ITEMS.filter(
        (item) => item.roles.includes(user.role) && (!item.module || !user.enabled_modules || user.enabled_modules.includes(item.module)),
      ),
    [user.role, user.enabled_modules],
  );
  const [activeNav, setActiveNav] = useState(() => {
    // Faculty land on Punch In / Out, admins on the dashboard, parents on My Children, students on My Portal.
    const preferred = { teacher: "punch", admin: "dashboard", parent: "my-children", student: "my-portal" }[user.role] ?? "attendance";
    return navItems.some((item) => item.id === preferred) ? preferred : navItems[0]?.id;
  });
  const [apiStatus, setApiStatus] = useState("checking");

  useEffect(() => {
    refreshUser();
    // Once per sign-in; refreshUser changes whenever the stored user does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A tapped phone notification opens its page: "/?nav=homework" on a fresh start,
  // or a message from the service worker when the app is already open.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromLink = params.get("nav");
    if (fromLink && navItems.some((item) => item.id === fromLink)) setActiveNav(fromLink);
    if (!("serviceWorker" in navigator)) return undefined;
    const onMessage = (event) => {
      if (event.data?.type === "open-nav" && navItems.some((item) => item.id === event.data.link)) setActiveNav(event.data.link);
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, [navItems]);

  // If the open page's module was just switched off, fall back to the first available page.
  useEffect(() => {
    if (!navItems.some((item) => item.id === activeNav)) setActiveNav(navItems[0]?.id);
  }, [navItems, activeNav]);

  useEffect(() => {
    fetch(`${apiUrl}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("API request failed");
        return response.json();
      })
      .then(() => setApiStatus("online"))
      .catch(() => setApiStatus("offline"));
  }, []);

  const activeLabel = navItems.find((item) => item.id === activeNav)?.label ?? "";

  function renderActivePage() {
    if (activeNav === "dashboard") return <DashboardPage onNavigate={setActiveNav} />;
    if (activeNav === "attendance") return <AttendancePage />;
    if (activeNav === "staff-attendance") return <StaffAttendancePage />;
    if (activeNav === "departments") return <DepartmentsPage />;
    if (activeNav === "teachers") return <TeachersPage />;
    if (activeNav === "classes") return <ClassesPage />;
    if (activeNav === "students") return <StudentsPage />;
    if (activeNav === "my-classes" || activeNav === "remarks") return <MyClassesPage />;
    if (activeNav === "parent-alerts") return <ParentAlertsPage />;
    if (activeNav === "account") return <ChangePasswordPage />;
    if (activeNav === "fees") return <FeesPage />;
    if (activeNav === "payment-integration") return <PaymentIntegrationPage />;
    if (activeNav === "exams") return <ExamsPage />;
    if (activeNav === "homework") return <HomeworkPage />;
    if (activeNav === "notices") return <NoticesPage />;
    if (activeNav === "timetable") return <TimetablePage />;
    if (activeNav === "calendar") return <CalendarPage />;
    if (activeNav === "reports") return <ReportsPage />;
    if (activeNav === "certificates") return <CertificatesPage />;
    if (activeNav === "admissions") return <AdmissionsPage />;
    if (activeNav === "activity") return <ActivityLogPage />;
    if (activeNav === "library") return <LibraryPage />;
    if (activeNav === "hostel") return <HostelPage />;
    if (activeNav === "transport") return <TransportPage />;
    if (activeNav === "placements") return <PlacementsPage />;
    if (activeNav === "my-placements") return <MyPlacementsPage />;
    if (activeNav === "payroll") return <PayrollPage />;
    if (activeNav === "my-payslips") return <MyPayslipsPage />;
    if (activeNav === "performance") return <PerformancePage />;
    if (activeNav === "app-links") return <AppLinksPage />;
    if (activeNav === "punch") return <PunchPage />;
    if (activeNav === "leave") return <LeavePage />;
    if (activeNav === "promotion") return <PromotionPage />;
    if (activeNav === "my-children" || activeNav === "my-portal") return <ParentPortalPage />;
    if (activeNav === "school-site") return <SchoolSitePage />;
    return <ComingSoon label={activeLabel} />;
  }

  return (
    <AppShell navItems={navItems} activeNav={activeNav} onNavChange={setActiveNav} user={user} onLogout={logout} apiStatus={apiStatus}>
      {renderActivePage()}
    </AppShell>
  );
}

const SUPER_ADMIN_TABS = [
  { id: "overview", label: "Overview" },
  { id: "schools", label: "Colleges" },
  { id: "leads", label: "Demo requests" },
  { id: "landing", label: "Landing page" },
  { id: "activity", label: "Activity log" },
  { id: "backups", label: "Backups" },
];

function SuperAdminApp() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState("overview");

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-4 sm:px-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">ANV College ERP</p>
          <h1 className="text-lg font-bold text-slate-900">Super admin console</h1>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <div className="hidden text-right leading-tight sm:block">
            <p className="font-semibold text-slate-800">{user.full_name}</p>
            <p className="text-xs capitalize text-slate-400">{user.role.replace("_", " ")}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-100"
          >
            Log out
          </button>
        </div>
      </header>
      <nav className="border-b border-slate-200 bg-white px-4 sm:px-6">
        <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto">
          {SUPER_ADMIN_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`shrink-0 border-b-2 px-4 py-3 text-sm font-semibold ${tab === t.id ? "border-emerald-600 text-emerald-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>
      <main className="mx-auto max-w-6xl p-4 sm:p-6">
        {tab === "overview" && <SuperAdminOverviewPage />}
        {tab === "activity" && <ActivityLogPage />}
        {tab === "backups" && <SuperAdminBackupsPage />}
        {tab === "schools" && <SuperAdminSchoolsPage />}
        {tab === "leads" && <LeadsPage />}
        {tab === "landing" && <LandingSettingsPage />}
      </main>
    </div>
  );
}

function Console() {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <LoginPage />;
  if (user.must_change_password) return <ChangePasswordPage required />;
  if (user.role === "super_admin") return <SuperAdminApp />;
  return <AuthenticatedApp />;
}

// "/" is the marketing page for visitors. Signed-in users, install/QR links (?as=...)
// and the installed app (?source=app) go straight to the app.
function Home() {
  const { isAuthenticated } = useAuth();
  const [params] = useSearchParams();
  if (isAuthenticated || params.has("as") || params.has("source")) return <Console />;
  return <MarketingPage />;
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/site/:slug" element={<PublicSitePage />} />
        <Route path="/apply/:code" element={<ApplyPage />} />
        <Route path="/templates/:id" element={<TemplatePreviewPage />} />
        <Route path="*" element={<Console />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;

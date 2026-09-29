export { THEMES } from "../siteTemplates/themes";
export const TEMPLATES = ["classic", "modern", "vibrant", "emerald", "royal", "neon", "sunrise", "ocean", "editorial", "split"];

export const BILLING_STATUSES = ["trial", "active", "suspended"];

// Optional modules the super admin switches per college (ids match OPTIONAL_MODULES in backend/app/core/modules.py).
// Students, teachers, classes, attendance, leave and punch in/out are always on.
export const MODULES = [
  { id: "dashboard", label: "Dashboard" },
  { id: "admissions", label: "Admissions" },
  { id: "exams", label: "Exams & Marks" },
  { id: "homework", label: "Assignments" },
  { id: "notices", label: "Notice board" },
  { id: "timetable", label: "Timetable & academic calendar" },
  { id: "fees", label: "Fees" },
  { id: "reports", label: "Reports" },
  { id: "performance", label: "Performance" },
  { id: "certificates", label: "ID cards & certificates" },
  { id: "payroll", label: "Payroll" },
  { id: "school-site", label: "College Website" },
  { id: "library", label: "Library" },
  { id: "hostel", label: "Hostel" },
  { id: "transport", label: "Transport" },
  { id: "placements", label: "Placements" },
];

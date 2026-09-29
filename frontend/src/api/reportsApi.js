import { apiBlob, apiRequest } from "../lib/apiClient";

function query(params) {
  return new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
}

export function fetchStudentAttendanceReport(token, params) {
  return apiRequest("/reports/student-attendance", { token, params });
}

export function fetchStaffAttendanceReport(token, month) {
  return apiRequest("/reports/staff-attendance", { token, params: { month } });
}

export function fetchFeeReport(token, onlyWithDues) {
  return apiRequest("/fees/report", { token, params: { only_with_dues: onlyWithDues } });
}

export function fetchExams(token) {
  return apiRequest("/exams", { token });
}

export function fetchExamPerformance(token, examId) {
  return apiRequest(`/reports/exam-performance/${examId}`, { token });
}

// Excel downloads need the auth header, so they're fetched as a blob and saved.
export async function downloadExcel(token, path, params, filename) {
  const qs = query(params);
  const blob = await apiBlob(`${path}${qs ? `?${qs}` : ""}`, { token });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

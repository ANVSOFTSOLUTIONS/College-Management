import { apiRequest } from "../lib/apiClient";

export const REMARK_CATEGORIES = [
  { id: "missed_exam", label: "Missed exam", alertByDefault: true },
  { id: "absent_class", label: "Absent from class", alertByDefault: true },
  { id: "homework", label: "Homework", alertByDefault: false },
  { id: "behaviour", label: "Behaviour", alertByDefault: false },
  { id: "appreciation", label: "Appreciation", alertByDefault: false },
  { id: "other", label: "Other", alertByDefault: false },
];

export function fetchTeachingClasses(token) {
  return apiRequest("/teaching/classes", { token });
}

export function fetchClassRoster(token, classId) {
  return apiRequest(`/teaching/classes/${classId}/students`, { token });
}

export function fetchRemarks(token, { classId, studentId } = {}) {
  return apiRequest("/remarks", { token, params: { class_id: classId, student_id: studentId } });
}

export function createRemark(token, body) {
  return apiRequest("/remarks", { method: "POST", token, body });
}

export function deleteRemark(token, remarkId) {
  return apiRequest(`/remarks/${remarkId}`, { method: "DELETE", token });
}

export function fetchParentAlerts(token, { classId } = {}) {
  return apiRequest("/parent-alerts", { token, params: { class_id: classId } });
}

export function fetchAlertSettings(token) {
  return apiRequest("/parent-alerts/settings", { token });
}

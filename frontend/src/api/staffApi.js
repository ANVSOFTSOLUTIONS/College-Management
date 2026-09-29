import { apiRequest } from "../lib/apiClient";

export function fetchMyPunches(token) {
  return apiRequest("/staff-punch/me", { token });
}

export function punchIn(token) {
  return apiRequest("/staff-punch/in", { method: "POST", token });
}

export function punchOut(token) {
  return apiRequest("/staff-punch/out", { method: "POST", token });
}

export function fetchPunchesForDay(token, date) {
  return apiRequest("/staff-punch", { token, params: { date } });
}

export function fetchSchoolSettings(token) {
  return apiRequest("/school-settings", { token });
}

export function saveSchoolSettings(token, body) {
  return apiRequest("/school-settings", { method: "PUT", token, body });
}

export const LEAVE_TYPES = [
  { id: "sick", label: "Sick leave" },
  { id: "casual", label: "Casual leave" },
  { id: "family", label: "Family function" },
  { id: "other", label: "Other" },
];

export function applyLeave(token, body) {
  return apiRequest("/leave", { method: "POST", token, body });
}

export function fetchMyLeaves(token) {
  return apiRequest("/leave/mine", { token });
}

export function fetchLeaveInbox(token) {
  return apiRequest("/leave/inbox", { token });
}

export function cancelLeave(token, leaveId) {
  return apiRequest(`/leave/${leaveId}/cancel`, { method: "POST", token });
}

export function reviewLeave(token, leaveId, status, note) {
  return apiRequest(`/leave/${leaveId}/review`, { method: "POST", token, body: { status, note } });
}

export function fetchNotifications(token) {
  return apiRequest("/notifications", { token });
}

export function markNotificationRead(token, id) {
  return apiRequest(`/notifications/${id}/read`, { method: "POST", token });
}

export function markAllNotificationsRead(token) {
  return apiRequest("/notifications/read-all", { method: "POST", token });
}

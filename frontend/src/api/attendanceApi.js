import { apiRequest } from "../lib/apiClient";

export function fetchMyClasses(token) {
  return apiRequest("/classes", { token });
}

export function fetchRoster(token, classId) {
  return apiRequest(`/classes/${classId}/students`, { token });
}

export function fetchAttendance(token, classId, date) {
  return apiRequest(`/classes/${classId}/attendance`, { token, params: { date } });
}

export function submitAttendance(token, classId, date, records) {
  return apiRequest(`/classes/${classId}/attendance`, {
    method: "POST",
    token,
    body: { date, records },
  });
}

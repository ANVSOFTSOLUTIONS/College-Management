import { apiRequest } from "../lib/apiClient";

export function fetchStaffAttendance(token, date) {
  return apiRequest("/staff-attendance", { token, params: { date } });
}

export function submitStaffAttendance(token, date, records) {
  return apiRequest("/staff-attendance", {
    method: "POST",
    token,
    body: { date, records },
  });
}

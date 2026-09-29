import { apiRequest } from "../lib/apiClient";

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function fetchPeriods(token) {
  return apiRequest("/timetable/periods", { token });
}

export function savePeriods(token, periods) {
  return apiRequest("/timetable/periods", { method: "PUT", token, body: { periods } });
}

export function fetchClassTimetable(token, classId) {
  return apiRequest(`/timetable/classes/${classId}`, { token });
}

export function saveClassTimetable(token, classId, cells) {
  return apiRequest(`/timetable/classes/${classId}`, { method: "PUT", token, body: { cells } });
}

export function fetchMyTimetable(token, studentId) {
  return apiRequest("/timetable/mine", { token, params: { student_id: studentId || undefined } });
}

export function fetchCalendar(token, start, end) {
  return apiRequest("/calendar", { token, params: { start, end } });
}

export function saveCalendarEntry(token, body, entryId) {
  return entryId
    ? apiRequest(`/calendar/${entryId}`, { method: "PUT", token, body })
    : apiRequest("/calendar", { method: "POST", token, body });
}

export function deleteCalendarEntry(token, entryId) {
  return apiRequest(`/calendar/${entryId}`, { method: "DELETE", token });
}

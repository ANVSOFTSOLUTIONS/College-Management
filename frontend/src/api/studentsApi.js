import { apiRequest } from "../lib/apiClient";

export function fetchStudents(token, { classId, q, includeLeft } = {}) {
  return apiRequest("/students", {
    token,
    params: { class_id: classId || undefined, q: q || undefined, include_left: includeLeft ? "true" : undefined },
  });
}

export function fetchStudent(token, studentId) {
  return apiRequest(`/students/${studentId}`, { token });
}

export function createStudent(token, body) {
  return apiRequest("/students", { method: "POST", token, body });
}

export function updateStudent(token, studentId, body) {
  return apiRequest(`/students/${studentId}`, { method: "PATCH", token, body });
}

export function markStudentLeft(token, studentId) {
  return apiRequest(`/students/${studentId}`, { method: "DELETE", token });
}

// A student's own login (college code + roll number). Omit the password to generate one.
export function enableStudentLogin(token, studentId, password) {
  return apiRequest(`/students/${studentId}/login`, { method: "POST", token, body: password ? { password } : {} });
}

export function disableStudentLogin(token, studentId) {
  return apiRequest(`/students/${studentId}/login`, { method: "DELETE", token });
}

export function enableClassStudentLogins(token, classId) {
  return apiRequest("/students/logins", { method: "POST", token, body: { class_id: classId } });
}

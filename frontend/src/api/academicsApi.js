import { apiRequest } from "../lib/apiClient";

// Teachers
export function fetchTeachers(token) {
  return apiRequest("/teachers", { token });
}

export function createTeacher(token, body) {
  return apiRequest("/teachers", { method: "POST", token, body });
}

export function updateTeacher(token, teacherId, body) {
  return apiRequest(`/teachers/${teacherId}`, { method: "PATCH", token, body });
}

export function removeTeacher(token, teacherId) {
  return apiRequest(`/teachers/${teacherId}`, { method: "DELETE", token });
}

// Subjects
export function fetchSubjects(token) {
  return apiRequest("/subjects", { token });
}

export function createSubject(token, body) {
  return apiRequest("/subjects", { method: "POST", token, body });
}

export function updateSubject(token, subjectId, body) {
  return apiRequest(`/subjects/${subjectId}`, { method: "PUT", token, body });
}

export function deleteSubject(token, subjectId) {
  return apiRequest(`/subjects/${subjectId}`, { method: "DELETE", token });
}

// Classes
export function fetchClasses(token) {
  return apiRequest("/classes", { token });
}

export function fetchClassDetail(token, classId) {
  return apiRequest(`/classes/${classId}`, { token });
}

export function createClass(token, body) {
  return apiRequest("/classes", { method: "POST", token, body });
}

export function updateClass(token, classId, body) {
  return apiRequest(`/classes/${classId}`, { method: "PATCH", token, body });
}

export function deleteClass(token, classId) {
  return apiRequest(`/classes/${classId}`, { method: "DELETE", token });
}

export function assignSubjectTeacher(token, classId, subjectId, teacherId) {
  return apiRequest(`/classes/${classId}/subjects/${subjectId}`, {
    method: "PUT",
    token,
    body: { teacher_id: teacherId },
  });
}

export function unassignSubject(token, classId, subjectId) {
  return apiRequest(`/classes/${classId}/subjects/${subjectId}`, { method: "DELETE", token });
}

// Departments
export function fetchDepartments(token) {
  return apiRequest("/departments", { token });
}

export function createDepartment(token, body) {
  return apiRequest("/departments", { method: "POST", token, body });
}

export function updateDepartment(token, departmentId, body) {
  return apiRequest(`/departments/${departmentId}`, { method: "PUT", token, body });
}

export function deleteDepartment(token, departmentId) {
  return apiRequest(`/departments/${departmentId}`, { method: "DELETE", token });
}

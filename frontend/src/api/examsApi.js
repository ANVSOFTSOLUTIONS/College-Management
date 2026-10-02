import { apiRequest } from "../lib/apiClient";

export function fetchExams(token) {
  return apiRequest("/exams", { token });
}

export function fetchExam(token, examId) {
  return apiRequest(`/exams/${examId}`, { token });
}

export function createExam(token, body) {
  return apiRequest("/exams", { method: "POST", token, body });
}

export function deleteExam(token, examId) {
  return apiRequest(`/exams/${examId}`, { method: "DELETE", token });
}

export function setExamPublished(token, examId, published) {
  return apiRequest(`/exams/${examId}/${published ? "publish" : "unpublish"}`, { method: "POST", token });
}

export function updatePaper(token, paperId, body) {
  return apiRequest(`/exam-papers/${paperId}`, { method: "PATCH", token, body });
}

export function fetchMyPapers(token) {
  return apiRequest("/exam-papers/mine", { token });
}

export function fetchMarkSheet(token, paperId) {
  return apiRequest(`/exam-papers/${paperId}/marks`, { token });
}

export function saveMarks(token, paperId, entries) {
  return apiRequest(`/exam-papers/${paperId}/marks`, { method: "PUT", token, body: { entries } });
}

export function fetchClassResults(token, examId, classId) {
  return apiRequest(`/exams/${examId}/classes/${classId}/results`, { token });
}

export function fetchReportCard(token, examId, studentId) {
  return apiRequest(`/exams/${examId}/students/${studentId}/report-card`, { token });
}

export function fetchChildResults(token, studentId) {
  return apiRequest(`/me/parent/children/${studentId}/results`, { token });
}

export function fetchClassBacklogs(token, classId) {
  return apiRequest("/exams/backlogs", { token, params: { class_id: classId } });
}

import { apiBlob, apiRequest } from "../lib/apiClient";

export function issueCertificate(token, studentId, body) {
  return apiRequest(`/students/${studentId}/certificates`, { method: "POST", token, body });
}

export function fetchRecentCertificates(token) {
  return apiRequest("/certificates", { token });
}

export function cancelCertificate(token, certificateId, reason) {
  return apiRequest(`/certificates/${certificateId}/cancel`, { method: "POST", token, body: { reason } });
}

export function fetchIdCards(token, classId) {
  return apiRequest("/id-cards", { token, params: { class_id: classId } });
}

export function fetchStudentPhoto(token, studentId) {
  return apiBlob(`/students/${studentId}/photo`, { token });
}

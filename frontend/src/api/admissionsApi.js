import { apiBlob, apiRequest, apiUpload } from "../lib/apiClient";

export const ADMISSION_DOC_TYPES = [
  { id: "birth_certificate", label: "Birth certificate" },
  { id: "photo", label: "Child's photo" },
  { id: "transfer_certificate", label: "Transfer certificate (TC)" },
  { id: "marks_memo", label: "Marks memo" },
  { id: "aadhaar", label: "Aadhaar" },
  { id: "other", label: "Other" },
];

// Public (no login)
export function fetchAdmissionForm(code) {
  return apiRequest(`/public/schools/${encodeURIComponent(code)}/admissions`);
}

export function submitApplication(code, body) {
  return apiRequest(`/public/schools/${encodeURIComponent(code)}/admissions`, { method: "POST", body });
}

export function uploadApplicationDocument(code, applicationId, token, docType, file) {
  const formData = new FormData();
  formData.append("token", token);
  formData.append("doc_type", docType);
  formData.append("file", file);
  return apiUpload(`/public/schools/${encodeURIComponent(code)}/admissions/${applicationId}/documents`, { formData });
}

// The application fee, paid online with the token from applying.
export function startFeePayment(code, applicationId, token) {
  return apiRequest(`/public/schools/${encodeURIComponent(code)}/admissions/${applicationId}/fee/pay`, { method: "POST", body: { token } });
}

export function confirmFeePayment(code, applicationId, token) {
  return apiRequest(`/public/schools/${encodeURIComponent(code)}/admissions/${applicationId}/fee/confirm`, { method: "POST", body: { token } });
}

// Admin
export function recordApplicationFee(token, applicationId, action, reference = "") {
  return apiRequest(`/admissions/${applicationId}/fee`, { method: "POST", token, body: { action, reference } });
}

export function fetchApplications(token, status) {
  return apiRequest("/admissions", { token, params: { status_filter: status || undefined } });
}

export function createWalkIn(token, body) {
  return apiRequest("/admissions", { method: "POST", token, body });
}

export function addApplicationDocument(token, applicationId, docType, file) {
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("file", file);
  return apiUpload(`/admissions/${applicationId}/documents`, { token, formData });
}

export function applicationDocument(token, applicationId, documentId) {
  return apiBlob(`/admissions/${applicationId}/documents/${documentId}`, { token });
}

export function approveApplication(token, applicationId, body) {
  return apiRequest(`/admissions/${applicationId}/approve`, { method: "POST", token, body });
}

export function rejectApplication(token, applicationId, note) {
  return apiRequest(`/admissions/${applicationId}/reject`, { method: "POST", token, body: { note } });
}

export function fetchAdmissionSettings(token) {
  return apiRequest("/admissions/settings", { token });
}

// body: { open, admission_fee? } (leave the fee out to keep it)
export function saveAdmissionSettings(token, body) {
  return apiRequest("/admissions/settings", { method: "PUT", token, body });
}

export function fetchNextAdmissionNumber(token) {
  return apiRequest("/admissions/next-admission-number", { token });
}

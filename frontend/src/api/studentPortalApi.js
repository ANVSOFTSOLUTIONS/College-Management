import { apiBlob, apiRequest, apiUpload } from "../lib/apiClient";

// A student's photo and documents. Where they live depends on who is looking: staff use
// /students/{id}, a parent /me/parent/children/{id}. Every helper takes that base path.

export const DOCUMENT_TYPES = [
  { id: "birth_certificate", label: "Birth certificate" },
  { id: "aadhaar", label: "Aadhaar card" },
  { id: "transfer_certificate", label: "Transfer certificate" },
  { id: "marks_memo", label: "Marks memo" },
  { id: "caste_certificate", label: "Caste certificate" },
  { id: "income_certificate", label: "Income certificate" },
  { id: "other", label: "Other" },
];

export function uploadPhoto(token, base, file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload(`${base}/photo`, { method: "PUT", token, formData });
}

export function fetchPhoto(token, base) {
  return apiBlob(`${base}/photo`, { token });
}

export function fetchDocuments(token, base) {
  return apiRequest(`${base}/documents`, { token });
}

export function uploadDocument(token, base, { docType, title, file }) {
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("title", title);
  formData.append("file", file);
  return apiUpload(`${base}/documents`, { token, formData });
}

export function deleteDocument(token, base, documentId) {
  return apiRequest(`${base}/documents/${documentId}`, { method: "DELETE", token });
}

export function fetchDocumentFile(token, base, documentId) {
  return apiBlob(`${base}/documents/${documentId}/file`, { token });
}

export function reviewDocument(token, studentId, documentId, status, note) {
  return apiRequest(`/students/${studentId}/documents/${documentId}`, {
    method: "PATCH",
    token,
    body: { status, note },
  });
}

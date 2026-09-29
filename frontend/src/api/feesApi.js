import { apiBlob, apiRequest } from "../lib/apiClient";

export const PAYMENT_METHODS = [
  { id: "cash", label: "Cash" },
  { id: "upi", label: "UPI" },
  { id: "cheque", label: "Cheque" },
  { id: "bank_transfer", label: "Bank transfer" },
  { id: "card", label: "Card" },
];

export const FEE_CATEGORIES = [
  { id: "tuition", label: "Tuition" },
  { id: "transport", label: "Transport / bus" },
  { id: "hostel", label: "Hostel" },
  { id: "library", label: "Library fine" },
  { id: "exam", label: "Exam" },
  { id: "books", label: "Books" },
  { id: "uniform", label: "Uniform" },
  { id: "admission", label: "Admission" },
  { id: "other", label: "Other" },
];

export function feeCategoryLabel(id) {
  return FEE_CATEGORIES.find((c) => c.id === id)?.label ?? "Other";
}

// Offline payments reported by parents
export function fetchFeeClaims(token, status) {
  return apiRequest("/fees/claims", { token, params: { status_filter: status || undefined } });
}

export function fetchClaimProof(token, claimId) {
  return apiBlob(`/fees/claims/${claimId}/proof`, { token });
}

export function approveFeeClaim(token, claimId) {
  return apiRequest(`/fees/claims/${claimId}/approve`, { method: "POST", token });
}

export function rejectFeeClaim(token, claimId, note) {
  return apiRequest(`/fees/claims/${claimId}/reject`, { method: "POST", token, body: { note } });
}

export function fetchOfflineInstructions(token) {
  return apiRequest("/fees/offline-instructions", { token });
}

export function saveOfflineInstructions(token, text) {
  return apiRequest("/fees/offline-instructions", { method: "PUT", token, body: { text } });
}

export function addStudentsToFee(token, itemId, studentIds) {
  return apiRequest(`/fees/items/${itemId}/students`, { method: "POST", token, body: { student_ids: studentIds } });
}

export function removeStudentFee(token, studentFeeId) {
  return apiRequest(`/fees/student-fees/${studentFeeId}`, { method: "DELETE", token });
}

export function formatRupees(value) {
  return `₹${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fetchFeeItems(token, classId) {
  return apiRequest("/fees/items", { token, params: { class_id: classId } });
}

export function createFeeItems(token, body) {
  return apiRequest("/fees/items", { method: "POST", token, body });
}

export function updateFeeItem(token, itemId, body) {
  return apiRequest(`/fees/items/${itemId}`, { method: "PATCH", token, body });
}

export function deleteFeeItem(token, itemId) {
  return apiRequest(`/fees/items/${itemId}`, { method: "DELETE", token });
}

export function syncFeeItem(token, itemId) {
  return apiRequest(`/fees/items/${itemId}/sync`, { method: "POST", token });
}

export function fetchStudentFees(token, studentId) {
  return apiRequest(`/fees/students/${studentId}`, { token });
}

export function setDiscount(token, studentFeeId, discount, note) {
  return apiRequest(`/fees/student-fees/${studentFeeId}/discount`, { method: "PUT", token, body: { discount, note } });
}

export function recordPayment(token, body) {
  return apiRequest("/fees/payments", { method: "POST", token, body });
}

export function cancelPayment(token, paymentId, reason) {
  return apiRequest(`/fees/payments/${paymentId}/cancel`, { method: "POST", token, body: { reason } });
}

export function fetchReceipt(token, paymentId) {
  return apiRequest(`/fees/payments/${paymentId}/receipt`, { token });
}

export function fetchFeeReport(token, { classId, onlyWithDues } = {}) {
  return apiRequest("/fees/report", { token, params: { class_id: classId, only_with_dues: onlyWithDues ? "true" : undefined } });
}

export function sendFeeReminders(token, { classId, onlyOverdue }) {
  return apiRequest("/fees/reminders", { method: "POST", token, body: { class_id: classId || null, only_overdue: onlyOverdue } });
}

export function fetchPaymentSettings(token) {
  return apiRequest("/fees/payment-settings", { token });
}

export function savePaymentSettings(token, body) {
  return apiRequest("/fees/payment-settings", { method: "PUT", token, body });
}

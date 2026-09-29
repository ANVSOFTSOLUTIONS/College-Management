import { apiBlob, apiRequest, apiUpload } from "../lib/apiClient";

// Staff side
export function enableParentLogin(token, studentId, resetPassword = false) {
  return apiRequest(`/students/${studentId}/parent-login`, { method: "POST", token, body: { reset_password: resetPassword } });
}

export function enableClassParentLogins(token, classId) {
  return apiRequest("/students/bulk-parent-logins", { method: "POST", token, body: { class_id: classId } });
}

// Parent portal
export function fetchChildren(token) {
  return apiRequest("/me/parent/children", { token });
}

export function fetchChildOverview(token, studentId) {
  return apiRequest(`/me/parent/children/${studentId}`, { token });
}

export function fetchChildPhoto(token, studentId) {
  return apiBlob(`/me/parent/children/${studentId}/photo`, { token });
}

export function fetchChildReceipt(token, studentId, paymentId) {
  return apiRequest(`/me/parent/children/${studentId}/receipts/${paymentId}`, { token });
}

export function startOnlinePayment(token, studentId, studentFeeId) {
  return apiRequest(`/me/parent/children/${studentId}/fees/${studentFeeId}/pay`, { method: "POST", token });
}

// A payment made outside the app (UPI to the college, bank, cash, cheque); the office confirms it.
export function reportOfflinePayment(token, studentId, studentFeeId, { amount, method, paidOn, reference, note, proof }) {
  const formData = new FormData();
  formData.append("amount", amount);
  formData.append("method", method);
  formData.append("paid_on", paidOn);
  formData.append("reference", reference);
  formData.append("note", note);
  if (proof) formData.append("proof", proof);
  return apiUpload(`/me/parent/children/${studentId}/fees/${studentFeeId}/offline`, { token, formData });
}

// Leave for a child (goes to the class teacher).
export function applyChildLeave(token, body) {
  return apiRequest("/leave", { method: "POST", token, body });
}

export function fetchMyLeaveRequests(token) {
  return apiRequest("/leave/mine", { token });
}

export function cancelLeaveRequest(token, leaveId) {
  return apiRequest(`/leave/${leaveId}/cancel`, { method: "POST", token });
}

// One payment for every due fee; each fee gets its own receipt.
export function startPayAll(token, studentId) {
  return apiRequest(`/me/parent/children/${studentId}/fees/pay-all`, { method: "POST", token });
}

export function confirmPayAll(token, studentId, batchId) {
  return apiRequest(`/me/parent/children/${studentId}/pay-all/${batchId}/confirm`, { method: "POST", token });
}

// After Cashfree Checkout closes; the server asks Cashfree whether the order is paid.
export function confirmOnlinePayment(token, studentId, paymentId) {
  return apiRequest(`/me/parent/children/${studentId}/payments/${paymentId}/confirm`, { method: "POST", token });
}

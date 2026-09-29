import { apiRequest } from "../lib/apiClient";

export const PAYMENT_MODES = [
  { id: "bank", label: "Bank transfer" },
  { id: "upi", label: "UPI" },
  { id: "cash", label: "Cash" },
  { id: "cheque", label: "Cheque" },
];

export function fetchSalaries(token) {
  return apiRequest("/payroll/salaries", { token });
}

export function saveSalary(token, teacherId, body) {
  return apiRequest(`/payroll/salaries/${teacherId}`, { method: "PUT", token, body });
}

export function fetchPayrollMonth(token, month) {
  return apiRequest(`/payroll/months/${month}`, { token });
}

export function generatePayroll(token, month) {
  return apiRequest(`/payroll/months/${month}/generate`, { method: "POST", token });
}

export function fetchPayslip(token, slipId) {
  return apiRequest(`/payroll/slips/${slipId}`, { token });
}

export function adjustPayslip(token, slipId, body) {
  return apiRequest(`/payroll/slips/${slipId}`, { method: "PATCH", token, body });
}

export function payPayslip(token, slipId, body) {
  return apiRequest(`/payroll/slips/${slipId}/pay`, { method: "POST", token, body });
}

export function revertPayslip(token, slipId) {
  return apiRequest(`/payroll/slips/${slipId}/revert`, { method: "POST", token });
}

export function fetchMyPayslips(token) {
  return apiRequest("/payroll/mine", { token });
}

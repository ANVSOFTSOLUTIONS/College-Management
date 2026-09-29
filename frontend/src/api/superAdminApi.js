import { apiRequest } from "../lib/apiClient";

export function fetchSchools(token) {
  return apiRequest("/super-admin/schools", { token });
}

export function createSchool(token, payload) {
  return apiRequest("/super-admin/schools", { method: "POST", token, body: payload });
}

export function updateSchool(token, schoolId, payload) {
  return apiRequest(`/super-admin/schools/${schoolId}`, { method: "PATCH", token, body: payload });
}

import { apiRequest } from "../lib/apiClient";

// credentials: { email, password, portal } for staff and parents (portal is "school" or "platform").
export function login(credentials) {
  return apiRequest("/auth/login", { method: "POST", body: credentials });
}

export function changePassword(token, currentPassword, newPassword) {
  return apiRequest("/auth/change-password", {
    method: "POST",
    token,
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

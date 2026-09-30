// Talks to the same backend as the web app.
// Set EXPO_PUBLIC_API_URL in mobile/.env (a phone can't reach "localhost" on your PC):
//   EXPO_PUBLIC_API_URL=http://192.168.1.10:8000/api/v1
export const API_URL = (process.env.EXPO_PUBLIC_API_URL || "http://10.0.2.2:8000/api/v1").replace(/\/+$/, "");
// The college website, for online fee payment (the gateways' checkout runs there). Optional.
export const WEB_URL = (process.env.EXPO_PUBLIC_WEB_URL || "").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function api(path, { method = "GET", token, body, params } = {}) {
  let url = `${API_URL}${path}`;
  if (params) {
    const query = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join("&");
    if (query) url += `?${query}`;
  }
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "offline", "Can't reach the college server. Check your internet connection.");
  }
  const isJson = response.status !== 204 && (response.headers.get("content-type") || "").includes("application/json");
  const payload = isJson ? await response.json() : null;
  if (!response.ok) {
    throw new ApiError(response.status, payload?.error?.code ?? "error", payload?.error?.message ?? "Something went wrong.");
  }
  return payload;
}

export function errorText(err, fallback = "Something went wrong.") {
  return err instanceof ApiError ? err.message : fallback;
}

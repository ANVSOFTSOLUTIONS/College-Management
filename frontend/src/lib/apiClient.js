const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function apiRequest(path, { method = "GET", token, body, params } = {}) {
  let url = `${API_BASE_URL}${path}`;
  if (params) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null),
    ).toString();
    if (query) url += `?${query}`;
  }

  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const isJson = response.status !== 204 && response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    throw new ApiError(response.status, payload?.error?.code ?? "unknown_error", payload?.error?.message ?? "Something went wrong.");
  }

  return payload;
}

async function throwIfError(response) {
  if (response.ok) return;
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;
  throw new ApiError(response.status, payload?.error?.code ?? "unknown_error", payload?.error?.message ?? "Something went wrong.");
}

// Multipart upload (FormData); the browser sets the multipart Content-Type itself.
export async function apiUpload(path, { method = "POST", token, formData }) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  await throwIfError(response);
  return response.status === 204 ? null : response.json();
}

// Private files (photos, documents) need the auth header, so they're fetched as blobs
// and shown through object URLs rather than plain <img src> links.
export async function apiBlob(path, { token }) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  await throwIfError(response);
  return response.blob();
}

import { apiRequest, apiUpload } from "../lib/apiClient";

// Public (no login)
export function fetchPublicSite(code) {
  return apiRequest(`/public/schools/${encodeURIComponent(code)}/site`);
}

// College admin
export function fetchMySite(token) {
  return apiRequest("/school-site", { token });
}

export function chooseTemplate(token, template) {
  return apiRequest("/school-site/template", { method: "PUT", token, body: { template } });
}

export function customizeSite(token, body) {
  return apiRequest("/school-site/customize", { method: "PUT", token, body });
}

export function saveCollegeInfo(token, body) {
  return apiRequest("/school-site/college-info", { method: "PUT", token, body });
}

export function saveAboutContact(token, about, contact) {
  return apiRequest("/school-site/about-contact", { method: "PUT", token, body: { about, contact } });
}

function upload(path, token, file, caption) {
  const formData = new FormData();
  formData.append("file", file);
  if (caption !== undefined) formData.append("caption", caption);
  return apiUpload(path, { token, formData });
}

export function uploadLogo(token, file) {
  return upload("/school-site/logo", token, file);
}

export function uploadBanner(token, file, caption) {
  return upload("/school-site/banners", token, file, caption);
}

export function deleteBanner(token, id) {
  return apiRequest(`/school-site/banners/${id}`, { method: "DELETE", token });
}

export function uploadGalleryImage(token, file, caption) {
  return upload("/school-site/gallery", token, file, caption);
}

export function deleteGalleryImage(token, id) {
  return apiRequest(`/school-site/gallery/${id}`, { method: "DELETE", token });
}

export function addActivity(token, body) {
  return apiRequest("/school-site/activities", { method: "POST", token, body });
}

export function deleteActivity(token, id) {
  return apiRequest(`/school-site/activities/${id}`, { method: "DELETE", token });
}

export function addNotice(token, body) {
  return apiRequest("/school-site/notices", { method: "POST", token, body });
}

export function deleteNotice(token, id) {
  return apiRequest(`/school-site/notices/${id}`, { method: "DELETE", token });
}

import { apiBlob, apiRequest, apiUpload } from "../lib/apiClient";

function upload(path, token, file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload(path, { token, formData });
}

// Notices
export function fetchNotices(token, includeExpired = false) {
  return apiRequest("/notices", { token, params: { include_expired: includeExpired } });
}

export function saveNotice(token, body, noticeId) {
  return noticeId
    ? apiRequest(`/notices/${noticeId}`, { method: "PUT", token, body })
    : apiRequest("/notices", { method: "POST", token, body });
}

export function deleteNotice(token, noticeId) {
  return apiRequest(`/notices/${noticeId}`, { method: "DELETE", token });
}

export function uploadNoticeAttachment(token, noticeId, file) {
  return upload(`/notices/${noticeId}/attachment`, token, file);
}

export function removeNoticeAttachment(token, noticeId) {
  return apiRequest(`/notices/${noticeId}/attachment`, { method: "DELETE", token });
}

export function noticeAttachment(token, noticeId) {
  return apiBlob(`/notices/${noticeId}/attachment`, { token });
}

// Homework
export function fetchPostingOptions(token) {
  return apiRequest("/homework/options", { token });
}

export function fetchHomework(token, params) {
  return apiRequest("/homework", { token, params });
}

export function saveHomework(token, body, homeworkId) {
  return homeworkId
    ? apiRequest(`/homework/${homeworkId}`, { method: "PUT", token, body })
    : apiRequest("/homework", { method: "POST", token, body });
}

export function deleteHomework(token, homeworkId) {
  return apiRequest(`/homework/${homeworkId}`, { method: "DELETE", token });
}

export function uploadHomeworkAttachment(token, homeworkId, file) {
  return upload(`/homework/${homeworkId}/attachment`, token, file);
}

export function homeworkAttachment(token, homeworkId) {
  return apiBlob(`/homework/${homeworkId}/attachment`, { token });
}

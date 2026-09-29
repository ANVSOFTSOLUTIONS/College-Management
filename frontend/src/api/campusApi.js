import { apiRequest } from "../lib/apiClient";

// Library
export const fetchLibrarySummary = (token) => apiRequest("/library/summary", { token });
export const fetchLibrarySettings = (token) => apiRequest("/library/settings", { token });
export const saveLibrarySettings = (token, body) => apiRequest("/library/settings", { method: "PUT", token, body });
export const fetchBooks = (token, q) => apiRequest("/library/books", { token, params: { q: q || undefined } });
export const saveBook = (token, body, bookId) =>
  apiRequest(bookId ? `/library/books/${bookId}` : "/library/books", { method: bookId ? "PUT" : "POST", token, body });
export const deleteBook = (token, bookId) => apiRequest(`/library/books/${bookId}`, { method: "DELETE", token });
export const fetchLoans = (token, view) => apiRequest("/library/loans", { token, params: { view } });
export const issueBook = (token, body) => apiRequest("/library/loans", { method: "POST", token, body });
export const loanAction = (token, loanId, action) => apiRequest(`/library/loans/${loanId}/${action}`, { method: "POST", token });

// Hostel
export const fetchHostels = (token) => apiRequest("/hostels", { token });
export const saveHostel = (token, body, hostelId) =>
  apiRequest(hostelId ? `/hostels/${hostelId}` : "/hostels", { method: hostelId ? "PUT" : "POST", token, body });
export const deleteHostel = (token, hostelId) => apiRequest(`/hostels/${hostelId}`, { method: "DELETE", token });
export const addRoom = (token, hostelId, body) => apiRequest(`/hostels/${hostelId}/rooms`, { method: "POST", token, body });
export const deleteRoom = (token, roomId) => apiRequest(`/hostels/rooms/${roomId}`, { method: "DELETE", token });
export const allocateRoom = (token, body) => apiRequest("/hostels/allocations", { method: "POST", token, body });
export const vacateRoom = (token, allocationId) => apiRequest(`/hostels/allocations/${allocationId}`, { method: "DELETE", token });

// Transport
export const fetchRoutes = (token) => apiRequest("/transport/routes", { token });
export const saveRoute = (token, body, routeId) =>
  apiRequest(routeId ? `/transport/routes/${routeId}` : "/transport/routes", { method: routeId ? "PUT" : "POST", token, body });
export const deleteRoute = (token, routeId) => apiRequest(`/transport/routes/${routeId}`, { method: "DELETE", token });
export const assignRoute = (token, body) => apiRequest("/transport/assignments", { method: "POST", token, body });
export const unassignRoute = (token, studentId) => apiRequest(`/transport/assignments/${studentId}`, { method: "DELETE", token });

// Placements
export const fetchPlacementStats = (token) => apiRequest("/placements/stats", { token });
export const fetchCompanies = (token) => apiRequest("/placements/companies", { token });
export const saveCompany = (token, body, companyId) =>
  apiRequest(companyId ? `/placements/companies/${companyId}` : "/placements/companies", { method: companyId ? "PUT" : "POST", token, body });
export const deleteCompany = (token, companyId) => apiRequest(`/placements/companies/${companyId}`, { method: "DELETE", token });
export const fetchDrives = (token) => apiRequest("/placements/drives", { token });
export const saveDrive = (token, body, driveId) =>
  apiRequest(driveId ? `/placements/drives/${driveId}` : "/placements/drives", { method: driveId ? "PUT" : "POST", token, body });
export const deleteDrive = (token, driveId) => apiRequest(`/placements/drives/${driveId}`, { method: "DELETE", token });
export const fetchApplications = (token, driveId) => apiRequest(`/placements/drives/${driveId}/applications`, { token });
export const setApplicationStatus = (token, applicationId, status) =>
  apiRequest(`/placements/applications/${applicationId}/status`, { method: "PUT", token, body: { status } });
export const fetchMyDrives = (token) => apiRequest("/placements/my-drives", { token });
export const applyToDrive = (token, driveId) => apiRequest(`/placements/drives/${driveId}/apply`, { method: "POST", token });
export const withdrawFromDrive = (token, driveId) => apiRequest(`/placements/drives/${driveId}/apply`, { method: "DELETE", token });

// Student / parent portal
export const fetchChildCampus = (token, studentId, what) => apiRequest(`/me/parent/children/${studentId}/${what}`, { token });

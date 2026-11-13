import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const errData = error.response?.data || {};
    const message = errData.detail || error.message || 'An error occurred';
    const code = errData.code || 'ERROR';
    const customError = new Error(message);
    customError.code = code;
    customError.status = error.response?.status;
    customError.errors = errData.errors;
    return Promise.reject(customError);
  }
);

export const authApi = {
  signIn: (data) => api.post('/auth/sign-in/', data),
  logout: () => api.post('/auth/logout/'),
  logoutAll: () => api.post('/auth/logout-all/'),
  changePassword: (data) => api.post('/auth/change-password/', data),
  forgotPassword: (data) => api.post('/auth/forgot-password/', data),
  resetPassword: (data) => api.post('/auth/reset-password/', data),
  getProfile: () => api.get('/auth/me/'),
  updateProfile: (data) => api.patch('/auth/me/', data),
};

export const usersApi = {
  getUsers: (params) => api.get('/users/', { params }),
  getUser: (id) => api.get(`/users/${id}/`),
  createUser: (data) => api.post('/users/', data),
  updateUser: (id, data) => api.patch(`/users/${id}/`, data),
  deactivateUser: (id, reason) => api.post(`/users/${id}/deactivate/`, { reason }),
  reactivateUser: (id) => api.post(`/users/${id}/reactivate/`),
  resetPassword: (id) => api.post(`/users/${id}/reset-password/`),
  unlockUser: (id) => api.post(`/users/${id}/unlock/`),
  resetDevice: (id, reason) => api.post(`/users/${id}/reset-device/`, { reason }),
  getLoginHistory: (id) => api.get(`/users/${id}/login-history/`),
};

export const dcrApi = {
  getDCRs: (params) => api.get('/device-change-requests/', { params }),
  approveDCR: (id) => api.post(`/device-change-requests/${id}/approve/`),
  rejectDCR: (id, decision_note) => api.post(`/device-change-requests/${id}/reject/`, { decision_note }),
};

export const notificationsApi = {
  getNotifications: () => api.get('/notifications/'),
  markRead: (id) => api.post(`/notifications/${id}/read/`),
  markAllRead: () => api.post('/notifications/read-all/'),
  getDeliveries: () => api.get('/notifications/deliveries/'),
};

export const auditApi = {
  getAuditLogs: (params) => api.get('/audit-log/', { params }),
  exportCsv: () => window.open('/api/audit-log/export/', '_blank'),
};

export const settingsApi = {
  getSettings: () => api.get('/settings/'),
  updateSettings: (settings, reason) => api.post('/settings/', { settings, reason }),
};

export const legalApi = {
  getTerms: () => api.get('/legal/terms/'),
  getPrivacy: () => api.get('/legal/privacy/'),
  getConsentStatus: () => api.get('/consent/status/'),
  submitConsent: (data) => api.post('/consent/', data),
};

export const masterApi = {
  getCompany: () => api.get('/master/company/'),
  updateCompany: (data) => api.put('/master/company/', data),
  getClients: (params) => api.get('/master/clients/', { params }),
  getClient: (id) => api.get(`/master/clients/${id}/`),
  createClient: (data) => api.post('/master/clients/', data),
  updateClient: (id, data) => api.put(`/master/clients/${id}/`, data),
  addClientContact: (clientId, data) => api.post(`/master/clients/${clientId}/contacts/`, data),
  importClientsCsv: (csv_content) => api.post('/master/clients/import-csv/', { csv_content }),
  getSites: (params) => api.get('/master/sites/', { params }),
  getSite: (id) => api.get(`/master/sites/${id}/`),
  createSite: (data) => api.post('/master/sites/', data),
  updateGeofence: (siteId, data) => api.post(`/master/sites/${siteId}/geofence/`, data),
  assignSupervisor: (siteId, data) => api.post(`/master/sites/${siteId}/supervisor/`, data),
  getPostTypes: () => api.get('/master/post-types/'),
  createPostType: (data) => api.post('/master/post-types/', data),
  getSiteShifts: (siteId) => api.get(`/master/sites/${siteId}/shifts/`),
  createSiteShift: (siteId, data) => api.post(`/master/sites/${siteId}/shifts/`, data),
  getSiteRequirements: (siteId) => api.get(`/master/sites/${siteId}/requirements/`),
  setSiteRequirement: (siteId, data) => api.post(`/master/sites/${siteId}/requirements/`, data),
  getAgreements: () => api.get('/master/agreements/'),
  createAgreement: (data) => api.post('/master/agreements/', data),
  getBillingRates: () => api.get('/master/billing-rates/'),
  setBillingRate: (data) => api.post('/master/billing-rates/', data),
  resolveBillingRate: (params) => api.get('/master/billing-rates/resolve/', { params }),
};

export const guardApi = {
  getDashboard: () => api.get('/guards/dashboard/'),
  getGuards: (params) => api.get('/guards/', { params }),
  getGuard: (id) => api.get(`/guards/${id}/`),
  registerGuard: (data) => api.post('/guards/', data),
  updateGuard: (id, data) => api.patch(`/guards/${id}/`, data),
  changeStatus: (id, data) => api.post(`/guards/${id}/status/`, data),
  uploadDocument: (id, data) => api.post(`/guards/${id}/documents/`, data),
  verifyDocument: (docId, data) => api.post(`/guards/documents/${docId}/verify/`, data),
  addTraining: (id, data) => api.post(`/guards/${id}/training/`, data),
  addCheck: (id, data) => api.post(`/guards/${id}/checks/`, data),
  updateBank: (id, data) => api.put(`/guards/${id}/bank/`, data),
  revealBank: (id) => api.post(`/guards/${id}/reveal-bank/`),
  createAccount: (id) => api.post(`/guards/${id}/create-account/`),
  checkDeployability: (id, params) => api.get(`/guards/${id}/deployability/`, { params }),
  requestUnavailability: (id, data) => api.post(`/guards/${id}/unavailability/`, data),
  decideUnavailability: (leaveId, data) => api.post(`/guards/unavailability/${leaveId}/decide/`, data),
  addDisciplinary: (id, data) => api.post(`/guards/${id}/disciplinary/`, data),
  generateIdCard: (id) => api.post(`/guards/${id}/id-card/`),
};

export const commercialsApi = {
  getRequests: (params) => api.get('/commercials/requests/', { params }),
  getRequest: (id) => api.get(`/commercials/requests/${id}/`),
  createRequest: (data) => api.post('/commercials/requests/', data),
  withdrawRequest: (id) => api.post(`/commercials/requests/${id}/withdraw/`),
  clarifyRequest: (id, data) => api.post(`/commercials/requests/${id}/clarify/`, data),
  recordSurvey: (id, data) => api.post(`/commercials/requests/${id}/survey/`, data),

  getQuotes: (params) => api.get('/commercials/quotes/', { params }),
  getQuote: (id) => api.get(`/commercials/quotes/${id}/`),
  createQuote: (data) => api.post('/commercials/quotes/create/', data),
  reviseQuote: (id, data) => api.post(`/commercials/quotes/${id}/revise/`, data),
  sendQuote: (versionId) => api.post(`/commercials/quotes/versions/${versionId}/send/`),
  acceptQuote: (versionId, data) => api.post(`/commercials/quotes/versions/${versionId}/accept/`, data),
  rejectQuote: (versionId, data) => api.post(`/commercials/quotes/versions/${versionId}/reject/`, data),
  counterQuote: (versionId, data) => api.post(`/commercials/quotes/versions/${versionId}/counter/`, data),
  convertQuote: (versionId) => api.post(`/commercials/quotes/versions/${versionId}/convert/`),
};

export const rosterApi = {
  getSlots: (params) => api.get('/roster/slots/', { params }),
  generateSlots: (data) => api.post('/roster/slots/generate/', data),
  assignSlot: (data) => api.post('/roster/slots/assign/', data),
  getAssignment: (id) => api.get(`/roster/assignments/${id}/`),
  cancelAssignment: (id, data) => api.post(`/roster/assignments/${id}/cancel/`, data),
  overrideLockedAssignment: (id, data) => api.post(`/roster/assignments/${id}/override-lock/`, data),
  acknowledgeDuty: (id, data) => api.post(`/roster/assignments/${id}/acknowledge/`, data),
  validateAssignment: (data) => api.post('/roster/validate/', data),
  publishRoster: (data) => api.post('/roster/publish/', data),
  createReplacement: (data) => api.post('/roster/replacements/', data),
  getSwaps: (params) => api.get('/roster/swaps/', { params }),
  requestSwap: (data) => api.post('/roster/swaps/', data),
  decideSwap: (id, data) => api.post(`/roster/swaps/${id}/decide/`, data),
  createEmergency: (data) => api.post('/roster/emergency/', data),
  getRatifications: (params) => api.get('/roster/emergency/ratifications/', { params }),
  ratifyEmergency: (id, data) => api.post(`/roster/emergency/ratifications/${id}/`, data),
  getCoverageDashboard: (params) => api.get('/roster/coverage-dashboard/', { params }),
  exportCoverage: (params) => api.get('/roster/coverage-export/', { params, responseType: 'blob' }),
  getMyDuties: (params) => api.get('/roster/my-duties/', { params }),
};

export const attendanceApi = {
  getDashboard: (params) => api.get('/attendance/dashboard/', { params }),
  getRecords: (params) => api.get('/attendance/records/', { params }),
  getRecord: (id) => api.get(`/attendance/records/${id}/`),
  checkIn: (data) => api.post('/attendance/check-in/', data),
  checkOut: (data) => api.post('/attendance/check-out/', data),
  approveRecord: (id, data) => api.post(`/attendance/records/${id}/approve/`, data),
  bulkApprove: (data) => api.post('/attendance/records/bulk-approve/', data),
  rejectRecord: (id, data) => api.post(`/attendance/records/${id}/reject/`, data),
  correctRecord: (id, data) => api.post(`/attendance/records/${id}/correct/`, data),
  markAbsent: (id, data) => api.post(`/attendance/records/${id}/mark-absent/`, data),
  getRegularisations: (params) => api.get('/attendance/regularisations/', { params }),
  submitRegularisation: (data) => api.post('/attendance/regularisations/', data),
  decideRegularisation: (id, data) => api.post(`/attendance/regularisations/${id}/decide/`, data),
  getPeriods: (params) => api.get('/attendance/periods/', { params }),
  closePeriod: (data) => api.post('/attendance/periods/', data),
  reopenPeriod: (id, data) => api.post(`/attendance/periods/${id}/reopen/`, data),
  exportAttendance: (params) => api.get('/attendance/export/', { params, responseType: 'blob' }),
  getClientSafeAttendance: (params) => api.get('/attendance/client-safe/', { params }),
};

export const monitoringApi = {
  getLiveMap: (params) => api.get('/monitoring/live-map/', { params }),
  getStatusBoard: (params) => api.get('/monitoring/status-board/', { params }),
  getGuardDetail: (guardId) => api.get(`/monitoring/guards/${guardId}/detail/`),
  getGuardTrail: (guardId) => api.get(`/monitoring/guards/${guardId}/trail/`),
  getHistoricalTrail: (guardId, params) => api.get(`/monitoring/guards/${guardId}/historical-trail/`, { params }),
  getSiteOverview: (siteId) => api.get(`/monitoring/sites/${siteId}/overview/`),
  getAlerts: (params) => api.get('/monitoring/alerts/', { params }),
  acknowledgeAlert: (alertId) => api.post(`/monitoring/alerts/${alertId}/acknowledge/`),
  resolveAlert: (alertId, data) => api.post(`/monitoring/alerts/${alertId}/resolve/`, data),
  dismissAlert: (alertId, data) => api.post(`/monitoring/alerts/${alertId}/dismiss/`, data),
  sendPing: (data) => api.post('/monitoring/pings/send/', data),
  respondPing: (pingId, data) => api.post(`/monitoring/pings/${pingId}/respond/`, data),
  getConfig: () => api.get('/monitoring/config/'),
  updateConfig: (data) => api.put('/monitoring/config/', data),
  getClientSafe: (params) => api.get('/monitoring/client-safe/', { params }),
};

export default api;


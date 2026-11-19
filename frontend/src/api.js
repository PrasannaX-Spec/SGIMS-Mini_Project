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

export const masterDataApi = masterApi;

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

export const incidentApi = {
  getUnifiedInbox: (params) => api.get('/incident-mgmt/inbox/', { params }),
  createIncident: (data) => api.post('/incident-mgmt/incidents/', data),
  getIncidentDetail: (id) => api.get(`/incident-mgmt/incidents/${id}/`),
  addAddendum: (id, data) => api.post(`/incident-mgmt/incidents/${id}/addendum/`, data),
  acknowledgeIncident: (id) => api.post(`/incident-mgmt/incidents/${id}/acknowledge/`),
  classifyIncident: (id, data) => api.patch(`/incident-mgmt/incidents/${id}/classify/`, data),
  escalateIncident: (id, data) => api.post(`/incident-mgmt/incidents/${id}/escalate/`, data),
  resolveIncident: (id, data) => api.post(`/incident-mgmt/incidents/${id}/resolve/`, data),
  closeIncident: (id) => api.post(`/incident-mgmt/incidents/${id}/close/`),
  reopenIncident: (id, data) => api.post(`/incident-mgmt/incidents/${id}/reopen/`, data),
  rejectIncident: (id, data) => api.post(`/incident-mgmt/incidents/${id}/reject/`, data),
  linkIncidents: (id, data) => api.post(`/incident-mgmt/incidents/${id}/link/`, data),
  shareWithClient: (id, data) => api.post(`/incident-mgmt/incidents/${id}/client-share/`, data),
  addTask: (id, data) => api.post(`/incident-mgmt/incidents/${id}/tasks/`, data),
  getGuardRequests: (params) => api.get('/incident-mgmt/requests/', { params }),
  createGuardRequest: (data) => api.post('/incident-mgmt/requests/', data),
  actionGuardRequest: (id, data) => api.post(`/incident-mgmt/requests/${id}/action/`, data),
  getClientTickets: (params) => api.get('/incident-mgmt/tickets/', { params }),
  createClientTicket: (data) => api.post('/incident-mgmt/tickets/', data),
  sendMessageClientTicket: (id, data) => api.post(`/incident-mgmt/tickets/${id}/message/`, data),
  getCategories: () => api.get('/incident-mgmt/categories/'),
  getRequestTypes: () => api.get('/incident-mgmt/request-types/'),
  getOutcomes: () => api.get('/incident-mgmt/outcomes/'),
  getAgingDashboard: () => api.get('/incident-mgmt/aging-dashboard/'),
  exportCSV: () => api.get('/incident-mgmt/export/csv/', { responseType: 'blob' }),
};

export const panicApi = {
  getActiveAlerts: () => api.get('/panic-escalation/alerts/active/'),
  getAlerts: (params) => api.get('/panic-escalation/alerts/', { params }),
  getAlertDetail: (id) => api.get(`/panic-escalation/alerts/${id}/`),
  triggerPanic: (data) => api.post('/panic-escalation/alerts/trigger/', data),
  acknowledgeAlert: (id, data) => api.post(`/panic-escalation/alerts/${id}/acknowledge/`, data),
  recordAction: (id, data) => api.post(`/panic-escalation/alerts/${id}/action/`, data),
  sendAreYouSafe: (id) => api.post(`/panic-escalation/alerts/${id}/are-you-safe/`),
  respondAreYouSafe: (id, data) => api.post(`/panic-escalation/alerts/${id}/respond-safe/`, data),
  reportFalseAlarm: (id, data) => api.post(`/panic-escalation/alerts/${id}/false-alarm/`, data),
  confirmFalseAlarm: (id, data) => api.post(`/panic-escalation/alerts/${id}/confirm-false-alarm/`, data),
  resolveAlert: (id, data) => api.post(`/panic-escalation/alerts/${id}/resolve/`, data),
  adminReview: (id, data) => api.post(`/panic-escalation/alerts/${id}/admin-review/`, data),
  addWelfareNote: (id, data) => api.post(`/panic-escalation/alerts/${id}/welfare-note/`, data),
  getTimeline: (id) => api.get(`/panic-escalation/alerts/${id}/timeline/`),
  linkIncident: (id, data) => api.post(`/panic-escalation/alerts/${id}/link-incident/`, data),
  getConfig: () => api.get('/panic-escalation/config/'),
  updateConfig: (data) => api.put('/panic-escalation/config/', data),
  getDeliveryMonitoring: () => api.get('/panic-escalation/deliveries/monitoring/'),
  getDeviceReadiness: (params) => api.get('/panic-escalation/device-readiness/', { params }),
  updateReadiness: (data) => api.post('/panic-escalation/device-readiness/', data),
  getDrills: () => api.get('/panic-escalation/drills/'),
  createDrill: (data) => api.post('/panic-escalation/drills/', data),
  getClientSafe: (siteId) => api.get('/panic-escalation/client-safe/', { params: { site_id: siteId } }),
  getMetrics: () => api.get('/panic-escalation/metrics/'),
  exportReport: (id, format = 'csv') => api.get(`/panic-escalation/alerts/${id}/export/`, { params: { format }, responseType: 'blob' }),
};

export const clientPortalApi = {
  getDashboard: () => api.get('/portal/dashboard/'),
  getSites: () => api.get('/portal/sites/'),
  getDeployment: (siteId) => api.get('/portal/deployment/', { params: { site_id: siteId } }),
  getGuardSafeCard: (guardId) => api.get(`/portal/guards/${guardId}/safe-card/`),
  reportPostIssue: (data) => api.post('/portal/report-post-issue/', data),
  getTodayAttendance: (siteId) => api.get('/portal/attendance/today/', { params: { site_id: siteId } }),
  getApprovedAttendance: (siteId, startDate, endDate) => api.get('/portal/attendance/approved/', { params: { site_id: siteId, start_date: startDate, end_date: endDate } }),
  downloadMonthlyAttendance: (siteId, month, year) => api.get('/portal/attendance/monthly-download/', { params: { site_id: siteId, month, year }, responseType: 'blob' }),
  raiseAttendanceQuery: (data) => api.post('/portal/attendance/query/', data),
  getIncidents: (siteId, status) => api.get('/portal/incidents/', { params: { site_id: siteId, status } }),
  commentIncident: (versionId, data) => api.post(`/portal/incidents/${versionId}/comment/`, data),
  getPanicStatus: (panicId) => api.get('/portal/panic/status/', { params: { panic_alert_id: panicId } }),
  acknowledgePanic: (panicId) => api.post(`/portal/panic/${panicId}/acknowledge/`),
  getDocuments: () => api.get('/portal/documents/'),
  getInvoices: () => api.get('/portal/invoices/'),
  getTickets: () => api.get('/portal/tickets/'),
  getTicketDetail: (ticketId) => api.get(`/portal/tickets/${ticketId}/`),
  createTicket: (data) => api.post('/portal/tickets/', data),
  replyTicket: (ticketId, data) => api.post(`/portal/tickets/${ticketId}/`, data),
  getAgencyContact: () => api.get('/portal/agency-contact/'),
  getPreferences: () => api.get('/portal/preferences/'),
  updatePreferences: (data) => api.put('/portal/preferences/', data),
  // Admin endpoints
  getAdminUsers: () => api.get('/portal/admin/users/'),
  getAdminUserSiteAccess: (userId) => api.get(`/portal/admin/users/${userId}/site-access/`),
  updateAdminUserSiteAccess: (userId, data) => api.post(`/portal/admin/users/${userId}/site-access/`, data),
  getAdminPortalConfig: (clientId) => api.get('/portal/admin/configuration/', { params: { client_id: clientId } }),
  updateAdminPortalConfig: (data) => api.put('/portal/admin/configuration/', data),
  getAdminPreview: (clientUserId) => api.get('/portal/admin/preview/', { params: { client_user_id: clientUserId } }),
  getAdminUsage: (days) => api.get('/portal/admin/usage/', { params: { days } }),
  getAdminAnnouncements: () => api.get('/portal/admin/announcements/'),
  createAdminAnnouncement: (data) => api.post('/portal/admin/announcements/', data),
};

export const billingApi = {
  getDashboardMetrics: () => api.get('/billing/dashboard/'),
  getCompanySettings: () => api.get('/billing/settings/company/'),
  updateCompanySettings: (data) => api.put('/billing/settings/company/', data),
  getClientSettings: (clientId) => api.get('/billing/settings/client/', { params: clientId ? { client_id: clientId } : {} }),
  createClientSettings: (data) => api.post('/billing/settings/client/', data),
  updateClientSettings: (id, data) => api.put(`/billing/settings/client/${id}/`, data),
  previewBilling: (data) => api.post('/billing/run/preview/', data),
  runBilling: (data) => api.post('/billing/run/execute/', data),
  getInvoices: (params) => api.get('/billing/invoices/', { params }),
  getInvoiceDetail: (id) => api.get(`/billing/invoices/${id}/`),
  addManualLine: (id, data) => api.post(`/billing/invoices/${id}/lines/manual/`, data),
  issueInvoice: (id) => api.post(`/billing/invoices/${id}/issue/`),
  cancelInvoice: (id, data) => api.post(`/billing/invoices/${id}/cancel/`, data),
  createReplacement: (id) => api.post(`/billing/invoices/${id}/replace/`),
  recordPayment: (id, data) => api.post(`/billing/invoices/${id}/payments/`, data),
  reversePayment: (paymentId, data) => api.post(`/billing/payments/${paymentId}/reverse/`, data),
  getReceivablesAgeing: () => api.get('/billing/receivables/ageing/'),
  getInvoiceAnnexure: (id) => api.get(`/billing/invoices/${id}/annexure/`),
  raiseInvoiceQuery: (id, data) => api.post(`/billing/invoices/${id}/queries/raise/`, data),
};

export const weaponsApi = {
  getDashboard: () => api.get('/weapons/dashboard/'),
  getWeapons: (params) => api.get('/weapons/records/', { params }),
  getWeapon: (id) => api.get(`/weapons/records/${id}/`),
  createWeapon: (data) => api.post('/weapons/records/', data),
  updateWeapon: (id, data) => api.patch(`/weapons/records/${id}/`, data),
  revealSerial: (id, reason) => api.post(`/weapons/records/${id}/reveal-serial/`, { reason }),
  relabelQR: (id) => api.post(`/weapons/records/${id}/relabel-qr/`),
  getLicences: () => api.get('/weapons/licences/'),
  createLicence: (data) => api.post('/weapons/licences/', data),
  issueWeapon: (data) => api.post('/weapons/transfers/issue/', data),
  confirmIssue: (transferId, data) => api.post(`/weapons/transfers/${transferId}/confirm-issue/`, data),
  returnWeapon: (data) => api.post('/weapons/transfers/return/', data),
  handoverWeapon: (data) => api.post('/weapons/transfers/handover/', data),
  getAmmunitionLots: () => api.get('/weapons/ammo/lots/'),
  createAmmunitionLot: (data) => api.post('/weapons/ammo/lots/', data),
  getAmmunitionLedger: () => api.get('/weapons/ammo/ledger/'),
  submitStockCount: (data) => api.post('/weapons/ammo/stock-count/', data),
  approveStockCount: (countId, approve) => api.post(`/weapons/ammo/stock-count/${countId}/approve/`, { approve }),
  getDiscrepancies: () => api.get('/weapons/discrepancies/'),
  resolveDiscrepancy: (id, data) => api.patch(`/weapons/discrepancies/${id}/`, data),
  getGuardBlocks: () => api.get('/weapons/guard-blocks/'),
  createGuardBlock: (data) => api.post('/weapons/guard-blocks/', data),
  getRecoveries: () => api.get('/weapons/recoveries/'),
  getDailyCustody: (params) => api.get('/weapons/daily-custody/', { params }),
  getMaintenanceLogs: () => api.get('/weapons/maintenance/'),
  createMaintenanceLog: (data) => api.post('/weapons/maintenance/', data),
  reportMissing: (data) => api.post('/weapons/missing-report/', data),
  exportRegister: (type = 'weapons') => api.get(`/weapons/export/register/?type=${type}`, { responseType: 'blob' }),
  getModule13Reporting: () => api.get('/weapons/reporting/module13/'),
};

export const reportsApi = {
  getAdminDashboard: (params) => api.get('/reports/dashboard/admin/', { params }),
  getSupervisorDashboard: (params) => api.get('/reports/dashboard/supervisor/', { params }),
  getDataHealth: () => api.get('/reports/data-health/'),
  getMetrics: (params) => api.get('/reports/metrics/', { params }),
  getMetricVersions: (metricId) => api.get(`/reports/metrics/${metricId}/versions/`),
  proposeMetricVersion: (metricId, data) => api.post(`/reports/metrics/${metricId}/propose-version/`, data),
  getCatalogue: (params) => api.get('/reports/catalogue/', { params }),
  getReportDetail: (code, params) => api.get(`/reports/detail/${code}/`, { params }),
  exportCsv: (data) => api.post('/reports/export/csv/', data, { responseType: 'blob' }),
  exportPdf: (data) => api.post('/reports/export/pdf/', data),
  getPresets: () => api.get('/reports/presets/'),
  createPreset: (data) => api.post('/reports/presets/', data),
  deletePreset: (id) => api.delete(`/reports/presets/${id}/`),
  getClientSummaries: (params) => api.get('/reports/client-summaries/', { params }),
  generateClientSummary: (data) => api.post('/reports/client-summaries/', data),
  releaseClientSummary: (id) => api.post(`/reports/client-summaries/${id}/release/`),
  getClientSafeSummaries: (params) => api.get('/reports/client-summaries/client-safe/', { params }),
  getReconciliation: () => api.get('/reports/reconciliation/'),
  triggerRepair: () => api.post('/reports/reconciliation/'),
  getExportHistory: () => api.get('/reports/export-history/'),
};

export const payrollApi = {
  getDashboard: () => api.get('/payroll/dashboard/'),
  getChecklist: (params) => api.get('/payroll/checklist/', { params }),
  getComponents: () => api.get('/payroll/components/'),
  createComponent: (data) => api.post('/payroll/components/', data),
  updateComponent: (id, data) => api.put(`/payroll/components/${id}/`, data),
  deleteComponent: (id) => api.delete(`/payroll/components/${id}/`),
  getStructures: () => api.get('/payroll/structures/'),
  createStructure: (data) => api.post('/payroll/structures/', data),
  getAssignments: (params) => api.get('/payroll/assignments/', { params }),
  createAssignment: (data) => api.post('/payroll/assignments/', data),
  bulkAssign: (data) => api.post('/payroll/assignments/bulk/', data),
  getMinimumWages: () => api.get('/payroll/minimum-wages/'),
  createMinimumWage: (data) => api.post('/payroll/minimum-wages/', data),
  getPaidDayRules: () => api.get('/payroll/paid-day-rules/'),
  createPaidDayRule: (data) => api.post('/payroll/paid-day-rules/', data),
  getStatutoryRules: () => api.get('/payroll/statutory-rules/'),
  createStatutoryRule: (data) => api.post('/payroll/statutory-rules/', data),
  approveStatutoryRule: (id) => api.post(`/payroll/statutory-rules/${id}/approve/`),
  getAdvances: (params) => api.get('/payroll/advances/', { params }),
  createAdvance: (data) => api.post('/payroll/advances/', data),
  getDeductions: () => api.get('/payroll/deductions/'),
  createDeduction: (data) => api.post('/payroll/deductions/', data),
  getRuns: (params) => api.get('/payroll/runs/', { params }),
  createRun: (data) => api.post('/payroll/runs/', data),
  calculateRun: (id) => api.post(`/payroll/runs/${id}/calculate/`),
  approveRun: (id, data) => api.post(`/payroll/runs/${id}/approve/`, data),
  releaseRun: (id) => api.post(`/payroll/runs/${id}/release/`),
  cancelRun: (id, data) => api.post(`/payroll/runs/${id}/cancel/`, data),
  exportBankFileUrl: (id) => `/api/payroll/runs/${id}/export-bank-file/`,
  getResults: (params) => api.get('/payroll/results/', { params }),
  getPayslips: (params) => api.get('/payroll/payslips/', { params }),
  getPayments: (params) => api.get('/payroll/payments/', { params }),
  recordPayment: (data) => api.post('/payroll/payments/', data),
  reversePayment: (id, data) => api.post(`/payroll/payments/${id}/reverse/`, data),
  getFinalSettlements: () => api.get('/payroll/final-settlements/'),
  createFinalSettlement: (data) => api.post('/payroll/final-settlements/', data),
  secondApproveFinalSettlement: (id) => api.post(`/payroll/final-settlements/${id}/second-approve/`),
  getStatutoryPayments: () => api.get('/payroll/statutory-payments/'),
  createStatutoryPayment: (data) => api.post('/payroll/statutory-payments/', data),
  getReports: (params) => api.get('/payroll/reports/', { params }),
};

export default api;


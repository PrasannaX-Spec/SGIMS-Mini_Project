import React, { useState, useEffect, useCallback } from 'react';
import {
  Building2,
  Shield,
  ShieldAlert,
  AlertOctagon,
  AlertTriangle,
  Clock,
  Calendar,
  CheckCircle2,
  XCircle,
  FileText,
  Download,
  MessageSquare,
  Phone,
  Settings,
  RefreshCw,
  Eye,
  User,
  Users,
  Lock,
  ChevronRight,
  Filter,
  Plus,
  Send,
  ExternalLink,
  WifiOff,
  FileCheck,
  Info,
  Check,
  Search,
  ChevronDown
} from 'lucide-react';
import { clientPortalApi } from '../api';

export default function ClientPortalScreen({ user }) {
  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';

  // Navigation State
  const [activeTab, setActiveTab] = useState(isAdmin ? 'admin_mgmt' : 'dashboard');
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  // Simulation / Preview State (for Admin)
  const [previewUser, setPreviewUser] = useState(null);
  const [simulatedData, setSimulatedData] = useState(null);

  // Data States
  const [dashboard, setDashboard] = useState(null);
  const [sites, setSites] = useState([]);
  const [selectedSiteId, setSelectedSiteId] = useState('');
  const [deployment, setDeployment] = useState(null);
  const [todayAttendance, setTodayAttendance] = useState([]);
  const [approvedAttendance, setApprovedAttendance] = useState([]);
  const [sharedIncidents, setSharedIncidents] = useState([]);
  const [panicStatus, setPanicStatus] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [invoicesData, setInvoicesData] = useState(null);
  const [agencyContact, setAgencyContact] = useState(null);
  const [preferences, setPreferences] = useState([]);

  // Admin Management States
  const [adminUsers, setAdminUsers] = useState([]);
  const [adminConfig, setAdminConfig] = useState(null);
  const [adminUsage, setAdminUsage] = useState(null);
  const [adminAnnouncements, setAdminAnnouncements] = useState([]);
  const [selectedClientForConfig, setSelectedClientForConfig] = useState('');

  // Modals & Forms State
  const [activeModal, setActiveModal] = useState(null); // 'safe_card' | 'post_issue' | 'att_query' | 'new_ticket' | 'site_access' | 'announcement'
  const [modalData, setModalData] = useState(null);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState(null);

  // Form Fields
  const [postIssueForm, setPostIssueForm] = useState({ category: 'OBSERVED_ISSUE', description: '', named_guard_id: '' });
  const [attQueryForm, setAttQueryForm] = useState({ record_id: '', reason: '' });
  const [newTicketForm, setNewTicketForm] = useState({ site_id: '', ticket_type: 'QUERY', title: '', description: '' });
  const [ticketReplyText, setTicketReplyText] = useState('');
  const [siteAccessForm, setSiteAccessForm] = useState({ user_id: '', access_mode: 'ALL_SITES', site_ids: [] });
  const [announcementForm, setAnnouncementForm] = useState({ title: '', message: '', ends_at: '' });

  // Month & Year for Attendance Downloads
  const [downloadMonth, setDownloadMonth] = useState(new Date().getMonth() + 1);
  const [downloadYear, setDownloadYear] = useState(new Date().getFullYear());

  // Offline detection
  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Fetch Core Portal Data
  const loadPortalData = useCallback(async () => {
    setLoading(true);
    try {
      if (previewUser) {
        // Admin Preview Mode
        const res = await clientPortalApi.getAdminPreview(previewUser.user_id);
        setSimulatedData(res.data);
        setDashboard(res.data.dashboard);
        const previewSites = res.data.dashboard?.sites || [];
        setSites(previewSites);
        if (previewSites.length > 0 && !selectedSiteId) {
          setSelectedSiteId(previewSites[0].site_id);
        }
      } else if (!isAdmin || activeTab !== 'admin_mgmt') {
        // Normal Client / Previewing Client Data
        const [dashRes, sitesRes, docsRes, contactRes, prefRes, invRes] = await Promise.allSettled([
          clientPortalApi.getDashboard(),
          clientPortalApi.getSites(),
          clientPortalApi.getDocuments(),
          clientPortalApi.getAgencyContact(),
          clientPortalApi.getPreferences(),
          clientPortalApi.getInvoices(),
        ]);

        if (dashRes.status === 'fulfilled') setDashboard(dashRes.value.data);
        if (sitesRes.status === 'fulfilled') {
          setSites(sitesRes.value.data);
          if (sitesRes.value.data.length > 0 && !selectedSiteId) {
            setSelectedSiteId(sitesRes.value.data[0].site_id);
          }
        }
        if (docsRes.status === 'fulfilled') setDocuments(docsRes.value.data);
        if (contactRes.status === 'fulfilled') setAgencyContact(contactRes.value.data);
        if (prefRes.status === 'fulfilled') setPreferences(prefRes.value.data);
        if (invRes.status === 'fulfilled') setInvoicesData(invRes.value.data);
      }

      if (isAdmin) {
        // Load Admin Management info
        const [usersRes, usageRes, annRes] = await Promise.allSettled([
          clientPortalApi.getAdminUsers(),
          clientPortalApi.getAdminUsage(30),
          clientPortalApi.getAdminAnnouncements(),
        ]);
        if (usersRes.status === 'fulfilled') setAdminUsers(usersRes.value.data);
        if (usageRes.status === 'fulfilled') setAdminUsage(usageRes.value.data);
        if (annRes.status === 'fulfilled') setAdminAnnouncements(annRes.value.data);
      }

      setLastUpdated(new Date());
    } catch (err) {
      console.error("Portal data loading failed:", err);
    } finally {
      setLoading(false);
    }
  }, [isAdmin, previewUser, selectedSiteId, activeTab]);

  useEffect(() => {
    loadPortalData();
  }, [loadPortalData]);

  // Load site-specific deployment & attendance when selectedSiteId changes
  useEffect(() => {
    if (!selectedSiteId) return;

    const loadSiteDetails = async () => {
      try {
        const [depRes, todayAttRes, appAttRes, incRes, panicRes] = await Promise.allSettled([
          clientPortalApi.getDeployment(selectedSiteId),
          clientPortalApi.getTodayAttendance(selectedSiteId),
          clientPortalApi.getApprovedAttendance(selectedSiteId),
          clientPortalApi.getIncidents(selectedSiteId),
          clientPortalApi.getPanicStatus(),
        ]);

        if (depRes.status === 'fulfilled') setDeployment(depRes.value.data);
        if (todayAttRes.status === 'fulfilled') setTodayAttendance(todayAttRes.value.data);
        if (appAttRes.status === 'fulfilled') setApprovedAttendance(appAttRes.value.data);
        if (incRes.status === 'fulfilled') setSharedIncidents(incRes.value.data);
        if (panicRes.status === 'fulfilled') setPanicStatus(panicRes.value.data);
      } catch (err) {
        console.error("Site details loading failed:", err);
      }
    };

    loadSiteDetails();
  }, [selectedSiteId]);

  // Load Tickets when Tickets tab is activated
  useEffect(() => {
    if (activeTab === 'tickets') {
      clientPortalApi.getTickets().then(res => setTickets(res.data)).catch(console.error);
    }
  }, [activeTab]);

  // Show transient alert message
  const showFeedback = (msg, isError = false) => {
    setFeedbackMsg({ text: msg, isError });
    setTimeout(() => setFeedbackMsg(null), 4000);
  };

  // ----------------------------------------------------------------------------
  // Action Handlers
  // ----------------------------------------------------------------------------

  const handlePostIssueSubmit = async (e) => {
    e.preventDefault();
    if (!selectedSiteId || !postIssueForm.description) return;
    setFormSubmitting(true);
    try {
      await clientPortalApi.reportPostIssue({
        site_id: selectedSiteId,
        category: postIssueForm.category,
        description: postIssueForm.description,
        named_guard_id: postIssueForm.named_guard_id || null,
      });
      showFeedback("Issue reported successfully to the agency control desk.");
      setActiveModal(null);
      setPostIssueForm({ category: 'OBSERVED_ISSUE', description: '', named_guard_id: '' });
      loadPortalData();
    } catch (err) {
      showFeedback(err.message || "Failed to report issue.", true);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleAttendanceQuerySubmit = async (e) => {
    e.preventDefault();
    if (!attQueryForm.record_id || !attQueryForm.reason) return;
    setFormSubmitting(true);
    try {
      await clientPortalApi.raiseAttendanceQuery({
        attendance_record_id: attQueryForm.record_id,
        site_id: selectedSiteId,
        reason: attQueryForm.reason
      });
      showFeedback("Attendance query ticket created. Supervisor / Admin will investigate.");
      setActiveModal(null);
      setAttQueryForm({ record_id: '', reason: '' });
      loadPortalData();
    } catch (err) {
      showFeedback(err.message || "Failed to submit attendance query.", true);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleCreateTicketSubmit = async (e) => {
    e.preventDefault();
    setFormSubmitting(true);
    try {
      await clientPortalApi.createTicket(newTicketForm);
      showFeedback("Ticket created successfully.");
      setActiveModal(null);
      setNewTicketForm({ site_id: '', ticket_type: 'QUERY', title: '', description: '' });
      const res = await clientPortalApi.getTickets();
      setTickets(res.data);
    } catch (err) {
      showFeedback(err.message || "Failed to create ticket.", true);
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSendTicketReply = async (ticketId) => {
    if (!ticketReplyText.trim()) return;
    try {
      await clientPortalApi.replyTicket(ticketId, { message: ticketReplyText });
      setTicketReplyText('');
      const updated = await clientPortalApi.getTicketDetail(ticketId);
      setSelectedTicket(updated.data);
      showFeedback("Reply sent.");
    } catch (err) {
      showFeedback(err.message || "Failed to send reply.", true);
    }
  };

  const handlePanicAcknowledge = async (panicId) => {
    try {
      await clientPortalApi.acknowledgePanic(panicId);
      showFeedback("Emergency alert acknowledged.");
      const res = await clientPortalApi.getPanicStatus(panicId);
      setPanicStatus(res.data);
      loadPortalData();
    } catch (err) {
      showFeedback(err.message || "Failed to acknowledge panic.", true);
    }
  };

  const handleDownloadMonthlyAttendance = async () => {
    if (!selectedSiteId) return;
    try {
      const res = await clientPortalApi.downloadMonthlyAttendance(selectedSiteId, downloadMonth, downloadYear);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `monthly_attendance_${downloadYear}_${downloadMonth}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      showFeedback("Monthly attendance sheet downloaded successfully.");
    } catch (err) {
      showFeedback(err.message || "Monthly attendance sheet can only be downloaded for locked billing periods.", true);
    }
  };

  const handleSavePreferences = async (updatedList) => {
    try {
      await clientPortalApi.updatePreferences({ preferences: updatedList });
      setPreferences(updatedList);
      showFeedback("Notification preferences updated.");
    } catch (err) {
      showFeedback(err.message || "Failed to update preferences.", true);
    }
  };

  const handleSaveSiteAccess = async (e) => {
    e.preventDefault();
    if (!siteAccessForm.user_id) return;
    setFormSubmitting(true);
    try {
      await clientPortalApi.updateAdminUserSiteAccess(siteAccessForm.user_id, {
        access_mode: siteAccessForm.access_mode,
        site_ids: siteAccessForm.site_ids
      });
      showFeedback("Site access restrictions updated.");
      setActiveModal(null);
      const usersRes = await clientPortalApi.getAdminUsers();
      setAdminUsers(usersRes.data);
    } catch (err) {
      showFeedback(err.message || "Failed to update site access.", true);
    } finally {
      setFormSubmitting(false);
    }
  };

  // Status Badge Color Helper
  const getStatusBadge = (statusWord) => {
    switch (statusWord) {
      case 'On Duty':
      case 'Attendance Approved':
      case 'Resolved':
      case 'ACTIVE':
      case 'Full Deployment':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Not Yet Confirmed':
      case 'Attendance Pending Approval':
      case 'Not Yet Approved':
      case 'Status Not Updated':
      case 'Alert Raised':
      case 'Agency Acknowledged':
      case 'Responding':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'Replacement Assigned':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Shift Completed':
      case 'Closed':
        return 'bg-gray-100 text-gray-700 border-gray-200';
      default:
        return 'bg-slate-50 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Admin Preview Mode Banner */}
      {previewUser && (
        <div className="bg-amber-500 text-slate-900 px-4 py-3 rounded-md flex items-center justify-between font-medium shadow-sm">
          <div className="flex items-center space-x-2">
            <Eye className="w-5 h-5" />
            <span>
              <strong>PREVIEW MODE:</strong> Simulating client portal as <strong>{previewUser.full_name}</strong> ({previewUser.email}).
              Scoped strictly to permitted sites.
            </span>
          </div>
          <button
            onClick={() => { setPreviewUser(null); setSimulatedData(null); setActiveTab('admin_mgmt'); }}
            className="px-3 py-1 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
          >
            Exit Simulation
          </button>
        </div>
      )}

      {/* 2. Active Panic Banner (Permitted Sites) */}
      {dashboard?.active_panic_banner && (
        <div className="bg-rose-600 text-white p-4 rounded-md shadow-md animate-pulse flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <AlertOctagon className="w-7 h-7 flex-shrink-0" />
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg uppercase tracking-wide">Emergency Notice: {dashboard.active_panic_banner.site_name}</span>
                <span className="bg-white text-rose-700 text-xs font-extrabold px-2 py-0.5 rounded-md uppercase">
                  {dashboard.active_panic_banner.client_safe_status}
                </span>
              </div>
              <p className="text-xs text-rose-100 mt-1 max-w-2xl">
                {dashboard.active_panic_banner.disclaimer}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
            <a
              href="tel:112"
              className="px-4 py-2 bg-white text-rose-700 font-bold rounded-md text-sm flex items-center space-x-1.5 hover:bg-rose-50 transition shadow-sm"
            >
              <Phone className="w-4 h-4" />
              <span>Call 112</span>
            </a>
            <button
              onClick={() => setActiveTab('emergency')}
              className="px-4 py-2 bg-rose-800 text-white font-medium rounded-md text-sm hover:bg-rose-900 transition border border-rose-500"
            >
              Emergency Details
            </button>
          </div>
        </div>
      )}

      {/* 3. Offline Status Warning */}
      {isOffline && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2.5 rounded-md flex items-center space-x-2 text-sm">
          <WifiOff className="w-4 h-4 flex-shrink-0 text-amber-600" />
          <span>You are currently offline. Showing cached information. Write actions (creating tickets, acknowledge, downloads) are disabled until connectivity returns.</span>
        </div>
      )}

      {/* Feedback Toast */}
      {feedbackMsg && (
        <div className={`p-3 rounded-md text-sm font-medium flex items-center space-x-2 transition ${feedbackMsg.isError ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}`}>
          {feedbackMsg.isError ? <XCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
          <span>{feedbackMsg.text}</span>
        </div>
      )}

      {/* 4. Portal Header */}
      <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-slate-900 text-white rounded-md">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {previewUser ? `Client Portal — ${previewUser.full_name}` : (user?.client_company_name || 'Client Security Portal')}
              </h1>
              <p className="text-xs text-gray-500 mt-0.5">
                Karnataka Security Services Ltd &bull; Dedicated Client Services Console &bull; Updated {lastUpdated.toLocaleTimeString()}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Site Selector Dropdown */}
          {sites.length > 0 && (
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold uppercase text-gray-500">Site:</span>
              <select
                value={selectedSiteId}
                onChange={(e) => setSelectedSiteId(e.target.value)}
                className="bg-gray-50 border border-gray-300 rounded-md text-sm px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-slate-900 font-medium"
              >
                {sites.map(s => (
                  <option key={s.site_id} value={s.site_id}>{s.site_name}</option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={loadPortalData}
            disabled={loading}
            className="p-2 border border-gray-200 rounded-md text-gray-600 hover:bg-gray-50 transition"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* 5. Navigation Tabs */}
      <div className="flex flex-wrap border-b border-gray-200 gap-1 bg-white p-1 rounded-t-md">
        {[
          { id: 'dashboard', label: 'Dashboard', icon: Building2 },
          { id: 'deployment', label: 'Deployment & Guards', icon: Shield },
          { id: 'attendance', label: 'Attendance', icon: Clock },
          { id: 'incidents', label: 'Shared Incidents', icon: ShieldAlert },
          { id: 'emergency', label: 'Emergency Status', icon: AlertOctagon },
          { id: 'tickets', label: 'Tickets & Inquiries', icon: MessageSquare },
          { id: 'documents', label: 'Documents', icon: FileText },
          { id: 'invoices', label: 'Invoices', icon: FileCheck },
          { id: 'contacts', label: 'Agency Contacts', icon: Phone },
          { id: 'preferences', label: 'Notification Preferences', icon: Settings },
          ...(isAdmin ? [{ id: 'admin_mgmt', label: 'Admin Management & Preview', icon: Lock }] : [])
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-semibold rounded-md transition ${
                isActive
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 1: DASHBOARD                                                         */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Key Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
              <span className="text-xs font-bold text-gray-400 uppercase">Permitted Sites</span>
              <div className="text-2xl font-bold text-gray-900 mt-1">{dashboard?.summary?.total_permitted_sites || sites.length}</div>
              <div className="text-xs text-gray-500 mt-1">Authorized locations</div>
            </div>
            <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
              <span className="text-xs font-bold text-gray-400 uppercase">Guards on Duty</span>
              <div className="text-2xl font-bold text-emerald-700 mt-1">
                {dashboard?.summary?.total_confirmed_on_duty || 0}
                <span className="text-xs text-gray-400 font-normal ml-1">/ {dashboard?.summary?.total_required_guards || 0} required</span>
              </div>
              <div className="text-xs text-emerald-600 mt-1">Confirmed presence today</div>
            </div>
            <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
              <span className="text-xs font-bold text-gray-400 uppercase">Open Client Tickets</span>
              <div className="text-2xl font-bold text-gray-900 mt-1">{dashboard?.summary?.open_tickets_count || 0}</div>
              <div className="text-xs text-gray-500 mt-1">Active queries & tickets</div>
            </div>
            <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
              <span className="text-xs font-bold text-gray-400 uppercase">Pending Quotations</span>
              <div className="text-2xl font-bold text-gray-900 mt-1">{dashboard?.summary?.awaiting_requests_count || 0}</div>
              <div className="text-xs text-gray-500 mt-1">Service requests awaiting review</div>
            </div>
          </div>

          {/* All Sites Summary Table */}
          <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wide">All Permitted Sites Summary</h2>
                <p className="text-xs text-gray-500 mt-0.5">Sorted by operational priority and attention requirement</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-600 uppercase font-semibold border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3">Site Details</th>
                    <th className="px-4 py-3">Operational Status</th>
                    <th className="px-4 py-3 text-center">Required</th>
                    <th className="px-4 py-3 text-center">Assigned</th>
                    <th className="px-4 py-3 text-center">Confirmed Duty</th>
                    <th className="px-4 py-3 text-center">Emergency Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {dashboard?.sites?.map(site => (
                    <tr key={site.site_id} className="hover:bg-gray-50 transition">
                      <td className="px-4 py-3">
                        <div className="font-bold text-gray-900">{site.site_name}</div>
                        <div className="text-gray-400 text-[11px]">{site.site_code} &bull; {site.city || 'Bangalore'}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-bold border uppercase ${getStatusBadge(site.status)}`}>
                          {site.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center font-semibold text-gray-700">{site.required_guards}</td>
                      <td className="px-4 py-3 text-center text-gray-600">{site.assigned_guards}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`font-bold ${site.confirmed_on_duty >= site.required_guards ? 'text-emerald-700' : 'text-amber-700'}`}>
                          {site.confirmed_on_duty}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {site.active_panic ? (
                          <span className="inline-block px-2 py-0.5 bg-rose-100 text-rose-700 text-[10px] font-bold rounded-md animate-pulse">
                            PANIC ACTIVE
                          </span>
                        ) : (
                          <span className="text-gray-400 text-[11px]">Normal</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => { setSelectedSiteId(site.site_id); setActiveTab('deployment'); }}
                          className="px-2.5 py-1 bg-slate-900 text-white rounded-md text-xs font-medium hover:bg-slate-800 transition"
                        >
                          View Deployment
                        </button>
                      </td>
                    </tr>
                  ))}
                  {(!dashboard?.sites || dashboard.sites.length === 0) && (
                    <tr>
                      <td colSpan="7" className="px-4 py-8 text-center text-gray-500">
                        No sites permitted for your account. Please contact agency administration.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Announcements & Recent Shared Incidents */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Recent Shared Incidents */}
            <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <h3 className="text-sm font-bold text-gray-900 uppercase">Recent Shared Incidents</h3>
                <button onClick={() => setActiveTab('incidents')} className="text-xs text-slate-900 font-medium hover:underline">View All &rarr;</button>
              </div>
              <div className="space-y-3">
                {dashboard?.recent_incidents?.map(inc => (
                  <div key={inc.version_id} className="p-3 bg-gray-50 rounded-md border border-gray-200">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-gray-900">{inc.title}</span>
                      <span className="text-[10px] bg-slate-200 px-1.5 py-0.5 rounded-md font-bold uppercase">{inc.status}</span>
                    </div>
                    <p className="text-xs text-gray-600 mt-1 line-clamp-2">{inc.summary}</p>
                    <div className="text-[11px] text-gray-400 mt-1.5">{new Date(inc.occurred_at).toLocaleDateString()}</div>
                  </div>
                ))}
                {(!dashboard?.recent_incidents || dashboard.recent_incidents.length === 0) && (
                  <div className="text-center py-6 text-gray-400 text-xs">No incidents currently shared for your sites.</div>
                )}
              </div>
            </div>

            {/* Agency Announcements */}
            <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <h3 className="text-sm font-bold text-gray-900 uppercase">Agency Announcements</h3>
                <span className="text-xs text-gray-400">Notice Board</span>
              </div>
              <div className="space-y-3">
                {dashboard?.announcements?.map(ann => (
                  <div key={ann.announcement_id} className="p-3 bg-blue-50/50 rounded-md border border-blue-100">
                    <div className="font-bold text-xs text-blue-950">{ann.title}</div>
                    <p className="text-xs text-blue-900/80 mt-1">{ann.message}</p>
                    <div className="text-[11px] text-blue-700/60 mt-1.5">Valid until {new Date(ann.ends_at).toLocaleDateString()}</div>
                  </div>
                ))}
                {(!dashboard?.announcements || dashboard.announcements.length === 0) && (
                  <div className="text-center py-6 text-gray-400 text-xs">No active announcements at this time.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 2: DEPLOYMENT & GUARDS                                               */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'deployment' && (
        <div className="space-y-6">
          {/* Deployment Header & Shortfall Summary */}
          {deployment && (
            <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-bold text-gray-400 uppercase">Deployment Status &bull; {deployment.current_date}</span>
                <h2 className="text-lg font-bold text-gray-900 mt-0.5">{deployment.site_name}</h2>
                <div className="flex items-center space-x-2 mt-2">
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold border ${getStatusBadge(deployment.shortfall_status)}`}>
                    {deployment.shortfall_status}
                  </span>
                  <span className="text-xs text-gray-500">Required: <strong>{deployment.required_guards}</strong> &bull; Confirmed On Duty: <strong>{deployment.confirmed_on_duty}</strong></span>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setActiveModal('post_issue')}
                  className="px-3 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition flex items-center space-x-1.5"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Report Issue With Post</span>
                </button>
              </div>
            </div>
          )}

          {/* Current Shift Guards Grid */}
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-gray-900 uppercase">Today's Assigned Guards</h3>
                <p className="text-xs text-gray-500">Neutral reported duty state. Last update timestamp shown on each card.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {deployment?.current_shift_guards?.map(guard => (
                <div key={guard.guard_id} className="border border-gray-200 rounded-md p-4 bg-gray-50/50 flex flex-col justify-between hover:border-gray-300 transition">
                  <div>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-md bg-slate-200 text-slate-700 font-bold flex items-center justify-center text-sm border border-slate-300">
                          {guard.name ? guard.name.charAt(0) : 'G'}
                        </div>
                        <div>
                          <h4 className="font-bold text-sm text-gray-900">{guard.name}</h4>
                          <span className="text-xs text-gray-500 font-mono">{guard.employee_code}</span>
                        </div>
                      </div>
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border uppercase ${getStatusBadge(guard.status_word)}`}>
                        {guard.status_word}
                      </span>
                    </div>

                    <div className="mt-3 text-xs text-gray-600 space-y-1">
                      <div><strong className="text-gray-700">Post:</strong> {guard.post}</div>
                      <div><strong className="text-gray-700">Timing:</strong> {guard.shift_timing}</div>
                      {guard.is_replacement && (
                        <div className="mt-2 text-xs bg-blue-50 text-blue-700 border border-blue-200 p-1.5 rounded-md font-medium">
                          Replacement Assigned ({guard.replacement_time ? new Date(guard.replacement_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Today'})
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-gray-200 flex items-center justify-between text-[11px] text-gray-400">
                    <span>Updated {new Date(guard.last_updated_time).toLocaleTimeString()}</span>
                    <button
                      onClick={() => { setModalData(guard); setActiveModal('safe_card'); }}
                      className="text-slate-900 font-semibold hover:underline"
                    >
                      Safe Card &rarr;
                    </button>
                  </div>
                </div>
              ))}

              {(!deployment?.current_shift_guards || deployment.current_shift_guards.length === 0) && (
                <div className="col-span-full py-8 text-center text-gray-400 text-xs">
                  No guard assignments scheduled for this site today.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 3: ATTENDANCE                                                        */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'attendance' && (
        <div className="space-y-6">
          {/* Monthly Sheet Download Card (Locked Periods Only) */}
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-gray-900 uppercase">Monthly Locked Attendance Sheets</h3>
              <p className="text-xs text-gray-500 mt-0.5">Download officially verified attendance CSV/PDF records for locked billing periods.</p>
            </div>
            <div className="flex items-center space-x-3">
              <select
                value={downloadMonth}
                onChange={(e) => setDownloadMonth(Number(e.target.value))}
                className="bg-gray-50 border border-gray-300 rounded-md text-xs px-2.5 py-1.5"
              >
                {[...Array(12)].map((_, i) => (
                  <option key={i + 1} value={i + 1}>{new Date(0, i).toLocaleString('en', { month: 'long' })}</option>
                ))}
              </select>
              <select
                value={downloadYear}
                onChange={(e) => setDownloadYear(Number(e.target.value))}
                className="bg-gray-50 border border-gray-300 rounded-md text-xs px-2.5 py-1.5"
              >
                <option value={2026}>2026</option>
                <option value={2025}>2025</option>
              </select>
              <button
                onClick={handleDownloadMonthlyAttendance}
                className="px-3.5 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition flex items-center space-x-1.5"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export Locked CSV</span>
              </button>
            </div>
          </div>

          {/* Today So Far (Provisional) View */}
          <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-sm font-bold text-gray-900 uppercase">Today So Far — Provisional View</h3>
                  <span className="bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 rounded-md uppercase">
                    Not Yet Approved
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">Live check-in times recorded today. Not an official or final attendance record.</p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-600 uppercase font-semibold border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3">Guard Name</th>
                    <th className="px-4 py-3">Shift</th>
                    <th className="px-4 py-3">Check-In</th>
                    <th className="px-4 py-3">Check-Out</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Source Labels</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {todayAttendance.map(att => (
                    <tr key={att.attendance_id} className="hover:bg-gray-50 transition">
                      <td className="px-4 py-3 font-bold text-gray-900">
                        {att.guard_name}
                        <div className="text-[11px] font-mono font-normal text-gray-400">{att.guard_code}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{att.shift_name}</td>
                      <td className="px-4 py-3 text-gray-700">{att.check_in_time ? new Date(att.check_in_time).toLocaleTimeString() : 'Not Yet Confirmed'}</td>
                      <td className="px-4 py-3 text-gray-700">{att.check_out_time ? new Date(att.check_out_time).toLocaleTimeString() : '—'}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 uppercase">
                          {att.status_label}
                        </span>
                      </td>
                      <td className="px-4 py-3 space-x-1">
                        {att.is_manual && <span className="px-1.5 py-0.5 bg-gray-200 text-gray-700 rounded text-[10px] font-medium">Manual</span>}
                        {att.is_offline && <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-medium">Offline</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => { setAttQueryForm({ record_id: att.attendance_id, reason: '' }); setActiveModal('att_query'); }}
                          className="text-xs text-slate-900 font-medium hover:underline"
                        >
                          Raise Query
                        </button>
                      </td>
                    </tr>
                  ))}
                  {todayAttendance.length === 0 && (
                    <tr>
                      <td colSpan="7" className="px-4 py-8 text-center text-gray-400 text-xs">
                        No check-ins recorded for this site yet today.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Approved Attendance Records */}
          <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h3 className="text-sm font-bold text-gray-900 uppercase">Approved Historical Attendance</h3>
              <p className="text-xs text-gray-500 mt-0.5">Approved and locked attendance records verified by supervisor and agency operations.</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-600 uppercase font-semibold border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Guard Name</th>
                    <th className="px-4 py-3">Shift</th>
                    <th className="px-4 py-3">In / Out Time</th>
                    <th className="px-4 py-3 text-center">Worked Minutes</th>
                    <th className="px-4 py-3">Period State</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {approvedAttendance.map(app => (
                    <tr key={app.attendance_id} className="hover:bg-gray-50 transition">
                      <td className="px-4 py-3 font-semibold text-gray-900">{app.duty_date}</td>
                      <td className="px-4 py-3 font-bold text-gray-900">
                        {app.guard_name}
                        <div className="text-[11px] font-mono font-normal text-gray-400">{app.guard_code}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{app.shift_name}</td>
                      <td className="px-4 py-3 text-gray-700">
                        {app.in_time ? new Date(app.in_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '—'} - {app.out_time ? new Date(app.out_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '—'}
                      </td>
                      <td className="px-4 py-3 text-center font-bold text-gray-900">{app.worked_minutes}m</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border uppercase ${app.is_locked ? 'bg-slate-900 text-white border-slate-900' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
                          {app.period_state}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => { setAttQueryForm({ record_id: app.attendance_id, reason: '' }); setActiveModal('att_query'); }}
                          className="text-xs text-slate-900 font-medium hover:underline"
                        >
                          Query
                        </button>
                      </td>
                    </tr>
                  ))}
                  {approvedAttendance.length === 0 && (
                    <tr>
                      <td colSpan="7" className="px-4 py-8 text-center text-gray-400 text-xs">
                        No approved attendance records found for this period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 4: SHARED INCIDENTS                                                  */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'incidents' && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Client-Shared Incident Log</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Verified operational occurrences approved by agency management for client visibility. Internal notes and raw guard drafts are strictly shielded.
            </p>
          </div>

          <div className="space-y-4">
            {sharedIncidents.map(inc => (
              <div key={inc.version_id} className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-3">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-gray-100 pb-3">
                  <div>
                    <span className="text-[11px] font-mono text-gray-400 uppercase">{inc.category} &bull; {new Date(inc.occurred_at).toLocaleString()}</span>
                    <h4 className="text-base font-bold text-gray-900 mt-0.5">{inc.title}</h4>
                  </div>
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold border uppercase self-start md:self-auto ${getStatusBadge(inc.status)}`}>
                    {inc.status}
                  </span>
                </div>

                <div className="text-xs text-gray-700 space-y-2">
                  <div><strong className="text-gray-900">Approved Incident Summary:</strong> {inc.summary}</div>
                  <div><strong className="text-gray-900">Corrective Actions Taken:</strong> {inc.actions_taken}</div>
                </div>

                <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
                  <span className="text-[11px] text-gray-400">Site: <strong>{inc.site_name}</strong></span>
                  <button
                    onClick={() => { setModalData(inc); setActiveModal('incident_comment'); }}
                    className="px-3 py-1 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
                  >
                    Add Client Comment
                  </button>
                </div>
              </div>
            ))}

            {sharedIncidents.length === 0 && (
              <div className="bg-white border border-gray-200 rounded-md p-10 text-center text-gray-400 text-xs">
                No incidents shared for this site.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 5: EMERGENCY & PANIC                                                 */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'emergency' && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Emergency Response Center</h3>
            <p className="text-xs text-gray-500 mt-0.5">Real-time emergency panic alerts and agency acknowledgement status.</p>
          </div>

          {panicStatus?.active_panic ? (
            <div className="bg-white border-2 border-rose-500 rounded-md p-6 shadow-md space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-rose-600 text-white rounded-md">
                    <AlertOctagon className="w-8 h-8" />
                  </div>
                  <div>
                    <h4 className="text-lg font-bold text-gray-900">Active Alert &bull; {panicStatus.site_name}</h4>
                    <span className="text-xs text-gray-500 font-mono">Reference: {panicStatus.alert_number}</span>
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-md text-xs font-bold border uppercase ${getStatusBadge(panicStatus.client_safe_status)}`}>
                  {panicStatus.client_safe_status}
                </span>
              </div>

              <div className="bg-rose-50 border border-rose-200 p-4 rounded-md text-xs text-rose-900">
                <strong>Emergency Disclaimer:</strong> {panicStatus.disclaimer}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-700">
                <div className="p-3 bg-gray-50 rounded-md">
                  <strong>Triggered Time:</strong> {new Date(panicStatus.alert_time).toLocaleString()}
                </div>
                <div className="p-3 bg-gray-50 rounded-md">
                  <strong>Agency 24/7 Helpline:</strong> {panicStatus.agency_control_room}
                </div>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-gray-100">
                <a
                  href="tel:112"
                  className="px-4 py-2 bg-rose-600 text-white font-bold rounded-md text-xs hover:bg-rose-700 transition"
                >
                  Call Emergency Police/PCR (112)
                </a>
                <button
                  onClick={() => handlePanicAcknowledge(panicStatus.panic_alert_id)}
                  disabled={panicStatus.is_acknowledged_by_client}
                  className={`px-4 py-2 rounded-md text-xs font-bold transition ${panicStatus.is_acknowledged_by_client ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-slate-900 text-white hover:bg-slate-800'}`}
                >
                  {panicStatus.is_acknowledged_by_client ? 'Alert Acknowledged by You' : 'Acknowledge Emergency Notice'}
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-md p-10 text-center space-y-3">
              <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
              <h4 className="text-base font-bold text-gray-900">All Permitted Sites Secure</h4>
              <p className="text-xs text-gray-500 max-w-md mx-auto">
                No active panic or high-urgency alerts reported at your facilities. Agency control room maintains 24/7 telemetry monitoring.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 6: TICKETS & INQUIRIES                                               */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'tickets' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Ticket List Column */}
          <div className="md:col-span-1 bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="text-sm font-bold text-gray-900 uppercase">Client Tickets</h3>
              <button
                onClick={() => setActiveModal('new_ticket')}
                className="px-2.5 py-1 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition flex items-center space-x-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New</span>
              </button>
            </div>

            <div className="space-y-2">
              {tickets.map(t => (
                <div
                  key={t.ticket_id}
                  onClick={() => clientPortalApi.getTicketDetail(t.ticket_id).then(res => setSelectedTicket(res.data))}
                  className={`p-3 rounded-md border cursor-pointer transition text-left ${selectedTicket?.ticket_id === t.ticket_id ? 'border-slate-900 bg-slate-50' : 'border-gray-200 hover:border-gray-300'}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-gray-400">{t.ticket_number}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border uppercase ${getStatusBadge(t.status)}`}>{t.status}</span>
                  </div>
                  <div className="font-bold text-xs text-gray-900 mt-1 line-clamp-1">{t.title}</div>
                  <div className="text-[11px] text-gray-500 mt-1">{t.site_name} &bull; {new Date(t.created_at).toLocaleDateString()}</div>
                </div>
              ))}
              {tickets.length === 0 && (
                <div className="text-center py-8 text-gray-400 text-xs">No tickets submitted.</div>
              )}
            </div>
          </div>

          {/* Ticket Detail / Conversation Column */}
          <div className="md:col-span-2 bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
            {selectedTicket ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                  <div>
                    <span className="text-[11px] font-mono text-gray-400">{selectedTicket.ticket_number} &bull; {selectedTicket.site_name}</span>
                    <h3 className="text-base font-bold text-gray-900">{selectedTicket.title}</h3>
                  </div>
                  <span className={`px-2.5 py-1 rounded-md text-xs font-bold border uppercase ${getStatusBadge(selectedTicket.status)}`}>
                    {selectedTicket.status}
                  </span>
                </div>

                {/* Message Stream */}
                <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                  {selectedTicket.messages?.map(m => (
                    <div
                      key={m.message_id}
                      className={`p-3.5 rounded-md text-xs max-w-[85%] ${
                        m.is_client_actor
                          ? 'ml-auto bg-slate-900 text-white rounded-br-none'
                          : 'mr-auto bg-gray-100 text-gray-900 rounded-bl-none border border-gray-200'
                      }`}
                    >
                      <div className="font-semibold text-[11px] opacity-75 mb-1">{m.actor_name} &bull; {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                      <p className="whitespace-pre-wrap">{m.message}</p>
                    </div>
                  ))}
                </div>

                {/* Reply Box */}
                <div className="pt-3 border-t border-gray-100 flex items-center space-x-2">
                  <input
                    type="text"
                    value={ticketReplyText}
                    onChange={(e) => setTicketReplyText(e.target.value)}
                    placeholder="Type a response to the agency..."
                    className="flex-1 bg-gray-50 border border-gray-300 rounded-md text-xs px-3 py-2 focus:outline-none focus:ring-1 focus:ring-slate-900"
                    onKeyDown={(e) => e.key === 'Enter' && handleSendTicketReply(selectedTicket.ticket_id)}
                  />
                  <button
                    onClick={() => handleSendTicketReply(selectedTicket.ticket_id)}
                    className="px-4 py-2 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition flex items-center space-x-1"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 text-gray-400 text-xs">
                Select a ticket from the left column to view conversation history.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 7: DOCUMENTS                                                         */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'documents' && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Approved Client Documents</h3>
            <p className="text-xs text-gray-500 mt-0.5">Master service agreements and verified attendance documents. Download access is logged for audit compliance.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {documents.map(doc => (
              <div key={doc.document_id} className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{doc.document_type} &bull; {doc.file_format}</span>
                  <h4 className="font-bold text-sm text-gray-900">{doc.document_name}</h4>
                  <p className="text-xs text-gray-500">{doc.description}</p>
                  <div className="text-[11px] text-gray-400 pt-1">Issued: {doc.issue_date}</div>
                </div>
                <button
                  onClick={() => showFeedback(`Downloading document: ${doc.document_name}...`)}
                  className="p-2 border border-gray-200 rounded-md hover:bg-gray-50 text-slate-900 transition flex items-center space-x-1 text-xs font-semibold"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>
            ))}
            {documents.length === 0 && (
              <div className="col-span-full py-8 text-center text-gray-400 text-xs">
                No approved documents available at this time.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 8: INVOICES                                                          */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'invoices' && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Client Invoices & Commercials</h3>
            <p className="text-xs text-gray-500 mt-0.5">Summary of billing statements and payments recorded by agency finance.</p>
          </div>

          {invoicesData?.invoices && invoicesData.invoices.length > 0 ? (
            <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-semibold uppercase text-[10px]">
                    <tr>
                      <th className="p-3">Invoice No</th>
                      <th className="p-3">Billing Period</th>
                      <th className="p-3">Issue Date</th>
                      <th className="p-3">Due Date</th>
                      <th className="p-3 text-right">Total Amount</th>
                      <th className="p-3 text-right">Outstanding</th>
                      <th className="p-3">Status</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {invoicesData.invoices.map((inv) => (
                      <tr key={inv.invoice_id} className="hover:bg-gray-50 transition">
                        <td className="p-3 font-semibold text-gray-900">{inv.invoice_no}</td>
                        <td className="p-3 text-gray-600 whitespace-nowrap">{inv.period_start} to {inv.period_end}</td>
                        <td className="p-3 text-gray-500">{inv.invoice_date || '-'}</td>
                        <td className="p-3 text-gray-500">{inv.due_date || '-'}</td>
                        <td className="p-3 text-right font-bold text-gray-900">₹{parseFloat(inv.total_amount).toFixed(2)}</td>
                        <td className="p-3 text-right font-bold text-blue-700">₹{parseFloat(inv.outstanding_amount).toFixed(2)}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 text-xs font-semibold rounded-md border ${
                            inv.status === 'PAID'
                              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                              : inv.status === 'PARTIALLY_PAID'
                              ? 'bg-indigo-50 text-indigo-800 border-indigo-200'
                              : inv.status === 'CANCELLED'
                              ? 'bg-red-50 text-red-800 border-red-200'
                              : 'bg-blue-50 text-blue-800 border-blue-200'
                          }`}>
                            {inv.status}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          <button
                            onClick={() => {
                              setActiveTab('tickets');
                              setTicketCategory('INVOICE_QUERY');
                              setTicketTitle(`Query Regarding Invoice ${inv.invoice_no}`);
                            }}
                            className="px-2.5 py-1 text-[11px] font-semibold border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700"
                          >
                            Raise Query
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-md p-12 text-center text-gray-400 text-xs">
              <FileCheck className="w-10 h-10 mx-auto text-gray-300 mb-2" />
              No issued invoices recorded for your client organization.
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 9: AGENCY CONTACTS                                                   */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'contacts' && agencyContact && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Security Agency Official Contacts</h3>
            <p className="text-xs text-gray-500 mt-0.5">Direct contact points for control room operations, emergency response, and client service desk.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-2">
              <Phone className="w-6 h-6 text-slate-900" />
              <h4 className="font-bold text-sm text-gray-900">24/7 Central Control Room</h4>
              <div className="text-lg font-bold text-slate-900 font-mono">{agencyContact.control_room_phone}</div>
              <p className="text-xs text-gray-500">Manned continuously for guard tracking, replacements, and field alerts.</p>
            </div>

            <div className="bg-white border-2 border-rose-200 bg-rose-50/30 rounded-md p-5 shadow-sm space-y-2">
              <AlertTriangle className="w-6 h-6 text-rose-600" />
              <h4 className="font-bold text-sm text-rose-900">Emergency Police / PCR</h4>
              <div className="text-2xl font-bold text-rose-700 font-mono">{agencyContact.emergency_helpline}</div>
              <p className="text-xs text-rose-800">State emergency number for life safety, fire, and immediate police response.</p>
            </div>

            <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-2">
              <Building2 className="w-6 h-6 text-slate-900" />
              <h4 className="font-bold text-sm text-gray-900">Client Service Office</h4>
              <div className="text-xs text-gray-700 font-medium">{agencyContact.support_email}</div>
              <p className="text-xs text-gray-500 mt-1">{agencyContact.office_hours}</p>
              <p className="text-[11px] text-gray-400 mt-2">{agencyContact.address}</p>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 10: NOTIFICATION PREFERENCES                                         */}
      {/* ------------------------------------------------------------------------ */}
      {activeTab === 'preferences' && (
        <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-6">
          <div>
            <h3 className="text-sm font-bold text-gray-900 uppercase">Notification Channel Preferences</h3>
            <p className="text-xs text-gray-500 mt-0.5">Control which normal service notifications you receive. Emergency panic alerts cannot be disabled.</p>
          </div>

          <div className="divide-y divide-gray-100">
            {preferences.map((p, idx) => (
              <div key={p.notification_category} className="py-4 flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-sm text-gray-900">{p.notification_category}</h4>
                  <p className="text-xs text-gray-500">Updates regarding {p.notification_category.toLowerCase()} operational activities.</p>
                </div>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => {
                      const updated = [...preferences];
                      updated[idx].enabled = !updated[idx].enabled;
                      handleSavePreferences(updated);
                    }}
                    className={`w-11 h-6 flex items-center rounded-full p-1 cursor-pointer transition ${p.enabled ? 'bg-slate-900' : 'bg-gray-300'}`}
                  >
                    <div className={`bg-white w-4 h-4 rounded-full shadow-md transform transition ${p.enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-amber-50 border border-amber-200 p-4 rounded-md text-xs text-amber-800 flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 flex-shrink-0 text-amber-700" />
            <span>Notice: Emergency panic alerts at your assigned sites are non-disableable by policy to ensure critical facility safety.</span>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* TAB 11: ADMIN MANAGEMENT & PREVIEW                                       */}
      {/* ------------------------------------------------------------------------ */}
      {isAdmin && activeTab === 'admin_mgmt' && (
        <div className="space-y-6">
          {/* Admin Real Metrics Dashboard */}
          {adminUsage && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                <span className="text-xs font-bold text-gray-400 uppercase">Client Logins (30d)</span>
                <div className="text-2xl font-bold text-gray-900 mt-1">{adminUsage.total_logins}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">Real authentication events</div>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                <span className="text-xs font-bold text-gray-400 uppercase">Active Client Users</span>
                <div className="text-2xl font-bold text-emerald-700 mt-1">{adminUsage.active_client_users}</div>
                <div className="text-[11px] text-emerald-600 mt-0.5">Distinct authenticated clients</div>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                <span className="text-xs font-bold text-gray-400 uppercase">Portal Tickets Raised</span>
                <div className="text-2xl font-bold text-gray-900 mt-1">{adminUsage.tickets_raised_via_portal}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">Inquiries & queries</div>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                <span className="text-xs font-bold text-gray-400 uppercase">Document Downloads</span>
                <div className="text-2xl font-bold text-gray-900 mt-1">{adminUsage.document_downloads}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">Audited file accesses</div>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-md shadow-sm">
                <span className="text-xs font-bold text-gray-400 uppercase">Admin Previews</span>
                <div className="text-2xl font-bold text-amber-700 mt-1">{adminUsage.admin_previews}</div>
                <div className="text-[11px] text-amber-600 mt-0.5">Client simulation checks</div>
              </div>
            </div>
          )}

          {/* Client Users Management Table */}
          <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-gray-900 uppercase">Client User Accounts & Site Restrictions</h3>
                <p className="text-xs text-gray-500 mt-0.5">Configure site-level access boundaries and simulate client user experience.</p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-600 uppercase font-semibold border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3">Client User</th>
                    <th className="px-4 py-3">Linked Organization</th>
                    <th className="px-4 py-3">Access Mode</th>
                    <th className="px-4 py-3">Permitted Sites</th>
                    <th className="px-4 py-3">Last Login</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {adminUsers.map(u => (
                    <tr key={u.user_id} className="hover:bg-gray-50 transition">
                      <td className="px-4 py-3">
                        <div className="font-bold text-gray-900">{u.full_name}</div>
                        <div className="text-[11px] text-gray-400">{u.email}</div>
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-700">{u.client_company_name}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${u.access_mode === 'ALL_SITES' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                          {u.access_mode === 'ALL_SITES' ? 'All Company Sites' : 'Selected Sites'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {u.access_mode === 'ALL_SITES' ? 'Unrestricted (All)' : u.selected_sites.join(', ')}
                      </td>
                      <td className="px-4 py-3 text-gray-400">
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => {
                            clientPortalApi.getAdminUserSiteAccess(u.user_id).then(res => {
                              setSiteAccessForm({
                                user_id: u.user_id,
                                access_mode: res.data.access_mode,
                                site_ids: res.data.selected_site_ids || []
                              });
                              setModalData(res.data);
                              setActiveModal('site_access');
                            });
                          }}
                          className="px-2.5 py-1 border border-gray-300 rounded text-xs font-semibold hover:bg-gray-100 transition"
                        >
                          Configure Sites
                        </button>
                        <button
                          onClick={() => { setPreviewUser(u); setActiveTab('dashboard'); }}
                          className="px-2.5 py-1 bg-slate-900 text-white rounded text-xs font-semibold hover:bg-slate-800 transition"
                        >
                          Simulate Portal
                        </button>
                      </td>
                    </tr>
                  ))}
                  {adminUsers.length === 0 && (
                    <tr>
                      <td colSpan="6" className="px-4 py-8 text-center text-gray-400 text-xs">
                        No client user accounts found. Create client users in User Management (Module 1).
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* MODAL: SAFE GUARD CARD (NO PHONE / COORDS)                                */}
      {/* ------------------------------------------------------------------------ */}
      {activeModal === 'safe_card' && modalData && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border border-gray-200 rounded-md max-w-sm w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-bold text-sm text-gray-900 uppercase">Verified Guard Safe Card</h3>
              <button onClick={() => setActiveModal(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div className="text-center space-y-2">
              <div className="w-16 h-16 rounded-md bg-slate-100 border border-slate-300 mx-auto flex items-center justify-center font-bold text-xl text-slate-700">
                {modalData.name.charAt(0)}
              </div>
              <h4 className="font-bold text-base text-gray-900">{modalData.name}</h4>
              <span className="text-xs text-gray-500 font-mono">Employee Code: {modalData.employee_code}</span>
            </div>
            <div className="bg-gray-50 p-3 rounded-md text-xs space-y-1 text-gray-700">
              <div><strong>Designation:</strong> {modalData.designation || 'Security Guard'}</div>
              <div><strong>Security Post:</strong> {modalData.post || 'General Security'}</div>
              <div><strong>Badge Number:</strong> {modalData.badge_number || 'BDG-KA-VERIFIED'}</div>
              <div><strong>Reported Status:</strong> <span className="font-bold text-emerald-700">{modalData.status_word}</span></div>
            </div>
            <p className="text-[11px] text-gray-400 text-center">
              Direct guard mobile numbers are restricted by agency security protocol. Please use agency control desk for operational communications.
            </p>
            <button
              onClick={() => setActiveModal(null)}
              className="w-full py-2 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* MODAL: REPORT POST ISSUE (WITH NAMED GUARD ADMIN ROUTING)                 */}
      {/* ------------------------------------------------------------------------ */}
      {activeModal === 'post_issue' && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <form onSubmit={handlePostIssueSubmit} className="bg-white border border-gray-200 rounded-md max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-bold text-sm text-gray-900 uppercase">Report Post or Duty Issue</h3>
              <button type="button" onClick={() => setActiveModal(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-gray-700 mb-1">Issue Category</label>
                <select
                  value={postIssueForm.category}
                  onChange={(e) => setPostIssueForm({ ...postIssueForm, category: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                >
                  <option value="OBSERVED_ISSUE">Observed Site Issue</option>
                  <option value="UNFILLED_POST">Guard Not At Post</option>
                  <option value="UNIFORM_DISCIPLINE">Uniform / Professional Conduct</option>
                  <option value="GUARD_COMPLAINT">Complaint About Specific Guard</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-gray-700 mb-1">Description of Issue</label>
                <textarea
                  required
                  rows="3"
                  value={postIssueForm.description}
                  onChange={(e) => setPostIssueForm({ ...postIssueForm, description: e.target.value })}
                  placeholder="Provide objective facts regarding what was observed at the post..."
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                />
              </div>

              {postIssueForm.category === 'GUARD_COMPLAINT' && (
                <div className="bg-amber-50 border border-amber-200 p-2.5 rounded-md text-[11px] text-amber-800">
                  <strong>Notice:</strong> Complaints involving named personnel are automatically routed exclusively to Executive Administration under confidential oversight.
                </div>
              )}
            </div>
            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={formSubmitting}
                className="px-4 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
              >
                {formSubmitting ? 'Submitting...' : 'Submit Issue'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* MODAL: ATTENDANCE QUERY                                                  */}
      {/* ------------------------------------------------------------------------ */}
      {activeModal === 'att_query' && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <form onSubmit={handleAttendanceQuerySubmit} className="bg-white border border-gray-200 rounded-md max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-bold text-sm text-gray-900 uppercase">Raise Attendance Query</h3>
              <button type="button" onClick={() => setActiveModal(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-gray-700 mb-1">Reason for Query / Dispute</label>
                <textarea
                  required
                  rows="3"
                  value={attQueryForm.reason}
                  onChange={(e) => setAttQueryForm({ ...attQueryForm, reason: e.target.value })}
                  placeholder="Explain the specific time discrepancy or question for the agency to investigate..."
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                />
              </div>
            </div>
            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={formSubmitting}
                className="px-4 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
              >
                {formSubmitting ? 'Creating Ticket...' : 'Submit Query Ticket'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* MODAL: NEW TICKET                                                        */}
      {/* ------------------------------------------------------------------------ */}
      {activeModal === 'new_ticket' && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <form onSubmit={handleCreateTicketSubmit} className="bg-white border border-gray-200 rounded-md max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-bold text-sm text-gray-900 uppercase">Create Client Inquiry / Ticket</h3>
              <button type="button" onClick={() => setActiveModal(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-bold text-gray-700 mb-1">Target Site</label>
                <select
                  required
                  value={newTicketForm.site_id}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, site_id: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                >
                  <option value="">Select a permitted site...</option>
                  {sites.map(s => (
                    <option key={s.site_id} value={s.site_id}>{s.site_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block font-bold text-gray-700 mb-1">Subject</label>
                <input
                  required
                  type="text"
                  value={newTicketForm.title}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, title: e.target.value })}
                  placeholder="Brief summary of inquiry..."
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                />
              </div>
              <div>
                <label className="block font-bold text-gray-700 mb-1">Message</label>
                <textarea
                  required
                  rows="3"
                  value={newTicketForm.description}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, description: e.target.value })}
                  placeholder="Details of the request..."
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                />
              </div>
            </div>
            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={formSubmitting}
                className="px-4 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
              >
                {formSubmitting ? 'Creating...' : 'Submit Ticket'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ------------------------------------------------------------------------ */}
      {/* MODAL: ADMIN SITE ACCESS CONFIGURATOR                                    */}
      {/* ------------------------------------------------------------------------ */}
      {activeModal === 'site_access' && modalData && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <form onSubmit={handleSaveSiteAccess} className="bg-white border border-gray-200 rounded-md max-w-md w-full p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-bold text-sm text-gray-900 uppercase">Configure Client Site Restrictions</h3>
              <button type="button" onClick={() => setActiveModal(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div className="space-y-3 text-xs">
              <p className="text-gray-600">Configuring site access boundary for <strong>{modalData.full_name}</strong>.</p>
              <div>
                <label className="block font-bold text-gray-700 mb-1">Access Mode</label>
                <select
                  value={siteAccessForm.access_mode}
                  onChange={(e) => setSiteAccessForm({ ...siteAccessForm, access_mode: e.target.value })}
                  className="w-full bg-gray-50 border border-gray-300 rounded-md p-2"
                >
                  <option value="ALL_SITES">All Company Sites (Unrestricted)</option>
                  <option value="SELECTED_SITES">Selected Sites Only (Restricted)</option>
                </select>
              </div>

              {siteAccessForm.access_mode === 'SELECTED_SITES' && (
                <div className="space-y-2 border border-gray-200 p-3 rounded-md bg-gray-50 max-h-48 overflow-y-auto">
                  <span className="block font-bold text-gray-700">Select Permitted Sites:</span>
                  {modalData.available_sites?.map(s => (
                    <label key={s.site_id} className="flex items-center space-x-2 text-xs">
                      <input
                        type="checkbox"
                        checked={siteAccessForm.site_ids.includes(s.site_id)}
                        onChange={(e) => {
                          const current = [...siteAccessForm.site_ids];
                          if (e.target.checked) {
                            setSiteAccessForm({ ...siteAccessForm, site_ids: [...current, s.site_id] });
                          } else {
                            setSiteAccessForm({ ...siteAccessForm, site_ids: current.filter(id => id !== s.site_id) });
                          }
                        }}
                      />
                      <span>{s.site_name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={formSubmitting}
                className="px-4 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
              >
                {formSubmitting ? 'Saving...' : 'Save Configuration'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

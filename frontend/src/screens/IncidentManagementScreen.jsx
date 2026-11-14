import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  ArrowUpRight,
  Filter,
  Search,
  Plus,
  MessageSquare,
  Lock,
  Eye,
  Download,
  Calendar,
  UserCheck,
  AlertCircle,
  HelpCircle,
  Send,
  Layers,
  Share2,
  RefreshCw
} from 'lucide-react';
import { incidentApi, masterDataApi } from '../api';

export default function IncidentManagementScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isSupervisor = currentUser?.role === 'SUPERVISOR';
  const isGuard = currentUser?.role === 'GUARD';

  const [activeTab, setActiveTab] = useState('incidents'); // incidents, requests, tickets, aging, taxonomies
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Data states
  const [incidents, setIncidents] = useState([]);
  const [requests, setRequests] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [categories, setCategories] = useState([]);
  const [requestTypes, setRequestTypes] = useState([]);
  const [outcomes, setOutcomes] = useState([]);
  const [sites, setSites] = useState([]);
  const [agingData, setAgingData] = useState(null);

  // Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSite, setFilterSite] = useState('');
  const [filterOverdue, setFilterOverdue] = useState(false);

  // Active Detail Modal
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [incidentDetailLoading, setIncidentDetailLoading] = useState(false);

  // Sub-action Modals
  const [showAddendumModal, setShowAddendumModal] = useState(false);
  const [addendumContent, setAddendumContent] = useState('');

  const [showResolveModal, setShowResolveModal] = useState(false);
  const [resolveOutcomeId, setResolveOutcomeId] = useState('');
  const [resolveNote, setResolveNote] = useState('');
  const [resolveActionTaken, setResolveActionTaken] = useState('');

  const [showEscalateModal, setShowEscalateModal] = useState(false);
  const [escalateReason, setEscalateReason] = useState('');

  const [showReopenModal, setShowReopenModal] = useState(false);
  const [reopenReason, setReopenReason] = useState('');

  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const [showClassifyModal, setShowClassifyModal] = useState(false);
  const [classifyCategory, setClassifyCategory] = useState('');
  const [classifySeverity, setClassifySeverity] = useState('');

  const [showShareModal, setShowShareModal] = useState(false);
  const [shareTitle, setShareTitle] = useState('');
  const [shareSummary, setShareSummary] = useState('');
  const [shareActions, setShareActions] = useState('');

  const [showNewIncidentModal, setShowNewIncidentModal] = useState(false);
  const [newIncidentData, setNewIncidentData] = useState({
    category_id: '',
    description: '',
    suggested_severity: 'MEDIUM',
    site_id: '',
    occurred_at: new Date().toISOString().slice(0, 16),
  });

  const [showRequestReplyModal, setShowRequestReplyModal] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [requestReplyNote, setRequestReplyNote] = useState('');

  const [showTicketMessageModal, setShowTicketMessageModal] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [ticketMessageText, setTicketMessageText] = useState('');
  const [ticketMessageVisibility, setTicketMessageVisibility] = useState('CLIENT_VISIBLE');

  // Load initial data
  useEffect(() => {
    loadTaxonomies();
    loadSites();
    fetchInbox();
  }, [activeTab, filterSeverity, filterStatus, filterSite, filterOverdue]);

  const loadTaxonomies = async () => {
    try {
      const [catsRes, typesRes, outRes] = await Promise.all([
        incidentApi.getCategories(),
        incidentApi.getRequestTypes(),
        incidentApi.getOutcomes(),
      ]);
      setCategories(catsRes.data || []);
      setRequestTypes(typesRes.data || []);
      setOutcomes(outRes.data || []);
    } catch (err) {
      console.error('Failed to load taxonomies:', err);
    }
  };

  const loadSites = async () => {
    try {
      const res = await masterDataApi.getSites();
      setSites(res.data || []);
    } catch (err) {
      console.error('Failed to load sites:', err);
    }
  };

  const fetchInbox = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        record_type: activeTab === 'incidents' ? 'INCIDENT' : activeTab === 'requests' ? 'REQUEST' : activeTab === 'tickets' ? 'TICKET' : 'ALL',
        severity: filterSeverity || undefined,
        status: filterStatus || undefined,
        site_id: filterSite || undefined,
        search: searchQuery || undefined,
        overdue: filterOverdue ? 'true' : undefined,
      };

      if (activeTab === 'aging') {
        const agingRes = await incidentApi.getAgingDashboard();
        setAgingData(agingRes.data);
      } else {
        const res = await incidentApi.getUnifiedInbox(params);
        setIncidents(res.data.incidents || []);
        setRequests(res.data.requests || []);
        setTickets(res.data.tickets || []);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch inbox data.');
    } finally {
      setLoading(false);
    }
  };

  const openIncidentDetail = async (incidentId) => {
    setIncidentDetailLoading(true);
    try {
      const res = await incidentApi.getIncidentDetail(incidentId);
      setSelectedIncident(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load incident detail.');
    } finally {
      setIncidentDetailLoading(false);
    }
  };

  // --------------------------------------------------------------------------
  // Incident Lifecycle Actions
  // --------------------------------------------------------------------------
  const handleAcknowledge = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.acknowledgeIncident(selectedIncident.incident_id);
      setSuccessMsg('Incident acknowledged successfully.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to acknowledge incident.');
    }
  };

  const handleResolve = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.resolveIncident(selectedIncident.incident_id, {
        outcome_id: resolveOutcomeId,
        resolution_note: resolveNote,
        action_taken: resolveActionTaken,
      });
      setShowResolveModal(false);
      setSuccessMsg('Incident marked as Resolved.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resolve incident.');
    }
  };

  const handleClose = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.closeIncident(selectedIncident.incident_id);
      setSuccessMsg('Incident closed successfully.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to close incident.');
    }
  };

  const handleEscalate = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.escalateIncident(selectedIncident.incident_id, { reason: escalateReason });
      setShowEscalateModal(false);
      setSuccessMsg('Incident escalated.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to escalate incident.');
    }
  };

  const handleReopen = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.reopenIncident(selectedIncident.incident_id, { reason: reopenReason });
      setShowReopenModal(false);
      setSuccessMsg('Incident reopened.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reopen incident.');
    }
  };

  const handleReject = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.rejectIncident(selectedIncident.incident_id, { reason: rejectReason });
      setShowRejectModal(false);
      setSuccessMsg('Incident rejected as invalid.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject incident.');
    }
  };

  const handleClassify = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.classifyIncident(selectedIncident.incident_id, {
        category_id: classifyCategory || undefined,
        severity: classifySeverity || undefined,
      });
      setShowClassifyModal(false);
      setSuccessMsg('Classification updated.');
      openIncidentDetail(selectedIncident.incident_id);
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update classification.');
    }
  };

  const handleAddAddendum = async () => {
    if (!selectedIncident || !addendumContent.trim()) return;
    try {
      await incidentApi.addAddendum(selectedIncident.incident_id, {
        content: addendumContent,
        client_generated_id: crypto.randomUUID(),
      });
      setShowAddendumModal(false);
      setAddendumContent('');
      setSuccessMsg('Addendum added to case file.');
      openIncidentDetail(selectedIncident.incident_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to append addendum.');
    }
  };

  const handleShareWithClient = async () => {
    if (!selectedIncident) return;
    try {
      await incidentApi.shareWithClient(selectedIncident.incident_id, {
        title: shareTitle,
        summary: shareSummary,
        actions_taken: shareActions,
        status: 'RESOLVED',
      });
      setShowShareModal(false);
      setSuccessMsg('Approved summary published to Client Portal.');
      openIncidentDetail(selectedIncident.incident_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to publish client summary.');
    }
  };

  const handleCreateNewIncident = async (e) => {
    e.preventDefault();
    try {
      await incidentApi.createIncident({
        ...newIncidentData,
        client_generated_id: crypto.randomUUID(),
        device_time: new Date().toISOString(),
      });
      setShowNewIncidentModal(false);
      setSuccessMsg('Incident reported successfully.');
      fetchInbox();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit incident.');
    }
  };

  const handleExportCSV = async () => {
    try {
      const res = await incidentApi.exportCSV();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `incidents_export_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Failed to export CSV metadata.');
    }
  };

  const getSeverityBadge = (severity) => {
    switch (severity) {
      case 'CRITICAL':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">CRITICAL</span>;
      case 'HIGH':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">HIGH</span>;
      case 'MEDIUM':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">MEDIUM</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">LOW</span>;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'REPORTED':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">Reported</span>;
      case 'ACKNOWLEDGED':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">Acknowledged</span>;
      case 'IN_PROGRESS':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800">In Progress</span>;
      case 'ESCALATED':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">Escalated</span>;
      case 'RESOLVED':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">Resolved</span>;
      case 'CLOSED':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">Closed</span>;
      case 'REOPENED':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">Reopened</span>;
      case 'REJECTED_AS_INVALID':
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-rose-100 text-rose-800">Invalid</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ShieldAlert className="w-7 h-7 text-red-600" />
            Module 8: Incident & Request Management
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Forensic incident reporting, immutable timeline audit, guard operational requests, and client portal service tickets.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-300 rounded-lg transition"
          >
            <Download className="w-4 h-4 text-gray-500" />
            Export CSV
          </button>
          <button
            onClick={() => setShowNewIncidentModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            Report Incident
          </button>
        </div>
      </div>

      {/* Notifications / Alerts */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between text-red-800 text-sm">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 font-bold ml-4">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-emerald-800 text-sm">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 flex-shrink-0 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-4">✕</button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-gray-200 bg-white px-4 rounded-t-xl">
        <button
          onClick={() => setActiveTab('incidents')}
          className={`py-3.5 px-4 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === 'incidents'
              ? 'border-red-600 text-red-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          Incidents ({incidents.length})
        </button>
        <button
          onClick={() => setActiveTab('requests')}
          className={`py-3.5 px-4 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === 'requests'
              ? 'border-red-600 text-red-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <Layers className="w-4 h-4" />
          Guard Requests ({requests.length})
        </button>
        <button
          onClick={() => setActiveTab('tickets')}
          className={`py-3.5 px-4 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === 'tickets'
              ? 'border-red-600 text-red-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          Client Tickets ({tickets.length})
        </button>
        <button
          onClick={() => setActiveTab('aging')}
          className={`py-3.5 px-4 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
            activeTab === 'aging'
              ? 'border-red-600 text-red-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <Clock className="w-4 h-4" />
          Aging & Overdue Dashboard
        </button>
        {isAdmin && (
          <button
            onClick={() => setActiveTab('taxonomies')}
            className={`py-3.5 px-4 text-sm font-medium border-b-2 flex items-center gap-2 transition ${
              activeTab === 'taxonomies'
                ? 'border-red-600 text-red-600 font-semibold'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Filter className="w-4 h-4" />
            Categories & Configuration
          </button>
        )}
      </div>

      {/* Filter Toolbar (For Incidents, Requests, Tickets) */}
      {activeTab !== 'aging' && activeTab !== 'taxonomies' && (
        <div className="bg-white p-4 rounded-b-xl border border-t-0 border-gray-200 shadow-sm flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search case #, description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
            />
          </div>

          {activeTab === 'incidents' && (
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          )}

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
          >
            <option value="">All Statuses</option>
            <option value="REPORTED">Reported</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="ESCALATED">Escalated</option>
            <option value="RESOLVED">Resolved</option>
            <option value="CLOSED">Closed</option>
          </select>

          <select
            value={filterSite}
            onChange={(e) => setFilterSite(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
          >
            <option value="">All Sites</option>
            {sites.map((s) => (
              <option key={s.site_id} value={s.site_id}>
                {s.site_name}
              </option>
            ))}
          </select>

          <label className="flex items-center gap-1.5 text-sm text-gray-600 select-none cursor-pointer">
            <input
              type="checkbox"
              checked={filterOverdue}
              onChange={(e) => setFilterOverdue(e.target.checked)}
              className="rounded text-red-600 focus:ring-red-500 h-4 w-4"
            />
            <span>Overdue SLA Only</span>
          </label>

          <button
            onClick={fetchInbox}
            className="p-2 text-gray-500 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-300 transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {loading ? (
        <div className="bg-white p-12 text-center rounded-xl border border-gray-200">
          <RefreshCw className="w-8 h-8 text-red-600 animate-spin mx-auto mb-2" />
          <p className="text-gray-500 text-sm">Loading operational records...</p>
        </div>
      ) : (
        <>
          {/* TAB 1: Incidents Table */}
          {activeTab === 'incidents' && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-gray-600">
                  <thead className="bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-700 uppercase">
                    <tr>
                      <th className="py-3 px-4">Case #</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Site</th>
                      <th className="py-3 px-4">Reporter</th>
                      <th className="py-3 px-4">Severity</th>
                      <th className="py-3 px-4">Occurred At</th>
                      <th className="py-3 px-4">Status / Verification</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {incidents.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="text-center py-8 text-gray-400">
                          No incidents found matching current filters.
                        </td>
                      </tr>
                    ) : (
                      incidents.map((inc) => (
                        <tr key={inc.incident_id} className="hover:bg-gray-50 transition">
                          <td className="py-3 px-4 font-mono font-medium text-gray-900 flex items-center gap-1.5">
                            {inc.case_number}
                            {inc.is_sensitive && (
                              <span title="Sensitive Category - Admin Restricted">
                                <Lock className="w-3.5 h-3.5 text-red-500" />
                              </span>
                            )}
                            {inc.is_overdue && (
                              <span className="w-2 h-2 rounded-full bg-red-600 animate-pulse" title="SLA Overdue" />
                            )}
                          </td>
                          <td className="py-3 px-4 font-medium text-gray-800">{inc.category_name}</td>
                          <td className="py-3 px-4">{inc.site_name}</td>
                          <td className="py-3 px-4">{inc.guard_name}</td>
                          <td className="py-3 px-4">{getSeverityBadge(inc.current_severity)}</td>
                          <td className="py-3 px-4 whitespace-nowrap text-xs text-gray-500">
                            {new Date(inc.occurred_at).toLocaleString('en-IN', {
                              day: '2-digit',
                              month: 'short',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col gap-1">
                              {getStatusBadge(inc.status)}
                              {inc.verification_state === 'REPORTED_NOT_VERIFIED' ? (
                                <span className="text-[11px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                                  Not yet verified
                                </span>
                              ) : (
                                <span className="text-[11px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                                  Supervisor Reviewed
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={() => openIncidentDetail(inc.incident_id)}
                              className="px-3 py-1 text-xs font-medium text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 rounded border border-red-200 transition"
                            >
                              Investigate
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 2: Guard Requests Table */}
          {activeTab === 'requests' && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-gray-600">
                  <thead className="bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-700 uppercase">
                    <tr>
                      <th className="py-3 px-4">Request #</th>
                      <th className="py-3 px-4">Request Type</th>
                      <th className="py-3 px-4">Guard</th>
                      <th className="py-3 px-4">Site</th>
                      <th className="py-3 px-4">Cost Item</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Due Target</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {requests.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="text-center py-8 text-gray-400">
                          No guard operational requests found.
                        </td>
                      </tr>
                    ) : (
                      requests.map((req) => (
                        <tr key={req.request_id} className="hover:bg-gray-50 transition">
                          <td className="py-3 px-4 font-mono font-medium text-gray-900">{req.request_number}</td>
                          <td className="py-3 px-4 font-medium text-gray-800">{req.request_type_name}</td>
                          <td className="py-3 px-4">{req.guard_name}</td>
                          <td className="py-3 px-4">{req.site_name}</td>
                          <td className="py-3 px-4">
                            {req.cost_related ? (
                              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-800">
                                Cost Item (Admin Only)
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">Standard</span>
                            )}
                          </td>
                          <td className="py-3 px-4">{getStatusBadge(req.status)}</td>
                          <td className="py-3 px-4 text-xs text-gray-500">
                            {req.response_due_at ? new Date(req.response_due_at).toLocaleTimeString() : 'N/A'}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={() => {
                                setSelectedRequest(req);
                                setShowRequestReplyModal(true);
                              }}
                              className="px-3 py-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 transition"
                            >
                              Manage Request
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: Client Tickets Table */}
          {activeTab === 'tickets' && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-gray-600">
                  <thead className="bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-700 uppercase">
                    <tr>
                      <th className="py-3 px-4">Ticket #</th>
                      <th className="py-3 px-4">Client</th>
                      <th className="py-3 px-4">Site</th>
                      <th className="py-3 px-4">Type</th>
                      <th className="py-3 px-4">Subject</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Admin Routing</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {tickets.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="text-center py-8 text-gray-400">
                          No client service tickets found.
                        </td>
                      </tr>
                    ) : (
                      tickets.map((tck) => (
                        <tr key={tck.ticket_id} className="hover:bg-gray-50 transition">
                          <td className="py-3 px-4 font-mono font-medium text-gray-900">{tck.ticket_number}</td>
                          <td className="py-3 px-4 font-medium text-gray-800">{tck.client_name}</td>
                          <td className="py-3 px-4">{tck.site_name}</td>
                          <td className="py-3 px-4 text-xs font-semibold text-gray-600">{tck.ticket_type}</td>
                          <td className="py-3 px-4 truncate max-w-xs">{tck.title}</td>
                          <td className="py-3 px-4">{getStatusBadge(tck.status)}</td>
                          <td className="py-3 px-4">
                            {tck.is_admin_only ? (
                              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
                                Guard Complaint (Admin Only)
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">Supervisor</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <button
                              onClick={() => {
                                setSelectedTicket(tck);
                                setShowTicketMessageModal(true);
                              }}
                              className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 rounded border border-blue-200 transition"
                            >
                              View & Reply
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: Aging & Overdue Dashboard */}
          {activeTab === 'aging' && agingData && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white p-5 rounded-xl border border-red-200 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-red-600 tracking-wider">Unacknowledged Incidents</span>
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                  </div>
                  <div className="text-3xl font-extrabold text-gray-900 mt-2">{agingData.overdue_incidents_count}</div>
                  <p className="text-xs text-gray-500 mt-1">Pending acknowledgement &gt; 30 mins</p>
                </div>

                <div className="bg-white p-5 rounded-xl border border-amber-200 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-amber-600 tracking-wider">Stale Investigations</span>
                    <Clock className="w-5 h-5 text-amber-500" />
                  </div>
                  <div className="text-3xl font-extrabold text-gray-900 mt-2">{agingData.stale_investigations_count}</div>
                  <p className="text-xs text-gray-500 mt-1">Active cases open &gt; 24 hours</p>
                </div>

                <div className="bg-white p-5 rounded-xl border border-indigo-200 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-indigo-600 tracking-wider">Overdue Guard Requests</span>
                    <Layers className="w-5 h-5 text-indigo-500" />
                  </div>
                  <div className="text-3xl font-extrabold text-gray-900 mt-2">{agingData.overdue_requests_count}</div>
                  <p className="text-xs text-gray-500 mt-1">Relief & equipment requests past SLA</p>
                </div>

                <div className="bg-white p-5 rounded-xl border border-blue-200 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-blue-600 tracking-wider">Overdue Client Tickets</span>
                    <MessageSquare className="w-5 h-5 text-blue-500" />
                  </div>
                  <div className="text-3xl font-extrabold text-gray-900 mt-2">{agingData.overdue_tickets_count}</div>
                  <p className="text-xs text-gray-500 mt-1">Client queries & issues unresolved</p>
                </div>
              </div>

              <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
                <h3 className="text-base font-bold text-gray-900 mb-2">Escalation Policy & Strict SLA Rules</h3>
                <ul className="text-sm text-gray-600 space-y-2 list-disc pl-5">
                  <li><strong>Critical Incidents:</strong> Primary supervisor notification immediately; escalates to Backup Supervisor after 15 mins unacknowledged, Admin after 30 mins.</li>
                  <li><strong>High Severity Incidents:</strong> Escalates to Backup Supervisor after 30 mins unacknowledged; Admin review mandatory before case closure.</li>
                  <li><strong>Supervisor Conduct Conflict:</strong> When a report implicates supervisor conduct, self-closure is prevented and handling is rerouted to Admin.</li>
                  <li><strong>Client Complaints on Named Guards:</strong> Automatically flagged and routed to Admin only, safeguarding guard-supervisor relationships.</li>
                </ul>
              </div>
            </div>
          )}

          {/* TAB 5: Categories & Taxonomies Configuration (Admin Only) */}
          {activeTab === 'taxonomies' && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <Filter className="w-5 h-5 text-gray-500" />
                  Configured Incident Categories
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-gray-600">
                    <thead className="bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-700 uppercase">
                      <tr>
                        <th className="py-2.5 px-3">Name</th>
                        <th className="py-2.5 px-3">Code</th>
                        <th className="py-2.5 px-3">Default Severity</th>
                        <th className="py-2.5 px-3">Sensitive</th>
                        <th className="py-2.5 px-3">Client Sharing Policy</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {categories.map((c) => (
                        <tr key={c.category_id} className="hover:bg-gray-50">
                          <td className="py-2.5 px-3 font-medium text-gray-900">{c.name}</td>
                          <td className="py-2.5 px-3 font-mono text-xs">{c.code}</td>
                          <td className="py-2.5 px-3">{getSeverityBadge(c.default_severity)}</td>
                          <td className="py-2.5 px-3">
                            {c.sensitive ? (
                              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">
                                SENSITIVE (Admin Gated)
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">Standard</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-xs font-medium text-gray-700">{c.sharing_policy}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* INCIDENT DETAIL & INVESTIGATION MODAL                                   */}
      {/* ---------------------------------------------------------------------- */}
      {selectedIncident && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex justify-center items-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-gray-200">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b border-gray-200 p-5 flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <ShieldAlert className="w-6 h-6 text-red-600" />
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-gray-900 font-mono">{selectedIncident.case_number}</h2>
                    {getSeverityBadge(selectedIncident.current_severity)}
                    {getStatusBadge(selectedIncident.status)}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Category: <span className="font-semibold">{selectedIncident.category_name}</span> | Site: <span className="font-semibold">{selectedIncident.site_name}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedIncident(null)}
                className="text-gray-400 hover:text-gray-600 p-2 rounded-lg text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Verification State Banner */}
              <div className={`p-4 rounded-xl border flex items-center gap-3 ${
                selectedIncident.verification_state === 'REPORTED_NOT_VERIFIED'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-900'
              }`}>
                {selectedIncident.verification_state === 'REPORTED_NOT_VERIFIED' ? (
                  <AlertCircle className="w-5 h-5 flex-shrink-0 text-amber-600" />
                ) : (
                  <CheckCircle className="w-5 h-5 flex-shrink-0 text-emerald-600" />
                )}
                <div className="text-xs">
                  <p className="font-bold uppercase tracking-wide">
                    {selectedIncident.verification_state === 'REPORTED_NOT_VERIFIED'
                      ? 'Reported by guard, not yet verified'
                      : 'Supervisor Reviewed & Documented'}
                  </p>
                  <p className="text-gray-600 mt-0.5">
                    {selectedIncident.verification_state === 'REPORTED_NOT_VERIFIED'
                      ? "The system records the guard's account and evidence integrity. A supervisor must investigate on site."
                      : "Investigation recorded by assigned supervisor. High/Critical cases require final Admin sign-off."}
                  </p>
                </div>
              </div>

              {/* Original Report Section (Strictly Immutable) */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold uppercase text-slate-700 tracking-wider flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-slate-500" />
                    Original Guard Submission (Immutable)
                  </span>
                  <span className="text-xs text-slate-500">
                    Reporter: {selectedIncident.guard_name} ({selectedIncident.guard_code})
                  </span>
                </div>
                <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                  {selectedIncident.description}
                </p>
                <div className="mt-3 pt-3 border-t border-slate-200 text-xs text-slate-500 flex flex-wrap gap-4">
                  <span>Occurred: <strong>{new Date(selectedIncident.occurred_at).toLocaleString()}</strong></span>
                  <span>Submitted: <strong>{new Date(selectedIncident.submitted_at).toLocaleString()}</strong></span>
                  <span>Original Severity: <strong>{selectedIncident.original_severity}</strong></span>
                  <span>Outside Duty: <strong>{selectedIncident.reported_outside_duty ? 'Yes' : 'No'}</strong></span>
                </div>
              </div>

              {/* Telemetry & GPS Context Banner */}
              {selectedIncident.context && (
                <div className="bg-blue-50 p-4 rounded-xl border border-blue-200 text-xs text-blue-900">
                  <span className="font-bold uppercase tracking-wider block mb-1">
                    {selectedIncident.context.location_label}
                  </span>
                  <div className="flex flex-wrap gap-4 text-blue-800">
                    <span>Latitude: <strong>{selectedIncident.context.latitude || 'N/A'}</strong></span>
                    <span>Longitude: <strong>{selectedIncident.context.longitude || 'N/A'}</strong></span>
                    <span>Accuracy: <strong>±{selectedIncident.context.accuracy_m || 10}m</strong></span>
                    <span>Source: <strong>{selectedIncident.context.position_source || 'Site GPS Anchor'}</strong></span>
                  </div>
                </div>
              )}

              {/* Evidence Attachments Gallery with Hash Audit */}
              <div>
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Eye className="w-4 h-4 text-gray-500" />
                  Evidence Files & SHA-256 Hashes ({selectedIncident.attachments?.length || 0})
                </h3>
                {selectedIncident.attachments && selectedIncident.attachments.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {selectedIncident.attachments.map((att) => (
                      <div key={att.attachment_id} className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs space-y-1">
                        <div className="flex justify-between items-center">
                          <span className="font-semibold text-gray-800">{att.media_type}: {att.original_file_name || 'Captured Photo'}</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            att.verification_state === 'VERIFIED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                          }`}>
                            {att.verification_state}
                          </span>
                        </div>
                        <div className="font-mono text-[10px] text-gray-500 truncate" title={att.original_hash}>
                          SHA-256: {att.original_hash}
                        </div>
                        <div className="text-gray-400 text-[10px]">
                          Size: {(att.file_size_bytes / 1024).toFixed(1)} KB | Source: {att.source_type}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">No media attachments attached to this report.</p>
                )}
              </div>

              {/* Append-Only Addendums */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
                    Addendums ({selectedIncident.addendums?.length || 0})
                  </h3>
                  <button
                    onClick={() => setShowAddendumModal(true)}
                    className="text-xs font-medium text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 px-2.5 py-1 rounded border border-red-200"
                  >
                    + Add Addendum
                  </button>
                </div>
                {selectedIncident.addendums && selectedIncident.addendums.length > 0 ? (
                  <div className="space-y-2">
                    {selectedIncident.addendums.map((add) => (
                      <div key={add.addendum_id} className="p-3 bg-amber-50/50 border border-amber-200 rounded-lg text-xs">
                        <div className="flex justify-between text-gray-500 mb-1">
                          <span className="font-semibold text-gray-800">By: {add.author_name}</span>
                          <span>{new Date(add.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-gray-800 whitespace-pre-wrap">{add.content}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">No subsequent addendums recorded.</p>
                )}
              </div>

              {/* Immutable Timeline */}
              <div>
                <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-2">
                  Immutable Case Timeline
                </h3>
                <div className="space-y-2 border-l-2 border-red-200 pl-4 ml-2">
                  {selectedIncident.timeline && selectedIncident.timeline.map((item) => (
                    <div key={item.timeline_id} className="text-xs space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900">{item.action_type}</span>
                        <span className="text-gray-400">• {new Date(item.created_at).toLocaleTimeString()}</span>
                        <span className="font-mono text-[10px] text-gray-400">[{item.audit_reference}]</span>
                      </div>
                      <p className="text-gray-600">{item.description}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Client Shared Version Status */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold uppercase text-gray-700 flex items-center gap-1.5">
                    <Share2 className="w-4 h-4 text-gray-500" />
                    Client Shared Version
                  </span>
                  <button
                    onClick={() => {
                      setShareTitle(`Incident Summary: ${selectedIncident.case_number}`);
                      setShareSummary(selectedIncident.description.slice(0, 150));
                      setShareActions(selectedIncident.resolution_action_taken || 'Security team investigated and secured premises.');
                      setShowShareModal(true);
                    }}
                    className="text-xs font-medium text-blue-600 hover:text-blue-700 bg-blue-50 px-2.5 py-1 rounded border border-blue-200"
                  >
                    Edit / Publish Client Summary
                  </button>
                </div>
                {selectedIncident.latest_client_version ? (
                  <div className="text-xs text-gray-600 space-y-1">
                    <p>Title: <strong>{selectedIncident.latest_client_version.title}</strong></p>
                    <p>Status: <span className="text-emerald-700 font-semibold">{selectedIncident.latest_client_version.sharing_state}</span></p>
                    <p className="text-gray-500 italic">"{selectedIncident.latest_client_version.summary}"</p>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">No approved summary has been shared with client yet.</p>
                )}
              </div>

              {/* ACTION TOOLBAR (SUPERVISOR / ADMIN) */}
              <div className="pt-4 border-t border-gray-200 flex flex-wrap gap-2 justify-end">
                {selectedIncident.status === 'REPORTED' && (
                  <button
                    onClick={handleAcknowledge}
                    className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
                  >
                    Acknowledge Case
                  </button>
                )}

                <button
                  onClick={() => setShowClassifyModal(true)}
                  className="px-3 py-2 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Change Category/Severity
                </button>

                {selectedIncident.status !== 'RESOLVED' && selectedIncident.status !== 'CLOSED' && (
                  <>
                    <button
                      onClick={() => setShowEscalateModal(true)}
                      className="px-3 py-2 text-xs font-semibold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg"
                    >
                      Escalate to Admin
                    </button>
                    <button
                      onClick={() => setShowResolveModal(true)}
                      className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm"
                    >
                      Resolve Case
                    </button>
                  </>
                )}

                {selectedIncident.status === 'RESOLVED' && (
                  <button
                    onClick={handleClose}
                    className="px-4 py-2 text-xs font-bold text-white bg-gray-800 hover:bg-gray-900 rounded-lg shadow-sm"
                  >
                    Close Incident
                  </button>
                )}

                {selectedIncident.status === 'CLOSED' && isAdmin && (
                  <button
                    onClick={() => setShowReopenModal(true)}
                    className="px-3 py-2 text-xs font-semibold text-orange-700 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-lg"
                  >
                    Reopen Case
                  </button>
                )}

                {selectedIncident.status !== 'CLOSED' && selectedIncident.status !== 'REJECTED_AS_INVALID' && (
                  <button
                    onClick={() => setShowRejectModal(true)}
                    className="px-3 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg"
                  >
                    Reject as Invalid
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* ADDENDUM MODAL                                                         */}
      {/* ---------------------------------------------------------------------- */}
      {showAddendumModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">Add Addendum to Case</h3>
            <p className="text-xs text-gray-500">
              The original report description is immutable. This addendum will be appended as a separate, dated entry with your signature.
            </p>
            <textarea
              rows="4"
              value={addendumContent}
              onChange={(e) => setAddendumContent(e.target.value)}
              placeholder="Enter supplemental details, corrections, or updates..."
              className="w-full text-sm p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:outline-none"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAddendumModal(false)}
                className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleAddAddendum}
                className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-lg"
              >
                Append Addendum
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* RESOLVE INCIDENT MODAL                                                 */}
      {/* ---------------------------------------------------------------------- */}
      {showResolveModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">Document Resolution Outcome</h3>
            <p className="text-xs text-gray-500">
              Every resolved incident requires an official outcome classification and a detailed explanation of action taken.
            </p>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Resolution Outcome *</label>
              <select
                value={resolveOutcomeId}
                onChange={(e) => setResolveOutcomeId(e.target.value)}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
                required
              >
                <option value="">Select Outcome...</option>
                {outcomes.map((o) => (
                  <option key={o.outcome_id} value={o.outcome_id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Resolution Note *</label>
              <textarea
                rows="3"
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
                placeholder="Explain the findings and final disposition..."
                className="w-full p-2.5 text-sm border border-gray-300 rounded-lg"
                required
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Action Taken</label>
              <input
                type="text"
                value={resolveActionTaken}
                onChange={(e) => setResolveActionTaken(e.target.value)}
                placeholder="Immediate actions taken on site..."
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowResolveModal(false)}
                className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleResolve}
                className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg"
              >
                Confirm Resolution
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* CLIENT SHARING WORKSPACE MODAL                                         */}
      {/* ---------------------------------------------------------------------- */}
      {showShareModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <Share2 className="w-5 h-5 text-blue-600" />
              Prepare Client-Safe Incident Version
            </h3>
            <p className="text-xs text-gray-500">
              Clients never receive raw guard reports, internal investigation notes, guard home/phone details, or raw coordinates.
            </p>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Approved Title *</label>
              <input
                type="text"
                value={shareTitle}
                onChange={(e) => setShareTitle(e.target.value)}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Plain-Language Summary *</label>
              <textarea
                rows="3"
                value={shareSummary}
                onChange={(e) => setShareSummary(e.target.value)}
                className="w-full p-2.5 text-sm border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Actions Taken *</label>
              <textarea
                rows="2"
                value={shareActions}
                onChange={(e) => setShareActions(e.target.value)}
                className="w-full p-2.5 text-sm border border-gray-300 rounded-lg"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowShareModal(false)}
                className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleShareWithClient}
                className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg"
              >
                Approve & Publish to Client
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* REOPEN MODAL (ADMIN ONLY)                                              */}
      {/* ---------------------------------------------------------------------- */}
      {showReopenModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">Reopen Closed Incident</h3>
            <p className="text-xs text-gray-500">
              Only Admin can reopen a closed incident. A mandatory reason must be supplied for the immutable timeline.
            </p>
            <textarea
              rows="3"
              value={reopenReason}
              onChange={(e) => setReopenReason(e.target.value)}
              placeholder="State the reason for reopening (e.g. new evidence, client appeal)..."
              className="w-full text-sm p-3 border border-gray-300 rounded-lg"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowReopenModal(false)} className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg">
                Cancel
              </button>
              <button onClick={handleReopen} className="px-4 py-2 text-xs font-bold text-white bg-orange-600 hover:bg-orange-700 rounded-lg">
                Confirm Reopen
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* ESCALATE MODAL                                                         */}
      {/* ---------------------------------------------------------------------- */}
      {showEscalateModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">Escalate Incident</h3>
            <textarea
              rows="3"
              value={escalateReason}
              onChange={(e) => setEscalateReason(e.target.value)}
              placeholder="State reason for escalation to Admin..."
              className="w-full text-sm p-3 border border-gray-300 rounded-lg"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowEscalateModal(false)} className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg">
                Cancel
              </button>
              <button onClick={handleEscalate} className="px-4 py-2 text-xs font-bold text-white bg-purple-600 hover:bg-purple-700 rounded-lg">
                Escalate
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* REJECT MODAL                                                           */}
      {/* ---------------------------------------------------------------------- */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">Reject Incident as Invalid</h3>
            <p className="text-xs text-gray-500">
              The report will not be deleted from the database. It will be permanently marked as rejected with your documented reason.
            </p>
            <textarea
              rows="3"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter explanation for invalidating this report..."
              className="w-full text-sm p-3 border border-gray-300 rounded-lg"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowRejectModal(false)} className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg">
                Cancel
              </button>
              <button onClick={handleReject} className="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg">
                Reject Case
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* CLASSIFICATION UPDATE MODAL                                            */}
      {/* ---------------------------------------------------------------------- */}
      {showClassifyModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">Update Category & Severity</h3>
            <p className="text-xs text-gray-500">
              The original guard-suggested values will be safely preserved in the audit log.
            </p>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">New Category</label>
              <select
                value={classifyCategory}
                onChange={(e) => setClassifyCategory(e.target.value)}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
              >
                <option value="">Keep current category</option>
                {categories.map((c) => (
                  <option key={c.category_id} value={c.category_id}>
                    {c.name} {c.sensitive ? '(Sensitive)' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">New Severity</label>
              <select
                value={classifySeverity}
                onChange={(e) => setClassifySeverity(e.target.value)}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
              >
                <option value="">Keep current severity</option>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowClassifyModal(false)} className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg">
                Cancel
              </button>
              <button onClick={handleClassify} className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-lg">
                Save Classification
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* REPORT NEW INCIDENT MODAL                                              */}
      {/* ---------------------------------------------------------------------- */}
      {showNewIncidentModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <form onSubmit={handleCreateNewIncident} className="bg-white rounded-xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              Report Security Occurrence
            </h3>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Site *</label>
              <select
                value={newIncidentData.site_id}
                onChange={(e) => setNewIncidentData({ ...newIncidentData, site_id: e.target.value })}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
                required
              >
                <option value="">Select Site...</option>
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.site_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Incident Category *</label>
              <select
                value={newIncidentData.category_id}
                onChange={(e) => setNewIncidentData({ ...newIncidentData, category_id: e.target.value })}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
                required
              >
                <option value="">Select Category...</option>
                {categories.map((c) => (
                  <option key={c.category_id} value={c.category_id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Occurred Time *</label>
              <input
                type="datetime-local"
                value={newIncidentData.occurred_at}
                onChange={(e) => setNewIncidentData({ ...newIncidentData, occurred_at: e.target.value })}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
                required
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Suggested Severity *</label>
              <select
                value={newIncidentData.suggested_severity}
                onChange={(e) => setNewIncidentData({ ...newIncidentData, suggested_severity: e.target.value })}
                className="w-full p-2 text-sm border border-gray-300 rounded-lg"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">Short Description (Account) *</label>
              <textarea
                rows="3"
                value={newIncidentData.description}
                onChange={(e) => setNewIncidentData({ ...newIncidentData, description: e.target.value })}
                placeholder="What occurred? Provide objective facts..."
                className="w-full p-2.5 text-sm border border-gray-300 rounded-lg"
                required
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowNewIncidentModal(false)}
                className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-lg"
              >
                Submit Incident Report
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* GUARD REQUEST ACTION MODAL                                             */}
      {/* ---------------------------------------------------------------------- */}
      {showRequestReplyModal && selectedRequest && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-gray-900">
              Manage Request: {selectedRequest.request_number}
            </h3>
            <div className="text-xs bg-gray-50 p-3 rounded-lg text-gray-700 space-y-1">
              <p>Type: <strong>{selectedRequest.request_type_name}</strong></p>
              <p>Guard: <strong>{selectedRequest.guard_name}</strong></p>
              <p>Description: <em>"{selectedRequest.description}"</em></p>
            </div>
            <textarea
              rows="3"
              value={requestReplyNote}
              onChange={(e) => setRequestReplyNote(e.target.value)}
              placeholder="Action note or reply message..."
              className="w-full text-sm p-3 border border-gray-300 rounded-lg"
            />
            <div className="flex flex-wrap justify-end gap-2">
              <button
                onClick={() => setShowRequestReplyModal(false)}
                className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  await incidentApi.actionGuardRequest(selectedRequest.request_id, {
                    action: 'REJECT',
                    note: requestReplyNote || 'Rejected by supervisor.',
                  });
                  setShowRequestReplyModal(false);
                  fetchInbox();
                }}
                className="px-3 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg"
              >
                Reject Request
              </button>
              <button
                onClick={async () => {
                  await incidentApi.actionGuardRequest(selectedRequest.request_id, {
                    action: 'APPROVE',
                    note: requestReplyNote,
                  });
                  setShowRequestReplyModal(false);
                  fetchInbox();
                }}
                className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg"
              >
                Approve Request
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* CLIENT TICKET REPLY MODAL                                              */}
      {/* ---------------------------------------------------------------------- */}
      {showTicketMessageModal && selectedTicket && (
        <div className="fixed inset-0 z-50 bg-black/50 flex justify-center items-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-lg w-full space-y-4 max-h-[85vh] overflow-y-auto">
            <h3 className="text-base font-bold text-gray-900">
              Ticket #{selectedTicket.ticket_number} - {selectedTicket.title}
            </h3>
            <p className="text-xs text-gray-600 bg-slate-50 p-3 rounded-lg border border-slate-200">
              {selectedTicket.description}
            </p>

            {/* Existing Messages */}
            <div className="space-y-2 max-h-48 overflow-y-auto border p-2 rounded-lg">
              {selectedTicket.messages && selectedTicket.messages.map((m) => (
                <div key={m.message_id} className={`p-2 rounded text-xs ${
                  m.visibility === 'INTERNAL' ? 'bg-amber-50 border border-amber-200' : 'bg-blue-50 border border-blue-200'
                }`}>
                  <div className="flex justify-between font-semibold mb-0.5">
                    <span>{m.actor_name} {m.visibility === 'INTERNAL' && '(Internal Note)'}</span>
                    <span className="text-[10px] text-gray-400">{new Date(m.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p>{m.message}</p>
                </div>
              ))}
            </div>

            <textarea
              rows="3"
              value={ticketMessageText}
              onChange={(e) => setTicketMessageText(e.target.value)}
              placeholder="Type message..."
              className="w-full text-sm p-3 border border-gray-300 rounded-lg"
            />

            {!isGuard && (
              <div className="flex items-center gap-3">
                <label className="text-xs font-semibold text-gray-700">Visibility:</label>
                <label className="flex items-center gap-1 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="ticketVis"
                    value="CLIENT_VISIBLE"
                    checked={ticketMessageVisibility === 'CLIENT_VISIBLE'}
                    onChange={() => setTicketMessageVisibility('CLIENT_VISIBLE')}
                  />
                  Client Visible
                </label>
                <label className="flex items-center gap-1 text-xs cursor-pointer">
                  <input
                    type="radio"
                    name="ticketVis"
                    value="INTERNAL"
                    checked={ticketMessageVisibility === 'INTERNAL'}
                    onChange={() => setTicketMessageVisibility('INTERNAL')}
                  />
                  Internal Note (Private)
                </label>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowTicketMessageModal(false)}
                className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg"
              >
                Close
              </button>
              <button
                onClick={async () => {
                  if (!ticketMessageText.trim()) return;
                  await incidentApi.sendMessageClientTicket(selectedTicket.ticket_id, {
                    message: ticketMessageText,
                    visibility: ticketMessageVisibility,
                  });
                  setShowTicketMessageModal(false);
                  setTicketMessageText('');
                  fetchInbox();
                }}
                className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                Send Message
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

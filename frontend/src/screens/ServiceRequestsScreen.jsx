import React, { useState, useEffect } from 'react';
import {
  FileText, Plus, Search, Filter, CheckCircle2, XCircle, Clock,
  ArrowRight, Shield, AlertCircle, Building2, MapPin, Calendar,
  DollarSign, ChevronRight, MessageSquare, Send, CheckSquare, RefreshCw
} from 'lucide-react';
import { commercialsApi, masterApi } from '../api';

export default function ServiceRequestsScreen({ user }) {
  const [activeTab, setActiveTab] = useState('requests'); // 'requests' | 'quotes'
  const [requests, setRequests] = useState([]);
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [postTypes, setPostTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Modals & Drawers
  const [showCreateRequestModal, setShowCreateRequestModal] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [showQuoteBuilder, setShowQuoteBuilder] = useState(false);
  const [showCounterModal, setShowCounterModal] = useState(false);
  const [showSurveyModal, setShowSurveyModal] = useState(false);
  const [showClarifyModal, setShowClarifyModal] = useState(false);

  // Form states
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  // New Request Form
  const [newRequestForm, setNewRequestForm] = useState({
    client_id: '',
    service_purpose: 'office',
    start_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
    duration_type: 'ongoing',
    end_date: '',
    site_contact_name: '',
    site_contact_phone: '',
    new_site_name: '',
    new_site_address: '',
    special_requirements: '',
    lines: [
      { post_type_id: '', guard_count: 2, shift_information: 'Day Shift 8hr', hours_per_day: 8.0, working_days: ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'] }
    ]
  });

  // Quotation Builder Form
  const [quoteForm, setQuoteForm] = useState({
    quotation_date: new Date().toISOString().split('T')[0],
    validity_days: 15,
    payment_terms: 'Net 30 days from invoice date',
    additional_terms: 'Statutory compliance included in accordance with Karnataka state regulations.',
    internal_notes: '',
    tax_note: 'Applicable taxes extra',
    lines: []
  });

  // Counter Form
  const [counterForm, setCounterForm] = useState({
    comment: '',
    proposed_rate: '',
    proposed_guard_count: ''
  });

  // Acceptance Checkbox
  const [acceptanceConfirmed, setAcceptanceConfirmed] = useState(false);

  // Survey Form
  const [surveyForm, setSurveyForm] = useState({
    survey_date: new Date().toISOString().split('T')[0],
    visited_by: '',
    findings: '',
    notes: ''
  });

  // Clarify Form
  const [clarifyMessage, setClarifyMessage] = useState('');

  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';
  const isClient = user?.role === 'CLIENT';

  const loadData = async () => {
    setLoading(true);
    try {
      const [reqRes, qRes, clientsRes, ptRes] = await Promise.all([
        commercialsApi.getRequests(),
        commercialsApi.getQuotes(),
        isAdmin ? masterApi.getClients() : Promise.resolve({ data: [] }),
        masterApi.getPostTypes()
      ]);
      setRequests(reqRes.data || []);
      setQuotes(qRes.data || []);
      if (clientsRes?.data) setClients(clientsRes.data);
      if (ptRes?.data) setPostTypes(ptRes.data);
    } catch (err) {
      console.error('Failed to load commercials data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateRequest = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setActionError('');
    try {
      const payload = { ...newRequestForm };
      if (!isAdmin && user?.client_company_id) {
        delete payload.client_id;
      }
      if (!payload.end_date) delete payload.end_date;
      await commercialsApi.createRequest(payload);
      setShowCreateRequestModal(false);
      setActionSuccess('Service request submitted successfully.');
      loadData();
    } catch (err) {
      setActionError(err.message || 'Failed to submit service request.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenQuoteBuilder = (request) => {
    setSelectedRequest(request);
    const initialLines = (request.lines || []).map(l => ({
      post_type_id: l.post_type,
      shift_hours: l.hours_per_day || 8.0,
      headcount: l.guard_count || 1,
      billing_unit: 'per_guard_per_month',
      unit_rate: 26000.00,
      line_total: (l.guard_count || 1) * 26000.00
    }));

    setQuoteForm({
      request_id: request.request_id,
      quotation_date: new Date().toISOString().split('T')[0],
      validity_days: 15,
      payment_terms: 'Net 30 days from invoice date',
      additional_terms: 'Includes uniform, basic training, and statutory provident fund compliance.',
      internal_notes: 'Calculated with 14% gross margin threshold.',
      tax_note: 'Applicable taxes extra',
      lines: initialLines
    });
    setShowQuoteBuilder(true);
  };

  const handleSaveQuote = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setActionError('');
    try {
      await commercialsApi.createQuote(quoteForm);
      setShowQuoteBuilder(false);
      setActionSuccess('Draft quotation prepared successfully.');
      loadData();
    } catch (err) {
      setActionError(err.message || 'Failed to create quotation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendQuote = async (versionId) => {
    if (!window.confirm('Send this quotation to the client? Once sent, this version becomes immutable.')) return;
    setSubmitting(true);
    setActionError('');
    try {
      await commercialsApi.sendQuote(versionId);
      setActionSuccess('Quotation sent to client.');
      loadData();
      if (selectedQuote) {
        const updated = await commercialsApi.getQuote(selectedQuote.quotation_id);
        setSelectedQuote(updated.data);
      }
    } catch (err) {
      setActionError(err.message || 'Failed to send quotation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAcceptQuote = async (versionId) => {
    if (!acceptanceConfirmed) {
      setActionError('You must check the confirmation box to accept the quotation terms.');
      return;
    }
    setSubmitting(true);
    setActionError('');
    try {
      await commercialsApi.acceptQuote(versionId, { confirmation_checked: true });
      setActionSuccess('Quotation accepted! Your acceptance has been officially recorded.');
      setAcceptanceConfirmed(false);
      loadData();
      if (selectedQuote) {
        const updated = await commercialsApi.getQuote(selectedQuote.quotation_id);
        setSelectedQuote(updated.data);
      }
    } catch (err) {
      setActionError(err.message || 'Failed to accept quotation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCounterQuote = async (e) => {
    e.preventDefault();
    if (!selectedQuote) return;
    const version = selectedQuote.versions?.[selectedQuote.versions.length - 1];
    if (!version) return;

    setSubmitting(true);
    setActionError('');
    try {
      await commercialsApi.counterQuote(version.quotation_version_id, counterForm);
      setShowCounterModal(false);
      setCounterForm({ comment: '', proposed_rate: '', proposed_guard_count: '' });
      setActionSuccess('Counter proposal submitted.');
      loadData();
      const updated = await commercialsApi.getQuote(selectedQuote.quotation_id);
      setSelectedQuote(updated.data);
    } catch (err) {
      setActionError(err.message || 'Failed to submit counter proposal.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleConvertQuote = async (versionId) => {
    if (!window.confirm('Convert this accepted quotation into Master Data records (Site, Agreement, Billing Rates, Manpower Requirements)?')) return;
    setSubmitting(true);
    setActionError('');
    try {
      const res = await commercialsApi.convertQuote(versionId);
      setActionSuccess(`Successfully created draft Master Data site & agreement records (Ref: ${res.data.conversion_reference}).`);
      loadData();
      if (selectedQuote) {
        const updated = await commercialsApi.getQuote(selectedQuote.quotation_id);
        setSelectedQuote(updated.data);
      }
    } catch (err) {
      setActionError(err.message || 'Failed to convert quotation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordSurvey = async (e) => {
    e.preventDefault();
    if (!selectedRequest) return;
    setSubmitting(true);
    setActionError('');
    try {
      await commercialsApi.recordSurvey(selectedRequest.request_id, surveyForm);
      setShowSurveyModal(false);
      setSurveyForm({ survey_date: new Date().toISOString().split('T')[0], visited_by: '', findings: '', notes: '' });
      setActionSuccess('Site survey findings recorded.');
      loadData();
    } catch (err) {
      setActionError(err.message || 'Failed to record site survey.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClarify = async (e) => {
    e.preventDefault();
    if (!selectedRequest) return;
    setSubmitting(true);
    setActionError('');
    try {
      await commercialsApi.clarifyRequest(selectedRequest.request_id, { message: clarifyMessage });
      setShowClarifyModal(false);
      setClarifyMessage('');
      setActionSuccess('Clarification request posted to client.');
      loadData();
    } catch (err) {
      setActionError(err.message || 'Failed to request clarification.');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    const map = {
      submitted: { bg: 'bg-blue-50 text-blue-700 border-blue-200', label: 'Submitted' },
      under_review: { bg: 'bg-amber-50 text-amber-700 border-amber-200', label: 'Under Review' },
      awaiting_client: { bg: 'bg-purple-50 text-purple-700 border-purple-200', label: 'Awaiting Client' },
      survey_scheduled: { bg: 'bg-indigo-50 text-indigo-700 border-indigo-200', label: 'Survey Done' },
      quoted: { bg: 'bg-sky-50 text-sky-700 border-sky-200', label: 'Quoted' },
      countered: { bg: 'bg-orange-50 text-orange-700 border-orange-200', label: 'Countered' },
      accepted: { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', label: 'Accepted' },
      converted: { bg: 'bg-teal-50 text-teal-700 border-teal-200', label: 'Converted' },
      withdrawn: { bg: 'bg-gray-100 text-gray-600 border-gray-200', label: 'Withdrawn' },
      sent: { bg: 'bg-blue-50 text-blue-700 border-blue-200', label: 'Sent' },
      draft: { bg: 'bg-gray-100 text-gray-700 border-gray-200', label: 'Draft' },
      superseded: { bg: 'bg-gray-50 text-gray-400 border-gray-200', label: 'Superseded' },
    };
    const s = map[status?.toLowerCase()] || { bg: 'bg-gray-50 text-gray-700 border-gray-200', label: status };
    return (
      <span className={`px-2 py-0.5 text-xs font-medium rounded border ${s.bg}`}>
        {s.label}
      </span>
    );
  };

  const filteredRequests = requests.filter(r => {
    const matchesSearch =
      (r.request_reference || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.client_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.new_site_name || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || r.status?.toUpperCase() === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const filteredQuotes = quotes.filter(q => {
    const matchesSearch =
      (q.quotation_no || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (q.client_name || '').toLowerCase().includes(searchTerm.toLowerCase());
    return matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">Service Requests & Quotations</h1>
          <p className="text-xs text-gray-500 mt-1">
            Manage client guarding inquiries, site surveys, quotation proposals, and commercial conversions.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="p-2 border border-gray-300 rounded-md text-gray-600 hover:bg-gray-50"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowCreateRequestModal(true)}
            className="px-3.5 py-2 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 flex items-center space-x-1.5 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Service Request</span>
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-md flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm">
          <div className="text-xs text-gray-500 font-medium">Total Requests</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{requests.length}</div>
        </div>
        <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm">
          <div className="text-xs text-gray-500 font-medium">Awaiting Quotation</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">
            {requests.filter(r => ['submitted', 'under_review', 'survey_scheduled'].includes(r.status)).length}
          </div>
        </div>
        <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm">
          <div className="text-xs text-gray-500 font-medium">Counter Proposals</div>
          <div className="text-2xl font-bold text-orange-600 mt-1">
            {requests.filter(r => r.status === 'countered').length}
          </div>
        </div>
        <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm">
          <div className="text-xs text-gray-500 font-medium">Accepted & Converted</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">
            {requests.filter(r => ['accepted', 'converted'].includes(r.status)).length}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 space-x-8">
        <button
          onClick={() => setActiveTab('requests')}
          className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition ${
            activeTab === 'requests'
              ? 'border-slate-900 text-slate-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Service Requests ({requests.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('quotes')}
          className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition ${
            activeTab === 'quotes'
              ? 'border-slate-900 text-slate-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <DollarSign className="w-4 h-4" />
          <span>Quotations ({quotes.length})</span>
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
          <input
            type="text"
            placeholder={activeTab === 'requests' ? "Search reference, client, or site..." : "Search quotation number or client..."}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-xs focus:ring-1 focus:ring-slate-900 focus:outline-none"
          />
        </div>
        {activeTab === 'requests' && (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-xs bg-white focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="AWAITING_CLIENT">Awaiting Client</option>
            <option value="SURVEY_SCHEDULED">Survey Scheduled</option>
            <option value="QUOTED">Quoted</option>
            <option value="COUNTERED">Countered</option>
            <option value="ACCEPTED">Accepted</option>
            <option value="CONVERTED">Converted</option>
            <option value="WITHDRAWN">Withdrawn</option>
          </select>
        )}
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="p-12 text-center text-xs text-gray-500">Loading data...</div>
      ) : activeTab === 'requests' ? (
        /* SERVICE REQUESTS TABLE */
        <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="p-3">Reference</th>
                <th className="p-3">Client</th>
                <th className="p-3">Target Site / Scope</th>
                <th className="p-3">Purpose</th>
                <th className="p-3">Start Date</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 text-gray-700">
              {filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan="7" className="p-8 text-center text-gray-400">
                    No service requests found.
                  </td>
                </tr>
              ) : (
                filteredRequests.map(r => (
                  <tr key={r.request_id} className="hover:bg-gray-50/80 transition">
                    <td className="p-3 font-semibold text-gray-900">{r.request_reference}</td>
                    <td className="p-3 font-medium">{r.client_name}</td>
                    <td className="p-3">
                      <div>{r.new_site_name || r.existing_site_name || 'Unspecified Site'}</div>
                      <div className="text-[11px] text-gray-400 truncate max-w-xs">{r.new_site_address || ''}</div>
                    </td>
                    <td className="p-3 capitalize">{r.service_purpose}</td>
                    <td className="p-3">{r.start_date}</td>
                    <td className="p-3">{getStatusBadge(r.status)}</td>
                    <td className="p-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        onClick={() => setSelectedRequest(r)}
                        className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded font-medium text-[11px]"
                      >
                        Details
                      </button>
                      {isAdmin && ['submitted', 'under_review', 'survey_scheduled', 'awaiting_client'].includes(r.status) && (
                        <button
                          onClick={() => handleOpenQuoteBuilder(r)}
                          className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-white rounded font-medium text-[11px]"
                        >
                          Create Quote
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* QUOTATIONS TABLE */
        <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="p-3">Quotation No</th>
                <th className="p-3">Client</th>
                <th className="p-3">Linked Request</th>
                <th className="p-3">Version</th>
                <th className="p-3">Issue Date</th>
                <th className="p-3">Subtotal</th>
                <th className="p-3">Status</th>
                <th className="p-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 text-gray-700">
              {filteredQuotes.length === 0 ? (
                <tr>
                  <td colSpan="8" className="p-8 text-center text-gray-400">
                    No quotations found.
                  </td>
                </tr>
              ) : (
                filteredQuotes.map(q => (
                  <tr key={q.quotation_id} className="hover:bg-gray-50/80 transition">
                    <td className="p-3 font-semibold text-gray-900">{q.quotation_no}</td>
                    <td className="p-3 font-medium">{q.client_name}</td>
                    <td className="p-3 text-gray-500">{q.request_reference || 'Standalone'}</td>
                    <td className="p-3 font-semibold">v{q.current_version}</td>
                    <td className="p-3">{q.issue_date}</td>
                    <td className="p-3 font-bold text-gray-900">₹{parseFloat(q.subtotal || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td className="p-3">{getStatusBadge(q.status)}</td>
                    <td className="p-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        onClick={() => setSelectedQuote(q)}
                        className="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-white rounded font-medium text-[11px]"
                      >
                        View & Decide
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* MODAL 1: NEW SERVICE REQUEST */}
      {showCreateRequestModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-md shadow-2xl max-w-2xl w-full border border-gray-200 overflow-hidden my-8">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="text-sm font-bold flex items-center space-x-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Submit Security Service Request</span>
              </h3>
              <button onClick={() => setShowCreateRequestModal(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleCreateRequest} className="p-6 space-y-4 text-xs">
              {isAdmin && (
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Client Company *</label>
                  <select
                    required
                    value={newRequestForm.client_id}
                    onChange={(e) => setNewRequestForm({ ...newRequestForm, client_id: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  >
                    <option value="">Select client...</option>
                    {clients.map(c => (
                      <option key={c.client_id} value={c.client_id}>{c.company_name || c.legal_name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Service Purpose *</label>
                  <select
                    value={newRequestForm.service_purpose}
                    onChange={(e) => setNewRequestForm({ ...newRequestForm, service_purpose: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  >
                    <option value="office">Corporate Office</option>
                    <option value="factory">Factory / Manufacturing</option>
                    <option value="residential">Residential Complex</option>
                    <option value="event">Event / Exhibition</option>
                    <option value="other">Other Commercial</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Start Date *</label>
                  <input
                    type="date"
                    required
                    value={newRequestForm.start_date}
                    onChange={(e) => setNewRequestForm({ ...newRequestForm, start_date: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Site / Facility Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Apex Tech Park Phase 2"
                    value={newRequestForm.new_site_name}
                    onChange={(e) => setNewRequestForm({ ...newRequestForm, new_site_name: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Site Contact Person *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Facilities Manager"
                    value={newRequestForm.site_contact_name}
                    onChange={(e) => setNewRequestForm({ ...newRequestForm, site_contact_name: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Site Contact Phone *</label>
                <input
                  type="text"
                  required
                  placeholder="+919876543210"
                  value={newRequestForm.site_contact_phone}
                  onChange={(e) => setNewRequestForm({ ...newRequestForm, site_contact_phone: e.target.value })}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>

              <div>
                <label className="block font-semibold text-gray-700 mb-1">Site Address *</label>
                <textarea
                  required
                  rows="2"
                  placeholder="Complete physical location address"
                  value={newRequestForm.new_site_address}
                  onChange={(e) => setNewRequestForm({ ...newRequestForm, new_site_address: e.target.value })}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>

              {/* Manpower Requirement Lines */}
              <div className="border border-gray-200 rounded p-3 bg-gray-50 space-y-2">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-semibold text-gray-800">Manpower Requirements *</span>
                  <button
                    type="button"
                    onClick={() => setNewRequestForm({
                      ...newRequestForm,
                      lines: [
                        ...newRequestForm.lines,
                        { post_type_id: '', guard_count: 1, shift_information: 'Day Shift 8hr', hours_per_day: 8.0, working_days: ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'] }
                      ]
                    })}
                    className="text-xs text-blue-600 hover:underline font-medium"
                  >
                    + Add Post Line
                  </button>
                </div>
                {newRequestForm.lines.map((line, idx) => (
                  <div key={idx} className="flex gap-2 items-center bg-white p-2 border border-gray-200 rounded">
                    <select
                      required
                      value={line.post_type_id}
                      onChange={(e) => {
                        const updated = [...newRequestForm.lines];
                        updated[idx].post_type_id = e.target.value;
                        setNewRequestForm({ ...newRequestForm, lines: updated });
                      }}
                      className="flex-1 border border-gray-300 rounded p-1.5 text-xs"
                    >
                      <option value="">Select Post Type...</option>
                      {postTypes.map(p => (
                        <option key={p.post_type_id} value={p.post_type_id}>
                          {p.name} {p.requires_armed_authorization ? '(Armed)' : ''}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min="1"
                      required
                      placeholder="Qty"
                      value={line.guard_count}
                      onChange={(e) => {
                        const updated = [...newRequestForm.lines];
                        updated[idx].guard_count = parseInt(e.target.value) || 1;
                        setNewRequestForm({ ...newRequestForm, lines: updated });
                      }}
                      className="w-16 border border-gray-300 rounded p-1.5 text-xs text-center"
                    />
                    <span className="text-gray-400 text-xs">guards</span>
                    {newRequestForm.lines.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = newRequestForm.lines.filter((_, i) => i !== idx);
                          setNewRequestForm({ ...newRequestForm, lines: updated });
                        }}
                        className="text-rose-500 hover:text-rose-700 text-xs px-1"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="pt-2 flex justify-end space-x-2 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowCreateRequestModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-slate-900 text-white rounded font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: QUOTATION BUILDER (ADMIN) */}
      {showQuoteBuilder && selectedRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-md shadow-2xl max-w-3xl w-full border border-gray-200 overflow-hidden my-8">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold flex items-center space-x-2">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  <span>Prepare Quotation for {selectedRequest.request_reference}</span>
                </h3>
                <p className="text-[11px] text-gray-400 mt-0.5">Client: {selectedRequest.client_name}</p>
              </div>
              <button onClick={() => setShowQuoteBuilder(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleSaveQuote} className="p-6 space-y-4 text-xs">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Quotation Date</label>
                  <input
                    type="date"
                    required
                    value={quoteForm.quotation_date}
                    onChange={(e) => setQuoteForm({ ...quoteForm, quotation_date: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Validity (Days)</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={quoteForm.validity_days}
                    onChange={(e) => setQuoteForm({ ...quoteForm, validity_days: parseInt(e.target.value) || 15 })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Tax Note</label>
                  <input
                    type="text"
                    value={quoteForm.tax_note}
                    onChange={(e) => setQuoteForm({ ...quoteForm, tax_note: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
              </div>

              {/* Quotation Pricing Lines */}
              <div className="border border-gray-200 rounded p-3 bg-gray-50 space-y-2">
                <div className="font-semibold text-gray-800 mb-1">Guarding Rates & Billing Items</div>
                {quoteForm.lines.map((l, idx) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center bg-white p-2.5 border border-gray-200 rounded">
                    <div className="col-span-4 font-semibold text-gray-800">
                      {postTypes.find(p => p.post_type_id === l.post_type_id)?.name || 'Security Post'}
                    </div>
                    <div className="col-span-2 text-center text-gray-600">
                      {l.headcount} guards
                    </div>
                    <div className="col-span-3">
                      <div className="relative">
                        <span className="absolute left-2 top-1.5 text-gray-400">₹</span>
                        <input
                          type="number"
                          step="0.01"
                          required
                          value={l.unit_rate}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value) || 0;
                            const updated = [...quoteForm.lines];
                            updated[idx].unit_rate = val;
                            updated[idx].line_total = val * l.headcount;
                            setQuoteForm({ ...quoteForm, lines: updated });
                          }}
                          className="w-full pl-6 pr-2 py-1 border border-gray-300 rounded text-xs"
                          placeholder="Rate"
                        />
                      </div>
                    </div>
                    <div className="col-span-3 text-right font-bold text-gray-900">
                      ₹{parseFloat(l.line_total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                  </div>
                ))}
                <div className="flex justify-between items-center pt-2 border-t border-gray-200 font-bold text-gray-900">
                  <span>Calculated Subtotal</span>
                  <span>
                    ₹{quoteForm.lines.reduce((acc, l) => acc + (parseFloat(l.line_total) || 0), 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Payment Terms</label>
                  <input
                    type="text"
                    value={quoteForm.payment_terms}
                    onChange={(e) => setQuoteForm({ ...quoteForm, payment_terms: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Confidential Margin Notes (Internal Only)</label>
                  <input
                    type="text"
                    value={quoteForm.internal_notes}
                    onChange={(e) => setQuoteForm({ ...quoteForm, internal_notes: e.target.value })}
                    placeholder="Hidden from clients and supervisors"
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end space-x-2 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowQuoteBuilder(false)}
                  className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-slate-900 text-white rounded font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : 'Save Draft Quotation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER / MODAL 3: QUOTATION DETAILS & DECISION WORKFLOW */}
      {selectedQuote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-md shadow-2xl max-w-2xl w-full border border-gray-200 overflow-hidden my-8">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold flex items-center space-x-2">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  <span>Quotation {selectedQuote.quotation_no} (Version {selectedQuote.current_version})</span>
                </h3>
                <p className="text-[11px] text-gray-400 mt-0.5">Client: {selectedQuote.client_name}</p>
              </div>
              <button onClick={() => setSelectedQuote(null)} className="text-gray-400 hover:text-white">✕</button>
            </div>

            <div className="p-6 space-y-4 text-xs">
              {/* Header Info */}
              <div className="grid grid-cols-3 gap-3 p-3 bg-gray-50 rounded border border-gray-200">
                <div>
                  <div className="text-gray-400 text-[11px]">Issue Date</div>
                  <div className="font-semibold text-gray-900 mt-0.5">{selectedQuote.issue_date}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-[11px]">Status</div>
                  <div className="mt-0.5">{getStatusBadge(selectedQuote.status)}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-[11px]">Subtotal</div>
                  <div className="font-bold text-gray-900 mt-0.5">
                    ₹{parseFloat(selectedQuote.subtotal || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                </div>
              </div>

              {/* Latest Version Lines */}
              {selectedQuote.versions && selectedQuote.versions.length > 0 && (
                <div className="border border-gray-200 rounded overflow-hidden">
                  <div className="p-2.5 bg-gray-50 border-b border-gray-200 font-semibold text-gray-800">
                    Pricing Breakdown (v{selectedQuote.versions[selectedQuote.versions.length - 1].version_number})
                  </div>
                  <div className="p-3 space-y-2">
                    {(selectedQuote.versions[selectedQuote.versions.length - 1].lines || []).map((l, idx) => (
                      <div key={idx} className="flex justify-between items-center text-xs border-b border-gray-100 pb-1.5 last:border-0 last:pb-0">
                        <div>
                          <span className="font-semibold text-gray-900">{l.post_type_name || 'Guard'}</span>
                          <span className="text-gray-400 ml-2">({l.headcount} guards @ ₹{l.unit_rate} / mo)</span>
                        </div>
                        <div className="font-bold text-gray-900">
                          ₹{parseFloat(l.line_total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </div>
                      </div>
                    ))}
                    <div className="text-[11px] text-gray-500 pt-2 border-t border-gray-100">
                      Note: {selectedQuote.versions[selectedQuote.versions.length - 1].tax_note}
                    </div>
                  </div>
                </div>
              )}

              {/* Client Action Section */}
              {isClient && selectedQuote.status === 'sent' && (
                <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded space-y-3">
                  <div className="font-semibold text-emerald-900">Commercial Decision</div>
                  <p className="text-[11px] text-emerald-800 leading-relaxed">
                    Please review the proposed rates and terms. Acceptance will bind this commercial offer and trigger operational site setup.
                  </p>
                  <label className="flex items-start space-x-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={acceptanceConfirmed}
                      onChange={(e) => setAcceptanceConfirmed(e.target.checked)}
                      className="mt-0.5 rounded border-gray-300 text-slate-900"
                    />
                    <span className="text-[11px] font-semibold text-gray-900">
                      I confirm and accept the guarding charges, headcount, and commercial terms set forth in this quotation.
                    </span>
                  </label>
                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={() => handleAcceptQuote(selectedQuote.versions[selectedQuote.versions.length - 1].quotation_version_id)}
                      disabled={submitting || !acceptanceConfirmed}
                      className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded font-semibold text-xs disabled:opacity-40"
                    >
                      {submitting ? 'Recording Acceptance...' : 'Accept Quotation'}
                    </button>
                    <button
                      onClick={() => setShowCounterModal(true)}
                      className="px-3 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-800 rounded font-medium text-xs"
                    >
                      Propose Changes (Counter)
                    </button>
                  </div>
                </div>
              )}

              {/* Admin Actions */}
              {isAdmin && (
                <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
                  {selectedQuote.status === 'draft' && selectedQuote.versions?.[0] && (
                    <button
                      onClick={() => handleSendQuote(selectedQuote.versions[0].quotation_version_id)}
                      disabled={submitting}
                      className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded font-semibold text-xs"
                    >
                      Send Quotation to Client
                    </button>
                  )}
                  {selectedQuote.status === 'accepted' && (
                    <button
                      onClick={() => handleConvertQuote(selectedQuote.versions[selectedQuote.versions.length - 1].quotation_version_id)}
                      disabled={submitting}
                      className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded font-semibold text-xs flex items-center space-x-1.5"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Convert to Master Data Setup</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: COUNTER PROPOSAL */}
      {showCounterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-2xl max-w-md w-full border border-gray-200 overflow-hidden">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="text-sm font-bold">Propose Commercial Changes</h3>
              <button onClick={() => setShowCounterModal(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleCounterQuote} className="p-6 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Client Feedback / Comment *</label>
                <textarea
                  required
                  rows="3"
                  placeholder="Explain proposed adjustments..."
                  value={counterForm.comment}
                  onChange={(e) => setCounterForm({ ...counterForm, comment: e.target.value })}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Proposed Rate (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="e.g. 25000"
                    value={counterForm.proposed_rate}
                    onChange={(e) => setCounterForm({ ...counterForm, proposed_rate: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Proposed Headcount</label>
                  <input
                    type="number"
                    placeholder="e.g. 3"
                    value={counterForm.proposed_guard_count}
                    onChange={(e) => setCounterForm({ ...counterForm, proposed_guard_count: e.target.value })}
                    className="w-full border border-gray-300 rounded p-2 text-xs"
                  />
                </div>
              </div>
              <div className="pt-2 flex justify-end space-x-2 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowCounterModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-3 py-1.5 bg-slate-900 text-white rounded font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  Submit Counter
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER / MODAL 5: REQUEST DETAILS */}
      {selectedRequest && !showQuoteBuilder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-md shadow-2xl max-w-2xl w-full border border-gray-200 overflow-hidden my-8">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-emerald-400" />
                  <span>Service Request Details: {selectedRequest.request_reference}</span>
                </h3>
                <p className="text-[11px] text-gray-400 mt-0.5">{selectedRequest.client_name}</p>
              </div>
              <button onClick={() => setSelectedRequest(null)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <div className="grid grid-cols-3 gap-3 p-3 bg-gray-50 rounded border border-gray-200">
                <div>
                  <div className="text-gray-400 text-[11px]">Site Name</div>
                  <div className="font-semibold text-gray-900 mt-0.5">{selectedRequest.new_site_name || 'Existing Site'}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-[11px]">Start Date</div>
                  <div className="font-semibold text-gray-900 mt-0.5">{selectedRequest.start_date}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-[11px]">Status</div>
                  <div className="mt-0.5">{getStatusBadge(selectedRequest.status)}</div>
                </div>
              </div>

              <div>
                <div className="font-semibold text-gray-800 mb-1">Location & Contact</div>
                <div className="text-gray-600 bg-gray-50 p-2.5 rounded border border-gray-200">
                  <div>{selectedRequest.new_site_address || 'No address provided'}</div>
                  <div className="text-gray-500 mt-1">
                    Contact: {selectedRequest.site_contact_name} ({selectedRequest.site_contact_phone})
                  </div>
                </div>
              </div>

              <div>
                <div className="font-semibold text-gray-800 mb-1">Manpower Lines Requested</div>
                <div className="border border-gray-200 rounded divide-y divide-gray-100">
                  {(selectedRequest.lines || []).map((l, idx) => (
                    <div key={idx} className="p-2.5 flex justify-between items-center">
                      <div>
                        <span className="font-semibold text-gray-900">{l.post_type_name || 'Guard Post'}</span>
                        {l.armed_required && <span className="ml-2 text-rose-600 font-bold">(Armed)</span>}
                        <div className="text-[11px] text-gray-500">{l.shift_information} • {l.hours_per_day}h/day</div>
                      </div>
                      <div className="font-bold text-gray-800 text-sm">
                        {l.guard_count} guards
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Admin Actions on Request */}
              {isAdmin && (
                <div className="flex justify-between items-center pt-3 border-t border-gray-200">
                  <div className="space-x-2">
                    <button
                      onClick={() => setShowSurveyModal(true)}
                      className="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-50 text-xs font-medium"
                    >
                      Record Site Survey
                    </button>
                    <button
                      onClick={() => setShowClarifyModal(true)}
                      className="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-50 text-xs font-medium"
                    >
                      Request Clarification
                    </button>
                  </div>
                  {['submitted', 'under_review', 'survey_scheduled', 'awaiting_client'].includes(selectedRequest.status) && (
                    <button
                      onClick={() => handleOpenQuoteBuilder(selectedRequest)}
                      className="px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded font-semibold text-xs"
                    >
                      Create Quotation
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 6: SITE SURVEY (ADMIN) */}
      {showSurveyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-2xl max-w-md w-full border border-gray-200 overflow-hidden">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="text-sm font-bold">Record Site Survey Findings</h3>
              <button onClick={() => setShowSurveyModal(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleRecordSurvey} className="p-6 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Survey Date *</label>
                <input
                  type="date"
                  required
                  value={surveyForm.survey_date}
                  onChange={(e) => setSurveyForm({ ...surveyForm, survey_date: e.target.value })}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Visited By (Inspector / Officer) *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Field Officer Rajesh"
                  value={surveyForm.visited_by}
                  onChange={(e) => setSurveyForm({ ...surveyForm, visited_by: e.target.value })}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Survey Findings & Assessment *</label>
                <textarea
                  required
                  rows="3"
                  placeholder="Boundary perimeter, lighting, entry gate points, CCTV coverage..."
                  value={surveyForm.findings}
                  onChange={(e) => setSurveyForm({ ...surveyForm, findings: e.target.value })}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>
              <div className="pt-2 flex justify-end space-x-2 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowSurveyModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-3 py-1.5 bg-slate-900 text-white rounded font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  Save Survey
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 7: CLARIFY */}
      {showClarifyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-2xl max-w-md w-full border border-gray-200 overflow-hidden">
            <div className="p-4 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="text-sm font-bold">Request Clarification from Client</h3>
              <button onClick={() => setShowClarifyModal(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleClarify} className="p-6 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-gray-700 mb-1">Question / Clarification Note *</label>
                <textarea
                  required
                  rows="3"
                  placeholder="Ask the client for clarification regarding post shifts, parking perimeter, etc."
                  value={clarifyMessage}
                  onChange={(e) => setClarifyMessage(e.target.value)}
                  className="w-full border border-gray-300 rounded p-2 text-xs"
                />
              </div>
              <div className="pt-2 flex justify-end space-x-2 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowClarifyModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-3 py-1.5 bg-slate-900 text-white rounded font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  Send Clarification Request
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Users,
  UserCheck,
  UserX,
  RefreshCw,
  Search,
  Filter,
  Plus,
  ArrowRightLeft,
  FileSpreadsheet,
  Send,
  AlertOctagon,
  ChevronLeft,
  ChevronRight,
  Info,
  Check,
  X,
  Lock,
  Unlock,
  AlertCircle
} from 'lucide-react';
import { rosterApi, masterApi, guardApi } from '../api';

export default function DeploymentDashboardScreen({ currentUser }) {
  // Main data states
  const [loading, setLoading] = useState(true);
  const [sites, setSites] = useState([]);
  const [selectedSiteId, setSelectedSiteId] = useState('');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [activeTab, setActiveTab] = useState('board'); // 'board', 'swaps', 'ratifications', 'pool'

  // Dashboard Metrics
  const [metrics, setMetrics] = useState({
    required_count: 0,
    filled_count: 0,
    vacant_count: 0,
    at_risk_count: 0,
    unacknowledged_count: 0,
    coverage_percentage: 0
  });

  // Slots & Assignments data
  const [slots, setSlots] = useState([]);
  const [swaps, setSwaps] = useState([]);
  const [ratifications, setRatifications] = useState([]);
  const [guardsList, setGuardsList] = useState([]);

  // Modals & Action States
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generateData, setGenerateData] = useState({
    site_id: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
  });

  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedSlotForAssign, setSelectedSlotForAssign] = useState(null);
  const [assignGuardId, setAssignGuardId] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [softWarnings, setSoftWarnings] = useState([]);
  const [assignError, setAssignError] = useState('');

  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [selectedAssignmentForReplace, setSelectedAssignmentForReplace] = useState(null);
  const [replacementGuardId, setReplacementGuardId] = useState('');
  const [replacementReason, setReplacementReason] = useState('NO_SHOW');

  const [showEmergencyModal, setShowEmergencyModal] = useState(false);
  const [emergencyData, setEmergencyData] = useState({
    site_id: '',
    shift_id: '',
    post_type_id: '',
    employee_id: '',
    deployment_date: new Date().toISOString().split('T')[0],
    reason: ''
  });

  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishDates, setPublishDates] = useState({
    site_id: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
  });

  const [message, setMessage] = useState({ type: '', text: '' });
  const [actionLoading, setActionLoading] = useState(false);

  // Initial Data Load
  useEffect(() => {
    fetchInitialData();
  }, []);

  // When Site or Date changes, fetch slots & metrics
  useEffect(() => {
    if (selectedSiteId) {
      fetchRosterData();
    }
  }, [selectedSiteId, selectedDate]);

  const fetchInitialData = async () => {
    setLoading(true);
    try {
      const [sitesRes, guardsRes] = await Promise.all([
        masterApi.getSites(),
        guardApi.getGuards({ lifecycle_status: 'active' })
      ]);
      const siteList = sitesRes.data?.results || sitesRes.data || [];
      setSites(siteList);
      if (siteList.length > 0) {
        setSelectedSiteId(siteList[0].site_id);
        setGenerateData(prev => ({ ...prev, site_id: siteList[0].site_id }));
        setPublishDates(prev => ({ ...prev, site_id: siteList[0].site_id }));
      }
      setGuardsList(guardsRes.data?.results || guardsRes.data || []);
    } catch (err) {
      console.error('Failed to load initial data', err);
      setMessage({ type: 'error', text: 'Failed to load master sites and guards.' });
    } finally {
      setLoading(false);
    }
  };

  const fetchRosterData = async () => {
    try {
      const [metricsRes, slotsRes, swapsRes, ratRes] = await Promise.all([
        rosterApi.getCoverageDashboard({ site_id: selectedSiteId, date: selectedDate }),
        rosterApi.getSlots({ site_id: selectedSiteId, date: selectedDate }),
        rosterApi.getSwaps({ site_id: selectedSiteId }),
        rosterApi.getRatifications()
      ]);

      if (metricsRes.data) {
        setMetrics(metricsRes.data);
      }
      setSlots(slotsRes.data?.results || slotsRes.data || []);
      setSwaps(swapsRes.data?.results || swapsRes.data || []);
      setRatifications(ratRes.data?.results || ratRes.data || []);
    } catch (err) {
      console.error('Error fetching roster data', err);
    }
  };

  const showNotification = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 5000);
  };

  // Generate Slots
  const handleGenerateSlots = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const res = await rosterApi.generateSlots(generateData);
      showNotification('success', `Generated ${res.data.slots_generated} slots successfully.`);
      setShowGenerateModal(false);
      fetchRosterData();
    } catch (err) {
      showNotification('error', err.response?.data?.detail || err.message || 'Failed to generate slots.');
    } finally {
      setActionLoading(false);
    }
  };

  // Validate Guard on Selection
  const handleGuardSelectionForAssign = async (guardId) => {
    setAssignGuardId(guardId);
    setSoftWarnings([]);
    setAssignError('');
    if (!guardId || !selectedSlotForAssign) return;

    try {
      const valRes = await rosterApi.validateAssignment({
        slot_id: selectedSlotForAssign.slot_id,
        employee_id: guardId
      });
      if (valRes.data.hard_blocked) {
        setAssignError(valRes.data.errors.join(' '));
      } else if (valRes.data.warnings && valRes.data.warnings.length > 0) {
        setSoftWarnings(valRes.data.warnings);
      }
    } catch (err) {
      console.error('Validation error', err);
    }
  };

  // Assign Guard
  const handleAssignGuard = async (e) => {
    e.preventDefault();
    if (!assignGuardId) return;
    if (softWarnings.length > 0 && !overrideReason.trim()) {
      setAssignError('Please provide an override reason for the fatigue warning.');
      return;
    }

    setActionLoading(true);
    try {
      await rosterApi.assignSlot({
        slot_id: selectedSlotForAssign.slot_id,
        employee_id: assignGuardId,
        override_reason: overrideReason.trim() || undefined
      });
      showNotification('success', 'Guard assigned to duty slot successfully.');
      setShowAssignModal(false);
      setSelectedSlotForAssign(null);
      setAssignGuardId('');
      setOverrideReason('');
      setSoftWarnings([]);
      fetchRosterData();
    } catch (err) {
      const errDetail = err.response?.data?.hard_conflicts?.join(' ') ||
        err.response?.data?.detail || err.message || 'Failed to assign guard.';
      setAssignError(errDetail);
    } finally {
      setActionLoading(false);
    }
  };

  // Create Replacement
  const handleCreateReplacement = async (e) => {
    e.preventDefault();
    if (!replacementGuardId || !selectedAssignmentForReplace) return;

    setActionLoading(true);
    try {
      await rosterApi.createReplacement({
        original_assignment_id: selectedAssignmentForReplace.assignment_id,
        replacement_employee_id: replacementGuardId,
        replacement_reason: replacementReason
      });
      showNotification('success', 'Replacement guard deployed successfully.');
      setShowReplaceModal(false);
      setSelectedAssignmentForReplace(null);
      setReplacementGuardId('');
      fetchRosterData();
    } catch (err) {
      showNotification('error', err.response?.data?.detail || err.message || 'Failed to deploy replacement.');
    } finally {
      setActionLoading(false);
    }
  };

  // Decide Swap Request
  const handleDecideSwap = async (swapId, decision, rejectionReason = '') => {
    setActionLoading(true);
    try {
      await rosterApi.decideSwap(swapId, {
        decision,
        rejection_reason: rejectionReason || undefined
      });
      showNotification('success', `Shift swap request ${decision}d.`);
      fetchRosterData();
    } catch (err) {
      showNotification('error', err.response?.data?.detail || err.message || 'Action failed.');
    } finally {
      setActionLoading(false);
    }
  };

  // Ratify Emergency Deployment
  const handleRatifyEmergency = async (ratificationId, decision, decisionNotes = '') => {
    setActionLoading(true);
    try {
      await rosterApi.ratifyEmergency(ratificationId, {
        decision,
        decision_notes: decisionNotes || undefined
      });
      showNotification('success', `Emergency deployment ${decision}d successfully.`);
      fetchRosterData();
    } catch (err) {
      showNotification('error', err.response?.data?.detail || err.message || 'Ratification failed.');
    } finally {
      setActionLoading(false);
    }
  };

  // Publish Roster
  const handlePublishRoster = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const res = await rosterApi.publishRoster(publishDates);
      showNotification('success', `Roster published. ${res.data.assignments_published} guard assignments notified.`);
      setShowPublishModal(false);
      fetchRosterData();
    } catch (err) {
      showNotification('error', err.response?.data?.detail || err.message || 'Failed to publish roster.');
    } finally {
      setActionLoading(false);
    }
  };

  // CSV Export
  const handleExportCSV = async () => {
    try {
      const response = await rosterApi.exportCoverage({
        site_id: selectedSiteId,
        start_date: selectedDate,
        end_date: selectedDate
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `roster_coverage_${selectedDate}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      showNotification('error', 'Failed to export CSV report.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Deployment & Roster</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage site guard allocations, daily shift rosters, replacements, and fatigue compliance
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => setShowGenerateModal(true)}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-gray-300 rounded-md hover:bg-slate-50 transition"
          >
            <Calendar className="w-4 h-4 text-slate-500" />
            Generate Slots
          </button>
          <button
            onClick={() => setShowPublishModal(true)}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-white bg-slate-900 rounded-md hover:bg-slate-800 transition"
          >
            <Send className="w-4 h-4" />
            Publish Roster
          </button>
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-gray-300 rounded-md hover:bg-slate-50 transition"
          >
            <FileSpreadsheet className="w-4 h-4 text-slate-500" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Alert Notification */}
      {message.text && (
        <div className={`p-4 rounded-md border flex items-center justify-between ${
          message.type === 'error'
            ? 'bg-red-50 border-red-200 text-red-800'
            : 'bg-emerald-50 border-emerald-200 text-emerald-800'
        }`}>
          <div className="flex items-center gap-3">
            {message.type === 'error' ? (
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            )}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
          <button onClick={() => setMessage({ type: '', text: '' })} className="text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Top Filter Bar */}
      <div className="bg-white p-4 rounded-md border border-gray-200 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-slate-500" />
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Site:</span>
            <select
              value={selectedSiteId}
              onChange={(e) => setSelectedSiteId(e.target.value)}
              className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-slate-900"
            >
              {sites.map(s => (
                <option key={s.site_id} value={s.site_id}>
                  {s.site_name} ({s.site_code})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-500" />
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Date:</span>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-slate-900"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const d = new Date(selectedDate);
              d.setDate(d.getDate() - 1);
              setSelectedDate(d.toISOString().split('T')[0]);
            }}
            className="p-1.5 border border-gray-300 rounded-md hover:bg-slate-50"
            title="Previous Day"
          >
            <ChevronLeft className="w-4 h-4 text-slate-600" />
          </button>
          <button
            onClick={() => setSelectedDate(new Date().toISOString().split('T')[0])}
            className="px-2.5 py-1 text-xs font-medium text-slate-700 border border-gray-300 rounded-md hover:bg-slate-50"
          >
            Today
          </button>
          <button
            onClick={() => {
              const d = new Date(selectedDate);
              d.setDate(d.getDate() + 1);
              setSelectedDate(d.toISOString().split('T')[0]);
            }}
            className="p-1.5 border border-gray-300 rounded-md hover:bg-slate-50"
            title="Next Day"
          >
            <ChevronRight className="w-4 h-4 text-slate-600" />
          </button>
          <button
            onClick={fetchRosterData}
            className="p-1.5 border border-gray-300 rounded-md hover:bg-slate-50 text-slate-600 ml-2"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-white p-4 rounded-md border border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Required Posts</div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{metrics.required_count}</div>
          <div className="mt-1 text-xs text-gray-500">From manpower rules</div>
        </div>

        <div className="bg-white p-4 rounded-md border border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Filled Slots</div>
          <div className="mt-2 text-2xl font-bold text-emerald-600">{metrics.filled_count}</div>
          <div className="mt-1 text-xs text-gray-500">Active assignments</div>
        </div>

        <div className="bg-white p-4 rounded-md border border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Vacant Slots</div>
          <div className="mt-2 text-2xl font-bold text-amber-600">{metrics.vacant_count}</div>
          <div className="mt-1 text-xs text-gray-500">Unassigned positions</div>
        </div>

        <div className="bg-white p-4 rounded-md border border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">At-Risk Posts</div>
          <div className="mt-2 text-2xl font-bold text-rose-600">{metrics.at_risk_count}</div>
          <div className="mt-1 text-xs text-gray-500">No-shows / Cancellations</div>
        </div>

        <div className="bg-white p-4 rounded-md border border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Coverage Rate</div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{metrics.coverage_percentage}%</div>
          <div className="mt-1 text-xs text-gray-500">Target: 100%</div>
        </div>

        <div className="bg-white p-4 rounded-md border border-gray-200">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">Unacknowledged</div>
          <div className="mt-2 text-2xl font-bold text-blue-600">{metrics.unacknowledged_count}</div>
          <div className="mt-1 text-xs text-gray-500">Pending guard view</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('board')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'board'
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Users className="w-4 h-4" />
            Duty Roster Board ({slots.length})
          </button>

          <button
            onClick={() => setActiveTab('swaps')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'swaps'
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <ArrowRightLeft className="w-4 h-4" />
            Shift Swaps ({swaps.filter(s => s.status === 'requested').length})
          </button>

          <button
            onClick={() => setActiveTab('ratifications')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'ratifications'
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <AlertOctagon className="w-4 h-4" />
            Emergency Ratifications ({ratifications.filter(r => r.status === 'pending').length})
          </button>
        </nav>
      </div>

      {/* Tab 1: Duty Roster Board */}
      {activeTab === 'board' && (
        <div className="bg-white rounded-md border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-slate-50/50">
            <h2 className="text-base font-semibold text-gray-900">
              Shift Slots for {selectedDate}
            </h2>
            <span className="text-xs text-gray-500">
              Showing all scheduled post positions
            </span>
          </div>

          {slots.length === 0 ? (
            <div className="p-12 text-center">
              <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <h3 className="text-base font-medium text-gray-900">No duty slots generated for this date</h3>
              <p className="text-sm text-gray-500 mt-1 max-w-md mx-auto">
                Generate post slots for this site based on its active manpower requirements.
              </p>
              <button
                onClick={() => setShowGenerateModal(true)}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-slate-900 rounded-md hover:bg-slate-800"
              >
                <Plus className="w-4 h-4" />
                Generate Duty Slots
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  <tr>
                    <th className="px-6 py-3 text-left">Shift / Post</th>
                    <th className="px-6 py-3 text-left">Slot #</th>
                    <th className="px-6 py-3 text-left">Assigned Guard</th>
                    <th className="px-6 py-3 text-left">Post Type</th>
                    <th className="px-6 py-3 text-left">Status</th>
                    <th className="px-6 py-3 text-left">Acknowledgement</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {slots.map((slot) => {
                    const assignment = slot.assignment;
                    return (
                      <tr key={slot.slot_id} className="hover:bg-slate-50/80 transition">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-semibold text-gray-900">{slot.shift_name}</div>
                          <div className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                            <Clock className="w-3.5 h-3.5" />
                            {slot.start_time} - {slot.end_time}
                          </div>
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap text-gray-600 font-mono">
                          Slot #{slot.slot_sequence}
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap">
                          {assignment ? (
                            <div>
                              <div className="font-medium text-gray-900 flex items-center gap-1.5">
                                {assignment.employee_name}
                                {assignment.is_emergency && (
                                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-700">
                                    EMERGENCY
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-gray-500 font-mono mt-0.5">
                                {assignment.employee_code}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs italic text-gray-400">Unassigned</span>
                          )}
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded ${
                            slot.requires_armed_authorization
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : 'bg-slate-100 text-slate-700'
                          }`}>
                            <Shield className="w-3 h-3" />
                            {slot.post_type_name}
                          </span>
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded ${
                            slot.slot_status === 'filled'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : slot.slot_status === 'at_risk'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                            {slot.slot_status === 'filled' ? 'Filled' :
                             slot.slot_status === 'at_risk' ? 'At-Risk' : 'Vacant'}
                          </span>
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap">
                          {assignment ? (
                            assignment.status === 'acknowledged' ? (
                              <span className="inline-flex items-center gap-1 text-xs text-emerald-600 font-medium">
                                <CheckCircle2 className="w-4 h-4" />
                                Acknowledged
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs text-amber-600 font-medium">
                                <Clock className="w-4 h-4" />
                                Pending Guard
                              </span>
                            )
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>

                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          {assignment ? (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => {
                                  setSelectedAssignmentForReplace(assignment);
                                  setShowReplaceModal(true);
                                }}
                                className="px-2.5 py-1 text-xs font-medium text-slate-700 border border-gray-300 rounded hover:bg-slate-50 transition"
                              >
                                Replace Guard
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => {
                                setSelectedSlotForAssign(slot);
                                setShowAssignModal(true);
                              }}
                              className="px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 rounded hover:bg-slate-800 transition"
                            >
                              Assign Guard
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Shift Swaps */}
      {activeTab === 'swaps' && (
        <div className="bg-white rounded-md border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-slate-50/50">
            <h2 className="text-base font-semibold text-gray-900">Shift Swap Requests</h2>
            <span className="text-xs text-gray-500">Atomic shift exchanges between guards</span>
          </div>

          {swaps.length === 0 ? (
            <div className="p-12 text-center text-gray-500 text-sm">
              No shift swap requests logged for this site.
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {swaps.map((s) => (
                <div key={s.swap_id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900">{s.requestor_guard_name}</span>
                      <ArrowRightLeft className="w-4 h-4 text-slate-400" />
                      <span className="text-sm font-semibold text-gray-900">{s.target_guard_name}</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      Reason: {s.reason || 'Personal mutual agreement'}
                    </div>
                    <div className="mt-1 text-xs text-gray-400">
                      Requested at: {new Date(s.created_at).toLocaleString()}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 text-xs font-semibold rounded ${
                      s.status === 'approved' ? 'bg-emerald-50 text-emerald-700' :
                      s.status === 'rejected' ? 'bg-red-50 text-red-700' :
                      'bg-amber-50 text-amber-700'
                    }`}>
                      {s.status.toUpperCase()}
                    </span>

                    {s.status === 'requested' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleDecideSwap(s.swap_id, 'approve')}
                          disabled={actionLoading}
                          className="px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 rounded hover:bg-emerald-700 transition"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleDecideSwap(s.swap_id, 'reject', 'Supervisor rejected')}
                          disabled={actionLoading}
                          className="px-3 py-1.5 text-xs font-medium text-red-700 border border-red-200 rounded hover:bg-red-50 transition"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Emergency Ratifications */}
      {activeTab === 'ratifications' && (
        <div className="bg-white rounded-md border border-gray-200 overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-slate-50/50">
            <h2 className="text-base font-semibold text-gray-900">Emergency Deployments (24h Ratification)</h2>
            <span className="text-xs text-gray-500">Supervisor field deployments requiring Admin ratification</span>
          </div>

          {ratifications.length === 0 ? (
            <div className="p-12 text-center text-gray-500 text-sm">
              No emergency ratifications pending.
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {ratifications.map((r) => (
                <div key={r.ratification_id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900">{r.employee_name}</span>
                      <span className="text-xs text-gray-500">at {r.site_name}</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-600">
                      Emergency Justification: {r.reason}
                    </div>
                    <div className="mt-1 text-xs font-mono text-rose-600">
                      Deadline: {new Date(r.ratification_deadline).toLocaleString()}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 text-xs font-semibold rounded ${
                      r.status === 'ratified' ? 'bg-emerald-50 text-emerald-700' :
                      r.status === 'rejected' ? 'bg-red-50 text-red-700' :
                      'bg-rose-50 text-rose-700 font-bold'
                    }`}>
                      {r.status.toUpperCase()}
                    </span>

                    {r.status === 'pending' && currentUser?.role === 'ADMIN' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleRatifyEmergency(r.ratification_id, 'ratified')}
                          disabled={actionLoading}
                          className="px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 rounded hover:bg-slate-800 transition"
                        >
                          Ratify Deployment
                        </button>
                        <button
                          onClick={() => handleRatifyEmergency(r.ratification_id, 'rejected', 'Unauthorized post')}
                          disabled={actionLoading}
                          className="px-3 py-1.5 text-xs font-medium text-red-700 border border-red-200 rounded hover:bg-red-50 transition"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modal: Generate Duty Slots */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md max-w-md w-full p-6 shadow-xl border border-gray-200">
            <div className="flex items-center justify-between border-b pb-3 mb-4">
              <h3 className="text-base font-bold text-gray-900">Generate Post Slots</h3>
              <button onClick={() => setShowGenerateModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleGenerateSlots} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Site
                </label>
                <select
                  value={generateData.site_id}
                  onChange={(e) => setGenerateData({ ...generateData, site_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                >
                  {sites.map(s => (
                    <option key={s.site_id} value={s.site_id}>{s.site_name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={generateData.start_date}
                  onChange={(e) => setGenerateData({ ...generateData, start_date: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={generateData.end_date}
                  onChange={(e) => setGenerateData({ ...generateData, end_date: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowGenerateModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-md hover:bg-slate-800 disabled:opacity-50"
                >
                  {actionLoading ? 'Generating...' : 'Generate Slots'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Assign Guard */}
      {showAssignModal && selectedSlotForAssign && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md max-w-lg w-full p-6 shadow-xl border border-gray-200">
            <div className="flex items-center justify-between border-b pb-3 mb-4">
              <div>
                <h3 className="text-base font-bold text-gray-900">Assign Guard to Slot</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {selectedSlotForAssign.shift_name} ({selectedSlotForAssign.start_time} - {selectedSlotForAssign.end_time})
                </p>
              </div>
              <button onClick={() => setShowAssignModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            {assignError && (
              <div className="mb-4 p-3 rounded-md bg-red-50 border border-red-200 text-xs text-red-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{assignError}</span>
              </div>
            )}

            {softWarnings.length > 0 && (
              <div className="mb-4 p-3 rounded-md bg-amber-50 border border-amber-200 text-xs text-amber-800 space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Fatigue Warning Triggered:
                </div>
                {softWarnings.map((w, idx) => (
                  <div key={idx}>• {w}</div>
                ))}
              </div>
            )}

            <form onSubmit={handleAssignGuard} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Select Active Guard
                </label>
                <select
                  value={assignGuardId}
                  onChange={(e) => handleGuardSelectionForAssign(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                >
                  <option value="">-- Choose Guard --</option>
                  {guardsList.map(g => (
                    <option key={g.employee_id} value={g.employee_id}>
                      {g.full_name} ({g.employee_code})
                    </option>
                  ))}
                </select>
              </div>

              {softWarnings.length > 0 && (
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                    Override Justification (Required for Fatigue Warning)
                  </label>
                  <textarea
                    rows={2}
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder="Enter explicit operational necessity reason..."
                    className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                    required
                  />
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowAssignModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || !!assignError}
                  className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-md hover:bg-slate-800 disabled:opacity-50"
                >
                  {actionLoading ? 'Assigning...' : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Replace Guard */}
      {showReplaceModal && selectedAssignmentForReplace && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md max-w-md w-full p-6 shadow-xl border border-gray-200">
            <div className="flex items-center justify-between border-b pb-3 mb-4">
              <div>
                <h3 className="text-base font-bold text-gray-900">Deploy Linked Replacement</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Replacing: {selectedAssignmentForReplace.employee_name}
                </p>
              </div>
              <button onClick={() => setShowReplaceModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateReplacement} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Replacement Reason
                </label>
                <select
                  value={replacementReason}
                  onChange={(e) => setReplacementReason(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                >
                  <option value="NO_SHOW">Guard No-Show</option>
                  <option value="MEDICAL_EMERGENCY">Medical Emergency</option>
                  <option value="CLIENT_REQUEST">Client Removal Request</option>
                  <option value="OPERATIONAL_NEED">Operational Necessity</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Select Reliever Guard
                </label>
                <select
                  value={replacementGuardId}
                  onChange={(e) => setReplacementGuardId(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                >
                  <option value="">-- Choose Reliever --</option>
                  {guardsList
                    .filter(g => g.employee_id !== selectedAssignmentForReplace.employee_id)
                    .map(g => (
                      <option key={g.employee_id} value={g.employee_id}>
                        {g.full_name} ({g.employee_code})
                      </option>
                    ))}
                </select>
              </div>

              <div className="p-3 bg-slate-50 border border-gray-200 rounded text-xs text-gray-500">
                Original assignment will be marked as replaced. The new reliever assignment maintains permanent trace linkage.
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowReplaceModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-md hover:bg-slate-800 disabled:opacity-50"
                >
                  {actionLoading ? 'Deploying...' : 'Deploy Replacement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Publish Roster */}
      {showPublishModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md max-w-md w-full p-6 shadow-xl border border-gray-200">
            <div className="flex items-center justify-between border-b pb-3 mb-4">
              <h3 className="text-base font-bold text-gray-900">Publish Roster</h3>
              <button onClick={() => setShowPublishModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handlePublishRoster} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Site
                </label>
                <select
                  value={publishDates.site_id}
                  onChange={(e) => setPublishDates({ ...publishDates, site_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                >
                  {sites.map(s => (
                    <option key={s.site_id} value={s.site_id}>{s.site_name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  From Date
                </label>
                <input
                  type="date"
                  value={publishDates.start_date}
                  onChange={(e) => setPublishDates({ ...publishDates, start_date: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  To Date
                </label>
                <input
                  type="date"
                  value={publishDates.end_date}
                  onChange={(e) => setPublishDates({ ...publishDates, end_date: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                  required
                />
              </div>

              <div className="p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
                Publishing sends instant duty notifications to all assigned guards. Duties become visible on their mobile app for acknowledgment.
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowPublishModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 text-sm font-semibold text-white bg-slate-900 rounded-md hover:bg-slate-800 disabled:opacity-50"
                >
                  {actionLoading ? 'Publishing...' : 'Publish & Notify'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


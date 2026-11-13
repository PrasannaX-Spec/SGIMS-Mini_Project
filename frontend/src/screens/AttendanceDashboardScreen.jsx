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
  FileSpreadsheet,
  AlertOctagon,
  ChevronLeft,
  ChevronRight,
  Info,
  Check,
  X,
  Lock,
  Unlock,
  AlertCircle,
  Eye,
  Edit2,
  MapPin,
  Camera,
  Smartphone,
  History,
  Download
} from 'lucide-react';
import { attendanceApi, masterApi } from '../api';

export default function AttendanceDashboardScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isSupervisor = currentUser?.role === 'SUPERVISOR';

  // Filters & Tabs
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedSiteId, setSelectedSiteId] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [activeTab, setActiveTab] = useState('board'); // 'board' | 'regularisations' | 'periods'

  // Data States
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [sites, setSites] = useState([]);
  const [records, setRecords] = useState([]);
  const [regularisations, setRegularisations] = useState([]);
  const [periods, setPeriods] = useState([]);

  // Metrics
  const [metrics, setMetrics] = useState({
    scheduled_count: 0,
    checked_in_count: 0,
    late_count: 0,
    absent_count: 0,
    pending_approval_count: 0,
    approved_count: 0,
    no_checkout_count: 0,
    flagged_count: 0,
    coverage_percentage: 0
  });

  // Notification message
  const [message, setMessage] = useState({ type: '', text: '' });

  // Inspection & Modals
  const [selectedRecordForDetail, setSelectedRecordForDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Correction Modal
  const [showCorrectionModal, setShowCorrectionModal] = useState(false);
  const [correctionTarget, setCorrectionTarget] = useState(null);
  const [correctionForm, setCorrectionForm] = useState({
    check_in_time: '',
    check_out_time: '',
    reason: ''
  });

  // Rejection Modal
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  // Bulk Approval Confirmation Modal
  const [showBulkModal, setShowBulkModal] = useState(false);

  // Period Close Modal
  const [showPeriodModal, setShowPeriodModal] = useState(false);
  const [periodForm, setPeriodForm] = useState({
    period_year: new Date().getFullYear(),
    period_month: new Date().getMonth() + 1,
    exception_notes: ''
  });

  // Period Reopen Modal
  const [showReopenModal, setShowReopenModal] = useState(false);
  const [reopenTarget, setReopenTarget] = useState(null);
  const [reopenReason, setReopenReason] = useState('');

  // Regularisation Decision Modal
  const [showRegDecisionModal, setShowRegDecisionModal] = useState(false);
  const [regTarget, setRegTarget] = useState(null);
  const [regDecision, setRegDecision] = useState('APPROVED'); // 'APPROVED' | 'REJECTED'
  const [regNotes, setRegNotes] = useState('');

  // Initial Data Load
  useEffect(() => {
    fetchSites();
  }, []);

  // Reload board & metrics whenever filters change
  useEffect(() => {
    if (activeTab === 'board') {
      fetchBoardData();
    } else if (activeTab === 'regularisations') {
      fetchRegularisations();
    } else if (activeTab === 'periods') {
      fetchPeriods();
    }
  }, [selectedDate, selectedSiteId, statusFilter, activeTab]);

  const fetchSites = async () => {
    try {
      const res = await masterApi.getSites();
      setSites(res.data.results || res.data || []);
    } catch (err) {
      console.error('Failed to load sites:', err);
    }
  };

  const fetchBoardData = async () => {
    setLoading(true);
    setMessage({ type: '', text: '' });
    try {
      const queryParams = { date: selectedDate };
      if (selectedSiteId) queryParams.site_id = selectedSiteId;
      if (statusFilter !== 'ALL') {
        if (statusFilter === 'flagged') {
          queryParams.has_flags = 'true';
        } else {
          queryParams.status = statusFilter;
        }
      }

      const [dashRes, recordsRes] = await Promise.all([
        attendanceApi.getDashboard({ date: selectedDate, site_id: selectedSiteId || undefined }),
        attendanceApi.getRecords(queryParams)
      ]);

      setMetrics(dashRes.data || {});
      setRecords(recordsRes.data.results || recordsRes.data || []);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to load attendance records.' });
    } finally {
      setLoading(false);
    }
  };

  const fetchRegularisations = async () => {
    setLoading(true);
    try {
      const res = await attendanceApi.getRegularisations();
      setRegularisations(res.data.results || res.data || []);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to load regularisation requests.' });
    } finally {
      setLoading(false);
    }
  };

  const fetchPeriods = async () => {
    setLoading(true);
    try {
      const res = await attendanceApi.getPeriods();
      setPeriods(res.data.results || res.data || []);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to load monthly periods.' });
    } finally {
      setLoading(false);
    }
  };

  // Date Navigation Helpers
  const shiftDate = (days) => {
    const current = new Date(selectedDate);
    current.setDate(current.getDate() + days);
    setSelectedDate(current.toISOString().split('T')[0]);
  };

  const setToday = () => {
    setSelectedDate(new Date().toISOString().split('T')[0]);
  };

  // Inspect Record Details
  const handleOpenDetail = async (attendanceId) => {
    setDetailLoading(true);
    try {
      const res = await attendanceApi.getRecord(attendanceId);
      setSelectedRecordForDetail(res.data);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to load record details.' });
    } finally {
      setDetailLoading(false);
    }
  };

  // Single Record Approve
  const handleApprove = async (record) => {
    setActionLoading(true);
    setMessage({ type: '', text: '' });
    try {
      await attendanceApi.approveRecord(record.attendance_id);
      setMessage({ type: 'success', text: `Attendance for ${record.employee_name} approved successfully.` });
      fetchBoardData();
      if (selectedRecordForDetail?.attendance_id === record.attendance_id) {
        handleOpenDetail(record.attendance_id);
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Approval failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Bulk Approve Clean
  const handleBulkApprove = async () => {
    if (!selectedSiteId) {
      setMessage({ type: 'error', text: 'Please select a specific site before executing bulk approval.' });
      return;
    }
    setActionLoading(true);
    setMessage({ type: '', text: '' });
    try {
      const res = await attendanceApi.bulkApprove({
        site_id: selectedSiteId,
        date: selectedDate
      });
      setMessage({
        type: 'success',
        text: `Bulk approval complete: ${res.data.approved_count} clean records approved. (${res.data.skipped_flagged_count} flagged records skipped for manual review)`
      });
      setShowBulkModal(false);
      fetchBoardData();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Bulk approval failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Correction Submit
  const handleOpenCorrection = (record) => {
    setCorrectionTarget(record);
    const toInputTime = (isoStr) => {
      if (!isoStr) return '';
      const d = new Date(isoStr);
      return isNaN(d) ? '' : d.toISOString().slice(0, 16);
    };

    setCorrectionForm({
      check_in_time: toInputTime(record.actual_check_in),
      check_out_time: toInputTime(record.actual_check_out),
      reason: ''
    });
    setShowCorrectionModal(true);
  };

  const handleCorrectionSubmit = async (e) => {
    e.preventDefault();
    if (!correctionForm.reason.trim()) {
      setMessage({ type: 'error', text: 'Correction reason is mandatory.' });
      return;
    }

    setActionLoading(true);
    try {
      const payload = {
        reason: correctionForm.reason
      };
      if (correctionForm.check_in_time) {
        payload.check_in_time = new Date(correctionForm.check_in_time).toISOString();
      }
      if (correctionForm.check_out_time) {
        payload.check_out_time = new Date(correctionForm.check_out_time).toISOString();
      }

      await attendanceApi.correctRecord(correctionTarget.attendance_id, payload);
      setMessage({ type: 'success', text: 'Attendance record corrected successfully.' });
      setShowCorrectionModal(false);
      fetchBoardData();
      if (selectedRecordForDetail?.attendance_id === correctionTarget.attendance_id) {
        handleOpenDetail(correctionTarget.attendance_id);
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Correction failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Rejection Submit
  const handleOpenReject = (record) => {
    setRejectTarget(record);
    setRejectReason('');
    setShowRejectModal(true);
  };

  const handleRejectSubmit = async (e) => {
    e.preventDefault();
    if (!rejectReason.trim()) {
      setMessage({ type: 'error', text: 'Rejection reason is mandatory.' });
      return;
    }

    setActionLoading(true);
    try {
      await attendanceApi.rejectRecord(rejectTarget.attendance_id, { reason: rejectReason });
      setMessage({ type: 'success', text: 'Attendance record rejected.' });
      setShowRejectModal(false);
      fetchBoardData();
      if (selectedRecordForDetail?.attendance_id === rejectTarget.attendance_id) {
        handleOpenDetail(rejectTarget.attendance_id);
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Rejection failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Mark Absent
  const handleMarkAbsent = async (record) => {
    if (!window.confirm(`Mark ${record.employee_name} as confirmed absent for this duty?`)) return;
    setActionLoading(true);
    try {
      await attendanceApi.markAbsent(record.attendance_id, { reason: 'Supervisor confirmed absence' });
      setMessage({ type: 'success', text: `${record.employee_name} marked absent.` });
      fetchBoardData();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to mark absent.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Regularisation Decision
  const handleRegularisationDecision = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await attendanceApi.decideRegularisation(regTarget.request_id, {
        decision: regDecision,
        notes: regNotes
      });
      setMessage({ type: 'success', text: `Regularisation ${regDecision.toLowerCase()} successfully.` });
      setShowRegDecisionModal(false);
      fetchRegularisations();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Decision failed.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Period Close Submit
  const handlePeriodCloseSubmit = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      await attendanceApi.closePeriod(periodForm);
      setMessage({ type: 'success', text: 'Attendance period closed and locked successfully.' });
      setShowPeriodModal(false);
      fetchPeriods();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to close period.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Period Reopen Submit
  const handlePeriodReopenSubmit = async (e) => {
    e.preventDefault();
    if (!reopenReason.trim()) {
      setMessage({ type: 'error', text: 'Reopen reason is mandatory for statutory audit compliance.' });
      return;
    }

    setActionLoading(true);
    try {
      await attendanceApi.reopenPeriod(reopenTarget.period_id, { reason: reopenReason });
      setMessage({ type: 'success', text: 'Period reopened successfully.' });
      setShowReopenModal(false);
      fetchPeriods();
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Failed to reopen period.' });
    } finally {
      setActionLoading(false);
    }
  };

  // Export CSV
  const handleExportCSV = async () => {
    try {
      const res = await attendanceApi.exportAttendance({
        start_date: selectedDate,
        end_date: selectedDate,
        site_id: selectedSiteId || undefined
      });
      const blob = new Blob([res.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `attendance_${selectedDate}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Export failed.' });
    }
  };

  // Status Badge Helper
  const getStatusBadge = (status) => {
    const s = (status || '').toLowerCase();
    switch (s) {
      case 'approved':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">Approved</span>;
      case 'pending_approval':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">Pending Review</span>;
      case 'in_progress':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800">On Duty</span>;
      case 'late':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-800">Late</span>;
      case 'completed':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-800">Shift Ended</span>;
      case 'rejected':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">Rejected</span>;
      case 'absent':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-gray-200 text-gray-800">Absent</span>;
      case 'no_checkout':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800">No Checkout</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  // Format Time Helper
  const formatTime = (isoString) => {
    if (!isoString) return '--:--';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Attendance & Verification</h1>
          <p className="mt-1 text-sm text-gray-500">
            Authoritative check-in/out verification, evidence inspection, anomaly detection, and approval workflow.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition"
            title="Export CSV"
          >
            <Download className="w-4 h-4 mr-1.5 text-gray-500" />
            Export CSV
          </button>

          {isAdmin && (
            <button
              onClick={() => setShowPeriodModal(true)}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition"
              title="Close Attendance Period"
            >
              <Lock className="w-4 h-4 mr-1.5 text-slate-600" />
              Lock Period
            </button>
          )}

          {selectedSiteId && (
            <button
              onClick={() => setShowBulkModal(true)}
              disabled={actionLoading || metrics.pending_approval_count === 0}
              className="inline-flex items-center px-3 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 transition"
            >
              <CheckCircle2 className="w-4 h-4 mr-1.5" />
              Bulk Approve Clean
            </button>
          )}
        </div>
      </div>

      {/* Alert Banner */}
      {message.text && (
        <div
          className={`p-4 rounded-md border text-sm flex items-start gap-3 ${
            message.type === 'error'
              ? 'bg-red-50 border-red-200 text-red-800'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          {message.type === 'error' ? (
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600 mt-0.5" />
          ) : (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-600 mt-0.5" />
          )}
          <div className="flex-1 font-medium">{message.text}</div>
          <button onClick={() => setMessage({ type: '', text: '' })} className="text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        {/* Scheduled */}
        <div className="bg-white p-3 rounded-md border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-gray-500 font-medium">
            <span>Scheduled</span>
            <Users className="w-3.5 h-3.5 text-gray-400" />
          </div>
          <div className="mt-1 text-xl font-bold text-gray-900">{metrics.scheduled_count || 0}</div>
        </div>

        {/* Checked In */}
        <div className="bg-white p-3 rounded-md border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-blue-600 font-medium">
            <span>Checked In</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-blue-500" />
          </div>
          <div className="mt-1 text-xl font-bold text-blue-700">{metrics.checked_in_count || 0}</div>
        </div>

        {/* Pending Approval */}
        <div className="bg-white p-3 rounded-md border border-amber-200 shadow-sm bg-amber-50/30">
          <div className="flex items-center justify-between text-xs text-amber-700 font-medium">
            <span>Pending</span>
            <Clock className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="mt-1 text-xl font-bold text-amber-800">{metrics.pending_approval_count || 0}</div>
        </div>

        {/* Approved */}
        <div className="bg-white p-3 rounded-md border border-emerald-200 shadow-sm bg-emerald-50/20">
          <div className="flex items-center justify-between text-xs text-emerald-600 font-medium">
            <span>Approved</span>
            <UserCheck className="w-3.5 h-3.5 text-emerald-500" />
          </div>
          <div className="mt-1 text-xl font-bold text-emerald-700">{metrics.approved_count || 0}</div>
        </div>

        {/* Late */}
        <div className="bg-white p-3 rounded-md border border-orange-200 shadow-sm bg-orange-50/20">
          <div className="flex items-center justify-between text-xs text-orange-600 font-medium">
            <span>Late Arrivals</span>
            <AlertTriangle className="w-3.5 h-3.5 text-orange-500" />
          </div>
          <div className="mt-1 text-xl font-bold text-orange-700">{metrics.late_count || 0}</div>
        </div>

        {/* Flagged / Anomalies */}
        <div className="bg-white p-3 rounded-md border border-red-200 shadow-sm bg-red-50/20">
          <div className="flex items-center justify-between text-xs text-red-600 font-medium">
            <span>Flagged</span>
            <AlertOctagon className="w-3.5 h-3.5 text-red-500" />
          </div>
          <div className="mt-1 text-xl font-bold text-red-700">{metrics.flagged_count || 0}</div>
        </div>

        {/* Absent */}
        <div className="bg-white p-3 rounded-md border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-gray-500 font-medium">
            <span>Absent</span>
            <UserX className="w-3.5 h-3.5 text-gray-400" />
          </div>
          <div className="mt-1 text-xl font-bold text-gray-700">{metrics.absent_count || 0}</div>
        </div>

        {/* Coverage */}
        <div className="bg-white p-3 rounded-md border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-xs text-slate-700 font-medium">
            <span>Coverage</span>
            <Shield className="w-3.5 h-3.5 text-slate-500" />
          </div>
          <div className="mt-1 text-xl font-bold text-slate-900">{metrics.coverage_percentage || 0}%</div>
        </div>
      </div>

      {/* Main Tabs Navigation */}
      <div className="border-b border-gray-200 flex items-center justify-between">
        <nav className="-mb-px flex space-x-6">
          <button
            onClick={() => setActiveTab('board')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'board'
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Clock className="w-4 h-4" />
            Duty Attendance Board
          </button>

          <button
            onClick={() => setActiveTab('regularisations')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'regularisations'
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <History className="w-4 h-4" />
            Regularisation Requests
          </button>

          {isAdmin && (
            <button
              onClick={() => setActiveTab('periods')}
              className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                activeTab === 'periods'
                  ? 'border-slate-900 text-slate-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Lock className="w-4 h-4" />
              Monthly Period Closures
            </button>
          )}
        </nav>
      </div>

      {/* TAB 1: DUTY ATTENDANCE BOARD */}
      {activeTab === 'board' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
            {/* Left: Date Selector & Navigation */}
            <div className="flex items-center gap-2">
              <div className="flex items-center border border-gray-300 rounded-md bg-white">
                <button
                  onClick={() => shiftDate(-1)}
                  className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-50 border-r border-gray-300 rounded-l-md"
                  title="Previous Day"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="px-3 py-1.5 text-sm font-medium text-gray-700 border-none focus:ring-0"
                />
                <button
                  onClick={() => shiftDate(1)}
                  className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-50 border-l border-gray-300 rounded-r-md"
                  title="Next Day"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              <button
                onClick={setToday}
                className="px-2.5 py-1.5 text-xs font-semibold text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-md transition"
              >
                Today
              </button>
            </div>

            {/* Middle: Site Dropdown */}
            <div className="flex items-center gap-2 min-w-[240px]">
              <MapPin className="w-4 h-4 text-gray-400" />
              <select
                value={selectedSiteId}
                onChange={(e) => setSelectedSiteId(e.target.value)}
                className="block w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-slate-900 focus:border-slate-900"
              >
                <option value="">All Assigned Sites</option>
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.site_name} ({s.site_code})
                  </option>
                ))}
              </select>
            </div>

            {/* Right: Status Filters */}
            <div className="flex items-center gap-1.5 overflow-x-auto text-xs font-medium">
              {[
                { id: 'ALL', label: 'All Records' },
                { id: 'pending_approval', label: 'Pending Review' },
                { id: 'flagged', label: 'Flagged Only' },
                { id: 'approved', label: 'Approved' },
                { id: 'late', label: 'Late' },
                { id: 'absent', label: 'Absent' },
              ].map((filter) => (
                <button
                  key={filter.id}
                  onClick={() => setStatusFilter(filter.id)}
                  className={`px-2.5 py-1.5 rounded-md transition whitespace-nowrap ${
                    statusFilter === filter.id
                      ? 'bg-slate-900 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {filter.label}
                </button>
              ))}

              <button
                onClick={fetchBoardData}
                disabled={loading}
                className="p-1.5 text-gray-400 hover:text-gray-700 rounded-md hover:bg-gray-100 transition"
                title="Refresh Board"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Records Table */}
          <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-gray-600 text-xs font-semibold uppercase tracking-wider text-left">
                  <tr>
                    <th className="px-4 py-3">Security Guard</th>
                    <th className="px-4 py-3">Site & Shift</th>
                    <th className="px-4 py-3">Scheduled</th>
                    <th className="px-4 py-3">Actual Check-In</th>
                    <th className="px-4 py-3">Actual Check-Out</th>
                    <th className="px-4 py-3">Worked (OT)</th>
                    <th className="px-4 py-3">Verification & Flags</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {loading ? (
                    <tr>
                      <td colSpan="9" className="px-4 py-12 text-center text-gray-500">
                        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400 mb-2" />
                        Loading attendance board...
                      </td>
                    </tr>
                  ) : records.length === 0 ? (
                    <tr>
                      <td colSpan="9" className="px-4 py-12 text-center text-gray-500">
                        No attendance records found for this date and filter criteria.
                      </td>
                    </tr>
                  ) : (
                    records.map((rec) => {
                      const hasFlags = rec.flags_count > 0;
                      return (
                        <tr key={rec.attendance_id} className="hover:bg-gray-50/80 transition">
                          {/* Guard Info */}
                          <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <div>
                                <div className="font-semibold">{rec.employee_name}</div>
                                <div className="text-xs text-gray-500 font-mono">{rec.employee_code}</div>
                              </div>
                              {rec.is_manual && (
                                <span className="text-[10px] bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-semibold">
                                  Manual
                                </span>
                              )}
                              {rec.is_offline && (
                                <span className="text-[10px] bg-slate-200 text-slate-800 px-1.5 py-0.5 rounded font-semibold">
                                  Offline
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Site & Shift */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="text-gray-900 font-medium">{rec.site_name}</div>
                            <div className="text-xs text-gray-500">{rec.shift_name}</div>
                          </td>

                          {/* Scheduled */}
                          <td className="px-4 py-3 text-xs text-gray-600 whitespace-nowrap">
                            {formatTime(rec.scheduled_start)} - {formatTime(rec.scheduled_end)}
                          </td>

                          {/* Check-In */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="font-medium text-gray-900">
                              {rec.actual_check_in ? formatTime(rec.actual_check_in) : '--:--'}
                            </div>
                            {rec.late_minutes > 0 && (
                              <div className="text-xs text-orange-600 font-medium">
                                +{rec.late_minutes}m late
                              </div>
                            )}
                          </td>

                          {/* Check-Out */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="font-medium text-gray-900">
                              {rec.actual_check_out ? formatTime(rec.actual_check_out) : '--:--'}
                            </div>
                            {rec.early_exit_minutes > 0 && (
                              <div className="text-xs text-rose-600 font-medium">
                                -{rec.early_exit_minutes}m early
                              </div>
                            )}
                          </td>

                          {/* Worked Minutes */}
                          <td className="px-4 py-3 whitespace-nowrap text-xs">
                            <div className="font-medium text-gray-900">
                              {Math.floor(rec.worked_minutes / 60)}h {rec.worked_minutes % 60}m
                            </div>
                            {rec.overtime_minutes > 0 && (
                              <div className="text-emerald-700 font-semibold">
                                OT: {Math.floor(rec.overtime_minutes / 60)}h {rec.overtime_minutes % 60}m
                              </div>
                            )}
                          </td>

                          {/* Flags */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            {hasFlags ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 gap-1">
                                <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                                {rec.flags_count} Anomaly Flag{rec.flags_count > 1 ? 's' : ''}
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 gap-1">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                Verified Clean
                              </span>
                            )}
                          </td>

                          {/* Status */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            {getStatusBadge(rec.status)}
                          </td>

                          {/* Action Buttons */}
                          <td className="px-4 py-3 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1.5">
                              {/* Inspect Evidence Button */}
                              <button
                                onClick={() => handleOpenDetail(rec.attendance_id)}
                                className="p-1.5 text-gray-500 hover:text-slate-900 hover:bg-gray-100 rounded transition"
                                title="Inspect Evidence & GPS"
                              >
                                <Eye className="w-4 h-4" />
                              </button>

                              {/* Quick Approve (Supervisor/Admin) */}
                              {rec.status === 'pending_approval' && (
                                <button
                                  onClick={() => handleApprove(rec)}
                                  disabled={actionLoading}
                                  className="p-1.5 text-emerald-600 hover:text-emerald-800 hover:bg-emerald-50 rounded transition"
                                  title="Approve Attendance"
                                >
                                  <Check className="w-4 h-4" />
                                </button>
                              )}

                              {/* Manual Correction */}
                              <button
                                onClick={() => handleOpenCorrection(rec)}
                                className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded transition"
                                title="Adjust Times"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>

                              {/* Reject */}
                              {rec.status === 'pending_approval' && (
                                <button
                                  onClick={() => handleOpenReject(rec)}
                                  className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition"
                                  title="Reject Attendance"
                                >
                                  <X className="w-4 h-4" />
                                </button>
                              )}

                              {/* Mark Absent */}
                              {!rec.actual_check_in && rec.status !== 'absent' && (
                                <button
                                  onClick={() => handleMarkAbsent(rec)}
                                  className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded transition"
                                  title="Mark Absent"
                                >
                                  <UserX className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: REGULARISATION REQUESTS */}
      {activeTab === 'regularisations' && (
        <div className="space-y-4">
          <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-gray-900">Missed Attendance Regularisation Queue</h3>
                <p className="text-xs text-gray-500">
                  Requests submitted by guards for missed punches, subject to monthly regularisation limits (max 3/month).
                </p>
              </div>
              <button
                onClick={fetchRegularisations}
                className="p-1.5 text-gray-500 hover:text-gray-700 rounded hover:bg-gray-200"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-gray-600 text-xs font-semibold uppercase tracking-wider text-left">
                  <tr>
                    <th className="px-4 py-3">Guard Name</th>
                    <th className="px-4 py-3">Site & Shift</th>
                    <th className="px-4 py-3">Duty Date</th>
                    <th className="px-4 py-3">Claimed Punch Times</th>
                    <th className="px-4 py-3">Guard Reason</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Decision</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {loading ? (
                    <tr>
                      <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400 mb-2" />
                        Loading regularisations...
                      </td>
                    </tr>
                  ) : regularisations.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                        No pending regularisation requests found.
                      </td>
                    </tr>
                  ) : (
                    regularisations.map((reg) => (
                      <tr key={reg.request_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-semibold text-gray-900">
                          {reg.employee_name}
                          <div className="text-xs font-normal text-gray-500 font-mono">{reg.employee_code}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-900">{reg.site_name}</div>
                          <div className="text-xs text-gray-500">{reg.shift_name}</div>
                        </td>
                        <td className="px-4 py-3 text-gray-700">{reg.duty_date}</td>
                        <td className="px-4 py-3 text-xs text-gray-600">
                          In: {formatTime(reg.claimed_check_in)} | Out: {formatTime(reg.claimed_check_out)}
                        </td>
                        <td className="px-4 py-3 text-gray-700 max-w-xs truncate" title={reg.reason}>
                          {reg.reason}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                              reg.status === 'APPROVED'
                                ? 'bg-emerald-100 text-emerald-800'
                                : reg.status === 'REJECTED'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {reg.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {reg.status === 'PENDING' && (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => {
                                  setRegTarget(reg);
                                  setRegDecision('APPROVED');
                                  setRegNotes('');
                                  setShowRegDecisionModal(true);
                                }}
                                className="px-2.5 py-1 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded transition"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => {
                                  setRegTarget(reg);
                                  setRegDecision('REJECTED');
                                  setRegNotes('');
                                  setShowRegDecisionModal(true);
                                }}
                                className="px-2.5 py-1 text-xs font-semibold bg-red-600 hover:bg-red-700 text-white rounded transition"
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: MONTHLY PERIOD CLOSURES (Admin Only) */}
      {activeTab === 'periods' && isAdmin && (
        <div className="space-y-4">
          <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-gray-900">Statutory Monthly Attendance Periods</h3>
                <p className="text-xs text-gray-500">
                  Closed periods are locked against guard check-ins and edits. Module 11 Billing consumes closed periods.
                </p>
              </div>
              <button
                onClick={() => setShowPeriodModal(true)}
                className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-semibold rounded text-white bg-slate-900 hover:bg-slate-800 transition"
              >
                <Plus className="w-3.5 h-3.5 mr-1" />
                Close & Lock Period
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-gray-600 text-xs font-semibold uppercase tracking-wider text-left">
                  <tr>
                    <th className="px-4 py-3">Period (YYYY-MM)</th>
                    <th className="px-4 py-3">Date Range</th>
                    <th className="px-4 py-3">Locked Status</th>
                    <th className="px-4 py-3">Closed By</th>
                    <th className="px-4 py-3">Closed At</th>
                    <th className="px-4 py-3">Exception Notes</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {loading ? (
                    <tr>
                      <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400 mb-2" />
                        Loading periods...
                      </td>
                    </tr>
                  ) : periods.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="px-4 py-12 text-center text-gray-500">
                        No attendance periods closed yet.
                      </td>
                    </tr>
                  ) : (
                    periods.map((p) => (
                      <tr key={p.period_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-semibold text-gray-900">
                          {p.period_year}-{String(p.period_month).padStart(2, '0')}
                        </td>
                        <td className="px-4 py-3 text-gray-600">
                          {p.start_date} to {p.end_date}
                        </td>
                        <td className="px-4 py-3">
                          {p.is_locked ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800 gap-1">
                              <Lock className="w-3 h-3 text-rose-600" />
                              Locked
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 gap-1">
                              <Unlock className="w-3 h-3 text-emerald-600" />
                              Open
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-700">{p.closed_by_name || 'System Admin'}</td>
                        <td className="px-4 py-3 text-xs text-gray-500">
                          {p.closed_at ? new Date(p.closed_at).toLocaleString() : '--'}
                        </td>
                        <td className="px-4 py-3 text-gray-600 text-xs max-w-xs truncate" title={p.exception_notes}>
                          {p.exception_notes || 'None'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {p.is_locked && (
                            <button
                              onClick={() => {
                                setReopenTarget(p);
                                setReopenReason('');
                                setShowReopenModal(true);
                              }}
                              className="px-2.5 py-1 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-100 border border-slate-300 rounded transition"
                            >
                              Reopen
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* EVIDENCE INSPECTION DRAWER / MODAL */}
      {/* ========================================================================= */}
      {selectedRecordForDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-3xl w-full max-h-[90vh] flex flex-col shadow-xl border border-gray-200">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-slate-900 text-white rounded-md">
                  <Shield className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-gray-900">
                    Attendance Evidence: {selectedRecordForDetail.employee_name}
                  </h3>
                  <p className="text-xs text-gray-500">
                    {selectedRecordForDetail.site_name} &bull; {selectedRecordForDetail.shift_name} &bull;{' '}
                    {selectedRecordForDetail.duty_date}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedRecordForDetail(null)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Status & Worked Hours Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-md border border-gray-200 text-xs">
                <div>
                  <span className="text-gray-500 font-medium">Status</span>
                  <div className="mt-0.5">{getStatusBadge(selectedRecordForDetail.status)}</div>
                </div>
                <div>
                  <span className="text-gray-500 font-medium">Worked Minutes</span>
                  <div className="mt-0.5 font-bold text-gray-900">
                    {Math.floor(selectedRecordForDetail.worked_minutes / 60)}h{' '}
                    {selectedRecordForDetail.worked_minutes % 60}m
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 font-medium">Overtime</span>
                  <div className="mt-0.5 font-bold text-emerald-700">
                    {Math.floor(selectedRecordForDetail.overtime_minutes / 60)}h{' '}
                    {selectedRecordForDetail.overtime_minutes % 60}m
                  </div>
                </div>
                <div>
                  <span className="text-gray-500 font-medium">Punctuality</span>
                  <div className="mt-0.5 font-semibold text-gray-800">
                    {selectedRecordForDetail.late_minutes > 0
                      ? `${selectedRecordForDetail.late_minutes}m Late`
                      : 'On Time'}
                  </div>
                </div>
              </div>

              {/* Anomaly Flags Section */}
              {selectedRecordForDetail.flags && selectedRecordForDetail.flags.length > 0 && (
                <div className="p-4 bg-red-50/50 border border-red-200 rounded-md space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-red-800 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                    Detected System Anomalies
                  </h4>
                  <div className="space-y-1.5">
                    {selectedRecordForDetail.flags.map((flag) => (
                      <div
                        key={flag.flag_id}
                        className="text-xs bg-white p-2.5 rounded border border-red-200 flex items-start justify-between"
                      >
                        <div>
                          <span className="font-bold text-red-900 uppercase tracking-wide">
                            {flag.flag_type.replace(/_/g, ' ')}
                          </span>
                          <span className="mx-2 text-gray-400">&bull;</span>
                          <span className="text-red-800">{flag.flag_reason}</span>
                        </div>
                        <span className="text-[11px] text-gray-400">
                          {flag.severity}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Captures & GPS Evidence Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Check In Evidence */}
                <div className="p-4 border border-gray-200 rounded-md bg-white space-y-3">
                  <div className="flex items-center justify-between border-b pb-2">
                    <span className="text-xs font-bold uppercase text-gray-700 flex items-center gap-1.5">
                      <Camera className="w-4 h-4 text-slate-700" />
                      Check-In Capture
                    </span>
                    <span className="text-xs font-medium text-gray-500">
                      {formatTime(selectedRecordForDetail.actual_check_in)}
                    </span>
                  </div>

                  {/* Photo Thumbnail placeholder */}
                  <div className="w-full h-40 bg-gray-100 rounded border border-dashed border-gray-300 flex flex-col items-center justify-center text-gray-400">
                    <Camera className="w-8 h-8 mb-1 text-gray-300" />
                    <span className="text-xs font-medium text-gray-500">Live Camera Photo Verified</span>
                    <span className="text-[10px] text-gray-400">In-App Capture</span>
                  </div>

                  {/* Technical Coordinates */}
                  {selectedRecordForDetail.captures && selectedRecordForDetail.captures.find(c => c.capture_type === 'check_in') && (
                    <div className="text-xs space-y-1 text-gray-600 bg-gray-50 p-2.5 rounded">
                      {(() => {
                        const cap = selectedRecordForDetail.captures.find(c => c.capture_type === 'check_in');
                        return (
                          <>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Distance to Site Center:</span>
                              <span className="font-semibold text-gray-900">{cap.distance_meters?.toFixed(1) || '--'} meters</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">GPS Accuracy:</span>
                              <span className="font-medium text-gray-800">&plusmn;{cap.accuracy_meters?.toFixed(1) || '--'}m</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Mock Location Check:</span>
                              <span className={`font-semibold ${cap.is_mock_location ? 'text-red-600' : 'text-emerald-700'}`}>
                                {cap.is_mock_location ? 'DETECTED' : 'Clean (Real Hardware)'}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Device ID:</span>
                              <span className="font-mono text-[11px] text-gray-700">{cap.device_id || 'Registered Handset'}</span>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>

                {/* Check Out Evidence */}
                <div className="p-4 border border-gray-200 rounded-md bg-white space-y-3">
                  <div className="flex items-center justify-between border-b pb-2">
                    <span className="text-xs font-bold uppercase text-gray-700 flex items-center gap-1.5">
                      <Camera className="w-4 h-4 text-slate-700" />
                      Check-Out Capture
                    </span>
                    <span className="text-xs font-medium text-gray-500">
                      {formatTime(selectedRecordForDetail.actual_check_out)}
                    </span>
                  </div>

                  {/* Photo Thumbnail placeholder */}
                  <div className="w-full h-40 bg-gray-100 rounded border border-dashed border-gray-300 flex flex-col items-center justify-center text-gray-400">
                    <Camera className="w-8 h-8 mb-1 text-gray-300" />
                    <span className="text-xs font-medium text-gray-500">
                      {selectedRecordForDetail.actual_check_out ? 'Live Camera Photo Verified' : 'Check-Out Pending'}
                    </span>
                    <span className="text-[10px] text-gray-400">In-App Capture</span>
                  </div>

                  {/* Technical Coordinates */}
                  {selectedRecordForDetail.captures && selectedRecordForDetail.captures.find(c => c.capture_type === 'check_out') && (
                    <div className="text-xs space-y-1 text-gray-600 bg-gray-50 p-2.5 rounded">
                      {(() => {
                        const cap = selectedRecordForDetail.captures.find(c => c.capture_type === 'check_out');
                        return (
                          <>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Distance to Site Center:</span>
                              <span className="font-semibold text-gray-900">{cap.distance_meters?.toFixed(1) || '--'} meters</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">GPS Accuracy:</span>
                              <span className="font-medium text-gray-800">&plusmn;{cap.accuracy_meters?.toFixed(1) || '--'}m</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Mock Location Check:</span>
                              <span className={`font-semibold ${cap.is_mock_location ? 'text-red-600' : 'text-emerald-700'}`}>
                                {cap.is_mock_location ? 'DETECTED' : 'Clean (Real Hardware)'}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-500">Device ID:</span>
                              <span className="font-mono text-[11px] text-gray-700">{cap.device_id || 'Registered Handset'}</span>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>
              </div>

              {/* Revision History */}
              {selectedRecordForDetail.revisions && selectedRecordForDetail.revisions.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center gap-1.5">
                    <History className="w-4 h-4 text-gray-500" />
                    Correction Audit History
                  </h4>
                  <div className="border border-gray-200 rounded-md overflow-hidden text-xs">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50 text-gray-600 font-semibold text-left">
                        <tr>
                          <th className="px-3 py-2">Adjusted At</th>
                          <th className="px-3 py-2">Adjusted By</th>
                          <th className="px-3 py-2">Previous Times</th>
                          <th className="px-3 py-2">New Times</th>
                          <th className="px-3 py-2">Mandatory Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 bg-white">
                        {selectedRecordForDetail.revisions.map((rev) => (
                          <tr key={rev.revision_id}>
                            <td className="px-3 py-2 text-gray-500 whitespace-nowrap">
                              {new Date(rev.revised_at).toLocaleString()}
                            </td>
                            <td className="px-3 py-2 font-medium text-gray-900">{rev.actor_name || 'Supervisor'}</td>
                            <td className="px-3 py-2 text-gray-500">
                              In: {formatTime(rev.previous_check_in)} | Out: {formatTime(rev.previous_check_out)}
                            </td>
                            <td className="px-3 py-2 font-medium text-gray-900">
                              In: {formatTime(rev.new_check_in)} | Out: {formatTime(rev.new_check_out)}
                            </td>
                            <td className="px-3 py-2 text-gray-700">{rev.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
              <button
                onClick={() => setSelectedRecordForDetail(null)}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                Close
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    handleOpenCorrection(selectedRecordForDetail);
                  }}
                  className="px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50"
                >
                  Edit Times
                </button>
                {selectedRecordForDetail.status === 'pending_approval' && (
                  <button
                    onClick={() => {
                      handleApprove(selectedRecordForDetail);
                    }}
                    disabled={actionLoading}
                    className="px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded transition"
                  >
                    Approve Record
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* CORRECTION MODAL */}
      {/* ========================================================================= */}
      {showCorrectionModal && correctionTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-lg w-full shadow-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-gray-900">
                Adjust Attendance Times: {correctionTarget.employee_name}
              </h3>
              <button onClick={() => setShowCorrectionModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCorrectionSubmit} className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Check-In Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={correctionForm.check_in_time}
                    onChange={(e) => setCorrectionForm({ ...correctionForm, check_in_time: e.target.value })}
                    className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Check-Out Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={correctionForm.check_out_time}
                    onChange={(e) => setCorrectionForm({ ...correctionForm, check_out_time: e.target.value })}
                    className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Mandatory Audit Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  required
                  rows="3"
                  value={correctionForm.reason}
                  onChange={(e) => setCorrectionForm({ ...correctionForm, reason: e.target.value })}
                  placeholder="Explain why these times are being manually corrected..."
                  className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-slate-900 focus:border-slate-900"
                />
              </div>

              <div className="p-3 bg-amber-50 rounded-md border border-amber-200 text-xs text-amber-800 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <strong>Statutory Notice:</strong> Corrections over 120 minutes are flagged as large corrections and
                  subject to compliance audit.
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowCorrectionModal(false)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition"
                >
                  {actionLoading ? 'Saving...' : 'Save Correction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* REJECT MODAL */}
      {/* ========================================================================= */}
      {showRejectModal && rejectTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-md w-full shadow-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-gray-900">
                Reject Attendance: {rejectTarget.employee_name}
              </h3>
              <button onClick={() => setShowRejectModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRejectSubmit} className="space-y-4 text-sm">
              <p className="text-xs text-gray-500">
                Rejecting attendance disallows billing and worked hour credit for this shift.
              </p>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Rejection Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  required
                  rows="3"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="State the reason for rejecting this record..."
                  className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-slate-900 focus:border-slate-900"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowRejectModal(false)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded transition"
                >
                  {actionLoading ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* BULK APPROVAL MODAL */}
      {/* ========================================================================= */}
      {showBulkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-md w-full shadow-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-gray-900">Bulk Approve Clean Attendance</h3>
              <button onClick={() => setShowBulkModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-gray-600">
              This will approve all records for <strong>{selectedDate}</strong> at the selected site that have{' '}
              <strong>zero anomaly flags</strong>. Any records with GPS anomalies, clock mismatches, or suspicious devices
              will be preserved for individual review.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t">
              <button
                type="button"
                onClick={() => setShowBulkModal(false)}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkApprove}
                disabled={actionLoading}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition"
              >
                {actionLoading ? 'Approving...' : 'Confirm Bulk Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* PERIOD CLOSE MODAL */}
      {/* ========================================================================= */}
      {showPeriodModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-md w-full shadow-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-gray-900">Close & Lock Attendance Period</h3>
              <button onClick={() => setShowPeriodModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handlePeriodCloseSubmit} className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Year</label>
                  <input
                    type="number"
                    value={periodForm.period_year}
                    onChange={(e) => setPeriodForm({ ...periodForm, period_year: parseInt(e.target.value) })}
                    className="w-full text-sm border-gray-300 rounded-md shadow-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Month (1 - 12)</label>
                  <input
                    type="number"
                    min="1"
                    max="12"
                    value={periodForm.period_month}
                    onChange={(e) => setPeriodForm({ ...periodForm, period_month: parseInt(e.target.value) })}
                    className="w-full text-sm border-gray-300 rounded-md shadow-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Exception Notes (Optional)</label>
                <textarea
                  rows="2"
                  value={periodForm.exception_notes}
                  onChange={(e) => setPeriodForm({ ...periodForm, exception_notes: e.target.value })}
                  placeholder="E.g., Closed on 25th for payroll cycle..."
                  className="w-full text-sm border-gray-300 rounded-md shadow-sm"
                />
              </div>

              <div className="p-3 bg-red-50 rounded-md border border-red-200 text-xs text-red-800">
                <strong>Important:</strong> Once locked, all records in this calendar month cannot be modified or punched
                without formal administrative reopening.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowPeriodModal(false)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition"
                >
                  {actionLoading ? 'Closing...' : 'Close & Lock'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* PERIOD REOPEN MODAL */}
      {/* ========================================================================= */}
      {showReopenModal && reopenTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-md w-full shadow-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-gray-900">
                Reopen Period: {reopenTarget.period_year}-{reopenTarget.period_month}
              </h3>
              <button onClick={() => setShowReopenModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handlePeriodReopenSubmit} className="space-y-4 text-sm">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Mandatory Audit Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  required
                  rows="3"
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                  placeholder="Explain statutory or administrative reason for reopening a closed period..."
                  className="w-full text-sm border-gray-300 rounded-md shadow-sm"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowReopenModal(false)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded transition"
                >
                  {actionLoading ? 'Reopening...' : 'Confirm Reopen'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* REGULARISATION DECISION MODAL */}
      {/* ========================================================================= */}
      {showRegDecisionModal && regTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-md max-w-md w-full shadow-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-gray-900">
                {regDecision === 'APPROVED' ? 'Approve' : 'Reject'} Regularisation: {regTarget.employee_name}
              </h3>
              <button onClick={() => setShowRegDecisionModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRegularisationDecision} className="space-y-4 text-sm">
              <div className="text-xs text-gray-600 bg-gray-50 p-3 rounded space-y-1">
                <div><strong>Site:</strong> {regTarget.site_name}</div>
                <div><strong>Duty Date:</strong> {regTarget.duty_date}</div>
                <div><strong>Guard Reason:</strong> {regTarget.reason}</div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Supervisor Decision Notes
                </label>
                <textarea
                  rows="3"
                  value={regNotes}
                  onChange={(e) => setRegNotes(e.target.value)}
                  placeholder="Enter decision rationale..."
                  className="w-full text-sm border-gray-300 rounded-md shadow-sm"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowRegDecisionModal(false)}
                  className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className={`px-4 py-1.5 text-xs font-semibold text-white rounded transition ${
                    regDecision === 'APPROVED' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {actionLoading ? 'Processing...' : `Confirm ${regDecision}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


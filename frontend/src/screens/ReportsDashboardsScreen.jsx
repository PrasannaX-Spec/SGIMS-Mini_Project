import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  FileSpreadsheet,
  Download,
  BookOpen,
  HeartPulse,
  Send,
  History,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Lock,
  Filter,
  Search,
  ChevronRight,
  Eye,
  FileText,
  Shield,
  Users,
  AlertOctagon,
  Receipt,
  Briefcase,
  Layers,
  Calendar,
  X,
  ExternalLink,
  Save,
  Trash2
} from 'lucide-react';
import { reportsApi, masterApi } from '../api';

export default function ReportsDashboardsScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isSupervisor = currentUser?.role === 'SUPERVISOR';

  // Navigation tab
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard' | 'catalogue' | 'dictionary' | 'health' | 'client-summaries' | 'export-history'

  // Common State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Sites list for filtering
  const [sites, setSites] = useState([]);
  const [clients, setClients] = useState([]);

  // 1. Dashboard State
  const [dashboardData, setDashboardData] = useState(null);
  const [dashboardSiteId, setDashboardSiteId] = useState('');

  // 2. Catalogue & Report Viewer State
  const [catalogue, setCatalogue] = useState([]);
  const [selectedReportCode, setSelectedReportCode] = useState('MANPOWER_REQ');
  const [reportStartDate, setReportStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split('T')[0];
  });
  const [reportEndDate, setReportEndDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [reportSiteId, setReportSiteId] = useState('');
  const [reportDetail, setReportDetail] = useState(null);
  const [tableSearch, setTableSearch] = useState('');

  // Presets
  const [presets, setPresets] = useState([]);
  const [presetNameInput, setPresetNameInput] = useState('');
  const [showSavePresetModal, setShowSavePresetModal] = useState(false);

  // Bulk Export Reason Modal
  const [showBulkExportModal, setShowBulkExportModal] = useState(false);
  const [bulkExportFormat, setBulkExportFormat] = useState('CSV');
  const [bulkReasonInput, setBulkReasonInput] = useState('');

  // 3. Metric Dictionary State
  const [metrics, setMetrics] = useState([]);
  const [metricsSearch, setMetricsSearch] = useState('');
  const [metricModuleFilter, setMetricModuleFilter] = useState('');
  const [selectedMetric, setSelectedMetric] = useState(null);
  const [metricVersions, setMetricVersions] = useState([]);
  const [showProposeModal, setShowProposeModal] = useState(false);
  const [proposeFormula, setProposeFormula] = useState('');
  const [proposeReason, setProposeReason] = useState('');

  // 4. Data Health State
  const [healthData, setHealthData] = useState(null);
  const [reconciling, setReconciling] = useState(false);

  // 5. Client Monthly Summaries State
  const [clientSummaries, setClientSummaries] = useState([]);
  const [summaryClientId, setSummaryClientId] = useState('');
  const [summaryMonth, setSummaryMonth] = useState(new Date().getMonth() + 1);
  const [summaryYear, setSummaryYear] = useState(new Date().getFullYear());
  const [activeSummaryDetail, setActiveSummaryDetail] = useState(null);

  // 6. Export History State
  const [exportHistory, setExportHistory] = useState([]);

  // Initial Load
  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchDashboard();
    } else if (activeTab === 'catalogue') {
      fetchCatalogueAndDetail();
      fetchPresets();
    } else if (activeTab === 'dictionary') {
      fetchMetrics();
    } else if (activeTab === 'health' && isAdmin) {
      fetchDataHealth();
    } else if (activeTab === 'client-summaries') {
      fetchClientSummaries();
    } else if (activeTab === 'export-history') {
      fetchExportHistory();
    }
  }, [activeTab]);

  const fetchInitialData = async () => {
    try {
      const [sitesRes, clientsRes] = await Promise.all([
        masterApi.getSites().catch(() => ({ data: [] })),
        isAdmin ? masterApi.getClients().catch(() => ({ data: [] })) : Promise.resolve({ data: [] })
      ]);
      setSites(sitesRes.data || []);
      setClients(clientsRes.data || []);
    } catch (err) {
      console.error("Failed to load sites/clients", err);
    }
  };

  // --------------------------------------------------------------------------
  // Dashboard Fetching
  // --------------------------------------------------------------------------
  const fetchDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (dashboardSiteId) params.site_id = dashboardSiteId;

      if (isAdmin) {
        const res = await reportsApi.getAdminDashboard(params);
        setDashboardData(res.data);
      } else if (isSupervisor) {
        const res = await reportsApi.getSupervisorDashboard(params);
        setDashboardData(res.data);
      }
    } catch (err) {
      setError(err.message || 'Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------------------------
  // Catalogue & Detail Fetching
  // --------------------------------------------------------------------------
  const fetchCatalogueAndDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const catRes = await reportsApi.getCatalogue();
      setCatalogue(catRes.data.reports || []);

      if (selectedReportCode) {
        await loadReportDetail(selectedReportCode);
      }
    } catch (err) {
      setError(err.message || 'Failed to load report catalogue');
    } finally {
      setLoading(false);
    }
  };

  const loadReportDetail = async (code) => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        start_date: reportStartDate,
        end_date: reportEndDate,
      };
      if (reportSiteId) params.site_id = reportSiteId;

      const res = await reportsApi.getReportDetail(code, params);
      setReportDetail(res.data);
      setSelectedReportCode(code);
    } catch (err) {
      setError(err.message || `Failed to load report ${code}`);
      setReportDetail(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchPresets = async () => {
    try {
      const res = await reportsApi.getPresets();
      setPresets(res.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSavePreset = async () => {
    if (!presetNameInput.trim()) return;
    try {
      await reportsApi.createPreset({
        name: presetNameInput,
        report_code: selectedReportCode,
        filter_payload: {
          start_date: reportStartDate,
          end_date: reportEndDate,
          site_id: reportSiteId
        }
      });
      setSuccessMsg(`Preset "${presetNameInput}" saved successfully`);
      setPresetNameInput('');
      setShowSavePresetModal(false);
      fetchPresets();
    } catch (err) {
      setError(err.message || 'Failed to save preset');
    }
  };

  const handleApplyPreset = (p) => {
    if (p.report_code) setSelectedReportCode(p.report_code);
    if (p.filter_payload?.start_date) setReportStartDate(p.filter_payload.start_date);
    if (p.filter_payload?.end_date) setReportEndDate(p.filter_payload.end_date);
    if (p.filter_payload?.site_id !== undefined) setReportSiteId(p.filter_payload.site_id || '');
    loadReportDetail(p.report_code || selectedReportCode);
  };

  const handleDeletePreset = async (id, e) => {
    e.stopPropagation();
    try {
      await reportsApi.deletePreset(id);
      fetchPresets();
    } catch (err) {
      setError(err.message || 'Failed to delete preset');
    }
  };

  // --------------------------------------------------------------------------
  // Exports (CSV / PDF)
  // --------------------------------------------------------------------------
  const initiateExport = (format) => {
    if (reportDetail && reportDetail.row_count > 100) {
      setBulkExportFormat(format);
      setShowBulkExportModal(true);
    } else {
      executeExport(format, '');
    }
  };

  const executeExport = async (format, bulkReason) => {
    setLoading(true);
    setError(null);
    setShowBulkExportModal(false);
    try {
      const payload = {
        report_code: selectedReportCode,
        start_date: reportStartDate,
        end_date: reportEndDate,
        site_id: reportSiteId || undefined,
        bulk_reason: bulkReason || undefined
      };

      if (format === 'CSV') {
        const res = await reportsApi.exportCsv(payload);
        const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${selectedReportCode}_${reportStartDate}_${reportEndDate}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        setSuccessMsg(`CSV export downloaded successfully.`);
      } else {
        const res = await reportsApi.exportPdf(payload);
        setSuccessMsg(`PDF generated: ${res.data.filename} (${res.data.status})`);
      }
    } catch (err) {
      setError(err.message || 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------------------------
  // Metric Dictionary
  // --------------------------------------------------------------------------
  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const params = {};
      if (metricModuleFilter) params.module = metricModuleFilter;
      if (metricsSearch) params.search = metricsSearch;
      const res = await reportsApi.getMetrics(params);
      setMetrics(res.data.metrics || []);
    } catch (err) {
      setError(err.message || 'Failed to load metric definitions');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectMetric = async (m) => {
    setSelectedMetric(m);
    try {
      const res = await reportsApi.getMetricVersions(m.metric_id);
      setMetricVersions(res.data.versions || []);
    } catch (err) {
      setMetricVersions([]);
    }
  };

  const handleProposeVersion = async () => {
    if (!proposeReason.trim()) return;
    try {
      await reportsApi.proposeMetricVersion(selectedMetric.metric_id, {
        formula: proposeFormula || selectedMetric.formula,
        change_reason: proposeReason
      });
      setSuccessMsg(`Version proposed successfully for ${selectedMetric.metric_id}`);
      setShowProposeModal(false);
      setProposeReason('');
      fetchMetrics();
      if (selectedMetric) handleSelectMetric(selectedMetric);
    } catch (err) {
      setError(err.message || 'Failed to propose new version');
    }
  };

  // --------------------------------------------------------------------------
  // Data Health Panel
  // --------------------------------------------------------------------------
  const fetchDataHealth = async () => {
    setLoading(true);
    try {
      const res = await reportsApi.getDataHealth();
      setHealthData(res.data);
    } catch (err) {
      setError(err.message || 'Failed to load data health metrics');
    } finally {
      setLoading(false);
    }
  };

  const handleRunReconciliation = async () => {
    setReconciling(true);
    try {
      const res = await reportsApi.triggerRepair();
      setSuccessMsg(res.data.message || 'Reconciliation completed.');
      fetchDataHealth();
    } catch (err) {
      setError(err.message || 'Reconciliation run failed');
    } finally {
      setReconciling(false);
    }
  };

  // --------------------------------------------------------------------------
  // Client Monthly Summaries
  // --------------------------------------------------------------------------
  const fetchClientSummaries = async () => {
    setLoading(true);
    try {
      const params = {};
      if (summaryClientId) params.client_id = summaryClientId;
      const res = await reportsApi.getClientSummaries(params);
      setClientSummaries(res.data || []);
    } catch (err) {
      setError(err.message || 'Failed to load client monthly summaries');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateClientSummary = async () => {
    if (!summaryClientId) {
      setError('Please select a client organization.');
      return;
    }
    setLoading(true);
    try {
      const res = await reportsApi.generateClientSummary({
        client_id: summaryClientId,
        month: parseInt(summaryMonth, 10),
        year: parseInt(summaryYear, 10)
      });
      setSuccessMsg(`Monthly Summary generated (${res.data.status})`);
      fetchClientSummaries();
    } catch (err) {
      setError(err.message || 'Failed to generate client summary');
    } finally {
      setLoading(false);
    }
  };

  const handleReleaseSummary = async (id) => {
    try {
      await reportsApi.releaseClientSummary(id);
      setSuccessMsg('Client Service Summary successfully released to Client Portal!');
      fetchClientSummaries();
    } catch (err) {
      setError(err.message || 'Failed to release summary');
    }
  };

  // --------------------------------------------------------------------------
  // Export History
  // --------------------------------------------------------------------------
  const fetchExportHistory = async () => {
    setLoading(true);
    try {
      const res = await reportsApi.getExportHistory();
      setExportHistory(res.data || []);
    } catch (err) {
      setError(err.message || 'Failed to load export history');
    } finally {
      setLoading(false);
    }
  };

  // Filtered rows for report detail view
  const filteredReportRows = (reportDetail?.rows || []).filter((r) => {
    if (!tableSearch) return true;
    return Object.values(r).some((val) =>
      String(val).toLowerCase().includes(tableSearch.toLowerCase())
    );
  });

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-gray-200">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Reports & Dashboards
            </h1>
            <span className="px-2 py-0.5 text-xs font-semibold bg-slate-100 text-slate-800 rounded-md border border-slate-300">
              Module 13
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Authoritative operational metrics, fixed reports catalogue, data health monitoring, and client service summaries.
          </p>
        </div>

        {/* Global Action / Status Badge */}
        <div className="flex items-center space-x-3">
          {dashboardData && (
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-gray-500">Data Status:</span>
              <span
                className={`px-2.5 py-1 rounded-md font-semibold ${
                  dashboardData.status_label === 'FINAL'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-300'
                    : 'bg-amber-50 text-amber-800 border border-amber-300'
                }`}
              >
                {dashboardData.status_label || 'PROVISIONAL'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-800 rounded-md text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 hover:text-emerald-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Primary Tab Navigation */}
      <div className="flex items-center space-x-1 border-b border-gray-200 overflow-x-auto text-sm">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 px-4 py-2.5 border-b-2 font-medium transition whitespace-nowrap rounded-t-md ${
            activeTab === 'dashboard'
              ? 'border-slate-900 text-slate-900 bg-slate-50'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Overview Dashboard</span>
        </button>

        <button
          onClick={() => setActiveTab('catalogue')}
          className={`flex items-center space-x-2 px-4 py-2.5 border-b-2 font-medium transition whitespace-nowrap rounded-t-md ${
            activeTab === 'catalogue'
              ? 'border-slate-900 text-slate-900 bg-slate-50'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" />
          <span>Report Catalogue & Viewer</span>
        </button>

        <button
          onClick={() => setActiveTab('dictionary')}
          className={`flex items-center space-x-2 px-4 py-2.5 border-b-2 font-medium transition whitespace-nowrap rounded-t-md ${
            activeTab === 'dictionary'
              ? 'border-slate-900 text-slate-900 bg-slate-50'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          <span>Metric Dictionary</span>
        </button>

        {isAdmin && (
          <button
            onClick={() => setActiveTab('health')}
            className={`flex items-center space-x-2 px-4 py-2.5 border-b-2 font-medium transition whitespace-nowrap rounded-t-md ${
              activeTab === 'health'
                ? 'border-slate-900 text-slate-900 bg-slate-50'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            <HeartPulse className="w-4 h-4" />
            <span>Data Health Panel</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab('client-summaries')}
          className={`flex items-center space-x-2 px-4 py-2.5 border-b-2 font-medium transition whitespace-nowrap rounded-t-md ${
            activeTab === 'client-summaries'
              ? 'border-slate-900 text-slate-900 bg-slate-50'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          <Send className="w-4 h-4" />
          <span>Client Service Summaries</span>
        </button>

        <button
          onClick={() => setActiveTab('export-history')}
          className={`flex items-center space-x-2 px-4 py-2.5 border-b-2 font-medium transition whitespace-nowrap rounded-t-md ${
            activeTab === 'export-history'
              ? 'border-slate-900 text-slate-900 bg-slate-50'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Export History</span>
        </button>
      </div>

      {/* ==================================================================== */}
      {/* TAB 1: OVERVIEW DASHBOARD */}
      {/* ==================================================================== */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {/* Dashboard Filter Bar */}
          <div className="bg-white p-4 border border-gray-200 rounded-md shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center space-x-3">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Scope Filter:
              </span>
              <select
                value={dashboardSiteId}
                onChange={(e) => setDashboardSiteId(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-hidden focus:ring-1 focus:ring-slate-900"
              >
                <option value="">All Authorized Sites</option>
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.site_name} ({s.site_code})
                  </option>
                ))}
              </select>
              <button
                onClick={fetchDashboard}
                disabled={loading}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-medium rounded-md flex items-center space-x-1"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>

            <div className="text-xs text-gray-500 flex items-center space-x-2">
              <Clock className="w-3.5 h-3.5 text-gray-400" />
              <span>Calculated: {dashboardData?.as_of_time ? new Date(dashboardData.as_of_time).toLocaleTimeString('en-IN') : '--'}</span>
            </div>
          </div>

          {/* Data Quality Notice Banner */}
          {dashboardData?.data_quality_notes && (
            <div
              className={`p-3 rounded-md text-xs border flex items-start space-x-3 ${
                dashboardData.status_label === 'PROVISIONAL'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-900'
              }`}
            >
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <div className="font-semibold">
                  Status: {dashboardData.status_label} &mdash; Data Quality Notes
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-gray-700">
                  <span>Pending Attendance Approvals: <strong>{dashboardData.data_quality_notes.pending_attendance_approvals}</strong></span>
                  <span>Unlocked Attendance Periods: <strong>{dashboardData.data_quality_notes.unlocked_attendance_periods}</strong></span>
                  <span>Manual Attendance Entries: <strong>{dashboardData.data_quality_notes.manual_attendance_entries}</strong></span>
                  <span>Offline Captures: <strong>{dashboardData.data_quality_notes.offline_attendance_captures}</strong></span>
                  {isAdmin && (
                    <span>Open Weapon Discrepancies: <strong>{dashboardData.data_quality_notes.unresolved_weapon_discrepancies}</strong></span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Metric Cards Grid */}
          {loading && !dashboardData ? (
            <div className="py-16 text-center text-gray-500">Loading operational metrics...</div>
          ) : dashboardData?.kpis ? (
            <div className="space-y-6">
              {/* Category 1: Manpower Deployment */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3 flex items-center space-x-1.5">
                  <Briefcase className="w-4 h-4 text-slate-700" />
                  <span>Deployment & Manpower Coverage</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                  <KpiCard
                    title="Required Posts"
                    metricId="M01"
                    data={dashboardData.kpis.required_posts}
                    onClick={() => {
                      setSelectedReportCode('MANPOWER_REQ');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Filled Posts"
                    metricId="M02"
                    data={dashboardData.kpis.filled_posts}
                    onClick={() => {
                      setSelectedReportCode('MANPOWER_REQ');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Fill Rate"
                    metricId="M03"
                    data={dashboardData.kpis.fill_rate}
                    highlight
                    onClick={() => {
                      setSelectedReportCode('MANPOWER_REQ');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Current Vacancies"
                    metricId="M04"
                    data={dashboardData.kpis.vacancies}
                    warning={dashboardData.kpis.vacancies?.value > 0}
                    onClick={() => {
                      setSelectedReportCode('VACANCY_SHORTFALL');
                      setActiveTab('catalogue');
                    }}
                  />
                </div>
              </div>

              {/* Category 2: Attendance Verification */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3 flex items-center space-x-1.5">
                  <Clock className="w-4 h-4 text-slate-700" />
                  <span>Attendance & Shift Compliance</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                  <KpiCard
                    title="Attendance Rate"
                    metricId="M12"
                    data={dashboardData.kpis.attendance_rate}
                    onClick={() => {
                      setSelectedReportCode('ATTENDANCE_SUMMARY');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Late Arrival Rate"
                    metricId="M13"
                    data={dashboardData.kpis.late_rate}
                    onClick={() => {
                      setSelectedReportCode('ATTENDANCE_SUMMARY');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Early Exit Rate"
                    metricId="M15"
                    data={dashboardData.kpis.early_exit_rate}
                    onClick={() => {
                      setSelectedReportCode('ATTENDANCE_SUMMARY');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Pending Approvals"
                    metricId="M21"
                    data={dashboardData.kpis.pending_approvals}
                    warning={dashboardData.kpis.pending_approvals?.value > 0}
                    onClick={() => {
                      setSelectedReportCode('ATTENDANCE_SUMMARY');
                      setActiveTab('catalogue');
                    }}
                  />
                </div>
              </div>

              {/* Category 3: Safety, Incidents & Panic */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3 flex items-center space-x-1.5">
                  <AlertOctagon className="w-4 h-4 text-slate-700" />
                  <span>Incidents & Panic Monitoring</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                  <KpiCard
                    title="Open Incidents"
                    metricId="M36"
                    data={dashboardData.kpis.open_incidents}
                    onClick={() => {
                      setSelectedReportCode('INCIDENT_SUMMARY');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Real Panic Alerts"
                    metricId="M50"
                    data={dashboardData.kpis.panic_alerts}
                    warning={dashboardData.kpis.panic_alerts?.value > 0}
                    onClick={() => {
                      setSelectedReportCode('PANIC_RESPONSE');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Docs Expiring (30d)"
                    metricId="M32"
                    data={dashboardData.kpis.expiring_docs}
                    onClick={() => {
                      setSelectedReportCode('DOC_EXPIRY');
                      setActiveTab('catalogue');
                    }}
                  />
                  <KpiCard
                    title="Active Headcount"
                    metricId="M27"
                    data={dashboardData.kpis.active_guards}
                    onClick={() => {
                      setSelectedReportCode('GUARD_STRENGTH');
                      setActiveTab('catalogue');
                    }}
                  />
                </div>
              </div>

              {/* Category 4: Financial & Armed (Admin Only) */}
              {isAdmin && dashboardData.kpis.billed_amount && (
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3 flex items-center space-x-1.5">
                    <Receipt className="w-4 h-4 text-slate-700" />
                    <span>Commercial & Armoury (Admin Confidential)</span>
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                    <KpiCard
                      title="Billed Amount"
                      metricId="M63"
                      data={dashboardData.kpis.billed_amount}
                      onClick={() => {
                        setSelectedReportCode('BILLING_SUMMARY');
                        setActiveTab('catalogue');
                      }}
                    />
                    <KpiCard
                      title="Outstanding Balance"
                      metricId="M64"
                      data={dashboardData.kpis.outstanding_balance}
                      onClick={() => {
                        setSelectedReportCode('BILLING_SUMMARY');
                        setActiveTab('catalogue');
                      }}
                    />
                    <KpiCard
                      title="Active Weapons"
                      metricId="M69"
                      data={dashboardData.kpis.active_weapons}
                      onClick={() => {
                        setSelectedReportCode('WEAPONS_AMMUNITION');
                        setActiveTab('catalogue');
                      }}
                    />
                    <KpiCard
                      title="Weapon Discrepancies"
                      metricId="M73"
                      data={dashboardData.kpis.open_discrepancies}
                      warning={dashboardData.kpis.open_discrepancies?.value > 0}
                      onClick={() => {
                        setSelectedReportCode('WEAPONS_AMMUNITION');
                        setActiveTab('catalogue');
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="py-16 text-center text-gray-400 bg-white border border-gray-200 rounded-md">
              No operational metric data available for the selected filters.
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: REPORT CATALOGUE & VIEWER */}
      {/* ==================================================================== */}
      {activeTab === 'catalogue' && (
        <div className="space-y-6">
          {/* Top Filter & Report Selector Panel */}
          <div className="bg-white p-5 border border-gray-200 rounded-md shadow-xs space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {/* Report Selection Dropdown */}
              <div className="md:col-span-2 space-y-1">
                <label className="text-xs font-semibold text-gray-700">Select Fixed Report:</label>
                <select
                  value={selectedReportCode}
                  onChange={(e) => loadReportDetail(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                >
                  {catalogue.map((cat) => (
                    <option key={cat.code} value={cat.code}>
                      {cat.report_number}. {cat.name} ({cat.category})
                    </option>
                  ))}
                </select>
              </div>

              {/* Date Range Start */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700">Start Date:</label>
                <input
                  type="date"
                  value={reportStartDate}
                  onChange={(e) => setReportStartDate(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                />
              </div>

              {/* Date Range End */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700">End Date:</label>
                <input
                  type="date"
                  value={reportEndDate}
                  onChange={(e) => setReportEndDate(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                />
              </div>
            </div>

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-3 border-t border-gray-100">
              {/* Site Filter */}
              <div className="flex items-center space-x-3">
                <label className="text-xs font-semibold text-gray-700">Site:</label>
                <select
                  value={reportSiteId}
                  onChange={(e) => setReportSiteId(e.target.value)}
                  className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                >
                  <option value="">All Permitted Sites</option>
                  {sites.map((s) => (
                    <option key={s.site_id} value={s.site_id}>
                      {s.site_name}
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => loadReportDetail(selectedReportCode)}
                  disabled={loading}
                  className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md flex items-center space-x-1.5"
                >
                  <Filter className="w-3.5 h-3.5" />
                  <span>Apply Filters</span>
                </button>
              </div>

              {/* Presets and Export Actions */}
              <div className="flex items-center space-x-2">
                {/* Save Preset Button */}
                <button
                  onClick={() => setShowSavePresetModal(true)}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium rounded-md flex items-center space-x-1"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Save Filter Preset</span>
                </button>

                {/* Export CSV */}
                <button
                  onClick={() => initiateExport('CSV')}
                  disabled={loading || !reportDetail}
                  className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-medium rounded-md flex items-center space-x-1"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export CSV</span>
                </button>

                {/* Export PDF */}
                <button
                  onClick={() => initiateExport('PDF')}
                  disabled={loading || !reportDetail}
                  className="px-3 py-1.5 bg-indigo-700 hover:bg-indigo-800 text-white text-xs font-medium rounded-md flex items-center space-x-1"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Generate PDF</span>
                </button>
              </div>
            </div>

            {/* Presets Bar */}
            {presets.length > 0 && (
              <div className="flex items-center space-x-2 pt-2 text-xs">
                <span className="text-gray-400 font-medium">Saved Presets:</span>
                <div className="flex flex-wrap gap-2">
                  {presets.map((p) => (
                    <span
                      key={p.preset_id}
                      onClick={() => handleApplyPreset(p)}
                      className="inline-flex items-center space-x-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 rounded-md cursor-pointer"
                    >
                      <span>{p.name}</span>
                      <button
                        onClick={(e) => handleDeletePreset(p.preset_id, e)}
                        className="text-gray-400 hover:text-red-600 ml-1"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Report Viewer Header & Data Quality Banner */}
          {reportDetail && (
            <div className="space-y-4">
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-md flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center space-x-2">
                    <h2 className="text-lg font-bold text-gray-900">{reportDetail.report_name}</h2>
                    <span className="text-xs px-2 py-0.5 rounded-md font-semibold bg-white border border-gray-300 text-gray-700">
                      {reportDetail.report_code}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-md font-semibold ${
                        reportDetail.status_label === 'FINAL'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-900'
                      }`}
                    >
                      {reportDetail.status_label}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Classification: <strong>{reportDetail.sensitivity}</strong> | Content Hash: <code>{reportDetail.content_hash?.substring(0, 12)}...</code>
                  </p>
                </div>

                <div className="text-xs text-right text-gray-500">
                  <div>Rows: <strong>{reportDetail.row_count}</strong></div>
                  <div>Calculated At: {new Date(reportDetail.as_of_time).toLocaleTimeString('en-IN')}</div>
                </div>
              </div>

              {/* Data Quality Notes Panel for Report */}
              {reportDetail.data_quality_notes && (
                <div className="p-3 bg-amber-50 border border-amber-200 text-amber-900 rounded-md text-xs space-y-1">
                  <div className="font-semibold flex items-center space-x-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                    <span>Data Quality & Integrity Notes:</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
                    <div>Pending Approvals: <strong>{reportDetail.data_quality_notes.pending_attendance_approvals}</strong></div>
                    <div>Unlocked Periods: <strong>{reportDetail.data_quality_notes.unlocked_attendance_periods}</strong></div>
                    <div>Manual Entries: <strong>{reportDetail.data_quality_notes.manual_attendance_entries}</strong></div>
                    <div>Offline Captures: <strong>{reportDetail.data_quality_notes.offline_attendance_captures}</strong></div>
                  </div>
                </div>
              )}

              {/* Table Search Bar */}
              <div className="flex items-center justify-between gap-4">
                <div className="relative w-72">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search in loaded records..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    className="w-full text-xs border border-gray-300 rounded-md pl-9 pr-3 py-2 bg-white focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                  />
                </div>
                <div className="text-xs text-gray-500">
                  Showing {filteredReportRows.length} of {reportDetail.row_count} rows
                </div>
              </div>

              {/* Data Table */}
              <div className="bg-white border border-gray-200 rounded-md overflow-x-auto shadow-xs">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-100 border-b border-gray-200 text-gray-700 font-semibold">
                      {reportDetail.columns.map((col) => (
                        <th key={col} className="p-3 whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredReportRows.length > 0 ? (
                      filteredReportRows.map((row, idx) => (
                        <tr key={row.id || idx} className="hover:bg-gray-50 transition">
                          {reportDetail.columns.map((col) => (
                            <td key={col} className="p-3 whitespace-nowrap text-gray-800">
                              {row[col] !== undefined && row[col] !== null ? String(row[col]) : '--'}
                            </td>
                          ))}
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan={reportDetail.columns.length}
                          className="p-8 text-center text-gray-400"
                        >
                          No records match the given filters or search term.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 3: METRIC DICTIONARY */}
      {/* ==================================================================== */}
      {activeTab === 'dictionary' && (
        <div className="space-y-6">
          <div className="bg-white p-4 border border-gray-200 rounded-md shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center space-x-3 w-full md:w-auto">
              <div className="relative w-72">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search metric ID, name, formula..."
                  value={metricsSearch}
                  onChange={(e) => setMetricsSearch(e.target.value)}
                  className="w-full text-xs border border-gray-300 rounded-md pl-9 pr-3 py-2 focus:outline-hidden focus:ring-1 focus:ring-slate-900"
                />
              </div>

              <select
                value={metricModuleFilter}
                onChange={(e) => setMetricModuleFilter(e.target.value)}
                className="text-xs border border-gray-300 rounded-md px-3 py-2 bg-white"
              >
                <option value="">All Source Modules</option>
                <option value="M2">M2: Master Data</option>
                <option value="M3">M3: Guard Lifecycle</option>
                <option value="M4">M4: Quotations</option>
                <option value="M5">M5: Deployment Roster</option>
                <option value="M6">M6: Attendance</option>
                <option value="M8">M8: Incidents</option>
                <option value="M9">M9: Panic Escalation</option>
                <option value="M11">M11: Invoices</option>
                <option value="M12">M12: Weapons</option>
              </select>

              <button
                onClick={fetchMetrics}
                className="px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md"
              >
                Filter
              </button>
            </div>

            <div className="text-xs text-gray-500">
              Total Central Metrics: <strong>{metrics.length}</strong> (Fixed M01 &ndash; M81)
            </div>
          </div>

          {/* Split Pane: Metric List + Detail Drawer */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Metric List */}
            <div className="lg:col-span-2 bg-white border border-gray-200 rounded-md shadow-xs divide-y divide-gray-100 max-h-[700px] overflow-y-auto">
              {metrics.length > 0 ? (
                metrics.map((m) => {
                  const isSelected = selectedMetric?.metric_id === m.metric_id;
                  return (
                    <div
                      key={m.metric_id}
                      onClick={() => handleSelectMetric(m)}
                      className={`p-4 hover:bg-slate-50 cursor-pointer transition flex items-start justify-between ${
                        isSelected ? 'bg-slate-100 border-l-4 border-slate-900' : ''
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-bold px-2 py-0.5 bg-slate-200 text-slate-800 rounded-md">
                            {m.metric_id}
                          </span>
                          <span className="font-semibold text-sm text-gray-900">{m.name}</span>
                          <span className="text-[11px] px-2 py-0.5 rounded-md bg-gray-100 text-gray-600">
                            v{m.current_version}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600 line-clamp-1">{m.definition}</p>
                        <div className="flex items-center space-x-3 text-[11px] text-gray-500">
                          <span>Module: <strong>{m.source_module}</strong></span>
                          <span>Unit: <strong>{m.unit}</strong></span>
                          <span>Visibility: <strong>{m.visibility}</strong></span>
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-400 mt-2 flex-shrink-0" />
                    </div>
                  );
                })
              ) : (
                <div className="p-8 text-center text-gray-400">No metric definitions found.</div>
              )}
            </div>

            {/* Metric Detail Card */}
            <div className="bg-white border border-gray-200 rounded-md shadow-xs p-5 space-y-4">
              {selectedMetric ? (
                <>
                  <div className="flex items-start justify-between border-b border-gray-200 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-sm font-bold text-slate-900">
                          {selectedMetric.metric_id}
                        </span>
                        <h3 className="font-bold text-base text-gray-900">{selectedMetric.name}</h3>
                      </div>
                      <span className="text-xs text-gray-500">
                        Version {selectedMetric.current_version} &bull; Module {selectedMetric.source_module}
                      </span>
                    </div>

                    {isAdmin && (
                      <button
                        onClick={() => {
                          setProposeFormula(selectedMetric.formula);
                          setShowProposeModal(true);
                        }}
                        className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md flex items-center space-x-1"
                      >
                        <span>Propose New Version</span>
                      </button>
                    )}
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="font-semibold text-gray-700">Official Definition:</span>
                      <p className="text-gray-600 mt-0.5">{selectedMetric.definition}</p>
                    </div>

                    <div>
                      <span className="font-semibold text-gray-700">Authoritative Formula:</span>
                      <pre className="p-2 bg-gray-50 border border-gray-200 rounded-md text-[11px] text-slate-800 font-mono mt-0.5 overflow-x-auto">
                        {selectedMetric.formula}
                      </pre>
                    </div>

                    {selectedMetric.numerator_desc && (
                      <div>
                        <span className="font-semibold text-gray-700">Numerator:</span>
                        <p className="text-gray-600 mt-0.5">{selectedMetric.numerator_desc}</p>
                      </div>
                    )}

                    {selectedMetric.denominator_desc && (
                      <div>
                        <span className="font-semibold text-gray-700">Denominator:</span>
                        <p className="text-gray-600 mt-0.5">{selectedMetric.denominator_desc}</p>
                      </div>
                    )}

                    <div>
                      <span className="font-semibold text-gray-700">Source Fields:</span>
                      <p className="text-gray-600 mt-0.5">{selectedMetric.source_fields}</p>
                    </div>

                    <div>
                      <span className="font-semibold text-gray-700">Period Basis:</span>
                      <p className="text-gray-600 mt-0.5">{selectedMetric.period_basis}</p>
                    </div>

                    {selectedMetric.inclusion_rules && (
                      <div>
                        <span className="font-semibold text-gray-700">Inclusion Rules:</span>
                        <p className="text-gray-600 mt-0.5">{selectedMetric.inclusion_rules}</p>
                      </div>
                    )}

                    {selectedMetric.exclusion_rules && (
                      <div>
                        <span className="font-semibold text-gray-700">Exclusion Rules:</span>
                        <p className="text-gray-600 mt-0.5">{selectedMetric.exclusion_rules}</p>
                      </div>
                    )}
                  </div>

                  {/* Version History */}
                  <div className="pt-3 border-t border-gray-200 space-y-2">
                    <span className="text-xs font-semibold text-gray-700">Audit Version History:</span>
                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                      {metricVersions.length > 0 ? (
                        metricVersions.map((v) => (
                          <div key={v.version_number} className="p-2 bg-gray-50 border border-gray-200 rounded-md text-[11px] space-y-0.5">
                            <div className="flex items-center justify-between font-semibold text-gray-800">
                              <span>Version {v.version_number}</span>
                              <span className="text-gray-400">{v.effective_from ? new Date(v.effective_from).toLocaleDateString('en-IN') : 'Initial'}</span>
                            </div>
                            <p className="text-gray-600">Reason: {v.change_reason}</p>
                          </div>
                        ))
                      ) : (
                        <div className="text-[11px] text-gray-400">Current active version is the initial base release (v1).</div>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="py-20 text-center text-gray-400">
                  Select a metric from the catalogue to view its authoritative formula and definitions.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 4: DATA HEALTH PANEL (ADMIN ONLY) */}
      {/* ==================================================================== */}
      {activeTab === 'health' && isAdmin && (
        <div className="space-y-6">
          <div className="bg-white p-5 border border-gray-200 rounded-md shadow-xs space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Data Health & Audit Readiness</h2>
                <p className="text-xs text-gray-500">
                  Systematic verification of source records before operational figures are committed to reports.
                </p>
              </div>

              <button
                onClick={handleRunReconciliation}
                disabled={reconciling}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md flex items-center space-x-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${reconciling ? 'animate-spin' : ''}`} />
                <span>{reconciling ? 'Reconciling...' : 'Run Reconciliation & Repair'}</span>
              </button>
            </div>

            {healthData ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-100">
                <HealthCard
                  title="Attendance Period Integrity"
                  value={healthData.unlocked_attendance_periods}
                  subtext="Unlocked / open attendance periods"
                  isOk={healthData.unlocked_attendance_periods === 0}
                />
                <HealthCard
                  title="Pending Guard Check-In Approvals"
                  value={healthData.pending_attendance_approvals}
                  subtext="Attendance records awaiting supervisor approval"
                  isOk={healthData.pending_attendance_approvals === 0}
                />
                <HealthCard
                  title="Weapons Discrepancies"
                  value={healthData.unresolved_weapon_discrepancies}
                  subtext="Open serial or ammunition mismatches"
                  isOk={healthData.unresolved_weapon_discrepancies === 0}
                />
                <HealthCard
                  title="Manual Attendance Entries"
                  value={healthData.manual_attendance_entries}
                  subtext="Records entered manually by supervisors"
                  neutral
                />
                <HealthCard
                  title="Offline Synced Captures"
                  value={healthData.offline_attendance_captures}
                  subtext="Check-ins recorded offline and synced late"
                  neutral
                />
                <HealthCard
                  title="Snapshot Discrepancies"
                  value={healthData.reconciliation_mismatches}
                  subtext="Stored snapshots out of sync with source tables"
                  isOk={healthData.reconciliation_mismatches === 0}
                />
              </div>
            ) : (
              <div className="py-12 text-center text-gray-400">Loading data health indicators...</div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 5: CLIENT SERVICE SUMMARIES (MODULE 10 INTEGRATION) */}
      {/* ==================================================================== */}
      {activeTab === 'client-summaries' && (
        <div className="space-y-6">
          {/* Header & Generation Form */}
          <div className="bg-white p-5 border border-gray-200 rounded-md shadow-xs space-y-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Client Monthly Service Summaries</h2>
              <p className="text-xs text-gray-500">
                Approved, client-safe operational performance reports released into Module 10 Client Portal.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-3 border-t border-gray-100">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700">Client Organization:</label>
                <select
                  value={summaryClientId}
                  onChange={(e) => setSummaryClientId(e.target.value)}
                  className="w-full text-xs border border-gray-300 rounded-md px-3 py-2 bg-white"
                >
                  <option value="">Select Client...</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>
                      {c.legal_name} ({c.client_code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700">Month:</label>
                <select
                  value={summaryMonth}
                  onChange={(e) => setSummaryMonth(e.target.value)}
                  className="w-full text-xs border border-gray-300 rounded-md px-3 py-2 bg-white"
                >
                  {[
                    'January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'
                  ].map((m, idx) => (
                    <option key={m} value={idx + 1}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700">Year:</label>
                <input
                  type="number"
                  value={summaryYear}
                  onChange={(e) => setSummaryYear(e.target.value)}
                  className="w-full text-xs border border-gray-300 rounded-md px-3 py-1.5"
                />
              </div>

              <div className="flex items-end">
                <button
                  onClick={handleGenerateClientSummary}
                  disabled={loading}
                  className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md"
                >
                  Generate Draft Summary
                </button>
              </div>
            </div>
          </div>

          {/* List of Generated Summaries */}
          <div className="bg-white border border-gray-200 rounded-md overflow-hidden shadow-xs">
            <div className="p-4 border-b border-gray-200 font-semibold text-sm text-gray-800">
              Generated Monthly Summaries
            </div>
            <div className="divide-y divide-gray-100">
              {clientSummaries.length > 0 ? (
                clientSummaries.map((s) => (
                  <div key={s.summary_id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-50">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-sm text-gray-900">
                          {s.client_name || 'Client'} &mdash; {s.month}/{s.year}
                        </span>
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded-md font-semibold ${
                            s.status === 'RELEASED'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : 'bg-amber-100 text-amber-800 border border-amber-300'
                          }`}
                        >
                          {s.status} (v{s.version})
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-x-4 text-xs text-gray-600">
                        <span>Coverage: <strong>{s.summary_data?.coverage_rate || 100}%</strong></span>
                        <span>Attendance: <strong>{s.summary_data?.attendance_rate || 100}%</strong></span>
                        <span>Incidents: <strong>{s.summary_data?.incidents_reported || 0}</strong></span>
                        <span>Panic Alerts: <strong>{s.summary_data?.panic_alerts_real || 0}</strong></span>
                        <span>Test Drills: <strong>{s.summary_data?.panic_drills || 0}</strong></span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      {s.status === 'DRAFT' && isAdmin && (
                        <button
                          onClick={() => handleReleaseSummary(s.summary_id)}
                          className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-medium rounded-md flex items-center space-x-1"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>Release to Client</span>
                        </button>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-gray-400 text-xs">
                  No monthly summaries generated yet.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 6: EXPORT HISTORY AUDIT LOG */}
      {/* ==================================================================== */}
      {activeTab === 'export-history' && (
        <div className="space-y-6">
          <div className="bg-white p-5 border border-gray-200 rounded-md shadow-xs space-y-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Report Export Audit Log</h2>
              <p className="text-xs text-gray-500">
                Tamper-evident log of all generated exports with SHA-256 integrity hashes and operational reasons.
              </p>
            </div>

            <div className="border border-gray-200 rounded-md overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-100 border-b border-gray-200 text-gray-700 font-semibold">
                    <th className="p-3">Report Code</th>
                    <th className="p-3">Format</th>
                    <th className="p-3">Row Count</th>
                    <th className="p-3">Generated At</th>
                    <th className="p-3">Content Hash</th>
                    <th className="p-3">Bulk Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {exportHistory.length > 0 ? (
                    exportHistory.map((h) => (
                      <tr key={h.generation_id} className="hover:bg-gray-50">
                        <td className="p-3 font-semibold text-gray-900">{h.report_code}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded-md bg-gray-100 text-gray-800 font-mono text-[11px]">
                            {h.export_format}
                          </span>
                        </td>
                        <td className="p-3 text-gray-700">{h.row_count}</td>
                        <td className="p-3 text-gray-600">
                          {h.generated_at ? new Date(h.generated_at).toLocaleString('en-IN') : '--'}
                        </td>
                        <td className="p-3 font-mono text-[11px] text-gray-500">
                          {h.content_hash ? `${h.content_hash.substring(0, 16)}...` : '--'}
                        </td>
                        <td className="p-3 text-gray-600">
                          {h.bulk_export_reason || <span className="text-gray-400">Standard (&le;100 rows)</span>}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-gray-400">
                        No report export audit logs recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: SAVE FILTER PRESET */}
      {/* ==================================================================== */}
      {showSavePresetModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-md shadow-lg max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-base text-gray-900">Save Filter Preset</h3>
            <p className="text-xs text-gray-500">
              Save your current filters ({selectedReportCode}, {reportStartDate} to {reportEndDate}) for quick access.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-700">Preset Name:</label>
              <input
                type="text"
                placeholder="e.g. Monthly South Campus Roster"
                value={presetNameInput}
                onChange={(e) => setPresetNameInput(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-md px-3 py-2"
              />
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowSavePresetModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSavePreset}
                disabled={!presetNameInput.trim()}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md"
              >
                Save Preset
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: BULK EXPORT REASON */}
      {/* ==================================================================== */}
      {showBulkExportModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-md shadow-lg max-w-md w-full p-6 space-y-4">
            <div className="flex items-center space-x-2 text-amber-700">
              <AlertTriangle className="w-5 h-5" />
              <h3 className="font-bold text-base text-gray-900">Bulk Export Authorization Required</h3>
            </div>
            <p className="text-xs text-gray-600">
              This report contains <strong>{reportDetail?.row_count} rows</strong>, which exceeds the threshold of 100 rows. Under statutory and agency security guidelines, an operational justification is required before exporting bulk records.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-700">Operational Reason:</label>
              <textarea
                rows={3}
                placeholder="e.g. Quarterly external client compliance audit requested by Director"
                value={bulkReasonInput}
                onChange={(e) => setBulkReasonInput(e.target.value)}
                className="w-full text-xs border border-gray-300 rounded-md p-2"
              />
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowBulkExportModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => executeExport(bulkExportFormat, bulkReasonInput)}
                disabled={!bulkReasonInput.trim()}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md"
              >
                Authorize & Export
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: PROPOSE METRIC VERSION */}
      {/* ==================================================================== */}
      {showProposeModal && selectedMetric && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-md shadow-lg max-w-lg w-full p-6 space-y-4">
            <h3 className="font-bold text-base text-gray-900">
              Propose New Version for {selectedMetric.metric_id}
            </h3>
            <p className="text-xs text-gray-500">
              Proposing a new version increments the metric version number and records the proposal reason in the audit trail without modifying previous historical reports.
            </p>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-700">Formula / Calculation Logic:</label>
              <textarea
                rows={3}
                value={proposeFormula}
                onChange={(e) => setProposeFormula(e.target.value)}
                className="w-full text-xs border border-gray-300 rounded-md p-2 font-mono"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-700">Mandatory Change Reason:</label>
              <textarea
                rows={2}
                placeholder="e.g. Aligned formula to include grace period for late arrivals"
                value={proposeReason}
                onChange={(e) => setProposeReason(e.target.value)}
                className="w-full text-xs border border-gray-300 rounded-md p-2"
              />
            </div>
            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowProposeModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleProposeVersion}
                disabled={!proposeReason.trim()}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md"
              >
                Commit New Version
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Helper KPI Card Component
// ----------------------------------------------------------------------------
function KpiCard({ title, metricId, data, highlight, warning, onClick }) {
  const displayVal = data ? data.display : '--';
  return (
    <div
      onClick={onClick}
      className={`p-4 bg-white border rounded-md shadow-xs transition cursor-pointer hover:border-slate-400 ${
        warning
          ? 'border-amber-300 bg-amber-50/30'
          : highlight
          ? 'border-slate-800'
          : 'border-gray-200'
      }`}
    >
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span className="font-medium">{title}</span>
        <span className="font-mono text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-md">
          {metricId}
        </span>
      </div>
      <div className="text-xl font-bold text-gray-900 tracking-tight">{displayVal}</div>
      <div className="text-[11px] text-gray-400 mt-1 flex items-center justify-between">
        <span>{data?.unit || 'Units'}</span>
        <span className="text-slate-600 hover:underline">Drill down &rarr;</span>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Helper Health Indicator Card Component
// ----------------------------------------------------------------------------
function HealthCard({ title, value, subtext, isOk, neutral }) {
  return (
    <div className="p-4 bg-white border border-gray-200 rounded-md shadow-xs space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-700">{title}</span>
        {!neutral && (
          <span
            className={`w-2 h-2 rounded-full ${
              isOk ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'
            }`}
          />
        )}
      </div>
      <div className="text-2xl font-bold text-gray-900">{value !== undefined ? value : '--'}</div>
      <p className="text-[11px] text-gray-500">{subtext}</p>
    </div>
  );
}

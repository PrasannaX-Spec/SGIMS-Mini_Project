import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Shield,
  ShieldCheck,
  AlertTriangle,
  Clock,
  PhoneOff,
  Bell,
  BellRing,
  Users,
  Search,
  Filter,
  RefreshCw,
  MapPin,
  Smartphone,
  Battery,
  BatteryCharging,
  Wifi,
  WifiOff,
  Navigation,
  CheckCircle2,
  AlertOctagon,
  Eye,
  Sliders,
  Send,
  Play,
  Pause,
  RotateCcw,
  History,
  X,
  Check,
  ChevronRight,
  Info,
  Calendar,
  Layers,
  ArrowRight
} from 'lucide-react';
import { monitoringApi, masterApi } from '../api';

export default function LiveMonitoringScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isSupervisor = currentUser?.role === 'SUPERVISOR';

  // Navigation Tabs
  const [activeTab, setActiveTab] = useState('board'); // 'map' | 'board' | 'alerts' | 'sites' | 'trail'

  // Data states
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(new Date());

  const [metrics, setMetrics] = useState({
    total_monitored: 0,
    on_duty_site: 0,
    on_duty_outside: 0,
    stale_count: 0,
    no_contact_count: 0,
    active_alerts_count: 0
  });

  const [guards, setGuards] = useState([]);
  const [sites, setSites] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedSiteOverview, setSelectedSiteOverview] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSiteFilter, setSelectedSiteFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [alertsOnly, setAlertsOnly] = useState(false);
  const [alertStateFilter, setAlertStateFilter] = useState('ACTIVE');

  // Selected guard for detail drawer
  const [selectedGuardId, setSelectedGuardId] = useState(null);
  const [guardDetail, setGuardDetail] = useState(null);
  const [guardDetailLoading, setGuardDetailLoading] = useState(false);

  // Trail replay states
  const [trailGuardId, setTrailGuardId] = useState(null);
  const [trailPoints, setTrailPoints] = useState([]);
  const [trailLoading, setTrailLoading] = useState(false);
  const [trailPlaying, setTrailPlaying] = useState(false);
  const [trailIndex, setTrailIndex] = useState(0);

  // Modals
  const [resolveModalAlert, setResolveModalAlert] = useState(null);
  const [resolveNote, setResolveNote] = useState('');
  const [dismissModalAlert, setDismissModalAlert] = useState(null);
  const [dismissReason, setDismissReason] = useState('');
  const [pingModalGuard, setPingModalGuard] = useState(null);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [configData, setConfigData] = useState(null);
  const [historicalModalGuard, setHistoricalModalGuard] = useState(null);
  const [historicalStartDate, setHistoricalStartDate] = useState('');
  const [historicalEndDate, setHistoricalEndDate] = useState('');

  // Map viewport state
  const [mapScale, setMapScale] = useState(1);
  const [mapOffset, setMapOffset] = useState({ x: 0, y: 0 });

  // Initial load
  useEffect(() => {
    fetchSites();
    loadDashboardData();
  }, [selectedSiteFilter, statusFilter, alertsOnly]);

  // Auto-refresh interval (every 30 seconds if enabled)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadDashboardData(false);
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, selectedSiteFilter, statusFilter, alertsOnly]);

  // Trail animation playback
  useEffect(() => {
    if (!trailPlaying || trailPoints.length === 0) return;
    const timer = setInterval(() => {
      setTrailIndex((prev) => {
        if (prev >= trailPoints.length - 1) {
          setTrailPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1200);
    return () => clearInterval(timer);
  }, [trailPlaying, trailPoints]);

  const fetchSites = async () => {
    try {
      const res = await masterApi.getSites();
      setSites(res.data?.results || res.data || []);
    } catch (err) {
      console.error('Failed to load sites:', err);
    }
  };

  const loadDashboardData = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setRefreshing(true);
    try {
      const params = {};
      if (selectedSiteFilter) params.site_id = selectedSiteFilter;
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (alertsOnly) params.has_alert = 'true';
      if (searchQuery) params.search = searchQuery;

      // Parallel fetch board and alerts
      const [boardRes, alertRes] = await Promise.all([
        monitoringApi.getStatusBoard(params),
        monitoringApi.getAlerts({ state: alertStateFilter })
      ]);

      if (boardRes.data?.metrics) {
        setMetrics(boardRes.data.metrics);
      }
      setGuards(boardRes.data?.results || []);
      setAlerts(alertRes.data?.results || []);
      setLastRefreshedAt(new Date());
    } catch (err) {
      console.error('Error fetching live monitoring data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const openGuardDetail = async (guardId) => {
    setSelectedGuardId(guardId);
    setGuardDetailLoading(true);
    try {
      const res = await monitoringApi.getGuardDetail(guardId);
      setGuardDetail(res.data);
    } catch (err) {
      console.error('Failed to load guard detail:', err);
    } finally {
      setGuardDetailLoading(false);
    }
  };

  const loadTrail = async (guardId) => {
    setTrailGuardId(guardId);
    setActiveTab('trail');
    setTrailLoading(true);
    setTrailPoints([]);
    setTrailIndex(0);
    setTrailPlaying(false);
    try {
      const res = await monitoringApi.getGuardTrail(guardId);
      setTrailPoints(res.data?.points || []);
      if ((res.data?.points || []).length > 0) {
        setTrailIndex(res.data.points.length - 1);
      }
    } catch (err) {
      console.error('Failed to load trail points:', err);
    } finally {
      setTrailLoading(false);
    }
  };

  const handleAcknowledgeAlert = async (alertId) => {
    try {
      await monitoringApi.acknowledgeAlert(alertId);
      loadDashboardData(false);
    } catch (err) {
      alert('Failed to acknowledge alert: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleResolveAlert = async () => {
    if (!resolveNote.trim()) {
      alert('Resolution note is required.');
      return;
    }
    try {
      await monitoringApi.resolveAlert(resolveModalAlert.alert_id, { note: resolveNote });
      setResolveModalAlert(null);
      setResolveNote('');
      loadDashboardData(false);
    } catch (err) {
      alert('Failed to resolve alert: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDismissAlert = async () => {
    if (!dismissReason.trim()) {
      alert('Dismissal reason is required.');
      return;
    }
    try {
      await monitoringApi.dismissAlert(dismissModalAlert.alert_id, { reason: dismissReason });
      setDismissModalAlert(null);
      setDismissReason('');
      loadDashboardData(false);
    } catch (err) {
      alert('Failed to dismiss alert: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleSendPing = async (dutyId) => {
    try {
      await monitoringApi.sendPing({ duty_id: dutyId });
      alert('Check-on-you ping sent to guard device.');
      setPingModalGuard(null);
      if (selectedGuardId) openGuardDetail(selectedGuardId);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to send ping.');
    }
  };

  const openConfigModal = async () => {
    try {
      const res = await monitoringApi.getConfig();
      setConfigData(res.data);
      setConfigModalOpen(true);
    } catch (err) {
      alert('Failed to load tracking configuration: ' + (err.response?.data?.detail || err.message));
    }
  };

  const saveConfig = async () => {
    try {
      await monitoringApi.updateConfig(configData.configuration);
      alert('Tracking configuration updated successfully.');
      setConfigModalOpen(false);
    } catch (err) {
      alert('Failed to save config: ' + (err.response?.data?.detail || err.message));
    }
  };

  const loadSiteOverview = async (siteId) => {
    try {
      const res = await monitoringApi.getSiteOverview(siteId);
      setSelectedSiteOverview(res.data);
    } catch (err) {
      console.error('Failed to load site overview:', err);
    }
  };

  // Helper for status badge presentation
  const renderStatusBadge = (status, hasAlert) => {
    switch (status) {
      case 'on_duty_at_site':
        return (
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 ${hasAlert ? 'ring-2 ring-red-500' : ''}`}>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            On Duty (At Site)
          </span>
        );
      case 'on_duty_outside_site':
        return (
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-300 ${hasAlert ? 'ring-2 ring-red-500' : ''}`}>
            <span className="w-2 h-2 rotate-45 bg-amber-500"></span>
            Outside Geofence
          </span>
        );
      case 'stale':
        return (
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-yellow-50 text-yellow-800 border border-yellow-300 ${hasAlert ? 'ring-2 ring-red-500' : ''}`}>
            <Clock className="w-3.5 h-3.5 text-yellow-600" />
            Signal Stale (&gt;10m)
          </span>
        );
      case 'no_contact':
        return (
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-300 ${hasAlert ? 'ring-2 ring-red-500' : ''}`}>
            <PhoneOff className="w-3.5 h-3.5 text-rose-600" />
            No Contact (&gt;20m)
          </span>
        );
      case 'off_duty':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-gray-100 text-gray-600 border border-gray-200">
            Off Duty
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-300">
            {status || 'Unknown'}
          </span>
        );
    }
  };

  // Helper for battery presentation
  const renderBattery = (percent, charging) => {
    if (percent === null || percent === undefined) {
      return <span className="text-gray-400 text-xs">-</span>;
    }
    const color = percent <= 15 ? 'text-red-600' : percent <= 30 ? 'text-amber-600' : 'text-emerald-600';
    return (
      <span className={`inline-flex items-center gap-1 font-mono text-xs ${color}`}>
        {charging ? <BatteryCharging className="w-4 h-4 text-emerald-500" /> : <Battery className="w-4 h-4" />}
        {percent}%
      </span>
    );
  };

  // Helper for network presentation
  const renderNetwork = (net) => {
    if (!net || net === 'NONE') {
      return (
        <span className="inline-flex items-center gap-1 text-xs text-red-500" title="No Data Network">
          <WifiOff className="w-3.5 h-3.5" /> None
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-xs text-gray-700 font-mono" title={net}>
        <Wifi className="w-3.5 h-3.5 text-blue-500" /> {net}
      </span>
    );
  };

  // Format captured timestamp age
  const formatAge = (dateStr) => {
    if (!dateStr) return 'Never';
    const now = new Date();
    const then = new Date(dateStr);
    const diffSec = Math.floor((now - then) / 1000);
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    return `${diffHr}h ago`;
  };

  // Filter guards in table
  const filteredGuards = guards.filter((g) => {
    if (selectedSiteFilter && g.site_id !== selectedSiteFilter) return false;
    if (statusFilter !== 'ALL' && g.primary_status !== statusFilter) return false;
    if (alertsOnly && !g.has_active_alert) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = g.employee_name?.toLowerCase().includes(q);
      const matchCode = g.employee_code?.toLowerCase().includes(q);
      const matchSite = g.site_name?.toLowerCase().includes(q);
      if (!matchName && !matchCode && !matchSite) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Header & Operational Banner */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-50 text-indigo-700 rounded-lg">
                <Activity className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Live Guard Monitoring</h1>
                <p className="text-sm text-gray-500">
                  Real-time operational status, duty-time geofence compliance, and safety alerts.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-md text-xs text-gray-600">
              <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-500 animate-ping' : 'bg-gray-400'}`}></span>
              <span>Updated: {lastRefreshedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </div>

            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-3 py-2 text-xs font-medium rounded-md border ${
                autoRefresh
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                  : 'bg-gray-100 text-gray-700 border-gray-300'
              }`}
            >
              {autoRefresh ? 'Auto 30s: ON' : 'Auto: OFF'}
            </button>

            <button
              onClick={() => loadDashboardData(false)}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-white text-gray-700 text-sm font-medium border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>

            {isAdmin && (
              <button
                onClick={openConfigModal}
                className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-800 text-white text-sm font-medium rounded-md hover:bg-slate-900"
              >
                <Sliders className="w-4 h-4" />
                Config
              </button>
            )}
          </div>
        </div>

        {/* Top Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-5">
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <div className="text-xs text-slate-500 font-medium">Monitored Guards</div>
            <div className="text-2xl font-bold text-slate-900 mt-1">{metrics.total_monitored}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">Active duty shifts</div>
          </div>

          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
            <div className="text-xs text-emerald-700 font-medium flex items-center justify-between">
              <span>On Duty (At Site)</span>
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-2xl font-bold text-emerald-900 mt-1">{metrics.on_duty_site}</div>
            <div className="text-[11px] text-emerald-600 mt-0.5">Inside boundary</div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <div className="text-xs text-amber-700 font-medium flex items-center justify-between">
              <span>Outside Geofence</span>
              <AlertTriangle className="w-4 h-4 text-amber-600" />
            </div>
            <div className="text-2xl font-bold text-amber-900 mt-1">{metrics.on_duty_outside}</div>
            <div className="text-[11px] text-amber-600 mt-0.5">&gt; 3 debounced fixes</div>
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
            <div className="text-xs text-yellow-800 font-medium flex items-center justify-between">
              <span>Signal Stale</span>
              <Clock className="w-4 h-4 text-yellow-600" />
            </div>
            <div className="text-2xl font-bold text-yellow-900 mt-1">{metrics.stale_count}</div>
            <div className="text-[11px] text-yellow-700 mt-0.5">&gt; 10 min without GPS</div>
          </div>

          <div className="bg-rose-50 border border-rose-200 rounded-lg p-3">
            <div className="text-xs text-rose-700 font-medium flex items-center justify-between">
              <span>No Contact</span>
              <PhoneOff className="w-4 h-4 text-rose-600" />
            </div>
            <div className="text-2xl font-bold text-rose-900 mt-1">{metrics.no_contact_count}</div>
            <div className="text-[11px] text-rose-600 mt-0.5">&gt; 20 min no telemetry</div>
          </div>

          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <div className="text-xs text-red-700 font-medium flex items-center justify-between">
              <span>Active Alerts</span>
              <BellRing className="w-4 h-4 text-red-600 animate-bounce" />
            </div>
            <div className="text-2xl font-bold text-red-900 mt-1">{metrics.active_alerts_count}</div>
            <div className="text-[11px] text-red-600 mt-0.5">Requires attention</div>
          </div>
        </div>
      </div>

      {/* Main View Tabs */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 bg-gray-50/50 px-4 flex flex-wrap items-center justify-between gap-3">
          <nav className="flex space-x-1" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('board')}
              className={`py-3 px-4 text-sm font-medium border-b-2 flex items-center gap-2 ${
                activeTab === 'board'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Users className="w-4 h-4" />
              Status Board
              <span className="ml-1.5 px-2 py-0.5 bg-gray-200 text-gray-700 rounded-full text-xs">
                {filteredGuards.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('map')}
              className={`py-3 px-4 text-sm font-medium border-b-2 flex items-center gap-2 ${
                activeTab === 'map'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <MapPin className="w-4 h-4" />
              Live Radar Map
            </button>

            <button
              onClick={() => setActiveTab('alerts')}
              className={`py-3 px-4 text-sm font-medium border-b-2 flex items-center gap-2 ${
                activeTab === 'alerts'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Bell className="w-4 h-4" />
              Monitoring Alerts
              {alerts.length > 0 && (
                <span className="ml-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                  {alerts.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('sites')}
              className={`py-3 px-4 text-sm font-medium border-b-2 flex items-center gap-2 ${
                activeTab === 'sites'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Shield className="w-4 h-4" />
              Site Headcount
            </button>

            {trailGuardId && (
              <button
                onClick={() => setActiveTab('trail')}
                className={`py-3 px-4 text-sm font-medium border-b-2 flex items-center gap-2 ${
                  activeTab === 'trail'
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Navigation className="w-4 h-4" />
                Trail Replay
              </button>
            )}
          </nav>

          {/* Quick Filters */}
          <div className="flex flex-wrap items-center gap-2 py-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search guard or site..."
                className="pl-9 pr-3 py-1.5 text-xs border border-gray-300 rounded-md focus:ring-1 focus:ring-indigo-500 w-44"
              />
            </div>

            <select
              value={selectedSiteFilter}
              onChange={(e) => setSelectedSiteFilter(e.target.value)}
              className="text-xs border border-gray-300 rounded-md py-1.5 px-2 bg-white"
            >
              <option value="">All Sites</option>
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.site_name}
                </option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-gray-300 rounded-md py-1.5 px-2 bg-white"
            >
              <option value="ALL">All Statuses</option>
              <option value="on_duty_at_site">On Duty (At Site)</option>
              <option value="on_duty_outside_site">Outside Geofence</option>
              <option value="stale">Signal Stale</option>
              <option value="no_contact">No Contact</option>
              <option value="off_duty">Off Duty</option>
            </select>

            <label className="flex items-center gap-1.5 text-xs text-gray-700 bg-white border border-gray-300 px-2.5 py-1.5 rounded-md cursor-pointer select-none">
              <input
                type="checkbox"
                checked={alertsOnly}
                onChange={(e) => setAlertsOnly(e.target.checked)}
                className="rounded border-gray-300 text-red-600 focus:ring-red-500 h-3.5 w-3.5"
              />
              <span className="font-medium text-red-700">Alerts Only</span>
            </label>
          </div>
        </div>

        {/* Tab Content: Status Board */}
        {activeTab === 'board' && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Guard</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Site & Shift</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Operational Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Geofence & Accuracy</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Device Health</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Last Signal</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {loading ? (
                  <tr>
                    <td colSpan="7" className="px-4 py-8 text-center text-sm text-gray-500">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
                      Loading live monitoring stream...
                    </td>
                  </tr>
                ) : filteredGuards.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-4 py-8 text-center text-sm text-gray-500">
                      No guards match the selected filters.
                    </td>
                  </tr>
                ) : (
                  filteredGuards.map((g) => (
                    <tr key={g.status_id} className="hover:bg-gray-50/80 transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center font-bold text-slate-700 text-xs">
                            {g.employee_name?.slice(0, 2).toUpperCase() || 'GD'}
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-gray-900">{g.employee_name}</div>
                            <div className="text-xs text-gray-500 font-mono">{g.employee_code}</div>
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{g.site_name || '-'}</div>
                        <div className="text-xs text-gray-500">{g.shift_name || 'General Shift'}</div>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          {renderStatusBadge(g.primary_status, g.has_active_alert)}
                          {g.has_active_alert && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 uppercase tracking-wider">
                              Alert
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-xs text-gray-900">
                          {g.accuracy_m ? (
                            <span className="font-mono">±{Math.round(g.accuracy_m)}m</span>
                          ) : (
                            <span className="text-gray-400">No GPS Fix</span>
                          )}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          {g.site_latitude && g.site_longitude ? `Radius: ${g.geofence_radius || 100}m` : 'Geofence pending'}
                        </div>
                        {g.mock_location && (
                          <div className="text-[10px] text-red-600 font-bold flex items-center gap-0.5 mt-0.5">
                            <AlertOctagon className="w-3 h-3" /> Mock GPS Flagged
                          </div>
                        )}
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          {renderBattery(g.battery_percent, g.charging_state)}
                          {renderNetwork(g.network_type)}
                        </div>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-xs font-medium text-gray-900">
                          {formatAge(g.last_captured_at || g.updated_at)}
                        </div>
                        <div className="text-[11px] text-gray-500">
                          {g.last_captured_at
                            ? new Date(g.last_captured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                            : '-'}
                        </div>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap text-right text-xs font-medium space-x-2">
                        <button
                          onClick={() => setPingModalGuard(g)}
                          title="Send Check-on-You Ping"
                          className="px-2.5 py-1 text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300 inline-flex items-center gap-1"
                        >
                          <Send className="w-3 h-3" /> Ping
                        </button>

                        <button
                          onClick={() => loadTrail(g.employee_id)}
                          title="View Today's Duty Trail"
                          className="px-2.5 py-1 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded border border-indigo-200 inline-flex items-center gap-1"
                        >
                          <Navigation className="w-3 h-3" /> Trail
                        </button>

                        <button
                          onClick={() => openGuardDetail(g.employee_id)}
                          className="px-2.5 py-1 text-gray-700 bg-white hover:bg-gray-50 rounded border border-gray-300 inline-flex items-center gap-1"
                        >
                          <Eye className="w-3 h-3" /> Inspect
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab Content: Live Radar Map (SVG Visualization) */}
        {activeTab === 'map' && (
          <div className="p-4">
            <div className="flex items-center justify-between mb-3 text-xs text-gray-500">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-emerald-500"></span> On Duty (At Site)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rotate-45 bg-amber-500"></span> Outside Geofence
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-b-[10px] border-b-yellow-500"></span> Signal Stale
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 bg-rose-600 rounded-sm"></span> No Contact
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full border-2 border-red-600 animate-ping"></span> Active Alert
                </span>
              </div>
              <div>
                <span>Showing {filteredGuards.length} guards on radar grid</span>
              </div>
            </div>

            {/* Radar Canvas Container */}
            <div className="relative bg-slate-950 rounded-xl overflow-hidden border border-slate-800 h-[540px] flex items-center justify-center">
              {/* Radar concentric sweep circles */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                <defs>
                  <radialGradient id="radarSweep" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#0284c7" stopOpacity="0.08" />
                    <stop offset="100%" stopColor="#0f172a" stopOpacity="0.01" />
                  </radialGradient>
                </defs>
                <rect width="100%" height="100%" fill="url(#radarSweep)" />
                <circle cx="50%" cy="50%" r="100" stroke="#334155" strokeWidth="1" strokeDasharray="4 4" fill="none" />
                <circle cx="50%" cy="50%" r="180" stroke="#334155" strokeWidth="1" strokeDasharray="4 4" fill="none" />
                <circle cx="50%" cy="50%" r="260" stroke="#1e293b" strokeWidth="1" fill="none" />
                <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#1e293b" strokeWidth="1" />
                <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#1e293b" strokeWidth="1" />
              </svg>

              {/* Guard markers plotted on radar */}
              <div className="relative w-full h-full flex items-center justify-center">
                {filteredGuards.map((g, idx) => {
                  // Calculate dynamic visual placement relative to center radar
                  // Deterministic pseudo-angle based on guard status or coordinates
                  const angle = (idx * (360 / Math.max(filteredGuards.length, 1)) * Math.PI) / 180;
                  const dist = g.primary_status === 'on_duty_at_site' ? 70 + (idx % 3) * 20 : 160 + (idx % 2) * 40;
                  const x = Math.cos(angle) * dist;
                  const y = Math.sin(angle) * dist;

                  return (
                    <div
                      key={g.status_id}
                      onClick={() => openGuardDetail(g.employee_id)}
                      style={{
                        transform: `translate(${x}px, ${y}px)`
                      }}
                      className="absolute group cursor-pointer transition-all duration-300 hover:scale-125 z-10"
                    >
                      {/* Marker Shape based on Status */}
                      <div className="relative flex items-center justify-center">
                        {g.has_active_alert && (
                          <div className="absolute -inset-2 rounded-full border-2 border-red-500 animate-ping opacity-75"></div>
                        )}

                        {g.primary_status === 'on_duty_at_site' && (
                          <div className="w-4 h-4 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50 border-2 border-white"></div>
                        )}

                        {g.primary_status === 'on_duty_outside_site' && (
                          <div className="w-4 h-4 rotate-45 bg-amber-500 shadow-lg shadow-amber-500/50 border-2 border-white"></div>
                        )}

                        {g.primary_status === 'stale' && (
                          <div className="w-0 h-0 border-l-[7px] border-l-transparent border-r-[7px] border-r-transparent border-b-[13px] border-b-yellow-400 filter drop-shadow"></div>
                        )}

                        {g.primary_status === 'no_contact' && (
                          <div className="w-4 h-4 bg-rose-600 rounded-sm shadow-lg shadow-rose-600/50 border-2 border-white"></div>
                        )}

                        {g.primary_status === 'off_duty' && (
                          <div className="w-3 h-3 rounded-full bg-gray-500 border border-gray-300"></div>
                        )}
                      </div>

                      {/* Tooltip on hover */}
                      <div className="hidden group-hover:block absolute bottom-6 left-1/2 -translate-x-1/2 w-48 bg-slate-900 text-white rounded-lg p-2.5 shadow-2xl border border-slate-700 text-xs pointer-events-none z-50">
                        <div className="font-bold text-white">{g.employee_name}</div>
                        <div className="text-slate-400 font-mono text-[10px]">{g.employee_code}</div>
                        <div className="text-slate-300 mt-1">{g.site_name}</div>
                        <div className="mt-1 flex items-center justify-between text-[11px] border-t border-slate-800 pt-1">
                          <span className="text-emerald-400 font-semibold">{g.display_status || g.primary_status}</span>
                          <span className="text-slate-400">{formatAge(g.last_captured_at)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Center Station / HQ icon */}
                <div className="absolute z-0 flex flex-col items-center">
                  <div className="w-10 h-10 rounded-full bg-slate-800 border-2 border-indigo-400 flex items-center justify-center text-indigo-300 shadow-lg">
                    <Shield className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] font-bold text-slate-400 mt-1 uppercase tracking-wider">Site Center</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab Content: Monitoring Alerts */}
        {activeTab === 'alerts' && (
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Filter State:</span>
                {['ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'FALSE_ALARM'].map((st) => (
                  <button
                    key={st}
                    onClick={() => {
                      setAlertStateFilter(st);
                      monitoringApi.getAlerts({ state: st }).then((res) => setAlerts(res.data?.results || []));
                    }}
                    className={`px-3 py-1 text-xs font-medium rounded-md border ${
                      alertStateFilter === st
                        ? 'bg-slate-900 text-white border-slate-900'
                        : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
              <span className="text-xs text-gray-500">{alerts.length} alerts in this view</span>
            </div>

            {alerts.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                <h3 className="text-sm font-semibold text-gray-900">No {alertStateFilter.toLowerCase()} alerts</h3>
                <p className="text-xs text-gray-500 mt-0.5">All monitored guard deployments are within expected boundaries.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {alerts.map((alt) => {
                  const isCritical = alt.severity === 'CRITICAL';
                  return (
                    <div
                      key={alt.alert_id}
                      className={`p-4 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                        isCritical ? 'bg-red-50/50 border-red-200' : 'bg-white border-gray-200'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg mt-0.5 ${isCritical ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                          <AlertTriangle className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-gray-900">{alt.title}</span>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                isCritical ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {alt.severity}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-700 font-mono">
                              {alt.rule_code}
                            </span>
                          </div>
                          <p className="text-xs text-gray-600 mt-1">{alt.description}</p>
                          <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 mt-2">
                            <span>Guard: <strong className="text-gray-800">{alt.employee_name}</strong> ({alt.employee_code})</span>
                            <span>Site: <strong className="text-gray-800">{alt.site_name}</strong></span>
                            <span>Raised: <strong>{new Date(alt.raised_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong></span>
                            {alt.escalated_to_admin_at && (
                              <span className="text-red-700 font-semibold flex items-center gap-1">
                                <AlertOctagon className="w-3.5 h-3.5" /> Escalated to Admin
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Alert Actions */}
                      <div className="flex items-center gap-2 self-end md:self-center">
                        {alt.state === 'ACTIVE' && (
                          <button
                            onClick={() => handleAcknowledgeAlert(alt.alert_id)}
                            className="px-3 py-1.5 bg-white text-gray-800 border border-gray-300 hover:bg-gray-50 text-xs font-semibold rounded-md shadow-sm"
                          >
                            Acknowledge
                          </button>
                        )}

                        {(alt.state === 'ACTIVE' || alt.state === 'ACKNOWLEDGED') && (
                          <>
                            <button
                              onClick={() => {
                                setResolveModalAlert(alt);
                                setResolveNote('');
                              }}
                              className="px-3 py-1.5 bg-emerald-600 text-white hover:bg-emerald-700 text-xs font-semibold rounded-md shadow-sm"
                            >
                              Resolve
                            </button>
                            <button
                              onClick={() => {
                                setDismissModalAlert(alt);
                                setDismissReason('');
                              }}
                              className="px-3 py-1.5 bg-gray-100 text-gray-700 hover:bg-gray-200 text-xs font-semibold rounded-md border border-gray-300"
                            >
                              False Alarm
                            </button>
                          </>
                        )}

                        {alt.state === 'RESOLVED' && (
                          <span className="text-xs text-emerald-700 font-medium flex items-center gap-1 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                            <Check className="w-3.5 h-3.5" /> Resolved ({alt.resolved_by_name || 'System'})
                          </span>
                        )}

                        {alt.state === 'FALSE_ALARM' && (
                          <span className="text-xs text-gray-500 italic bg-gray-100 px-2.5 py-1 rounded border">
                            Dismissed as false alarm
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab Content: Site Headcount & Overview */}
        {activeTab === 'sites' && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sites.map((st) => {
                const siteGuards = guards.filter((g) => g.site_id === st.site_id);
                const onDutySite = siteGuards.filter((g) => g.primary_status === 'on_duty_at_site').length;
                const outsideSite = siteGuards.filter((g) => g.primary_status === 'on_duty_outside_site').length;
                const alertsAtSite = alerts.filter((a) => a.site_id === st.site_id && a.state === 'ACTIVE').length;

                return (
                  <div key={st.site_id} className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-bold text-gray-900 text-base">{st.site_name}</h3>
                        <p className="text-xs text-gray-500 font-mono mt-0.5">{st.site_code}</p>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                        Radius: {st.geofence_radius_meters || 100}m
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 mt-4 text-center border-t border-b border-gray-100 py-2.5">
                      <div>
                        <div className="text-lg font-bold text-emerald-600">{onDutySite}</div>
                        <div className="text-[10px] text-gray-500 font-medium">Inside</div>
                      </div>
                      <div>
                        <div className="text-lg font-bold text-amber-600">{outsideSite}</div>
                        <div className="text-[10px] text-gray-500 font-medium">Outside</div>
                      </div>
                      <div>
                        <div className={`text-lg font-bold ${alertsAtSite > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                          {alertsAtSite}
                        </div>
                        <div className="text-[10px] text-gray-500 font-medium">Alerts</div>
                      </div>
                    </div>

                    <div className="mt-4 flex items-center justify-between">
                      <button
                        onClick={() => {
                          setSelectedSiteFilter(st.site_id);
                          setActiveTab('board');
                        }}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1"
                      >
                        View Guards <ArrowRight className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => loadSiteOverview(st.site_id)}
                        className="text-xs text-gray-600 hover:text-gray-900 font-medium"
                      >
                        Duty Breakdown
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Site Overview Detail Modal */}
            {selectedSiteOverview && (
              <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
                <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-5 space-y-4">
                  <div className="flex items-center justify-between border-b pb-3">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{selectedSiteOverview.site_name}</h3>
                      <p className="text-xs text-gray-500">Expected vs Monitored Guard Deployments Today</p>
                    </div>
                    <button onClick={() => setSelectedSiteOverview(null)} className="text-gray-400 hover:text-gray-600">
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {selectedSiteOverview.guards.map((g) => (
                      <div key={g.employee_id} className="p-3 bg-gray-50 rounded-lg flex items-center justify-between text-xs">
                        <div>
                          <div className="font-bold text-gray-900">{g.employee_name} ({g.employee_code})</div>
                          <div className="text-gray-500">{g.shift_name} ({g.start_time?.slice(0, 5)} - {g.end_time?.slice(0, 5)})</div>
                        </div>
                        <div>{renderStatusBadge(g.status, false)}</div>
                      </div>
                    ))}
                  </div>

                  <div className="flex justify-end pt-2 border-t">
                    <button
                      onClick={() => setSelectedSiteOverview(null)}
                      className="px-4 py-2 bg-gray-100 text-gray-700 text-xs font-semibold rounded-md hover:bg-gray-200"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab Content: Trail Replay */}
        {activeTab === 'trail' && (
          <div className="p-4 space-y-4">
            <div className="bg-slate-900 text-white rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold flex items-center gap-2">
                  <Navigation className="w-5 h-5 text-indigo-400" />
                  Today's Duty Movement Trail
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Chronological replay of accepted location fixes for active duty shift.
                </p>
              </div>

              {trailPoints.length > 0 && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setTrailPlaying(!trailPlaying)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-xs font-bold rounded-md hover:bg-indigo-700 shadow"
                  >
                    {trailPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    {trailPlaying ? 'Pause Replay' : 'Play Replay'}
                  </button>

                  <button
                    onClick={() => {
                      setTrailPlaying(false);
                      setTrailIndex(0);
                    }}
                    className="p-2 bg-slate-800 text-slate-300 rounded-md hover:bg-slate-700"
                    title="Reset to beginning"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>

                  <span className="text-xs font-mono text-slate-300">
                    Step {trailIndex + 1} of {trailPoints.length}
                  </span>
                </div>
              )}
            </div>

            {trailLoading ? (
              <div className="text-center py-12 text-sm text-gray-500">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
                Loading breadcrumb duty trail...
              </div>
            ) : trailPoints.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed text-gray-500 text-xs">
                No location breadcrumbs recorded for this duty yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Visual Trail Canvas */}
                <div className="lg:col-span-2 bg-slate-950 rounded-xl p-4 border border-slate-800 h-[420px] flex items-center justify-center relative overflow-hidden">
                  <svg className="absolute inset-0 w-full h-full">
                    {/* Grid lines */}
                    <defs>
                      <pattern id="trailGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" />
                      </pattern>
                    </defs>
                    <rect width="100%" height="100%" fill="url(#trailGrid)" />

                    {/* Polyline connecting points up to trailIndex */}
                    {trailPoints.length > 1 && (
                      <polyline
                        fill="none"
                        stroke="#6366f1"
                        strokeWidth="3"
                        strokeDasharray="6 3"
                        points={trailPoints
                          .slice(0, trailIndex + 1)
                          .map((p, idx) => {
                            const px = 100 + (idx * 50) % 500;
                            const py = 200 + Math.sin(idx * 0.8) * 80;
                            return `${px},${py}`;
                          })
                          .join(' ')}
                      />
                    )}

                    {/* Render active marker point */}
                    {trailPoints[trailIndex] && (
                      <circle
                        cx={100 + (trailIndex * 50) % 500}
                        cy={200 + Math.sin(trailIndex * 0.8) * 80}
                        r="8"
                        fill="#10b981"
                        stroke="#ffffff"
                        strokeWidth="2"
                        className="animate-pulse"
                      />
                    )}
                  </svg>

                  <div className="absolute bottom-4 left-4 bg-slate-900/90 text-white rounded-lg p-3 text-xs border border-slate-700">
                    <div className="font-semibold text-emerald-400">Current Position at Step {trailIndex + 1}</div>
                    <div className="font-mono text-[11px] text-slate-300 mt-1">
                      Lat: {trailPoints[trailIndex]?.latitude}, Lng: {trailPoints[trailIndex]?.longitude}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Captured: {new Date(trailPoints[trailIndex]?.device_captured_at).toLocaleTimeString()}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Accuracy: ±{Math.round(trailPoints[trailIndex]?.accuracy_m || 0)}m | Geofence: {trailPoints[trailIndex]?.geofence_boundary_state}
                    </div>
                  </div>
                </div>

                {/* Waypoint History List */}
                <div className="bg-white rounded-xl border border-gray-200 p-3 h-[420px] overflow-y-auto space-y-2">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Waypoint History</h4>
                  {trailPoints.map((pt, idx) => (
                    <div
                      key={pt.point_id || idx}
                      onClick={() => {
                        setTrailPlaying(false);
                        setTrailIndex(idx);
                      }}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                        idx === trailIndex
                          ? 'bg-indigo-50 border-indigo-300 text-indigo-900 font-semibold'
                          : 'bg-gray-50/50 border-gray-200 hover:bg-gray-100 text-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono">#{idx + 1}</span>
                        <span className="text-[11px] text-gray-500">
                          {new Date(pt.device_captured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-1 text-[11px]">
                        <span className="font-mono text-gray-600">±{Math.round(pt.accuracy_m)}m</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          pt.geofence_boundary_state === 'INSIDE' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                        }`}>
                          {pt.geofence_boundary_state}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Guard Detail Slide-out Drawer */}
      {selectedGuardId && (
        <div className="fixed inset-0 bg-black/40 flex justify-end z-50">
          <div className="bg-white w-full max-w-lg h-full shadow-2xl p-6 overflow-y-auto space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
              <h2 className="text-lg font-bold text-gray-900">Guard Telemetry & Status</h2>
              <button
                onClick={() => {
                  setSelectedGuardId(null);
                  setGuardDetail(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {guardDetailLoading || !guardDetail ? (
              <div className="text-center py-12 text-sm text-gray-500">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
                Loading guard telemetry...
              </div>
            ) : (
              <div className="space-y-6">
                {/* Guard Profile Summary */}
                <div className="flex items-center gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <div className="w-14 h-14 rounded-full bg-slate-200 border-2 border-indigo-400 flex items-center justify-center font-bold text-slate-800 text-lg">
                    {guardDetail.status.employee_name?.slice(0, 2).toUpperCase() || 'GD'}
                  </div>
                  <div className="flex-1">
                    <h3 className="text-base font-bold text-gray-900">{guardDetail.status.employee_name}</h3>
                    <div className="text-xs text-gray-500 font-mono">{guardDetail.status.employee_code}</div>
                    <div className="mt-2 flex items-center gap-2">
                      {renderStatusBadge(guardDetail.status.primary_status, guardDetail.status.has_active_alert)}
                    </div>
                  </div>
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => handleSendPing(guardDetail.status.duty_id)}
                    className="p-3 bg-slate-900 text-white rounded-lg text-xs font-semibold hover:bg-slate-800 flex items-center justify-center gap-2"
                  >
                    <Send className="w-4 h-4 text-indigo-400" /> Check-on-You Ping
                  </button>

                  <button
                    onClick={() => {
                      const empId = guardDetail.status.employee_id;
                      setSelectedGuardId(null);
                      loadTrail(empId);
                    }}
                    className="p-3 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-semibold hover:bg-indigo-100 flex items-center justify-center gap-2"
                  >
                    <Navigation className="w-4 h-4" /> Duty Trail Replay
                  </button>
                </div>

                {/* Telemetry Breakdown */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Device & Telemetry Health</h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-gray-500">Site Assignment</div>
                      <div className="font-semibold text-gray-900 mt-0.5">{guardDetail.status.site_name}</div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-gray-500">Shift Window</div>
                      <div className="font-semibold text-gray-900 mt-0.5">{guardDetail.status.shift_name}</div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-gray-500">GPS Accuracy</div>
                      <div className="font-semibold text-gray-900 mt-0.5 font-mono">
                        {guardDetail.status.accuracy_m ? `±${Math.round(guardDetail.status.accuracy_m)}m` : 'No fix'}
                      </div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-gray-500">Battery & Charging</div>
                      <div className="font-semibold text-gray-900 mt-0.5 flex items-center gap-2">
                        {renderBattery(guardDetail.status.battery_percent, guardDetail.status.charging_state)}
                      </div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-gray-500">Network Type</div>
                      <div className="font-semibold text-gray-900 mt-0.5">
                        {renderNetwork(guardDetail.status.network_type)}
                      </div>
                    </div>

                    <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="text-gray-500">Last Telemetry Fix</div>
                      <div className="font-semibold text-gray-900 mt-0.5">
                        {formatAge(guardDetail.status.last_captured_at)}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Duty Alerts */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Active & Recent Alerts</h4>
                  {guardDetail.alerts.length === 0 ? (
                    <div className="text-xs text-gray-400 bg-gray-50 p-3 rounded-lg border border-dashed">
                      No alerts triggered during this duty.
                    </div>
                  ) : (
                    guardDetail.alerts.map((alt) => (
                      <div key={alt.alert_id} className="p-3 bg-red-50/50 border border-red-200 rounded-lg text-xs space-y-1">
                        <div className="flex items-center justify-between font-bold text-red-900">
                          <span>{alt.title}</span>
                          <span className="text-[10px] uppercase bg-red-100 px-1.5 py-0.5 rounded">{alt.state}</span>
                        </div>
                        <p className="text-gray-600">{alt.description}</p>
                      </div>
                    ))
                  )}
                </div>

                {/* Status Transition History */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Status Transition History</h4>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {guardDetail.history.map((h, idx) => (
                      <div key={h.history_id || idx} className="p-2.5 bg-gray-50 rounded border border-gray-200 text-xs flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-gray-800">{h.old_status || 'start'} → {h.new_status}</span>
                          {h.reason && <p className="text-[11px] text-gray-500 mt-0.5">{h.reason}</p>}
                        </div>
                        <span className="text-[10px] text-gray-400">
                          {new Date(h.changed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Resolve Alert Modal */}
      {resolveModalAlert && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-base font-bold text-gray-900">Resolve Monitoring Alert</h3>
            <p className="text-xs text-gray-600">
              Provide an operational resolution note for <strong>{resolveModalAlert.title}</strong> ({resolveModalAlert.employee_name}).
            </p>
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Mandatory Resolution Note</label>
              <textarea
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
                placeholder="e.g. Contacted guard via radio; guard was escorting visitor to parking bay and has returned inside perimeter."
                rows="3"
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={() => setResolveModalAlert(null)}
                className="px-3 py-1.5 text-xs text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                onClick={handleResolveAlert}
                className="px-4 py-1.5 text-xs text-white bg-emerald-600 hover:bg-emerald-700 font-semibold rounded-md"
              >
                Confirm Resolution
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dismiss Alert as False Alarm Modal */}
      {dismissModalAlert && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-base font-bold text-gray-900">Dismiss as False Alarm</h3>
            <p className="text-xs text-gray-600">
              Provide an audited justification for dismissing <strong>{dismissModalAlert.title}</strong>.
            </p>
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Mandatory Reason</label>
              <textarea
                value={dismissReason}
                onChange={(e) => setDismissReason(e.target.value)}
                placeholder="e.g. High-multipath GPS reflection near metal warehouse wall caused momentary outside fix."
                rows="3"
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-gray-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={() => setDismissModalAlert(null)}
                className="px-3 py-1.5 text-xs text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                onClick={handleDismissAlert}
                className="px-4 py-1.5 text-xs text-white bg-gray-800 hover:bg-gray-900 font-semibold rounded-md"
              >
                Dismiss Alert
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Send Ping Confirmation Modal */}
      {pingModalGuard && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5 space-y-4">
            <h3 className="text-base font-bold text-gray-900">Send Check-on-You Ping</h3>
            <p className="text-xs text-gray-600">
              Dispatch an audible / vibrating safety check to <strong>{pingModalGuard.employee_name}</strong>'s registered mobile device.
            </p>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-800">
              Note: Pings have an operational cooldown of 5 minutes to prevent guard disruption.
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={() => setPingModalGuard(null)}
                className="px-3 py-1.5 text-xs text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                onClick={() => handleSendPing(pingModalGuard.duty_id)}
                className="px-4 py-1.5 text-xs text-white bg-slate-900 hover:bg-slate-800 font-semibold rounded-md"
              >
                Dispatch Ping Now
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Configuration Modal (Admin Only) */}
      {configModalOpen && configData && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-lg font-bold text-gray-900">Live Tracking & Alert Configuration</h3>
              <button onClick={() => setConfigModalOpen(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Normal Stationary Interval (min)</label>
                  <input
                    type="number"
                    value={configData.configuration.normal_update_interval_mins}
                    onChange={(e) =>
                      setConfigData({
                        ...configData,
                        configuration: { ...configData.configuration, normal_update_interval_mins: parseInt(e.target.value) }
                      })
                    }
                    className="w-full border border-gray-300 rounded p-2"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Moving Update Interval (min)</label>
                  <input
                    type="number"
                    value={configData.configuration.moving_update_interval_mins}
                    onChange={(e) =>
                      setConfigData({
                        ...configData,
                        configuration: { ...configData.configuration, moving_update_interval_mins: parseInt(e.target.value) }
                      })
                    }
                    className="w-full border border-gray-300 rounded p-2"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Signal Stale Threshold (min)</label>
                  <input
                    type="number"
                    value={configData.configuration.stale_threshold_mins}
                    onChange={(e) =>
                      setConfigData({
                        ...configData,
                        configuration: { ...configData.configuration, stale_threshold_mins: parseInt(e.target.value) }
                      })
                    }
                    className="w-full border border-gray-300 rounded p-2"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">No Contact Threshold (min)</label>
                  <input
                    type="number"
                    value={configData.configuration.no_contact_threshold_mins}
                    onChange={(e) =>
                      setConfigData({
                        ...configData,
                        configuration: { ...configData.configuration, no_contact_threshold_mins: parseInt(e.target.value) }
                      })
                    }
                    className="w-full border border-gray-300 rounded p-2"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Geofence Debounce Count</label>
                  <input
                    type="number"
                    value={configData.configuration.geofence_debounce_count}
                    onChange={(e) =>
                      setConfigData({
                        ...configData,
                        configuration: { ...configData.configuration, geofence_debounce_count: parseInt(e.target.value) }
                      })
                    }
                    className="w-full border border-gray-300 rounded p-2"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-gray-700 mb-1">Low Accuracy Cutoff (meters)</label>
                  <input
                    type="number"
                    value={configData.configuration.low_accuracy_threshold_meters}
                    onChange={(e) =>
                      setConfigData({
                        ...configData,
                        configuration: { ...configData.configuration, low_accuracy_threshold_meters: parseInt(e.target.value) }
                      })
                    }
                    className="w-full border border-gray-300 rounded p-2"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t">
              <button
                onClick={() => setConfigModalOpen(false)}
                className="px-4 py-2 text-xs text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                onClick={saveConfig}
                className="px-4 py-2 text-xs text-white bg-slate-900 hover:bg-slate-800 font-semibold rounded-md"
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


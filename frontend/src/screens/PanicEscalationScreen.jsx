import React, { useState, useEffect, useRef } from 'react';
import {
  AlertOctagon,
  AlertTriangle,
  Bell,
  BellOff,
  PhoneCall,
  Shield,
  ShieldAlert,
  Clock,
  CheckCircle2,
  XCircle,
  MapPin,
  Battery,
  Wifi,
  User,
  Building2,
  RefreshCw,
  Search,
  Filter,
  FileText,
  Download,
  Send,
  Radio,
  Activity,
  Smartphone,
  ExternalLink,
  ChevronRight,
  Eye,
  Check,
  X,
  PlayCircle,
  HelpCircle,
  AlertCircle
} from 'lucide-react';
import { panicApi, masterDataApi } from '../api';
import Modal from '../components/Modal';

export default function PanicEscalationScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isSupervisor = currentUser?.role === 'SUPERVISOR';
  const isGuard = currentUser?.role === 'GUARD';

  const [activeTab, setActiveTab] = useState('active'); // active, history, config, drills, readiness, client_safe, metrics
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Core Data
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [historyAlerts, setHistoryAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [alertDetailLoading, setAlertDetailLoading] = useState(false);
  const [sites, setSites] = useState([]);
  const [config, setConfig] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [readinessList, setReadinessList] = useState([]);
  const [drills, setDrills] = useState([]);
  const [clientSafeStatus, setClientSafeStatus] = useState(null);
  const [selectedSiteForClient, setSelectedSiteForClient] = useState('');

  // Audio Alarm State
  const [soundEnabled, setSoundEnabled] = useState(true);
  const audioContextRef = useRef(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSite, setFilterSite] = useState('');
  const [filterStage, setFilterStage] = useState('');
  const [includeTests, setIncludeTests] = useState(true);

  // Action Modals
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [triggerForm, setTriggerForm] = useState({
    site_id: '',
    battery_level: 85,
    network_type: '4G',
    latitude: 12.9716,
    longitude: 77.5946,
    accuracy_meters: 15.0,
    test_flag: false
  });
  const [triggerStatusNotice, setTriggerStatusNotice] = useState(null);

  const [showActionModal, setShowActionModal] = useState(false);
  const [actionType, setActionType] = useState('RESPONSE_STARTED');
  const [actionNote, setActionNote] = useState('');
  const [actionPoliceStation, setActionPoliceStation] = useState('');
  const [actionPoliceRef, setActionPoliceRef] = useState('');

  const [showResolveModal, setShowResolveModal] = useState(false);
  const [resolveOutcome, setResolveOutcome] = useState('RESOLVED_ASSISTED');
  const [resolveFindings, setResolveFindings] = useState('');
  const [resolvePreventive, setResolvePreventive] = useState('');

  const [showAdminReviewModal, setShowAdminReviewModal] = useState(false);
  const [adminReviewStatus, setAdminReviewStatus] = useState('CLOSED');
  const [adminReviewNote, setAdminReviewNote] = useState('');

  const [showFalseAlarmModal, setShowFalseAlarmModal] = useState(false);
  const [falseAlarmReason, setFalseAlarmReason] = useState('ACCIDENTAL_BUTTON_PRESS');
  const [falseAlarmNotes, setFalseAlarmNotes] = useState('');

  const [showConfirmFalseAlarmModal, setShowConfirmFalseAlarmModal] = useState(false);
  const [confirmSupervisorNote, setConfirmSupervisorNote] = useState('');

  const [showWelfareModal, setShowWelfareModal] = useState(false);
  const [welfareNote, setWelfareNote] = useState('');

  const [showDrillModal, setShowDrillModal] = useState(false);
  const [drillTitle, setDrillTitle] = useState('');
  const [drillDescription, setDrillDescription] = useState('');
  const [drillSiteId, setDrillSiteId] = useState('');
  const [drillScenario, setDrillScenario] = useState('INTRUSION_SIMULATION');

  // Play audio beep for unacknowledged active alarms
  const playAlarmBeep = () => {
    if (!soundEnabled) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioCtx();
      }
      const ctx = audioContextRef.current;
      if (ctx.state === 'suspended') {
        ctx.resume();
      }
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(880, ctx.currentTime); // A5 note
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
      console.warn('Audio alarm could not play:', e);
    }
  };

  // Fetch initial data & sites
  useEffect(() => {
    fetchSites();
    fetchActiveAlerts();
    fetchConfig();
  }, []);

  // Polling loop for active alerts (every 6 seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      fetchActiveAlerts(false);
    }, 6000);
    return () => clearInterval(timer);
  }, [soundEnabled]);

  const fetchSites = async () => {
    try {
      const res = await masterDataApi.getSites();
      const siteList = res.data?.results || res.data || [];
      setSites(siteList);
      if (siteList.length > 0 && !selectedSiteForClient) {
        setSelectedSiteForClient(siteList[0].site_id);
      }
    } catch (err) {
      console.error('Failed to load sites:', err);
    }
  };

  const fetchActiveAlerts = async (showLoadingState = true) => {
    if (showLoadingState) setLoading(true);
    try {
      const res = await panicApi.getActiveAlerts();
      const data = res.data?.active_alerts || res.data || [];
      setActiveAlerts(data);

      // Check if any unacknowledged active alert exists
      const hasUnacked = data.some(
        (a) => a.alert_status === 'TRIGGERED' || a.alert_status === 'DELIVERING' || a.alert_status === 'ESCALATED'
      );
      if (hasUnacked && soundEnabled) {
        playAlarmBeep();
      }
    } catch (err) {
      console.error('Error fetching active panic alerts:', err);
    } finally {
      if (showLoadingState) setLoading(false);
    }
  };

  const fetchHistoryAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        search: searchQuery || undefined,
        status: filterStatus || undefined,
        site_id: filterSite || undefined,
        stage: filterStage || undefined,
        include_tests: includeTests ? 'true' : 'false'
      };
      const res = await panicApi.getAlerts(params);
      setHistoryAlerts(res.data?.results || res.data || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch panic history');
    } finally {
      setLoading(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await panicApi.getConfig();
      setConfig(res.data);
    } catch (err) {
      console.error('Failed to fetch config:', err);
    }
  };

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await panicApi.getMetrics();
      setMetrics(res.data);
    } catch (err) {
      setError(err.message || 'Failed to fetch metrics');
    } finally {
      setLoading(false);
    }
  };

  const fetchReadiness = async () => {
    setLoading(true);
    try {
      const res = await panicApi.getDeviceReadiness();
      setReadinessList(res.data?.results || res.data || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch device readiness');
    } finally {
      setLoading(false);
    }
  };

  const fetchDrills = async () => {
    setLoading(true);
    try {
      const res = await panicApi.getDrills();
      setDrills(res.data?.results || res.data || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch drills');
    } finally {
      setLoading(false);
    }
  };

  const fetchClientSafe = async (siteId) => {
    if (!siteId) return;
    setLoading(true);
    try {
      const res = await panicApi.getClientSafe(siteId);
      setClientSafeStatus(res.data);
    } catch (err) {
      setError(err.message || 'Failed to fetch client safe status');
    } finally {
      setLoading(false);
    }
  };

  // Switch tabs
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setError(null);
    setSuccessMsg(null);
    if (tab === 'active') fetchActiveAlerts();
    if (tab === 'history') fetchHistoryAlerts();
    if (tab === 'config') fetchConfig();
    if (tab === 'metrics') fetchMetrics();
    if (tab === 'readiness') fetchReadiness();
    if (tab === 'drills') fetchDrills();
    if (tab === 'client_safe') fetchClientSafe(selectedSiteForClient);
  };

  const loadAlertDetail = async (alertId) => {
    setAlertDetailLoading(true);
    try {
      const res = await panicApi.getAlertDetail(alertId);
      setSelectedAlert(res.data);
    } catch (err) {
      setError(err.message || 'Failed to load alert details');
    } finally {
      setAlertDetailLoading(false);
    }
  };

  // Actions
  const handleAcknowledge = async (alertId) => {
    try {
      await panicApi.acknowledgeAlert(alertId, { notes: 'Supervisor acknowledged via web monitor' });
      setSuccessMsg('Alert acknowledged. Repeat audible alarm silenced.');
      fetchActiveAlerts(false);
      if (selectedAlert?.panic_alert_id === alertId) {
        loadAlertDetail(alertId);
      }
    } catch (err) {
      setError(err.message || 'Failed to acknowledge alert');
    }
  };

  const handleSendAreYouSafe = async (alertId) => {
    try {
      await panicApi.sendAreYouSafe(alertId);
      setSuccessMsg('"Are You Safe?" prompt dispatched to guard device.');
      loadAlertDetail(alertId);
    } catch (err) {
      setError(err.message || 'Failed to dispatch safety prompt');
    }
  };

  const handleRecordAction = async () => {
    if (!selectedAlert) return;
    try {
      await panicApi.recordAction(selectedAlert.panic_alert_id, {
        action_type: actionType,
        action_note: actionNote,
        police_station_name: actionPoliceStation || undefined,
        police_reference_number: actionPoliceRef || undefined
      });
      setShowActionModal(false);
      setActionNote('');
      setActionPoliceStation('');
      setActionPoliceRef('');
      setSuccessMsg('Responder action recorded on immutable timeline.');
      loadAlertDetail(selectedAlert.panic_alert_id);
      fetchActiveAlerts(false);
    } catch (err) {
      setError(err.message || 'Failed to record responder action');
    }
  };

  const handleResolveAlert = async () => {
    if (!selectedAlert) return;
    try {
      await panicApi.resolveAlert(selectedAlert.panic_alert_id, {
        outcome: resolveOutcome,
        findings: resolveFindings,
        preventive_measures: resolvePreventive
      });
      setShowResolveModal(false);
      setResolveFindings('');
      setResolvePreventive('');
      setSuccessMsg('Alert resolution submitted. Awaiting Admin final closure review.');
      loadAlertDetail(selectedAlert.panic_alert_id);
      fetchActiveAlerts(false);
    } catch (err) {
      setError(err.message || 'Failed to resolve alert');
    }
  };

  const handleAdminReview = async () => {
    if (!selectedAlert) return;
    try {
      await panicApi.adminReview(selectedAlert.panic_alert_id, {
        review_status: adminReviewStatus,
        review_note: adminReviewNote
      });
      setShowAdminReviewModal(false);
      setAdminReviewNote('');
      setSuccessMsg(`Admin review completed: Alert set to ${adminReviewStatus}.`);
      loadAlertDetail(selectedAlert.panic_alert_id);
      fetchActiveAlerts(false);
    } catch (err) {
      setError(err.message || 'Failed to complete admin review');
    }
  };

  const handleReportFalseAlarm = async () => {
    if (!selectedAlert) return;
    try {
      await panicApi.reportFalseAlarm(selectedAlert.panic_alert_id, {
        reason: falseAlarmReason,
        additional_notes: falseAlarmNotes
      });
      setShowFalseAlarmModal(false);
      setFalseAlarmNotes('');
      setSuccessMsg('False alarm claim logged. Note: Alert remains active until confirmed by Supervisor and reviewed by Admin.');
      loadAlertDetail(selectedAlert.panic_alert_id);
      fetchActiveAlerts(false);
    } catch (err) {
      setError(err.message || 'Failed to report false alarm');
    }
  };

  const handleConfirmFalseAlarm = async () => {
    if (!selectedAlert) return;
    try {
      await panicApi.confirmFalseAlarm(selectedAlert.panic_alert_id, {
        supervisor_verification_notes: confirmSupervisorNote
      });
      setShowConfirmFalseAlarmModal(false);
      setConfirmSupervisorNote('');
      setSuccessMsg('False alarm confirmed by supervisor. Forwarded to Admin for final closure.');
      loadAlertDetail(selectedAlert.panic_alert_id);
      fetchActiveAlerts(false);
    } catch (err) {
      setError(err.message || 'Failed to confirm false alarm');
    }
  };

  const handleAddWelfareNote = async () => {
    if (!selectedAlert) return;
    try {
      await panicApi.addWelfareNote(selectedAlert.panic_alert_id, {
        notes: welfareNote
      });
      setShowWelfareModal(false);
      setWelfareNote('');
      setSuccessMsg('Guard post-incident welfare follow-up logged.');
      loadAlertDetail(selectedAlert.panic_alert_id);
    } catch (err) {
      setError(err.message || 'Failed to log welfare follow-up');
    }
  };

  const handleLinkIncident = async (alertId) => {
    try {
      const res = await panicApi.linkIncident(alertId, {});
      setSuccessMsg(`Incident #${res.data?.case_number || 'created'} linked successfully.`);
      loadAlertDetail(alertId);
    } catch (err) {
      setError(err.message || 'Failed to link incident');
    }
  };

  const handleExport = async (alertId, format = 'csv') => {
    try {
      const res = await panicApi.exportReport(alertId, format);
      const blob = new Blob([res.data], { type: format === 'csv' ? 'text/csv' : 'text/html' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `panic_report_${alertId}.${format}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Export failed');
    }
  };

  const handleCreateDrill = async () => {
    if (!drillTitle || !drillSiteId) {
      setError('Drill title and site are required.');
      return;
    }
    try {
      await panicApi.createDrill({
        title: drillTitle,
        description: drillDescription,
        site_id: drillSiteId,
        scenario_type: drillScenario,
        scheduled_start: new Date().toISOString(),
        scheduled_end: new Date(Date.now() + 3600000).toISOString()
      });
      setShowDrillModal(false);
      setDrillTitle('');
      setDrillDescription('');
      setSuccessMsg('Emergency drill registered. Test alerts linked to this drill will be excluded from real metrics.');
      fetchDrills();
    } catch (err) {
      setError(err.message || 'Failed to register emergency drill');
    }
  };

  const handleTriggerPanic = async () => {
    setTriggerStatusNotice('Dispatching emergency panic signal to server...');
    try {
      const payload = {
        client_generated_id: `panic-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
        site_id: triggerForm.site_id || undefined,
        battery_level: Number(triggerForm.battery_level),
        network_type: triggerForm.network_type,
        latitude: Number(triggerForm.latitude),
        longitude: Number(triggerForm.longitude),
        accuracy_meters: Number(triggerForm.accuracy_meters),
        test_flag: Boolean(triggerForm.test_flag),
        device_time: new Date().toISOString()
      };
      const res = await panicApi.triggerPanic(payload);
      setTriggerStatusNotice('Sent! Server acknowledged emergency trigger.');
      setTimeout(() => {
        setShowTriggerModal(false);
        setTriggerStatusNotice(null);
        fetchActiveAlerts(false);
        loadAlertDetail(res.data.panic_alert_id);
      }, 1000);
    } catch (err) {
      setTriggerStatusNotice('Not Sent. Trying again. Call 112 or your supervisor immediately.');
      setError(err.message || 'Failed to dispatch panic trigger');
    }
  };

  // Stage Badge Helper
  const getStageBadge = (stage) => {
    switch (stage) {
      case 0:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-blue-100 text-blue-800">Stage 0 (Initial)</span>;
      case 1:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-800">Stage 1 (Primary Sup)</span>;
      case 2:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-orange-100 text-orange-800">Stage 2 (Backup & Admin)</span>;
      case 3:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-100 text-red-800 animate-pulse">Stage 3 (Client Warn)</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-purple-100 text-purple-800">Stage {stage}</span>;
    }
  };

  // Status Badge Helper
  const getStatusBadge = (status) => {
    switch (status) {
      case 'TRIGGERED':
      case 'DELIVERING':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-600 text-white animate-pulse">TRIGGERED</span>;
      case 'ACKNOWLEDGED':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-500 text-white">ACKNOWLEDGED</span>;
      case 'RESPONDING':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-indigo-600 text-white">RESPONDING</span>;
      case 'ESCALATED':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-800 text-white">ESCALATED</span>;
      case 'GUARD_CONFIRMED_SAFE':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-teal-600 text-white">GUARD SAFE</span>;
      case 'RESOLVED':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-blue-600 text-white">RESOLVED</span>;
      case 'FALSE_ALARM':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-gray-600 text-white">FALSE ALARM</span>;
      case 'CLOSED':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-green-700 text-white">CLOSED</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-gray-200 text-gray-800">{status}</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Banner / Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-red-50 text-red-600 rounded-lg border border-red-200">
              <AlertOctagon className="w-8 h-8" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold text-gray-900">Panic & Escalation Management</h1>
                <span className="px-2 py-0.5 text-xs font-semibold bg-gray-100 text-gray-600 rounded border border-gray-300">
                  Module 9
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Emergency alert triage, multi-route notifications, responder tracking & escalation ladder.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              title={soundEnabled ? 'Alarm sound active (click to mute)' : 'Alarm sound muted (click to enable)'}
              className={`inline-flex items-center px-3 py-2 text-xs font-medium rounded-md border ${soundEnabled
                  ? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
                  : 'bg-gray-100 text-gray-600 border-gray-300 hover:bg-gray-200'
                }`}
            >
              {soundEnabled ? <Bell className="w-4 h-4 mr-1 text-amber-600 animate-bounce" /> : <BellOff className="w-4 h-4 mr-1" />}
              {soundEnabled ? 'Alarm Sound: ON' : 'Alarm Sound: OFF'}
            </button>

            <button
              onClick={() => {
                fetchActiveAlerts();
                if (activeTab === 'history') fetchHistoryAlerts();
              }}
              className="inline-flex items-center px-3 py-2 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <RefreshCw className="w-4 h-4 mr-1 text-gray-500" />
              Refresh
            </button>

            <button
              onClick={() => setShowTriggerModal(true)}
              className="inline-flex items-center px-4 py-2 text-xs font-bold text-white bg-red-600 rounded-md hover:bg-red-700 shadow-sm"
            >
              <AlertTriangle className="w-4 h-4 mr-1.5" />
              Trigger Emergency Panic
            </button>
          </div>
        </div>

        {/* Honest Limitations Notice */}
        <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-md flex items-start space-x-2 text-xs text-slate-700">
          <HelpCircle className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-slate-900">System Capability Notice: </span>
            Panic alerts rely on cellular signal, device battery, and available human responders.
            The system cannot guarantee response times, rescue, or physical safety. In imminent life danger, always contact local police / 112 directly.
          </div>
        </div>
      </div>

      {/* Flashing Emergency Banner for Active Alarms */}
      {activeAlerts.length > 0 && (
        <div className="bg-red-50 border-2 border-red-500 rounded-lg p-4 animate-pulse shadow-md">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-red-600 text-white rounded-full">
                <Radio className="w-6 h-6 animate-spin" />
              </div>
              <div>
                <div className="text-sm font-extrabold text-red-900 flex items-center space-x-2">
                  <span>🚨 ACTIVE PANIC EMERGENCY IN PROGRESS ({activeAlerts.length})</span>
                  {activeAlerts[0]?.test_flag && (
                    <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-200 text-amber-900 rounded">TEST DRILL</span>
                  )}
                </div>
                <div className="text-xs text-red-700 mt-0.5">
                  Latest: <span className="font-semibold">{activeAlerts[0]?.alert_number}</span> &bull;
                  Guard: <span className="font-semibold">{activeAlerts[0]?.guard_name}</span> &bull;
                  Site: <span className="font-semibold">{activeAlerts[0]?.site_name || 'Off-site / In-transit'}</span> &bull;
                  Status: <span className="font-bold underline">{activeAlerts[0]?.alert_status}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => {
                  setSelectedAlert(activeAlerts[0]);
                  loadAlertDetail(activeAlerts[0].panic_alert_id);
                }}
                className="px-3 py-1.5 bg-red-600 text-white text-xs font-bold rounded shadow hover:bg-red-700 flex items-center"
              >
                <Eye className="w-3.5 h-3.5 mr-1" />
                Triage Incident
              </button>
              {activeAlerts[0]?.alert_status === 'TRIGGERED' && (
                <button
                  onClick={() => handleAcknowledge(activeAlerts[0].panic_alert_id)}
                  className="px-3 py-1.5 bg-amber-500 text-white text-xs font-bold rounded shadow hover:bg-amber-600 flex items-center"
                >
                  <Check className="w-3.5 h-3.5 mr-1" />
                  Acknowledge & Silence
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md text-sm text-red-700 flex items-start space-x-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-600" />
          <div className="flex-1">
            <span className="font-semibold">Error: </span> {error}
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-md text-sm text-green-700 flex items-start space-x-2">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5 text-green-600" />
          <div className="flex-1">
            <span className="font-semibold">Success: </span> {successMsg}
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-green-500 hover:text-green-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-gray-200 bg-white px-4 rounded-t-lg shadow-sm overflow-x-auto">
        <button
          onClick={() => handleTabChange('active')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'active'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <Radio className="w-4 h-4 text-red-600" />
          <span>Active Emergencies</span>
          {activeAlerts.length > 0 && (
            <span className="ml-1.5 px-1.5 py-0.5 bg-red-600 text-white rounded-full text-[10px]">
              {activeAlerts.length}
            </span>
          )}
        </button>

        <button
          onClick={() => handleTabChange('history')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'history'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <Clock className="w-4 h-4" />
          <span>Alert History</span>
        </button>

        <button
          onClick={() => handleTabChange('config')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'config'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <ShieldAlert className="w-4 h-4" />
          <span>Escalation Rules</span>
        </button>

        <button
          onClick={() => handleTabChange('drills')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'drills'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <PlayCircle className="w-4 h-4" />
          <span>Emergency Drills</span>
        </button>

        <button
          onClick={() => handleTabChange('readiness')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'readiness'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <Smartphone className="w-4 h-4" />
          <span>Device Readiness</span>
        </button>

        <button
          onClick={() => handleTabChange('client_safe')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'client_safe'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <Eye className="w-4 h-4" />
          <span>Client Safe Portal View</span>
        </button>

        <button
          onClick={() => handleTabChange('metrics')}
          className={`py-3.5 px-4 font-semibold text-xs border-b-2 flex items-center space-x-2 whitespace-nowrap ${activeTab === 'metrics'
              ? 'border-red-600 text-red-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
        >
          <Activity className="w-4 h-4" />
          <span>Analytics & Metrics</span>
        </button>
      </div>

      {/* TAB 1: ACTIVE EMERGENCIES MONITOR */}
      {activeTab === 'active' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
              Live Ongoing Panic Alarms ({activeAlerts.length})
            </h2>
            <div className="text-xs text-gray-500 flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
              <span>Live Polling Active (every 6s)</span>
            </div>
          </div>

          {activeAlerts.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
              <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-gray-900">No Active Panic Emergencies</h3>
              <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
                All security guards are currently operating normally. In an emergency, guards can tap the panic button on their device.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeAlerts.map((alert) => (
                <div
                  key={alert.panic_alert_id}
                  className={`border rounded-lg p-5 shadow-sm transition hover:shadow-md ${alert.alert_status === 'TRIGGERED' || alert.alert_status === 'DELIVERING'
                      ? 'border-red-400 bg-red-50/40'
                      : 'border-amber-300 bg-amber-50/20'
                    }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-extrabold text-gray-900">{alert.alert_number}</span>
                        {getStatusBadge(alert.alert_status)}
                        {getStageBadge(alert.current_escalation_stage)}
                        {alert.test_flag && (
                          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-purple-100 text-purple-700">
                            TEST
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        Triggered: {new Date(alert.trigger_server_time).toLocaleTimeString()} ({new Date(alert.trigger_server_time).toLocaleDateString()})
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
                    <div>
                      <span className="text-gray-500 block">Security Guard</span>
                      <span className="font-semibold text-gray-900">{alert.guard_name}</span>
                      <div className="text-gray-500 text-[11px]">Badge: {alert.guard_badge_number || 'N/A'}</div>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Duty Site</span>
                      <span className="font-semibold text-gray-900">{alert.site_name || 'Off-site / Outside Duty'}</span>
                      <div className="text-[11px] font-medium text-amber-700">{alert.duty_status}</div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-gray-200/60 flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      <span className="text-gray-500">Acknowledgements:</span>
                      <span className="font-bold text-gray-800">{alert.acknowledgement_count || 0}</span>
                    </div>

                    <div className="flex items-center space-x-2">
                      {alert.alert_status === 'TRIGGERED' && (
                        <button
                          onClick={() => handleAcknowledge(alert.panic_alert_id)}
                          className="px-2.5 py-1 bg-amber-600 text-white font-medium rounded hover:bg-amber-700"
                        >
                          Acknowledge
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setSelectedAlert(alert);
                          loadAlertDetail(alert.panic_alert_id);
                        }}
                        className="px-3 py-1 bg-slate-900 text-white font-medium rounded hover:bg-slate-800 flex items-center"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" />
                        Triage & Actions
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: ALL PANIC HISTORY */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-4">
          {/* Filter Bar */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
              <input
                type="text"
                placeholder="Search alert #, guard..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs border border-gray-300 rounded-md"
              />
            </div>

            <div>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="w-full py-2 px-3 text-xs border border-gray-300 rounded-md"
              >
                <option value="">All Statuses</option>
                <option value="TRIGGERED">TRIGGERED</option>
                <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                <option value="RESPONDING">RESPONDING</option>
                <option value="RESOLVED">RESOLVED</option>
                <option value="FALSE_ALARM">FALSE_ALARM</option>
                <option value="CLOSED">CLOSED</option>
              </select>
            </div>

            <div>
              <select
                value={filterSite}
                onChange={(e) => setFilterSite(e.target.value)}
                className="w-full py-2 px-3 text-xs border border-gray-300 rounded-md"
              >
                <option value="">All Sites</option>
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.site_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <select
                value={filterStage}
                onChange={(e) => setFilterStage(e.target.value)}
                className="w-full py-2 px-3 text-xs border border-gray-300 rounded-md"
              >
                <option value="">All Stages</option>
                <option value="0">Stage 0</option>
                <option value="1">Stage 1</option>
                <option value="2">Stage 2</option>
                <option value="3">Stage 3</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <label className="flex items-center space-x-1.5 text-xs text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeTests}
                  onChange={(e) => setIncludeTests(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span>Include Test Drills</span>
              </label>

              <button
                onClick={fetchHistoryAlerts}
                className="ml-auto px-3 py-2 bg-slate-900 text-white text-xs font-medium rounded-md hover:bg-slate-800"
              >
                Filter
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto border border-gray-200 rounded-md">
            <table className="min-w-full divide-y divide-gray-200 text-xs">
              <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left">Alert Number</th>
                  <th className="px-4 py-3 text-left">Guard</th>
                  <th className="px-4 py-3 text-left">Site</th>
                  <th className="px-4 py-3 text-left">Trigger Time</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Stage</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {historyAlerts.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="px-4 py-8 text-center text-gray-500">
                      No panic alerts found matching criteria.
                    </td>
                  </tr>
                ) : (
                  historyAlerts.map((a) => (
                    <tr key={a.panic_alert_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-bold text-gray-900">{a.alert_number}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{a.guard_name}</div>
                        <div className="text-gray-400 text-[11px]">{a.duty_status}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-700">{a.site_name || 'Off-site'}</td>
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(a.trigger_server_time).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">{getStatusBadge(a.alert_status)}</td>
                      <td className="px-4 py-3">{getStageBadge(a.current_escalation_stage)}</td>
                      <td className="px-4 py-3">
                        {a.test_flag ? (
                          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-purple-100 text-purple-800">
                            TEST DRILL
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-red-100 text-red-800">
                            REAL
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-1">
                        <button
                          onClick={() => {
                            setSelectedAlert(a);
                            loadAlertDetail(a.panic_alert_id);
                          }}
                          className="px-2.5 py-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-800 rounded font-medium"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleExport(a.panic_alert_id, 'csv')}
                          title="Export CSV"
                          className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded"
                        >
                          <Download className="w-3.5 h-3.5" />
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

      {/* TAB 3: ESCALATION RULES & CONFIG */}
      {activeTab === 'config' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
                Configurable Escalation Ladder & Intervals
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Multi-tier escalation stages (0 to 3) triggered when unacknowledged.
              </p>
            </div>
            {isAdmin && (
              <button
                onClick={async () => {
                  try {
                    await panicApi.updateConfig(config);
                    setSuccessMsg('Escalation configuration saved successfully.');
                  } catch (err) {
                    setError(err.message || 'Failed to save config');
                  }
                }}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                Save Settings
              </button>
            )}
          </div>

          {config ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
              <div className="p-4 border border-gray-200 rounded-lg space-y-4 bg-gray-50/50">
                <h3 className="font-bold text-gray-900 text-sm flex items-center">
                  <Clock className="w-4 h-4 mr-1.5 text-blue-600" /> Escalation Intervals (Minutes)
                </h3>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    Stage 1 Escalation Interval (minutes):
                  </label>
                  <input
                    type="number"
                    value={config.stage1_interval_minutes}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, stage1_interval_minutes: Number(e.target.value) })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                  />
                  <span className="text-gray-400 text-[11px]">Primary site supervisor notified. Default: 3 min.</span>
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    Stage 2 Escalation Interval (minutes):
                  </label>
                  <input
                    type="number"
                    value={config.stage2_interval_minutes}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, stage2_interval_minutes: Number(e.target.value) })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                  />
                  <span className="text-gray-400 text-[11px]">Backup supervisor & Admin duty officers. Default: 5 min.</span>
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    Stage 3 Escalation Interval (minutes):
                  </label>
                  <input
                    type="number"
                    value={config.stage3_interval_minutes}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, stage3_interval_minutes: Number(e.target.value) })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                  />
                  <span className="text-gray-400 text-[11px]">Critical escalation notice sent to client escalation contacts. Default: 10 min.</span>
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    No-Acknowledgement Warning Interval (minutes):
                  </label>
                  <input
                    type="number"
                    value={config.no_ack_warning_interval_minutes}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, no_ack_warning_interval_minutes: Number(e.target.value) })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                  />
                  <span className="text-gray-400 text-[11px]">High-priority repeated alarm if zero responses. Default: 2 min.</span>
                </div>
              </div>

              <div className="p-4 border border-gray-200 rounded-lg space-y-4 bg-gray-50/50">
                <h3 className="font-bold text-gray-900 text-sm flex items-center">
                  <PhoneCall className="w-4 h-4 mr-1.5 text-emerald-600" /> Emergency Recipient Fallbacks
                </h3>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    Backup On-Call Phone Number:
                  </label>
                  <input
                    type="text"
                    value={config.backup_on_call_phone || ''}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, backup_on_call_phone: e.target.value })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                    placeholder="+91-9876543210"
                  />
                  <span className="text-gray-400 text-[11px]">Automated SMS recipient if no site supervisor assigned.</span>
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    Alert Re-trigger Cooldown (seconds):
                  </label>
                  <input
                    type="number"
                    value={config.cooldown_seconds}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, cooldown_seconds: Number(e.target.value) })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                  />
                  <span className="text-gray-400 text-[11px]">Debounce window for accidental double taps. Default: 30s.</span>
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">
                    Notification Repeat Retries:
                  </label>
                  <input
                    type="number"
                    value={config.max_repeat_retries}
                    disabled={!isAdmin}
                    onChange={(e) => setConfig({ ...config, max_repeat_retries: Number(e.target.value) })}
                    className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                  />
                  <span className="text-gray-400 text-[11px]">Max automated SMS / push retries if unacknowledged.</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 text-xs">Loading configuration...</div>
          )}
        </div>
      )}

      {/* TAB 4: CONTROLLED DRILLS & TESTS */}
      {activeTab === 'drills' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
                Controlled Emergency Drills & Mock Tests
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                All alerts triggered during a scheduled drill are marked with <code className="text-purple-700 font-bold">test_flag = True</code> and excluded from real KPIs.
              </p>
            </div>
            <button
              onClick={() => setShowDrillModal(true)}
              className="px-3 py-2 bg-purple-600 text-white text-xs font-semibold rounded-md hover:bg-purple-700 flex items-center"
            >
              <PlayCircle className="w-4 h-4 mr-1.5" />
              Schedule New Drill
            </button>
          </div>

          <div className="overflow-x-auto border border-gray-200 rounded-md">
            <table className="min-w-full divide-y divide-gray-200 text-xs">
              <thead className="bg-gray-50 text-gray-600 font-semibold uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Drill Title</th>
                  <th className="px-4 py-3 text-left">Site</th>
                  <th className="px-4 py-3 text-left">Scenario</th>
                  <th className="px-4 py-3 text-left">Scheduled Period</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Test Alerts</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {drills.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="px-4 py-8 text-center text-gray-500">
                      No emergency drills recorded. Click "Schedule New Drill" to register a training session.
                    </td>
                  </tr>
                ) : (
                  drills.map((d) => (
                    <tr key={d.drill_id}>
                      <td className="px-4 py-3 font-semibold text-gray-900">{d.title}</td>
                      <td className="px-4 py-3 text-gray-700">{d.site_name}</td>
                      <td className="px-4 py-3 text-gray-500">{d.scenario_type}</td>
                      <td className="px-4 py-3 text-gray-500">
                        {new Date(d.scheduled_start).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-purple-100 text-purple-800">
                          {d.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold text-gray-700">{d.alerts_count || 0}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: DEVICE READINESS MONITOR */}
      {activeTab === 'readiness' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
                Guard Mobile Device Readiness (FR-9.141)
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Monitors background location permission, battery health, mock location spoofing & panic readiness.
              </p>
            </div>
            <button
              onClick={fetchReadiness}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200"
            >
              Refresh Diagnostics
            </button>
          </div>

          <div className="overflow-x-auto border border-gray-200 rounded-md">
            <table className="min-w-full divide-y divide-gray-200 text-xs">
              <thead className="bg-gray-50 text-gray-600 font-semibold uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Guard</th>
                  <th className="px-4 py-3 text-left">Battery</th>
                  <th className="px-4 py-3 text-left">Location Permission</th>
                  <th className="px-4 py-3 text-left">Background GPS</th>
                  <th className="px-4 py-3 text-left">Mock Location</th>
                  <th className="px-4 py-3 text-left">App Version</th>
                  <th className="px-4 py-3 text-left">Last Diagnostics</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {readinessList.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="px-4 py-8 text-center text-gray-500">
                      No device telemetry logged yet.
                    </td>
                  </tr>
                ) : (
                  readinessList.map((r) => {
                    const lowBattery = Number(r.battery_percentage) < 20;
                    const ready = r.location_permission_granted && !r.mock_location_detected && !lowBattery;
                    return (
                      <tr key={r.readiness_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-semibold text-gray-900">{r.guard_name}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`font-semibold ${lowBattery ? 'text-red-600 font-bold' : 'text-gray-700'
                              }`}
                          >
                            {r.battery_percentage}%
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {r.location_permission_granted ? (
                            <span className="text-emerald-700 font-medium">GRANTED</span>
                          ) : (
                            <span className="text-red-700 font-bold">DENIED</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {r.background_location_enabled ? (
                            <span className="text-emerald-700">ENABLED</span>
                          ) : (
                            <span className="text-amber-700 font-semibold">RESTRICTED</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {r.mock_location_detected ? (
                            <span className="px-1.5 py-0.5 bg-red-100 text-red-800 font-bold rounded">
                              DETECTED (MOCK)
                            </span>
                          ) : (
                            <span className="text-emerald-700">CLEAN</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-600">{r.app_version || 'v1.0.0'}</td>
                        <td className="px-4 py-3 text-gray-500">
                          {new Date(r.last_heartbeat_at).toLocaleTimeString()}
                        </td>
                        <td className="px-4 py-3">
                          {ready ? (
                            <span className="px-2 py-0.5 text-xs font-bold rounded bg-emerald-100 text-emerald-800">
                              READY
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-100 text-red-800">
                              ATTENTION REQ
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: CLIENT SAFE PORTAL VIEW */}
      {activeTab === 'client_safe' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-6">
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
              Client Portal Sanitized View (Section 7.1 / FR-9.150)
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Verified privacy-safe feed for clients. <strong>Never exposes</strong> exact guard coordinates, location trail, guard battery, phone numbers, or supervisor internal investigation notes.
            </p>
          </div>

          <div className="max-w-xs">
            <label className="block text-xs font-medium text-gray-700 mb-1">Select Client Site:</label>
            <select
              value={selectedSiteForClient}
              onChange={(e) => {
                setSelectedSiteForClient(e.target.value);
                fetchClientSafe(e.target.value);
              }}
              className="w-full py-2 px-3 text-xs border border-gray-300 rounded-md"
            >
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.site_name}
                </option>
              ))}
            </select>
          </div>

          {clientSafeStatus ? (
            <div className="p-5 border border-slate-200 rounded-lg bg-slate-50/50 space-y-4 max-w-lg">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Site Monitored:</span>
                <span className="text-xs font-bold text-slate-900">{clientSafeStatus.site_name}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Security Status:</span>
                <span className={`px-2 py-0.5 text-xs font-bold rounded ${clientSafeStatus.has_active_emergency ? 'bg-red-100 text-red-800' : 'bg-emerald-100 text-emerald-800'
                  }`}>
                  {clientSafeStatus.status_label}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Active Emergencies:</span>
                <span className="text-xs font-bold text-slate-900">{clientSafeStatus.active_emergency_count}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Last Verified Status Time:</span>
                <span className="text-xs text-slate-600">
                  {new Date(clientSafeStatus.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="pt-3 border-t border-slate-200 text-[11px] text-slate-500 italic">
                {clientSafeStatus.safe_description || 'Site security is actively monitored by response team.'}
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-500">Select a site to inspect client-safe status.</div>
          )}
        </div>
      )}

      {/* TAB 7: ANALYTICS & METRICS */}
      {activeTab === 'metrics' && (
        <div className="bg-white rounded-b-lg shadow-sm border border-t-0 border-gray-200 p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
                Emergency Response Operational Performance (FR-9.153)
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Controlled drill tests (<code className="text-purple-700">test_flag=True</code>) are strictly excluded from these operational metrics.
              </p>
            </div>
            <button
              onClick={fetchMetrics}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200"
            >
              Refresh Metrics
            </button>
          </div>

          {metrics ? (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-slate-500 font-medium">Real Emergencies</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">{metrics.total_real_alerts}</div>
                  <div className="text-[11px] text-purple-600 mt-1">({metrics.total_test_alerts} drill tests excluded)</div>
                </div>

                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-slate-500 font-medium">Avg Time to Acknowledge</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">
                    {metrics.avg_time_to_acknowledgement_seconds !== null ? `${metrics.avg_time_to_acknowledgement_seconds}s` : 'N/A'}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">From trigger to first responder ack</div>
                </div>

                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-slate-500 font-medium">Avg Time to Resolution</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">
                    {metrics.avg_time_to_resolution_seconds !== null ? `${Math.round(metrics.avg_time_to_resolution_seconds / 60)} min` : 'N/A'}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">From trigger to resolved/closed</div>
                </div>

                <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="text-slate-500 font-medium">False Alarm Rate</div>
                  <div className="text-2xl font-black text-amber-600 mt-1">{metrics.false_alarm_rate_percentage}%</div>
                  <div className="text-[11px] text-slate-400 mt-1">{metrics.false_alarm_count} confirmed false alarms</div>
                </div>
              </div>

              {/* Stage breakdown */}
              <div className="p-4 border border-gray-200 rounded-lg bg-gray-50/50">
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-3">
                  Escalation Ladder Stage Distribution
                </h3>
                <div className="grid grid-cols-4 gap-3 text-center text-xs">
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-500 block">Stage 0 (Initial)</span>
                    <span className="text-lg font-bold text-blue-700">{metrics.stage_breakdown?.stage_0 || 0}</span>
                  </div>
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-500 block">Stage 1 (Primary Sup)</span>
                    <span className="text-lg font-bold text-amber-700">{metrics.stage_breakdown?.stage_1 || 0}</span>
                  </div>
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-500 block">Stage 2 (Backup & Admin)</span>
                    <span className="text-lg font-bold text-orange-700">{metrics.stage_breakdown?.stage_2 || 0}</span>
                  </div>
                  <div className="p-3 bg-white border border-gray-200 rounded">
                    <span className="text-gray-500 block">Stage 3 (Client Warn)</span>
                    <span className="text-lg font-bold text-red-700">{metrics.stage_breakdown?.stage_3_warning || 0}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-500">Loading performance telemetry...</div>
          )}
        </div>
      )}

      {/* DETAIL / TRIAGE DRAWER (MODAL) */}
      <Modal
        isOpen={Boolean(selectedAlert)}
        onClose={() => setSelectedAlert(null)}
        title={
          selectedAlert ? (
            <div className="flex items-center space-x-2">
              <span>Emergency Triage: {selectedAlert.alert_number}</span>
              {selectedAlert.test_flag && (
                <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-purple-100 text-purple-800">
                  TEST DRILL
                </span>
              )}
            </div>
          ) : (
            'Alert Detail'
          )
        }
        maxWidth="max-w-4xl"
      >
        {alertDetailLoading ? (
          <div className="py-12 text-center text-xs text-gray-500">Loading incident data...</div>
        ) : selectedAlert ? (
          <div className="space-y-6 text-xs max-h-[80vh] overflow-y-auto pr-1">
            {/* Top Status Banner */}
            <div className="p-3 bg-slate-900 text-white rounded-lg flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-slate-300">Status:</span>
                {getStatusBadge(selectedAlert.alert_status)}
                {getStageBadge(selectedAlert.current_escalation_stage)}
              </div>
              <div className="flex items-center space-x-2 text-slate-300">
                <span>Triggered: {new Date(selectedAlert.trigger_server_time).toLocaleString()}</span>
                <button
                  onClick={() => handleExport(selectedAlert.panic_alert_id, 'csv')}
                  className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-white text-[11px] flex items-center"
                >
                  <Download className="w-3 h-3 mr-1" /> Export CSV
                </button>
              </div>
            </div>

            {/* Guard & Site Info Card */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 border border-gray-200 rounded-lg bg-gray-50">
              <div>
                <span className="text-gray-500 block font-medium">Security Guard</span>
                <span className="font-bold text-gray-900 text-sm">{selectedAlert.guard_name}</span>
                <div className="mt-1 flex items-center space-x-2">
                  {selectedAlert.guard_phone ? (
                    <a
                      href={`tel:${selectedAlert.guard_phone}`}
                      className="inline-flex items-center text-blue-600 font-semibold hover:underline"
                    >
                      <PhoneCall className="w-3.5 h-3.5 mr-1" /> {selectedAlert.guard_phone}
                    </a>
                  ) : (
                    <span className="text-gray-400">No phone on file</span>
                  )}
                </div>
              </div>

              <div>
                <span className="text-gray-500 block font-medium">Assignment & Site</span>
                <span className="font-bold text-gray-900">{selectedAlert.site_name || 'Off-site / In transit'}</span>
                <div className="text-gray-600 mt-1">
                  Duty Status: <span className="font-semibold text-amber-700">{selectedAlert.duty_status}</span>
                </div>
              </div>

              <div>
                <span className="text-gray-500 block font-medium">Device & Context</span>
                <div className="space-y-1 mt-1">
                  <div className="flex items-center space-x-1">
                    <Battery className="w-3.5 h-3.5 text-gray-500" />
                    <span>Battery: {selectedAlert.context?.battery_level ? `${selectedAlert.context.battery_level}%` : 'N/A'}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Wifi className="w-3.5 h-3.5 text-gray-500" />
                    <span>Network: {selectedAlert.context?.network_type || 'Unknown'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Position Resolution & Map Link */}
            {selectedAlert.position && (
              <div className="p-4 border border-blue-200 bg-blue-50/40 rounded-lg space-y-2">
                <div className="flex items-center justify-between">
                  <div className="font-bold text-blue-900 flex items-center">
                    <MapPin className="w-4 h-4 mr-1 text-blue-700" /> Resolved Position & Coordinates
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${selectedAlert.position.is_stale ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                    }`}>
                    {selectedAlert.position.is_stale ? 'STALE LOCATION' : 'FRESH LOCATION'}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
                  <div>
                    <span className="text-gray-500 block">Coordinates:</span>
                    <span className="font-mono font-semibold text-gray-900">
                      {selectedAlert.position.latitude}, {selectedAlert.position.longitude}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Accuracy:</span>
                    <span className="font-semibold text-gray-900">
                      &plusmn;{selectedAlert.position.accuracy_meters}m
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Source:</span>
                    <span className="font-semibold text-gray-900">{selectedAlert.position.source_type}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Location Age:</span>
                    <span className="font-semibold text-gray-900">{selectedAlert.position.location_age_minutes}m ago</span>
                  </div>
                </div>

                <div className="pt-2">
                  <a
                    href={`https://maps.google.com/?q=${selectedAlert.position.latitude},${selectedAlert.position.longitude}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center text-blue-700 font-bold hover:underline"
                  >
                    <ExternalLink className="w-3.5 h-3.5 mr-1" /> Open in Google Maps
                  </a>
                </div>
              </div>
            )}

            {/* Multi-Route Delivery Attempts */}
            <div className="space-y-2">
              <h4 className="font-bold text-gray-900 uppercase tracking-wider text-xs">
                Multi-Route Notification Dispatch (Section 4.1)
              </h4>
              <div className="border border-gray-200 rounded-md overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200 text-xs">
                  <thead className="bg-gray-50 text-gray-600 font-semibold uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left">Recipient</th>
                      <th className="px-3 py-2 text-left">Role</th>
                      <th className="px-3 py-2 text-left">Channel</th>
                      <th className="px-3 py-2 text-left">Status</th>
                      <th className="px-3 py-2 text-left">Sent / Delivered At</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {selectedAlert.delivery_attempts?.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="px-3 py-4 text-center text-gray-400">
                          No delivery attempts recorded.
                        </td>
                      </tr>
                    ) : (
                      selectedAlert.delivery_attempts?.map((d) => (
                        <tr key={d.attempt_id}>
                          <td className="px-3 py-2 font-medium text-gray-900">{d.recipient_name}</td>
                          <td className="px-3 py-2 text-gray-600">{d.recipient_type}</td>
                          <td className="px-3 py-2 font-semibold text-gray-700">{d.delivery_channel}</td>
                          <td className="px-3 py-2">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${d.delivery_status === 'DELIVERED'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : d.delivery_status === 'FAILED'
                                    ? 'bg-red-100 text-red-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                            >
                              {d.delivery_status}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-gray-500">
                            {d.delivered_at
                              ? new Date(d.delivered_at).toLocaleTimeString()
                              : d.sent_at
                                ? new Date(d.sent_at).toLocaleTimeString()
                                : 'Pending'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Actions Timeline */}
            <div className="space-y-2">
              <h4 className="font-bold text-gray-900 uppercase tracking-wider text-xs">
                Immutable Event Timeline (AC-9.54)
              </h4>
              <div className="border border-gray-200 rounded-md p-3 max-h-48 overflow-y-auto space-y-2 bg-gray-50/50">
                {selectedAlert.timeline?.length === 0 ? (
                  <div className="text-gray-400 text-center py-2">No timeline events recorded.</div>
                ) : (
                  selectedAlert.timeline?.map((t) => (
                    <div key={t.timeline_id} className="text-[11px] border-b border-gray-100 pb-1.5 last:border-0">
                      <div className="flex items-center justify-between text-gray-500">
                        <span className="font-bold text-gray-800">{t.event_type}</span>
                        <span>{new Date(t.created_at).toLocaleTimeString()}</span>
                      </div>
                      <div className="text-gray-600 mt-0.5">
                        Actor: <span className="font-medium text-gray-800">{t.actor_name || 'System Engine'}</span> &bull;{' '}
                        {JSON.stringify(t.event_data)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* ACTION BUTTONS TOOLBAR */}
            <div className="pt-4 border-t border-gray-200 flex flex-wrap gap-2">
              {/* 1. Acknowledge */}
              {selectedAlert.alert_status === 'TRIGGERED' && (
                <button
                  onClick={() => handleAcknowledge(selectedAlert.panic_alert_id)}
                  className="px-3 py-2 bg-amber-600 text-white font-semibold rounded hover:bg-amber-700 shadow-sm"
                >
                  Acknowledge (Silence Alarm)
                </button>
              )}

              {/* 2. Call Guard */}
              {selectedAlert.guard_phone && (
                <a
                  href={`tel:${selectedAlert.guard_phone}`}
                  onClick={() => {
                    // Log call guard action automatically
                    panicApi.recordAction(selectedAlert.panic_alert_id, {
                      action_type: 'CALL_GUARD',
                      action_note: 'Initiated direct phone call to guard'
                    });
                  }}
                  className="px-3 py-2 bg-emerald-600 text-white font-semibold rounded hover:bg-emerald-700 shadow-sm inline-flex items-center"
                >
                  <PhoneCall className="w-3.5 h-3.5 mr-1" />
                  Call Guard Now
                </a>
              )}

              {/* 3. Send Are You Safe? */}
              <button
                onClick={() => handleSendAreYouSafe(selectedAlert.panic_alert_id)}
                className="px-3 py-2 bg-indigo-600 text-white font-semibold rounded hover:bg-indigo-700 shadow-sm"
              >
                Send "Are You Safe?" Prompt
              </button>

              {/* 4. Record Action */}
              <button
                onClick={() => setShowActionModal(true)}
                className="px-3 py-2 bg-slate-800 text-white font-semibold rounded hover:bg-slate-700 shadow-sm"
              >
                Record Responder Action / Emergency Service
              </button>

              {/* 5. Report False Alarm */}
              {selectedAlert.alert_status !== 'CLOSED' && selectedAlert.alert_status !== 'FALSE_ALARM' && (
                <button
                  onClick={() => setShowFalseAlarmModal(true)}
                  className="px-3 py-2 bg-gray-200 text-gray-800 font-semibold rounded hover:bg-gray-300"
                >
                  Report False Alarm
                </button>
              )}

              {/* 6. Confirm False Alarm (Supervisor) */}
              {selectedAlert.false_alarm && !selectedAlert.false_alarm.supervisor_confirmed && (isSupervisor || isAdmin) && (
                <button
                  onClick={() => setShowConfirmFalseAlarmModal(true)}
                  className="px-3 py-2 bg-amber-700 text-white font-semibold rounded hover:bg-amber-800"
                >
                  Confirm False Alarm Claim
                </button>
              )}

              {/* 7. Resolve Alert */}
              {selectedAlert.alert_status !== 'RESOLVED' && selectedAlert.alert_status !== 'CLOSED' && (
                <button
                  onClick={() => setShowResolveModal(true)}
                  className="px-3 py-2 bg-blue-600 text-white font-semibold rounded hover:bg-blue-700 shadow-sm"
                >
                  Resolve Alert
                </button>
              )}

              {/* 8. Admin Review Closure */}
              {isAdmin && selectedAlert.alert_status === 'RESOLVED' && (
                <button
                  onClick={() => setShowAdminReviewModal(true)}
                  className="px-3 py-2 bg-green-700 text-white font-semibold rounded hover:bg-green-800 shadow-sm"
                >
                  Admin Final Closure Review
                </button>
              )}

              {/* 9. Welfare Note */}
              {isAdmin && (
                <button
                  onClick={() => setShowWelfareModal(true)}
                  className="px-3 py-2 bg-purple-700 text-white font-semibold rounded hover:bg-purple-800 shadow-sm"
                >
                  Add Welfare Follow-up
                </button>
              )}

              {/* 10. Link Module 8 Incident */}
              <button
                onClick={() => handleLinkIncident(selectedAlert.panic_alert_id)}
                className="px-3 py-2 bg-slate-100 text-slate-800 border border-slate-300 font-semibold rounded hover:bg-slate-200"
              >
                Create / Link Module 8 Incident
              </button>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* SUB-MODAL: TRIGGER PANIC */}
      <Modal
        isOpen={showTriggerModal}
        onClose={() => setShowTriggerModal(false)}
        title="Emergency Panic Alert Trigger (Guard Device Interface)"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-800">
            <strong>Emergency Simulation: </strong> Dispatches an immediate high-priority panic alert across SMS, Web, and Push notification channels.
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Deployment Site:</label>
            <select
              value={triggerForm.site_id}
              onChange={(e) => setTriggerForm({ ...triggerForm, site_id: e.target.value })}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="">Off-site / In Transit / Outside Duty</option>
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.site_name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-700 font-medium mb-1">Battery Level (%):</label>
              <input
                type="number"
                value={triggerForm.battery_level}
                onChange={(e) => setTriggerForm({ ...triggerForm, battery_level: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded"
              />
            </div>
            <div>
              <label className="block text-gray-700 font-medium mb-1">Network Type:</label>
              <select
                value={triggerForm.network_type}
                onChange={(e) => setTriggerForm({ ...triggerForm, network_type: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded"
              >
                <option value="5G">5G</option>
                <option value="4G">4G / LTE</option>
                <option value="3G">3G</option>
                <option value="WIFI">Wi-Fi</option>
                <option value="OFFLINE">Offline Buffer</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-700 font-medium mb-1">Latitude:</label>
              <input
                type="number"
                step="0.0001"
                value={triggerForm.latitude}
                onChange={(e) => setTriggerForm({ ...triggerForm, latitude: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-700 font-medium mb-1">Longitude:</label>
              <input
                type="number"
                step="0.0001"
                value={triggerForm.longitude}
                onChange={(e) => setTriggerForm({ ...triggerForm, longitude: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded font-mono"
              />
            </div>
          </div>

          <div>
            <label className="flex items-center space-x-2 text-purple-900 font-semibold cursor-pointer">
              <input
                type="checkbox"
                checked={triggerForm.test_flag}
                onChange={(e) => setTriggerForm({ ...triggerForm, test_flag: e.target.checked })}
                className="rounded border-gray-300"
              />
              <span>Mark as Test Drill (Excludes from real KPIs)</span>
            </label>
          </div>

          {triggerStatusNotice && (
            <div className="p-2.5 bg-slate-900 text-white rounded font-bold text-center">
              {triggerStatusNotice}
            </div>
          )}

          <div className="pt-2 flex justify-end space-x-2">
            <button
              onClick={() => setShowTriggerModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              onClick={handleTriggerPanic}
              className="px-4 py-2 bg-red-600 text-white font-bold rounded hover:bg-red-700 shadow-md flex items-center"
            >
              <AlertOctagon className="w-4 h-4 mr-1.5" />
              TRIGGER PANIC NOW
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: RECORD RESPONDER ACTION */}
      <Modal
        isOpen={showActionModal}
        onClose={() => setShowActionModal(false)}
        title="Record Supervisor / Emergency Services Action"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block text-gray-700 font-medium mb-1">Action Type:</label>
            <select
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="RESPONSE_STARTED">RESPONSE_STARTED (Supervisor en route to site)</option>
              <option value="EMERGENCY_SERVICES_INFORMED">EMERGENCY_SERVICES_INFORMED (Police / PCR / Ambulance)</option>
              <option value="REINFORCEMENTS_DEPLOYED">REINFORCEMENTS_DEPLOYED (Additional guards dispatched)</option>
              <option value="SITE_CONTACT_INFORMED">SITE_CONTACT_INFORMED (Client site rep notified)</option>
            </select>
          </div>

          {actionType === 'EMERGENCY_SERVICES_INFORMED' && (
            <div className="space-y-3 p-3 bg-red-50 border border-red-200 rounded">
              <div>
                <label className="block text-gray-700 font-medium mb-1">Police Station / PCR Unit:</label>
                <input
                  type="text"
                  placeholder="e.g. Indiranagar Police Station"
                  value={actionPoliceStation}
                  onChange={(e) => setActionPoliceStation(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded bg-white"
                />
              </div>
              <div>
                <label className="block text-gray-700 font-medium mb-1">GD Entry / Diary Reference Number:</label>
                <input
                  type="text"
                  placeholder="e.g. GD-2026-9912A"
                  value={actionPoliceRef}
                  onChange={(e) => setActionPoliceRef(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded bg-white"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-gray-700 font-medium mb-1">Action Details / Notes:</label>
            <textarea
              rows="3"
              placeholder="Describe actions taken, vehicle details, estimated arrival..."
              value={actionNote}
              onChange={(e) => setActionNote(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowActionModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleRecordAction}
              className="px-3 py-1.5 bg-slate-900 text-white font-medium rounded hover:bg-slate-800"
            >
              Save Action to Timeline
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: RESOLVE ALERT */}
      <Modal
        isOpen={showResolveModal}
        onClose={() => setShowResolveModal(false)}
        title="Submit Emergency Resolution (Supervisor Review)"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block text-gray-700 font-medium mb-1">Resolution Outcome:</label>
            <select
              value={resolveOutcome}
              onChange={(e) => setResolveOutcome(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="RESOLVED_ASSISTED">RESOLVED_ASSISTED (Supervisor attended & resolved)</option>
              <option value="RESOLVED_POLICE_HANDOVER">RESOLVED_POLICE_HANDOVER (Handed over to law enforcement)</option>
              <option value="RESOLVED_MEDICAL_ATTENTION">RESOLVED_MEDICAL_ATTENTION (Medical care administered)</option>
              <option value="RESOLVED_NO_THREAT_FOUND">RESOLVED_NO_THREAT_FOUND (Inspection cleared site)</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Investigation Findings:</label>
            <textarea
              rows="3"
              placeholder="Summary of incident cause, situation on ground..."
              value={resolveFindings}
              onChange={(e) => setResolveFindings(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Preventive Measures / Actions Recommended:</label>
            <textarea
              rows="2"
              placeholder="Follow-up training, lighting improvement, patrol frequency..."
              value={resolvePreventive}
              onChange={(e) => setResolvePreventive(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowResolveModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleResolveAlert}
              className="px-3 py-1.5 bg-blue-600 text-white font-medium rounded hover:bg-blue-700"
            >
              Submit Resolution
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: ADMIN REVIEW & CLOSURE */}
      <Modal
        isOpen={showAdminReviewModal}
        onClose={() => setShowAdminReviewModal(false)}
        title="Admin Closure Review (Section 5.3)"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 bg-green-50 border border-green-200 rounded text-green-800">
            <strong>Mandatory Admin Verification: </strong> Real panic alerts cannot be closed without explicit Admin sign-off and review note.
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Review Decision:</label>
            <select
              value={adminReviewStatus}
              onChange={(e) => setAdminReviewStatus(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="CLOSED">CLOSED (Approve closure and archive)</option>
              <option value="REOPENED">REOPENED (Require further investigation)</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Admin Sign-off Notes:</label>
            <textarea
              rows="3"
              placeholder="Confirming resolution was verified with site supervisor..."
              value={adminReviewNote}
              onChange={(e) => setAdminReviewNote(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowAdminReviewModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleAdminReview}
              className="px-3 py-1.5 bg-green-700 text-white font-medium rounded hover:bg-green-800"
            >
              Confirm Admin Review
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: FALSE ALARM CLAIM */}
      <Modal
        isOpen={showFalseAlarmModal}
        onClose={() => setShowFalseAlarmModal(false)}
        title="Report Accidental / False Alarm"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded text-amber-800">
            <strong>Safety Constraint: </strong> Reporting an accidental trigger does <em>not</em> cancel the alert.
            Supervisors and responders remain assigned until verified on site.
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Reason for Accidental Trigger:</label>
            <select
              value={falseAlarmReason}
              onChange={(e) => setFalseAlarmReason(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="ACCIDENTAL_BUTTON_PRESS">Accidental Button Press</option>
              <option value="DEVICE_DROPPED">Device Dropped / Pocket Press</option>
              <option value="MISTAKEN_THREAT">Mistaken Threat Perception</option>
              <option value="DEVICE_TEST_UNAUTHORIZED">Unauthorized Testing</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Notes / Context:</label>
            <textarea
              rows="2"
              value={falseAlarmNotes}
              onChange={(e) => setFalseAlarmNotes(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
              placeholder="Guard explanation..."
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowFalseAlarmModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleReportFalseAlarm}
              className="px-3 py-1.5 bg-slate-900 text-white font-medium rounded hover:bg-slate-800"
            >
              Submit False Alarm Report
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: SUPERVISOR CONFIRM FALSE ALARM */}
      <Modal
        isOpen={showConfirmFalseAlarmModal}
        onClose={() => setShowConfirmFalseAlarmModal(false)}
        title="Supervisor False Alarm Confirmation"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block text-gray-700 font-medium mb-1">Supervisor On-Site Verification Notes:</label>
            <textarea
              rows="3"
              placeholder="Confirm that you spoke to the guard, verified physical well-being, and confirmed no coercion..."
              value={confirmSupervisorNote}
              onChange={(e) => setConfirmSupervisorNote(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowConfirmFalseAlarmModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmFalseAlarm}
              className="px-3 py-1.5 bg-amber-700 text-white font-medium rounded hover:bg-amber-800"
            >
              Confirm False Alarm
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: POST-INCIDENT WELFARE NOTE */}
      <Modal
        isOpen={showWelfareModal}
        onClose={() => setShowWelfareModal(false)}
        title="Guard Welfare & Medical Follow-up Note"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block text-gray-700 font-medium mb-1">Welfare Check Summary:</label>
            <textarea
              rows="3"
              placeholder="Medical check-up conducted, counselling provided, relief guard arranged, leave sanctioned..."
              value={welfareNote}
              onChange={(e) => setWelfareNote(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowWelfareModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleAddWelfareNote}
              className="px-3 py-1.5 bg-purple-700 text-white font-medium rounded hover:bg-purple-800"
            >
              Save Welfare Record
            </button>
          </div>
        </div>
      </Modal>

      {/* SUB-MODAL: SCHEDULE DRILL */}
      <Modal
        isOpen={showDrillModal}
        onClose={() => setShowDrillModal(false)}
        title="Schedule Controlled Emergency Drill"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="block text-gray-700 font-medium mb-1">Drill Title:</label>
            <input
              type="text"
              placeholder="e.g. Q4 Night Intrusion Drill"
              value={drillTitle}
              onChange={(e) => setDrillTitle(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Site:</label>
            <select
              value={drillSiteId}
              onChange={(e) => setDrillSiteId(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="">Select Site</option>
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.site_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Scenario Type:</label>
            <select
              value={drillScenario}
              onChange={(e) => setDrillScenario(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            >
              <option value="INTRUSION_SIMULATION">Intrusion Simulation</option>
              <option value="FIRE_EMERGENCY_DRILL">Fire Emergency Drill</option>
              <option value="MEDICAL_EVACUATION_DRILL">Medical Evacuation Drill</option>
              <option value="DISPATCH_LATENCY_TEST">Dispatch Latency Test</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">Description / Brief:</label>
            <textarea
              rows="2"
              placeholder="Drill instructions and participating shifts..."
              value={drillDescription}
              onChange={(e) => setDrillDescription(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowDrillModal(false)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded"
            >
              Cancel
            </button>
            <button
              onClick={handleCreateDrill}
              className="px-3 py-1.5 bg-purple-700 text-white font-medium rounded hover:bg-purple-800"
            >
              Register Drill
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

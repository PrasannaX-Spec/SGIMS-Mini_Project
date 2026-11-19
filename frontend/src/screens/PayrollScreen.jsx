import React, { useState, useEffect } from 'react';
import {
  Banknote, Calendar, CheckCircle2, AlertTriangle, AlertCircle, Clock,
  FileText, Download, Plus, ChevronRight, RefreshCw, ShieldCheck,
  CreditCard, DollarSign, Users, ArrowUpRight, ArrowDownLeft, X,
  FileCheck, ShieldAlert, Check, Ban, Lock, Unlock, HelpCircle
} from 'lucide-react';
import { payrollApi } from '../api';

export default function PayrollScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isGuard = currentUser?.role === 'GUARD';

  const [activeTab, setActiveTab] = useState(isGuard ? 'payslips' : 'dashboard');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Core Data
  const [dashboardData, setDashboardData] = useState(null);
  const [checklistData, setChecklistData] = useState(null);
  const [selectedPeriod, setSelectedPeriod] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });

  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runResults, setRunResults] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);

  const [components, setComponents] = useState([]);
  const [structures, setStructures] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [advances, setAdvances] = useState([]);
  const [deductions, setDeductions] = useState([]);
  const [payslips, setPayslips] = useState([]);
  const [payments, setPayments] = useState([]);
  const [statutoryRules, setStatutoryRules] = useState([]);
  const [statutoryPayments, setStatutoryPayments] = useState([]);
  const [settlements, setSettlements] = useState([]);

  // Modals
  const [showCreateRunModal, setShowCreateRunModal] = useState(false);
  const [showComponentModal, setShowComponentModal] = useState(false);
  const [showStructureModal, setShowStructureModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [showAdvanceModal, setShowAdvanceModal] = useState(false);
  const [showDeductionModal, setShowDeductionModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showReversalModal, setShowReversalModal] = useState(false);
  const [showStatutoryModal, setShowStatutoryModal] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [reversalTarget, setReversalTarget] = useState(null);
  const [reversalReason, setReversalReason] = useState('');

  // Initial Load
  useEffect(() => {
    loadTabContent();
  }, [activeTab, selectedPeriod]);

  const loadTabContent = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'dashboard') {
        const [dashRes, checkRes] = await Promise.all([
          payrollApi.getDashboard(),
          payrollApi.getChecklist({ period_start: `${selectedPeriod}-01`, period_end: `${selectedPeriod}-28` })
        ]);
        setDashboardData(dashRes.data);
        setChecklistData(checkRes.data);
      } else if (activeTab === 'runs') {
        const res = await payrollApi.getRuns();
        setRuns(res.data.results || res.data || []);
      } else if (activeTab === 'components') {
        const [cRes, sRes] = await Promise.all([
          payrollApi.getComponents(),
          payrollApi.getStructures()
        ]);
        setComponents(cRes.data.results || cRes.data || []);
        setStructures(sRes.data.results || sRes.data || []);
      } else if (activeTab === 'assignments') {
        const [aRes, sRes] = await Promise.all([
          payrollApi.getAssignments(),
          payrollApi.getStructures()
        ]);
        setAssignments(aRes.data.results || aRes.data || []);
        setStructures(sRes.data.results || sRes.data || []);
      } else if (activeTab === 'advances') {
        const [advRes, dedRes] = await Promise.all([
          payrollApi.getAdvances(),
          payrollApi.getDeductions()
        ]);
        setAdvances(advRes.data.results || advRes.data || []);
        setDeductions(dedRes.data.results || dedRes.data || []);
      } else if (activeTab === 'payslips') {
        const [pRes, payRes] = await Promise.all([
          payrollApi.getPayslips(),
          isAdmin ? payrollApi.getPayments() : Promise.resolve({ data: [] })
        ]);
        setPayslips(pRes.data.results || pRes.data || []);
        setPayments(payRes.data.results || payRes.data || []);
      } else if (activeTab === 'statutory') {
        const [rRes, pRes] = await Promise.all([
          payrollApi.getStatutoryRules(),
          payrollApi.getStatutoryPayments()
        ]);
        setStatutoryRules(rRes.data.results || rRes.data || []);
        setStatutoryPayments(pRes.data.results || pRes.data || []);
      } else if (activeTab === 'settlement') {
        const res = await payrollApi.getFinalSettlements();
        setSettlements(res.data.results || res.data || []);
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || 'Failed to load data.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRun = async (run) => {
    setSelectedRun(run);
    try {
      const res = await payrollApi.getResults({ run_id: run.run_id });
      setRunResults(res.data.results || res.data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCalculateRun = async (runId) => {
    try {
      setLoading(true);
      await payrollApi.calculateRun(runId);
      setSuccessMsg("Payroll run calculated successfully.");
      loadTabContent();
      if (selectedRun?.run_id === runId) {
        handleSelectRun(selectedRun);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to calculate run.");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveRun = async (runId) => {
    try {
      setLoading(true);
      await payrollApi.approveRun(runId, overrideReason ? { override_reason: overrideReason } : {});
      setSuccessMsg("Payroll run approved and frozen successfully.");
      setShowOverrideModal(false);
      setOverrideReason('');
      loadTabContent();
    } catch (err) {
      if (err.response?.data && typeof err.response.data === 'string' && err.response.data.includes("override")) {
        setShowOverrideModal(true);
      } else {
        setError(err.response?.data?.detail || JSON.stringify(err.response?.data) || "Approval rejected.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReleaseRun = async (runId) => {
    try {
      setLoading(true);
      await payrollApi.releaseRun(runId);
      setSuccessMsg("Run released for payment! Immutable payslips generated.");
      loadTabContent();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to release run.");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (val) => {
    if (val === null || val === undefined) return '₹0.00';
    return `₹${Number(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Control */}
      <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="p-2 bg-slate-900 text-white rounded-md">
                <Banknote className="w-5 h-5" />
              </span>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Module 14: Payroll & Compensation</h1>
                <p className="text-xs text-slate-500">
                  Explainable salary calculation, statutory rules, zero-floor net pay, and dual-admin approval
                </p>
              </div>
            </div>
          </div>

          {isAdmin && (
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-md">
                <Calendar className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-semibold text-slate-600">Period:</span>
                <input
                  type="month"
                  value={selectedPeriod}
                  onChange={(e) => setSelectedPeriod(e.target.value)}
                  className="text-xs font-bold text-slate-900 bg-transparent outline-hidden cursor-pointer"
                />
              </div>

              <button
                onClick={() => setShowCreateRunModal(true)}
                className="inline-flex items-center space-x-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-md text-xs font-semibold shadow-xs transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Run</span>
              </button>
            </div>
          )}
        </div>

        {/* Notifications */}
        {error && (
          <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-md text-rose-800 text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
        {successMsg && (
          <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-md text-emerald-800 text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>{successMsg}</span>
            </div>
            <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Sub Navigation */}
        <div className="mt-5 border-t border-slate-100 pt-3 flex flex-wrap gap-1">
          {isAdmin && [
            { id: 'dashboard', label: 'Overview & Checklist' },
            { id: 'runs', label: 'Payroll Runs & Approvals' },
            { id: 'components', label: 'Components & Structures' },
            { id: 'assignments', label: 'Guard Salary Assignments' },
            { id: 'advances', label: 'Advances & Deductions' },
            { id: 'payslips', label: 'Payslips & Bank Disbursal' },
            { id: 'statutory', label: 'Statutory Rules (PF/ESI/PT)' },
            { id: 'settlement', label: 'Final Settlement' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
                activeTab === tab.id
                  ? 'bg-slate-900 text-white font-semibold'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
          {isGuard && (
            <button
              className="px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 text-white"
            >
              My Payslips & Advances
            </button>
          )}
        </div>
      </div>

      {/* TAB 1: OVERVIEW & PRE-RUN CHECKLIST */}
      {activeTab === 'dashboard' && (
        <div className="space-y-5">
          {/* Top Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 rounded-md p-4 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase">Active Guards</span>
                <Users className="w-4 h-4 text-slate-400" />
              </div>
              <p className="text-2xl font-bold text-slate-900 mt-2">{dashboardData?.total_active_guards ?? '—'}</p>
              <p className="text-[11px] text-slate-400 mt-1">Eligible for {selectedPeriod} payroll</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-md p-4 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase">Pending Approvals</span>
                <Clock className="w-4 h-4 text-amber-500" />
              </div>
              <p className="text-2xl font-bold text-amber-600 mt-2">{dashboardData?.pending_run_approvals ?? '—'}</p>
              <p className="text-[11px] text-slate-400 mt-1">Runs awaiting designated second admin</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-md p-4 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase">Pending Payments</span>
                <CreditCard className="w-4 h-4 text-blue-500" />
              </div>
              <p className="text-2xl font-bold text-blue-600 mt-2">{dashboardData?.pending_payments_count ?? '—'}</p>
              <p className="text-[11px] text-slate-400 mt-1">Released runs awaiting bank disbursal</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-md p-4 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 uppercase">Advances Outstanding</span>
                <DollarSign className="w-4 h-4 text-emerald-500" />
              </div>
              <p className="text-2xl font-bold text-emerald-700 mt-2">{formatCurrency(dashboardData?.total_advances_outstanding)}</p>
              <p className="text-[11px] text-slate-400 mt-1">Under ledger recovery plan</p>
            </div>
          </div>

          {/* Pre-Run Checklist Banner */}
          <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Pre-Run Checklist for Period {selectedPeriod}</h3>
                <p className="text-xs text-slate-500">
                  Pre-flight validation checks before generating final payroll results
                </p>
              </div>
              <button
                onClick={loadTabContent}
                className="inline-flex items-center space-x-1.5 text-xs text-slate-600 hover:text-slate-900 font-medium px-2.5 py-1.5 border border-slate-200 rounded-md hover:bg-slate-50"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Re-check</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Check 1: Attendance Period Lock */}
              <div className={`p-4 rounded-md border ${
                checklistData?.attendance_locked ? 'bg-emerald-50/50 border-emerald-200' : 'bg-amber-50/50 border-amber-200'
              }`}>
                <div className="flex items-center space-x-2">
                  {checklistData?.attendance_locked ? (
                    <Lock className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <Unlock className="w-4 h-4 text-amber-600" />
                  )}
                  <span className="text-xs font-bold text-slate-900">Attendance Lock Status</span>
                </div>
                <p className="text-xs mt-2 text-slate-700 font-medium">
                  {checklistData?.attendance_locked
                    ? 'Period is LOCKED. Final approved run permitted.'
                    : 'Period is UNLOCKED. Any run will be PROVISIONAL.'}
                </p>
                <p className="text-[11px] text-slate-500 mt-1">Module 6 Locked Attendance Enforcement (AC14.9, AC14.10)</p>
              </div>

              {/* Check 2: Missing Salary Structures */}
              <div className={`p-4 rounded-md border ${
                (checklistData?.missing_salary_structures_count || 0) === 0 ? 'bg-emerald-50/50 border-emerald-200' : 'bg-rose-50/50 border-rose-200'
              }`}>
                <div className="flex items-center space-x-2">
                  {(checklistData?.missing_salary_structures_count || 0) === 0 ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-rose-600" />
                  )}
                  <span className="text-xs font-bold text-slate-900">Salary Structure Assignment</span>
                </div>
                <p className="text-xs mt-2 text-slate-700 font-medium">
                  {checklistData?.missing_salary_structures_count === 0
                    ? 'All active guards have an assigned salary structure.'
                    : `${checklistData?.missing_salary_structures_count} guards lack an active salary structure.`}
                </p>
                <p className="text-[11px] text-slate-500 mt-1">Effective-dated assignments required (AC14.6)</p>
              </div>

              {/* Check 3: Minimum Wage Configuration */}
              <div className={`p-4 rounded-md border ${
                checklistData?.minimum_wage_rules_configured ? 'bg-emerald-50/50 border-emerald-200' : 'bg-slate-50 border-slate-200'
              }`}>
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-bold text-slate-900">Minimum Wage Baseline</span>
                </div>
                <p className="text-xs mt-2 text-slate-700 font-medium">
                  {checklistData?.minimum_wage_rules_configured
                    ? 'State minimum wage tables active.'
                    : 'No minimum wage thresholds configured.'}
                </p>
                <p className="text-[11px] text-slate-500 mt-1">Karnataka minimum wage check (AC14.7)</p>
              </div>
            </div>

            {/* Blocking reasons alert */}
            {checklistData?.blocking_reasons?.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                <span className="text-xs font-bold text-amber-900 block mb-1">Attention Required Before Final Run:</span>
                <ul className="list-disc pl-5 text-xs text-amber-800 space-y-0.5">
                  {checklistData.blocking_reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: PAYROLL RUNS & APPROVALS */}
      {activeTab === 'runs' && (
        <div className="space-y-5">
          <div className="bg-white border border-slate-200 rounded-md overflow-hidden shadow-xs">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Payroll Runs Register</h3>
                <p className="text-xs text-slate-500">Track draft, calculated, approved, and released payroll runs</p>
              </div>
              <button
                onClick={() => setShowCreateRunModal(true)}
                className="px-3 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
              >
                + New Payroll Run
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-4">Period</th>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Guards</th>
                    <th className="py-2.5 px-4">Result Hash</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="py-6 text-center text-slate-400">
                        No payroll runs created yet. Click "+ New Payroll Run" to start.
                      </td>
                    </tr>
                  ) : (
                    runs.map((r) => (
                      <tr key={r.run_id} className="hover:bg-slate-50 transition">
                        <td className="py-3 px-4 font-bold text-slate-900">{r.period_reference}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            r.run_type === 'FINAL' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                            {r.run_type}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            r.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' :
                            r.status === 'RELEASED' ? 'bg-blue-100 text-blue-800' :
                            r.status === 'PAID' ? 'bg-purple-100 text-purple-800' :
                            r.status === 'CALCULATED' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'
                          }`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="py-3 px-4">{r.results_count ?? '—'}</td>
                        <td className="py-3 px-4 font-mono text-[10px] text-slate-400">
                          {r.result_hash ? `${r.result_hash.substring(0, 16)}...` : 'Pending calculation'}
                        </td>
                        <td className="py-3 px-4 text-right space-x-1.5">
                          <button
                            onClick={() => handleSelectRun(r)}
                            className="px-2.5 py-1 text-slate-700 border border-slate-200 rounded-md hover:bg-slate-100 text-xs font-medium"
                          >
                            View
                          </button>
                          {['DRAFT', 'CALCULATED', 'UNDER_REVIEW'].includes(r.status) && (
                            <button
                              onClick={() => handleCalculateRun(r.run_id)}
                              className="px-2.5 py-1 bg-slate-100 text-slate-800 border border-slate-300 rounded-md hover:bg-slate-200 text-xs font-semibold"
                            >
                              Calculate
                            </button>
                          )}
                          {['CALCULATED', 'UNDER_REVIEW'].includes(r.status) && (
                            <button
                              onClick={() => handleApproveRun(r.run_id)}
                              className="px-2.5 py-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 text-xs font-semibold"
                            >
                              Approve
                            </button>
                          )}
                          {r.status === 'APPROVED' && (
                            <button
                              onClick={() => handleReleaseRun(r.run_id)}
                              className="px-2.5 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-xs font-semibold"
                            >
                              Release Payout
                            </button>
                          )}
                          {['RELEASED', 'PAID', 'PARTIALLY_PAID'].includes(r.status) && (
                            <a
                              href={payrollApi.exportBankFileUrl(r.run_id)}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center space-x-1 px-2.5 py-1 bg-slate-900 text-white rounded-md hover:bg-slate-800 text-xs font-semibold"
                            >
                              <Download className="w-3 h-3" />
                              <span>Bank File</span>
                            </a>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Run Detail Breakdown Drawer / Table */}
          {selectedRun && (
            <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h4 className="text-sm font-bold text-slate-900">
                    Run Calculation Breakdown: {selectedRun.period_reference} ({selectedRun.status})
                  </h4>
                  <p className="text-xs text-slate-500 font-mono">
                    Integrity Hash: {selectedRun.result_hash || 'Unapproved'}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedRun(null)}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2 px-3">Guard</th>
                      <th className="py-2 px-3">Days</th>
                      <th className="py-2 px-3">OT (Mins)</th>
                      <th className="py-2 px-3 text-right">Gross Earnings</th>
                      <th className="py-2 px-3 text-right">Employee Deductions</th>
                      <th className="py-2 px-3 text-right font-bold">Net Pay</th>
                      <th className="py-2 px-3 text-right">Employer Contrib.</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3 text-right">Lines</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {runResults.map((res) => (
                      <tr key={res.result_id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 font-semibold text-slate-900">
                          {res.calculation_details?.guard_name || res.guard_id}
                          <span className="block text-[10px] text-slate-400 font-normal">
                            {res.calculation_details?.employee_code}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">{res.paid_days}</td>
                        <td className="py-2.5 px-3">{res.overtime_minutes}</td>
                        <td className="py-2.5 px-3 text-right font-medium text-slate-800">
                          {formatCurrency(res.gross_earnings)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-rose-600">
                          -{formatCurrency(res.employee_deductions)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                          {formatCurrency(res.net_pay)}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-500">
                          {formatCurrency(res.employer_contributions)}
                        </td>
                        <td className="py-2.5 px-3">
                          {res.is_held ? (
                            <span className="px-1.5 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded text-[10px] font-bold">
                              Held (Min Wage)
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[10px] font-bold">
                              Valid
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            onClick={() => setSelectedResult(res)}
                            className="px-2 py-1 text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md font-medium"
                          >
                            Explain
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Calculation Explanation Dialog (PRD AC14.64) */}
          {selectedResult && (
            <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
              <div className="bg-white rounded-md border border-slate-200 max-w-xl w-full p-6 shadow-xl space-y-4 max-h-[85vh] overflow-y-auto">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Calculation Explanation (AC14.64)</h3>
                    <p className="text-xs text-slate-500">
                      {selectedResult.calculation_details?.guard_name} ({selectedResult.calculation_details?.employee_code})
                    </p>
                  </div>
                  <button onClick={() => setSelectedResult(null)} className="text-slate-400 hover:text-slate-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-2 p-3 bg-slate-50 border border-slate-200 rounded-md text-center text-xs">
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Gross Earnings</span>
                    <p className="text-sm font-bold text-slate-900">{formatCurrency(selectedResult.gross_earnings)}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Deductions</span>
                    <p className="text-sm font-bold text-rose-600">-{formatCurrency(selectedResult.employee_deductions)}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Net Pay (Zero-Floor)</span>
                    <p className="text-sm font-bold text-emerald-700">{formatCurrency(selectedResult.net_pay)}</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Itemized Line Items</h4>
                  <div className="border border-slate-200 rounded-md divide-y divide-slate-100 text-xs">
                    {selectedResult.lines?.map((line, idx) => (
                      <div key={idx} className="p-2.5 flex items-center justify-between hover:bg-slate-50">
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                              line.line_type === 'EARNING' ? 'bg-emerald-50 text-emerald-700' :
                              line.line_type === 'EMPLOYER_CONTRIBUTION' ? 'bg-blue-50 text-blue-700' : 'bg-rose-50 text-rose-700'
                            }`}>
                              {line.line_type}
                            </span>
                            <span className="font-bold text-slate-900">{line.code}</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">{line.description}</p>
                          {line.formula_reference && (
                            <p className="text-[10px] font-mono text-slate-400">Formula: {line.formula_reference}</p>
                          )}
                        </div>
                        <span className={`font-bold ${
                          line.line_type === 'EARNING' ? 'text-slate-900' :
                          line.line_type === 'EMPLOYER_CONTRIBUTION' ? 'text-blue-700' : 'text-rose-600'
                        }`}>
                          {line.line_type === 'EARNING' ? '+' : '-'}{formatCurrency(line.amount)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border-t border-slate-100 pt-3 flex justify-end">
                  <button
                    onClick={() => setSelectedResult(null)}
                    className="px-4 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SALARY COMPONENTS & STRUCTURES */}
      {activeTab === 'components' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Components Catalog */}
          <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Salary Components Catalog</h3>
                <p className="text-xs text-slate-500">Earnings, recurring deductions, and employer contributions</p>
              </div>
              <button
                onClick={() => setShowComponentModal(true)}
                className="px-2.5 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                + New Component
              </button>
            </div>

            <div className="space-y-2">
              {components.map((c) => (
                <div key={c.component_id} className="p-3 border border-slate-200 rounded-md flex items-center justify-between hover:bg-slate-50">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-xs text-slate-900">{c.component_code}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                        c.component_type === 'EARNING' ? 'bg-emerald-50 text-emerald-700' :
                        c.component_type === 'EMPLOYER_CONTRIBUTION' ? 'bg-blue-50 text-blue-700' : 'bg-rose-50 text-rose-700'
                      }`}>
                        {c.component_type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1">{c.component_name}</p>
                    <div className="flex items-center space-x-2 text-[10px] text-slate-400 mt-0.5">
                      <span>Proration: {c.proration_enabled ? 'Yes' : 'No'}</span>
                      <span>•</span>
                      <span>Order: {c.display_order}</span>
                    </div>
                  </div>
                  <span className="text-xs font-semibold text-slate-400">Active</span>
                </div>
              ))}
            </div>
          </div>

          {/* Salary Structures */}
          <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Configured Salary Structures</h3>
                <p className="text-xs text-slate-500">Versioned packages assigned to security guards</p>
              </div>
              <button
                onClick={() => setShowStructureModal(true)}
                className="px-2.5 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                + Create Structure
              </button>
            </div>

            <div className="space-y-3">
              {structures.map((s) => (
                <div key={s.structure_id} className="p-3.5 border border-slate-200 rounded-md bg-slate-50/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-bold text-xs text-slate-900">{s.name}</span>
                      <span className="ml-2 text-[10px] text-slate-500">v{s.version}</span>
                    </div>
                    <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded text-[10px] font-bold">
                      {s.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">Effective: {s.effective_from} to {s.effective_to || 'Indefinite'}</p>

                  <div className="bg-white border border-slate-200 rounded-md p-2 divide-y divide-slate-100 text-xs">
                    {s.lines?.map((line, idx) => (
                      <div key={idx} className="py-1 flex items-center justify-between">
                        <span className="text-slate-600">{line.component_name || line.component_code}</span>
                        <span className="font-semibold text-slate-900">{formatCurrency(line.amount)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: GUARD SALARY ASSIGNMENTS */}
      {activeTab === 'assignments' && (
        <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Effective-Dated Salary Assignments</h3>
              <p className="text-xs text-slate-500">Assign versioned salary packages to individual or grouped guards</p>
            </div>
            <button
              onClick={() => setShowAssignModal(true)}
              className="px-3 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
            >
              + Assign Structure
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">Guard Reference</th>
                  <th className="py-2.5 px-4">Salary Structure</th>
                  <th className="py-2.5 px-4">Pay Basis</th>
                  <th className="py-2.5 px-4">Effective Dates</th>
                  <th className="py-2.5 px-4">Reason</th>
                  <th className="py-2.5 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {assignments.map((asgn) => (
                  <tr key={asgn.assignment_id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-bold text-slate-900">{asgn.guard_id}</td>
                    <td className="py-3 px-4 font-semibold text-slate-700">{asgn.structure_name || asgn.structure}</td>
                    <td className="py-3 px-4">{asgn.pay_basis}</td>
                    <td className="py-3 px-4">{asgn.effective_from} to {asgn.effective_to || 'Ongoing'}</td>
                    <td className="py-3 px-4 text-slate-500">{asgn.reason}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[10px] font-bold">
                        {asgn.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: ADVANCES & MANUAL DEDUCTIONS */}
      {activeTab === 'advances' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Advances Ledger */}
          <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Guard Advances & Loans</h3>
                <p className="text-xs text-slate-500">Append-only recovery ledger with zero-floor safety</p>
              </div>
              <button
                onClick={() => setShowAdvanceModal(true)}
                className="px-2.5 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                + Issue Advance
              </button>
            </div>

            <div className="space-y-3">
              {advances.map((adv) => (
                <div key={adv.advance_id} className="p-3 border border-slate-200 rounded-md space-y-1.5 hover:bg-slate-50">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">Advance: {formatCurrency(adv.amount)}</span>
                    <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[10px] font-bold">
                      {adv.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600">Reason: {adv.reason}</p>
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-100">
                    <span>Current Balance: <strong className="text-slate-900">{formatCurrency(adv.current_balance)}</strong></span>
                    <span>Max/Month: {formatCurrency(adv.max_per_instalment)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Manual Deductions */}
          <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Approved Manual Deductions</h3>
                <p className="text-xs text-slate-500">No automatic deductions from incidents or attendance flags</p>
              </div>
              <button
                onClick={() => setShowDeductionModal(true)}
                className="px-2.5 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                + Add Deduction
              </button>
            </div>

            <div className="space-y-3">
              {deductions.map((d) => (
                <div key={d.deduction_id} className="p-3 border border-slate-200 rounded-md space-y-1.5 hover:bg-slate-50">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900">{d.category}: {formatCurrency(d.amount)}</span>
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-bold">
                      {d.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600">{d.reason}</p>
                  <p className="text-[11px] text-slate-400">Reference: {d.source_reference || 'N/A'}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: PAYSLIPS & BANK DISBURSAL */}
      {activeTab === 'payslips' && (
        <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Immutable Payslips Register</h3>
              <p className="text-xs text-slate-500">Cryptographically hashed payslips released after run approval</p>
            </div>
            {isAdmin && (
              <button
                onClick={() => setShowPaymentModal(true)}
                className="px-3 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                + Record External Payment
              </button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">Payslip Number</th>
                  <th className="py-2.5 px-4">Guard Reference</th>
                  <th className="py-2.5 px-4">Released Date</th>
                  <th className="py-2.5 px-4">Integrity Hash</th>
                  <th className="py-2.5 px-4 text-right">PDF File</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {payslips.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="py-6 text-center text-slate-400">
                      No released payslips available. Payslips generate when a payroll run is released.
                    </td>
                  </tr>
                ) : (
                  payslips.map((ps) => (
                    <tr key={ps.payslip_id} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-bold text-slate-900">{ps.payslip_number}</td>
                      <td className="py-3 px-4">{ps.guard_id}</td>
                      <td className="py-3 px-4">{new Date(ps.released_at).toLocaleDateString('en-IN')}</td>
                      <td className="py-3 px-4 font-mono text-[10px] text-slate-400">
                        {ps.pdf_hash ? `${ps.pdf_hash.substring(0, 20)}...` : 'N/A'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="inline-flex items-center space-x-1 text-slate-700 hover:text-slate-900 font-semibold cursor-pointer">
                          <FileText className="w-3.5 h-3.5" />
                          <span>View PDF</span>
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 7: STATUTORY RULES & COMPLIANCE */}
      {activeTab === 'statutory' && (
        <div className="space-y-5">
          <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Generic Statutory Rule Sets (PRD Section 9)</h3>
                <p className="text-xs text-slate-500">
                  Dual-admin approval required. Values entered after review with CA/mentor.
                </p>
              </div>
              <button
                onClick={() => setShowStatutoryModal(true)}
                className="px-3 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                + Configure Scheme
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {statutoryRules.map((r) => (
                <div key={r.rule_set_id} className="p-4 border border-slate-200 rounded-md bg-slate-50/50 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-slate-900">{r.scheme}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      r.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {r.status} (v{r.version})
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-1">
                    <div>Employee Rate: <strong>{r.employee_rate ? `${floatToPercent(r.employee_rate)}%` : 'Blank'}</strong></div>
                    <div>Employer Rate: <strong>{r.employer_rate ? `${floatToPercent(r.employer_rate)}%` : 'Blank'}</strong></div>
                    <div>Wage Floor: <strong>{r.wage_floor ? formatCurrency(r.wage_floor) : 'None'}</strong></div>
                    <div>Wage Ceiling: <strong>{r.wage_ceiling ? formatCurrency(r.wage_ceiling) : 'None'}</strong></div>
                  </div>
                  {r.status === 'DRAFT' && (
                    <div className="pt-2 border-t border-slate-200 flex justify-end">
                      <button
                        onClick={async () => {
                          try {
                            await payrollApi.approveStatutoryRule(r.rule_set_id);
                            setSuccessMsg("Rule activated by second designated admin!");
                            loadTabContent();
                          } catch (err) {
                            setError(err.response?.data?.detail || "Dual-admin approval failed.");
                          }
                        }}
                        className="px-2.5 py-1 bg-emerald-600 text-white rounded text-xs font-semibold hover:bg-emerald-700"
                      >
                        Approve Activation (2nd Admin)
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 8: FULL AND FINAL SETTLEMENT */}
      {activeTab === 'settlement' && (
        <div className="bg-white border border-slate-200 rounded-md p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Full and Final Settlement (Dual-Approval)</h3>
              <p className="text-xs text-slate-500">Calculate exit settlement, deduct advance balances, and require 2 approvers</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">Guard Reference</th>
                  <th className="py-2.5 px-4">Exit Date</th>
                  <th className="py-2.5 px-4 text-right">Final Pay</th>
                  <th className="py-2.5 px-4 text-right">Advance Bal.</th>
                  <th className="py-2.5 px-4 text-right font-bold">Total Settlement</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {settlements.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="py-6 text-center text-slate-400">
                      No active exit settlements being processed.
                    </td>
                  </tr>
                ) : (
                  settlements.map((s) => (
                    <tr key={s.settlement_id} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-bold text-slate-900">{s.guard_id}</td>
                      <td className="py-3 px-4">{s.exit_date}</td>
                      <td className="py-3 px-4 text-right">{formatCurrency(s.final_pay)}</td>
                      <td className="py-3 px-4 text-right text-rose-600">-{formatCurrency(s.advance_balance)}</td>
                      <td className="py-3 px-4 text-right font-bold text-emerald-700">{formatCurrency(s.settlement_total)}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-[10px] font-bold">
                          {s.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {s.status === 'UNDER_REVIEW' && (
                          <button
                            onClick={async () => {
                              try {
                                await payrollApi.secondApproveFinalSettlement(s.settlement_id);
                                setSuccessMsg("Settlement fully approved by second admin!");
                                loadTabContent();
                              } catch (err) {
                                setError(err.response?.data?.detail || "Approval failed.");
                              }
                            }}
                            className="px-2.5 py-1 bg-emerald-600 text-white rounded text-xs font-semibold hover:bg-emerald-700"
                          >
                            2nd Approval
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
      )}

      {/* CREATE RUN MODAL */}
      {showCreateRunModal && (
        <CreateRunModal
          defaultPeriod={selectedPeriod}
          onClose={() => setShowCreateRunModal(false)}
          onCreated={() => {
            setShowCreateRunModal(false);
            setSuccessMsg("Payroll run created in DRAFT status.");
            loadTabContent();
          }}
        />
      )}

      {/* OVERRIDE REASON MODAL */}
      {showOverrideModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-md border border-slate-200 max-w-md w-full p-5 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Minimum Wage Override Justification (AC14.8)</h3>
            <p className="text-xs text-slate-600">
              Some guards have calculated daily earnings below Karnataka minimum wage. Document the authorized reason to approve:
            </p>
            <textarea
              rows="3"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Enter documented justification..."
              className="w-full text-xs p-2.5 border border-slate-300 rounded-md outline-hidden focus:border-slate-900"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowOverrideModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 border border-slate-200 rounded-md hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleApproveRun(selectedRun.run_id)}
                disabled={!overrideReason.trim()}
                className="px-3 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 disabled:opacity-50"
              >
                Confirm Override & Approve
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function floatToPercent(val) {
  if (!val) return '0';
  return (Number(val) * 100).toFixed(1);
}

// ----------------------------------------------------------------------------
// Simple Modal: Create Run
// ----------------------------------------------------------------------------
function CreateRunModal({ defaultPeriod, onClose, onCreated }) {
  const [period, setPeriod] = useState(defaultPeriod);
  const [runType, setRunType] = useState('FINAL');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      const [year, month] = period.split('-');
      const numDays = new Date(year, month, 0).getDate();
      await payrollApi.createRun({
        period_reference: period,
        period_start: `${period}-01`,
        period_end: `${period}-${String(numDays).padStart(2, '0')}`,
        run_type: runType
      });
      onCreated();
    } catch (error) {
      setErr(error.response?.data?.detail || error.message || "Failed to create run.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-md border border-slate-200 max-w-sm w-full p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <h3 className="text-sm font-bold text-slate-900">Initiate Payroll Run</h3>
          <button onClick={onClose}><X className="w-4 h-4 text-slate-400" /></button>
        </div>

        {err && <div className="p-2 bg-rose-50 text-rose-700 text-xs rounded border border-rose-200">{err}</div>}

        <form onSubmit={handleSubmit} className="space-y-3 text-xs">
          <div>
            <label className="font-semibold text-slate-700 block mb-1">Period Reference</label>
            <input
              type="month"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-md outline-hidden focus:border-slate-900"
              required
            />
          </div>

          <div>
            <label className="font-semibold text-slate-700 block mb-1">Run Type</label>
            <select
              value={runType}
              onChange={(e) => setRunType(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-md outline-hidden focus:border-slate-900"
            >
              <option value="FINAL">Final Run (Requires Locked Attendance)</option>
              <option value="PROVISIONAL">Provisional Run (Draft)</option>
              <option value="SUPPLEMENTARY">Supplementary Run (Corrections)</option>
            </select>
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 border border-slate-200 text-slate-600 rounded-md hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-3.5 py-1.5 bg-slate-900 text-white font-semibold rounded-md hover:bg-slate-800 disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Run'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

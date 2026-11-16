import React, { useState, useEffect } from 'react';
import {
  Receipt,
  DollarSign,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Plus,
  RefreshCw,
  FileDown,
  Send,
  XCircle,
  RotateCcw,
  FileText,
  Check,
  Search,
  Sliders,
  Eye,
  HelpCircle,
  CreditCard,
  Building2,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { billingApi, masterDataApi } from '../api';

export default function BillingInvoicesScreen({ currentUser }) {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'invoices' | 'run' | 'payments' | 'settings'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Data states
  const [metrics, setMetrics] = useState({
    total_invoiced: '0.00',
    total_paid: '0.00',
    total_outstanding: '0.00',
    total_overdue: '0.00',
    draft_count: 0,
    sent_count: 0,
    paid_count: 0,
    overdue_count: 0
  });
  const [ageingData, setAgeingData] = useState({
    summary: { current_0_30: '0.00', days_31_60: '0.00', days_61_90: '0.00', days_90_plus: '0.00', total_outstanding: '0.00' },
    clients: []
  });
  const [invoices, setInvoices] = useState([]);
  const [clientsList, setClientsList] = useState([]);
  const [companySettings, setCompanySettings] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [clientFilter, setClientFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals & Active selections
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [invoiceDetail, setInvoiceDetail] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showManualLineModal, setShowManualLineModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [showAnnexureModal, setShowAnnexureModal] = useState(false);
  const [annexureData, setAnnexureData] = useState([]);

  // Billing Run Form
  const now = new Date();
  const firstDayPrevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().split('T')[0];
  const lastDayPrevMonth = new Date(now.getFullYear(), now.getMonth(), 0).toISOString().split('T')[0];

  const [runPeriodStart, setRunPeriodStart] = useState(firstDayPrevMonth);
  const [runPeriodEnd, setRunPeriodEnd] = useState(lastDayPrevMonth);
  const [runClientId, setRunClientId] = useState('');
  const [allowUnlocked, setAllowUnlocked] = useState(false);
  const [unlockedReason, setUnlockedReason] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [runResult, setRunResult] = useState(null);

  // Manual line form
  const [manualLine, setManualLine] = useState({
    description: '',
    quantity: '1',
    unit_rate: '',
    tax_rate: '18.00',
    is_negative: false,
    manual_reason: '',
    client_visible_description: ''
  });

  // Payment form
  const [paymentForm, setPaymentForm] = useState({
    payment_date: new Date().toISOString().split('T')[0],
    amount: '',
    payment_method: 'NEFT',
    reference_no: '',
    tds_amount: '',
    tds_section: '194C',
    other_deductions_amount: '',
    notes: ''
  });

  // Reversal form
  const [reversalPaymentId, setReversalPaymentId] = useState(null);
  const [reversalReason, setReversalReason] = useState('');
  const [showReversalModal, setShowReversalModal] = useState(false);

  // Cancel form
  const [cancelReason, setCancelReason] = useState('');
  const [clientVisibleCancelReason, setClientVisibleCancelReason] = useState('');

  // --------------------------------------------------------------------------
  // Lifecycle & Initial Fetch
  // --------------------------------------------------------------------------
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsRes, ageingRes, invoicesRes, clientsRes, settingsRes] = await Promise.allSettled([
        billingApi.getDashboardMetrics(),
        billingApi.getReceivablesAgeing(),
        billingApi.getInvoices(),
        masterDataApi.getClients(),
        billingApi.getCompanySettings()
      ]);

      if (metricsRes.status === 'fulfilled') setMetrics(metricsRes.value.data);
      if (ageingRes.status === 'fulfilled') setAgeingData(ageingRes.value.data);
      if (invoicesRes.status === 'fulfilled') setInvoices(invoicesRes.value.data);
      if (clientsRes.status === 'fulfilled') setClientsList(clientsRes.value.data);
      if (settingsRes.status === 'fulfilled') setCompanySettings(settingsRes.value.data);
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Failed to load billing data.');
    } finally {
      setLoading(false);
    }
  };

  const refreshInvoices = async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (clientFilter) params.client_id = clientFilter;
      const res = await billingApi.getInvoices(params);
      setInvoices(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (activeTab === 'invoices') {
      refreshInvoices();
    }
  }, [statusFilter, clientFilter]);

  // --------------------------------------------------------------------------
  // Handlers: Billing Run & Preview
  // --------------------------------------------------------------------------
  const handlePreviewBilling = async () => {
    if (!runClientId) {
      setError('Please select a specific client organization to preview calculation.');
      return;
    }
    setLoading(true);
    setError(null);
    setPreviewData(null);
    try {
      const res = await billingApi.previewBilling({
        client_id: runClientId,
        period_start: runPeriodStart,
        period_end: runPeriodEnd,
        is_unlocked_period_override: allowUnlocked,
        unlocked_period_reason: unlockedReason
      });
      setPreviewData(res.data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to generate billing preview.');
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteBillingRun = async () => {
    if (allowUnlocked && !unlockedReason.trim()) {
      setError('A justification reason is required when overriding unlocked attendance periods.');
      return;
    }
    setLoading(true);
    setError(null);
    setRunResult(null);
    try {
      const res = await billingApi.runBilling({
        period_start: runPeriodStart,
        period_end: runPeriodEnd,
        client_ids: runClientId ? [runClientId] : null,
        is_unlocked_period_override: allowUnlocked,
        unlocked_period_reason: unlockedReason
      });
      setRunResult(res.data);
      setSuccessMsg(`Billing run completed! Created: ${res.data.drafts_created?.length || 0}, Refreshed: ${res.data.drafts_refreshed?.length || 0}`);
      await refreshInvoices();
      const mRes = await billingApi.getDashboardMetrics();
      setMetrics(mRes.data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to execute billing run.');
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------------------------
  // Handlers: Invoices Actions
  // --------------------------------------------------------------------------
  const openInvoiceDetail = async (invoiceId) => {
    setLoading(true);
    try {
      const res = await billingApi.getInvoiceDetail(invoiceId);
      setInvoiceDetail(res.data);
      setShowDetailModal(true);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to fetch invoice details.');
    } finally {
      setLoading(false);
    }
  };

  const handleIssueInvoice = async (invoiceId) => {
    if (!window.confirm('Are you sure you want to issue this invoice? Issued invoices are legally immutable.')) return;
    setLoading(true);
    setError(null);
    try {
      const res = await billingApi.issueInvoice(invoiceId);
      setSuccessMsg(`Invoice ${res.data.invoice_no} issued successfully! Immutable PDF hash recorded.`);
      await refreshInvoices();
      const mRes = await billingApi.getDashboardMetrics();
      setMetrics(mRes.data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to issue invoice.');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelInvoice = async () => {
    if (!cancelReason.trim()) {
      setError('Cancellation reason is required.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await billingApi.cancelInvoice(selectedInvoice.invoice_id, {
        cancelled_reason: cancelReason,
        client_visible_cancellation_reason: clientVisibleCancelReason
      });
      setSuccessMsg(`Invoice ${selectedInvoice.invoice_no} cancelled successfully.`);
      setShowCancelModal(false);
      setCancelReason('');
      setClientVisibleCancelReason('');
      await refreshInvoices();
      const mRes = await billingApi.getDashboardMetrics();
      setMetrics(mRes.data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to cancel invoice.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateReplacement = async (invoiceId) => {
    if (!window.confirm('Generate a fresh replacement draft linked to this cancelled invoice?')) return;
    setLoading(true);
    setError(null);
    try {
      const res = await billingApi.createReplacement(invoiceId);
      setSuccessMsg(`Replacement draft ${res.data.draft_reference} created successfully.`);
      await refreshInvoices();
      setActiveTab('invoices');
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to create replacement draft.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddManualLine = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await billingApi.addManualLine(selectedInvoice.invoice_id, {
        ...manualLine,
        quantity: parseFloat(manualLine.quantity),
        unit_rate: parseFloat(manualLine.unit_rate),
        tax_rate: parseFloat(manualLine.tax_rate)
      });
      setSuccessMsg('Manual line added to draft.');
      setShowManualLineModal(false);
      setManualLine({
        description: '',
        quantity: '1',
        unit_rate: '',
        tax_rate: '18.00',
        is_negative: false,
        manual_reason: '',
        client_visible_description: ''
      });
      await refreshInvoices();
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to add manual line.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecordPayment = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const deductions = [];
      if (parseFloat(paymentForm.tds_amount || '0') > 0) {
        deductions.push({
          deduction_type: 'TDS',
          section: paymentForm.tds_section,
          amount: parseFloat(paymentForm.tds_amount)
        });
      }
      if (parseFloat(paymentForm.other_deductions_amount || '0') > 0) {
        deductions.push({
          deduction_type: 'OTHER',
          amount: parseFloat(paymentForm.other_deductions_amount)
        });
      }

      await billingApi.recordPayment(selectedInvoice.invoice_id, {
        payment_date: paymentForm.payment_date,
        amount: parseFloat(paymentForm.amount),
        payment_method: paymentForm.payment_method,
        reference_no: paymentForm.reference_no,
        notes: paymentForm.notes,
        deductions
      });

      setSuccessMsg(`Payment of ₹${paymentForm.amount} recorded successfully.`);
      setShowPaymentModal(false);
      setPaymentForm({
        payment_date: new Date().toISOString().split('T')[0],
        amount: '',
        payment_method: 'NEFT',
        reference_no: '',
        tds_amount: '',
        tds_section: '194C',
        other_deductions_amount: '',
        notes: ''
      });
      await refreshInvoices();
      const mRes = await billingApi.getDashboardMetrics();
      setMetrics(mRes.data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to record payment.');
    } finally {
      setLoading(false);
    }
  };

  const handleReversePayment = async () => {
    if (!reversalReason.trim()) {
      setError('Reversal reason is required.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await billingApi.reversePayment(reversalPaymentId, { reversal_reason: reversalReason });
      setSuccessMsg('Payment reversed. Outstanding amount restored.');
      setShowReversalModal(false);
      setReversalReason('');
      setReversalPaymentId(null);
      await refreshInvoices();
      const mRes = await billingApi.getDashboardMetrics();
      setMetrics(mRes.data);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to reverse payment.');
    } finally {
      setLoading(false);
    }
  };

  const openAnnexureModal = async (invoiceId) => {
    setLoading(true);
    try {
      const res = await billingApi.getInvoiceAnnexure(invoiceId);
      setAnnexureData(res.data);
      setShowAnnexureModal(true);
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to load attendance annexure.');
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------------------------
  // Handlers: Settings Save
  // --------------------------------------------------------------------------
  const handleSaveCompanySettings = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await billingApi.updateCompanySettings(companySettings);
      setCompanySettings(res.data);
      setSuccessMsg('Company invoice settings updated successfully.');
    } catch (err) {
      setError(err?.response?.data?.error || 'Failed to update company settings.');
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------------------------
  // Exports
  // --------------------------------------------------------------------------
  const handleExportInvoicesCSV = () => {
    window.open('/api/billing/exports/invoices/', '_blank');
  };

  const handleExportPaymentsCSV = () => {
    window.open('/api/billing/exports/payments/', '_blank');
  };

  // Status Badge Helper
  const renderStatusBadge = (status, overdueFlag, queryFlag, sourceChanged) => {
    let color = 'bg-gray-100 text-gray-800 border-gray-200';
    if (status === 'DRAFT') color = 'bg-amber-50 text-amber-800 border-amber-200';
    if (status === 'SENT') color = 'bg-blue-50 text-blue-800 border-blue-200';
    if (status === 'PARTIALLY_PAID') color = 'bg-indigo-50 text-indigo-800 border-indigo-200';
    if (status === 'PAID') color = 'bg-emerald-50 text-emerald-800 border-emerald-200';
    if (status === 'CANCELLED') color = 'bg-red-50 text-red-800 border-red-200';

    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`px-2 py-0.5 text-xs font-semibold rounded-md border ${color}`}>
          {status}
        </span>
        {overdueFlag && (
          <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded-md bg-rose-100 text-rose-800 border border-rose-300">
            Overdue
          </span>
        )}
        {queryFlag && (
          <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded-md bg-orange-100 text-orange-800 border border-orange-300">
            Under Query
          </span>
        )}
        {sourceChanged && (
          <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded-md bg-amber-100 text-amber-800 border border-amber-300">
            Source Changed
          </span>
        )}
      </div>
    );
  };

  // Filtered invoices
  const filteredInvoices = invoices.filter(inv => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (inv.invoice_no && inv.invoice_no.toLowerCase().includes(q)) ||
      (inv.draft_reference && inv.draft_reference.toLowerCase().includes(q)) ||
      (inv.client_name && inv.client_name.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white border border-gray-200 p-5 rounded-md shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <Receipt className="w-6 h-6 text-slate-800" />
            <h1 className="text-xl font-bold text-gray-900">Billing & Invoices</h1>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Module 11: Direct billing calculations, immutable invoice lifecycle, collections & receivables ageing
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleExportInvoicesCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 rounded-md text-xs font-medium shadow-sm transition"
          >
            <FileDown className="w-3.5 h-3.5 text-gray-500" />
            Export Invoices CSV
          </button>
          <button
            onClick={handleExportPaymentsCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 rounded-md text-xs font-medium shadow-sm transition"
          >
            <FileDown className="w-3.5 h-3.5 text-gray-500" />
            Export Payments CSV
          </button>
        </div>
      </div>

      {/* Notifications / Alerts */}
      {error && (
        <div className="flex items-center justify-between p-3.5 bg-red-50 border border-red-200 text-red-800 text-xs rounded-md">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 font-bold ml-2">×</button>
        </div>
      )}
      {successMsg && (
        <div className="flex items-center justify-between p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-md">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-2">×</button>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex border-b border-gray-200 space-x-1">
        {[
          { id: 'overview', label: 'Overview & Ageing', icon: DollarSign },
          { id: 'invoices', label: 'Invoices & Drafts', icon: Receipt },
          { id: 'run', label: 'Billing Run & Calculation', icon: RefreshCw },
          { id: 'settings', label: 'Billing Settings', icon: Sliders }
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition ${
                isActive
                  ? 'border-slate-900 text-slate-900 bg-white'
                  : 'border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ==================================================================== */}
      {/* TAB 1: OVERVIEW & AGEING                                            */}
      {/* ==================================================================== */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Total Billed</span>
              <div className="text-2xl font-bold text-gray-900 mt-1">₹{parseFloat(metrics.total_invoiced || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              <p className="text-[11px] text-gray-500 mt-1">{metrics.sent_count + metrics.paid_count} issued billing statements</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Collected Payments</span>
              <div className="text-2xl font-bold text-emerald-600 mt-1">₹{parseFloat(metrics.total_paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              <p className="text-[11px] text-gray-500 mt-1">{metrics.paid_count} settled invoices</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Outstanding Receivables</span>
              <div className="text-2xl font-bold text-blue-600 mt-1">₹{parseFloat(metrics.total_outstanding || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              <p className="text-[11px] text-gray-500 mt-1">Active client balances</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Overdue Balance</span>
              <div className="text-2xl font-bold text-rose-600 mt-1">₹{parseFloat(metrics.total_overdue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              <p className="text-[11px] text-rose-600 font-medium mt-1">{metrics.overdue_count} overdue statements</p>
            </div>
          </div>

          {/* Ageing Summary Breakdown */}
          <div className="bg-white border border-gray-200 rounded-md shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Receivables Ageing Breakdown</h2>
                <p className="text-xs text-gray-500 mt-0.5">Categorized by invoice due date (PRD 6.13, FR-11.138 to FR-11.144)</p>
              </div>
              <div className="text-xs font-semibold text-gray-700">
                Total Outstanding: <span className="text-slate-900 font-bold">₹{parseFloat(ageingData?.summary?.total_outstanding || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="border border-emerald-100 bg-emerald-50/50 rounded-md p-3">
                <span className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider">Current (0 - 30 Days)</span>
                <div className="text-lg font-bold text-emerald-900 mt-1">₹{parseFloat(ageingData?.summary?.current_0_30 || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              </div>
              <div className="border border-blue-100 bg-blue-50/50 rounded-md p-3">
                <span className="text-[10px] font-bold text-blue-800 uppercase tracking-wider">31 - 60 Days</span>
                <div className="text-lg font-bold text-blue-900 mt-1">₹{parseFloat(ageingData?.summary?.days_31_60 || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              </div>
              <div className="border border-amber-100 bg-amber-50/50 rounded-md p-3">
                <span className="text-[10px] font-bold text-amber-800 uppercase tracking-wider">61 - 90 Days</span>
                <div className="text-lg font-bold text-amber-900 mt-1">₹{parseFloat(ageingData?.summary?.days_61_90 || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              </div>
              <div className="border border-rose-100 bg-rose-50/50 rounded-md p-3">
                <span className="text-[10px] font-bold text-rose-800 uppercase tracking-wider">&gt; 90 Days</span>
                <div className="text-lg font-bold text-rose-900 mt-1">₹{parseFloat(ageingData?.summary?.days_90_plus || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
              </div>
            </div>

            {/* Per-Client Ageing Table */}
            <div className="overflow-x-auto border border-gray-100 rounded-md mt-4">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Client Organization</th>
                    <th className="p-3 text-right">0 - 30 Days</th>
                    <th className="p-3 text-right">31 - 60 Days</th>
                    <th className="p-3 text-right">61 - 90 Days</th>
                    <th className="p-3 text-right">&gt; 90 Days</th>
                    <th className="p-3 text-right">Total Outstanding</th>
                    <th className="p-3 text-center">Overdue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {ageingData?.clients?.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="p-6 text-center text-gray-400">
                        No outstanding receivables found across client accounts.
                      </td>
                    </tr>
                  ) : (
                    ageingData?.clients?.map((cl) => (
                      <tr key={cl.client_id} className="hover:bg-gray-50">
                        <td className="p-3 font-medium text-gray-900">
                          <div>{cl.client_name}</div>
                          <div className="text-[10px] text-gray-400">{cl.client_code}</div>
                        </td>
                        <td className="p-3 text-right font-medium text-emerald-700">₹{parseFloat(cl.current_0_30 || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-medium text-blue-700">₹{parseFloat(cl.days_31_60 || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-medium text-amber-700">₹{parseFloat(cl.days_61_90 || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-medium text-rose-700">₹{parseFloat(cl.days_90_plus || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-bold text-slate-900">₹{parseFloat(cl.total_outstanding || 0).toFixed(2)}</td>
                        <td className="p-3 text-center">
                          {cl.overdue_count > 0 ? (
                            <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded-md bg-rose-100 text-rose-800 border border-rose-200">
                              {cl.overdue_count} Overdue
                            </span>
                          ) : (
                            <span className="text-gray-400 text-[11px]">-</span>
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

      {/* ==================================================================== */}
      {/* TAB 2: INVOICES & DRAFTS MANAGEMENT                                 */}
      {/* ==================================================================== */}
      {activeTab === 'invoices' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
            <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search invoice no, draft ref, client..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-1 focus:ring-slate-900 focus:outline-none"
                />
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs bg-white text-gray-700 focus:outline-none"
              >
                <option value="">All Statuses</option>
                <option value="DRAFT">DRAFT</option>
                <option value="SENT">SENT (Issued)</option>
                <option value="PARTIALLY_PAID">PARTIALLY_PAID</option>
                <option value="PAID">PAID</option>
                <option value="CANCELLED">CANCELLED</option>
              </select>
              <select
                value={clientFilter}
                onChange={(e) => setClientFilter(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs bg-white text-gray-700 focus:outline-none"
              >
                <option value="">All Clients</option>
                {clientsList.map(c => (
                  <option key={c.client_id} value={c.client_id}>{c.legal_name || c.display_name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={refreshInvoices}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 rounded-md text-xs font-medium shadow-sm"
            >
              <RefreshCw className="w-3.5 h-3.5 text-gray-500" />
              Refresh
            </button>
          </div>

          {/* Invoices Table */}
          <div className="bg-white border border-gray-200 rounded-md shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Invoice / Draft Ref</th>
                    <th className="p-3">Client</th>
                    <th className="p-3">Period</th>
                    <th className="p-3 text-right">Subtotal</th>
                    <th className="p-3 text-right">Tax (18%)</th>
                    <th className="p-3 text-right">Total</th>
                    <th className="p-3 text-right">Outstanding</th>
                    <th className="p-3">Status & Flags</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredInvoices.length === 0 ? (
                    <tr>
                      <td colSpan="9" className="p-8 text-center text-gray-400">
                        No billing invoices or drafts match your filter criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredInvoices.map((inv) => (
                      <tr key={inv.invoice_id} className="hover:bg-gray-50 transition">
                        <td className="p-3 font-semibold text-gray-900">
                          <div>{inv.invoice_no || inv.draft_reference}</div>
                          {inv.invoice_no && inv.draft_reference && (
                            <div className="text-[10px] text-gray-400 font-normal">Draft: {inv.draft_reference}</div>
                          )}
                        </td>
                        <td className="p-3 text-gray-700 font-medium">
                          <div>{inv.client_name || 'Client Org'}</div>
                          <div className="text-[10px] text-gray-400">{inv.client_code}</div>
                        </td>
                        <td className="p-3 text-gray-600 whitespace-nowrap">
                          {inv.period_start} to {inv.period_end}
                        </td>
                        <td className="p-3 text-right font-medium text-gray-700">₹{parseFloat(inv.subtotal || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-medium text-gray-600">₹{parseFloat(inv.tax_amount || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-bold text-gray-900">₹{parseFloat(inv.total_amount || 0).toFixed(2)}</td>
                        <td className="p-3 text-right font-bold text-blue-700">₹{parseFloat(inv.outstanding_amount || 0).toFixed(2)}</td>
                        <td className="p-3">
                          {renderStatusBadge(inv.status, inv.overdue_flag, inv.under_query_flag, inv.source_changed)}
                        </td>
                        <td className="p-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => openInvoiceDetail(inv.invoice_id)}
                              title="View Invoice Detail"
                              className="p-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-md transition"
                            >
                              <Eye className="w-4 h-4" />
                            </button>

                            {/* DRAFT Actions */}
                            {inv.status === 'DRAFT' && (
                              <>
                                <button
                                  onClick={() => {
                                    setSelectedInvoice(inv);
                                    setShowManualLineModal(true);
                                  }}
                                  title="Add Manual Line"
                                  className="px-2 py-1 text-[11px] font-medium border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700"
                                >
                                  + Line
                                </button>
                                <button
                                  onClick={() => handleIssueInvoice(inv.invoice_id)}
                                  title="Issue Invoice (Locks PDF & SHA-256)"
                                  className="px-2 py-1 text-[11px] font-medium bg-slate-900 text-white rounded-md hover:bg-slate-800"
                                >
                                  Issue
                                </button>
                              </>
                            )}

                            {/* SENT / PARTIALLY_PAID Actions */}
                            {(inv.status === 'SENT' || inv.status === 'PARTIALLY_PAID') && (
                              <>
                                <button
                                  onClick={() => {
                                    setSelectedInvoice(inv);
                                    setPaymentForm(prev => ({ ...prev, amount: inv.outstanding_amount }));
                                    setShowPaymentModal(true);
                                  }}
                                  title="Record Payment"
                                  className="px-2 py-1 text-[11px] font-medium bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                                >
                                  Pay
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedInvoice(inv);
                                    setShowCancelModal(true);
                                  }}
                                  title="Cancel Invoice"
                                  className="p-1 text-rose-500 hover:text-rose-700 hover:bg-rose-50 rounded-md"
                                >
                                  <XCircle className="w-4 h-4" />
                                </button>
                              </>
                            )}

                            {/* CANCELLED Action */}
                            {inv.status === 'CANCELLED' && (
                              <button
                                onClick={() => handleCreateReplacement(inv.invoice_id)}
                                title="Generate Replacement Draft"
                                className="px-2 py-1 text-[11px] font-medium border border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-md flex items-center gap-1"
                              >
                                <RotateCcw className="w-3 h-3" />
                                Replace
                              </button>
                            )}

                            {/* Attendance Annexure */}
                            <button
                              onClick={() => openAnnexureModal(inv.invoice_id)}
                              title="View Attendance Annexure"
                              className="p-1 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-md"
                            >
                              <FileText className="w-4 h-4" />
                            </button>
                          </div>
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

      {/* ==================================================================== */}
      {/* TAB 3: BILLING RUN & CALCULATION ENGINE                             */}
      {/* ==================================================================== */}
      {activeTab === 'run' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Run Form */}
          <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Execute Monthly Billing Run</h2>
            <p className="text-xs text-gray-500">
              Aggregates verified attendance records from Module 6, matches effective-dated post rates, and generates draft invoices.
            </p>

            <div className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Billing Period Start</label>
                <input
                  type="date"
                  value={runPeriodStart}
                  onChange={(e) => setRunPeriodStart(e.target.value)}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-1 focus:ring-slate-900"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Billing Period End</label>
                <input
                  type="date"
                  value={runPeriodEnd}
                  onChange={(e) => setRunPeriodEnd(e.target.value)}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-1 focus:ring-slate-900"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Target Client Organization</label>
                <select
                  value={runClientId}
                  onChange={(e) => setRunClientId(e.target.value)}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs bg-white text-gray-800"
                >
                  <option value="">All Clients (Full Monthly Batch)</option>
                  {clientsList.map(c => (
                    <option key={c.client_id} value={c.client_id}>{c.legal_name || c.display_name} ({c.client_code})</option>
                  ))}
                </select>
                <p className="text-[10px] text-gray-400 mt-1">Leave blank to process all client organizations in batch.</p>
              </div>

              {/* Unlocked Period Override Checkbox */}
              <div className="pt-2 border-t border-gray-100">
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allowUnlocked}
                    onChange={(e) => setAllowUnlocked(e.target.checked)}
                    className="mt-0.5 rounded border-gray-300 text-slate-900 focus:ring-slate-900"
                  />
                  <div>
                    <span className="text-xs font-semibold text-gray-800">Allow Unlocked Period Billing</span>
                    <p className="text-[10px] text-gray-500">Requires audit reason; provisional records will be flagged (AC-11.5).</p>
                  </div>
                </label>
                {allowUnlocked && (
                  <div className="mt-2">
                    <label className="block text-[11px] font-semibold text-gray-700 mb-1">Audit Reason / Justification *</label>
                    <textarea
                      rows="2"
                      value={unlockedReason}
                      onChange={(e) => setUnlockedReason(e.target.value)}
                      placeholder="e.g. Authorized early billing run prior to formal attendance period close."
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                    />
                  </div>
                )}
              </div>

              {/* Buttons */}
              <div className="pt-3 space-y-2">
                <button
                  type="button"
                  onClick={handlePreviewBilling}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-1.5 px-4 py-2 border border-slate-900 text-slate-900 bg-white hover:bg-gray-50 rounded-md text-xs font-semibold transition"
                >
                  <Eye className="w-3.5 h-3.5" />
                  Preview Billing Calculation
                </button>
                <button
                  type="button"
                  onClick={handleExecuteBillingRun}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-1.5 px-4 py-2 bg-slate-900 text-white hover:bg-slate-800 rounded-md text-xs font-semibold shadow-sm transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Execute Billing Run
                </button>
              </div>
            </div>
          </div>

          {/* Preview or Result Panel */}
          <div className="lg:col-span-2 space-y-4">
            {previewData ? (
              <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 uppercase">Billing Calculation Preview</h3>
                    <p className="text-xs text-gray-500">{runPeriodStart} to {runPeriodEnd} (Duty attendance verified)</p>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-500">Estimated Total</div>
                    <div className="text-lg font-bold text-slate-900">₹{parseFloat(previewData.total_amount || 0).toFixed(2)}</div>
                  </div>
                </div>

                {/* Calculation Totals */}
                <div className="grid grid-cols-3 gap-3 bg-gray-50 p-3 rounded-md border border-gray-100 text-xs">
                  <div>
                    <span className="text-gray-400 font-medium">Subtotal:</span>
                    <div className="font-bold text-gray-900">₹{parseFloat(previewData.subtotal || 0).toFixed(2)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400 font-medium">GST (18%):</span>
                    <div className="font-bold text-gray-900">₹{parseFloat(previewData.tax_amount || 0).toFixed(2)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400 font-medium">Verified Sources:</span>
                    <div className="font-bold text-gray-900">{previewData.snapshot?.length || 0} shifts</div>
                  </div>
                </div>

                {/* Line Items Table */}
                <div className="overflow-x-auto border border-gray-100 rounded-md">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 text-gray-500 font-semibold uppercase text-[10px]">
                      <tr>
                        <th className="p-2.5">Description</th>
                        <th className="p-2.5">Unit</th>
                        <th className="p-2.5 text-right">Quantity</th>
                        <th className="p-2.5 text-right">Rate</th>
                        <th className="p-2.5 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {previewData.lines?.map((line, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="p-2.5 font-medium text-gray-900">{line.description}</td>
                          <td className="p-2.5 text-gray-500">{line.unit}</td>
                          <td className="p-2.5 text-right font-medium">{line.quantity}</td>
                          <td className="p-2.5 text-right text-gray-600">₹{parseFloat(line.unit_rate).toFixed(2)}</td>
                          <td className="p-2.5 text-right font-bold text-slate-900">₹{parseFloat(line.line_amount).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : runResult ? (
              <div className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-gray-900 uppercase">Billing Run Execution Report</h3>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="border border-emerald-100 bg-emerald-50/50 p-3 rounded-md">
                    <span className="font-bold text-emerald-800">Fresh Drafts Created</span>
                    <div className="text-xl font-bold text-emerald-900 mt-1">{runResult.drafts_created?.length || 0}</div>
                  </div>
                  <div className="border border-blue-100 bg-blue-50/50 p-3 rounded-md">
                    <span className="font-bold text-blue-800">Existing Drafts Refreshed</span>
                    <div className="text-xl font-bold text-blue-900 mt-1">{runResult.drafts_refreshed?.length || 0}</div>
                  </div>
                </div>

                {runResult.clients_skipped?.length > 0 && (
                  <div className="border border-amber-200 bg-amber-50 p-3 rounded-md text-xs space-y-1">
                    <span className="font-bold text-amber-900">Skipped Clients Report:</span>
                    {runResult.clients_skipped.map((s, idx) => (
                      <div key={idx} className="text-amber-800 text-[11px]">
                        • {s.client_code}: {s.reason}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-md p-12 text-center text-gray-400 text-xs">
                <Receipt className="w-10 h-10 mx-auto text-gray-300 mb-2" />
                Select a client and period to generate a calculation preview or execute a draft run.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 4: BILLING SETTINGS                                             */}
      {/* ==================================================================== */}
      {activeTab === 'settings' && companySettings && (
        <div className="bg-white border border-gray-200 rounded-md p-6 shadow-sm max-w-4xl space-y-6">
          <div>
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Company Invoice Settings</h2>
            <p className="text-xs text-gray-500 mt-0.5">Configure numbering sequences, bank details, and default payment terms (PRD 6.1)</p>
          </div>

          <form onSubmit={handleSaveCompanySettings} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Invoice Prefix</label>
                <input
                  type="text"
                  value={companySettings.prefix || ''}
                  onChange={(e) => setCompanySettings({ ...companySettings, prefix: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Sequence Digits</label>
                <input
                  type="number"
                  value={companySettings.sequence_digits || 4}
                  onChange={(e) => setCompanySettings({ ...companySettings, sequence_digits: parseInt(e.target.value) })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Default Due Days</label>
                <input
                  type="number"
                  value={companySettings.default_payment_terms_days || 30}
                  onChange={(e) => setCompanySettings({ ...companySettings, default_payment_terms_days: parseInt(e.target.value) })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-gray-100">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Bank Name</label>
                <input
                  type="text"
                  value={companySettings.bank_name || ''}
                  onChange={(e) => setCompanySettings({ ...companySettings, bank_name: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Account Number</label>
                <input
                  type="text"
                  value={companySettings.bank_account_number || ''}
                  onChange={(e) => setCompanySettings({ ...companySettings, bank_account_number: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">IFSC Code</label>
                <input
                  type="text"
                  value={companySettings.bank_ifsc || ''}
                  onChange={(e) => setCompanySettings({ ...companySettings, bank_ifsc: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs font-mono uppercase"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Branch Name</label>
                <input
                  type="text"
                  value={companySettings.bank_branch || ''}
                  onChange={(e) => setCompanySettings({ ...companySettings, bank_branch: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>
            </div>

            <div className="pt-2 border-t border-gray-100">
              <label className="block text-xs font-semibold text-gray-700 mb-1">Invoice Terms & Notes</label>
              <textarea
                rows="3"
                value={companySettings.invoice_notes || ''}
                onChange={(e) => setCompanySettings({ ...companySettings, invoice_notes: e.target.value })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
              />
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800 transition"
              >
                Save Company Invoice Settings
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL 1: INVOICE DETAIL & VIEWER                                    */}
      {/* ==================================================================== */}
      {showDetailModal && invoiceDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white border border-gray-200 rounded-md shadow-lg max-w-3xl w-full p-6 space-y-5 my-8 max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="flex justify-between items-start border-b border-gray-100 pb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Tax Invoice</span>
                <h3 className="text-lg font-bold text-gray-900">{invoiceDetail.invoice_no || invoiceDetail.draft_reference}</h3>
                <p className="text-xs text-gray-500">Period: {invoiceDetail.period_start} to {invoiceDetail.period_end}</p>
              </div>
              <div className="text-right">
                {renderStatusBadge(invoiceDetail.status, invoiceDetail.overdue_flag, invoiceDetail.under_query_flag)}
                {invoiceDetail.invoice_date && (
                  <div className="text-[11px] text-gray-500 mt-1">Date: {invoiceDetail.invoice_date}</div>
                )}
                {invoiceDetail.due_date && (
                  <div className="text-[11px] text-gray-500">Due: {invoiceDetail.due_date}</div>
                )}
              </div>
            </div>

            {/* Billed To / Client Metadata */}
            <div className="grid grid-cols-2 gap-4 bg-gray-50 p-3.5 rounded-md text-xs">
              <div>
                <span className="font-bold text-gray-500 uppercase text-[10px]">Billed To (Client Org)</span>
                <div className="font-bold text-gray-900 mt-0.5">{invoiceDetail.client_name || 'Client Org'}</div>
                <div className="text-gray-600 mt-0.5">GSTIN: {invoiceDetail.client_gstin || 'Unspecified'}</div>
                <div className="text-gray-600">PAN: {invoiceDetail.client_pan || 'Unspecified'}</div>
                {invoiceDetail.client_address && (
                  <div className="text-gray-500 mt-1 text-[11px]">{invoiceDetail.client_address}</div>
                )}
              </div>
              <div className="text-right">
                <span className="font-bold text-gray-500 uppercase text-[10px]">Payment Summary</span>
                <div className="mt-1">
                  <span className="text-gray-500">Total Billed: </span>
                  <span className="font-bold text-gray-900">₹{parseFloat(invoiceDetail.total_amount).toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-gray-500">Paid Amount: </span>
                  <span className="font-bold text-emerald-600">₹{parseFloat(invoiceDetail.paid_amount || 0).toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-gray-500">Deductions (TDS/Other): </span>
                  <span className="font-bold text-gray-700">₹{parseFloat(invoiceDetail.deduction_amount || 0).toFixed(2)}</span>
                </div>
                <div className="pt-1 mt-1 border-t border-gray-200">
                  <span className="text-gray-500">Outstanding: </span>
                  <span className="font-bold text-blue-700">₹{parseFloat(invoiceDetail.outstanding_amount).toFixed(2)}</span>
                </div>
              </div>
            </div>

            {/* Line Items Table */}
            <div className="overflow-x-auto border border-gray-100 rounded-md">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-500 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-2.5">Line Description</th>
                    <th className="p-2.5">Unit</th>
                    <th className="p-2.5 text-right">Qty</th>
                    <th className="p-2.5 text-right">Unit Rate</th>
                    <th className="p-2.5 text-right">Tax (%)</th>
                    <th className="p-2.5 text-right">Line Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {invoiceDetail.lines?.map((line) => (
                    <tr key={line.invoice_line_id} className="hover:bg-gray-50">
                      <td className="p-2.5 font-medium text-gray-900">
                        <div>{line.description}</div>
                        {line.manual_reason && (
                          <div className="text-[10px] text-amber-700 italic">Manual note: {line.manual_reason}</div>
                        )}
                      </td>
                      <td className="p-2.5 text-gray-500">{line.unit}</td>
                      <td className="p-2.5 text-right font-medium">{line.quantity}</td>
                      <td className="p-2.5 text-right text-gray-600">₹{parseFloat(line.unit_rate).toFixed(2)}</td>
                      <td className="p-2.5 text-right text-gray-600">{line.tax_rate}%</td>
                      <td className={`p-2.5 text-right font-bold ${line.is_negative ? 'text-rose-600' : 'text-slate-900'}`}>
                        {line.is_negative ? '-' : ''}₹{Math.abs(parseFloat(line.line_amount)).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Financial Summary & Amount in Words */}
            <div className="bg-slate-50 border border-slate-100 p-4 rounded-md space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-600">Taxable Subtotal:</span>
                <span className="font-semibold text-gray-900">₹{parseFloat(invoiceDetail.subtotal).toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">GST (18%):</span>
                <span className="font-semibold text-gray-900">₹{parseFloat(invoiceDetail.tax_amount).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm font-bold pt-2 border-t border-slate-200">
                <span className="text-slate-900">Total Invoice Amount:</span>
                <span className="text-slate-900">₹{parseFloat(invoiceDetail.total_amount).toFixed(2)}</span>
              </div>
              {invoiceDetail.total_in_words && (
                <div className="text-[11px] text-slate-700 pt-1 font-medium italic">
                  Amount in words: {invoiceDetail.total_in_words}
                </div>
              )}
            </div>

            {/* SHA-256 PDF Verification */}
            {invoiceDetail.pdf_hash && (
              <div className="p-3 bg-gray-50 border border-gray-200 rounded-md text-[10px] font-mono text-gray-600">
                <span className="font-bold text-gray-700">Digital Verification Hash (SHA-256): </span>
                {invoiceDetail.pdf_hash}
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setShowDetailModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-xs font-semibold text-gray-700 hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL 2: ADD MANUAL LINE ITEM                                       */}
      {/* ==================================================================== */}
      {showManualLineModal && selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-gray-200 rounded-md shadow-lg max-w-md w-full p-6 space-y-4">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Add Manual Line Item</h3>
            <p className="text-xs text-gray-500">Draft: {selectedInvoice.draft_reference}</p>

            <form onSubmit={handleAddManualLine} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Description *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Additional Event Guarding, Delay Rebate"
                  value={manualLine.description}
                  onChange={(e) => setManualLine({ ...manualLine, description: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Quantity</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={manualLine.quantity}
                    onChange={(e) => setManualLine({ ...manualLine, quantity: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Unit Rate (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    placeholder="250.00"
                    value={manualLine.unit_rate}
                    onChange={(e) => setManualLine({ ...manualLine, unit_rate: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Tax (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={manualLine.tax_rate}
                    onChange={(e) => setManualLine({ ...manualLine, tax_rate: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                  />
                </div>
              </div>

              {/* Is Deduction Checkbox */}
              <div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={manualLine.is_negative}
                    onChange={(e) => setManualLine({ ...manualLine, is_negative: e.target.checked })}
                    className="rounded border-gray-300 text-slate-900 focus:ring-slate-900"
                  />
                  <span className="text-xs font-semibold text-gray-700">Deduction / Credit Adjustment (Negative Line)</span>
                </label>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Internal Reason *</label>
                <textarea
                  rows="2"
                  required
                  placeholder="Justification recorded for internal audit"
                  value={manualLine.manual_reason}
                  onChange={(e) => setManualLine({ ...manualLine, manual_reason: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Client Visible Description</label>
                <input
                  type="text"
                  placeholder="Printed on client tax invoice"
                  value={manualLine.client_visible_description}
                  onChange={(e) => setManualLine({ ...manualLine, client_visible_description: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowManualLineModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-semibold text-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md text-xs font-semibold"
                >
                  Add Line Item
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL 3: RECORD PAYMENT                                             */}
      {/* ==================================================================== */}
      {showPaymentModal && selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-gray-200 rounded-md shadow-lg max-w-md w-full p-6 space-y-4">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Record Client Payment</h3>
            <p className="text-xs text-gray-500">Invoice: {selectedInvoice.invoice_no} | Outstanding: ₹{selectedInvoice.outstanding_amount}</p>

            <form onSubmit={handleRecordPayment} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Payment Date *</label>
                  <input
                    type="date"
                    required
                    value={paymentForm.payment_date}
                    onChange={(e) => setPaymentForm({ ...paymentForm, payment_date: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Amount Paid (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={paymentForm.amount}
                    onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs font-bold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Method *</label>
                  <select
                    value={paymentForm.payment_method}
                    onChange={(e) => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs bg-white"
                  >
                    <option value="NEFT">NEFT</option>
                    <option value="RTGS">RTGS</option>
                    <option value="IMPS">IMPS</option>
                    <option value="CHEQUE">Cheque</option>
                    <option value="UPI">UPI</option>
                    <option value="CASH">Cash</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Reference / UTR No</label>
                  <input
                    type="text"
                    placeholder="UTR / Cheque No"
                    value={paymentForm.reference_no}
                    onChange={(e) => setPaymentForm({ ...paymentForm, reference_no: e.target.value })}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs font-mono"
                  />
                </div>
              </div>

              {/* Deductions: TDS & Other */}
              <div className="pt-2 border-t border-gray-100 space-y-2">
                <span className="text-[11px] font-bold text-gray-700 uppercase">Statutory & Other Deductions</span>
                <div className="grid grid-cols-3 gap-2">
                  <div className="col-span-2">
                    <label className="block text-[10px] font-semibold text-gray-500 mb-0.5">TDS Deducted (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      value={paymentForm.tds_amount}
                      onChange={(e) => setPaymentForm({ ...paymentForm, tds_amount: e.target.value })}
                      className="w-full px-2 py-1 border border-gray-300 rounded-md text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-gray-500 mb-0.5">TDS Sec</label>
                    <input
                      type="text"
                      value={paymentForm.tds_section}
                      onChange={(e) => setPaymentForm({ ...paymentForm, tds_section: e.target.value })}
                      className="w-full px-2 py-1 border border-gray-300 rounded-md text-xs"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-gray-500 mb-0.5">Other Client Deductions (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={paymentForm.other_deductions_amount}
                    onChange={(e) => setPaymentForm({ ...paymentForm, other_deductions_amount: e.target.value })}
                    className="w-full px-2 py-1 border border-gray-300 rounded-md text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowPaymentModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-semibold text-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 bg-emerald-600 text-white rounded-md text-xs font-semibold hover:bg-emerald-700"
                >
                  Record Payment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL 4: CANCEL INVOICE                                             */}
      {/* ==================================================================== */}
      {showCancelModal && selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-gray-200 rounded-md shadow-lg max-w-md w-full p-6 space-y-4">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Cancel Issued Invoice</h3>
            <p className="text-xs text-rose-600 font-medium">
              Invoice {selectedInvoice.invoice_no} will be permanently marked CANCELLED. Any active payments must be reversed first.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Reason for Cancellation (Audit) *</label>
                <textarea
                  rows="2"
                  required
                  placeholder="e.g. Major rate dispute resolved with client; credit to be reissued."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Client Visible Explanation</label>
                <textarea
                  rows="2"
                  placeholder="Text visible to client in portal"
                  value={clientVisibleCancelReason}
                  onChange={(e) => setClientVisibleCancelReason(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowCancelModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-semibold text-gray-700"
                >
                  Go Back
                </button>
                <button
                  type="button"
                  onClick={handleCancelInvoice}
                  disabled={loading}
                  className="px-4 py-1.5 bg-rose-600 text-white rounded-md text-xs font-semibold hover:bg-rose-700"
                >
                  Confirm Cancellation
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL 5: ATTENDANCE ANNEXURE VIEWER                                 */}
      {/* ==================================================================== */}
      {showAnnexureModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white border border-gray-200 rounded-md shadow-lg max-w-2xl w-full p-6 space-y-4 max-h-[85vh] overflow-y-auto">
            <h3 className="text-sm font-bold text-gray-900 uppercase">Invoice Attendance Annexure</h3>
            <p className="text-xs text-gray-500">Day-by-day duty attendance snapshot supporting the invoice calculation.</p>

            <div className="overflow-x-auto border border-gray-100 rounded-md">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-500 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-2.5">Duty Date</th>
                    <th className="p-2.5">Site Name</th>
                    <th className="p-2.5">Guard / Employee</th>
                    <th className="p-2.5">Shift</th>
                    <th className="p-2.5">Post Type</th>
                    <th className="p-2.5 text-right">Billable Units</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {annexureData.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="p-6 text-center text-gray-400">
                        No annexure rows recorded for this invoice.
                      </td>
                    </tr>
                  ) : (
                    annexureData.map((row) => (
                      <tr key={row.annexure_id} className="hover:bg-gray-50">
                        <td className="p-2.5 font-medium text-gray-900 whitespace-nowrap">{row.duty_date}</td>
                        <td className="p-2.5 text-gray-700">{row.site_name}</td>
                        <td className="p-2.5 text-gray-800 font-medium">{row.employee_name}</td>
                        <td className="p-2.5 text-gray-500">{row.shift_code}</td>
                        <td className="p-2.5 text-gray-600">{row.post_type_code}</td>
                        <td className="p-2.5 text-right font-bold text-slate-900">{row.billable_units}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setShowAnnexureModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-xs font-semibold text-gray-700 hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

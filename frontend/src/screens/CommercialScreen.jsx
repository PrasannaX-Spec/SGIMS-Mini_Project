import React, { useState, useEffect } from 'react';
import { DollarSign, Shield, Clock, Plus, AlertCircle, CheckCircle2 } from 'lucide-react';
import { masterApi } from '../api';

export default function CommercialScreen() {
  const [rates, setRates] = useState([]);
  const [agreements, setAgreements] = useState([]);
  const [clients, setClients] = useState([]);
  const [postTypes, setPostTypes] = useState([]);
  const [loading, setLoading] = useState(true);

  // Rate modal
  const [showRateModal, setShowRateModal] = useState(false);
  const [rateForm, setRateForm] = useState({
    client_id: '',
    site_id: '',
    post_type_id: '',
    rate_type: 'hourly',
    rate_amount: '',
    effective_from: new Date().toISOString().split('T')[0],
  });

  // Test resolution modal
  const [resolveForm, setResolveForm] = useState({
    client_id: '',
    post_type_id: '',
    date: new Date().toISOString().split('T')[0],
  });
  const [resolvedResult, setResolvedResult] = useState(null);

  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [rateRes, agreeRes, clientRes, ptRes] = await Promise.all([
        masterApi.getBillingRates(),
        masterApi.getAgreements(),
        masterApi.getClients(),
        masterApi.getPostTypes(),
      ]);
      setRates(rateRes.data);
      setAgreements(agreeRes.data);
      setClients(clientRes.data);
      setPostTypes(ptRes.data);
    } catch (err) {
      console.error('Failed to load commercial data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSetRate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      const payload = { ...rateForm };
      if (!payload.site_id) delete payload.site_id;
      await masterApi.setBillingRate(payload);
      setShowRateModal(false);
      setRateForm({
        client_id: '',
        site_id: '',
        post_type_id: '',
        rate_type: 'hourly',
        rate_amount: '',
        effective_from: new Date().toISOString().split('T')[0],
      });
      fetchData();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to configure billing rate.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestResolve = async (e) => {
    e.preventDefault();
    try {
      const res = await masterApi.resolveBillingRate(resolveForm);
      setResolvedResult(res.data);
    } catch (err) {
      alert(err.message || 'Resolution failed');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-md border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-slate-700" />
            Billing Rates & Service Agreements
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Effective-dated client and site billing rates with resolution precedence and legal service agreements
          </p>
        </div>
        <button
          onClick={() => setShowRateModal(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 transition"
        >
          <Plus className="w-4 h-4" />
          Configure Billing Rate
        </button>
      </div>

      {/* Precedence Tester Widget */}
      <div className="bg-white p-4 rounded-md border border-gray-200 space-y-3">
        <h3 className="font-bold text-xs text-gray-900 uppercase tracking-wider flex items-center gap-1.5">
          <Clock className="w-4 h-4 text-slate-600" />
          Billing Rate Precedence Resolver (Site Specific &gt; Client Default)
        </h3>
        <form onSubmit={handleTestResolve} className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs">
          <select
            required
            value={resolveForm.client_id}
            onChange={(e) => setResolveForm({ ...resolveForm, client_id: e.target.value })}
            className="px-3 py-1.5 border border-gray-300 rounded-md"
          >
            <option value="">Select Client</option>
            {clients.map((c) => (
              <option key={c.client_id} value={c.client_id}>
                {c.client_code} - {c.legal_name}
              </option>
            ))}
          </select>

          <select
            required
            value={resolveForm.post_type_id}
            onChange={(e) => setResolveForm({ ...resolveForm, post_type_id: e.target.value })}
            className="px-3 py-1.5 border border-gray-300 rounded-md"
          >
            <option value="">Select Post Type</option>
            {postTypes.map((p) => (
              <option key={p.post_type_id} value={p.post_type_id}>
                {p.name} ({p.code})
              </option>
            ))}
          </select>

          <input
            type="date"
            required
            value={resolveForm.date}
            onChange={(e) => setResolveForm({ ...resolveForm, date: e.target.value })}
            className="px-3 py-1.5 border border-gray-300 rounded-md"
          />

          <button
            type="submit"
            className="px-4 py-1.5 bg-slate-100 text-slate-800 font-semibold rounded-md hover:bg-slate-200 transition"
          >
            Resolve Rate
          </button>
        </form>

        {resolvedResult && (
          <div className="p-3 bg-gray-50 border border-gray-200 rounded-md text-xs flex items-center justify-between">
            <div>
              <span className="font-medium text-gray-600">Resolution Source: </span>
              <span className="font-bold uppercase text-slate-800">{resolvedResult.source}</span>
            </div>
            {resolvedResult.resolved ? (
              <div className="font-bold text-emerald-700">
                ₹{resolvedResult.rate?.rate_amount} / {resolvedResult.rate?.rate_type} (v{resolvedResult.rate?.version})
              </div>
            ) : (
              <div className="font-semibold text-rose-600">No applicable rate found for this date.</div>
            )}
          </div>
        )}
      </div>

      {/* Billing Rates Table */}
      <div className="bg-white rounded-md border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 font-bold text-xs text-gray-900 uppercase">
          Active Client & Site Billing Rates
        </div>
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider">
            <tr>
              <th className="p-3">Client</th>
              <th className="p-3">Scope / Site</th>
              <th className="p-3">Post Type</th>
              <th className="p-3">Rate Amount</th>
              <th className="p-3">Effective Period</th>
              <th className="p-3">Version</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan="6" className="p-6 text-center text-gray-500">
                  Loading rates...
                </td>
              </tr>
            ) : rates.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-6 text-center text-gray-500">
                  No billing rates configured yet.
                </td>
              </tr>
            ) : (
              rates.map((rate) => (
                <tr key={rate.rate_id} className="hover:bg-gray-50/80 transition">
                  <td className="p-3 font-semibold text-gray-900">{rate.client_code}</td>
                  <td className="p-3">
                    {rate.site_code ? (
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-medium">
                        Site {rate.site_code}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-medium">
                        Client Default
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-gray-700">{rate.post_type_name}</td>
                  <td className="p-3 font-mono font-bold text-emerald-700">
                    ₹{rate.rate_amount} <span className="text-[11px] font-normal text-gray-500">/ {rate.rate_type}</span>
                  </td>
                  <td className="p-3 text-[11px] text-gray-600">
                    From {rate.effective_from} {rate.effective_to ? `to ${rate.effective_to}` : '(Indefinite)'}
                  </td>
                  <td className="p-3 font-mono text-[11px] text-gray-500">v{rate.version}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Configure Rate Modal */}
      {showRateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Configure Client Billing Rate</h3>
              <button onClick={() => setShowRateModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleSetRate} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">Client Organization *</label>
                <select
                  required
                  value={rateForm.client_id}
                  onChange={(e) => setRateForm({ ...rateForm, client_id: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="">Select a Client</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>
                      {c.client_code} - {c.legal_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Security Post Type *</label>
                <select
                  required
                  value={rateForm.post_type_id}
                  onChange={(e) => setRateForm({ ...rateForm, post_type_id: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="">Select Post Type</option>
                  {postTypes.map((p) => (
                    <option key={p.post_type_id} value={p.post_type_id}>
                      {p.name} ({p.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Rate Type</label>
                  <select
                    value={rateForm.rate_type}
                    onChange={(e) => setRateForm({ ...rateForm, rate_type: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  >
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Amount (INR) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="150.00"
                    value={rateForm.rate_amount}
                    onChange={(e) => setRateForm({ ...rateForm, rate_amount: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Effective From Date *</label>
                <input
                  type="date"
                  required
                  value={rateForm.effective_from}
                  onChange={(e) => setRateForm({ ...rateForm, effective_from: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowRateModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : 'Save Rate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


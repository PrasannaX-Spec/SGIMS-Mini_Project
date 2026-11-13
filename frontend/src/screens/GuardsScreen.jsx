import React, { useState, useEffect } from 'react';
import { 
  Users, UserCheck, ShieldAlert, Award, FileText, Plus, Search, 
  Filter, CheckCircle2, XCircle, Clock, AlertTriangle, Eye 
} from 'lucide-react';
import { guardApi, masterApi } from '../api';

export default function GuardsScreen() {
  const [metrics, setMetrics] = useState(null);
  const [guards, setGuards] = useState([]);
  const [postTypes, setPostTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Modals
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [selectedGuard, setSelectedGuard] = useState(null);
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [showDocModal, setShowDocModal] = useState(false);
  const [showBankModal, setShowBankModal] = useState(false);
  const [revealedBank, setRevealedBank] = useState(null);
  const [tempAccountPass, setTempAccountPass] = useState(null);

  // Forms
  const [regForm, setRegForm] = useState({
    full_name: '',
    phone: '',
    date_of_birth: '1995-01-01',
    gender: 'male',
    permanent_address: '',
    current_address: '',
    emergency_name: '',
    emergency_phone: '',
    emergency_relation: 'Spouse',
    post_type_id: '',
    aadhaar_number: '',
    home_district: 'Bengaluru Urban',
  });

  const [statusForm, setStatusForm] = useState({
    status: '',
    reason: '',
  });

  const [docForm, setDocForm] = useState({
    document_type: 'identity_proof',
    document_number: '',
    issue_date: new Date().toISOString().split('T')[0],
    expiry_date: '',
  });

  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [dashRes, listRes, ptRes] = await Promise.all([
        guardApi.getDashboard(),
        guardApi.getGuards({ status: statusFilter || undefined, search: searchTerm || undefined }),
        masterApi.getPostTypes(),
      ]);
      setMetrics(dashRes.data);
      setGuards(listRes.data);
      setPostTypes(ptRes.data);
    } catch (err) {
      console.error('Failed to load guard data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [statusFilter]);

  const handleRegister = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      const payload = {
        full_name: regForm.full_name,
        phone: regForm.phone,
        date_of_birth: regForm.date_of_birth,
        gender: regForm.gender,
        permanent_address: regForm.permanent_address,
        current_address: regForm.current_address,
        aadhaar_number: regForm.aadhaar_number,
        home_district: regForm.home_district,
        emergency_contact: {
          name: regForm.emergency_name,
          phone: regForm.emergency_phone,
          relation: regForm.emergency_relation,
        },
      };
      if (regForm.post_type_id) payload.post_type_id = regForm.post_type_id;

      await guardApi.registerGuard(payload);
      setShowRegisterModal(false);
      setRegForm({
        full_name: '',
        phone: '',
        date_of_birth: '1995-01-01',
        gender: 'male',
        permanent_address: '',
        current_address: '',
        emergency_name: '',
        emergency_phone: '',
        emergency_relation: 'Spouse',
        post_type_id: '',
        aadhaar_number: '',
        home_district: 'Bengaluru Urban',
      });
      fetchData();
    } catch (err) {
      setErrorMsg(err.message || 'Registration failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await guardApi.changeStatus(selectedGuard.employee_id, statusForm);
      setShowStatusModal(false);
      const updated = await guardApi.getGuard(selectedGuard.employee_id);
      setSelectedGuard(updated.data);
      fetchData();
    } catch (err) {
      setErrorMsg(err.message || 'Status transition failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUploadDoc = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await guardApi.uploadDocument(selectedGuard.employee_id, docForm);
      setShowDocModal(false);
      const updated = await guardApi.getGuard(selectedGuard.employee_id);
      setSelectedGuard(updated.data);
      fetchData();
    } catch (err) {
      setErrorMsg(err.message || 'Document upload failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyDoc = async (docId, decision, reason = '') => {
    try {
      await guardApi.verifyDocument(docId, { decision, rejection_reason: reason });
      const updated = await guardApi.getGuard(selectedGuard.employee_id);
      setSelectedGuard(updated.data);
      fetchData();
    } catch (err) {
      alert(err.message || 'Verification update failed.');
    }
  };

  const handleCreateLoginAccount = async () => {
    try {
      const res = await guardApi.createAccount(selectedGuard.employee_id);
      setTempAccountPass(res.data.temporary_password);
      alert(`Login account created! Temporary password: ${res.data.temporary_password}`);
    } catch (err) {
      alert(err.message || 'Account creation failed.');
    }
  };

  const handleRevealBank = async () => {
    try {
      const res = await guardApi.revealBank(selectedGuard.employee_id);
      setRevealedBank(res.data);
    } catch (err) {
      alert(err.message || 'Bank details reveal failed.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-md border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="w-5 h-5 text-slate-700" />
            Guard Lifecycle & Deployability
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            End-to-end security personnel repository, document compliance, armed certifications, and roster eligibility
          </p>
        </div>
        <button
          onClick={() => setShowRegisterModal(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 transition"
        >
          <Plus className="w-4 h-4" />
          Register Walk-In Guard
        </button>
      </div>

      {/* Metrics Header */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
          <div className="bg-white p-3 rounded-md border border-gray-200">
            <span className="text-gray-400 block text-[10px] uppercase font-bold">TOTAL REGISTERED</span>
            <span className="text-lg font-bold text-gray-900">{metrics.total_guards}</span>
          </div>
          <div className="bg-white p-3 rounded-md border border-gray-200">
            <span className="text-blue-600 block text-[10px] uppercase font-bold">APPLICANTS</span>
            <span className="text-lg font-bold text-blue-700">{metrics.applicants}</span>
          </div>
          <div className="bg-white p-3 rounded-md border border-gray-200">
            <span className="text-amber-600 block text-[10px] uppercase font-bold">VERIFICATION</span>
            <span className="text-lg font-bold text-amber-700">{metrics.under_verification}</span>
          </div>
          <div className="bg-white p-3 rounded-md border border-gray-200">
            <span className="text-emerald-600 block text-[10px] uppercase font-bold">ACTIVE GUARDS</span>
            <span className="text-lg font-bold text-emerald-700">{metrics.active}</span>
          </div>
          <div className="bg-white p-3 rounded-md border border-gray-200">
            <span className="text-rose-600 block text-[10px] uppercase font-bold">NON-DEPLOYABLE</span>
            <span className="text-lg font-bold text-rose-700">{metrics.non_deployable_active}</span>
          </div>
          <div className="bg-white p-3 rounded-md border border-gray-200">
            <span className="text-gray-500 block text-[10px] uppercase font-bold">SUSPENDED / OFF</span>
            <span className="text-lg font-bold text-gray-700">{metrics.suspended + metrics.on_leave}</span>
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 bg-white p-4 rounded-md border border-gray-200">
        <div className="flex-1 flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by guard name or employee code..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900"
            />
          </div>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-slate-100 text-gray-700 text-xs font-medium rounded-md hover:bg-gray-200"
          >
            Search
          </button>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md px-3 py-2 focus:outline-none"
          >
            <option value="">All Lifecycle Statuses</option>
            <option value="applicant">Applicant</option>
            <option value="under_verification">Under Verification</option>
            <option value="approved">Approved</option>
            <option value="active">Active</option>
            <option value="on_leave">On Leave</option>
            <option value="suspended">Suspended</option>
            <option value="resigned">Resigned</option>
            <option value="terminated">Terminated</option>
          </select>
        </div>
      </div>

      {/* Guard List Table */}
      <div className="bg-white rounded-md border border-gray-200 overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider">
            <tr>
              <th className="p-3">Employee Code</th>
              <th className="p-3">Guard Name</th>
              <th className="p-3">Phone</th>
              <th className="p-3">Post Type</th>
              <th className="p-3">Status</th>
              <th className="p-3">Deployability (Module 5)</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan="7" className="p-8 text-center text-gray-500">
                  Loading guard profiles...
                </td>
              </tr>
            ) : guards.length === 0 ? (
              <tr>
                <td colSpan="7" className="p-8 text-center text-gray-500">
                  No guard records found. Click &quot;Register Walk-In Guard&quot; to begin.
                </td>
              </tr>
            ) : (
              guards.map((g) => (
                <tr key={g.employee_id} className="hover:bg-gray-50/80 transition">
                  <td className="p-3 font-mono font-bold text-slate-800">{g.employee_code}</td>
                  <td className="p-3">
                    <div className="font-semibold text-gray-900">{g.full_name}</div>
                    <div className="text-[11px] text-gray-500">{g.home_district || 'Karnataka'}</div>
                  </td>
                  <td className="p-3 font-mono text-gray-700">{g.phone}</td>
                  <td className="p-3 text-gray-600">{g.post_type_name || 'Standard Guard'}</td>
                  <td className="p-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        g.lifecycle_status === 'active'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : g.lifecycle_status === 'applicant'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : g.lifecycle_status === 'approved'
                          ? 'bg-cyan-50 text-cyan-700 border border-cyan-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {g.lifecycle_status}
                    </span>
                  </td>
                  <td className="p-3">
                    {g.deployability?.deployable ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Deployable
                      </span>
                    ) : (
                      <span
                        title={g.deployability?.failure_reasons?.join('\n')}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200 cursor-help"
                      >
                        <XCircle className="w-3.5 h-3.5" /> Non-Deployable
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={async () => {
                        const full = await guardApi.getGuard(g.employee_id);
                        setSelectedGuard(full.data);
                      }}
                      className="px-3 py-1 bg-slate-900 text-white font-medium rounded-md hover:bg-slate-800 transition"
                    >
                      Manage Profile
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Guard Detail Drawer / Modal */}
      {selectedGuard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-2xl max-w-3xl w-full border border-gray-200 max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <div>
                <h3 className="font-bold text-base flex items-center gap-2">
                  {selectedGuard.full_name}
                  <span className="text-xs font-mono font-normal bg-slate-800 px-2 py-0.5 rounded text-gray-300">
                    {selectedGuard.employee_code}
                  </span>
                </h3>
                <p className="text-xs text-gray-300">Status: <span className="font-bold uppercase text-emerald-400">{selectedGuard.lifecycle_status}</span></p>
              </div>
              <button onClick={() => setSelectedGuard(null)} className="text-gray-400 hover:text-white text-lg font-bold">
                &times;
              </button>
            </div>

            <div className="p-6 space-y-6 text-xs text-gray-700">
              {/* Deployability Status Box */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-md flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-xs text-gray-900 uppercase tracking-wider">Module 5 Deployability Evaluation</h4>
                  {selectedGuard.deployability?.deployable ? (
                    <div className="text-emerald-700 font-semibold mt-1 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" /> Ready for Roster Allocation
                    </div>
                  ) : (
                    <div className="text-rose-700 font-medium mt-1 space-y-0.5">
                      <div className="flex items-center gap-1.5 font-bold">
                        <AlertTriangle className="w-4 h-4 text-rose-600" /> Ineligible for deployment:
                      </div>
                      <ul className="list-disc pl-5 text-[11px] text-rose-600">
                        {selectedGuard.deployability?.failure_reasons?.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => {
                      setStatusForm({ status: '', reason: '' });
                      setShowStatusModal(true);
                    }}
                    className="px-3 py-1.5 bg-slate-900 text-white font-semibold rounded-md hover:bg-slate-800"
                  >
                    Change Lifecycle Status
                  </button>
                  {selectedGuard.lifecycle_status === 'approved' && (
                    <button
                      onClick={handleCreateLoginAccount}
                      className="px-3 py-1.5 bg-emerald-700 text-white font-semibold rounded-md hover:bg-emerald-800"
                    >
                      Create Mobile Account
                    </button>
                  )}
                </div>
              </div>

              {/* Personal & Emergency Details */}
              <div className="grid grid-cols-2 gap-4 bg-white p-4 rounded-md border border-gray-200">
                <div>
                  <span className="text-gray-400 block text-[10px]">PHONE</span>
                  <span className="font-mono font-semibold">{selectedGuard.phone}</span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">DATE OF BIRTH</span>
                  <span>{selectedGuard.date_of_birth}</span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">MASKED AADHAAR</span>
                  <span className="font-mono">{selectedGuard.aadhaar_masked || 'Not recorded'}</span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">EMERGENCY CONTACT</span>
                  <span>
                    {selectedGuard.emergency_contact?.name || 'N/A'} ({selectedGuard.emergency_contact?.phone || 'No phone'})
                  </span>
                </div>
              </div>

              {/* Documents & Verification Section */}
              <div className="border border-gray-200 rounded-md overflow-hidden">
                <div className="p-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                  <h4 className="font-bold text-xs text-gray-900 uppercase">Compliance Documents</h4>
                  <button
                    onClick={() => setShowDocModal(true)}
                    className="px-2.5 py-1 bg-slate-900 text-white text-[11px] font-semibold rounded-md"
                  >
                    + Upload Document
                  </button>
                </div>
                <div className="divide-y divide-gray-200">
                  {selectedGuard.documents?.length === 0 ? (
                    <div className="p-4 text-center text-gray-400">No documents uploaded yet.</div>
                  ) : (
                    selectedGuard.documents?.map((doc) => (
                      <div key={doc.document_id} className="p-3 flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-gray-900 capitalize">
                            {doc.document_type.replace('_', ' ')} (v{doc.version})
                          </div>
                          <div className="text-[11px] text-gray-500">
                            Status: <span className="font-bold uppercase">{doc.verification_status}</span>
                            {doc.expiry_date && ` • Expires: ${doc.expiry_date}`}
                          </div>
                          {doc.rejection_reason && (
                            <div className="text-[11px] text-rose-600 mt-0.5">
                              Rejection note: {doc.rejection_reason}
                            </div>
                          )}
                        </div>

                        {doc.verification_status === 'pending' && (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleVerifyDoc(doc.document_id, 'verify')}
                              className="px-2.5 py-1 bg-emerald-600 text-white rounded text-[11px] font-bold"
                            >
                              Verify
                            </button>
                            <button
                              onClick={() => {
                                const r = prompt('Enter mandatory rejection reason:');
                                if (r) handleVerifyDoc(doc.document_id, 'reject', r);
                              }}
                              className="px-2.5 py-1 bg-rose-600 text-white rounded text-[11px] font-bold"
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Sensitive Bank Details (Masked with Audited Reveal) */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-xs text-gray-900 uppercase">Protected Bank & Statutory Data</h4>
                  {!revealedBank ? (
                    <button
                      onClick={handleRevealBank}
                      className="flex items-center gap-1.5 px-3 py-1 bg-slate-900 text-white text-[11px] font-semibold rounded-md hover:bg-slate-800"
                    >
                      <Eye className="w-3.5 h-3.5" /> Reveal Full Bank Account (Audited)
                    </button>
                  ) : (
                    <span className="text-[10px] bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded">
                      ACCESS LOGGED TO AUDIT TRAIL
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <span className="text-gray-400 block text-[10px]">BANK NAME</span>
                    <span className="font-medium">{selectedGuard.masked_bank_details?.bank_name}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block text-[10px]">ACCOUNT NUMBER</span>
                    <span className="font-mono font-bold">
                      {revealedBank ? revealedBank.account_number : selectedGuard.masked_bank_details?.account_number_masked}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400 block text-[10px]">IFSC CODE</span>
                    <span className="font-mono">{selectedGuard.masked_bank_details?.ifsc}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setSelectedGuard(null)}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Walk-in Guard Modal */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-2xl max-w-lg w-full border border-gray-200 max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Register Walk-In Guard</h3>
              <button onClick={() => setShowRegisterModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleRegister} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">Full Legal Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramesh Kumar"
                  value={regForm.full_name}
                  onChange={(e) => setRegForm({ ...regForm, full_name: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Primary Phone Number *</label>
                  <input
                    type="text"
                    required
                    placeholder="+91..."
                    value={regForm.phone}
                    onChange={(e) => setRegForm({ ...regForm, phone: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Date of Birth (Min 18 Yrs) *</label>
                  <input
                    type="date"
                    required
                    value={regForm.date_of_birth}
                    onChange={(e) => setRegForm({ ...regForm, date_of_birth: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Permanent Address *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="Village / Town, District, Karnataka"
                  value={regForm.permanent_address}
                  onChange={(e) => setRegForm({ ...regForm, permanent_address: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="p-3 bg-gray-50 border border-gray-200 rounded-md space-y-2">
                <span className="font-bold text-gray-800 block text-[11px]">Emergency Contact (Mandatory)</span>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    required
                    placeholder="Contact Name"
                    value={regForm.emergency_name}
                    onChange={(e) => setRegForm({ ...regForm, emergency_name: e.target.value })}
                    className="px-3 py-1.5 border border-gray-300 rounded-md bg-white"
                  />
                  <input
                    type="text"
                    required
                    placeholder="Contact Phone"
                    value={regForm.emergency_phone}
                    onChange={(e) => setRegForm({ ...regForm, emergency_phone: e.target.value })}
                    className="px-3 py-1.5 border border-gray-300 rounded-md bg-white"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowRegisterModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Registering...' : 'Register as Applicant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Change Status Modal */}
      {showStatusModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Change Guard Lifecycle Status</h3>
              <button onClick={() => setShowStatusModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleStatusChange} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">New Lifecycle Status *</label>
                <select
                  required
                  value={statusForm.status}
                  onChange={(e) => setStatusForm({ ...statusForm, status: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="">Select target status</option>
                  <option value="under_verification">Under Verification</option>
                  <option value="approved">Approved</option>
                  <option value="active">Active</option>
                  <option value="on_leave">On Leave</option>
                  <option value="suspended">Suspended</option>
                  <option value="resigned">Resigned</option>
                  <option value="terminated">Terminated</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Mandatory Audit Reason *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="State the reason for this lifecycle transition..."
                  value={statusForm.reason}
                  onChange={(e) => setStatusForm({ ...statusForm, reason: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowStatusModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Updating...' : 'Confirm Status Change'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Upload Document Modal */}
      {showDocModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Upload Compliance Document</h3>
              <button onClick={() => setShowDocModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleUploadDoc} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">Document Type *</label>
                <select
                  value={docForm.document_type}
                  onChange={(e) => setDocForm({ ...docForm, document_type: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="identity_proof">Identity Proof (Aadhaar/Voter)</option>
                  <option value="address_proof">Address Proof</option>
                  <option value="arms_licence">Arms Licence (Armed Post)</option>
                  <option value="education_certificate">Education Certificate</option>
                  <option value="bank_proof">Bank Proof</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Document Number</label>
                <input
                  type="text"
                  placeholder="Doc / ID number"
                  value={docForm.document_number}
                  onChange={(e) => setDocForm({ ...docForm, document_number: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Issue Date</label>
                  <input
                    type="date"
                    value={docForm.issue_date}
                    onChange={(e) => setDocForm({ ...docForm, issue_date: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Expiry Date (If applicable)</label>
                  <input
                    type="date"
                    value={docForm.expiry_date}
                    onChange={(e) => setDocForm({ ...docForm, expiry_date: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowDocModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Uploading...' : 'Save Document'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


import React, { useState, useEffect } from 'react';
import { Smartphone, Check, X, Clock, AlertTriangle, RefreshCw, Filter, Search } from 'lucide-react';
import { dcrApi } from '../api';
import Modal from '../components/Modal';

export default function DeviceChangeScreen() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedDcr, setSelectedDcr] = useState(null);
  const [actionType, setActionType] = useState(null); // 'approve' | 'reject'
  const [decisionNote, setDecisionNote] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const fetchRequests = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      const res = await dcrApi.getDCRs(params);
      const data = res.data.results || res.data;
      setRequests(Array.isArray(data) ? data : []);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load device change requests.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  const handleOpenApprove = (dcr) => {
    setSelectedDcr(dcr);
    setActionType('approve');
    setDecisionNote('');
    setErrorMsg('');
  };

  const handleOpenReject = (dcr) => {
    setSelectedDcr(dcr);
    setActionType('reject');
    setDecisionNote('');
    setErrorMsg('');
  };

  const handleCloseModal = () => {
    setSelectedDcr(null);
    setActionType(null);
    setDecisionNote('');
    setErrorMsg('');
  };

  const handleConfirmAction = async () => {
    if (!selectedDcr) return;

    if (actionType === 'reject' && !decisionNote.trim()) {
      setErrorMsg('A rejection reason note is mandatory.');
      return;
    }

    setActionLoading(true);
    setErrorMsg('');
    try {
      if (actionType === 'approve') {
        const res = await dcrApi.approveDCR(selectedDcr.request_id);
        setSuccessMsg(res.data.detail || 'Device change approved successfully.');
      } else {
        const res = await dcrApi.rejectDCR(selectedDcr.request_id, decisionNote.trim());
        setSuccessMsg(res.data.detail || 'Device change request rejected.');
      }
      handleCloseModal();
      fetchRequests();
      setTimeout(() => setSuccessMsg(''), 5000);
    } catch (err) {
      setErrorMsg(err.message || 'Action failed.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Device Change Requests</h2>
          <p className="text-xs text-gray-500">
            Review and decide guard device re-binding requests
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchRequests}
            className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1 text-gray-500" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Alerts */}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-md flex items-center space-x-2">
          <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && !selectedDcr && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-gray-400" />
          <span className="text-xs font-semibold text-gray-700">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md p-1.5 bg-white text-gray-700 focus:ring-1 focus:ring-slate-900"
          >
            <option value="">All Requests</option>
            <option value="PENDING">Pending Approval</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>
        <div className="text-xs text-gray-500 font-medium">
          Total: {requests.length} requests
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-gray-500">Loading device change requests...</div>
        ) : requests.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No device change requests match this filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
              <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Guard Name / Phone</th>
                  <th className="px-4 py-3">Requested Device</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Requested (IST)</th>
                  <th className="px-4 py-3">Decision Note</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {requests.map((req) => (
                  <tr key={req.request_id} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-900">{req.guard_name || 'Guard'}</div>
                      <div className="text-[11px] text-gray-500 font-mono">{req.guard_phone}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-800 flex items-center space-x-1">
                        <Smartphone className="w-3.5 h-3.5 text-gray-400" />
                        <span>{req.new_model || 'Unknown Model'}</span>
                      </div>
                      <div className="text-[11px] text-gray-500">
                        OS: {req.new_os_version || 'N/A'} &bull; App: v{req.new_app_version || '1.0'}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {req.status === 'PENDING' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          <Clock className="w-3 h-3 mr-1" />
                          Pending
                        </span>
                      )}
                      {req.status === 'APPROVED' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <Check className="w-3 h-3 mr-1" />
                          Approved
                        </span>
                      )}
                      {req.status === 'REJECTED' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                          <X className="w-3 h-3 mr-1" />
                          Rejected
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600 font-mono text-[11px]">
                      {req.requested_at_ist}
                    </td>
                    <td className="px-4 py-3 max-w-xs truncate text-gray-500 text-[11px]">
                      {req.decision_note || (req.status === 'PENDING' ? 'Awaiting review' : 'None')}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      {req.status === 'PENDING' ? (
                        <>
                          <button
                            onClick={() => handleOpenApprove(req)}
                            className="inline-flex items-center px-2.5 py-1 bg-emerald-600 text-white font-medium rounded-md hover:bg-emerald-700 shadow-sm transition text-[11px]"
                          >
                            <Check className="w-3 h-3 mr-1" />
                            Approve
                          </button>
                          <button
                            onClick={() => handleOpenReject(req)}
                            className="inline-flex items-center px-2.5 py-1 bg-rose-600 text-white font-medium rounded-md hover:bg-rose-700 shadow-sm transition text-[11px]"
                          >
                            <X className="w-3 h-3 mr-1" />
                            Reject
                          </button>
                        </>
                      ) : (
                        <span className="text-gray-400 text-[11px]">Decided</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Decision Modal */}
      {selectedDcr && (
        <Modal
          isOpen={true}
          onClose={handleCloseModal}
          title={actionType === 'approve' ? 'Approve Device Change' : 'Reject Device Change'}
        >
          <div className="space-y-4">
            {errorMsg && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="p-3 bg-gray-50 rounded-md border border-gray-200 text-xs space-y-1">
              <div>
                <span className="text-gray-500">Guard:</span>{' '}
                <span className="font-semibold text-gray-900">{selectedDcr.guard_name}</span> ({selectedDcr.guard_phone})
              </div>
              <div>
                <span className="text-gray-500">New Phone Model:</span>{' '}
                <span className="font-semibold text-gray-900">{selectedDcr.new_model || 'Unknown'}</span>
              </div>
              <div>
                <span className="text-gray-500">Requested:</span>{' '}
                <span className="font-mono text-gray-700">{selectedDcr.requested_at_ist}</span>
              </div>
            </div>

            {actionType === 'approve' ? (
              <p className="text-xs text-gray-600 leading-relaxed">
                Approving this request will immediately unbind the guard's previous phone, terminate any existing sessions, and bind this new device. The guard will now be able to sign in from the new device.
              </p>
            ) : (
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Reason for Rejection <span className="text-rose-500">*</span>
                </label>
                <textarea
                  value={decisionNote}
                  onChange={(e) => setDecisionNote(e.target.value)}
                  placeholder="State why this phone change is rejected (e.g., Unverified device, phone not registered to guard)..."
                  rows={3}
                  className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  This note will be shown to the guard and recorded in the audit log.
                </p>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={actionLoading}
                className="px-3 py-1.5 border border-gray-300 text-gray-700 font-medium rounded-md text-xs hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmAction}
                disabled={actionLoading}
                className={`px-4 py-1.5 text-white font-medium rounded-md text-xs shadow-sm transition ${
                  actionType === 'approve'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {actionLoading ? 'Processing...' : actionType === 'approve' ? 'Confirm Approval' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}


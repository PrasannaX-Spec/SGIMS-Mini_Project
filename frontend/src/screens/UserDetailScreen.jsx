import React, { useState, useEffect } from 'react';
import { ArrowLeft, Key, Lock, Unlock, Smartphone, LogOut, UserX, UserCheck, Shield, AlertTriangle, Copy, Check } from 'lucide-react';
import { usersApi } from '../api';
import Modal from '../components/Modal';

export default function UserDetailScreen({ userId, onBack }) {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('details');
  const [loginHistory, setLoginHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Modals state
  const [deactivateReason, setDeactivateReason] = useState('');
  const [showDeactivateModal, setShowDeactivateModal] = useState(false);
  const [resetDeviceReason, setResetDeviceReason] = useState('');
  const [showResetDeviceModal, setShowResetDeviceModal] = useState(false);
  const [tempPasswordModal, setTempPasswordModal] = useState(null);
  const [copied, setCopied] = useState(false);

  // Edit fields state
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  const fetchUser = async () => {
    setLoading(true);
    try {
      const res = await usersApi.getUser(userId);
      setUser(res.data);
      setFullName(res.data.full_name || '');
      setEmail(res.data.email || '');
      setPhone(res.data.phone || '');
      setRole(res.data.role || '');
    } catch (err) {
      setError(err.message || 'Failed to load user details.');
    } finally {
      setLoading(false);
    }
  };

  const fetchLoginHistory = async () => {
    try {
      const res = await usersApi.getLoginHistory(userId);
      setLoginHistory(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchUser();
  }, [userId]);

  useEffect(() => {
    if (activeTab === 'history') {
      fetchLoginHistory();
    }
  }, [activeTab]);

  const handleSaveEdit = async () => {
    setError('');
    try {
      const payload = { full_name: fullName };
      if (email !== user.email) payload.email = email;
      if (phone !== user.phone) payload.phone = phone;
      if (role !== user.role) payload.role = role;

      const res = await usersApi.updateUser(userId, payload);
      setUser(res.data);
      setIsEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to update user.');
    }
  };

  const handleDeactivate = async () => {
    if (!deactivateReason.trim()) return;
    try {
      await usersApi.deactivateUser(userId, deactivateReason.trim());
      setShowDeactivateModal(false);
      setDeactivateReason('');
      fetchUser();
    } catch (err) {
      setError(err.message || 'Failed to deactivate user.');
    }
  };

  const handleReactivate = async () => {
    try {
      await usersApi.reactivateUser(userId);
      fetchUser();
    } catch (err) {
      setError(err.message || 'Failed to reactivate user.');
    }
  };

  const handleUnlock = async () => {
    try {
      await usersApi.unlockUser(userId);
      fetchUser();
    } catch (err) {
      setError(err.message || 'Failed to unlock user.');
    }
  };

  const handleAdminResetPassword = async () => {
    try {
      const res = await usersApi.resetPassword(userId);
      setTempPasswordModal(res.data.temporary_password);
      fetchUser();
    } catch (err) {
      setError(err.message || 'Failed to reset password.');
    }
  };

  const handleResetDevice = async () => {
    if (!resetDeviceReason.trim()) return;
    try {
      const res = await usersApi.resetDevice(userId, resetDeviceReason.trim());
      setShowResetDeviceModal(false);
      setResetDeviceReason('');
      setTempPasswordModal(res.data.temporary_password);
      fetchUser();
    } catch (err) {
      setError(err.message || 'Failed to reset device binding.');
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-xs text-gray-500">Loading user details...</div>;
  }

  if (!user) {
    return <div className="p-8 text-center text-xs text-red-500">User not found.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <button
          onClick={onBack}
          className="inline-flex items-center text-xs font-semibold text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Users
        </button>

        <div className="flex flex-wrap items-center gap-2">
          {user.locked_until && (
            <button
              onClick={handleUnlock}
              className="px-3 py-1.5 text-xs font-semibold bg-amber-600 text-white rounded hover:bg-amber-700 flex items-center space-x-1"
            >
              <Unlock className="w-3.5 h-3.5" /> <span>Unlock Account</span>
            </button>
          )}

          <button
            onClick={handleAdminResetPassword}
            className="px-3 py-1.5 text-xs font-semibold bg-slate-800 text-white rounded hover:bg-slate-700 flex items-center space-x-1"
          >
            <Key className="w-3.5 h-3.5" /> <span>Reset Password</span>
          </button>

          {user.role === 'GUARD' && (
            <button
              onClick={() => setShowResetDeviceModal(true)}
              className="px-3 py-1.5 text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-300 rounded hover:bg-slate-200 flex items-center space-x-1"
            >
              <Smartphone className="w-3.5 h-3.5" /> <span>Reset Device Binding</span>
            </button>
          )}

          {user.status === 'ACTIVE' ? (
            <button
              onClick={() => setShowDeactivateModal(true)}
              className="px-3 py-1.5 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-700 flex items-center space-x-1"
            >
              <UserX className="w-3.5 h-3.5" /> <span>Deactivate</span>
            </button>
          ) : (
            <button
              onClick={handleReactivate}
              className="px-3 py-1.5 text-xs font-semibold bg-green-600 text-white rounded hover:bg-green-700 flex items-center space-x-1"
            >
              <UserCheck className="w-3.5 h-3.5" /> <span>Reactivate</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md">
          {error}
        </div>
      )}

      {/* Main Card with Tabs */}
      <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
        {/* Header Summary */}
        <div className="p-6 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{user.full_name}</h2>
            <div className="flex items-center space-x-3 mt-1 text-xs text-gray-500 font-mono">
              <span>{user.email || user.phone}</span>
              <span>&bull;</span>
              <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-800 font-semibold">{user.role}</span>
              <span>&bull;</span>
              <span className={`px-2 py-0.5 rounded font-semibold ${user.status === 'ACTIVE' ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-700'}`}>
                {user.status}
              </span>
            </div>
          </div>
          <div className="text-right text-xs text-gray-400">
            <p>User ID: <span className="font-mono text-gray-600">{user.user_id.slice(0, 8)}...</span></p>
            <p>Version: <span className="font-semibold text-gray-600">v{user.version}</span></p>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="border-b border-gray-200 px-6 flex space-x-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('details')}
            className={`py-3 border-b-2 transition ${activeTab === 'details' ? 'border-slate-900 text-slate-900' : 'border-transparent text-gray-500 hover:text-gray-800'}`}
          >
            Account Details
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 border-b-2 transition ${activeTab === 'history' ? 'border-slate-900 text-slate-900' : 'border-transparent text-gray-500 hover:text-gray-800'}`}
          >
            Login History
          </button>
          {user.role === 'GUARD' && (
            <button
              onClick={() => setActiveTab('device')}
              className={`py-3 border-b-2 transition ${activeTab === 'device' ? 'border-slate-900 text-slate-900' : 'border-transparent text-gray-500 hover:text-gray-800'}`}
            >
              Bound Device
            </button>
          )}
        </div>

        {/* Tab content */}
        <div className="p-6">
          {activeTab === 'details' && (
            <div className="space-y-6 max-w-2xl">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Full Name</label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full text-sm border border-gray-300 rounded p-2"
                    />
                  ) : (
                    <p className="text-sm font-semibold text-gray-900">{user.full_name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Role</label>
                  {isEditing && (user.role === 'ADMIN' || user.role === 'SUPERVISOR') ? (
                    <select
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      className="w-full text-sm border border-gray-300 rounded p-2 bg-white"
                    >
                      <option value="ADMIN">ADMIN</option>
                      <option value="SUPERVISOR">SUPERVISOR</option>
                    </select>
                  ) : (
                    <p className="text-sm font-semibold text-gray-900">{user.role}</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Email Address</label>
                  {isEditing ? (
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full text-sm border border-gray-300 rounded p-2"
                    />
                  ) : (
                    <p className="text-sm font-mono text-gray-900">{user.email || '—'}</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Phone Number</label>
                  {isEditing ? (
                    <input
                      type="text"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className="w-full text-sm border border-gray-300 rounded p-2"
                    />
                  ) : (
                    <p className="text-sm font-mono text-gray-900">{user.phone || '—'}</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Last Login (IST)</label>
                  <p className="text-sm text-gray-900">{user.last_login_ist || 'Never signed in'}</p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Created At</label>
                  <p className="text-sm text-gray-900">{new Date(user.created_at).toLocaleDateString()}</p>
                </div>
              </div>

              {user.status === 'INACTIVE' && user.deactivation_reason && (
                <div className="p-3 bg-red-50 border border-red-200 rounded text-xs text-red-800">
                  <strong>Deactivation Reason:</strong> {user.deactivation_reason}
                </div>
              )}

              <div className="pt-4 border-t border-gray-100 flex items-center space-x-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={handleSaveEdit}
                      className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded hover:bg-slate-800"
                    >
                      Save Changes
                    </button>
                    <button
                      onClick={() => setIsEditing(false)}
                      className="px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-4 py-2 bg-slate-100 text-slate-800 border border-slate-300 text-xs font-semibold rounded hover:bg-slate-200"
                  >
                    Edit Details
                  </button>
                )}
              </div>
            </div>
          )}

          {activeTab === 'history' && (
            <div className="space-y-4">
              {loginHistory.length === 0 ? (
                <p className="text-xs text-gray-500">No login attempts recorded yet.</p>
              ) : (
                <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500 font-semibold uppercase">
                    <tr>
                      <th className="px-3 py-2">Timestamp (IST)</th>
                      <th className="px-3 py-2">Result</th>
                      <th className="px-3 py-2">Platform</th>
                      <th className="px-3 py-2">IP Address</th>
                      <th className="px-3 py-2">Device Model</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-gray-700">
                    {loginHistory.map((h) => (
                      <tr key={h.attempt_id}>
                        <td className="px-3 py-2 font-mono">{h.attempted_at_ist}</td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${h.result === 'SUCCESS' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {h.result}
                          </span>
                        </td>
                        <td className="px-3 py-2">{h.platform}</td>
                        <td className="px-3 py-2 font-mono text-gray-500">{h.ip_address}</td>
                        <td className="px-3 py-2">{h.device_model || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === 'device' && (
            <div className="space-y-4 max-w-lg">
              {user.bound_device ? (
                <div className="p-4 bg-gray-50 border border-gray-200 rounded-md space-y-2 text-xs">
                  <p><strong>Device ID:</strong> <span className="font-mono">{user.bound_device.device_id}</span></p>
                  <p><strong>Model:</strong> {user.bound_device.model || 'Unknown'}</p>
                  <p><strong>OS Version:</strong> {user.bound_device.os_version || 'Unknown'}</p>
                  <p><strong>App Version:</strong> {user.bound_device.app_version || 'Unknown'}</p>
                  <p><strong>Bound At (IST):</strong> {user.bound_device.bound_at}</p>
                </div>
              ) : (
                <p className="text-xs text-gray-500">No active device bound. The first Android device signed into will be bound automatically.</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Deactivate Modal */}
      <Modal
        isOpen={showDeactivateModal}
        onClose={() => setShowDeactivateModal(false)}
        title="Deactivate User Account"
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <p className="text-xs text-gray-600">
            Deactivating this user will immediately revoke all active sessions. This action is audited and can be reversed.
          </p>
          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
              Reason for Deactivation (Mandatory)
            </label>
            <textarea
              required
              rows={3}
              value={deactivateReason}
              onChange={(e) => setDeactivateReason(e.target.value)}
              placeholder="e.g. Guard left service, contract terminated, security precaution"
              className="w-full text-xs border border-gray-300 rounded p-2"
            />
          </div>
          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowDeactivateModal(false)}
              className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded"
            >
              Cancel
            </button>
            <button
              disabled={!deactivateReason.trim()}
              onClick={handleDeactivate}
              className="px-3 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded disabled:opacity-50"
            >
              Deactivate Account
            </button>
          </div>
        </div>
      </Modal>

      {/* Reset Device Binding Modal */}
      <Modal
        isOpen={showResetDeviceModal}
        onClose={() => setShowResetDeviceModal(false)}
        title="Reset Guard Device Binding"
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded">
            <strong>Lost or Stolen Phone Procedure:</strong>
            <p>This action clears the current device binding, revokes all sessions, and issues a temporary password. The guard's next sign-in will bind their new replacement phone.</p>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
              Reason for Reset (Mandatory)
            </label>
            <textarea
              required
              rows={2}
              value={resetDeviceReason}
              onChange={(e) => setResetDeviceReason(e.target.value)}
              placeholder="e.g. Phone lost, screen damaged, new company device issued"
              className="w-full text-xs border border-gray-300 rounded p-2"
            />
          </div>
          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowResetDeviceModal(false)}
              className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded"
            >
              Cancel
            </button>
            <button
              disabled={!resetDeviceReason.trim()}
              onClick={handleResetDevice}
              className="px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded disabled:opacity-50"
            >
              Confirm Device Reset
            </button>
          </div>
        </div>
      </Modal>

      {/* One-Time Temporary Password Display Modal */}
      {tempPasswordModal && (
        <Modal
          isOpen={true}
          onClose={() => setTempPasswordModal(null)}
          title="Temporary Password Issued"
          maxWidth="max-w-md"
        >
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded text-amber-800 text-xs">
              This temporary password will be shown <strong>only once</strong>. Pass it to the user directly.
            </div>
            <div className="flex items-center justify-between p-3 bg-gray-100 border border-gray-300 rounded">
              <span className="font-mono text-sm font-bold text-slate-900 select-all">
                {tempPasswordModal}
              </span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(tempPasswordModal);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="px-2.5 py-1 bg-white border border-gray-300 text-gray-700 text-xs font-medium rounded hover:bg-gray-50 flex items-center space-x-1"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
            <div className="text-right">
              <button
                onClick={() => setTempPasswordModal(null)}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded hover:bg-slate-800"
              >
                Done
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}


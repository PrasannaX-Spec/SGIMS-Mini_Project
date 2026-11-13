import React, { useState } from 'react';
import { Copy, Check, AlertTriangle, Key } from 'lucide-react';
import Modal from '../components/Modal';
import { usersApi } from '../api';

export default function CreateUserModal({ isOpen, onClose, onUserCreated }) {
  const [role, setRole] = useState('SUPERVISOR');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [deliveryMethod, setDeliveryMethod] = useState('temporary_password');
  const [guardProfileId, setGuardProfileId] = useState('');
  const [clientCompanyId, setClientCompanyId] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // One-time temp password display state (FR-1.10, AC-64)
  const [createdTempPassword, setCreatedTempPassword] = useState(null);
  const [createdUserName, setCreatedUserName] = useState('');
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload = {
        role,
        full_name: fullName.trim(),
        delivery_method: role === 'GUARD' ? 'temporary_password' : deliveryMethod,
      };

      if (role === 'GUARD') {
        payload.phone = phone.trim();
        if (guardProfileId) payload.guard_profile_id = guardProfileId.trim();
      } else {
        payload.email = email.trim();
        if (role === 'CLIENT' && clientCompanyId) {
          payload.client_company_id = clientCompanyId.trim();
        }
      }

      const res = await usersApi.createUser(payload);

      if (res.data.temporary_password) {
        setCreatedTempPassword(res.data.temporary_password);
        setCreatedUserName(res.data.full_name);
      } else {
        onUserCreated();
        onClose();
      }
    } catch (err) {
      setError(err.message || 'Failed to create user');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (createdTempPassword) {
      navigator.clipboard.writeText(createdTempPassword);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleFinish = () => {
    setCreatedTempPassword(null);
    onUserCreated();
    onClose();
  };

  return (
    <>
      {/* Creation Modal */}
      {!createdTempPassword && (
        <Modal isOpen={isOpen} onClose={onClose} title="Create New System User" maxWidth="max-w-md">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                Role
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-md p-2 bg-white"
              >
                <option value="SUPERVISOR">Supervisor (Web & Mobile)</option>
                <option value="ADMIN">Admin (Web only)</option>
                <option value="GUARD">Guard (Mobile only)</option>
                <option value="CLIENT">Client (Mobile only)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                Full Name
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Rajesh Kumar"
                className="w-full text-sm border border-gray-300 rounded-md p-2"
              />
            </div>

            {role === 'GUARD' ? (
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                  10-Digit Mobile Phone (Login ID)
                </label>
                <input
                  type="text"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="9876543210"
                  className="w-full text-sm border border-gray-300 rounded-md p-2"
                />
                <p className="text-[11px] text-gray-500 mt-1">Guards log in with phone number.</p>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                  Email Address (Login ID)
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@agency.local"
                  className="w-full text-sm border border-gray-300 rounded-md p-2"
                />
              </div>
            )}

            {/* Delivery method (for non-guards) */}
            {role !== 'GUARD' && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                  Initial Credential Delivery
                </label>
                <div className="flex space-x-4 text-xs">
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="delivery"
                      value="temporary_password"
                      checked={deliveryMethod === 'temporary_password'}
                      onChange={() => setDeliveryMethod('temporary_password')}
                    />
                    <span>Temporary password (shown on screen)</span>
                  </label>
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="delivery"
                      value="invite"
                      checked={deliveryMethod === 'invite'}
                      onChange={() => setDeliveryMethod('invite')}
                    />
                    <span>Invite email link (72h)</span>
                  </label>
                </div>
              </div>
            )}

            {/* Links for Guard / Client */}
            {role === 'GUARD' && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                  Linked Guard Profile ID (Module 3)
                </label>
                <input
                  type="text"
                  value={guardProfileId}
                  onChange={(e) => setGuardProfileId(e.target.value)}
                  placeholder="Optional UUID until Module 3"
                  className="w-full text-xs font-mono border border-gray-300 rounded-md p-2"
                />
              </div>
            )}

            {role === 'CLIENT' && (
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase mb-1">
                  Linked Client Company ID (Module 2)
                </label>
                <input
                  type="text"
                  value={clientCompanyId}
                  onChange={(e) => setClientCompanyId(e.target.value)}
                  placeholder="Optional UUID until Module 2"
                  className="w-full text-xs font-mono border border-gray-300 rounded-md p-2"
                />
              </div>
            )}

            <div className="pt-2 flex justify-end space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* One-Time Temporary Password Display Modal (FR-1.10, AC-64) */}
      {createdTempPassword && (
        <Modal isOpen={true} onClose={handleFinish} title="Temporary Credentials Issued" maxWidth="max-w-md">
          <div className="space-y-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md flex items-start space-x-2 text-amber-800 text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Important Security Notice:</p>
                <p>This temporary password is shown <strong>only once</strong> and cannot be recovered or viewed again after closing this window.</p>
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-1">User: <strong className="text-gray-800">{createdUserName}</strong></p>
              <div className="flex items-center justify-between p-3 bg-gray-100 border border-gray-300 rounded-md">
                <span className="font-mono text-sm font-bold tracking-wider text-slate-900 select-all">
                  {createdTempPassword}
                </span>
                <button
                  onClick={handleCopy}
                  className="px-2.5 py-1 bg-white border border-gray-300 text-gray-700 text-xs font-medium rounded hover:bg-gray-50 flex items-center space-x-1"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <p className="text-xs text-gray-500">
              The user will be required to choose their own new password upon their first sign-in.
            </p>

            <div className="pt-2 text-right">
              <button
                onClick={handleFinish}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                Done
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}


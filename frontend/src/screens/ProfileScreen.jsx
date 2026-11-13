import React, { useState, useEffect } from 'react';
import { User, Shield, Lock, Smartphone, Bell, Check, AlertTriangle, Key, LogOut } from 'lucide-react';
import { authApi } from '../api';
import Modal from '../components/Modal';

export default function ProfileScreen({ user, onUserUpdated, onLogoutAll }) {
  const [profile, setProfile] = useState(user || null);
  const [loading, setLoading] = useState(!user);
  const [contactPhone, setContactPhone] = useState(user?.contact_phone || '');
  const [pushNormal, setPushNormal] = useState(true);
  const [browserNotifications, setBrowserNotifications] = useState(true);

  // Password change modal
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Logout all modal
  const [isLogoutAllModalOpen, setIsLogoutAllModalOpen] = useState(false);

  const [savingProfile, setSavingProfile] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [passwordError, setPasswordError] = useState('');

  const fetchProfile = async () => {
    try {
      const res = await authApi.getProfile();
      setProfile(res.data);
      setContactPhone(res.data.contact_phone || '');
      if (res.data.notification_preferences) {
        setPushNormal(res.data.notification_preferences.push_normal ?? true);
        setBrowserNotifications(res.data.notification_preferences.browser_notifications ?? true);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load profile.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    setErrorMsg('');
    try {
      const res = await authApi.updateProfile({
        contact_phone: contactPhone.trim() || null,
        push_normal: pushNormal,
        browser_notifications: browserNotifications,
      });
      setProfile(res.data);
      setSuccessMsg('Profile updated successfully.');
      if (onUserUpdated) onUserUpdated(res.data);
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to save profile changes.');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPasswordError('');

    if (!currentPassword) {
      setPasswordError('Current password is required.');
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.');
      return;
    }
    if (newPassword === currentPassword) {
      setPasswordError('New password must differ from your current password.');
      return;
    }

    setPasswordLoading(true);
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setIsPasswordModalOpen(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setSuccessMsg('Password changed successfully. All other sessions have been revoked.');
      setTimeout(() => setSuccessMsg(''), 6000);
    } catch (err) {
      setPasswordError(err.message || 'Password change failed.');
    } finally {
      setPasswordLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-xs text-gray-500">Loading profile...</div>;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-gray-900">My Profile & Security</h2>
        <p className="text-xs text-gray-500">
          Manage your personal contact details, preferences and account security
        </p>
      </div>

      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-md flex items-center space-x-2">
          <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Read-Only Info */}
        <div className="bg-white p-5 rounded-md border border-gray-200 shadow-sm space-y-4 md:col-span-1">
          <div className="flex items-center space-x-3 pb-3 border-b border-gray-100">
            <div className="w-12 h-12 bg-slate-900 text-white rounded-md flex items-center justify-center font-bold text-lg">
              {profile?.full_name?.charAt(0) || 'U'}
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-900">{profile?.full_name}</h3>
              <span className="inline-block mt-0.5 text-[10px] font-bold px-2 py-0.5 bg-slate-100 text-slate-800 rounded">
                {profile?.role}
              </span>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <span className="text-gray-400 block text-[11px]">Login Identifier</span>
              <span className="font-semibold text-gray-800">{profile?.email || profile?.phone}</span>
            </div>

            <div>
              <span className="text-gray-400 block text-[11px]">Account Status</span>
              <span className="font-semibold text-emerald-600">Active</span>
            </div>

            <div>
              <span className="text-gray-400 block text-[11px]">Assigned Scope</span>
              <div className="mt-1 space-y-1">
                {profile?.scope_grants && profile.scope_grants.length > 0 ? (
                  profile.scope_grants.map((sg, idx) => (
                    <span
                      key={idx}
                      className="inline-block px-1.5 py-0.5 text-[10px] font-mono bg-gray-100 text-gray-700 rounded mr-1"
                    >
                      {sg.scope_type}
                    </span>
                  ))
                ) : (
                  <span className="text-gray-500 font-mono text-[11px]">—</span>
                )}
              </div>
            </div>

            <div>
              <span className="text-gray-400 block text-[11px]">Member Since</span>
              <span className="text-gray-600 font-mono text-[11px]">
                {profile?.created_at ? new Date(profile.created_at).toLocaleDateString('en-IN') : '—'}
              </span>
            </div>
          </div>

          <div className="pt-3 border-t border-gray-100 text-[11px] text-gray-400">
            <Shield className="w-3.5 h-3.5 inline mr-1 text-gray-400" />
            <span>Role & scope are managed by Admin</span>
          </div>
        </div>

        {/* Right Column: Editable Details & Security */}
        <div className="space-y-6 md:col-span-2">
          {/* Contact Details & Preferences */}
          <form onSubmit={handleSaveProfile} className="bg-white p-5 rounded-md border border-gray-200 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-gray-900 border-b border-gray-100 pb-2">
              Personal Information & Preferences
            </h3>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Secondary Contact Phone
              </label>
              <input
                type="text"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+91 9876543210 (Optional emergency number)"
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
              />
              <p className="text-[10px] text-gray-500 mt-1">
                Used for urgent supervisory operational communication.
              </p>
            </div>

            <div className="space-y-2 pt-2 border-t border-gray-100">
              <span className="block text-xs font-semibold text-gray-700">Notification Alerts</span>
              <label className="flex items-center space-x-2 text-xs text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pushNormal}
                  onChange={(e) => setPushNormal(e.target.checked)}
                  className="rounded border-gray-300 text-slate-900 focus:ring-slate-900"
                />
                <span>Receive push alerts for non-critical routine events</span>
              </label>
              <label className="flex items-center space-x-2 text-xs text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={browserNotifications}
                  onChange={(e) => setBrowserNotifications(e.target.checked)}
                  className="rounded border-gray-300 text-slate-900 focus:ring-slate-900"
                />
                <span>Enable desktop browser notifications for instant alerts</span>
              </label>
            </div>

            <div className="flex justify-end pt-3">
              <button
                type="submit"
                disabled={savingProfile}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 shadow-sm transition disabled:opacity-50"
              >
                {savingProfile ? 'Saving...' : 'Save Profile Changes'}
              </button>
            </div>
          </form>

          {/* Account Security Card */}
          <div className="bg-white p-5 rounded-md border border-gray-200 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-gray-900 border-b border-gray-100 pb-2">
              Account Security & Sessions
            </h3>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-gray-50 rounded-md border border-gray-200">
              <div>
                <h4 className="text-xs font-bold text-gray-900 flex items-center space-x-1.5">
                  <Key className="w-3.5 h-3.5 text-slate-700" />
                  <span>Account Password</span>
                </h4>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  Requires your current password. Never share it with anyone.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPasswordError('');
                  setCurrentPassword('');
                  setNewPassword('');
                  setConfirmPassword('');
                  setIsPasswordModalOpen(true);
                }}
                className="px-3 py-1.5 bg-white border border-gray-300 text-slate-800 text-xs font-semibold rounded-md hover:bg-gray-50 shadow-sm transition whitespace-nowrap"
              >
                Change Password
              </button>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-rose-50/50 rounded-md border border-rose-200">
              <div>
                <h4 className="text-xs font-bold text-rose-900 flex items-center space-x-1.5">
                  <LogOut className="w-3.5 h-3.5 text-rose-600" />
                  <span>Log Out All Other Devices</span>
                </h4>
                <p className="text-[11px] text-rose-700 mt-0.5">
                  Terminates all active web sessions and mobile app logins immediately.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsLogoutAllModalOpen(true)}
                className="px-3 py-1.5 bg-rose-600 text-white text-xs font-semibold rounded-md hover:bg-rose-700 shadow-sm transition whitespace-nowrap"
              >
                Log Out All Devices
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Change Password Modal */}
      {isPasswordModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsPasswordModalOpen(false)}
          title="Change Account Password"
        >
          <form onSubmit={handleChangePassword} className="space-y-4">
            {passwordError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{passwordError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Current Password <span className="text-rose-500">*</span>
              </label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                New Password <span className="text-rose-500">*</span>
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                placeholder="At least 8 chars with letter and number"
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Confirm New Password <span className="text-rose-500">*</span>
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div className="p-3 bg-amber-50 rounded-md border border-amber-200 text-[11px] text-amber-800">
              <span className="font-semibold">Security Note:</span> Changing your password will invalidate all active sessions across your browsers and mobile devices.
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsPasswordModalOpen(false)}
                disabled={passwordLoading}
                className="px-3 py-1.5 border border-gray-300 text-gray-700 font-medium rounded-md text-xs hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={passwordLoading}
                className="px-4 py-1.5 bg-slate-900 text-white font-medium rounded-md text-xs hover:bg-slate-800 shadow-sm transition disabled:opacity-50"
              >
                {passwordLoading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Logout All Confirmation Modal */}
      {isLogoutAllModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsLogoutAllModalOpen(false)}
          title="Confirm Global Sign Out"
        >
          <div className="space-y-4">
            <p className="text-xs text-gray-600 leading-relaxed">
              Are you sure you want to log out from all devices? This will immediately terminate all active web sessions and mobile app logins for your account. You will need to sign in again everywhere.
            </p>
            <div className="flex justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsLogoutAllModalOpen(false)}
                className="px-3 py-1.5 border border-gray-300 text-gray-700 font-medium rounded-md text-xs hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsLogoutAllModalOpen(false);
                  if (onLogoutAll) onLogoutAll();
                }}
                className="px-4 py-1.5 bg-rose-600 text-white font-medium rounded-md text-xs hover:bg-rose-700 shadow-sm transition"
              >
                Sign Out Everywhere
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}


import React, { useState } from 'react';
import { Lock, Check, X, AlertCircle } from 'lucide-react';
import { authApi } from '../api';

export default function SetPasswordScreen({ token, isForcedChange = false, onSuccess }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Live rule checks (FR-1.4)
  const isLengthValid = newPassword.length >= 8 && newPassword.length <= 64;
  const hasLetter = /[a-zA-Z]/.test(newPassword);
  const hasDigit = /[0-9]/.test(newPassword);
  const passwordsMatch = newPassword.length > 0 && newPassword === confirmPassword;
  const isValid = isLengthValid && hasLetter && hasDigit && passwordsMatch;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    if (!isValid) {
      setErrorMessage('Please ensure your password meets all stated security rules.');
      return;
    }

    setLoading(true);
    try {
      if (isForcedChange) {
        await authApi.changePassword({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_password: confirmPassword,
        });
      } else {
        await authApi.resetPassword({
          token,
          new_password: newPassword,
          confirm_password: confirmPassword,
        });
      }
      onSuccess();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to update password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full mx-auto space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">
            {isForcedChange ? 'Set Your New Password' : 'Create New Password'}
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {isForcedChange
              ? 'Security policy requires you to set your own password before accessing the system.'
              : 'Choose a strong, unique password for your account.'}
          </p>
        </div>

        <div className="bg-white py-8 px-6 shadow-sm rounded-md border border-gray-200 sm:px-8">
          {errorMessage && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-xs font-medium flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isForcedChange && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Current / Temporary Password
                </label>
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                New Password
              </label>
              <input
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                Confirm New Password
              </label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900"
              />
            </div>

            {/* Live Rules Checklist (FR-1.4, AC-5) */}
            <div className="p-3 bg-gray-50 border border-gray-100 rounded-md space-y-1.5 text-xs text-gray-600">
              <div className="flex items-center space-x-2">
                {isLengthValid ? <Check className="w-4 h-4 text-green-600" /> : <X className="w-4 h-4 text-gray-400" />}
                <span className={isLengthValid ? 'text-green-700 font-medium' : ''}>8 to 64 characters in length</span>
              </div>
              <div className="flex items-center space-x-2">
                {hasLetter && hasDigit ? <Check className="w-4 h-4 text-green-600" /> : <X className="w-4 h-4 text-gray-400" />}
                <span className={hasLetter && hasDigit ? 'text-green-700 font-medium' : ''}>At least one letter and one number</span>
              </div>
              <div className="flex items-center space-x-2">
                {passwordsMatch ? <Check className="w-4 h-4 text-green-600" /> : <X className="w-4 h-4 text-gray-400" />}
                <span className={passwordsMatch ? 'text-green-700 font-medium' : ''}>Passwords match exactly</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !isValid}
              className="w-full py-2.5 px-4 rounded-md text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 transition"
            >
              {loading ? 'Saving...' : 'Save Password & Continue'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}


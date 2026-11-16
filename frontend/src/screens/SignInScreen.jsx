import React, { useState } from 'react';
import { Eye, EyeOff, Lock, User, AlertCircle, ArrowRight } from 'lucide-react';
import { authApi } from '../api';

export default function SignInScreen({ onSignInSuccess, onNavigate }) {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    if (!identifier.trim() || !password) {
      setErrorMessage('Please enter both your identifier and password.');
      return;
    }

    setLoading(true);
    try {
      const res = await authApi.signIn({
        identifier: identifier.trim(),
        password: password.trim(),
        platform: 'WEB'
      });
      onSignInSuccess(res.data.user, res.data.must_change_password);
    } catch (err) {
      setErrorMessage(err.message || 'Sign in failed. Check your details and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full mx-auto space-y-8 my-auto">
        {/* Monogram and Heading */}
        <div className="text-center">
          <div className="mx-auto w-14 h-14 bg-slate-900 text-white rounded-md flex items-center justify-center font-bold text-2xl tracking-widest shadow-sm">
            SG
          </div>
          <h2 className="mt-4 text-2xl font-bold tracking-tight text-gray-900">
            Sign In to Security Agency ERP
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Authorized access for Agency Administration and Field Supervisors
          </p>
        </div>

        {/* Card Form */}
        <div className="bg-white py-8 px-6 shadow-sm rounded-md border border-gray-200 sm:px-8">
          {errorMessage && (
            <div className="mb-6 p-4 rounded-md bg-red-50 border border-red-200 flex items-start space-x-3 text-red-800 text-sm">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{errorMessage}</div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1.5">
                Email Address or Mobile Number
              </label>
              <div className="relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="admin@agency.local or 9876543210"
                  className="block w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900 focus:border-slate-900 placeholder-gray-400"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => onNavigate('forgot-password')}
                  className="text-xs font-medium text-slate-700 hover:text-slate-900 hover:underline"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full pl-9 pr-10 py-2 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900 focus:border-slate-900 placeholder-gray-400"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-900 disabled:opacity-60 transition"
              >
                {loading ? 'Verifying credentials...' : 'Sign In'}
                {!loading && <ArrowRight className="ml-2 w-4 h-4" />}
              </button>
            </div>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-100 text-center">
            <p className="text-xs text-gray-500">
              Guards and Clients: Please sign in via the Mobile App.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="text-center text-xs text-gray-500 mt-8 space-x-4">
        <button onClick={() => onNavigate('terms')} className="hover:text-gray-800 underline">Terms and Conditions</button>
        <span>&bull;</span>
        <button onClick={() => onNavigate('privacy')} className="hover:text-gray-800 underline">Privacy Policy</button>
      </footer>
    </div>
  );
}


import React, { useState } from 'react';
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react';
import { authApi } from '../api';

export default function ForgotPasswordScreen({ onNavigate }) {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) return;

    setLoading(true);
    try {
      await authApi.forgotPassword({ email: email.trim() });
    } catch (err) {
      // PRD FR-1.8: Always shows same confirmation whether or not account exists
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full mx-auto space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">
            Reset Password
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Web users (Admin, Supervisor) can request a single-use password reset link.
          </p>
        </div>

        <div className="bg-white py-8 px-6 shadow-sm rounded-md border border-gray-200 sm:px-8">
          {submitted ? (
            <div className="text-center space-y-4">
              <div className="mx-auto w-12 h-12 bg-green-50 rounded-full flex items-center justify-center text-green-600">
                <CheckCircle className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-gray-900">Check your email</h3>
              <p className="text-sm text-gray-600">
                If this email has an account, a reset link has been sent. It is valid for 30 minutes.
              </p>
              <button
                onClick={() => onNavigate('signin')}
                className="mt-4 inline-flex items-center text-sm font-semibold text-slate-800 hover:text-slate-900 hover:underline"
              >
                <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Sign In
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 mb-1">
                  Registered Email Address
                </label>
                <div className="relative rounded-md shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                    <Mail className="h-4 w-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="supervisor@agency.local"
                    className="block w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-md text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-60 transition"
              >
                {loading ? 'Sending link...' : 'Send Reset Link'}
              </button>

              <div className="pt-2 text-center">
                <button
                  type="button"
                  onClick={() => onNavigate('signin')}
                  className="text-xs font-medium text-gray-500 hover:text-gray-800 hover:underline inline-flex items-center"
                >
                  <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Sign In
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}


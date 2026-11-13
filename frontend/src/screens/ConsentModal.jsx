import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, FileText, Check } from 'lucide-react';
import { legalApi } from '../api';

export default function ConsentModal({ onConsentAccepted, onLogout }) {
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleAccept = async () => {
    if (!agreed) {
      setErrorMsg('You must check the box to confirm you agree before continuing.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');
    try {
      await legalApi.submitConsent({
        item: 'TERMS_PRIVACY',
        decision: 'GRANTED',
        app_version: '1.0.0-web',
      });
      if (onConsentAccepted) onConsentAccepted();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to record your consent. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-md shadow-2xl max-w-lg w-full border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="p-5 bg-slate-900 text-white flex items-center space-x-3">
          <ShieldCheck className="w-6 h-6 text-emerald-400 flex-shrink-0" />
          <div>
            <h3 className="text-base font-bold">Terms of Service & Privacy Policy Update</h3>
            <p className="text-xs text-gray-300">Mandatory statutory consent requirement</p>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 text-xs text-gray-700 leading-relaxed">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <p>
            Welcome to the Security Agency ERP system. Before you proceed, you must review and agree to our updated Terms of Service and Privacy Policy.
          </p>

          <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2 text-[11px] text-gray-600">
            <div className="font-semibold text-gray-800">Key Disclosures:</div>
            <ul className="list-disc pl-4 space-y-1">
              <li>Duty timestamps and security actions are permanently audited and cannot be deleted.</li>
              <li>Guard mobile accounts require phone device binding to prevent attendance fraud.</li>
              <li>Location coordinates are collected strictly during scheduled active duty shifts.</li>
            </ul>
          </div>

          <label className="flex items-start space-x-2.5 pt-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 rounded border-gray-300 text-slate-900 focus:ring-slate-900"
            />
            <span className="font-semibold text-gray-900">
              I have read, understood, and accept the Terms & Conditions and Privacy Policy for Karnataka Security Agency ERP.
            </span>
          </label>
        </div>

        {/* Actions */}
        <div className="p-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <button
            type="button"
            onClick={onLogout}
            className="text-xs text-gray-500 hover:text-gray-800 hover:underline"
          >
            Decline & Sign Out
          </button>
          <button
            type="button"
            onClick={handleAccept}
            disabled={submitting || !agreed}
            className="px-4 py-2 bg-slate-900 text-white font-semibold rounded-md text-xs hover:bg-slate-800 shadow-sm transition disabled:opacity-40"
          >
            {submitting ? 'Recording Consent...' : 'Accept & Proceed'}
          </button>
        </div>
      </div>
    </div>
  );
}


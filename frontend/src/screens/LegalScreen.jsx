import React, { useState, useEffect } from 'react';
import { FileText, ShieldCheck, Printer, RefreshCw } from 'lucide-react';
import { legalApi } from '../api';

export default function LegalScreen() {
  const [activeTab, setActiveTab] = useState('terms'); // 'terms' | 'privacy'
  const [termsData, setTermsData] = useState(null);
  const [privacyData, setPrivacyData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDocs = async () => {
      setLoading(true);
      try {
        const [termsRes, privacyRes] = await Promise.all([
          legalApi.getTerms(),
          legalApi.getPrivacy(),
        ]);
        setTermsData(termsRes.data);
        setPrivacyData(privacyRes.data);
      } catch (err) {
        console.error('Failed to load legal documents', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDocs();
  }, []);

  const currentDoc = activeTab === 'terms' ? termsData : privacyData;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Legal, Terms & Privacy</h2>
          <p className="text-xs text-gray-500">
            Mandatory operational conditions and statutory disclosures
          </p>
        </div>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center px-3 py-1.5 bg-white border border-gray-300 text-xs font-semibold rounded-md text-gray-700 hover:bg-gray-50 shadow-sm transition"
        >
          <Printer className="w-3.5 h-3.5 mr-1.5 text-gray-500" />
          <span>Print Document</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('terms')}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'terms'
              ? 'border-slate-900 text-slate-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Terms & Conditions</span>
        </button>

        <button
          onClick={() => setActiveTab('privacy')}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'privacy'
              ? 'border-slate-900 text-slate-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          <span>Privacy Policy</span>
        </button>
      </div>

      {/* Document Sheet */}
      <div className="bg-white p-8 rounded-md border border-gray-200 shadow-sm space-y-6">
        {loading ? (
          <div className="text-center text-xs text-gray-500 py-12">Loading legal document...</div>
        ) : !currentDoc ? (
          <div className="text-center text-xs text-gray-500 py-12">Failed to load legal document.</div>
        ) : (
          <>
            {/* Header / Meta */}
            <div className="border-b border-gray-200 pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  {activeTab === 'terms' ? 'Standard Terms and Conditions of Service' : 'Privacy & Data Protection Policy'}
                </h3>
                <p className="text-xs text-gray-500">Security Agency ERP System &bull; Karnataka, India</p>
              </div>
              <div className="text-left sm:text-right text-xs">
                <span className="inline-block px-2 py-0.5 bg-slate-100 text-slate-800 font-mono text-[11px] font-semibold rounded">
                  Version {currentDoc.version}
                </span>
                <p className="text-[11px] text-gray-500 mt-1 font-mono">
                  Effective: {currentDoc.effective_date}
                </p>
              </div>
            </div>

            {/* Legal Status Notice */}
            {currentDoc.status && (
              <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-md">
                <span className="font-semibold uppercase tracking-wider text-[10px] mr-1">Status:</span>
                {currentDoc.status}
              </div>
            )}

            {/* Sections */}
            <div className="space-y-6 text-xs text-gray-700 leading-relaxed">
              {currentDoc.sections?.map((sec, idx) => (
                <div key={idx} className="space-y-1.5">
                  <h4 className="font-bold text-gray-900 text-sm">{sec.title}</h4>
                  <p className="text-gray-600 whitespace-pre-line">{sec.content}</p>
                </div>
              ))}
            </div>

            {/* Footer Sign-off */}
            <div className="pt-6 border-t border-gray-100 text-[11px] text-gray-400 flex justify-between items-center">
              <span>Security Agency ERP Foundation Module 1</span>
              <span>Compliant with IT Act 2000 & Digital Personal Data Protection</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}


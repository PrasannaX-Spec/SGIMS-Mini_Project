import React, { useState, useEffect } from 'react';
import { Settings, Save, AlertTriangle, Check, RefreshCw, Info } from 'lucide-react';
import { settingsApi } from '../api';
import Modal from '../components/Modal';

export default function SystemSettingsScreen() {
  const [settingsList, setSettingsList] = useState([]);
  const [formData, setFormData] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  // Audit reason modal
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [changeReason, setChangeReason] = useState('');

  const fetchSettings = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await settingsApi.getSettings();
      const list = res.data.settings || [];
      setSettingsList(list);

      const initialValues = {};
      list.forEach((item) => {
        initialValues[item.key] = item.current_value;
      });
      setFormData(initialValues);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load system settings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleChange = (key, val) => {
    setFormData((prev) => ({
      ...prev,
      [key]: val,
    }));
    if (fieldErrors[key]) {
      setFieldErrors((prev) => {
        const copy = { ...prev };
        delete copy[key];
        return copy;
      });
    }
  };

  const handlePreSave = (e) => {
    e.preventDefault();
    setFieldErrors({});

    // Client-side range validation
    const errors = {};
    settingsList.forEach((s) => {
      const val = formData[s.key];
      if (s.type === 'int') {
        const num = parseInt(val, 10);
        if (isNaN(num)) {
          errors[s.key] = 'Must be an integer.';
        } else if (s.min !== undefined && num < s.min) {
          errors[s.key] = `Value cannot be less than ${s.min}.`;
        } else if (s.max !== undefined && num > s.max) {
          errors[s.key] = `Value cannot be greater than ${s.max}.`;
        }
      }
    });

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setChangeReason('');
    setIsConfirmModalOpen(true);
  };

  const handleConfirmSave = async () => {
    if (!changeReason.trim()) {
      setErrorMsg('A reason for updating system settings is required for the audit trail.');
      return;
    }

    setSaving(true);
    setErrorMsg('');
    try {
      // Find modified settings
      const updates = {};
      settingsList.forEach((s) => {
        if (formData[s.key] !== s.current_value) {
          updates[s.key] = formData[s.key];
        }
      });

      if (Object.keys(updates).length === 0) {
        setIsConfirmModalOpen(false);
        setSuccessMsg('No configuration values were modified.');
        setTimeout(() => setSuccessMsg(''), 4000);
        return;
      }

      await settingsApi.updateSettings(updates, changeReason.trim());
      setIsConfirmModalOpen(false);
      setSuccessMsg('System settings updated and cached successfully.');
      fetchSettings();
      setTimeout(() => setSuccessMsg(''), 5000);
    } catch (err) {
      if (err.errors) {
        setFieldErrors(err.errors);
      }
      setErrorMsg(err.message || 'Failed to update system settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">System Settings</h2>
          <p className="text-xs text-gray-500">
            Configure system policies, lockout thresholds, retention periods and timeouts
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchSettings}
            className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-md transition"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
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

      <form onSubmit={handlePreSave} className="space-y-6">
        <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-xs text-gray-500">Loading settings...</div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
              <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3">Setting Parameter</th>
                  <th className="px-4 py-3 w-48">Configured Value</th>
                  <th className="px-4 py-3">Allowed Range / Default</th>
                  <th className="px-4 py-3">Affected Subsystem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {settingsList.map((s) => (
                  <tr key={s.key} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-900">{s.label}</div>
                      <div className="text-[11px] font-mono text-gray-400">{s.key}</div>
                      {fieldErrors[s.key] && (
                        <div className="text-[11px] text-rose-600 font-medium mt-1">
                          {fieldErrors[s.key]}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type={s.type === 'int' ? 'number' : 'text'}
                        value={formData[s.key] ?? ''}
                        onChange={(e) => handleChange(s.key, e.target.value)}
                        className={`w-full text-xs border rounded-md p-1.5 focus:ring-1 focus:ring-slate-900 ${
                          fieldErrors[s.key] ? 'border-rose-400 bg-rose-50' : 'border-gray-300'
                        }`}
                      />
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-[11px]">
                      {s.min !== undefined && s.max !== undefined ? (
                        <span>
                          [{s.min} – {s.max}] &bull; Default:{' '}
                          <span className="font-mono font-semibold">{s.default_value}</span>
                        </span>
                      ) : (
                        <span>
                          Default: <span className="font-mono font-semibold">{s.default_value}</span>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-[11px]">
                      <span className="inline-block px-1.5 py-0.5 rounded bg-gray-100 font-mono text-[10px] text-gray-700">
                        {s.used_by || 'General'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex justify-between items-center p-4 bg-white rounded-md border border-gray-200 shadow-sm">
          <div className="flex items-center space-x-2 text-xs text-gray-500">
            <Info className="w-4 h-4 text-gray-400" />
            <span>Changes take effect immediately and are cached for high performance.</span>
          </div>
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 shadow-sm transition"
          >
            <Save className="w-4 h-4 mr-1.5" />
            <span>Save Configuration</span>
          </button>
        </div>
      </form>

      {/* Confirmation & Audit Reason Modal */}
      {isConfirmModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsConfirmModalOpen(false)}
          title="Confirm Setting Modification"
        >
          <div className="space-y-4">
            <p className="text-xs text-gray-600">
              Modifying system settings impacts agency-wide authentication, notification and retention rules. Please provide a clear justification for this change.
            </p>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Reason for Change <span className="text-rose-500">*</span>
              </label>
              <textarea
                value={changeReason}
                onChange={(e) => setChangeReason(e.target.value)}
                placeholder="E.g., Updated lockout threshold per revised agency security policy 2026..."
                rows={3}
                required
                className="w-full text-xs border border-gray-300 rounded-md p-2 focus:ring-1 focus:ring-slate-900"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setIsConfirmModalOpen(false)}
                disabled={saving}
                className="px-3 py-1.5 border border-gray-300 text-gray-700 font-medium rounded-md text-xs hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSave}
                disabled={saving}
                className="px-4 py-1.5 bg-slate-900 text-white font-medium rounded-md text-xs hover:bg-slate-800 shadow-sm transition disabled:opacity-50"
              >
                {saving ? 'Applying...' : 'Confirm & Save'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}


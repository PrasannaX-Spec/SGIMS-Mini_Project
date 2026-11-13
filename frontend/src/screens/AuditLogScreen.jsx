import React, { useState, useEffect } from 'react';
import { FileText, Download, Filter, RefreshCw, ChevronDown, ChevronRight, Shield, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import { auditApi } from '../api';

export default function AuditLogScreen() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [actionFilter, setActionFilter] = useState('');
  const [recordTypeFilter, setRecordTypeFilter] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const params = {};
      if (actionFilter) params.action = actionFilter;
      if (recordTypeFilter) params.record_type = recordTypeFilter;
      const res = await auditApi.getAuditLogs(params);
      setLogs(res.data.events || []);
      setTotalCount(res.data.total_count || 0);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [actionFilter, recordTypeFilter]);

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Append-Only Audit Trail</h2>
          <p className="text-xs text-gray-500">
            Tamper-proof compliance log of all security and lifecycle events
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => auditApi.exportCsv()}
            className="inline-flex items-center px-3 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 shadow-sm transition"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={fetchLogs}
            className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-md transition"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Immutability Banner */}
      <div className="bg-slate-50 border border-slate-200 p-3 rounded-md flex items-center space-x-2.5 text-xs text-slate-700">
        <Shield className="w-4 h-4 text-slate-600 flex-shrink-0" />
        <div>
          <span className="font-semibold">Immutability Guaranteed:</span>{' '}
          Database triggers unconditionally forbid any <code className="bg-slate-200 px-1 py-0.5 rounded text-[11px]">UPDATE</code> or <code className="bg-slate-200 px-1 py-0.5 rounded text-[11px]">DELETE</code> on audit records. Passwords and hashes are never recorded.
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-md">
          {errorMsg}
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-semibold text-gray-700">Filter:</span>
          </div>

          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md p-1.5 bg-white text-gray-700 focus:ring-1 focus:ring-slate-900"
          >
            <option value="">All Action Codes</option>
            <option value="auth.login">auth.login</option>
            <option value="auth.logout">auth.logout</option>
            <option value="auth.lockout">auth.lockout</option>
            <option value="auth.unlock">auth.unlock</option>
            <option value="auth.password.change">auth.password.change</option>
            <option value="auth.password.reset">auth.password.reset</option>
            <option value="user.created">user.created</option>
            <option value="user.edited">user.edited</option>
            <option value="user.deactivated">user.deactivated</option>
            <option value="user.reactivated">user.reactivated</option>
            <option value="device.change.approved">device.change.approved</option>
            <option value="device.change.rejected">device.change.rejected</option>
            <option value="settings.changed">settings.changed</option>
          </select>

          <select
            value={recordTypeFilter}
            onChange={(e) => setRecordTypeFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md p-1.5 bg-white text-gray-700 focus:ring-1 focus:ring-slate-900"
          >
            <option value="">All Record Types</option>
            <option value="User">User</option>
            <option value="DeviceChangeRequest">DeviceChangeRequest</option>
            <option value="SystemSetting">SystemSetting</option>
            <option value="BoundDevice">BoundDevice</option>
            <option value="ScopeGrant">ScopeGrant</option>
          </select>
        </div>

        <div className="text-xs text-gray-500 font-mono">
          Showing {logs.length} of {totalCount} events
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-gray-500">Loading audit trail...</div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">No audit events match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
              <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="w-8 px-3 py-3"></th>
                  <th className="px-4 py-3">Timestamp (IST)</th>
                  <th className="px-4 py-3">Actor / Role</th>
                  <th className="px-4 py-3">Action Code</th>
                  <th className="px-4 py-3">Target Record</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {logs.map((log) => {
                  const isExpanded = expandedId === log.id;
                  const isSuccess = log.result === 'SUCCESS';
                  return (
                    <React.Fragment key={log.id}>
                      <tr
                        onClick={() => toggleExpand(log.id)}
                        className={`cursor-pointer hover:bg-gray-50 transition ${
                          isExpanded ? 'bg-slate-50/70' : ''
                        }`}
                      >
                        <td className="px-3 py-3 text-gray-400">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-slate-700" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px] text-gray-700 whitespace-nowrap">
                          {log.occurred_at_ist}
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-semibold text-gray-900">{log.actor_name || 'System'}</div>
                          <span className="text-[10px] text-gray-500 font-medium">{log.actor_role || 'SYSTEM'}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-[11px] font-semibold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded">
                            {log.action_code}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          <span className="font-medium">{log.record_type}</span>{' '}
                          {log.record_id && (
                            <span className="text-[11px] text-gray-400 font-mono">
                              #{log.record_id.slice(0, 8)}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isSuccess ? (
                            <span className="inline-flex items-center text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Success
                            </span>
                          ) : (
                            <span className="inline-flex items-center text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                              <XCircle className="w-3 h-3 mr-1" />
                              Failure
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-[11px] text-gray-500 whitespace-nowrap">
                          {log.ip_address || '—'}
                        </td>
                      </tr>

                      {/* Expanded Diff Drawer (FR-1.72) */}
                      {isExpanded && (
                        <tr className="bg-slate-50">
                          <td colSpan={7} className="px-6 py-4 border-t border-b border-gray-200">
                            <div className="space-y-3 text-xs">
                              {log.reason && (
                                <div>
                                  <span className="font-semibold text-gray-700">Action Reason:</span>{' '}
                                  <span className="text-gray-900 font-medium">{log.reason}</span>
                                </div>
                              )}

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                                <div className="bg-white p-3 rounded border border-gray-200">
                                  <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider mb-1">
                                    Previous Values (old_values)
                                  </div>
                                  <pre className="text-[11px] font-mono bg-gray-50 p-2 rounded text-gray-700 overflow-x-auto">
                                    {log.old_values && Object.keys(log.old_values).length > 0
                                      ? JSON.stringify(log.old_values, null, 2)
                                      : 'No previous state'}
                                  </pre>
                                </div>

                                <div className="bg-white p-3 rounded border border-gray-200">
                                  <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider mb-1">
                                    Updated Values (new_values)
                                  </div>
                                  <pre className="text-[11px] font-mono bg-gray-50 p-2 rounded text-gray-700 overflow-x-auto">
                                    {log.new_values && Object.keys(log.new_values).length > 0
                                      ? JSON.stringify(log.new_values, null, 2)
                                      : 'No state modifications'}
                                  </pre>
                                </div>
                              </div>

                              <div className="text-[11px] text-gray-500 font-mono pt-2 border-t border-gray-200 flex flex-wrap gap-4">
                                <span>UTC: {log.occurred_at_utc}</span>
                                <span>Device ID: {log.device_id || 'N/A'}</span>
                                <span className="truncate max-w-md">Client Agent: {log.user_agent || 'N/A'}</span>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


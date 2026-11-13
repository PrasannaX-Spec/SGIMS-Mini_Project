import React, { useState, useEffect } from 'react';
import { Bell, CheckCheck, Check, Clock, AlertTriangle, Send, RefreshCw, Filter } from 'lucide-react';
import { notificationsApi } from '../api';

export default function NotificationCenterScreen({ user }) {
  const [activeTab, setActiveTab] = useState('inbox'); // 'inbox' | 'deliveries'
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterUnread, setFilterUnread] = useState(false);
  const [actionMsg, setActionMsg] = useState('');

  const isAdminOrSupervisor = user?.role === 'ADMIN' || user?.role === 'SUPERVISOR';

  const fetchInbox = async () => {
    setLoading(true);
    try {
      const res = await notificationsApi.getNotifications();
      setNotifications(res.data.notifications || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDeliveries = async () => {
    if (!isAdminOrSupervisor) return;
    setLoading(true);
    try {
      const res = await notificationsApi.getDeliveries();
      setDeliveries(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'inbox') {
      fetchInbox();
    } else {
      fetchDeliveries();
    }
  }, [activeTab]);

  const handleMarkRead = async (id) => {
    try {
      await notificationsApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.notification_id === id ? { ...n, read_at: new Date().toISOString() } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
      setActionMsg('All notifications marked as read.');
      setTimeout(() => setActionMsg(''), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const displayedNotifications = filterUnread
    ? notifications.filter((n) => !n.read_at)
    : notifications;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Notification Center</h2>
          <p className="text-xs text-gray-500">
            View system alerts, operational messages and dispatch logs
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {activeTab === 'inbox' && unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="inline-flex items-center px-3 py-1.5 bg-white border border-gray-300 text-xs font-semibold rounded-md text-gray-700 hover:bg-gray-50 shadow-sm transition"
            >
              <CheckCheck className="w-3.5 h-3.5 mr-1.5 text-slate-700" />
              <span>Mark All as Read ({unreadCount})</span>
            </button>
          )}
          <button
            onClick={activeTab === 'inbox' ? fetchInbox : fetchDeliveries}
            className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-md transition"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-md flex items-center space-x-2">
          <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionMsg}</span>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('inbox')}
          className={`pb-3 px-4 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
            activeTab === 'inbox'
              ? 'border-slate-900 text-slate-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>In-App Notifications</span>
          {unreadCount > 0 && (
            <span className="bg-red-600 text-white text-[10px] px-1.5 py-0.2 rounded-full font-bold">
              {unreadCount}
            </span>
          )}
        </button>

        {isAdminOrSupervisor && (
          <button
            onClick={() => setActiveTab('deliveries')}
            className={`pb-3 px-4 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
              activeTab === 'deliveries'
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Send className="w-4 h-4" />
            <span>Delivery Logs</span>
          </button>
        )}
      </div>

      {/* Tab Content: INBOX */}
      {activeTab === 'inbox' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex items-center justify-between text-xs text-gray-600 bg-white p-3 rounded-md border border-gray-200 shadow-sm">
            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filterUnread}
                  onChange={(e) => setFilterUnread(e.target.checked)}
                  className="rounded border-gray-300 text-slate-900 focus:ring-slate-900"
                />
                <span className="font-medium text-gray-700">Show unread only</span>
              </label>
            </div>
            <div className="text-gray-500 font-mono text-[11px]">
              Showing {displayedNotifications.length} of {notifications.length} notifications
            </div>
          </div>

          {/* List */}
          <div className="bg-white rounded-md border border-gray-200 shadow-sm divide-y divide-gray-100">
            {loading ? (
              <div className="p-8 text-center text-xs text-gray-500">Loading notifications...</div>
            ) : displayedNotifications.length === 0 ? (
              <div className="p-8 text-center text-xs text-gray-500">
                {filterUnread ? 'No unread notifications.' : 'Your notification center is empty.'}
              </div>
            ) : (
              displayedNotifications.map((notif) => {
                const isUnread = !notif.read_at;
                return (
                  <div
                    key={notif.notification_id}
                    className={`p-4 flex items-start justify-between gap-4 transition ${
                      isUnread ? 'bg-slate-50/70 hover:bg-slate-50' : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center space-x-2">
                        {isUnread && (
                          <span className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0" />
                        )}
                        <span className="text-xs font-bold text-gray-900">{notif.subject}</span>
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                          {notif.type_code}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 whitespace-pre-line leading-relaxed">
                        {notif.message}
                      </p>
                      <div className="flex items-center space-x-3 text-[11px] text-gray-400 font-mono pt-1">
                        <span>{notif.created_at_ist}</span>
                        {notif.related_record_type && (
                          <span>
                            Ref: {notif.related_record_type} #{notif.related_record_id?.slice(0, 8)}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex-shrink-0">
                      {isUnread ? (
                        <button
                          onClick={() => handleMarkRead(notif.notification_id)}
                          className="px-2.5 py-1 text-[11px] font-medium text-slate-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-md shadow-sm transition flex items-center space-x-1"
                        >
                          <Check className="w-3 h-3 text-gray-500" />
                          <span>Mark Read</span>
                        </button>
                      ) : (
                        <span className="text-[11px] text-gray-400">Read</span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Tab Content: DELIVERIES (W15) */}
      {activeTab === 'deliveries' && (
        <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-xs text-gray-500">Loading delivery logs...</div>
          ) : deliveries.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500">No delivery logs recorded yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
                <thead className="bg-gray-50 text-gray-600 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">Event Type</th>
                    <th className="px-4 py-3">Recipient</th>
                    <th className="px-4 py-3">Channel</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Attempts</th>
                    <th className="px-4 py-3">Last Attempt (IST)</th>
                    <th className="px-4 py-3">Failure Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {deliveries.map((del) => (
                    <tr key={del.delivery_id} className="hover:bg-gray-50 transition">
                      <td className="px-4 py-3 font-mono font-medium text-gray-900 text-[11px]">
                        {del.type_code || 'EVENT'}
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {del.recipient_name || 'System User'}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block uppercase px-1.5 py-0.5 text-[10px] font-mono bg-slate-100 text-slate-700 rounded">
                          {del.channel}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {del.status === 'SENT' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            Sent
                          </span>
                        )}
                        {del.status === 'PENDING' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            Pending
                          </span>
                        )}
                        {del.status === 'FAILED' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            Failed
                          </span>
                        )}
                        {del.status === 'RETRYING' && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                            Retrying
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-gray-600">
                        {del.attempts}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-gray-600">
                        {del.last_attempt_ist || '—'}
                      </td>
                      <td className="px-4 py-3 text-rose-600 text-[11px] max-w-xs truncate">
                        {del.failure_reason || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


import React, { useState, useEffect } from 'react';
import { Bell, User as UserIcon, LogOut, Shield, ChevronDown } from 'lucide-react';
import { notificationsApi } from '../api';

export default function Navbar({ user, onLogout, onLogoutAll, onNavigate, activeTab }) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (user) {
      notificationsApi.getNotifications()
        .then(res => setUnreadCount(res.data.unread_count || 0))
        .catch(() => {});
    }
  }, [user, activeTab]);

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Monogram Brand Logo (FR-1.87) */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onNavigate('dashboard')}>
          <div className="w-10 h-10 bg-slate-900 text-white rounded-md flex items-center justify-center font-bold text-lg tracking-wider">
            SG
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-900 leading-tight">Security Agency ERP</h1>
            <p className="text-xs text-gray-500 font-medium">Karnataka, India &bull; Foundation</p>
          </div>
        </div>

        {/* Right actions */}
        <div className="flex items-center space-x-4">
          {/* Notification Bell */}
          <button
            onClick={() => onNavigate('notifications')}
            className={`relative p-2 rounded-md hover:bg-gray-100 transition text-gray-600 ${
              activeTab === 'notifications' ? 'bg-gray-100 text-slate-900 font-medium' : ''
            }`}
            title="Notifications"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 bg-red-600 text-white text-xs font-semibold px-1.5 py-0.5 rounded-full">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center space-x-2 p-1.5 rounded-md hover:bg-gray-100 transition border border-gray-200"
            >
              <div className="w-7 h-7 bg-slate-200 text-slate-700 rounded-sm flex items-center justify-center font-medium text-xs">
                {user?.full_name?.charAt(0) || 'U'}
              </div>
              <div className="text-left hidden md:block">
                <p className="text-xs font-semibold text-gray-800 leading-none">{user?.full_name}</p>
                <p className="text-[10px] text-gray-500 uppercase font-semibold mt-0.5">{user?.role}</p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-40">
                <div className="px-4 py-2 border-b border-gray-100">
                  <p className="text-xs font-medium text-gray-500">Signed in as</p>
                  <p className="text-sm font-semibold text-gray-900 truncate">{user?.email || user?.phone}</p>
                  <span className="inline-block mt-1 text-[10px] px-2 py-0.5 bg-slate-100 text-slate-700 font-semibold rounded">
                    {user?.role}
                  </span>
                </div>

                <button
                  onClick={() => { setMenuOpen(false); onNavigate('profile'); }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
                >
                  <UserIcon className="w-4 h-4 text-gray-400" />
                  <span>My Profile</span>
                </button>

                <div className="border-t border-gray-100 my-1"></div>

                <button
                  onClick={() => { setMenuOpen(false); onLogout(); }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
                >
                  <LogOut className="w-4 h-4 text-gray-400" />
                  <span>Sign Out</span>
                </button>

                <button
                  onClick={() => { setMenuOpen(false); onLogoutAll(); }}
                  className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                >
                  <Shield className="w-4 h-4 text-red-500" />
                  <span>Sign Out All Devices</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}


import React from 'react';
import { Users, Smartphone, Bell, FileText, Settings, ShieldCheck, User, Building2, MapPin, DollarSign, UserCheck, FileCheck, Calendar, Clock, Activity } from 'lucide-react';

export default function Sidebar({ user, activeTab, onNavigate }) {
  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';

  const deploymentItems = (isAdmin || user?.role === 'SUPERVISOR')
    ? [
        { id: 'monitoring', label: 'Live Monitoring', icon: Activity },
        { id: 'attendance', label: 'Attendance & Verification', icon: Clock },
        { id: 'roster', label: 'Deployment & Roster', icon: Calendar },
      ]
    : [];

  const commercialItems = (isAdmin || user?.role === 'CLIENT')
    ? [
        { id: 'service-requests', label: 'Requests & Quotations', icon: FileCheck },
      ]
    : [];

  const guardItems = isAdmin
    ? [
        { id: 'guards', label: 'Guards & Verification', icon: UserCheck },
      ]
    : user?.role === 'SUPERVISOR'
    ? [
        { id: 'guards', label: 'Assigned Guards', icon: UserCheck },
      ]
    : [];

  const masterItems = isAdmin
    ? [
        { id: 'clients', label: 'Client Organizations', icon: Building2 },
        { id: 'sites', label: 'Security Sites & Geofences', icon: MapPin },
        { id: 'commercial', label: 'Commercial & Rates', icon: DollarSign },
      ]
    : [
        { id: 'sites', label: 'Assigned Sites', icon: MapPin },
      ];

  const foundationItems = isAdmin
    ? [
        { id: 'users', label: 'User Management', icon: Users },
        { id: 'devices', label: 'Device Requests', icon: Smartphone },
        { id: 'notifications', label: 'Notifications', icon: Bell },
        { id: 'audit', label: 'Audit Log', icon: FileText },
        { id: 'settings', label: 'System Settings', icon: Settings },
        { id: 'profile', label: 'My Profile', icon: User },
        { id: 'legal', label: 'Terms & Privacy', icon: ShieldCheck },
      ]
    : [
        { id: 'profile', label: 'My Profile', icon: User },
        { id: 'notifications', label: 'Notifications', icon: Bell },
        { id: 'legal', label: 'Terms & Privacy', icon: ShieldCheck },
      ];

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-[calc(100vh-4rem)] p-4 flex flex-col justify-between">
      <nav className="space-y-4">
        {/* Module 5: Deployment & Roster */}
        {deploymentItems.length > 0 && (
          <div className="space-y-1">
            <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
              Roster & Deployment
            </div>
            {deploymentItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-sm font-medium transition text-left ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Module 4: Commercials & Service Requests */}
        {commercialItems.length > 0 && (
          <div className="space-y-1">
            <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
              Commercials & Sales
            </div>
            {commercialItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-sm font-medium transition text-left ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Module 3: Guard Management */}
        {guardItems.length > 0 && (
          <div className="space-y-1">
            <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
              Guard Operations
            </div>
            {guardItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-sm font-medium transition text-left ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Module 2: Master Data */}
        <div className="space-y-1">
          <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
            Master Data
          </div>
          {masterItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-sm font-medium transition text-left ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Module 1: Foundation */}
        <div className="space-y-1">
          <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
            Foundation & Admin
          </div>
          {foundationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-sm font-medium transition text-left ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-gray-100 pt-4 px-3 text-[11px] text-gray-400">
        <p className="font-semibold text-gray-600">Karnataka Security ERP</p>
        <p>PostgreSQL 18 &bull; IST Timezone</p>
      </div>
    </aside>
  );
}


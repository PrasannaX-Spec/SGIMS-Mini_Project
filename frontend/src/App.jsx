import React, { useState, useEffect } from 'react';
import { authApi, legalApi } from './api';

// Components
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Footer from './components/Footer';

// Screens
import SignInScreen from './screens/SignInScreen';
import ForgotPasswordScreen from './screens/ForgotPasswordScreen';
import SetPasswordScreen from './screens/SetPasswordScreen';
import UserListScreen from './screens/UserListScreen';
import UserDetailScreen from './screens/UserDetailScreen';
import DeviceChangeScreen from './screens/DeviceChangeScreen';
import NotificationCenterScreen from './screens/NotificationCenterScreen';
import ProfileScreen from './screens/ProfileScreen';
import AuditLogScreen from './screens/AuditLogScreen';
import SystemSettingsScreen from './screens/SystemSettingsScreen';
import LegalScreen from './screens/LegalScreen';
import ConsentModal from './screens/ConsentModal';

// Module 2 Master Data Screens
import ClientsScreen from './screens/ClientsScreen';
import SitesScreen from './screens/SitesScreen';
import CommercialScreen from './screens/CommercialScreen';

// Module 3 Guard Management Screens
import GuardsScreen from './screens/GuardsScreen';

// Module 4 Service Request & Quotations Screen
import ServiceRequestsScreen from './screens/ServiceRequestsScreen';

// Module 5 Deployment and Roster Screen
import DeploymentDashboardScreen from './screens/DeploymentDashboardScreen';

// Module 6 Attendance Screen
import AttendanceDashboardScreen from './screens/AttendanceDashboardScreen';

// Module 7 Live Monitoring Screen
import LiveMonitoringScreen from './screens/LiveMonitoringScreen';

// Module 8 Incident and Request Management Screen
import IncidentManagementScreen from './screens/IncidentManagementScreen';

// Module 9 Panic and Escalation Screen
import PanicEscalationScreen from './screens/PanicEscalationScreen';

// Module 10 Client Portal Screen
import ClientPortalScreen from './screens/ClientPortalScreen';

// Module 11 Billing and Invoices Screen
import BillingInvoicesScreen from './screens/BillingInvoicesScreen';

// Module 12 Armed Guard and Weapons Register Screen
import WeaponsRegisterScreen from './screens/WeaponsRegisterScreen';

// Module 13 Reports and Dashboards Screen
import ReportsDashboardsScreen from './screens/ReportsDashboardsScreen';

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [authView, setAuthView] = useState('signin'); // 'signin' | 'forgot_password' | 'set_password' | 'force_password'
  const [resetToken, setResetToken] = useState(null);

  // App Navigation State
  const [activeTab, setActiveTab] = useState('users'); // 'users' | 'devices' | 'notifications' | 'audit' | 'settings' | 'profile' | 'legal'
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [needsConsent, setNeedsConsent] = useState(false);

  // Check current session & token on initial mount
  useEffect(() => {
    const initApp = async () => {
      // Check query params for reset or invite token
      const urlParams = new URLSearchParams(window.location.search);
      const tokenFromUrl = urlParams.get('token');
      if (tokenFromUrl) {
        setResetToken(tokenFromUrl);
        setAuthView('set_password');
        setAuthChecking(false);
        return;
      }

      // Check current login session
      try {
        const res = await authApi.getProfile();
        const userData = res.data;
        setUser(userData);

        if (userData.must_change_password) {
          setAuthView('force_password');
        } else {
          setActiveTab(userData.role === 'ADMIN' ? 'users' : userData.role === 'CLIENT' ? 'client-portal' : 'profile');
          checkConsent();
        }
      } catch (err) {
        // Unauthenticated - show sign-in screen
        setUser(null);
        setAuthView('signin');
      } finally {
        setAuthChecking(false);
      }
    };

    initApp();
  }, []);

  const checkConsent = async () => {
    try {
      const res = await legalApi.getConsentStatus();
      if (res.data.needs_reconsent) {
        setNeedsConsent(true);
      }
    } catch (err) {
      console.error('Consent check error', err);
    }
  };

  const handleSignInSuccess = (userData, mustChange) => {
    setUser(userData);
    if (mustChange) {
      setAuthView('force_password');
    } else {
      setAuthView('signin');
      setActiveTab(userData.role === 'ADMIN' ? 'users' : userData.role === 'CLIENT' ? 'client-portal' : 'profile');
      checkConsent();
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.error('Logout error', err);
    } finally {
      setUser(null);
      setSelectedUserId(null);
      setNeedsConsent(false);
      setAuthView('signin');
    }
  };

  const handleLogoutAll = async () => {
    try {
      await authApi.logoutAll();
    } catch (err) {
      console.error('Logout all error', err);
    } finally {
      setUser(null);
      setSelectedUserId(null);
      setNeedsConsent(false);
      setAuthView('signin');
    }
  };

  const handlePasswordSetSuccess = () => {
    // Clean token URL if present
    if (window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname);
    }
    setResetToken(null);
    setUser(null);
    setAuthView('signin');
  };

  const handleNavigate = (tab) => {
    if (tab === 'dashboard') {
      setActiveTab(user?.role === 'ADMIN' ? 'users' : user?.role === 'CLIENT' ? 'client-portal' : 'profile');
      setSelectedUserId(null);
    } else if (tab === 'users') {
      setActiveTab('users');
      setSelectedUserId(null);
    } else if (tab === 'terms' || tab === 'privacy') {
      setActiveTab('legal');
    } else {
      setActiveTab(tab);
    }
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 bg-slate-900 text-white rounded-md flex items-center justify-center font-bold text-xl tracking-widest shadow-md animate-pulse">
          SG
        </div>
        <p className="mt-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Initializing Security ERP Foundation...
        </p>
      </div>
    );
  }

  // Unauthenticated / Auth views
  if (!user || authView === 'set_password') {
    if (authView === 'forgot_password') {
      return <ForgotPasswordScreen onNavigate={(view) => setAuthView(view)} />;
    }
    if (authView === 'set_password') {
      return (
        <SetPasswordScreen
          token={resetToken}
          isForcedChange={false}
          onSuccess={handlePasswordSetSuccess}
        />
      );
    }
    return (
      <SignInScreen
        onSignInSuccess={handleSignInSuccess}
        onNavigate={(view) => setAuthView(view)}
      />
    );
  }

  // Force first-login password change (FR-1.11, AC-7)
  if (authView === 'force_password' || user.must_change_password) {
    return (
      <SetPasswordScreen
        isForcedChange={true}
        onSuccess={() => {
          setUser({ ...user, must_change_password: false });
          setAuthView('signin');
          setActiveTab(user.role === 'ADMIN' ? 'users' : user.role === 'CLIENT' ? 'client-portal' : 'profile');
          checkConsent();
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans text-gray-800">
      {/* Mandatory Statutory Consent Modal (FR-1.78) */}
      {needsConsent && (
        <ConsentModal
          onConsentAccepted={() => setNeedsConsent(false)}
          onLogout={handleLogout}
        />
      )}

      {/* Main Top Navigation */}
      <Navbar
        user={user}
        onLogout={handleLogout}
        onLogoutAll={handleLogoutAll}
        onNavigate={handleNavigate}
        activeTab={activeTab}
      />

      {/* Main Workspace Body */}
      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        {/* Left Sidebar */}
        <Sidebar
          user={user}
          activeTab={activeTab}
          onNavigate={handleNavigate}
        />

        {/* Dynamic Screen Content */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          {/* Module 13 Reports & Dashboards */}
          {activeTab === 'reports' && <ReportsDashboardsScreen currentUser={user} />}

          {/* Module 12 Armed Guard & Weapons Register */}
          {activeTab === 'weapons' && <WeaponsRegisterScreen currentUser={user} />}

          {/* Module 11 Billing & Invoices */}
          {activeTab === 'billing-invoices' && <BillingInvoicesScreen currentUser={user} />}

          {/* Module 10 Client Portal */}
          {activeTab === 'client-portal' && <ClientPortalScreen user={user} />}

          {/* Module 9 Panic and Escalation */}
          {activeTab === 'panic' && <PanicEscalationScreen currentUser={user} />}

          {/* Module 8 Incident and Request Management */}
          {activeTab === 'incidents' && <IncidentManagementScreen currentUser={user} />}

          {/* Module 7 Live Monitoring */}
          {activeTab === 'monitoring' && <LiveMonitoringScreen currentUser={user} />}

          {/* Module 6 Attendance & Verification */}
          {activeTab === 'attendance' && <AttendanceDashboardScreen currentUser={user} />}

          {/* Module 5 Deployment & Roster */}
          {activeTab === 'roster' && <DeploymentDashboardScreen currentUser={user} />}

          {/* Module 4 Service Requests & Quotations */}
          {activeTab === 'service-requests' && <ServiceRequestsScreen user={user} />}

          {/* Module 3 Guard Management Screen */}
          {activeTab === 'guards' && <GuardsScreen />}

          {/* Module 2 Master Data Screens */}
          {activeTab === 'clients' && <ClientsScreen />}
          {activeTab === 'sites' && <SitesScreen />}
          {activeTab === 'commercial' && <CommercialScreen />}

          {/* Module 1 Foundation Screens */}
          {activeTab === 'users' && (
            selectedUserId ? (
              <UserDetailScreen
                userId={selectedUserId}
                onBack={() => setSelectedUserId(null)}
              />
            ) : (
              <UserListScreen
                onSelectUser={(userId) => setSelectedUserId(userId)}
              />
            )
          )}

          {activeTab === 'devices' && <DeviceChangeScreen />}

          {activeTab === 'notifications' && (
            <NotificationCenterScreen user={user} />
          )}

          {activeTab === 'audit' && <AuditLogScreen />}

          {activeTab === 'settings' && <SystemSettingsScreen />}

          {activeTab === 'profile' && (
            <ProfileScreen
              user={user}
              onUserUpdated={(updated) => setUser(updated)}
              onLogoutAll={handleLogoutAll}
            />
          )}

          {activeTab === 'legal' && <LegalScreen />}
        </main>
      </div>

      {/* Standard Footer */}
      <Footer onNavigate={handleNavigate} />
    </div>
  );
}

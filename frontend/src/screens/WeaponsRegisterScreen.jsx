import React, { useState, useEffect } from 'react';
import {
  Crosshair, Shield, AlertTriangle, AlertOctagon, CheckCircle2,
  Clock, FileText, QrCode, Eye, EyeOff, Plus, Download, RefreshCw,
  Search, Filter, Lock, Unlock, ArrowRightLeft, UserCheck, Wrench, X
} from 'lucide-react';
import { weaponsApi, masterApi, usersApi } from '../api';

export default function WeaponsRegisterScreen({ currentUser }) {
  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role === 'SUPER_ADMIN';
  const isSupervisor = currentUser?.role === 'SUPERVISOR';
  const isGuard = currentUser?.role === 'GUARD';

  const [activeSubTab, setActiveSubTab] = useState('weapons');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Dashboard KPI data
  const [dashboard, setDashboard] = useState(null);

  // Weapons Master state
  const [weapons, setWeapons] = useState([]);
  const [weaponFilter, setWeaponFilter] = useState('');
  const [weaponSearch, setWeaponSearch] = useState('');

  // Modals state
  const [showAddWeaponModal, setShowAddWeaponModal] = useState(false);
  const [showRevealModal, setShowRevealModal] = useState(false);
  const [selectedWeaponForReveal, setSelectedWeaponForReveal] = useState(null);
  const [revealReason, setRevealReason] = useState('');
  const [revealedSerial, setRevealedSerial] = useState(null);

  const [showQRModal, setShowQRModal] = useState(false);
  const [selectedWeaponForQR, setSelectedWeaponForQR] = useState(null);

  // Licences state
  const [licences, setLicences] = useState([]);
  const [showAddLicenceModal, setShowAddLicenceModal] = useState(false);

  // Transfers / Issue / Return state
  const [guardsList, setGuardsList] = useState([]);
  const [sitesList, setSitesList] = useState([]);
  const [availableWeapons, setAvailableWeapons] = useState([]);
  const [issuedWeapons, setIssuedWeapons] = useState([]);
  const [ammoLots, setAmmoLots] = useState([]);

  // Forms
  const [issueForm, setIssueForm] = useState({
    weapon_id: '',
    guard_id: '',
    site_id: '',
    condition: 'GOOD',
    ammunition_count: 0,
    lot_id: '',
    is_emergency: false,
    emergency_reason: '',
  });

  const [returnForm, setReturnForm] = useState({
    weapon_id: '',
    condition: 'GOOD',
    rounds_returned: 0,
    rounds_expended: 0,
    incident_id: '',
    reason: '',
  });

  const [handoverForm, setHandoverForm] = useState({
    weapon_id: '',
    incoming_guard_id: '',
    condition: 'GOOD',
    ammunition_count: 0,
  });

  // Ammunition State
  const [ammoLedger, setAmmoLedger] = useState([]);
  const [showAddLotModal, setShowAddLotModal] = useState(false);
  const [showStockCountModal, setShowStockCountModal] = useState(false);
  const [stockCountForm, setStockCountForm] = useState({
    location_id: '',
    lot_id: '',
    physical_quantity: 0,
    reason: '',
  });

  // Discrepancy & Recovery
  const [discrepancies, setDiscrepancies] = useState([]);
  const [recoveries, setRecoveries] = useState([]);
  const [guardBlocks, setGuardBlocks] = useState([]);
  const [showAddBlockModal, setShowAddBlockModal] = useState(false);
  const [blockForm, setBlockForm] = useState({ guard_id: '', reason: '' });

  const [showResolveDiscModal, setShowResolveDiscModal] = useState(false);
  const [selectedDisc, setSelectedDisc] = useState(null);
  const [resolveForm, setResolveForm] = useState({
    recount_value: '',
    explanation: '',
    outcome: 'EXPLAINED',
    resolved: true,
  });

  // Daily Custody & Maintenance
  const [dailyCustody, setDailyCustody] = useState([]);
  const [maintenanceLogs, setMaintenanceLogs] = useState([]);
  const [showAddMaintModal, setShowAddMaintModal] = useState(false);
  const [maintForm, setMaintForm] = useState({
    weapon_id: '',
    maintenance_type: 'CLEANING',
    done_by: '',
    outcome: 'PASSED',
    notes: '',
  });

  // Missing / Stolen Report
  const [missingForm, setMissingForm] = useState({
    weapon_id: '',
    description: '',
    is_stolen: false,
  });

  // New Weapon Form
  const [newWeapon, setNewWeapon] = useState({
    weapon_type: 'Pistol',
    make: '',
    model: '',
    calibre: '.32 ACP',
    serial_number: '',
    serial_number_confirm: '',
    acquisition_date: new Date().toISOString().split('T')[0],
    supplier: '',
    licence_id: '',
  });

  // New Licence Form
  const [newLicence, setNewLicence] = useState({
    licence_number: '',
    licence_type: 'Form III Security Agency',
    issuing_authority: 'Police Commissioner Bangalore',
    holder_type: 'AGENCY',
    holder_name: 'Karnataka Security Services Ltd',
    valid_from: new Date().toISOString().split('T')[0],
    valid_until: '',
    max_weapons_allowed: 10,
    max_ammunition_allowed: 500,
  });

  // New Ammunition Lot Form
  const [newLot, setNewLot] = useState({
    lot_number: '',
    ammunition_type: '.32 ACP',
    manufacturer: 'Ordnance Factory Board',
    initial_quantity: 100,
    expiry_date: '',
  });

  // Load Initial Dashboard & Tab Data
  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, wpnRes, licRes] = await Promise.all([
        weaponsApi.getDashboard().catch(() => ({ data: null })),
        weaponsApi.getWeapons().catch(() => ({ data: [] })),
        weaponsApi.getLicences().catch(() => ({ data: [] })),
      ]);

      setDashboard(dashRes.data);
      const wpnData = Array.isArray(wpnRes.data) ? wpnRes.data : wpnRes.data.results || [];
      setWeapons(wpnData);
      setAvailableWeapons(wpnData.filter(w => w.status === 'IN_STORAGE'));
      setIssuedWeapons(wpnData.filter(w => w.status === 'ISSUED'));

      const licData = Array.isArray(licRes.data) ? licRes.data : licRes.data.results || [];
      setLicences(licData);

      // Load reference data
      const [usersRes, sitesRes, ammoRes] = await Promise.all([
        usersApi.getUsers({ role: 'GUARD', status: 'ACTIVE' }).catch(() => ({ data: [] })),
        masterApi.getSites().catch(() => ({ data: [] })),
        weaponsApi.getAmmunitionLots().catch(() => ({ data: [] })),
      ]);

      const uData = Array.isArray(usersRes.data) ? usersRes.data : usersRes.data.results || [];
      setGuardsList(uData);

      const sData = Array.isArray(sitesRes.data) ? sitesRes.data : sitesRes.data.results || [];
      setSitesList(sData);

      const aData = Array.isArray(ammoRes.data) ? ammoRes.data : ammoRes.data.results || [];
      setAmmoLots(aData);
    } catch (err) {
      setError(err.message || 'Failed to load weapon management data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Fetch data specifically for subtabs
  useEffect(() => {
    if (activeSubTab === 'ammunition') {
      weaponsApi.getAmmunitionLedger().then(res => {
        setAmmoLedger(Array.isArray(res.data) ? res.data : res.data.results || []);
      }).catch(() => {});
    } else if (activeSubTab === 'discrepancies') {
      weaponsApi.getDiscrepancies().then(res => {
        setDiscrepancies(Array.isArray(res.data) ? res.data : res.data.results || []);
      }).catch(() => {});
      weaponsApi.getRecoveries().then(res => {
        setRecoveries(Array.isArray(res.data) ? res.data : res.data.results || []);
      }).catch(() => {});
      weaponsApi.getGuardBlocks().then(res => {
        setGuardBlocks(Array.isArray(res.data) ? res.data : res.data.results || []);
      }).catch(() => {});
    } else if (activeSubTab === 'daily-custody') {
      weaponsApi.getDailyCustody().then(res => {
        setDailyCustody(Array.isArray(res.data) ? res.data : res.data.results || []);
      }).catch(() => {});
      weaponsApi.getMaintenanceLogs().then(res => {
        setMaintenanceLogs(Array.isArray(res.data) ? res.data : res.data.results || []);
      }).catch(() => {});
    }
  }, [activeSubTab]);

  const notifySuccess = (msg) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 5000);
  };

  // 1. Weapon Creation Handler
  const handleCreateWeapon = async (e) => {
    e.preventDefault();
    if (newWeapon.serial_number !== newWeapon.serial_number_confirm) {
      alert("Serial number double entry verification failed. The values do not match.");
      return;
    }
    try {
      await weaponsApi.createWeapon(newWeapon);
      notifySuccess("Weapon record registered successfully.");
      setShowAddWeaponModal(false);
      setNewWeapon({
        weapon_type: 'Pistol',
        make: '',
        model: '',
        calibre: '.32 ACP',
        serial_number: '',
        serial_number_confirm: '',
        acquisition_date: new Date().toISOString().split('T')[0],
        supplier: '',
        licence_id: '',
      });
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Error registering weapon record.');
    }
  };

  // 2. Reveal Serial Number Handler
  const handleRevealSerial = async (e) => {
    e.preventDefault();
    if (!revealReason.trim()) {
      alert("A mandatory reason is required to reveal the weapon serial number.");
      return;
    }
    try {
      const res = await weaponsApi.revealSerial(selectedWeaponForReveal.weapon_id, revealReason);
      setRevealedSerial(res.data.serial_number);
      notifySuccess("Serial number revealed and access logged in audit history.");
    } catch (err) {
      alert(err.message || 'Error revealing serial number.');
    }
  };

  // 3. Relabel QR Handler
  const handleRelabelQR = async (weaponId) => {
    if (!window.confirm("Relabelling will increment the label version count and invalidate previous physical QR codes. Confirm?")) {
      return;
    }
    try {
      const res = await weaponsApi.relabelQR(weaponId);
      notifySuccess(res.data.message || "QR relabel recorded successfully.");
      loadInitialData();
      if (selectedWeaponForQR) {
        setShowQRModal(false);
      }
    } catch (err) {
      alert(err.message || 'Error recording QR relabel.');
    }
  };

  // 4. Create Licence Handler
  const handleCreateLicence = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.createLicence(newLicence);
      notifySuccess("Licence record registered successfully.");
      setShowAddLicenceModal(false);
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Error creating licence record.');
    }
  };

  // 5. Weapon Issue Handler
  const handleIssueWeapon = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.issueWeapon({
        ...issueForm,
        ammunition_count: parseInt(issueForm.ammunition_count, 10) || 0,
      });
      notifySuccess("Weapon issue initiated! Status is ISSUE_PENDING awaiting Guard receipt confirmation.");
      setIssueForm({
        weapon_id: '',
        guard_id: '',
        site_id: '',
        condition: 'GOOD',
        ammunition_count: 0,
        lot_id: '',
        is_emergency: false,
        emergency_reason: '',
      });
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Weapon issue failed.');
    }
  };

  // 6. Weapon Return Handler
  const handleReturnWeapon = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.returnWeapon({
        ...returnForm,
        rounds_returned: parseInt(returnForm.rounds_returned, 10) || 0,
        rounds_expended: parseInt(returnForm.rounds_expended, 10) || 0,
      });
      notifySuccess("Weapon return recorded successfully.");
      setReturnForm({
        weapon_id: '',
        condition: 'GOOD',
        rounds_returned: 0,
        rounds_expended: 0,
        incident_id: '',
        reason: '',
      });
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Weapon return failed.');
    }
  };

  // 7. Handover Handler
  const handleHandoverWeapon = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.handoverWeapon({
        ...handoverForm,
        ammunition_count: parseInt(handoverForm.ammunition_count, 10) || 0,
      });
      notifySuccess("Guard-to-guard handover completed and custody reassigned.");
      setHandoverForm({
        weapon_id: '',
        incoming_guard_id: '',
        condition: 'GOOD',
        ammunition_count: 0,
      });
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Handover failed.');
    }
  };

  // 8. Add Ammunition Lot Handler
  const handleCreateAmmoLot = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.createAmmunitionLot(newLot);
      notifySuccess("Ammunition lot added to inventory.");
      setShowAddLotModal(false);
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Error creating ammunition lot.');
    }
  };

  // 9. Stock Count Handler
  const handleStockCount = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.submitStockCount({
        ...stockCountForm,
        physical_quantity: parseInt(stockCountForm.physical_quantity, 10) || 0,
      });
      notifySuccess("Physical count submitted. Any variance recorded for Admin approval.");
      setShowStockCountModal(false);
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Error submitting stock count.');
    }
  };

  // 10. Resolve Discrepancy Handler
  const handleResolveDiscrepancy = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.resolveDiscrepancy(selectedDisc.discrepancy_id, {
        recount_value: resolveForm.recount_value ? parseInt(resolveForm.recount_value, 10) : null,
        explanation: resolveForm.explanation,
        outcome: resolveForm.outcome,
        resolved: true,
      });
      notifySuccess("Discrepancy resolved successfully.");
      setShowResolveDiscModal(false);
      weaponsApi.getDiscrepancies().then(res => {
        setDiscrepancies(Array.isArray(res.data) ? res.data : res.data.results || []);
      });
    } catch (err) {
      alert(err.message || 'Error resolving discrepancy.');
    }
  };

  // 11. Add Guard Weapon Block
  const handleCreateBlock = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.createGuardBlock(blockForm);
      notifySuccess("Guard weapon restriction registered.");
      setShowAddBlockModal(false);
      weaponsApi.getGuardBlocks().then(res => {
        setGuardBlocks(Array.isArray(res.data) ? res.data : res.data.results || []);
      });
    } catch (err) {
      alert(err.message || 'Error creating restriction.');
    }
  };

  // 12. Add Maintenance Log
  const handleCreateMaint = async (e) => {
    e.preventDefault();
    try {
      await weaponsApi.createMaintenanceLog(maintForm);
      notifySuccess("Maintenance log created and weapon status updated.");
      setShowAddMaintModal(false);
      weaponsApi.getMaintenanceLogs().then(res => {
        setMaintenanceLogs(Array.isArray(res.data) ? res.data : res.data.results || []);
      });
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Error recording maintenance.');
    }
  };

  // 13. Urgent Missing/Stolen Report Handler
  const handleReportMissing = async (e) => {
    e.preventDefault();
    if (!window.confirm("CRITICAL ACTION: Reporting a weapon MISSING or STOLEN immediately notifies Admin and Police/Licensing liaison. Proceed?")) {
      return;
    }
    try {
      const res = await weaponsApi.reportMissing(missingForm);
      notifySuccess(`CRITICAL ALERT RECORDED: Weapon reported as ${res.data.status}.`);
      setMissingForm({ weapon_id: '', description: '', is_stolen: false });
      loadInitialData();
    } catch (err) {
      alert(err.message || 'Error reporting missing weapon.');
    }
  };

  // 14. Export Registers Handler
  const handleExport = (type) => {
    weaponsApi.exportRegister(type)
      .then(res => {
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${type}_register_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        notifySuccess(`${type.toUpperCase()} register CSV downloaded.`);
      })
      .catch(() => alert("Export failed."));
  };

  // Filtered Weapons List
  const filteredWeapons = weapons.filter(w => {
    const matchesFilter = weaponFilter ? w.status === weaponFilter : true;
    const matchesSearch = weaponSearch
      ? (w.asset_id?.toLowerCase().includes(weaponSearch.toLowerCase()) ||
         w.make?.toLowerCase().includes(weaponSearch.toLowerCase()) ||
         w.model?.toLowerCase().includes(weaponSearch.toLowerCase()) ||
         w.calibre?.toLowerCase().includes(weaponSearch.toLowerCase()))
      : true;
    return matchesFilter && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Screen Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-gray-200 pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <Crosshair className="w-6 h-6 text-slate-800" />
            <h1 className="text-2xl font-bold text-gray-900">Armed Guard & Weapons Register</h1>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Authoritative custody chain, licence compliance, ammunition ledger & discrepancy monitoring (Module 12)
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="mt-4 md:mt-0 flex items-center space-x-3">
          <button
            onClick={() => loadInitialData()}
            className="p-2 border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700 transition"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {isAdmin && (
            <button
              onClick={() => setShowAddWeaponModal(true)}
              className="flex items-center space-x-2 bg-slate-900 text-white px-3.5 py-2 rounded-md text-sm font-medium hover:bg-slate-800 transition"
            >
              <Plus className="w-4 h-4" />
              <span>Register Weapon</span>
            </button>
          )}
        </div>
      </div>

      {/* Success Notification Banner */}
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-md text-sm text-emerald-800 flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-700 hover:text-emerald-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-300 rounded-md text-sm text-rose-800">
          {error}
        </div>
      )}

      {/* KPI Summary Cards (PRD Section 12.1, Screen 1) */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">Total Weapons</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{dashboard.total_weapons}</div>
            <div className="text-[11px] text-gray-400 mt-0.5">Active Master</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">In Storage</div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">
              {dashboard.status_counts?.IN_STORAGE || 0}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">Armoury / Safe</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">Issued Active</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {dashboard.active_custody_count || 0}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">Guard Custody</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">Maintenance</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {dashboard.status_counts?.IN_MAINTENANCE || 0}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">Inspection / Repair</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">Discrepancies</div>
            <div className="text-2xl font-bold text-rose-600 mt-1">
              {dashboard.open_discrepancies || 0}
            </div>
            <div className="text-[11px] text-rose-500 mt-0.5">Open & Review</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">Licence Expiry</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {dashboard.expiring_licences || 0}
            </div>
            <div className="text-[11px] text-gray-400 mt-0.5">&lt;60d / {dashboard.expired_licences || 0} Expired</div>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-3">
            <div className="text-xs font-medium text-gray-500 uppercase">Recovery Req.</div>
            <div className="text-2xl font-bold text-rose-700 mt-1">
              {dashboard.recovery_required || 0}
            </div>
            <div className="text-[11px] text-rose-600 mt-0.5">Urgent Recovery</div>
          </div>
        </div>
      )}

      {/* Sub-Tabs Navigation */}
      <div className="flex overflow-x-auto border-b border-gray-200 space-x-1 pb-1">
        {[
          { id: 'weapons', label: 'Weapons Master', icon: Crosshair },
          { id: 'licences', label: 'Licences & Compliance', icon: Shield },
          { id: 'transfers', label: 'Issue, Return & Handover', icon: ArrowRightLeft },
          { id: 'ammunition', label: 'Ammunition & Stock Counts', icon: Clock },
          { id: 'discrepancies', label: 'Discrepancies & Recovery', icon: AlertTriangle },
          { id: 'daily-custody', label: 'Daily Custody & Maintenance', icon: FileText },
          { id: 'urgent-report', label: 'Urgent Missing Report', icon: AlertOctagon },
          { id: 'export', label: 'Statutory Exports', icon: Download },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeSubTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id)}
              className={`flex items-center space-x-2 px-3.5 py-2 text-sm font-medium border-b-2 whitespace-nowrap transition ${
                isActive
                  ? 'border-slate-900 text-slate-900 font-semibold'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* ========================================================================= */}
      {/* SUBTAB 1: WEAPONS MASTER (Screens 2, 3, 4)                                */}
      {/* ========================================================================= */}
      {activeSubTab === 'weapons' && (
        <div className="space-y-4">
          {/* Filters & Search */}
          <div className="flex flex-col md:flex-row gap-3 justify-between items-center bg-white p-3 border border-gray-200 rounded-md">
            <div className="flex items-center space-x-3 w-full md:w-auto">
              <div className="relative flex-1 md:w-64">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search Asset ID, Make, Calibre..."
                  value={weaponSearch}
                  onChange={(e) => setWeaponSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900 outline-none"
                />
              </div>

              <select
                value={weaponFilter}
                onChange={(e) => setWeaponFilter(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:ring-1 focus:ring-slate-900 outline-none"
              >
                <option value="">All Statuses</option>
                <option value="IN_STORAGE">In Storage</option>
                <option value="ISSUED">Issued</option>
                <option value="IN_MAINTENANCE">In Maintenance</option>
                <option value="MISSING">Missing</option>
                <option value="LOST_OR_STOLEN">Lost or Stolen</option>
                <option value="RETIRED_OR_DISPOSED">Retired / Disposed</option>
              </select>
            </div>

            <div className="text-xs text-gray-500">
              Showing <strong>{filteredWeapons.length}</strong> registered weapons
            </div>
          </div>

          {/* Weapons Master Table */}
          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-gray-600 font-semibold">
                  <tr>
                    <th className="px-4 py-3 text-left">Asset ID</th>
                    <th className="px-4 py-3 text-left">Type</th>
                    <th className="px-4 py-3 text-left">Make & Model</th>
                    <th className="px-4 py-3 text-left">Calibre</th>
                    <th className="px-4 py-3 text-left">Serial Number</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Relabel Count</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredWeapons.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="px-4 py-8 text-center text-gray-400">
                        No weapons match current search or filters.
                      </td>
                    </tr>
                  ) : (
                    filteredWeapons.map((wpn) => {
                      const isStorage = wpn.status === 'IN_STORAGE';
                      const isIssued = wpn.status === 'ISSUED';
                      const isMaint = wpn.status === 'IN_MAINTENANCE';
                      const isMissing = wpn.status === 'MISSING' || wpn.status === 'LOST_OR_STOLEN';

                      return (
                        <tr key={wpn.weapon_id} className="hover:bg-gray-50 transition">
                          <td className="px-4 py-3 font-mono font-medium text-gray-900">
                            {wpn.asset_id}
                          </td>
                          <td className="px-4 py-3 text-gray-600">{wpn.weapon_type}</td>
                          <td className="px-4 py-3 text-gray-900 font-medium">
                            {wpn.make} {wpn.model}
                          </td>
                          <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                            {wpn.calibre}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">
                            <span className="text-gray-700 bg-gray-100 px-2 py-0.5 rounded border border-gray-200">
                              {wpn.display_serial}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                isStorage
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : isIssued
                                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                  : isMaint
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : isMissing
                                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                  : 'bg-gray-100 text-gray-700 border border-gray-200'
                              }`}
                            >
                              {wpn.status.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-500 text-xs">
                            v{wpn.qr_relabel_count + 1}
                          </td>
                          <td className="px-4 py-3 text-right space-x-2">
                            {/* QR Preview */}
                            <button
                              onClick={() => {
                                setSelectedWeaponForQR(wpn);
                                setShowQRModal(true);
                              }}
                              className="text-gray-600 hover:text-gray-900 text-xs inline-flex items-center space-x-1 p-1 border border-gray-200 rounded hover:bg-gray-100"
                              title="View Weapon QR Label"
                            >
                              <QrCode className="w-3.5 h-3.5" />
                              <span>QR</span>
                            </button>

                            {/* Reveal Serial Modal Button */}
                            {!isAdmin && wpn.display_serial.startsWith('***') && (
                              <button
                                onClick={() => {
                                  setSelectedWeaponForReveal(wpn);
                                  setRevealedSerial(null);
                                  setRevealReason('');
                                  setShowRevealModal(true);
                                }}
                                className="text-blue-600 hover:text-blue-800 text-xs inline-flex items-center space-x-1 p-1 border border-blue-200 rounded hover:bg-blue-50"
                                title="Reveal Serial Number"
                              >
                                <Eye className="w-3.5 h-3.5" />
                                <span>Reveal</span>
                              </button>
                            )}

                            {/* Admin Relabel QR */}
                            {isAdmin && (
                              <button
                                onClick={() => handleRelabelQR(wpn.weapon_id)}
                                className="text-gray-600 hover:text-gray-900 text-xs inline-flex items-center space-x-1 p-1 border border-gray-200 rounded hover:bg-gray-100"
                                title="Relabel QR Code"
                              >
                                <RefreshCw className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 2: LICENCES & COMPLIANCE (Screens 5, 6)                            */}
      {/* ========================================================================= */}
      {activeSubTab === 'licences' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white p-3 border border-gray-200 rounded-md">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Arms Licences Register</h2>
              <p className="text-xs text-gray-500">
                Statutory Form III / individual licences, validity horizons & capacity limits
              </p>
            </div>
            {isAdmin && (
              <button
                onClick={() => setShowAddLicenceModal(true)}
                className="flex items-center space-x-2 bg-slate-900 text-white px-3 py-1.5 rounded-md text-sm font-medium hover:bg-slate-800 transition"
              >
                <Plus className="w-4 h-4" />
                <span>Add Licence</span>
              </button>
            )}
          </div>

          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-gray-600 font-semibold">
                  <tr>
                    <th className="px-4 py-3 text-left">Licence Number</th>
                    <th className="px-4 py-3 text-left">Licence Type</th>
                    <th className="px-4 py-3 text-left">Issuing Authority</th>
                    <th className="px-4 py-3 text-left">Holder</th>
                    <th className="px-4 py-3 text-left">Valid Period</th>
                    <th className="px-4 py-3 text-left">Limits</th>
                    <th className="px-4 py-3 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {licences.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="px-4 py-8 text-center text-gray-400">
                        No licence records registered.
                      </td>
                    </tr>
                  ) : (
                    licences.map((lic) => {
                      const today = new Date();
                      const expiry = new Date(lic.valid_until);
                      const daysLeft = Math.ceil((expiry - today) / (1000 * 60 * 60 * 24));
                      const isExpired = daysLeft < 0;
                      const isWarning = daysLeft >= 0 && daysLeft <= 60;

                      return (
                        <tr key={lic.licence_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono font-medium text-gray-900">
                            {lic.licence_number}
                          </td>
                          <td className="px-4 py-3 text-gray-600">{lic.licence_type}</td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{lic.issuing_authority}</td>
                          <td className="px-4 py-3 text-gray-900 font-medium">
                            {lic.holder_name}
                            <span className="block text-[10px] text-gray-400 font-normal">
                              ({lic.holder_type})
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-600">
                            {lic.valid_from} to <strong>{lic.valid_until}</strong>
                            {isExpired && (
                              <span className="block text-rose-600 font-semibold mt-0.5">
                                Expired {Math.abs(daysLeft)} days ago
                              </span>
                            )}
                            {isWarning && (
                              <span className="block text-amber-600 font-semibold mt-0.5">
                                {daysLeft} days to expiry
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-600">
                            {lic.max_weapons_allowed} Weapons / {lic.max_ammunition_allowed} Rounds
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                isExpired
                                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                  : isWarning
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              }`}
                            >
                              {isExpired ? 'EXPIRED' : isWarning ? 'EXPIRING' : 'ACTIVE'}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 3: ISSUE, RETURN & HANDOVER (Screens 18, 19, 20)                   */}
      {/* ========================================================================= */}
      {activeSubTab === 'transfers' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Issue Weapon Card */}
          <div className="bg-white border border-gray-200 rounded-md p-5 space-y-4">
            <div className="flex items-center space-x-2 border-b border-gray-100 pb-3">
              <ArrowRightLeft className="w-5 h-5 text-slate-800" />
              <div>
                <h3 className="text-base font-semibold text-gray-900">Initiate Weapon Issue</h3>
                <p className="text-xs text-gray-500">
                  Step 1: Supervisor creates transfer. Status remains ISSUE_PENDING until Guard confirms.
                </p>
              </div>
            </div>

            <form onSubmit={handleIssueWeapon} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Select Available Weapon *</label>
                <select
                  required
                  value={issueForm.weapon_id}
                  onChange={(e) => setIssueForm({ ...issueForm, weapon_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                >
                  <option value="">-- Choose Weapon in Storage --</option>
                  {availableWeapons.map((w) => (
                    <option key={w.weapon_id} value={w.weapon_id}>
                      {w.asset_id} - {w.make} {w.model} ({w.calibre})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Select Eligible Guard *</label>
                <select
                  required
                  value={issueForm.guard_id}
                  onChange={(e) => setIssueForm({ ...issueForm, guard_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                >
                  <option value="">-- Choose Active Guard --</option>
                  {guardsList.map((g) => (
                    <option key={g.user_id} value={g.user_id}>
                      {g.full_name} ({g.email})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Site / Deployment</label>
                  <select
                    value={issueForm.site_id}
                    onChange={(e) => setIssueForm({ ...issueForm, site_id: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  >
                    <option value="">Central Armoury</option>
                    {sitesList.map((s) => (
                      <option key={s.site_id} value={s.site_id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Weapon Condition</label>
                  <select
                    value={issueForm.condition}
                    onChange={(e) => setIssueForm({ ...issueForm, condition: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  >
                    <option value="GOOD">Good / Serviceable</option>
                    <option value="FAIR">Fair</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Ammunition Count (Rounds)</label>
                  <input
                    type="number"
                    min="0"
                    max="50"
                    value={issueForm.ammunition_count}
                    onChange={(e) => setIssueForm({ ...issueForm, ammunition_count: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Ammunition Lot</label>
                  <select
                    value={issueForm.lot_id}
                    onChange={(e) => setIssueForm({ ...issueForm, lot_id: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  >
                    <option value="">Default Available Lot</option>
                    {ammoLots.map((lot) => (
                      <option key={lot.lot_id} value={lot.lot_id}>
                        {lot.lot_number} ({lot.ammunition_type})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="border border-amber-200 bg-amber-50 p-3 rounded-md space-y-2">
                <label className="flex items-center space-x-2 text-xs font-medium text-amber-900">
                  <input
                    type="checkbox"
                    checked={issueForm.is_emergency}
                    onChange={(e) => setIssueForm({ ...issueForm, is_emergency: e.target.checked })}
                    className="rounded text-slate-900"
                  />
                  <span>Emergency Issue (Bypass normal roster/attendance prerequisite)</span>
                </label>
                {issueForm.is_emergency && (
                  <input
                    type="text"
                    required
                    placeholder="Mandatory emergency justification reason..."
                    value={issueForm.emergency_reason}
                    onChange={(e) => setIssueForm({ ...issueForm, emergency_reason: e.target.value })}
                    className="w-full text-xs border border-amber-300 rounded p-1.5 bg-white outline-none"
                  />
                )}
              </div>

              <button
                type="submit"
                className="w-full bg-slate-900 text-white py-2 rounded-md text-sm font-medium hover:bg-slate-800 transition"
              >
                Initiate Issue
              </button>
            </form>
          </div>

          {/* Return Weapon Card */}
          <div className="bg-white border border-gray-200 rounded-md p-5 space-y-4">
            <div className="flex items-center space-x-2 border-b border-gray-100 pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <div>
                <h3 className="text-base font-semibold text-gray-900">Process Weapon Return</h3>
                <p className="text-xs text-gray-500">
                  Reconciles rounds: (Issued - Returned - Expended = 0). Mismatches create Discrepancies.
                </p>
              </div>
            </div>

            <form onSubmit={handleReturnWeapon} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Select Currently Issued Weapon *</label>
                <select
                  required
                  value={returnForm.weapon_id}
                  onChange={(e) => setReturnForm({ ...returnForm, weapon_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                >
                  <option value="">-- Choose Issued Weapon --</option>
                  {issuedWeapons.map((w) => (
                    <option key={w.weapon_id} value={w.weapon_id}>
                      {w.asset_id} - {w.make} {w.model}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Rounds Returned *</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={returnForm.rounds_returned}
                    onChange={(e) => setReturnForm({ ...returnForm, rounds_returned: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Rounds Expended</label>
                  <input
                    type="number"
                    min="0"
                    value={returnForm.rounds_expended}
                    onChange={(e) => setReturnForm({ ...returnForm, rounds_expended: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  />
                </div>
              </div>

              {parseInt(returnForm.rounds_expended, 10) > 0 && (
                <div className="p-2.5 bg-rose-50 border border-rose-300 rounded-md">
                  <label className="block text-xs font-medium text-rose-900 mb-1">
                    Linked Incident ID * (Module 8 mandatory)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. INC-2024-0012"
                    value={returnForm.incident_id}
                    onChange={(e) => setReturnForm({ ...returnForm, incident_id: e.target.value })}
                    className="w-full text-xs border border-rose-300 rounded p-1.5 bg-white outline-none"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Return Condition</label>
                <select
                  value={returnForm.condition}
                  onChange={(e) => setReturnForm({ ...returnForm, condition: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                >
                  <option value="GOOD">Good / Serviceable</option>
                  <option value="CLEANING_REQUIRED">Requires Cleaning</option>
                  <option value="DAMAGED">Damaged (Sends to Maintenance)</option>
                  <option value="NEEDS_REPAIR">Needs Armourer Repair</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Return Notes / Comments</label>
                <input
                  type="text"
                  placeholder="Optional condition remarks..."
                  value={returnForm.reason}
                  onChange={(e) => setReturnForm({ ...returnForm, reason: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                />
              </div>

              <button
                type="submit"
                className="w-full bg-emerald-700 text-white py-2 rounded-md text-sm font-medium hover:bg-emerald-800 transition"
              >
                Complete Return
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 4: AMMUNITION & STOCK COUNTS (Screens 7, 8, 9)                     */}
      {/* ========================================================================= */}
      {activeSubTab === 'ammunition' && (
        <div className="space-y-6">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white p-4 border border-gray-200 rounded-md gap-3">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Ammunition Inventory & Ledger</h2>
              <p className="text-xs text-gray-500">
                Tamper-evident immutable ledger. Negative stock strictly prohibited.
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setShowStockCountModal(true)}
                className="flex items-center space-x-1 border border-gray-300 px-3 py-1.5 rounded-md text-xs font-medium hover:bg-gray-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-gray-600" />
                <span>Physical Stock Count</span>
              </button>
              {isAdmin && (
                <button
                  onClick={() => setShowAddLotModal(true)}
                  className="flex items-center space-x-1 bg-slate-900 text-white px-3 py-1.5 rounded-md text-xs font-medium hover:bg-slate-800"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>New Ammo Lot</span>
                </button>
              )}
            </div>
          </div>

          {/* Lots Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {ammoLots.map((lot) => (
              <div key={lot.lot_id} className="bg-white border border-gray-200 rounded-md p-4 space-y-2">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-mono text-xs font-semibold text-gray-900">{lot.lot_number}</span>
                    <span className="block text-xs text-gray-500">{lot.ammunition_type}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {lot.status}
                  </span>
                </div>
                <div className="text-xs text-gray-600">
                  Manufacturer: <strong>{lot.manufacturer || 'OFB'}</strong>
                </div>
              </div>
            ))}
          </div>

          {/* Immutable Ledger Table */}
          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center bg-gray-50">
              <h3 className="text-sm font-semibold text-gray-900">Immutable Ledger Entries</h3>
              <span className="text-xs text-gray-500 font-mono">APPEND-ONLY AUDIT TRAIL</span>
            </div>
            <div className="overflow-x-auto max-h-96">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50 text-gray-600 font-semibold sticky top-0">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Timestamp (IST)</th>
                    <th className="px-4 py-2.5 text-left">Entry Type</th>
                    <th className="px-4 py-2.5 text-left">Type / Calibre</th>
                    <th className="px-4 py-2.5 text-left">Quantity</th>
                    <th className="px-4 py-2.5 text-left">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {ammoLedger.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-4 py-6 text-center text-gray-400">
                        No ledger transactions recorded.
                      </td>
                    </tr>
                  ) : (
                    ammoLedger.map((entry) => {
                      const isPositive = ['RECEIVED', 'RETURNED', 'ADJUSTED'].includes(entry.entry_type);
                      return (
                        <tr key={entry.ledger_entry_id} className="hover:bg-gray-50">
                          <td className="px-4 py-2 text-gray-500 font-mono">
                            {new Date(entry.server_timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                          </td>
                          <td className="px-4 py-2">
                            <span className={`px-2 py-0.5 rounded font-semibold text-[10px] ${
                              entry.entry_type === 'EXPENDED'
                                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                : entry.entry_type === 'ISSUED'
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            }`}>
                              {entry.entry_type}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-gray-700">{entry.ammunition_type}</td>
                          <td className={`px-4 py-2 font-mono font-bold ${isPositive ? 'text-emerald-700' : 'text-rose-700'}`}>
                            {isPositive ? '+' : '-'}{entry.quantity}
                          </td>
                          <td className="px-4 py-2 text-gray-600">{entry.reason || '-'}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 5: DISCREPANCIES & RECOVERY (Screens 10, 11, 12)                   */}
      {/* ========================================================================= */}
      {activeSubTab === 'discrepancies' && (
        <div className="space-y-6">
          {/* Recovery Required Alert Table */}
          <div className="bg-white border border-rose-200 rounded-md overflow-hidden">
            <div className="px-4 py-3 bg-rose-50 border-b border-rose-200 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <AlertOctagon className="w-4 h-4 text-rose-700" />
                <h3 className="text-sm font-semibold text-rose-900">Weapons Requiring Urgent Recovery</h3>
              </div>
              <span className="text-xs text-rose-700 font-medium">
                {recoveries.filter(r => r.status === 'RECOVERY_REQUIRED').length} active recoveries
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50 text-gray-600 font-semibold">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Created At</th>
                    <th className="px-4 py-2.5 text-left">Trigger Reason</th>
                    <th className="px-4 py-2.5 text-left">Rounds Held</th>
                    <th className="px-4 py-2.5 text-left">Notes</th>
                    <th className="px-4 py-2.5 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {recoveries.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-4 py-4 text-center text-gray-400">
                        No active weapon recovery orders.
                      </td>
                    </tr>
                  ) : (
                    recoveries.map((rec) => (
                      <tr key={rec.recovery_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono text-gray-500">
                          {new Date(rec.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-2 font-medium text-rose-700">{rec.trigger_reason}</td>
                        <td className="px-4 py-2 font-mono">{rec.ammunition_rounds}</td>
                        <td className="px-4 py-2 text-gray-600">{rec.notes}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            rec.status === 'RECOVERY_REQUIRED'
                              ? 'bg-rose-100 text-rose-800'
                              : 'bg-gray-100 text-gray-700'
                          }`}>
                            {rec.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Open Discrepancies Table */}
          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
              <h3 className="text-sm font-semibold text-gray-900">Recorded Discrepancies</h3>
              <span className="text-xs text-gray-500 font-medium">Blocking custody mismatches</span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50 text-gray-600 font-semibold">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Discrepancy Type</th>
                    <th className="px-4 py-2.5 text-left">Expected vs Reported</th>
                    <th className="px-4 py-2.5 text-left">Explanation</th>
                    <th className="px-4 py-2.5 text-left">Status</th>
                    <th className="px-4 py-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {discrepancies.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-4 py-6 text-center text-gray-400">
                        Zero discrepancies recorded. All balances reconciled.
                      </td>
                    </tr>
                  ) : (
                    discrepancies.map((disc) => (
                      <tr key={disc.discrepancy_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-900">{disc.discrepancy_type}</td>
                        <td className="px-4 py-2 font-mono text-gray-600">
                          Exp: {JSON.stringify(disc.expected_value)} / Rep: {JSON.stringify(disc.reported_value)}
                        </td>
                        <td className="px-4 py-2 text-gray-700">{disc.explanation}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            disc.status === 'RESOLVED'
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-rose-50 text-rose-700'
                          }`}>
                            {disc.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-right">
                          {isAdmin && disc.status !== 'RESOLVED' && (
                            <button
                              onClick={() => {
                                setSelectedDisc(disc);
                                setShowResolveDiscModal(true);
                              }}
                              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                            >
                              Resolve
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 6: DAILY CUSTODY & MAINTENANCE (Screens 13, 14)                    */}
      {/* ========================================================================= */}
      {activeSubTab === 'daily-custody' && (
        <div className="space-y-6">
          {/* Daily Custody Sheet */}
          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Daily Custody Sheet</h3>
                <p className="text-xs text-gray-500">Live active custody snapshot across all sites</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50 text-gray-600 font-semibold">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Asset ID</th>
                    <th className="px-4 py-2.5 text-left">Weapon</th>
                    <th className="px-4 py-2.5 text-left">Custodian Type</th>
                    <th className="px-4 py-2.5 text-left">Ammunition Rounds</th>
                    <th className="px-4 py-2.5 text-left">Start Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {dailyCustody.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-4 py-6 text-center text-gray-400">
                        No active custody records found.
                      </td>
                    </tr>
                  ) : (
                    dailyCustody.map((cust) => (
                      <tr key={cust.custody_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono font-medium text-gray-900">{cust.asset_id}</td>
                        <td className="px-4 py-2 text-gray-700">{cust.make_model}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            cust.custodian_type === 'GUARD'
                              ? 'bg-blue-50 text-blue-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}>
                            {cust.custodian_type}
                          </span>
                        </td>
                        <td className="px-4 py-2 font-mono font-semibold">{cust.ammunition_rounds}</td>
                        <td className="px-4 py-2 text-gray-500 font-mono">
                          {new Date(cust.start_time).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Maintenance Logs */}
          <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Weapon Maintenance & Inspection Logs</h3>
                <p className="text-xs text-gray-500">Scheduled servicing, repair logs & armourer certification</p>
              </div>
              {isAdmin && (
                <button
                  onClick={() => setShowAddMaintModal(true)}
                  className="flex items-center space-x-1 bg-slate-900 text-white px-3 py-1.5 rounded-md text-xs font-medium hover:bg-slate-800"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Log Maintenance</span>
                </button>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-xs">
                <thead className="bg-gray-50 text-gray-600 font-semibold">
                  <tr>
                    <th className="px-4 py-2.5 text-left">Record Date</th>
                    <th className="px-4 py-2.5 text-left">Type</th>
                    <th className="px-4 py-2.5 text-left">Certified By</th>
                    <th className="px-4 py-2.5 text-left">Outcome</th>
                    <th className="px-4 py-2.5 text-left">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {maintenanceLogs.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-4 py-6 text-center text-gray-400">
                        No maintenance entries recorded.
                      </td>
                    </tr>
                  ) : (
                    maintenanceLogs.map((log) => (
                      <tr key={log.log_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono text-gray-500">{log.record_date}</td>
                        <td className="px-4 py-2 font-medium text-gray-900">{log.maintenance_type}</td>
                        <td className="px-4 py-2 text-gray-600">{log.done_by}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded font-semibold ${
                            log.outcome === 'PASSED' || log.outcome === 'REPAIRED'
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-amber-50 text-amber-700'
                          }`}>
                            {log.outcome}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-gray-600">{log.notes || '-'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 7: URGENT MISSING REPORT (Screens 15, 28)                          */}
      {/* ========================================================================= */}
      {activeSubTab === 'urgent-report' && (
        <div className="max-w-2xl mx-auto bg-rose-50 border-2 border-rose-400 rounded-md p-6 space-y-4">
          <div className="flex items-center space-x-3 text-rose-800">
            <AlertOctagon className="w-8 h-8 flex-shrink-0" />
            <div>
              <h2 className="text-lg font-bold">URGENT: Missing or Stolen Weapon Report</h2>
              <p className="text-xs text-rose-700">
                Submitting this form changes the weapon status to MISSING or LOST_OR_STOLEN and raises a CRITICAL emergency alert to all Admins immediately.
              </p>
            </div>
          </div>

          <form onSubmit={handleReportMissing} className="space-y-4 bg-white p-5 border border-rose-200 rounded-md">
            <div>
              <label className="block text-xs font-semibold text-gray-800 mb-1">Select Weapon *</label>
              <select
                required
                value={missingForm.weapon_id}
                onChange={(e) => setMissingForm({ ...missingForm, weapon_id: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-rose-500"
              >
                <option value="">-- Choose Weapon --</option>
                {weapons.map((w) => (
                  <option key={w.weapon_id} value={w.weapon_id}>
                    {w.asset_id} - {w.make} {w.model} ({w.status})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="flex items-center space-x-2 text-xs font-semibold text-rose-900">
                <input
                  type="checkbox"
                  checked={missingForm.is_stolen}
                  onChange={(e) => setMissingForm({ ...missingForm, is_stolen: e.target.checked })}
                  className="rounded text-rose-600"
                />
                <span>Suspected Thefts / Stolen Weapon (Mark as LOST_OR_STOLEN)</span>
              </label>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-800 mb-1">Incident Circumstances & Description *</label>
              <textarea
                required
                rows="4"
                placeholder="State the exact time, location, suspect information, physical conditions, and last known custody..."
                value={missingForm.description}
                onChange={(e) => setMissingForm({ ...missingForm, description: e.target.value })}
                className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-rose-500"
              />
            </div>

            <button
              type="submit"
              className="w-full bg-rose-700 text-white py-2.5 rounded-md text-sm font-bold hover:bg-rose-800 transition"
            >
              Submit Urgent Report & Notify Authorities
            </button>
          </form>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 8: STATUTORY EXPORTS (Screen 16)                                   */}
      {/* ========================================================================= */}
      {activeSubTab === 'export' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white border border-gray-200 rounded-md p-5 space-y-3">
            <h3 className="font-semibold text-gray-900">Weapons Register CSV</h3>
            <p className="text-xs text-gray-500">
              Complete inventory with permanent Asset IDs, make, model, calibre, serial numbers, acquisition dates and current operational statuses.
            </p>
            <button
              onClick={() => handleExport('weapons')}
              className="w-full flex items-center justify-center space-x-2 bg-slate-900 text-white py-2 rounded-md text-sm font-medium hover:bg-slate-800"
            >
              <Download className="w-4 h-4" />
              <span>Export Weapons CSV</span>
            </button>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-5 space-y-3">
            <h3 className="font-semibold text-gray-900">Ammunition Ledger CSV</h3>
            <p className="text-xs text-gray-500">
              Immutable ammunition movements ledger with lot numbers, received, issued, returned, expended, and adjusted transactions.
            </p>
            <button
              onClick={() => handleExport('ammunition')}
              className="w-full flex items-center justify-center space-x-2 bg-slate-900 text-white py-2 rounded-md text-sm font-medium hover:bg-slate-800"
            >
              <Download className="w-4 h-4" />
              <span>Export Ammunition CSV</span>
            </button>
          </div>

          <div className="bg-white border border-gray-200 rounded-md p-5 space-y-3">
            <h3 className="font-semibold text-gray-900">Discrepancy Audit CSV</h3>
            <p className="text-xs text-gray-500">
              Audit log of all custody discrepancies, count mismatches, recount explanations, and resolutions.
            </p>
            <button
              onClick={() => handleExport('discrepancies')}
              className="w-full flex items-center justify-center space-x-2 bg-slate-900 text-white py-2 rounded-md text-sm font-medium hover:bg-slate-800"
            >
              <Download className="w-4 h-4" />
              <span>Export Discrepancies CSV</span>
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: REGISTER NEW WEAPON                                                */}
      {/* ========================================================================= */}
      {showAddWeaponModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-lg font-bold text-gray-900">Register New Weapon</h3>
              <button onClick={() => setShowAddWeaponModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateWeapon} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Weapon Type *</label>
                  <select
                    value={newWeapon.weapon_type}
                    onChange={(e) => setNewWeapon({ ...newWeapon, weapon_type: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none"
                  >
                    <option value="Pistol">Pistol</option>
                    <option value="Revolver">Revolver</option>
                    <option value="Shotgun">Shotgun</option>
                    <option value="Rifle">Rifle</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Calibre *</label>
                  <input
                    type="text"
                    required
                    value={newWeapon.calibre}
                    onChange={(e) => setNewWeapon({ ...newWeapon, calibre: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Make / Manufacturer *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. OFB / Ashani"
                    value={newWeapon.make}
                    onChange={(e) => setNewWeapon({ ...newWeapon, make: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Model *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. .32 Mk III"
                    value={newWeapon.model}
                    onChange={(e) => setNewWeapon({ ...newWeapon, model: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none"
                  />
                </div>
              </div>

              {/* Serial Number Double Entry Verification */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-md space-y-2">
                <div className="text-xs font-semibold text-slate-800">
                  Mandatory Double-Entry Serial Number Check (AC-12.2)
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Serial Number *</label>
                    <input
                      type="text"
                      required
                      value={newWeapon.serial_number}
                      onChange={(e) => setNewWeapon({ ...newWeapon, serial_number: e.target.value })}
                      className="w-full text-sm border border-gray-300 rounded p-1.5 outline-none font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Confirm Serial *</label>
                    <input
                      type="text"
                      required
                      value={newWeapon.serial_number_confirm}
                      onChange={(e) => setNewWeapon({ ...newWeapon, serial_number_confirm: e.target.value })}
                      className="w-full text-sm border border-gray-300 rounded p-1.5 outline-none font-mono"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Acquisition Date *</label>
                  <input
                    type="date"
                    required
                    value={newWeapon.acquisition_date}
                    onChange={(e) => setNewWeapon({ ...newWeapon, acquisition_date: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Link Licence</label>
                  <select
                    value={newWeapon.licence_id}
                    onChange={(e) => setNewWeapon({ ...newWeapon, licence_id: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none"
                  >
                    <option value="">-- Choose Licence --</option>
                    {licences.map((l) => (
                      <option key={l.licence_id} value={l.licence_id}>
                        {l.licence_number} ({l.holder_name})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="pt-2 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowAddWeaponModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800"
                >
                  Save Weapon Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: REVEAL SERIAL NUMBER                                              */}
      {/* ========================================================================= */}
      {showRevealModal && selectedWeaponForReveal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">Reveal Weapon Serial Number</h3>
              <button onClick={() => setShowRevealModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="text-xs text-gray-600">
              Weapon: <strong>{selectedWeaponForReveal.asset_id}</strong> ({selectedWeaponForReveal.make} {selectedWeaponForReveal.model})
            </div>

            {!revealedSerial ? (
              <form onSubmit={handleRevealSerial} className="space-y-3">
                <div className="p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                  Notice: Every reveal action is permanently logged with your user identity and timestamp in the immutable audit trail.
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Mandatory Operational Reason *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Police physical verification, custody transfer check..."
                    value={revealReason}
                    onChange={(e) => setRevealReason(e.target.value)}
                    className="w-full text-sm border border-gray-300 rounded-md p-2 outline-none focus:ring-1 focus:ring-slate-900"
                  />
                </div>

                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowRevealModal(false)}
                    className="px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
                  >
                    Confirm & Reveal
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-md text-center">
                  <div className="text-xs font-medium text-emerald-800">Unmasked Serial Number</div>
                  <div className="text-2xl font-mono font-bold text-emerald-950 mt-1">
                    {revealedSerial}
                  </div>
                </div>
                <button
                  onClick={() => setShowRevealModal(false)}
                  className="w-full bg-slate-900 text-white py-2 rounded-md text-sm font-medium hover:bg-slate-800"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: QR CODE LABEL PREVIEW                                              */}
      {/* ========================================================================= */}
      {showQRModal && selectedWeaponForQR && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-sm w-full p-6 text-center space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-2">
              <h3 className="text-base font-bold text-gray-900">Weapon QR Asset Label</h3>
              <button onClick={() => setShowQRModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* QR Simulation Box */}
            <div className="p-6 bg-gray-50 border-2 border-dashed border-gray-300 rounded-md flex flex-col items-center space-y-3">
              <QrCode className="w-32 h-32 text-slate-900" />
              <div className="font-mono text-base font-bold text-gray-900">
                {selectedWeaponForQR.asset_id}
              </div>
              <div className="text-[11px] text-gray-500">
                Label Version: v{selectedWeaponForQR.qr_relabel_count + 1}
              </div>
            </div>

            <p className="text-xs text-gray-500">
              Scannable QR identifier for guard mobile verification. Exactly one active label is valid per weapon.
            </p>

            <div className="flex justify-center space-x-2 pt-2">
              <button
                onClick={() => window.print()}
                className="px-3.5 py-1.5 border border-gray-300 rounded-md text-xs font-medium hover:bg-gray-50"
              >
                Print Label
              </button>
              <button
                onClick={() => setShowQRModal(false)}
                className="px-3.5 py-1.5 bg-slate-900 text-white rounded-md text-xs font-medium hover:bg-slate-800"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: ADD LICENCE                                                        */}
      {/* ========================================================================= */}
      {showAddLicenceModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">Add Arms Licence</h3>
              <button onClick={() => setShowAddLicenceModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateLicence} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Licence Number *</label>
                  <input
                    type="text"
                    required
                    value={newLicence.licence_number}
                    onChange={(e) => setNewLicence({ ...newLicence, licence_number: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Licence Type *</label>
                  <input
                    type="text"
                    required
                    value={newLicence.licence_type}
                    onChange={(e) => setNewLicence({ ...newLicence, licence_type: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Issuing Authority *</label>
                <input
                  type="text"
                  required
                  value={newLicence.issuing_authority}
                  onChange={(e) => setNewLicence({ ...newLicence, issuing_authority: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Holder Name *</label>
                  <input
                    type="text"
                    required
                    value={newLicence.holder_name}
                    onChange={(e) => setNewLicence({ ...newLicence, holder_name: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Holder Type *</label>
                  <select
                    value={newLicence.holder_type}
                    onChange={(e) => setNewLicence({ ...newLicence, holder_type: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  >
                    <option value="AGENCY">Agency</option>
                    <option value="INDIVIDUAL">Individual Guard</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Valid From *</label>
                  <input
                    type="date"
                    required
                    value={newLicence.valid_from}
                    onChange={(e) => setNewLicence({ ...newLicence, valid_from: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Valid Until (Expiry) *</label>
                  <input
                    type="date"
                    required
                    value={newLicence.valid_until}
                    onChange={(e) => setNewLicence({ ...newLicence, valid_until: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Max Weapons Limit</label>
                  <input
                    type="number"
                    value={newLicence.max_weapons_allowed}
                    onChange={(e) => setNewLicence({ ...newLicence, max_weapons_allowed: parseInt(e.target.value, 10) || 1 })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Max Ammunition Limit</label>
                  <input
                    type="number"
                    value={newLicence.max_ammunition_allowed}
                    onChange={(e) => setNewLicence({ ...newLicence, max_ammunition_allowed: parseInt(e.target.value, 10) || 1 })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddLicenceModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800"
                >
                  Save Licence
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: ADD AMMO LOT                                                       */}
      {/* ========================================================================= */}
      {showAddLotModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">Add Ammunition Lot</h3>
              <button onClick={() => setShowAddLotModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateAmmoLot} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Lot Number *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. LOT-OFB-2024-01"
                  value={newLot.lot_number}
                  onChange={(e) => setNewLot({ ...newLot, lot_number: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none font-mono"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Calibre / Type *</label>
                  <input
                    type="text"
                    required
                    value={newLot.ammunition_type}
                    onChange={(e) => setNewLot({ ...newLot, ammunition_type: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Manufacturer</label>
                  <input
                    type="text"
                    value={newLot.manufacturer}
                    onChange={(e) => setNewLot({ ...newLot, manufacturer: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Initial Quantity (Rounds) *</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={newLot.initial_quantity}
                  onChange={(e) => setNewLot({ ...newLot, initial_quantity: parseInt(e.target.value, 10) || 1 })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddLotModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800"
                >
                  Create Lot
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: PHYSICAL STOCK COUNT                                               */}
      {/* ========================================================================= */}
      {showStockCountModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">Record Physical Stock Count</h3>
              <button onClick={() => setShowStockCountModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleStockCount} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Select Lot *</label>
                <select
                  required
                  value={stockCountForm.lot_id}
                  onChange={(e) => setStockCountForm({ ...stockCountForm, lot_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                >
                  <option value="">-- Choose Lot --</option>
                  {ammoLots.map((l) => (
                    <option key={l.lot_id} value={l.lot_id}>
                      {l.lot_number} ({l.ammunition_type})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Counted Physical Quantity *</label>
                <input
                  type="number"
                  min="0"
                  required
                  value={stockCountForm.physical_quantity}
                  onChange={(e) => setStockCountForm({ ...stockCountForm, physical_quantity: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Reason / Notes (Mandatory if variance)</label>
                <input
                  type="text"
                  placeholder="Explain any physical variance from ledger..."
                  value={stockCountForm.reason}
                  onChange={(e) => setStockCountForm({ ...stockCountForm, reason: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowStockCountModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800"
                >
                  Submit Stock Count
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: RESOLVE DISCREPANCY                                                */}
      {/* ========================================================================= */}
      {showResolveDiscModal && selectedDisc && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">Resolve Custody Discrepancy</h3>
              <button onClick={() => setShowResolveDiscModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleResolveDiscrepancy} className="space-y-3">
              <div className="p-2.5 bg-gray-50 border border-gray-200 rounded text-xs space-y-1">
                <div>Type: <strong>{selectedDisc.discrepancy_type}</strong></div>
                <div>Issue: {selectedDisc.explanation}</div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Recount / Confirmed Value</label>
                <input
                  type="number"
                  placeholder="Recounted rounds or confirmation value"
                  value={resolveForm.recount_value}
                  onChange={(e) => setResolveForm({ ...resolveForm, recount_value: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Resolution Outcome *</label>
                <select
                  value={resolveForm.outcome}
                  onChange={(e) => setResolveForm({ ...resolveForm, outcome: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                >
                  <option value="EXPLAINED">Legitimate Variance Explained</option>
                  <option value="FOUND">Missing Items Located / Found</option>
                  <option value="DISCIPLINARY_ACTION">Disciplinary Action Taken</option>
                  <option value="WRITTEN_OFF">Approved Armoury Write-off</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Resolution Explanation *</label>
                <textarea
                  required
                  rows="3"
                  value={resolveForm.explanation}
                  onChange={(e) => setResolveForm({ ...resolveForm, explanation: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowResolveDiscModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-700 text-white rounded-md text-sm font-medium hover:bg-emerald-800"
                >
                  Mark Resolved
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL: ADD MAINTENANCE LOG                                                */}
      {/* ========================================================================= */}
      {showAddMaintModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 pb-3">
              <h3 className="text-base font-bold text-gray-900">Record Weapon Maintenance</h3>
              <button onClick={() => setShowAddMaintModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateMaint} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Select Weapon *</label>
                <select
                  required
                  value={maintForm.weapon_id}
                  onChange={(e) => setMaintForm({ ...maintForm, weapon_id: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                >
                  <option value="">-- Choose Weapon --</option>
                  {weapons.map((w) => (
                    <option key={w.weapon_id} value={w.weapon_id}>
                      {w.asset_id} - {w.make} {w.model} ({w.status})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Maintenance Type *</label>
                  <select
                    value={maintForm.maintenance_type}
                    onChange={(e) => setMaintForm({ ...maintForm, maintenance_type: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  >
                    <option value="INSPECTION">Inspection</option>
                    <option value="CLEANING">Cleaning & Oiling</option>
                    <option value="REPAIR">Armourer Repair</option>
                    <option value="CALIBRATION">Calibration</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Outcome *</label>
                  <select
                    value={maintForm.outcome}
                    onChange={(e) => setMaintForm({ ...maintForm, outcome: e.target.value })}
                    className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                  >
                    <option value="PASSED">Passed / Serviceable</option>
                    <option value="REPAIRED">Repaired & Certified</option>
                    <option value="PENDING_PARTS">Pending Parts</option>
                    <option value="FAILED">Failed / Unserviceable</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Armourer / Performed By *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Master Armourer J. Rao (Cert #402)"
                  value={maintForm.done_by}
                  onChange={(e) => setMaintForm({ ...maintForm, done_by: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Notes / Findings</label>
                <input
                  type="text"
                  value={maintForm.notes}
                  onChange={(e) => setMaintForm({ ...maintForm, notes: e.target.value })}
                  className="w-full text-sm border border-gray-300 rounded p-2 outline-none"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddMaintModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-slate-900 text-white rounded-md text-sm font-medium hover:bg-slate-800"
                >
                  Record Maintenance
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

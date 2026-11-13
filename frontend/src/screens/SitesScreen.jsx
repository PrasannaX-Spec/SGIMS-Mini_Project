import React, { useState, useEffect } from 'react';
import { MapPin, Plus, Search, Filter, ShieldCheck, Users, Clock, AlertCircle } from 'lucide-react';
import { masterApi, usersApi } from '../api';

export default function SitesScreen() {
  const [sites, setSites] = useState([]);
  const [clients, setClients] = useState([]);
  const [supervisors, setSupervisors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedSite, setSelectedSite] = useState(null);

  // Supervisor assignment modal
  const [showSupervisorModal, setShowSupervisorModal] = useState(false);
  const [supFormData, setSupFormData] = useState({
    supervisor_user_id: '',
    role_type: 'primary',
    assignment_reason: '',
  });

  // Geofence modal
  const [showGeofenceModal, setShowGeofenceModal] = useState(false);
  const [geoFormData, setGeoFormData] = useState({
    latitude: '',
    longitude: '',
    radius_meters: 100,
    reason_for_change: '',
  });

  // Create Site form state
  const [formData, setFormData] = useState({
    client_id: '',
    site_code: '',
    site_name: '',
    address_line1: '',
    city: 'Bengaluru',
    district: 'Bengaluru Urban',
    state_code: 'KA',
    postal_code: '',
    latitude: '',
    longitude: '',
    geofence_radius_m: 100,
    guard_instructions: '',
  });

  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchSites = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      const res = await masterApi.getSites(params);
      setSites(res.data);
    } catch (err) {
      console.error('Failed to load sites', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDependencies = async () => {
    try {
      const clientRes = await masterApi.getClients();
      setClients(clientRes.data);
      const userRes = await usersApi.getUsers({ role: 'SUPERVISOR' });
      setSupervisors(userRes.data?.results || userRes.data || []);
    } catch (err) {
      console.error('Failed to load clients/supervisors', err);
    }
  };

  useEffect(() => {
    fetchSites();
    fetchDependencies();
  }, [statusFilter]);

  const handleCreateSite = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await masterApi.createSite(formData);
      setShowCreateModal(false);
      setFormData({
        client_id: '',
        site_code: '',
        site_name: '',
        address_line1: '',
        city: 'Bengaluru',
        district: 'Bengaluru Urban',
        state_code: 'KA',
        postal_code: '',
        latitude: '',
        longitude: '',
        geofence_radius_m: 100,
        guard_instructions: '',
      });
      fetchSites();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to create site.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateGeofence = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await masterApi.updateGeofence(selectedSite.site_id, geoFormData);
      setShowGeofenceModal(false);
      const updated = await masterApi.getSite(selectedSite.site_id);
      setSelectedSite(updated.data);
      fetchSites();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to update geofence.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssignSupervisor = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await masterApi.assignSupervisor(selectedSite.site_id, supFormData);
      setShowSupervisorModal(false);
      const updated = await masterApi.getSite(selectedSite.site_id);
      setSelectedSite(updated.data);
      fetchSites();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to assign supervisor.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-md border border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-slate-700" />
            Security Sites & Geofences
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Operational client locations, circular geofence perimeters, supervisor assignments, and instructions
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 transition"
        >
          <Plus className="w-4 h-4" />
          Add Security Site
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex items-center justify-between bg-white p-4 rounded-md border border-gray-200">
        <div className="text-xs text-gray-600 font-medium">
          Showing {sites.length} operational site locations
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none"
          >
            <option value="">All Operational Statuses</option>
            <option value="active">Active</option>
            <option value="planned">Planned</option>
            <option value="suspended">Suspended</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Sites Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-3 bg-white p-8 rounded-md border border-gray-200 text-center text-xs text-gray-500">
            Loading security sites...
          </div>
        ) : sites.length === 0 ? (
          <div className="col-span-3 bg-white p-8 rounded-md border border-gray-200 text-center text-xs text-gray-500">
            No sites registered yet. Click &quot;Add Security Site&quot; to configure one.
          </div>
        ) : (
          sites.map((site) => (
            <div
              key={site.site_id}
              className="bg-white rounded-md border border-gray-200 p-5 flex flex-col justify-between hover:shadow-sm transition"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono text-[11px] font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                      {site.site_code}
                    </span>
                    <h3 className="font-bold text-sm text-gray-900 mt-1">{site.site_name}</h3>
                    <p className="text-xs text-gray-500">{site.client_name}</p>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                      site.operational_status === 'active'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}
                  >
                    {site.operational_status}
                  </span>
                </div>

                <div className="text-xs text-gray-600 space-y-1">
                  <div>
                    <span className="text-gray-400">City:</span> {site.city || 'Karnataka'}, {site.district || ''}
                  </div>
                  <div>
                    <span className="text-gray-400">Geofence:</span>{' '}
                    {site.latitude && site.longitude ? (
                      <span className="text-slate-800 font-medium">
                        Radius {site.geofence_radius_m || 100}m ({Number(site.latitude).toFixed(4)}, {Number(site.longitude).toFixed(4)})
                      </span>
                    ) : (
                      <span className="text-rose-600 font-medium">Not configured</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                <div className="text-gray-500 text-[11px]">
                  Supervisor: {site.primary_supervisor ? 'Assigned' : 'Unassigned'}
                </div>
                <button
                  onClick={() => setSelectedSite(site)}
                  className="px-3 py-1 bg-slate-900 text-white font-medium rounded-md hover:bg-slate-800 transition"
                >
                  Manage Site
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Manage Site Drawer / Modal */}
      {selectedSite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-2xl w-full border border-gray-200 max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <div>
                <h3 className="font-bold text-base">{selectedSite.site_name}</h3>
                <p className="text-xs text-gray-300 font-mono">Code: {selectedSite.site_code} &bull; {selectedSite.client_name}</p>
              </div>
              <button onClick={() => setSelectedSite(null)} className="text-gray-400 hover:text-white text-lg font-bold">
                &times;
              </button>
            </div>

            <div className="p-6 space-y-6 text-xs text-gray-700">
              {/* Geofence Card */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-gray-900 text-xs flex items-center gap-1.5">
                    <MapPin className="w-4 h-4 text-emerald-600" />
                    Circular Geofence Configuration
                  </h4>
                  <button
                    onClick={() => {
                      setGeoFormData({
                        latitude: selectedSite.latitude || '',
                        longitude: selectedSite.longitude || '',
                        radius_meters: selectedSite.geofence_radius_m || 100,
                        reason_for_change: '',
                      });
                      setShowGeofenceModal(true);
                    }}
                    className="px-2.5 py-1 bg-slate-900 text-white text-[11px] font-semibold rounded-md hover:bg-slate-800"
                  >
                    Update Geofence
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-2 text-gray-600">
                  <div>
                    <span className="text-gray-400 block text-[10px]">LATITUDE</span>
                    <span className="font-mono">{selectedSite.latitude || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block text-[10px]">LONGITUDE</span>
                    <span className="font-mono">{selectedSite.longitude || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block text-[10px]">RADIUS</span>
                    <span className="font-mono">{selectedSite.geofence_radius_m || 100} meters</span>
                  </div>
                </div>
              </div>

              {/* Supervisor Assignment Card */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-bold text-gray-900 text-xs flex items-center gap-1.5">
                    <Users className="w-4 h-4 text-slate-700" />
                    Supervisor Assignment
                  </h4>
                  <button
                    onClick={() => {
                      setSupFormData({
                        supervisor_user_id: '',
                        role_type: 'primary',
                        assignment_reason: '',
                      });
                      setShowSupervisorModal(true);
                    }}
                    className="px-2.5 py-1 bg-slate-900 text-white text-[11px] font-semibold rounded-md hover:bg-slate-800"
                  >
                    Assign Supervisor
                  </button>
                </div>

                <div className="text-gray-600">
                  {selectedSite.primary_supervisor ? (
                    <div>
                      <span className="text-emerald-700 font-semibold">Active Primary Supervisor Assigned</span>
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        Role: {selectedSite.primary_supervisor.role_type} &bull; Effective from: {new Date(selectedSite.primary_supervisor.effective_from).toLocaleDateString()}
                      </p>
                    </div>
                  ) : (
                    <div className="text-rose-600 font-medium">
                      No primary supervisor currently assigned to this site.
                    </div>
                  )}
                </div>
              </div>

              {/* Operational Instructions */}
              <div>
                <h4 className="font-bold text-gray-900 text-xs mb-1">Standard Guard Post Instructions</h4>
                <div className="p-3 bg-gray-50 border border-gray-200 rounded-md text-gray-600 whitespace-pre-wrap">
                  {selectedSite.guard_instructions || 'No special operational instructions defined for this site.'}
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setSelectedSite(null)}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Site Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-lg w-full border border-gray-200 max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Create New Security Site</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateSite} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">Client Organization *</label>
                <select
                  required
                  value={formData.client_id}
                  onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="">Select a Client</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>
                      {c.client_code} - {c.legal_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Site Code *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. BLR-EC-01"
                    value={formData.site_code}
                    onChange={(e) => setFormData({ ...formData, site_code: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md uppercase"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Site Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Tech Park Main Gate"
                    value={formData.site_name}
                    onChange={(e) => setFormData({ ...formData, site_name: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Address *</label>
                <input
                  type="text"
                  required
                  placeholder="Street / Sector"
                  value={formData.address_line1}
                  onChange={(e) => setFormData({ ...formData, address_line1: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">City</label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">District</label>
                  <input
                    type="text"
                    value={formData.district}
                    onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">PIN Code</label>
                  <input
                    type="text"
                    placeholder="560100"
                    value={formData.postal_code}
                    onChange={(e) => setFormData({ ...formData, postal_code: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-gray-100">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Latitude</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="12.9716"
                    value={formData.latitude}
                    onChange={(e) => setFormData({ ...formData, latitude: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Longitude</label>
                  <input
                    type="number"
                    step="any"
                    placeholder="77.5946"
                    value={formData.longitude}
                    onChange={(e) => setFormData({ ...formData, longitude: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Radius (meters)</label>
                  <input
                    type="number"
                    value={formData.geofence_radius_m}
                    onChange={(e) => setFormData({ ...formData, geofence_radius_m: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Guard Post Instructions</label>
                <textarea
                  rows={2}
                  placeholder="Specific duty instructions for guards stationed here..."
                  value={formData.guard_instructions}
                  onChange={(e) => setFormData({ ...formData, guard_instructions: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Creating...' : 'Create Site'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Geofence Update Modal */}
      {showGeofenceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Update Circular Geofence</h3>
              <button onClick={() => setShowGeofenceModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleUpdateGeofence} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Latitude *</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={geoFormData.latitude}
                    onChange={(e) => setGeoFormData({ ...geoFormData, latitude: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Longitude *</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={geoFormData.longitude}
                    onChange={(e) => setGeoFormData({ ...geoFormData, longitude: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Radius (meters) *</label>
                <input
                  type="number"
                  required
                  min={20}
                  max={2000}
                  value={geoFormData.radius_meters}
                  onChange={(e) => setGeoFormData({ ...geoFormData, radius_meters: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
                <span className="text-[11px] text-gray-400">Permitted range: 20m - 2000m</span>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Reason for Perimeter Modification *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="e.g. Relocated security gate, perimeter expansion..."
                  value={geoFormData.reason_for_change}
                  onChange={(e) => setGeoFormData({ ...geoFormData, reason_for_change: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowGeofenceModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Updating...' : 'Save New Version'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Supervisor Assignment Modal */}
      {showSupervisorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Assign Site Supervisor</h3>
              <button onClick={() => setShowSupervisorModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleAssignSupervisor} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">Select Supervisor *</label>
                <select
                  required
                  value={supFormData.supervisor_user_id}
                  onChange={(e) => setSupFormData({ ...supFormData, supervisor_user_id: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="">Select an active supervisor</option>
                  {supervisors.map((s) => (
                    <option key={s.user_id} value={s.user_id}>
                      {s.full_name} ({s.email})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Role Type</label>
                <select
                  value={supFormData.role_type}
                  onChange={(e) => setSupFormData({ ...supFormData, role_type: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                >
                  <option value="primary">Primary Supervisor</option>
                  <option value="backup">Backup Supervisor</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Mandatory Reason for Assignment *</label>
                <textarea
                  rows={2}
                  required
                  placeholder="e.g. Initial operational deployment, supervisor roster transfer..."
                  value={supFormData.assignment_reason}
                  onChange={(e) => setSupFormData({ ...supFormData, assignment_reason: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowSupervisorModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Assigning...' : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


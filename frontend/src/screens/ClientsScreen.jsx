import React, { useState, useEffect } from 'react';
import { Building2, Plus, Search, Filter, ShieldCheck, MapPin, Users, AlertCircle } from 'lucide-react';
import { masterApi } from '../api';

export default function ClientsScreen() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedClient, setSelectedClient] = useState(null);
  const [showContactModal, setShowContactModal] = useState(false);

  // Form states
  const [formData, setFormData] = useState({
    client_code: '',
    legal_name: '',
    display_name: '',
    pan: '',
    gstin: '',
    billing_email: '',
    billing_phone: '',
    notes: '',
  });
  const [contactData, setContactData] = useState({
    contact_name: '',
    phone: '',
    email: '',
    designation: '',
    contact_role: 'primary',
    is_primary: true,
  });
  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchClients = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (searchTerm) params.search = searchTerm;
      const res = await masterApi.getClients(params);
      setClients(res.data);
    } catch (err) {
      console.error('Failed to load clients', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, [statusFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchClients();
  };

  const handleCreateClient = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await masterApi.createClient(formData);
      setShowCreateModal(false);
      setFormData({
        client_code: '',
        legal_name: '',
        display_name: '',
        pan: '',
        gstin: '',
        billing_email: '',
        billing_phone: '',
        notes: '',
      });
      fetchClients();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to create client.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddContact = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    try {
      await masterApi.addClientContact(selectedClient.client_id, contactData);
      setShowContactModal(false);
      setContactData({
        contact_name: '',
        phone: '',
        email: '',
        designation: '',
        contact_role: 'primary',
        is_primary: true,
      });
      // Refresh client details
      const updated = await masterApi.getClient(selectedClient.client_id);
      setSelectedClient(updated.data);
      fetchClients();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to add contact.');
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
            <Building2 className="w-5 h-5 text-slate-700" />
            Client Directory
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Central repository of client organizations, authorized contacts, and linked site deployments
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 transition"
        >
          <Plus className="w-4 h-4" />
          Add Client
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 bg-white p-4 rounded-md border border-gray-200">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search clients by legal or trade name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-slate-900"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-slate-100 text-gray-700 text-xs font-medium rounded-md hover:bg-gray-200"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-slate-900"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="prospect">Prospect</option>
            <option value="suspended">Suspended</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Client List Table */}
      <div className="bg-white rounded-md border border-gray-200 overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider">
            <tr>
              <th className="p-3">Client Code</th>
              <th className="p-3">Legal Entity Name</th>
              <th className="p-3">Tax Identifiers</th>
              <th className="p-3">Sites</th>
              <th className="p-3">Status</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan="6" className="p-8 text-center text-gray-500">
                  Loading clients...
                </td>
              </tr>
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-8 text-center text-gray-500">
                  No clients registered yet.
                </td>
              </tr>
            ) : (
              clients.map((client) => (
                <tr key={client.client_id} className="hover:bg-gray-50/80 transition">
                  <td className="p-3 font-mono font-bold text-slate-800">{client.client_code}</td>
                  <td className="p-3">
                    <div className="font-semibold text-gray-900">{client.legal_name}</div>
                    {client.display_name && (
                      <div className="text-[11px] text-gray-500">{client.display_name}</div>
                    )}
                  </td>
                  <td className="p-3 text-[11px] text-gray-600">
                    <div>PAN: {client.pan || 'N/A'}</div>
                    <div>GSTIN: {client.gstin || 'N/A'}</div>
                  </td>
                  <td className="p-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                      <MapPin className="w-3 h-3" />
                      {client.sites_count || 0} sites
                    </span>
                  </td>
                  <td className="p-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold uppercase ${
                        client.status === 'active'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : client.status === 'prospect'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {client.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => setSelectedClient(client)}
                      className="px-3 py-1 bg-slate-100 text-slate-700 text-xs font-medium rounded-md hover:bg-slate-200"
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Client Detail Drawer / Modal */}
      {selectedClient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-2xl w-full border border-gray-200 max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b border-gray-200 flex items-center justify-between bg-slate-900 text-white">
              <div>
                <h3 className="font-bold text-base">{selectedClient.legal_name}</h3>
                <p className="text-xs text-gray-300 font-mono mt-0.5">Code: {selectedClient.client_code}</p>
              </div>
              <button
                onClick={() => setSelectedClient(null)}
                className="text-gray-400 hover:text-white text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-6 text-xs text-gray-700">
              {/* Primary Info */}
              <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-md border border-gray-200">
                <div>
                  <span className="text-gray-500 font-medium">PAN:</span> {selectedClient.pan || 'Not provided'}
                </div>
                <div>
                  <span className="text-gray-500 font-medium">GSTIN:</span> {selectedClient.gstin || 'Not provided'}
                </div>
                <div>
                  <span className="text-gray-500 font-medium">Billing Email:</span> {selectedClient.billing_email || 'N/A'}
                </div>
                <div>
                  <span className="text-gray-500 font-medium">Billing Phone:</span> {selectedClient.billing_phone || 'N/A'}
                </div>
                <div className="col-span-2">
                  <span className="text-gray-500 font-medium">Status:</span>{' '}
                  <span className="font-semibold uppercase">{selectedClient.status}</span>
                </div>
              </div>

              {/* Authorized Contacts */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-bold text-gray-900 text-sm flex items-center gap-1.5">
                    <Users className="w-4 h-4 text-slate-700" />
                    Authorized Contacts
                  </h4>
                  <button
                    onClick={() => setShowContactModal(true)}
                    className="px-2.5 py-1 bg-slate-100 text-slate-800 text-[11px] font-semibold rounded-md hover:bg-slate-200"
                  >
                    + Add Contact
                  </button>
                </div>

                {selectedClient.contacts && selectedClient.contacts.length > 0 ? (
                  <div className="space-y-2">
                    {selectedClient.contacts.map((contact) => (
                      <div
                        key={contact.contact_id}
                        className="p-3 bg-white border border-gray-200 rounded-md flex items-center justify-between"
                      >
                        <div>
                          <div className="font-semibold text-gray-900 flex items-center gap-2">
                            {contact.contact_name}
                            {contact.is_primary && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 font-bold uppercase">
                                Primary
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-gray-500">
                            {contact.designation || 'No designation'} &bull; Role: {contact.contact_role}
                          </div>
                        </div>
                        <div className="text-right text-[11px] text-gray-600">
                          <div>{contact.phone}</div>
                          <div>{contact.email || ''}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 bg-gray-50 border border-dashed border-gray-200 rounded-md text-center text-gray-500">
                    No contacts recorded for this client.
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setSelectedClient(null)}
                className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Client Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-lg w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Register New Client Organization</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateClient} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Client Code *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. CLI-INF-01"
                    value={formData.client_code}
                    onChange={(e) => setFormData({ ...formData, client_code: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md uppercase"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Legal Entity Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Infosys Ltd"
                    value={formData.legal_name}
                    onChange={(e) => setFormData({ ...formData, legal_name: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">PAN Number</label>
                  <input
                    type="text"
                    maxLength={10}
                    placeholder="e.g. AABCI1234D"
                    value={formData.pan}
                    onChange={(e) => setFormData({ ...formData, pan: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md uppercase"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">GSTIN</label>
                  <input
                    type="text"
                    maxLength={15}
                    placeholder="e.g. 29AABCI1234D1Z5"
                    value={formData.gstin}
                    onChange={(e) => setFormData({ ...formData, gstin: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md uppercase"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Billing Email</label>
                  <input
                    type="email"
                    placeholder="accounts@client.com"
                    value={formData.billing_email}
                    onChange={(e) => setFormData({ ...formData, billing_email: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Billing Phone</label>
                  <input
                    type="text"
                    placeholder="+91..."
                    value={formData.billing_phone}
                    onChange={(e) => setFormData({ ...formData, billing_phone: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
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
                  {submitting ? 'Registering...' : 'Register Client'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Contact Modal */}
      {showContactModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-md shadow-xl max-w-md w-full border border-gray-200">
            <div className="p-4 border-b border-gray-200 bg-slate-900 text-white flex justify-between items-center">
              <h3 className="font-bold text-sm">Add Authorized Contact</h3>
              <button onClick={() => setShowContactModal(false)} className="text-gray-400 hover:text-white">
                &times;
              </button>
            </div>

            <form onSubmit={handleAddContact} className="p-5 space-y-3 text-xs">
              {errorMsg && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
                  {errorMsg}
                </div>
              )}

              <div>
                <label className="block text-gray-700 font-medium mb-1">Contact Name *</label>
                <input
                  type="text"
                  required
                  placeholder="Full Name"
                  value={contactData.contact_name}
                  onChange={(e) => setContactData({ ...contactData, contact_name: e.target.value })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Phone Number *</label>
                  <input
                    type="text"
                    required
                    placeholder="+91..."
                    value={contactData.phone}
                    onChange={(e) => setContactData({ ...contactData, phone: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Email</label>
                  <input
                    type="email"
                    placeholder="contact@client.com"
                    value={contactData.email}
                    onChange={(e) => setContactData({ ...contactData, email: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Role Type</label>
                  <select
                    value={contactData.contact_role}
                    onChange={(e) => setContactData({ ...contactData, contact_role: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  >
                    <option value="primary">Primary</option>
                    <option value="billing">Billing</option>
                    <option value="site_contact">Site Contact</option>
                    <option value="escalation">Escalation</option>
                    <option value="general">General</option>
                  </select>
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Designation</label>
                  <input
                    type="text"
                    placeholder="e.g. Facility Manager"
                    value={contactData.designation}
                    onChange={(e) => setContactData({ ...contactData, designation: e.target.value })}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="primaryContactCheck"
                  checked={contactData.is_primary}
                  onChange={(e) => setContactData({ ...contactData, is_primary: e.target.checked })}
                />
                <label htmlFor="primaryContactCheck" className="text-gray-700">
                  Set as primary organization contact
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowContactModal(false)}
                  className="px-3 py-1.5 border border-gray-300 rounded-md text-gray-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-slate-900 text-white rounded-md font-semibold hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : 'Save Contact'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


import React, { useState, useEffect } from 'react';
import { Search, UserPlus, AlertCircle, RefreshCw, ChevronRight, AlertTriangle } from 'lucide-react';
import { usersApi } from '../api';
import CreateUserModal from './CreateUserModal';

export default function UserListScreen({ onSelectUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [totalCount, setTotalCount] = useState(0);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params = {};
      if (search.trim()) params.search = search.trim();
      if (roleFilter) params.role = roleFilter;
      if (statusFilter) params.status = statusFilter;

      const res = await usersApi.getUsers(params);
      const results = res.data.results || res.data;
      setUsers(results);
      setTotalCount(res.data.count || results.length);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [roleFilter, statusFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchUsers();
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">User Management</h2>
          <p className="text-xs text-gray-500">Manage user accounts, roles, access scope and status</p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="inline-flex items-center px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-md hover:bg-slate-800 shadow-sm transition"
        >
          <UserPlus className="w-4 h-4 mr-1.5" />
          <span>Create User</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-md border border-gray-200 shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
        <form onSubmit={handleSearchSubmit} className="relative w-full md:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, or phone..."
            className="w-full pl-9 pr-3 py-1.5 text-xs border border-gray-300 rounded-md focus:ring-1 focus:ring-slate-900"
          />
          <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-2" />
        </form>

        <div className="flex items-center space-x-2 w-full md:w-auto">
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md p-1.5 bg-white text-gray-700"
          >
            <option value="">All Roles</option>
            <option value="ADMIN">Admin</option>
            <option value="SUPERVISOR">Supervisor</option>
            <option value="GUARD">Guard</option>
            <option value="CLIENT">Client</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-gray-300 rounded-md p-1.5 bg-white text-gray-700"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </select>

          <button
            onClick={fetchUsers}
            className="p-1.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-md transition"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-md border border-gray-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-gray-500">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center text-xs text-gray-500">
            No users match these filters.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Full Name</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Login ID</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last Login (IST)</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              {users.map((u) => (
                <tr
                  key={u.user_id}
                  onClick={() => onSelectUser(u.user_id)}
                  className="hover:bg-slate-50 cursor-pointer transition"
                >
                  <td className="px-4 py-3 font-semibold text-gray-900 flex items-center space-x-2">
                    <span>{u.full_name}</span>
                    {u.has_warning && (
                      <span title="Account missing linked profile or company" className="text-amber-500">
                        <AlertTriangle className="w-3.5 h-3.5 inline" />
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px]">
                    <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-semibold">
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-600">
                    {u.email || u.phone}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                        u.status === 'ACTIVE'
                          ? 'bg-green-50 text-green-700 border border-green-200'
                          : 'bg-gray-100 text-gray-600 border border-gray-200'
                      }`}
                    >
                      {u.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {u.last_login_ist || 'Never'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ChevronRight className="w-4 h-4 text-gray-400 inline" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="p-3 bg-gray-50 border-t border-gray-100 text-xs text-gray-500 flex justify-between items-center">
          <span>Total Users: <strong>{totalCount}</strong></span>
          <span>Showing 25 rows per page</span>
        </div>
      </div>

      <CreateUserModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onUserCreated={fetchUsers}
      />
    </div>
  );
}


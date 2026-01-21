'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { companiesAPI, agentsAPI, Company, Agent } from '@/lib/api';

export default function CompaniesPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeploymentModal, setShowDeploymentModal] = useState(false);
  const [deployingCompanyId, setDeployingCompanyId] = useState<string | null>(null);
  const [deploymentLogs, setDeploymentLogs] = useState<string[]>([]);
  const [deploymentStatus, setDeploymentStatus] = useState<string>('deploying');
  const [deletingCompanyId, setDeletingCompanyId] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [formData, setFormData] = useState({
    name: '',
    admin_email: '',
    admin_password: '',
    employee_email: '',
    employee_password: '',
  });
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [createdCredentials, setCreatedCredentials] = useState<{
    employee?: { email: string; password: string; role: string };
    admin?: { email: string; role: string };
  } | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }
    loadCompanies();
  }, [router]);

  const loadCompanies = async () => {
    try {
      const data = await companiesAPI.list();
      setCompanies(data);
    } catch (error) {
      console.error('Failed to load companies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Prepare data - only include employee fields if provided
      const createData: any = {
        name: formData.name,
        admin_email: formData.admin_email,
        admin_password: formData.admin_password,
      };
      
      if (formData.employee_email) {
        createData.employee_email = formData.employee_email;
      }
      if (formData.employee_password) {
        createData.employee_password = formData.employee_password;
      }
      
      const newCompany = await companiesAPI.create(createData);
      
      // Store credentials to show in modal
      if (newCompany.employee_credentials || newCompany.admin_credentials) {
        setCreatedCredentials({
          employee: newCompany.employee_credentials,
          admin: newCompany.admin_credentials,
        });
        setShowCredentialsModal(true);
      }
      
      setShowCreateModal(false);
      setFormData({ name: '', admin_email: '', admin_password: '', employee_email: '', employee_password: '' });
      
      // Start deployment monitoring
      setDeployingCompanyId(newCompany.company_id);
      setDeploymentLogs([]);
      setDeploymentStatus('deploying');
      setShowDeploymentModal(true);
      
      // Start polling for deployment logs
      startDeploymentPolling(newCompany.company_id);
      
      // Reload companies list
      loadCompanies();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to create company');
    }
  };

  const startDeploymentPolling = (companyId: string) => {
    // Clear any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    // Poll every 2 seconds for deployment logs
    pollingIntervalRef.current = setInterval(async () => {
      try {
        // Get agent deployment status and logs
        const agent = await agentsAPI.getByCompany(companyId);
        
        if (agent) {
          // Update logs
          if (agent.deployment_logs && agent.deployment_logs.length > 0) {
            setDeploymentLogs(agent.deployment_logs);
          }
          
          // Update status
          setDeploymentStatus(agent.deployment_status);
          
          // If deployment is complete (active or failed), stop polling
          if (agent.deployment_status === 'active' || agent.deployment_status === 'failed') {
            stopDeploymentPolling();
            
            // Reload companies to show updated status
            loadCompanies();
            
            // Auto-close modal after 3 seconds if successful
            if (agent.deployment_status === 'active') {
              setTimeout(() => {
                setShowDeploymentModal(false);
                setDeployingCompanyId(null);
                router.push(`/companies/${companyId}`);
              }, 3000);
            }
          }
        }
      } catch (error: any) {
        // Agent might not exist yet (404), continue polling
        // Show a waiting message if we don't have any logs yet
        if (error.response?.status === 404 && deploymentLogs.length === 0) {
          setDeploymentLogs([`[${new Date().toISOString()}] Waiting for agent deployment to start...`]);
        }
        // Continue polling - agent will be created soon
      }
    }, 2000);
  };

  const stopDeploymentPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      stopDeploymentPolling();
    };
  }, []);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [deploymentLogs]);

  const handleDelete = async (companyId: string, companyName: string) => {
    if (!confirm(`Are you sure you want to delete "${companyName}"? This will permanently delete:\n\n- The company and all its data\n- All associated users\n- The agent and its deployment\n- All knowledge base data\n- All audit logs\n\nThis action cannot be undone.`)) {
      return;
    }
    
    setDeletingCompanyId(companyId);
    try {
      await companiesAPI.delete(companyId);
      loadCompanies();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to delete company');
    } finally {
      setDeletingCompanyId(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('company_id');
    localStorage.removeItem('role');
    router.push('/login');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold">Admin Panel</h1>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={handleLogout}
                className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Companies</h2>
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              Create Company
            </button>
          </div>

          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {companies.map((company) => (
                <li key={company.company_id} className="hover:bg-gray-50">
                  <div className="flex items-center justify-between px-4 py-4 sm:px-6">
                    <Link
                      href={`/companies/${company.company_id}`}
                      className="flex-1 block"
                    >
                      <div>
                        <p className="text-sm font-medium text-blue-600 truncate">
                          {company.name}
                        </p>
                        <p className="mt-2 flex items-center text-sm text-gray-500">
                          Status: {company.status} | Agent: {company.agent_status || 'N/A'}
                        </p>
                      </div>
                    </Link>
                    <div className="ml-5 flex items-center space-x-2 flex-shrink-0">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleDelete(company.company_id, company.name);
                        }}
                        disabled={deletingCompanyId === company.company_id}
                        className="text-red-600 hover:text-red-800 disabled:opacity-50 disabled:cursor-not-allowed p-2 rounded-md hover:bg-red-50 transition-colors"
                        title="Delete company"
                      >
                        {deletingCompanyId === company.company_id ? (
                          <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        ) : (
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        )}
                      </button>
                      <Link
                        href={`/companies/${company.company_id}`}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <svg
                          className="h-5 w-5"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </Link>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </main>

      {showCreateModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold mb-4">Create New Company</h3>
            <form onSubmit={handleCreate}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Admin Email
                </label>
                <input
                  type="email"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  value={formData.admin_email}
                  onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Admin Password
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  value={formData.admin_password}
                  onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                />
              </div>
              
              <div className="mb-4 border-t pt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Employee Account (Optional)</h4>
                <p className="text-xs text-gray-500 mb-3">
                  Leave empty to auto-generate employee credentials
                </p>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Employee Email (optional)
                  </label>
                  <input
                    type="email"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="employee@company.com"
                    value={formData.employee_email}
                    onChange={(e) => setFormData({ ...formData, employee_email: e.target.value })}
                  />
                </div>
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Employee Password (optional, min 8 chars)
                  </label>
                  <input
                    type="password"
                    minLength={8}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    placeholder="Leave empty for default"
                    value={formData.employee_password}
                    onChange={(e) => setFormData({ ...formData, employee_password: e.target.value })}
                  />
                </div>
              </div>
              
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showDeploymentModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-10 mx-auto p-5 border w-4/5 max-w-4xl shadow-lg rounded-md bg-white">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">
                Agent Deployment Progress
                {deploymentStatus === 'deploying' && (
                  <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    <svg className="animate-spin -ml-1 mr-2 h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Deploying...
                  </span>
                )}
                {deploymentStatus === 'active' && (
                  <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    ✓ Active
                  </span>
                )}
                {deploymentStatus === 'failed' && (
                  <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                    ✗ Failed
                  </span>
                )}
              </h3>
              <button
                onClick={() => {
                  stopDeploymentPolling();
                  setShowDeploymentModal(false);
                  setDeployingCompanyId(null);
                  if (deployingCompanyId) {
                    router.push(`/companies/${deployingCompanyId}`);
                  }
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="bg-gray-900 text-green-400 font-mono text-sm p-4 rounded-md h-96 overflow-y-auto">
              {deploymentLogs.length === 0 ? (
                <div className="text-gray-500">Waiting for deployment logs...</div>
              ) : (
                deploymentLogs.map((log, index) => {
                  const isError = log.toLowerCase().includes('error') || log.toLowerCase().includes('failed');
                  const isSuccess = log.toLowerCase().includes('success') || log.toLowerCase().includes('completed');
                  return (
                    <div
                      key={index}
                      className={`${
                        isError ? 'text-red-400' : isSuccess ? 'text-green-300' : 'text-gray-300'
                      } mb-1`}
                    >
                      {log}
                    </div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>
            
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => {
                  stopDeploymentPolling();
                  setShowDeploymentModal(false);
                  setDeployingCompanyId(null);
                  if (deployingCompanyId) {
                    router.push(`/companies/${deployingCompanyId}`);
                  }
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {deploymentStatus === 'deploying' ? 'View Details' : 'Close'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showCredentialsModal && createdCredentials && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-bold mb-4">Company Created Successfully!</h3>
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-4">
                Save these credentials. They won't be shown again.
              </p>
              
              {createdCredentials.employee && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <h4 className="text-sm font-semibold text-blue-900 mb-2">Employee Credentials</h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="font-medium text-gray-700">Email:</span>
                      <div className="mt-1 p-2 bg-white border border-blue-200 rounded font-mono text-xs break-all">
                        {createdCredentials.employee.email}
                      </div>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Password:</span>
                      <div className="mt-1 p-2 bg-white border border-blue-200 rounded font-mono text-xs break-all">
                        {createdCredentials.employee.password}
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-gray-600">
                      Role: {createdCredentials.employee.role}
                    </div>
                  </div>
                </div>
              )}
              
              {createdCredentials.admin && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md">
                  <h4 className="text-sm font-semibold text-green-900 mb-2">Admin Credentials</h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="font-medium text-gray-700">Email:</span>
                      <div className="mt-1 p-2 bg-white border border-green-200 rounded font-mono text-xs break-all">
                        {createdCredentials.admin.email}
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-gray-600">
                      Role: {createdCredentials.admin.role}
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => {
                  setShowCredentialsModal(false);
                  setCreatedCredentials(null);
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

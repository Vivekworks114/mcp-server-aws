'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { companiesAPI, usersAPI, agentsAPI, knowledgeBaseAPI, auditLogsAPI, vectorDBAPI, Company, User, Agent, AuditLog, VectorDBStats, KnowledgeBaseEntry } from '@/lib/api';

export default function CompanyDetailPage() {
  const router = useRouter();
  const params = useParams();
  const companyId = params.id as string;
  
  const [company, setCompany] = useState<Company | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [kbStats, setKbStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'knowledge-base' | 'audit-logs' | 'logs'>('overview');
  const [redeploying, setRedeploying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [vectorDBStats, setVectorDBStats] = useState<VectorDBStats | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }
    loadData();
    
    // Start polling for deployment logs if deployment is in progress
    const startPolling = () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      
      // Poll every 2 seconds if deployment is in progress
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const agentData = await agentsAPI.getByCompany(companyId);
          if (agentData) {
            setAgent(agentData);
            
            // Stop polling if deployment is complete
            if (agentData.deployment_status === 'active' || agentData.deployment_status === 'failed') {
              if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
              }
              // Reload all data to get final state
              loadData();
            }
          }
        } catch (error: any) {
          // Agent might not exist yet (404), continue polling
          // This is normal right after company creation
          if (error.response?.status !== 404) {
            console.error('Error polling agent status:', error);
          }
        }
      }, 2000);
    };
    
    // Check if we need to start polling
    const checkAndStartPolling = async () => {
      try {
        const agentData = await agentsAPI.getByCompany(companyId).catch(() => null);
        if (agentData && (agentData.deployment_status === 'deploying' || agentData.deployment_status === 'pending')) {
          startPolling();
        }
      } catch (error) {
        // Ignore errors
      }
    };
    
    // Start polling after initial load
    setTimeout(checkAndStartPolling, 1000);
    
    // Cleanup on unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [companyId, router]);
  
  // Auto-scroll logs to bottom when logs tab is active
  useEffect(() => {
    if (activeTab === 'logs' && logsEndRef.current && agent?.deployment_logs) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeTab, agent?.deployment_logs]);

  const loadData = async () => {
    try {
      const [companyData, usersData, agentData, kbData, logsData, vectorStats] = await Promise.all([
        companiesAPI.get(companyId),
        usersAPI.listByCompany(companyId),
        agentsAPI.getByCompany(companyId).catch(() => null),
        knowledgeBaseAPI.getStats(companyId).catch(() => null),
        auditLogsAPI.getByCompany(companyId).catch(() => []),
        vectorDBAPI.getStats(companyId).catch(() => null),
      ]);
      setCompany(companyData);
      setUsers(usersData);
      setAgent(agentData);
      setKbStats(kbData);
      setAuditLogs(logsData);
      setVectorDBStats(vectorStats);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRedeploy = async () => {
    if (!confirm('Are you sure you want to redeploy this agent? This will restart the deployment process.')) {
      return;
    }
    
    setRedeploying(true);
    try {
      await agentsAPI.redeploy(companyId);
      // Switch to logs tab to show deployment progress
      setActiveTab('logs');
      // Start polling for deployment logs
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const agentData = await agentsAPI.getByCompany(companyId);
          if (agentData) {
            setAgent(agentData);
            if (agentData.deployment_status === 'active' || agentData.deployment_status === 'failed') {
              if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
              }
              loadData();
            }
          }
        } catch (error) {
          // Continue polling
        }
      }, 2000);
      // Reload data to get updated status
      await loadData();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to redeploy agent');
    } finally {
      setRedeploying(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this agent? This action cannot be undone.')) {
      return;
    }
    
    setDeleting(true);
    try {
      await agentsAPI.delete(companyId);
      alert('Agent deleted successfully!');
      // Reload data to reflect deletion
      setAgent(null);
      await loadData();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to delete agent');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!company) {
    return <div>Company not found</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-4">
              <Link href="/companies" className="text-blue-600 hover:text-blue-800">
                ← Back to Companies
              </Link>
              <h1 className="text-xl font-bold">{company.name}</h1>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('overview')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'overview'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('users')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'users'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Users ({users.length})
              </button>
              <button
                onClick={() => setActiveTab('knowledge-base')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'knowledge-base'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Knowledge Base
              </button>
              <button
                onClick={() => setActiveTab('audit-logs')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'audit-logs'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Audit Logs ({auditLogs.length})
              </button>
              <button
                onClick={() => setActiveTab('logs')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'logs'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Deployment Logs
              </button>
            </nav>
          </div>

          <div className="mt-6">
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div className="bg-white shadow rounded-lg p-6">
                  <h2 className="text-lg font-medium mb-4">Company Information</h2>
                  <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Company ID</dt>
                      <dd className="mt-1 text-sm text-gray-900">{company.company_id}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Status</dt>
                      <dd className="mt-1 text-sm text-gray-900">{company.status}</dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Agent Status</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {/* Prioritize company status if it's failed (more reliable), otherwise use agent status */}
                        {(() => {
                          const status = company?.agent_status === 'failed' ? 'failed' : 
                                        (agent?.deployment_status || company?.agent_status || 'N/A');
                          const error = agent?.deployment_error || null;
                          return (
                            <>
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                status === 'active' ? 'bg-green-100 text-green-800' :
                                status === 'failed' ? 'bg-red-100 text-red-800' :
                                status === 'deploying' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-gray-100 text-gray-800'
                              }`}>
                                {status}
                              </span>
                              {status === 'failed' && error && (
                                <div className="mt-2 text-xs text-red-600">
                                  Error: {error}
                                </div>
                              )}
                            </>
                          );
                        })()}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Vector DB Namespace</dt>
                      <dd className="mt-1 text-xs text-gray-900 font-mono">{company.vector_db_namespace || 'N/A'}</dd>
                    </div>
                    {vectorDBStats && (
                      <>
                        <div>
                          <dt className="text-sm font-medium text-gray-500">Vector DB Index</dt>
                          <dd className="mt-1 text-sm text-gray-900">{vectorDBStats.index_name || 'N/A'}</dd>
                        </div>
                        <div>
                          <dt className="text-sm font-medium text-gray-500">Total Vectors</dt>
                          <dd className="mt-1 text-sm text-gray-900 font-semibold">{vectorDBStats.total_entries.toLocaleString()}</dd>
                        </div>
                        {vectorDBStats.last_updated && (
                          <div>
                            <dt className="text-sm font-medium text-gray-500">Last Updated</dt>
                            <dd className="mt-1 text-sm text-gray-900">
                              {new Date(vectorDBStats.last_updated).toLocaleString()}
                            </dd>
                          </div>
                        )}
                      </>
                    )}
                    {agent?.deployment_id && (
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Deployment ID</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{agent.deployment_id}</dd>
                      </div>
                    )}
                    {agent?.agent_arn && (
                      <div className="sm:col-span-2">
                        <dt className="text-sm font-medium text-gray-500">Agent ARN</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{agent.agent_arn}</dd>
                      </div>
                    )}
                    {agent?.agent_endpoint && (
                      <div className="sm:col-span-2">
                        <dt className="text-sm font-medium text-gray-500">Agent Endpoint</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{agent.agent_endpoint}</dd>
                      </div>
                    )}
                    {agent?.ecr_uri && (
                      <div className="sm:col-span-2">
                        <dt className="text-sm font-medium text-gray-500">ECR URI</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{agent.ecr_uri}</dd>
                      </div>
                    )}
                    {agent?.codebuild_id && (
                      <div>
                        <dt className="text-sm font-medium text-gray-500">CodeBuild ID</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{agent.codebuild_id}</dd>
                      </div>
                    )}
                    {agent?.deployment_error && (
                      <div className="sm:col-span-2">
                        <dt className="text-sm font-medium text-red-600">Deployment Error</dt>
                        <dd className="mt-1 text-sm text-red-800 bg-red-50 p-3 rounded">{agent.deployment_error}</dd>
                      </div>
                    )}
                  </dl>
                </div>

                {agent && (
                  <div className="space-y-6">
                    <div className="bg-white shadow rounded-lg p-6">
                      <div className="flex justify-between items-center mb-4">
                        <h2 className="text-lg font-medium">Agent Management</h2>
                        <button
                          onClick={() => loadData()}
                          disabled={loading}
                          className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                        >
                          {loading ? (
                            <>
                              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Refreshing...
                            </>
                          ) : (
                            <>
                              <svg className="-ml-1 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                              Refresh Status
                            </>
                          )}
                        </button>
                      </div>
                      <div className="flex space-x-4">
                        {(() => {
                          // Use company status if failed (more reliable), otherwise use agent status
                          const effectiveStatus = company?.agent_status === 'failed' ? 'failed' : 
                                                (agent?.deployment_status || company?.agent_status);
                          const isDeploying = effectiveStatus === 'deploying' && company?.agent_status !== 'failed';
                          
                          return (
                            <>
                              <button
                                onClick={handleRedeploy}
                                disabled={redeploying || isDeploying}
                                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {redeploying ? 'Redeploying...' : 'Redeploy Agent'}
                              </button>
                              <button
                                onClick={handleDelete}
                                disabled={deleting || isDeploying}
                                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {deleting ? 'Deleting...' : 'Delete Agent'}
                              </button>
                            </>
                          );
                        })()}
                      </div>
                      <p className="mt-2 text-sm text-gray-500">
                        {(() => {
                          // Use company status if failed (more reliable), otherwise use agent status
                          const effectiveStatus = company?.agent_status === 'failed' ? 'failed' : 
                                                (agent?.deployment_status || company?.agent_status);
                          
                          if (effectiveStatus === 'failed') {
                            return 'Agent deployment failed. You can redeploy or delete it.';
                          } else if (effectiveStatus === 'deploying') {
                            return (
                              <span className="flex items-center">
                                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-yellow-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                Agent is currently being deployed. Click "Refresh Status" to check the latest status.
                              </span>
                            );
                          } else if (effectiveStatus === 'active') {
                            return 'Agent is active. You can redeploy to update it or delete it.';
                          }
                          return null;
                        })()}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'logs' && (
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-medium">Deployment Logs</h2>
                  {agent && (agent.deployment_status === 'deploying' || agent.deployment_status === 'pending') && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      <svg className="animate-spin -ml-1 mr-2 h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Live updating...
                    </span>
                  )}
                </div>
                {agent && agent.deployment_logs && agent.deployment_logs.length > 0 ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <p className="text-sm text-gray-500">
                        Total log entries: {agent.deployment_logs.length}
                      </p>
                      <button
                        onClick={() => loadData()}
                        disabled={loading}
                        className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                      >
                        {loading ? (
                          <>
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Refreshing...
                          </>
                        ) : (
                          <>
                            <svg className="-ml-1 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Refresh Logs
                          </>
                        )}
                      </button>
                    </div>
                    <div className="bg-gray-900 text-green-400 font-mono text-xs p-4 rounded-lg overflow-x-auto max-h-[600px] overflow-y-auto">
                      {agent.deployment_logs.map((log: string, index: number) => (
                        <div key={index} className="mb-1 whitespace-pre-wrap break-words">
                          {log.includes('ERROR') || log.includes('error') || log.includes('Error') || log.includes('Failed') ? (
                            <span className="text-red-400">{log}</span>
                          ) : log.includes('SUCCESS') || log.includes('success') || log.includes('Success') || log.includes('completed') ? (
                            <span className="text-green-300">{log}</span>
                          ) : (
                            <span>{log}</span>
                          )}
                        </div>
                      ))}
                      <div ref={logsEndRef} />
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <p className="text-gray-500">No deployment logs available</p>
                    {!agent && (
                      <p className="text-sm text-gray-400 mt-2">Agent has not been deployed yet</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'users' && (
              <div className="bg-white shadow rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Email
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Role
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {users.map((user) => (
                      <tr key={user.user_id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {user.email}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.role}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {new Date(user.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === 'knowledge-base' && (
              <KnowledgeBaseTab companyId={companyId} stats={kbStats} />
            )}

            {activeTab === 'audit-logs' && (
              <div className="bg-white shadow rounded-lg overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-medium">Audit Logs</h2>
                  <p className="mt-1 text-sm text-gray-500">
                    View all actions and events for this company
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Timestamp
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Action
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          User ID
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Details
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {auditLogs.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-6 py-4 text-center text-sm text-gray-500">
                            No audit logs found
                          </td>
                        </tr>
                      ) : (
                        auditLogs.map((log) => (
                          <tr key={log.log_id} className={log.action.includes('failed') || log.action.includes('error') ? 'bg-red-50' : ''}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {new Date(log.timestamp).toLocaleString()}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                log.action.includes('failed') || log.action.includes('error') 
                                  ? 'bg-red-100 text-red-800'
                                  : log.action.includes('deployed') || log.action.includes('created')
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-blue-100 text-blue-800'
                              }`}>
                                {log.action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-500 font-mono">
                              {log.user_id.substring(0, 8)}...
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900">
                              <details className="cursor-pointer">
                                <summary className="text-blue-600 hover:text-blue-800">
                                  View Details
                                </summary>
                                <pre className="mt-2 p-3 bg-gray-50 rounded text-xs overflow-x-auto">
                                  {JSON.stringify(log.details, null, 2)}
                                </pre>
                              </details>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function KnowledgeBaseTab({ companyId, stats }: { companyId: string; stats: any }) {
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Array<{ question: string; answer: string }>>([]);
  const [entries, setEntries] = useState<Array<{ id: string; question: string; answer: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [activeView, setActiveView] = useState<'list' | 'upload'>('list');

  const loadEntries = async () => {
    setLoading(true);
    try {
      const data = await knowledgeBaseAPI.listEntries(companyId);
      setEntries(data);
    } catch (error: any) {
      console.error('Failed to load entries:', error);
      alert(error.response?.data?.detail || 'Failed to load knowledge base entries');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeView === 'list') {
      loadEntries();
    }
  }, [companyId, activeView]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const text = event.target?.result as string;
          const lines = text.split('\n').filter(line => line.trim());
          const data = lines.map(line => {
            const [question, ...answerParts] = line.split(',');
            return {
              question: question?.trim() || '',
              answer: answerParts.join(',').trim() || '',
            };
          }).filter(item => item.question && item.answer);
          setPreview(data.slice(0, 5));
        } catch (error) {
          alert('Failed to parse file');
        }
      };
      reader.readAsText(selectedFile);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const text = await file.text();
      const lines = text.split('\n').filter(line => line.trim());
      const data = lines.map(line => {
        const [question, ...answerParts] = line.split(',');
        return {
          question: question?.trim() || '',
          answer: answerParts.join(',').trim() || '',
        };
      }).filter(item => item.question && item.answer);
      
      await knowledgeBaseAPI.upload(companyId, data);
      alert('Knowledge base uploaded successfully!');
      setFile(null);
      setPreview([]);
      // Refresh entries and stats
      if (activeView === 'list') {
        loadEntries();
      }
      window.location.reload(); // Refresh to update stats
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(entries.map(e => e.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectEntry = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) {
      alert('Please select entries to delete');
      return;
    }
    
    if (!confirm(`Are you sure you want to delete ${selectedIds.size} selected entry(ies)?`)) {
      return;
    }
    
    setDeleting(true);
    try {
      await knowledgeBaseAPI.deleteEntries(companyId, Array.from(selectedIds));
      alert('Selected entries deleted successfully!');
      setSelectedIds(new Set());
      loadEntries();
      window.location.reload(); // Refresh to update stats
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to delete entries');
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm('Are you sure you want to delete ALL knowledge base entries? This action cannot be undone.')) {
      return;
    }
    
    setDeleting(true);
    try {
      await knowledgeBaseAPI.deleteEntries(companyId);
      alert('All entries deleted successfully!');
      setSelectedIds(new Set());
      loadEntries();
      window.location.reload(); // Refresh to update stats
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to delete all entries');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Stats and View Toggle */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-medium">Knowledge Base Management</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveView('list')}
              className={`px-4 py-2 rounded-md text-sm font-medium ${
                activeView === 'list'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              View Entries
            </button>
            <button
              onClick={() => setActiveView('upload')}
              className={`px-4 py-2 rounded-md text-sm font-medium ${
                activeView === 'upload'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Upload
            </button>
          </div>
        </div>
        
        {stats && (
          <div className="mb-4 p-4 bg-blue-50 rounded">
            <p className="text-sm text-gray-700">
              Total Entries: <strong>{stats.total_entries || 0}</strong>
            </p>
          </div>
        )}
      </div>

      {/* List View */}
      {activeView === 'list' && (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="p-4 border-b border-gray-200 flex justify-between items-center">
            <div className="flex items-center gap-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={selectedIds.size === entries.length && entries.length > 0}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">
                  Select All ({selectedIds.size} selected)
                </span>
              </label>
            </div>
            <div className="flex gap-2">
              {selectedIds.size > 0 && (
                <button
                  onClick={handleDeleteSelected}
                  disabled={deleting}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
                >
                  {deleting ? 'Deleting...' : `Delete Selected (${selectedIds.size})`}
                </button>
              )}
              <button
                onClick={handleDeleteAll}
                disabled={deleting || entries.length === 0}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
              >
                {deleting ? 'Deleting...' : 'Delete All'}
              </button>
              <button
                onClick={loadEntries}
                disabled={loading}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50 text-sm font-medium"
              >
                {loading ? 'Loading...' : 'Refresh'}
              </button>
            </div>
          </div>

          {loading ? (
            <div className="p-12 text-center">
              <p className="text-gray-500">Loading entries...</p>
            </div>
          ) : entries.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-gray-500">No knowledge base entries found</p>
              <p className="text-sm text-gray-400 mt-2">Upload entries using the Upload tab</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                      <input
                        type="checkbox"
                        checked={selectedIds.size === entries.length && entries.length > 0}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Question
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Answer
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {entries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(entry.id)}
                          onChange={(e) => handleSelectEntry(entry.id, e.target.checked)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900 max-w-md">
                        <div className="truncate" title={entry.question}>
                          {entry.question}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600 max-w-md">
                        <div className="truncate" title={entry.answer}>
                          {entry.answer}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Upload View */}
      {activeView === 'upload' && (
        <div className="bg-white shadow rounded-lg p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Upload CSV File (question,answer format)
              </label>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>

            {preview.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium mb-2">Preview (first 5 entries):</h3>
                <div className="border rounded p-4 max-h-64 overflow-y-auto">
                  {preview.map((item, idx) => (
                    <div key={idx} className="mb-4 pb-4 border-b last:border-0">
                      <p className="font-medium text-sm">Q: {item.question}</p>
                      <p className="text-sm text-gray-600 mt-1">A: {item.answer}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {file && (
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {uploading ? 'Uploading...' : 'Upload Knowledge Base'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

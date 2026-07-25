import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { supabase } from '../../lib/supabase'

interface Report {
  id: string
  breach_id: string
  organization_name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at: string
  completed_at?: string
  processing_time_ms?: number
  search_results_count?: number
  scraped_urls_count?: number
  cost_estimate?: number
  error_message?: string
  ai_model_used?: string
  report_type?: string
  metadata?: {
    research_methodology?: string
    research_phases?: any
    total_research_scope?: {
      total_sources: number
      total_scraped_content: number
      research_depth: string
    }
  }
}

interface ReportsTableProps {
  filters?: {
    search?: string
    status?: string[]
  }
}

export function ReportsTable({ filters = {} }: ReportsTableProps) {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState(filters.search || '')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'created_at' | 'completed_at' | 'processing_time_ms'>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // Load reports from database
  useEffect(() => {
    loadReports()
  }, [searchTerm, statusFilter, sortBy, sortOrder])

  // Test database connection on component mount
  useEffect(() => {
    const testConnection = async () => {
      try {
        console.log('Testing v_ai_reports view connection...')
        const { data, error, count } = await supabase
          .from('v_ai_reports')
          .select('*', { count: 'exact', head: true })

        if (error) {
          console.error('v_ai_reports view error:', error)
          console.log('Trying research_jobs table directly...')

          // Fallback to research_jobs table
          const { data: jobsData, error: jobsError, count: jobsCount } = await supabase
            .from('research_jobs')
            .select('*', { count: 'exact', head: true })

          if (jobsError) {
            console.error('research_jobs table error:', jobsError)
          } else {
            console.log(`research_jobs table exists with ${jobsCount} records`)
          }
        } else {
          console.log(`v_ai_reports view exists with ${count} records`)
        }
      } catch (error) {
        console.error('Database connection test failed:', error)
      }
    }

    testConnection()
  }, [])

  const loadReports = async () => {
    try {
      setLoading(true)
      console.log('Loading AI reports...')

      let query = supabase
        .from('v_ai_reports')
        .select(`
          id,
          breach_id,
          organization_name,
          status,
          created_at,
          completed_at,
          processing_time_ms,
          search_results_count,
          scraped_urls_count,
          cost_estimate,
          error_message,
          metadata,
          ai_model_used,
          report_type
        `)

      // Apply search filter
      if (searchTerm) {
        query = query.ilike('organization_name', `%${searchTerm}%`)
      }

      // Apply status filter
      if (statusFilter !== 'all') {
        query = query.eq('status', statusFilter)
      }

      // Apply sorting
      query = query.order(sortBy, { ascending: sortOrder === 'asc' })

      const { data, error } = await query.limit(100)

      if (error) {
        console.error('Error loading reports:', error)
        alert(`Error loading reports: ${error.message}`)
        return
      }

      console.log(`Loaded ${data?.length || 0} AI reports`)
      setReports(data || [])
    } catch (error) {
      console.error('Failed to load reports:', error)
      alert(`Failed to load reports: ${error}`)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      pending: { variant: 'secondary', text: 'Pending' },
      processing: { variant: 'default', text: 'Processing' },
      completed: { variant: 'success', text: 'Completed' },
      failed: { variant: 'destructive', text: 'Failed' }
    }

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending
    return <Badge variant={config.variant as any}>{config.text}</Badge>
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A'
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60000).toFixed(1)}m`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const viewReport = (reportId: string) => {
    // Account for GitHub Pages base path
    const basePath = import.meta.env.BASE_URL || '/'
    // Ensure proper slash handling: remove trailing slash from basePath, then add one
    const normalizedBasePath = basePath.replace(/\/$/, '') + '/'
    const reportUrl = `${normalizedBasePath}ai-report?id=${reportId}`
    window.open(reportUrl, '_blank')
  }

  const deleteReport = async (reportId: string) => {
    if (!confirm('Are you sure you want to delete this report?')) return

    try {
      const { error } = await supabase
        .from('research_jobs')
        .delete()
        .eq('id', reportId)

      if (error) {
        console.error('Error deleting report:', error)
        alert('Failed to delete report. Please try again.')
        return
      }

      // Reload reports
      loadReports()
    } catch (error) {
      console.error('Failed to delete report:', error)
      alert('Failed to delete report. Please try again.')
    }
  }

  const regenerateReport = async (breachId: string, organizationName: string) => {
    if (!confirm(`Regenerate AI report for ${organizationName}? This will create a new report with the latest research.`)) return

    try {
      // Call Supabase Edge Function using the client (avoids CORS issues)
      const { data, error } = await supabase.functions.invoke('generate-ai-report', {
        body: {
          breachId: breachId,
          userId: 'reports-tab-user' // Optional user tracking
        }
      })

      if (error) {
        throw new Error(error.message)
      }

      if (data?.reportId) {
        alert('Report generation started! Refresh the page in a few minutes to see the new report.')
        // Reload reports to show the new pending report
        loadReports()
      }
    } catch (error) {
      console.error('Failed to regenerate report:', error)
      alert('Failed to start report generation. Please try again.')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600 dark:text-gray-400">Loading reports...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">AI Reports</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Comprehensive 4-phase business intelligence reports with extensive research
          </p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {reports.length} reports found
          </div>
          {reports.length > 0 && (
            <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {reports.filter(r => r.status === 'completed').length} completed • {' '}
              {reports.filter(r => r.status === 'processing').length} processing • {' '}
              {reports.filter(r => r.status === 'failed').length} failed
            </div>
          )}
        </div>
      </div>

      {/* Summary Statistics */}
      {reports.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {reports.filter(r => r.status === 'completed').length}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Completed Reports</div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {Math.round(reports.filter(r => r.metadata?.total_research_scope?.total_sources).reduce((sum, r) => sum + (r.metadata?.total_research_scope?.total_sources || 0), 0) / Math.max(reports.filter(r => r.metadata?.total_research_scope?.total_sources).length, 1))}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Avg Sources per Report</div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
              {Math.round(reports.filter(r => r.processing_time_ms).reduce((sum, r) => sum + (r.processing_time_ms || 0), 0) / Math.max(reports.filter(r => r.processing_time_ms).length, 1) / 1000)}s
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Avg Processing Time</div>
          </div>
          {/* Removed total research cost box */}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            type="text"
            placeholder="Search by organization name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full"
          />
        </div>
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="all">All Status</option>
          <option value="completed">Completed</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
        </select>

        <select
          value={`${sortBy}-${sortOrder}`}
          onChange={(e) => {
            const [field, order] = e.target.value.split('-')
            setSortBy(field as any)
            setSortOrder(order as any)
          }}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="created_at-desc">Newest First</option>
          <option value="created_at-asc">Oldest First</option>
          <option value="completed_at-desc">Recently Completed</option>
          <option value="processing_time_ms-desc">Longest Processing</option>
          <option value="processing_time_ms-asc">Fastest Processing</option>
        </select>
      </div>

      {/* Reports Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Organization
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Research Scope
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Processing Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
              {reports.map((report) => (
                <tr key={report.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex flex-col">
                      <div className="text-sm font-medium text-gray-900 dark:text-white">
                        {report.organization_name}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        ID: {report.id.slice(0, 8)}...
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getStatusBadge(report.status)}
                    {report.error_message && (
                      <div className="text-xs text-red-600 dark:text-red-400 mt-1">
                        {report.error_message.slice(0, 50)}...
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900 dark:text-white">
                      {report.metadata?.total_research_scope ? (
                        <>
                          <div>{report.metadata.total_research_scope.total_sources} sources</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {report.metadata.total_research_scope.total_scraped_content} scraped
                          </div>
                        </>
                      ) : (
                        <>
                          <div>{report.search_results_count || 0} sources</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {report.scraped_urls_count || 0} scraped
                          </div>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                    {formatDuration(report.processing_time_ms)}
                    {/* Cost estimate removed */}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    <div>{formatDate(report.created_at)}</div>
                    {report.completed_at && (
                      <div className="text-xs">
                        Completed: {formatDate(report.completed_at)}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex flex-col space-y-1">
                      <div className="flex space-x-2">
                        {report.status === 'completed' && (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => viewReport(report.id)}
                          >
                            View Report
                          </Button>
                        )}
                        {(report.status === 'completed' || report.status === 'failed') && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => regenerateReport(report.breach_id, report.organization_name)}
                          >
                            Regenerate
                          </Button>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => deleteReport(report.id)}
                        className="self-start"
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {reports.length === 0 && !loading && (
          <div className="text-center py-12">
            <div className="text-gray-500 dark:text-gray-400">
              <div className="text-4xl mb-4"></div>
              <h3 className="text-lg font-medium mb-2">No AI reports found</h3>
              <p className="text-sm mb-4">
                Generate your first AI report by clicking the "AI Report" button on any breach in the Breach Notifications tab.
              </p>
              <div className="text-xs text-gray-400 dark:text-gray-500">
                Search filters: "{searchTerm}" | Status: {statusFilter} | Sort: {sortBy}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

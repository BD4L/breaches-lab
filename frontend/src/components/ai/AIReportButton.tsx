import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { supabase, type BreachRecord } from '../../lib/supabase'
import { Brain, FileText, Clock, AlertCircle, CheckCircle, ExternalLink } from 'lucide-react'

interface AIReportButtonProps {
  breach: BreachRecord
  className?: string
}

interface ReportStatus {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  processingTimeMs?: number
  searchResultsCount?: number
  scrapedUrlsCount?: number
  errorMessage?: string
  cached?: boolean
}

export function AIReportButton({ breach, className }: AIReportButtonProps) {
  const [loading, setLoading] = useState(false)
  const [reportStatus, setReportStatus] = useState<ReportStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Check for existing report on component mount
  useEffect(() => {
    checkExistingReport()
  }, [breach.id])

  const checkExistingReport = async () => {
    try {
      const { data, error } = await supabase
        .from('research_jobs')
        .select('id, status, processing_time_ms, search_results_count, scraped_urls_count, error_message')
        .eq('scraped_item', breach.id)
        .eq('report_type', 'ai_breach_analysis')
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()

      if (data) {
        setReportStatus({
          id: data.id,
          status: data.status,
          processingTimeMs: data.processing_time_ms,
          searchResultsCount: data.search_results_count,
          scrapedUrlsCount: data.scraped_urls_count,
          errorMessage: data.error_message
        })
      }
    } catch (err) {
      console.error('Error checking existing report:', err)
    }
  }

  const generateReport = async () => {
    setLoading(true)
    setError(null)

    try {
      // Call Supabase Edge Function
      const { data, error } = await supabase.functions.invoke('generate-ai-report', {
        body: { 
          breachId: breach.id,
          userId: null // For now, using anonymous access
        }
      })

      if (error) {
        throw new Error(error.message)
      }

      const result = data as {
        reportId: string
        status: string
        processingTimeMs?: number
        searchResultsCount?: number
        scrapedUrlsCount?: number
        cached?: boolean
      }

      setReportStatus({
        id: result.reportId,
        status: result.status as any,
        processingTimeMs: result.processingTimeMs,
        searchResultsCount: result.searchResultsCount,
        scrapedUrlsCount: result.scrapedUrlsCount,
        cached: result.cached
      })

      // If processing, start polling for completion
      if (result.status === 'processing') {
        pollReportStatus(result.reportId)
      } else if (result.status === 'completed') {
        // Open report immediately if completed
        openReport(result.reportId)
      }

    } catch (err) {
      console.error('Error generating report:', err)
      setError(err instanceof Error ? err.message : 'Failed to generate report')
    } finally {
      setLoading(false)
    }
  }

  const pollReportStatus = async (reportId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const { data } = await supabase
          .from('research_jobs')
          .select('id, status, processing_time_ms, search_results_count, scraped_urls_count, error_message')
          .eq('id', reportId)
          .single()

        if (data) {
          const newStatus: ReportStatus = {
            id: data.id,
            status: data.status,
            processingTimeMs: data.processing_time_ms,
            searchResultsCount: data.search_results_count,
            scrapedUrlsCount: data.scraped_urls_count,
            errorMessage: data.error_message
          }

          setReportStatus(newStatus)

          if (data.status === 'completed') {
            clearInterval(pollInterval)
            setLoading(false)
            // Auto-open completed report
            openReport(reportId)
          } else if (data.status === 'failed') {
            clearInterval(pollInterval)
            setLoading(false)
            setError(data.error_message || 'Report generation failed')
          }
        }
      } catch (err) {
        console.error('Error polling report status:', err)
        clearInterval(pollInterval)
        setLoading(false)
      }
    }, 2000) // Poll every 2 seconds

    // Stop polling after 5 minutes
    setTimeout(() => {
      clearInterval(pollInterval)
      setLoading(false)
    }, 300000)
  }

  const openReport = (reportId: string) => {
    // Open report in new tab/window - use correct base path for GitHub Pages
    const basePath = import.meta.env.BASE_URL || '/'
    // Ensure proper slash handling: remove trailing slash from basePath, then add one
    const normalizedBasePath = basePath.replace(/\/$/, '') + '/'
    const reportUrl = `${normalizedBasePath}ai-report?id=${reportId}`
    window.open(reportUrl, '_blank')
  }

  const getButtonContent = () => {
    if (loading) {
      return (
        <>
          <Clock className="w-4 h-4 animate-spin" />
          <span>Generating...</span>
        </>
      )
    }

    if (reportStatus) {
      switch (reportStatus.status) {
        case 'completed':
          return (
            <>
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span>View Report</span>
              <ExternalLink className="w-3 h-3" />
            </>
          )
        case 'processing':
          return (
            <>
              <Clock className="w-4 h-4 animate-pulse text-blue-600" />
              <span>Processing...</span>
            </>
          )
        case 'failed':
          return (
            <>
              <AlertCircle className="w-4 h-4 text-red-600" />
              <span>Retry Report</span>
            </>
          )
        default:
          return (
            <>
              <Brain className="w-4 h-4" />
              <span>AI Report</span>
            </>
          )
      }
    }

    return (
      <>
        <Brain className="w-4 h-4" />
        <span>AI Report</span>
      </>
    )
  }

  const handleClick = () => {
    if (reportStatus?.status === 'completed') {
      openReport(reportStatus.id)
    } else {
      generateReport()
    }
  }

  const getButtonVariant = () => {
    if (reportStatus?.status === 'completed') return 'default'
    if (reportStatus?.status === 'failed') return 'destructive'
    return 'outline'
  }

  const getTooltipText = () => {
    if (reportStatus?.status === 'completed') {
      const stats = []
      if (reportStatus.processingTimeMs) {
        stats.push(`Generated in ${(reportStatus.processingTimeMs / 1000).toFixed(1)}s`)
      }
      if (reportStatus.searchResultsCount) {
        stats.push(`${reportStatus.searchResultsCount} sources`)
      }
      if (reportStatus.cached) {
        stats.push('Cached result')
      }
      return stats.length > 0 ? stats.join(' • ') : 'Click to view AI-generated business intelligence report'
    }

    if (reportStatus?.status === 'failed') {
      return reportStatus.errorMessage || 'Report generation failed - click to retry'
    }

    if (loading || reportStatus?.status === 'processing') {
      return'AI is conducting 4-phase legal intelligence research: breach analysis individual damages affected demographics legal marketing strategy...'
    }

    return 'Generate comprehensive legal intelligence report: breach details, individual damages assessment, affected demographics analysis, and class action marketing strategy with 15-25 sources per report'
  }

  return (
    <div className="relative">
      <Button
        variant={getButtonVariant()}
        size="sm"
        onClick={handleClick}
        disabled={loading || reportStatus?.status === 'processing'}
        className={`${className} flex items-center space-x-2 transition-all duration-200`}
        title={getTooltipText()}
      >
        {getButtonContent()}
      </Button>

      {/* Error display */}
      {error && (
        <div className="absolute top-full left-0 mt-1 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700 max-w-xs z-10">
          {error}
        </div>
      )}

      {/* Processing status */}
      {reportStatus?.status === 'processing' && (
        <div className="absolute top-full left-0 mt-1 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700 max-w-xs z-10">
          <div className="flex items-center space-x-1">
            <Clock className="w-3 h-3 animate-pulse" />
            <span>AI is conducting 4-phase legal intelligence research...</span>
          </div>
        </div>
      )}
    </div>
  )
}

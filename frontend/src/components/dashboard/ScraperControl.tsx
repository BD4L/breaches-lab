import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { ScheduleManager } from './ScheduleManager'
import { githubActions } from '../../lib/github-actions'

interface ScraperGroup {
  id: string
  name: string
  description: string
  scrapers: string[]
  schedule: string
  lastRun?: string
  status: 'idle' | 'running' | 'success' | 'failed'
  canTrigger: boolean
}

interface ScraperControlProps {
  onClose: () => void
}

export function ScraperControl({ onClose }: ScraperControlProps) {
  const [scraperGroups, setScraperGroups] = useState<ScraperGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState<string | null>(null)
  const [showScheduleManager, setShowScheduleManager] = useState(false)

  // Define scraper groups based on paralell.yml workflow structure
  const defaultScraperGroups: ScraperGroup[] = [
    {
      id: 'government-scrapers',
      name:'Government & Federal Scrapers',
      description: 'SEC EDGAR 8-K, HHS OCR Breach Portal',
      scrapers: ['SEC EDGAR 8-K', 'HHS OCR'],
      schedule: 'Every 30 minutes',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-1',
      name:'State AG Group 1 (DE, CA, WA, HI)',
      description: 'Delaware, California, Washington, Hawaii',
      scrapers: ['Delaware AG', 'California AG', 'Washington AG', 'Hawaii AG'],
      schedule: 'Every 30 minutes',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-2',
      name:'State AG Group 2 (IN, IA, ME)',
      description: 'Indiana, Iowa, Maine',
      scrapers: ['Indiana AG', 'Iowa AG', 'Maine AG'],
      schedule: 'Every 30 minutes',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-3',
      name:'State AG Group 3 (MA, MT, NH, NJ)',
      description: 'Massachusetts, Montana, New Hampshire, New Jersey',
      scrapers: ['Massachusetts AG', 'Montana AG', 'New Hampshire AG', 'New Jersey AG'],
      schedule: 'Every 30 minutes',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'state-ag-group-4',
      name:'State AG Group 4 (ND, OK, VT, WI, TX)',
      description: 'North Dakota, Oklahoma, Vermont, Wisconsin, Texas',
      scrapers: ['North Dakota AG', 'Oklahoma Cyber', 'Vermont AG', 'Wisconsin DATCP', 'Texas AG'],
      schedule: 'Every 30 minutes',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'news-and-api-scrapers',
      name:'News & API Scrapers',
      description: 'BreachSense, Cybersecurity News, Company IR, HIBP API',
      scrapers: ['BreachSense', 'Cybersecurity News RSS', 'Company IR', 'HIBP API'],
      schedule: 'Every 30 minutes',
      status: 'idle',
      canTrigger: true
    },
    {
      id: 'problematic-scrapers',
      name:'Problematic Scrapers (MD)',
      description: 'Maryland AG (known website issues)',
      scrapers: ['Maryland AG'],
      schedule: 'Every 30 minutes (Continue on Error)',
      status: 'idle',
      canTrigger: true
    }
  ]

  useEffect(() => {
    // Load scraper status from GitHub Actions API
    loadScraperStatus()
  }, [])

  const loadScraperStatus = async () => {
    try {
      // Try to load real status from GitHub Actions API
      const scraperStatus = await githubActions.getScraperStatus()

      if (scraperStatus.length > 0) {
        // Update default groups with real status
        const updatedGroups = defaultScraperGroups.map(group => {
          const matchingStatus = scraperStatus.find(status =>
            status.workflow.toLowerCase().includes(group.id.replace('-', ' ')) ||
            status.workflow.toLowerCase().includes('parallel') ||
            status.workflow.toLowerCase().includes('scraper')
          )

          if (matchingStatus) {
            return {
              ...group,
              status: matchingStatus.status === 'completed'
                ? (matchingStatus.conclusion === 'success' ? 'success' : 'failed')
                : matchingStatus.status === 'in_progress' ? 'running' : 'idle',
              lastRun: matchingStatus.lastRun
            }
          }
          return group
        })
        setScraperGroups(updatedGroups)
      } else {
        // Fallback to default groups if API fails
        setScraperGroups(defaultScraperGroups)
      }
    } catch (error) {
      console.error('Failed to load scraper status:', error)
      setScraperGroups(defaultScraperGroups)
    } finally {
      setLoading(false)
    }
  }

  const triggerWorkflow = async (groupId: string) => {
    setTriggering(groupId)

    try {
      let success = false

      // Handle special cases and workflow triggering
      switch (groupId) {
        case 'all':
          // Trigger the main parallel workflow with all groups enabled
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: true,
            run_state_ag_1: true,
            run_state_ag_2: true,
            run_state_ag_3: true,
            run_state_ag_4: true,
            run_news_api: true,
            run_problematic: true
          })
          break
        case 'government-scrapers':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: true,
            run_state_ag_1: false,
            run_state_ag_2: false,
            run_state_ag_3: false,
            run_state_ag_4: false,
            run_news_api: false,
            run_problematic: false
          })
          break
        case 'state-ag-group-1':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: false,
            run_state_ag_1: true,
            run_state_ag_2: false,
            run_state_ag_3: false,
            run_state_ag_4: false,
            run_news_api: false,
            run_problematic: false
          })
          break
        case 'state-ag-group-2':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: false,
            run_state_ag_1: false,
            run_state_ag_2: true,
            run_state_ag_3: false,
            run_state_ag_4: false,
            run_news_api: false,
            run_problematic: false
          })
          break
        case 'state-ag-group-3':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: false,
            run_state_ag_1: false,
            run_state_ag_2: false,
            run_state_ag_3: true,
            run_state_ag_4: false,
            run_news_api: false,
            run_problematic: false
          })
          break
        case 'state-ag-group-4':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: false,
            run_state_ag_1: false,
            run_state_ag_2: false,
            run_state_ag_3: false,
            run_state_ag_4: true,
            run_news_api: false,
            run_problematic: false
          })
          break
        case 'news-and-api-scrapers':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: false,
            run_state_ag_1: false,
            run_state_ag_2: false,
            run_state_ag_3: false,
            run_state_ag_4: false,
            run_news_api: true,
            run_problematic: false
          })
          break
        case 'problematic-scrapers':
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: false,
            run_state_ag_1: false,
            run_state_ag_2: false,
            run_state_ag_3: false,
            run_state_ag_4: false,
            run_news_api: false,
            run_problematic: true
          })
          break

        default:
          // Default to running all groups
          success = await githubActions.triggerWorkflowByName('Run All Scrapers (Parallel)', {
            run_government: true,
            run_state_ag_1: true,
            run_state_ag_2: true,
            run_state_ag_3: true,
            run_state_ag_4: true,
            run_news_api: true,
            run_problematic: true
          })
          break
      }

      if (success) {
        console.log(`Successfully triggered workflow for group: ${groupId}`)

        // Update status to running
        setScraperGroups(prev => prev.map(group =>
          group.id === groupId || groupId === 'all'
            ? { ...group, status: 'running' as const, lastRun: new Date().toISOString() }
            : group
        ))

        // Reload status after a delay to get real updates
        setTimeout(() => {
          loadScraperStatus()
        }, 10000)

      } else {
        throw new Error('Failed to trigger workflow')
      }

    } catch (error) {
      console.error('Failed to trigger workflow:', error)

      // Show error status
      setScraperGroups(prev => prev.map(group =>
        group.id === groupId
          ? { ...group, status: 'failed' as const }
          : group
      ))

      // Show user-friendly error message
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      console.error('Workflow trigger error details:', error)

      if (errorMessage.includes('GitHub token not configured')) {
        alert('GitHub token not configured. Please add PUBLIC_GITHUB_TOKEN to repository secrets and redeploy.')
      } else if (errorMessage.includes('422')) {
        alert('Cannot run workflow: The workflow may be disabled or have invalid inputs. Check that paralell.yml is enabled and has proper workflow_dispatch configuration.')
      } else if (errorMessage.includes('Workflow') && errorMessage.includes('not found')) {
        alert(`Workflow not found: ${errorMessage}`)
      } else if (errorMessage.includes('403')) {
        alert('Permission denied. Check if GitHub token has workflow permissions.')
      } else {
        alert(`Failed to trigger workflow: ${errorMessage}`)
      }
    } finally {
      setTriggering(null)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-blue-100 text-blue-800'
      case 'success': return 'bg-green-100 text-green-800'
      case 'failed': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case'running': return''
      case'success': return''
      case'failed': return''
      default: return''
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Scraper Control Center
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manage and trigger breach data scrapers across 37+ sources
            </p>
          </div>
          <Button variant="outline" onClick={onClose}>
             Close
          </Button>
        </div>

        {/* Quick Actions */}
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">Quick Actions</h3>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => triggerWorkflow('all')}
              disabled={!!triggering}
            >
               Run All Scrapers
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('government-scrapers')}
              disabled={!!triggering}
            >
               Government & Federal
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('news-and-api-scrapers')}
              disabled={!!triggering}
            >
               News & API
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('problematic-scrapers')}
              disabled={!!triggering}
            >
               Problematic (MD)
            </Button>
          </div>
        </div>

        {/* Scraper Groups */}
        <div className="space-y-4">
          {scraperGroups.map(group => (
            <div key={group.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {group.name}
                  </h3>
                  <Badge className={getStatusColor(group.status)}>
                    {getStatusIcon(group.status)} {group.status}
                  </Badge>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => triggerWorkflow(group.id)}
                  disabled={!group.canTrigger || triggering === group.id || group.status === 'running'}
                >
                  {triggering === group.id ?'Starting...':'▶ Run Now'}
                </Button>
              </div>
              
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                {group.description}
              </p>
              
              <div className="flex flex-wrap gap-1 mb-2">
                {group.scrapers.map(scraper => (
                  <Badge key={scraper} variant="secondary" className="text-xs">
                    {scraper}
                  </Badge>
                ))}
              </div>
              
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                <span>Schedule: {group.schedule}</span>
                {group.lastRun && (
                  <span>Last run: {new Date(group.lastRun).toLocaleString()}</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Schedule Management */}
        <div className="mt-8 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
             Schedule Management & Frequency Control
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
            Current schedules and manual frequency controls:
          </p>
          <div className="space-y-2 text-sm mb-4">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
              <span><strong>Parallel workflow:</strong> Every 30 minutes (all scraper groups)</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span><strong>Daily tracking:</strong> 1am to 1am change detection</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-orange-500 rounded-full"></span>
              <span><strong>Manual triggers:</strong> Available for individual groups or all groups</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-purple-500 rounded-full"></span>
              <span><strong>Email alerts:</strong> Automatic notifications for new breaches</span>
            </div>
          </div>

          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowScheduleManager(true)}
            >
               Manage Schedules
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => triggerWorkflow('all')}
              disabled={!!triggering}
            >
               Run All Now
            </Button>
          </div>
        </div>

        {/* Schedule Manager Modal */}
        {showScheduleManager && (
          <ScheduleManager onClose={() => setShowScheduleManager(false)} />
        )}
      </div>
    </div>
  )
}

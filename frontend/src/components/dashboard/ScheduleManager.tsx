import React, { useState } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'

interface ScheduleConfig {
  id: string
  name: string
  cron: string
  description: string
  enabled: boolean
  nextRun?: string
}

interface ScheduleManagerProps {
  onClose: () => void
}

export function ScheduleManager({ onClose }: ScheduleManagerProps) {
  const [schedules, setSchedules] = useState<ScheduleConfig[]>([
    {
      id: 'main-daily',
      name: 'Main Scraper Workflow',
      cron: '0 3 * * *',
      description: 'Daily at 3 AM UTC - All scraper groups',
      enabled: true,
      nextRun: '2025-06-02T03:00:00Z'
    },
    {
      id: 'ma-ag-frequent',
      name: 'Massachusetts AG (Frequent)',
      cron: '0 */6 * * *',
      description: 'Every 6 hours - High priority state',
      enabled: true,
      nextRun: '2025-06-01T21:00:00Z'
    },
    {
      id: 'news-hourly',
      name: 'News & API (Hourly)',
      cron: '0 * * * *',
      description: 'Every hour - News feeds and APIs',
      enabled: false
    },
    {
      id: 'weekend-light',
      name: 'Weekend Light Mode',
      cron: '0 6,18 * * 6,0',
      description: 'Twice daily on weekends - Reduced load',
      enabled: false
    }
  ])

  const [editingSchedule, setEditingSchedule] = useState<string | null>(null)
  const [newCron, setNewCron] = useState('')

  const cronPresets = [
    { label: 'Every 15 minutes', value: '*/15 * * * *' },
    { label: 'Every 30 minutes', value: '*/30 * * * *' },
    { label: 'Every hour', value: '0 * * * *' },
    { label: 'Every 2 hours', value: '0 */2 * * *' },
    { label: 'Every 6 hours', value: '0 */6 * * *' },
    { label: 'Every 12 hours', value: '0 */12 * * *' },
    { label: 'Daily at 3 AM', value: '0 3 * * *' },
    { label: 'Daily at 6 AM', value: '0 6 * * *' },
    { label: 'Twice daily (6 AM, 6 PM)', value: '0 6,18 * * *' },
    { label: 'Weekdays only at 9 AM', value: '0 9 * * 1-5' },
    { label: 'Weekends only at 10 AM', value: '0 10 * * 6,0' }
  ]

  const toggleSchedule = (id: string) => {
    setSchedules(prev => prev.map(schedule => 
      schedule.id === id 
        ? { ...schedule, enabled: !schedule.enabled }
        : schedule
    ))
  }

  const updateCron = (id: string, newCronValue: string) => {
    setSchedules(prev => prev.map(schedule => 
      schedule.id === id 
        ? { ...schedule, cron: newCronValue }
        : schedule
    ))
    setEditingSchedule(null)
    setNewCron('')
  }

  const parseCronDescription = (cron: string): string => {
    // Simple cron parser for common patterns
    const parts = cron.split(' ')
    if (parts.length !== 5) return cron

    const [minute, hour, day, month, weekday] = parts

    if (minute.startsWith('*/')) {
      const interval = minute.slice(2)
      return `Every ${interval} minutes`
    }

    if (hour.startsWith('*/')) {
      const interval = hour.slice(2)
      return `Every ${interval} hours`
    }

    if (minute === '0' && hour !== '*') {
      if (hour.includes(',')) {
        const hours = hour.split(',').map(h => `${h}:00`).join(', ')
        return `Daily at ${hours}`
      }
      return `Daily at ${hour}:00`
    }

    return cron
  }

  const getNextRunTime = (cron: string): string => {
    // In a real implementation, this would calculate the next run time
    // For demo purposes, we'll show a placeholder
    return 'Next: In 2h 15m'
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
               Schedule Manager
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Configure automated scraping schedules and intervals
            </p>
          </div>
          <Button variant="outline" onClick={onClose}>
             Close
          </Button>
        </div>

        {/* Warning Notice */}
        <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <div className="flex items-start space-x-2">
            <div>
              <h3 className="font-medium text-yellow-800 dark:text-yellow-200">
                GitHub Actions Integration Required
              </h3>
              <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                Schedule changes require updating GitHub Actions workflow files. 
                This interface shows current schedules and provides cron expressions for manual updates.
              </p>
            </div>
          </div>
        </div>

        {/* Current Schedules */}
        <div className="space-y-4 mb-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Current Schedules
          </h3>
          
          {schedules.map(schedule => (
            <div key={schedule.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-3">
                  <h4 className="font-medium text-gray-900 dark:text-white">
                    {schedule.name}
                  </h4>
                  <Badge variant={schedule.enabled ? 'default' : 'secondary'}>
                    {schedule.enabled ?'Active':'Disabled'}
                  </Badge>
                </div>
                <div className="flex space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setEditingSchedule(schedule.id)
                      setNewCron(schedule.cron)
                    }}
                  >
                     Edit
                  </Button>
                  <Button
                    variant={schedule.enabled ? 'destructive' : 'default'}
                    size="sm"
                    onClick={() => toggleSchedule(schedule.id)}
                  >
                    {schedule.enabled ? 'Disable' : 'Enable'}
                  </Button>
                </div>
              </div>
              
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                {schedule.description}
              </p>
              
              {editingSchedule === schedule.id ? (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Cron Expression
                    </label>
                    <Input
                      value={newCron}
                      onChange={(e) => setNewCron(e.target.value)}
                      placeholder="0 3 * * *"
                      className="font-mono"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Quick Presets
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {cronPresets.map(preset => (
                        <Button
                          key={preset.value}
                          variant="outline"
                          size="sm"
                          onClick={() => setNewCron(preset.value)}
                          className="text-xs"
                        >
                          {preset.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                  
                  <div className="flex space-x-2">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => updateCron(schedule.id, newCron)}
                    >
                      Save
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditingSchedule(null)
                        setNewCron('')
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-between items-center text-sm">
                  <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded font-mono">
                    {schedule.cron}
                  </code>
                  <span className="text-gray-500 dark:text-gray-400">
                    {parseCronDescription(schedule.cron)}
                  </span>
                  {schedule.enabled && (
                    <span className="text-blue-600 dark:text-blue-400">
                      {getNextRunTime(schedule.cron)}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Cron Help */}
        <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
             Cron Expression Format
          </h3>
          <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
            <div className="font-mono bg-white dark:bg-gray-800 p-2 rounded">
              * * * * *<br/>
              │ │ │ │ │<br/>
              │ │ │ │ └─ Day of week (0-7, Sunday = 0 or 7)<br/>
              │ │ │ └─── Month (1-12)<br/>
              │ │ └───── Day of month (1-31)<br/>
              │ └─────── Hour (0-23)<br/>
              └───────── Minute (0-59)
            </div>
            <div>
              <strong>Examples:</strong>
              <ul className="list-disc list-inside mt-1 space-y-1">
                <li><code>*/15 * * * *</code> - Every 15 minutes</li>
                <li><code>0 */2 * * *</code> - Every 2 hours</li>
                <li><code>0 9 * * 1-5</code> - 9 AM on weekdays</li>
                <li><code>0 0 1 * *</code> - First day of every month</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

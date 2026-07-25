import React, { useState } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import type { ViewType } from '../dashboard/ViewToggle'

interface DateFilterProps {
  onDateFilterChange: (filter: {
    scrapedDateRange: string
    breachDateRange: string
    publicationDateRange: string
  }) => void
  currentView: ViewType
}

export function DateFilter({ onDateFilterChange, currentView }: DateFilterProps) {
  const [scrapedDateRange, setScrapedDateRange] = useState('')
  const [breachDateRange, setBreachDateRange] = useState('')
  const [publicationDateRange, setPublicationDateRange] = useState('')

  // Predefined date ranges for scraped data
  const scrapedPresets = [
    { label: 'Today', value: 'today', days: 0 },
    { label: 'Yesterday', value: 'yesterday', days: 1 },
    { label: 'Last 3 days', value: 'last-3-days', days: 3 },
    { label: 'Last week', value: 'last-week', days: 7 },
    { label: 'Last 2 weeks', value: 'last-2-weeks', days: 14 },
    { label: 'Last month', value: 'last-month', days: 30 },
    { label: 'Last 3 months', value: 'last-3-months', days: 90 },
    { label: 'All time', value: 'all-time', days: null }
  ]

  // Predefined date ranges for breach/publication dates
  const eventPresets = [
    { label: 'Last 7 days', value: 'last-7-days', days: 7 },
    { label: 'Last 30 days', value: 'last-30-days', days: 30 },
    { label: 'Last 3 months', value: 'last-3-months', days: 90 },
    { label: 'Last 6 months', value: 'last-6-months', days: 180 },
    { label: 'Last year', value: 'last-year', days: 365 },
    { label: 'All time', value: 'all-time', days: null }
  ]

  const handleScrapedDateChange = (value: string) => {
    setScrapedDateRange(value)
    updateFilters(value, breachDateRange, publicationDateRange)
  }

  const handleBreachDateChange = (value: string) => {
    setBreachDateRange(value)
    updateFilters(scrapedDateRange, value, publicationDateRange)
  }

  const handlePublicationDateChange = (value: string) => {
    setPublicationDateRange(value)
    updateFilters(scrapedDateRange, breachDateRange, value)
  }

  const updateFilters = (scraped: string, breach: string, publication: string) => {
    onDateFilterChange({
      scrapedDateRange: scraped,
      breachDateRange: breach,
      publicationDateRange: publication
    })
  }

  const clearFilters = () => {
    setScrapedDateRange('')
    setBreachDateRange('')
    setPublicationDateRange('')
    updateFilters('', '', '')
  }

  const getDateRangeDescription = (value: string, presets: typeof scrapedPresets) => {
    const preset = presets.find(p => p.value === value)
    if (!preset) return value
    
    if (preset.days === null) return 'All records'
    if (preset.days === 0) return 'Today only'
    if (preset.days === 1) return 'Yesterday only'
    
    const endDate = new Date()
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - preset.days)
    
    return `${startDate.toLocaleDateString()} - ${endDate.toLocaleDateString()}`
  }

  return (
    <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
             Date Filters
          </h3>
          {(scrapedDateRange || breachDateRange || publicationDateRange) && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear All
            </Button>
          )}
        </div>

        {/* Scraped Date Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
             When Scraped (Data Collection Date)
          </label>
          <div className="flex flex-wrap gap-2">
            {scrapedPresets.map(preset => (
              <button
                key={preset.value}
                onClick={() => handleScrapedDateChange(preset.value)}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                  scrapedDateRange === preset.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
          {scrapedDateRange && (
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {getDateRangeDescription(scrapedDateRange, scrapedPresets)}
            </div>
          )}
        </div>

        {/* Breach Date Filter - Only for breach view */}
        {currentView === 'breaches' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
               Breach Occurrence Date
            </label>
            <div className="flex flex-wrap gap-2">
              {eventPresets.map(preset => (
                <button
                  key={preset.value}
                  onClick={() => handleBreachDateChange(preset.value)}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    breachDateRange === preset.value
                      ? 'bg-red-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            {breachDateRange && (
              <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Breaches that occurred: {getDateRangeDescription(breachDateRange, eventPresets)}
              </div>
            )}
          </div>
        )}

        {/* Publication Date Filter */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
             Publication/Disclosure Date
          </label>
          <div className="flex flex-wrap gap-2">
            {eventPresets.map(preset => (
              <button
                key={preset.value}
                onClick={() => handlePublicationDateChange(preset.value)}
                className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                  publicationDateRange === preset.value
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
          {publicationDateRange && (
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Published/disclosed: {getDateRangeDescription(publicationDateRange, eventPresets)}
            </div>
          )}
        </div>

        {/* Custom Date Range Inputs */}
        <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Custom Date Ranges
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                Scraped From - To
              </label>
              <div className="flex space-x-2">
                <Input
                  type="date"
                  className="text-xs"
                  onChange={(e) => {
                    const customRange = `custom-scraped-${e.target.value}`
                    handleScrapedDateChange(customRange)
                  }}
                />
                <Input
                  type="date"
                  className="text-xs"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                Breach From - To
              </label>
              <div className="flex space-x-2">
                <Input
                  type="date"
                  className="text-xs"
                  onChange={(e) => {
                    const customRange = `custom-breach-${e.target.value}`
                    handleBreachDateChange(customRange)
                  }}
                />
                <Input
                  type="date"
                  className="text-xs"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                Published From - To
              </label>
              <div className="flex space-x-2">
                <Input
                  type="date"
                  className="text-xs"
                  onChange={(e) => {
                    const customRange = `custom-publication-${e.target.value}`
                    handlePublicationDateChange(customRange)
                  }}
                />
                <Input
                  type="date"
                  className="text-xs"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Active Filters Summary */}
        {(scrapedDateRange || breachDateRange || publicationDateRange) && (
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Active Date Filters
            </h4>
            <div className="flex flex-wrap gap-2">
              {scrapedDateRange && (
                <Badge variant="outline" className="text-xs">
                   Scraped: {scrapedPresets.find(p => p.value === scrapedDateRange)?.label || scrapedDateRange}
                </Badge>
              )}
              {breachDateRange && (
                <Badge variant="outline" className="text-xs">
                   Breach: {eventPresets.find(p => p.value === breachDateRange)?.label || breachDateRange}
                </Badge>
              )}
              {publicationDateRange && (
                <Badge variant="outline" className="text-xs">
                   Published: {eventPresets.find(p => p.value === publicationDateRange)?.label || publicationDateRange}
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

import React, { useState, useEffect } from 'react'
import { Input } from '../ui/Input'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { getSourceTypes, getSourceTypeCounts, getSourcesByCategory, isNewsSource, isBreachSource } from '../../lib/supabase'
import { getSourceTypeColor } from '../../lib/utils'
import { SourceSelector } from './SourceSelector'
import type { ViewType } from '../dashboard/ViewToggle'

interface FilterPanelProps {
  onFiltersChange: (filters: {
    search: string
    sourceTypes: string[]
    selectedSources: number[]
    minAffected: number
  }) => void
  currentView: ViewType
}

export function FilterPanel({ onFiltersChange, currentView }: FilterPanelProps) {
  const [search, setSearch] = useState('')
  const [selectedSourceTypes, setSelectedSourceTypes] = useState<string[]>([])
  const [selectedSources, setSelectedSources] = useState<number[]>([])
  const [minAffected, setMinAffected] = useState(0)
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [sourceTypeCounts, setSourceTypeCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [showSourceSelector, setShowSourceSelector] = useState<string | null>(null)
  const [sourcesByCategory, setSourcesByCategory] = useState<Record<string, Array<{id: number, name: string, itemCount: number, itemType: string}>>>({})
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    async function loadFilterOptions() {
      try {
        const [types, counts, sourcesByCategory] = await Promise.all([
          getSourceTypes(),
          getSourceTypeCounts(),
          getSourcesByCategory()
        ])
        setSourceTypes(types)
        setSourceTypeCounts(counts)
        setSourcesByCategory(sourcesByCategory)

        // Calculate source counts per category
        const categorySourceCounts: Record<string, number> = {}
        Object.keys(sourcesByCategory).forEach(category => {
          categorySourceCounts[category] = sourcesByCategory[category].length
        })
        setSourceCounts(categorySourceCounts)
      } catch (error) {
        console.error('Error loading filter options:', error)
      } finally {
        setLoading(false)
      }
    }

    loadFilterOptions()
  }, [])

  useEffect(() => {
    onFiltersChange({
      search,
      sourceTypes: selectedSourceTypes,
      selectedSources,
      minAffected
    })
  }, [search, selectedSourceTypes, selectedSources, minAffected, onFiltersChange])

  const toggleSourceType = (type: string) => {
    setSelectedSourceTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    )
  }

  const handleSourcesSelected = (category: string, sourceIds: number[]) => {
    // Update selected sources for this category
    const categorySourceIds = sourcesByCategory[category]?.map(s => s.id) || []
    const otherSources = selectedSources.filter(id => !categorySourceIds.includes(id))
    setSelectedSources([...otherSources, ...sourceIds])
    setShowSourceSelector(null)
  }

  const getSelectedSourcesForCategory = (category: string): number[] => {
    const categorySourceIds = sourcesByCategory[category]?.map(s => s.id) || []
    return selectedSources.filter(id => categorySourceIds.includes(id))
  }

  const clearFilters = () => {
    setSearch('')
    setSelectedSourceTypes([])
    setSelectedSources([])
    setMinAffected(0)
  }

  const getCategoryIcon = (category: string): string => {
    switch (category) {
      case'State AG Sites': return''
      case'Government Portals': return''
      case'RSS News Feeds': return''
      case'Specialized Breach Sites': return''
      case'Company IR Sites': return''
      default: return''
    }
  }

  const getCategoryItemType = (category: string): string => {
    switch (category) {
      case 'State AG Sites': return 'breaches'
      case 'Government Portals': return 'breaches'
      case 'RSS News Feeds': return 'articles'
      case 'Specialized Breach Sites': return 'breaches'
      case 'Company IR Sites': return 'reports'
      default: return 'items'
    }
  }

  const affectedThresholds = [
    { label: 'Any', value: 0 },
    { label: '1K+', value: 1000 },
    { label: '10K+', value: 10000 },
    { label: '100K+', value: 100000 },
    { label: '1M+', value: 1000000 }
  ]

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="flex space-x-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-20"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      <div className="space-y-6">
        {/* Search */}
        <div>
          <label htmlFor="search" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            {currentView === 'breaches' ? 'Search Organizations' : 'Search Articles'}
          </label>
          <Input
            id="search"
            type="text"
            placeholder={currentView === 'breaches'
              ? "Search by organization name or leaked data..."
              : "Search by article title or content..."
            }
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Source Categories */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Source Categories
          </label>
          <div className="space-y-3">
            {sourceTypes.filter(type => {
              // Filter source types based on current view
              if (currentView === 'breaches') {
                return !['RSS News Feeds', 'Company IR Sites'].includes(type)
              } else {
                return ['RSS News Feeds', 'Company IR Sites'].includes(type)
              }
            }).map(type => {
              const selectedCount = getSelectedSourcesForCategory(type).length
              const totalCount = sourceCounts[type] || 0
              const isTypeSelected = selectedSourceTypes.includes(type)

              return (
                <div key={type} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => toggleSourceType(type)}
                      className={`inline-flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        isTypeSelected
                          ? 'bg-blue-600 text-white'
                          : getSourceTypeColor(type)
                      } hover:opacity-80`}
                    >
                      <span className="mr-2">{getCategoryIcon(type)}</span>
                      {type}
                      <span className="ml-2 text-xs opacity-75">
                        ({sourceTypeCounts[type] || 0} {getCategoryItemType(type)})
                      </span>
                    </button>

                    {selectedCount > 0 && (
                      <Badge variant="outline" className="text-xs">
                        {selectedCount}/{totalCount} sources
                      </Badge>
                    )}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowSourceSelector(type)}
                    className="text-xs"
                  >
                    Select Sources ({totalCount})
                  </Button>
                </div>
              )
            })}
          </div>
        </div>

        {/* Affected Individuals Threshold - Only for breach view */}
        {currentView === 'breaches' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Minimum Affected Individuals
            </label>
            <div className="flex flex-wrap gap-2">
              {affectedThresholds.map(threshold => (
                <button
                  key={threshold.value}
                  onClick={() => setMinAffected(threshold.value)}
                  className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                    minAffected === threshold.value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                  }`}
                >
                  {threshold.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Active Filters & Clear */}
        {(search || selectedSourceTypes.length > 0 || selectedSources.length > 0 || minAffected > 0) && (
          <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
            <div className="flex flex-wrap gap-2">
              {search && (
                <Badge variant="outline">
                  Search: "{search}"
                </Badge>
              )}
              {selectedSourceTypes.map(type => (
                <Badge key={type} variant="outline">
                  {type}
                </Badge>
              ))}
              {selectedSources.length > 0 && (
                <Badge variant="outline">
                  {selectedSources.length} specific sources
                </Badge>
              )}
              {minAffected > 0 && (
                <Badge variant="outline">
                  Min: {minAffected.toLocaleString()}+
                </Badge>
              )}
            </div>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear All
            </Button>
          </div>
        )}
      </div>

      {/* Source Selector Modal */}
      {showSourceSelector && (
        <SourceSelector
          category={showSourceSelector}
          onClose={() => setShowSourceSelector(null)}
          onSourcesSelected={(sourceIds) => handleSourcesSelected(showSourceSelector, sourceIds)}
          selectedSources={getSelectedSourcesForCategory(showSourceSelector)}
        />
      )}
    </div>
  )
}

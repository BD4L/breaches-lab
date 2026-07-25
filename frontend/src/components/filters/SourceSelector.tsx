import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Input } from '../ui/Input'
import { getSourcesByCategory } from '../../lib/supabase'

interface SourceSelectorProps {
  category: string
  onClose: () => void
  onSourcesSelected: (sourceIds: number[]) => void
  selectedSources: number[]
}

interface Source {
  id: number
  name: string
  originalType: string
  itemCount: number
  itemType: string
}

export function SourceSelector({ category, onClose, onSourcesSelected, selectedSources }: SourceSelectorProps) {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [tempSelected, setTempSelected] = useState<number[]>(selectedSources)

  useEffect(() => {
    loadSources()
  }, [category])

  const loadSources = async () => {
    try {
      setLoading(true)
      const sourcesByCategory = await getSourcesByCategory()
      setSources(sourcesByCategory[category] || [])
    } catch (error) {
      console.error('Failed to load sources:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredSources = sources.filter(source =>
    source.name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const toggleSource = (sourceId: number) => {
    setTempSelected(prev =>
      prev.includes(sourceId)
        ? prev.filter(id => id !== sourceId)
        : [...prev, sourceId]
    )
  }

  const selectAll = () => {
    setTempSelected(filteredSources.map(source => source.id))
  }

  const selectNone = () => {
    setTempSelected([])
  }

  const applySelection = () => {
    onSourcesSelected(tempSelected)
    onClose()
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

  const getBadgeColor = (itemType: string): string => {
    switch (itemType) {
      case 'breaches': return 'bg-red-100 text-red-800'
      case 'articles': return 'bg-blue-100 text-blue-800'
      case 'reports': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getStateFromName = (name: string): string => {
    // Extract state abbreviation or name from source name
    const statePatterns = [
      { pattern: /California/i, state: 'CA' },
      { pattern: /Delaware/i, state: 'DE' },
      { pattern: /Hawaii/i, state: 'HI' },
      { pattern: /Indiana/i, state: 'IN' },
      { pattern: /Iowa/i, state: 'IA' },
      { pattern: /Maine/i, state: 'ME' },
      { pattern: /Massachusetts/i, state: 'MA' },
      { pattern: /Montana/i, state: 'MT' },
      { pattern: /North Dakota/i, state: 'ND' },
      { pattern: /Oklahoma/i, state: 'OK' },
      { pattern: /Vermont/i, state: 'VT' },
      { pattern: /Washington/i, state: 'WA' },
      { pattern: /Wisconsin/i, state: 'WI' },
      { pattern: /Texas/i, state: 'TX' },
      { pattern: /Maryland/i, state: 'MD' },
      { pattern: /New Hampshire/i, state: 'NH' },
      { pattern: /New Jersey/i, state: 'NJ' }
    ]

    for (const { pattern, state } of statePatterns) {
      if (pattern.test(name)) {
        return state
      }
    }
    return ''
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-3xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">{getCategoryIcon(category)}</span>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Select {category}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {sources.reduce((sum, source) => sum + source.itemCount, 0)} total {sources[0]?.itemType || 'items'} across {sources.length} sources
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={onClose}>
             Close
          </Button>
        </div>

        {/* Search and Controls */}
        <div className="mb-4 space-y-3">
          <Input
            type="text"
            placeholder="Search sources..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <div className="flex justify-between items-center">
            <div className="flex space-x-2">
              <Button variant="outline" size="sm" onClick={selectAll}>
                Select All ({filteredSources.length})
              </Button>
              <Button variant="outline" size="sm" onClick={selectNone}>
                Select None
              </Button>
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {tempSelected.length} of {sources.length} selected
            </div>
          </div>
        </div>

        {/* Sources List */}
        <div className="flex-1 overflow-y-auto mb-4">
          <div className="space-y-2">
            {filteredSources.map(source => {
              const isSelected = tempSelected.includes(source.id)
              const stateCode = category === 'State AG Sites' ? getStateFromName(source.name) : ''
              
              return (
                <div
                  key={source.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700'
                  }`}
                  onClick={() => toggleSource(source.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                        isSelected 
                          ? 'border-blue-500 bg-blue-500' 
                          : 'border-gray-300 dark:border-gray-600'
                      }`}>
                        {isSelected && <svg className="w-3 h-3 text-white" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 111.4-1.4l3.8 3.8 6.8-6.8a1 1 0 011.4 0z" clipRule="evenodd" /></svg>}
                      </div>
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white">
                          {source.name}
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          ID: {source.id} • Type: {source.originalType} • {source.itemCount} {source.itemType}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {stateCode && (
                        <Badge variant="secondary" className="text-xs">
                          {stateCode}
                        </Badge>
                      )}
                      <Badge
                        variant={source.itemCount > 0 ? "default" : "secondary"}
                        className={`text-xs ${source.itemCount > 0 ? getBadgeColor(source.itemType) : 'bg-gray-100 text-gray-600'}`}
                      >
                        {source.itemCount} {source.itemType}
                      </Badge>
                      {isSelected && (
                        <Badge variant="default" className="text-xs bg-green-100 text-green-800">
                           Selected
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          
          {filteredSources.length === 0 && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              {searchTerm ? 'No sources match your search.' : 'No sources available.'}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {tempSelected.length} source{tempSelected.length !== 1 ? 's' : ''} selected
          </div>
          <div className="flex space-x-3">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={applySelection}>
              Apply Selection
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

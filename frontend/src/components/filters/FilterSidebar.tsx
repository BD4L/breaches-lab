import React, { useState, useEffect, useRef, useCallback } from 'react'
import { X, Filter, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { DateRangePicker } from './DateRangePicker'
import { NumericSlider } from './NumericSlider'
import { getSourcesByCategory, supabase } from '../../lib/supabase'
import type { ViewType } from '../dashboard/ViewToggle'

// Move SectionHeader outside to prevent remounting
const SectionHeader = ({
  title,
  section,
  children,
  expandedSections,
  onToggle
}: {
  title: string
  section: string
  children: React.ReactNode
  expandedSections: Record<string, boolean>
  onToggle: (section: string) => void
}) => (
  <div className="space-y-3">
    <button
      onClick={() => onToggle(section)}
      className="flex items-center justify-between w-full text-left"
    >
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">{title}</h3>
      {expandedSections[section] ? (
        <ChevronDown className="w-4 h-4 text-gray-400" />
      ) : (
        <ChevronRight className="w-4 h-4 text-gray-400" />
      )}
    </button>
    {expandedSections[section] && <div className="space-y-3">{children}</div>}
  </div>
)

interface FilterSidebarProps {
  isOpen: boolean
  onClose: () => void
  currentView: ViewType
  onFiltersChange: (filters: {
    search: string
    sourceTypes: string[]
    selectedSources: number[]
    minAffected: number
    affectedKnown?: boolean
    noticesSent?: boolean
    scrapedDateRange: { start?: string; end?: string }
    breachDateRange: { start?: string; end?: string }
    publicationDateRange: { start?: string; end?: string }
  }) => void
}

export function FilterSidebar({ isOpen, onClose, currentView, onFiltersChange }: FilterSidebarProps) {
  const [search, setSearch] = useState('')
  const [sourceTypes, setSourceTypes] = useState<string[]>([])
  const [selectedSources, setSelectedSources] = useState<number[]>([])
  const [minAffected, setMinAffected] = useState(0)
  const [affectedKnown, setAffectedKnown] = useState<boolean | undefined>(undefined)
  const [noticesSent, setNoticesSent] = useState<boolean | undefined>(undefined)
  const [scrapedDateRange, setScrapedDateRange] = useState<{ start?: string; end?: string }>({})
  const [breachDateRange, setBreachDateRange] = useState<{ start?: string; end?: string }>({})
  const [publicationDateRange, setPublicationDateRange] = useState<{ start?: string; end?: string }>({})

  // Use refs to prevent re-renders during typing
  const searchTimeoutRef = useRef<NodeJS.Timeout>()
  const lastSearchRef = useRef('')

  // Collapsible sections
  const [expandedSections, setExpandedSections] = useState({
    search: true,
    dates: true,
    sources: true,
    affected: currentView === 'breaches'
  })

  // Source categories (without counts)
  const [sourcesByCategory, setSourcesByCategory] = useState<Record<string, Array<{id: number, name: string, itemType: string}>>>({})
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({})

  useEffect(() => {
    loadSourcesByCategory()
  }, [currentView])

  // Handle search input with debouncing
  const handleSearchChange = (value: string) => {
    setSearch(value)

    // Clear existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    // Set new timeout for search
    searchTimeoutRef.current = setTimeout(() => {
      if (lastSearchRef.current !== value) {
        lastSearchRef.current = value
        onFiltersChange({
          search: value,
          sourceTypes,
          selectedSources,
          minAffected,
          affectedKnown,
          noticesSent,
          scrapedDateRange,
          breachDateRange,
          publicationDateRange
        })
      }
    }, 500) // Increased debounce time
  }

  // Update filters immediately for non-search changes
  const updateFiltersImmediate = useCallback(() => {
    onFiltersChange({
      search: lastSearchRef.current || search,
      sourceTypes,
      selectedSources,
      minAffected,
      affectedKnown,
      noticesSent,
      scrapedDateRange,
      breachDateRange,
      publicationDateRange
    })
  }, [onFiltersChange, search, sourceTypes, selectedSources, minAffected, affectedKnown, noticesSent, scrapedDateRange, breachDateRange, publicationDateRange])

  // Only update filters when specific filter values change (not on every render)
  useEffect(() => {
    // Only call if we have actual filter values to avoid initial empty calls
    if (sourceTypes.length > 0 || selectedSources.length > 0 || minAffected > 0 || affectedKnown !== undefined || noticesSent !== undefined ||
        Object.keys(scrapedDateRange).length > 0 || Object.keys(breachDateRange).length > 0 ||
        Object.keys(publicationDateRange).length > 0) {
      updateFiltersImmediate()
    }
  }, [sourceTypes, selectedSources, minAffected, affectedKnown, noticesSent, scrapedDateRange, breachDateRange, publicationDateRange])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [])



  const loadSourcesByCategory = async () => {
    try {
      const sourcesByCategory = await getSourcesByCategory()

      // Filter categories based on current view and remove itemCount
      const filteredCategories: Record<string, Array<{id: number, name: string, itemType: string}>> = {}

      Object.entries(sourcesByCategory).forEach(([category, sources]) => {
        const isNewsCategory = ['RSS News Feeds', 'Company IR Sites'].includes(category)

        if (currentView === 'breaches' && !isNewsCategory) {
          // Remove itemCount from sources
          filteredCategories[category] = sources.map(({ id, name, itemType }) => ({ id, name, itemType }))
        } else if (currentView === 'news' && isNewsCategory) {
          // Remove itemCount from sources
          filteredCategories[category] = sources.map(({ id, name, itemType }) => ({ id, name, itemType }))
        }
      })

      setSourcesByCategory(filteredCategories)
    } catch (error) {
      console.error('Failed to load sources by category:', error)
    }
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section as keyof typeof prev]
    }))
  }

  const clearAllFilters = () => {
    setSearch('')
    setSourceTypes([])
    setSelectedSources([])
    setMinAffected(0)
    setAffectedKnown(undefined)
    setNoticesSent(undefined)
    setScrapedDateRange({})
    setBreachDateRange({})
    setPublicationDateRange({})

    // Clear the search ref and immediately update filters
    lastSearchRef.current = ''
    onFiltersChange({
      search: '',
      sourceTypes: [],
      selectedSources: [],
      minAffected: 0,
      affectedKnown: undefined,
      noticesSent: undefined,
      scrapedDateRange: {},
      breachDateRange: {},
      publicationDateRange: {}
    })
  }

  const applyBreachesOfTheDayFilter = async () => {
    try {
      // Get all State AG sources and HHS OCR portal
      const { data: sources } = await supabase
        .from('data_sources')
        .select('id, name, type')
        .or('type.eq.State AG,type.eq.State Cybersecurity,type.eq.State Agency,name.ilike.%HHS OCR%')

      const sourceIds = sources?.map(s => s.id) || []

      console.log('Breaches of the Day sources found:', sources?.map(s => ({ id: s.id, name: s.name, type: s.type })))

      // Get last 24 hours range (more accurate for frequent scraping)
      const now = new Date()
      const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000)

      // Format dates for date picker (YYYY-MM-DD format) - use local timezone
      const formatDateForPicker = (date: Date) => {
        const year = date.getFullYear()
        const month = String(date.getMonth() + 1).padStart(2, '0')
        const day = String(date.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
      }

      const last24HoursStart = formatDateForPicker(last24Hours)
      const nowEnd = formatDateForPicker(now)

      console.log('Setting Breaches Of The Day filter with dates:', {
        last24HoursStart,
        nowEnd,
        affectedKnown: true
      })

      // Set the predefined filter
      setSourceTypes(['State AG Sites', 'Government Portals'])
      setSelectedSources(sourceIds)
      setAffectedKnown(true) // Only known affected counts
      setNoticesSent(undefined) // Reset notices filter
      setScrapedDateRange({ start: last24HoursStart, end: nowEnd }) // Last 24 hours
      setBreachDateRange({})
      setPublicationDateRange({})
      setMinAffected(0)
      setSearch('')

      // Clear search ref and apply filters immediately
      lastSearchRef.current = ''
      const filterConfig = {
        search: '',
        sourceTypes: ['State AG Sites', 'Government Portals'],
        selectedSources: sourceIds,
        minAffected: 0,
        affectedKnown: true,
        noticesSent: undefined,
        scrapedDateRange: { start: last24HoursStart, end: nowEnd },
        breachDateRange: {},
        publicationDateRange: {}
      }

      console.log('Applying Breaches Of The Day filter:', filterConfig)
      onFiltersChange(filterConfig)
    } catch (error) {
      console.error('Failed to apply Breaches of the Day filter:', error)
    }
  }

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }))
  }

  const toggleCategorySelection = (category: string) => {
    const categorySourceIds = sourcesByCategory[category]?.map(source => source.id) || []
    const allSelected = categorySourceIds.every(id => selectedSources.includes(id))

    if (allSelected) {
      // Deselect all sources in this category
      setSelectedSources(prev => prev.filter(id => !categorySourceIds.includes(id)))
    } else {
      // Select all sources in this category
      setSelectedSources(prev => [...new Set([...prev, ...categorySourceIds])])
    }
  }

  const toggleSourceSelection = (sourceId: number) => {
    setSelectedSources(prev =>
      prev.includes(sourceId)
        ? prev.filter(id => id !== sourceId)
        : [...prev, sourceId]
    )
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



  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 lg:hidden"
          onClick={onClose}
          style={{ zIndex: 40 }}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed lg:static inset-y-0 left-0 w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700
          transform transition-transform duration-300 ease-in-out lg:transform-none
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col h-full shadow-2xl lg:shadow-none
        `}
        style={{ zIndex: 45 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <Filter className="w-5 h-5 mr-2" />
            Filters
          </h2>
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAllFilters}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Clear All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="lg:hidden p-1"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* Predefined Filters - Only for breach view */}
        {currentView === 'breaches' && (
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Quick Filters</h3>
            <Button
              onClick={applyBreachesOfTheDayFilter}
              className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium py-2 px-4 rounded-lg shadow-sm transition-all duration-200 flex items-center justify-center space-x-2"
            >
              <span className="text-lg"></span>
              <span>Breaches Of The Day</span>
            </Button>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
              Last 24 hours: State AGs + HHS OCR Portal breaches with known affected counts
            </p>
          </div>
        )}

        {/* Filter Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Search */}
          <SectionHeader
            title="Search"
            section="search"
            expandedSections={expandedSections}
            onToggle={toggleSection}
          >
            <Input
              type="text"
              placeholder={currentView === 'breaches'
                ? "Search organizations, data types..."
                : "Search articles, content..."
              }
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </SectionHeader>

          {/* Date Filters */}
          <SectionHeader
            title="Date Ranges"
            section="dates"
            expandedSections={expandedSections}
            onToggle={toggleSection}
          >
            <DateRangePicker
              label="Scraped Date"
              value={scrapedDateRange}
              onChange={setScrapedDateRange}
            />

            {currentView === 'breaches' && (
              <DateRangePicker
                label="Breach Date"
                value={breachDateRange}
                onChange={setBreachDateRange}
              />
            )}

            <DateRangePicker
              label="Publication Date"
              value={publicationDateRange}
              onChange={setPublicationDateRange}
            />
          </SectionHeader>

          {/* Affected Individuals - Only for breach view */}
          {currentView === 'breaches' && (
            <SectionHeader
              title="People Affected"
              section="affected"
              expandedSections={expandedSections}
              onToggle={toggleSection}
            >
              {/* Enhanced Affected People Filter */}
              <div className="space-y-4">
                {/* Alert Threshold Info */}
                {minAffected > 0 && (
                  <div className="p-3 bg-gradient-to-r from-orange-50 to-red-50 dark:from-orange-900/20 dark:to-red-900/20 border border-orange-200 dark:border-orange-800 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg"></span>
                      <div>
                        <p className="text-sm font-medium text-orange-800 dark:text-orange-200">
                          Alert Threshold Set
                        </p>
                        <p className="text-xs text-orange-600 dark:text-orange-300">
                          Showing breaches affecting {minAffected.toLocaleString()}+ people
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Numeric Slider */}
                <NumericSlider
                  label="Minimum Affected People"
                  value={minAffected}
                  onChange={setMinAffected}
                  min={0}
                  max={1000000}
                  step={100}
                  formatValue={(val) => {
                    if (val === 0) return 'Any'
                    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
                    if (val >= 1000) return `${(val / 1000).toFixed(0)}K`
                    return val.toLocaleString()
                  }}
                />



                {/* Affected Count Known Filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Data Availability
                  </label>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2 cursor-pointer group">
                      <input
                        type="radio"
                        name="affectedKnown"
                        checked={affectedKnown === undefined}
                        onChange={() => setAffectedKnown(undefined)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
                        All records
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        (includes unknown counts)
                      </span>
                    </label>
                    <label className="flex items-center space-x-2 cursor-pointer group">
                      <input
                        type="radio"
                        name="affectedKnown"
                        checked={affectedKnown === true}
                        onChange={() => setAffectedKnown(true)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
                        Count known
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        (specific numbers only)
                      </span>
                    </label>
                    <label className="flex items-center space-x-2 cursor-pointer group">
                      <input
                        type="radio"
                        name="affectedKnown"
                        checked={affectedKnown === false}
                        onChange={() => setAffectedKnown(false)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
                        Count unknown
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        (TBD, under investigation)
                      </span>
                    </label>
                  </div>
                </div>

                {/* Victim Notices Filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Victim Notifications
                  </label>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2 cursor-pointer group">
                      <input
                        type="radio"
                        name="noticesSent"
                        checked={noticesSent === undefined}
                        onChange={() => setNoticesSent(undefined)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
                        All records
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        (with and without notices)
                      </span>
                    </label>
                    <label className="flex items-center space-x-2 cursor-pointer group">
                      <input
                        type="radio"
                        name="noticesSent"
                        checked={noticesSent === true}
                        onChange={() => setNoticesSent(true)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
                        Notices sent
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        (victims have been notified)
                      </span>
                    </label>
                    <label className="flex items-center space-x-2 cursor-pointer group">
                      <input
                        type="radio"
                        name="noticesSent"
                        checked={noticesSent === false}
                        onChange={() => setNoticesSent(false)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
                        No notices sent
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        (victims not yet notified)
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            </SectionHeader>
          )}

          {/* Source Categories */}
          <SectionHeader
            title="Source Categories"
            section="sources"
            expandedSections={expandedSections}
            onToggle={toggleSection}
          >
            <div className="space-y-2">
              {Object.entries(sourcesByCategory).map(([category, sources]) => {
                const isExpanded = expandedCategories[category]
                const categorySourceIds = sources.map(source => source.id)
                const selectedInCategory = categorySourceIds.filter(id => selectedSources.includes(id))

                return (
                  <div key={category} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                    {/* Category Header */}
                    <div className="p-3">
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => toggleCategory(category)}
                          className="flex items-center space-x-2 flex-1 text-left hover:bg-gray-50 dark:hover:bg-gray-700 p-1 rounded"
                        >
                          <span className="text-lg">{getCategoryIcon(category)}</span>
                          <div className="flex-1">
                            <div className="font-medium text-gray-900 dark:text-white text-sm">
                              {category}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              {sources.length} sources
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            {selectedInCategory.length > 0 && (
                              <Badge variant="secondary" className="text-xs">
                                {selectedInCategory.length} selected
                              </Badge>
                            )}
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-gray-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-gray-400" />
                            )}
                          </div>
                        </button>

                        {/* Category Select All/None */}
                        <button
                          onClick={() => toggleCategorySelection(category)}
                          className="ml-2 px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
                        >
                          {selectedInCategory.length === categorySourceIds.length ? 'None' : 'All'}
                        </button>
                      </div>
                    </div>

                    {/* Expanded Sources */}
                    {isExpanded && (
                      <div className="border-t border-gray-200 dark:border-gray-700 p-3 space-y-2">
                        {sources.map(source => {
                          const isSelected = selectedSources.includes(source.id)

                          return (
                            <div
                              key={source.id}
                              className={`flex items-center justify-between p-2 rounded cursor-pointer transition-colors ${
                                isSelected
                                  ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                                  : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                              }`}
                              onClick={() => toggleSourceSelection(source.id)}
                            >
                              <div className="flex items-center space-x-2">
                                <div className={`w-3 h-3 rounded border flex items-center justify-center ${
                                  isSelected
                                    ? 'border-blue-500 bg-blue-500'
                                    : 'border-gray-300 dark:border-gray-600'
                                }`}>
                                  {isSelected && <span className="text-white text-xs"></span>}
                                </div>
                                <span className="text-sm text-gray-900 dark:text-white">
                                  {source.name}
                                </span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </SectionHeader>
        </div>
      </div>
    </>
  )
}

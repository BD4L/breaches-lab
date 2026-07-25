import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ExpandedState,
} from '@tanstack/react-table'
import { getBreaches, saveBreach, checkIfBreachSaved, removeSavedBreach, type BreachRecord } from '../../lib/supabase'
import { formatDate, formatAffectedCount, getSourceTypeColor, getSeverityColor, truncateText } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { BreachDetail } from '../breach/BreachDetail'
import { SaveBreachButton, type SaveBreachData } from '../saved/SaveBreachButton'
import { AIReportButton } from '../ai/AIReportButton'

interface BreachTableProps {
  filters: {
    search: string
    sourceTypes: string[]
    selectedSources: number[]
    minAffected: number
    affectedKnown?: boolean
    noticesSent?: boolean
    scrapedDateRange: string
    breachDateRange: string
    publicationDateRange: string
  }
  onSavedCountChange?: (count: number) => void
}

export function BreachTable({ filters, onSavedCountChange }: BreachTableProps) {
  const [data, setData] = useState<BreachRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'publication_date', desc: true }
  ])
  const [expanded, setExpanded] = useState<ExpandedState>({})
  const [totalCount, setTotalCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 50

  // Add debouncing to prevent excessive API calls
  const [debouncedFilters, setDebouncedFilters] = useState(filters)
  const debounceTimeoutRef = useRef<NodeJS.Timeout>()

  // Track saved breaches
  const [savedBreaches, setSavedBreaches] = useState<Record<number, any>>({})

  // Update saved count when savedBreaches changes
  useEffect(() => {
    const savedCount = Object.keys(savedBreaches).length
    if (onSavedCountChange) {
      onSavedCountChange(savedCount)
    }
  }, [savedBreaches, onSavedCountChange])

  // Load saved breach status for current data
  useEffect(() => {
    const loadSavedStatus = async () => {
      console.log('Loading saved status for', data.length,'breaches')
      const savedStatus: Record<number, any> = {}
      for (const breach of data) {
        try {
          const result = await checkIfBreachSaved(breach.id)
          if (result.data && !result.error) {
            console.log('Found saved breach:', breach.id, result.data)
            savedStatus[breach.id] = {
              id: result.data.id, // This is the saved_breaches.id
              collection_name: result.data.collection_name,
              priority_level: result.data.priority_level,
              review_status: result.data.review_status
            }
          }
        } catch (error) {
          console.error('Error checking saved status for breach', breach.id, error)
        }
      }
      console.log('Final saved status:', savedStatus)
      setSavedBreaches(savedStatus)
    }

    if (data.length > 0) {
      loadSavedStatus()
    }
  }, [data])

  const handleSaveBreach = async (breachId: number, saveData: SaveBreachData) => {
    try {
      // Check if already saved to prevent duplicates
      if (savedBreaches[breachId]) {
        console.warn('Breach already saved:', breachId)
        return
      }

      console.log('Handling save breach:', breachId, saveData)
      const result = await saveBreach(breachId, saveData)
      if (result.data && result.data[0]) {
        // Immediately update local state to show saved status
        setSavedBreaches(prev => ({
          ...prev,
          [breachId]: {
            id: result.data[0].id, // This is the saved_breaches.id
            collection_name: saveData.collection_name,
            priority_level: saveData.priority_level,
            review_status: saveData.review_status
          }
        }))
        console.log('Successfully saved and updated local state')
      } else if (result.error) {
        console.error('Supabase error:', result.error)
        throw new Error(result.error.message || 'Failed to save breach')
      }
    } catch (error) {
      console.error('Failed to save breach:', error)
      throw error
    }
  }

  const handleRemoveSavedBreach = async (breachId: number) => {
    try {
      console.log('Handling remove saved breach:', breachId)
      const savedData = savedBreaches[breachId]
      console.log('Saved data for removal:', savedData)

      if (savedData?.id) {
        const result = await removeSavedBreach(savedData.id)
        if (result.error) {
          console.error('Supabase error:', result.error)
          throw new Error(result.error.message || 'Failed to remove saved breach')
        }

        // Immediately update local state to show unsaved status
        setSavedBreaches(prev => {
          const newState = { ...prev }
          delete newState[breachId]
          return newState
        })
        console.log('Successfully removed and updated local state')
      } else {
        console.warn('No saved data found for breach:', breachId)
        throw new Error('No saved data found for this breach')
      }
    } catch (error) {
      console.error('Failed to remove saved breach:', error)
      throw error
    }
  }

  const columns = useMemo<ColumnDef<BreachRecord>[]>(
    () => [
      {
        id: 'expander',
        header: '',
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="sm"
            onClick={row.getToggleExpandedHandler()}
            className="p-1"
          >
            {row.getIsExpanded() ? '▼' : '▶'}
          </Button>
        ),
        size: 40,
      },
      {
        accessorKey: 'organization_name',
        header: 'Organization',
        cell: ({ getValue, row }) => (
          <div className="min-w-0">
            <div className="font-medium text-gray-900 dark:text-white truncate">
              {getValue() as string}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
              {row.original.source_name}
            </div>
          </div>
        ),
        size: 220,
      },
      {
        accessorKey: 'affected_individuals',
        header: 'People Affected',
        cell: ({ getValue }) => {
          const count = getValue() as number | null
          return (
            <div className="text-right">
              <span className={`font-semibold ${getSeverityColor(count)}`}>
                {formatAffectedCount(count)}
              </span>
            </div>
          )
        },
        size: 140,
      },
      {
        accessorKey: 'source_type',
        header: 'Source Type',
        cell: ({ getValue }) => (
          <Badge className={getSourceTypeColor(getValue() as string)}>
            {getValue() as string}
          </Badge>
        ),
        size: 120,
      },
      {
        accessorKey: 'breach_date',
        header: 'Breach Date',
        cell: ({ getValue }) => (
          <span className="text-sm">
            {formatDate(getValue() as string)}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: 'publication_date',
        header: 'Published',
        cell: ({ getValue }) => (
          <span className="text-sm">
            {formatDate(getValue() as string)}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: 'scraped_at',
        header: 'Discovered',
        cell: ({ getValue }) => (
          <span className="text-sm text-blue-600 dark:text-blue-400">
            {formatDate(getValue() as string)}
          </span>
        ),
        size: 120,
      },
      {
        accessorKey: 'what_was_leaked',
        header: 'Data Compromised',
        cell: ({ getValue }) => (
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {truncateText(getValue() as string, 80)}
          </span>
        ),
        size: 200,
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex flex-col space-y-2">
            <div className="flex space-x-2">
              {row.original.notice_document_url && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(row.original.notice_document_url!, '_blank')}
                >

                </Button>
              )}
              {row.original.item_url && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(row.original.item_url!, '_blank')}
                >

                </Button>
              )}
            </div>

            {/* AI Report Button */}
            <AIReportButton
              breach={row.original}
              className="w-full"
            />

            {/* Save Breach Button */}
            <SaveBreachButton
              key={`save-${row.original.id}-${!!savedBreaches[row.original.id]}`}
              breach={row.original}
              isSaved={!!savedBreaches[row.original.id]}
              savedData={savedBreaches[row.original.id]}
              onSave={handleSaveBreach}
              onRemove={handleRemoveSavedBreach}
              className="w-full"
            />
          </div>
        ),
        size: 200,
      },
    ],
    [savedBreaches, handleSaveBreach, handleRemoveSavedBreach]
  )

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      expanded,
    },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getRowCanExpand: () => true,
  })

  // Debounce filter changes to prevent excessive API calls
  useEffect(() => {
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current)
    }

    debounceTimeoutRef.current = setTimeout(() => {
      setDebouncedFilters(filters)
    }, 300)

    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current)
      }
    }
  }, [filters])

  // Auto-sort by affected individuals when "Breaches Of The Day" filter is active
  useEffect(() => {
    // Check if this looks like the "Breaches Of The Day" filter
    const isBreachesOfTheDayFilter =
      filters.affectedKnown === true &&
      filters.sourceTypes.includes('State AG Sites') &&
      filters.sourceTypes.includes('Government Portals') &&
      (filters.scrapedDateRange.start && filters.scrapedDateRange.end)

    if (isBreachesOfTheDayFilter) {
      // Auto-sort by affected individuals (descending) to show most impactful breaches first
      setSorting([{ id: 'affected_individuals', desc: true }])
    }
  }, [filters.affectedKnown, filters.sourceTypes, filters.scrapedDateRange])

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      setError(null)

      console.log('Loading breach data with parameters:', {
        currentPage,
        pageSize,
        filters: debouncedFilters,
        sorting
      })

      try {
        const sortBy = sorting[0]?.id || 'publication_date'
        const sortOrder = sorting[0]?.desc ? 'desc' : 'asc'

        const queryParams = {
          page: currentPage,
          limit: pageSize,
          sourceTypes: debouncedFilters.sourceTypes,
          selectedSources: debouncedFilters.selectedSources,
          minAffected: debouncedFilters.minAffected,
          affectedKnown: debouncedFilters.affectedKnown,
          noticesSent: debouncedFilters.noticesSent,
          search: debouncedFilters.search,
          sortBy,
          sortOrder,
          scrapedDateRange: debouncedFilters.scrapedDateRange,
          breachDateRange: debouncedFilters.breachDateRange,
          publicationDateRange: debouncedFilters.publicationDateRange,
        }

        console.log('Query parameters:', queryParams)

        const result = await getBreaches(queryParams)
        console.log('Supabase query result:', result)

        const { data: breaches, error, count } = result

        if (error) {
          console.error('Supabase error:', error)
          throw error
        }

        console.log('Successfully loaded breaches:', {
          breachCount: breaches?.length || 0,
          totalCount: count,
          firstBreach: breaches?.[0]?.organization_name || 'None'
        })

        setData(breaches || [])
        setTotalCount(count || 0)
      } catch (err) {
        console.error('Error loading breach data:', err)
        setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [debouncedFilters, sorting, currentPage])

  const totalPages = Math.ceil(totalCount / pageSize)

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="p-6">
          <div className="animate-pulse space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-red-200 dark:border-red-700 p-6">
        <div className="text-red-600 dark:text-red-400">
          <h3 className="font-medium">Error loading breach data</h3>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Breach Records
          </h2>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {totalCount.toLocaleString()} total records
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={
                          header.column.getCanSort()
                            ? 'cursor-pointer select-none flex items-center space-x-1'
                            : ''
                        }
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{
                          asc:'',
                          desc:'',
                        }[header.column.getIsSorted() as string] ?? null}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {table.getRowModel().rows.map(row => (
              <React.Fragment key={row.id}>
                <tr className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  {row.getVisibleCells().map(cell => (
                    <td
                      key={cell.id}
                      className="px-6 py-4 whitespace-nowrap"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {row.getIsExpanded() && (
                  <tr>
                    <td colSpan={columns.length} className="px-6 py-4 bg-gray-50 dark:bg-gray-700">
                      <BreachDetail breach={row.original} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              Showing {currentPage * pageSize + 1} to {Math.min((currentPage + 1) * pageSize, totalCount)} of {totalCount} results
            </div>
            <div className="flex space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(0, prev - 1))}
                disabled={currentPage === 0}
              >
                Previous
              </Button>
              <span className="flex items-center px-3 py-1 text-sm">
                Page {currentPage + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages - 1, prev + 1))}
                disabled={currentPage >= totalPages - 1}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

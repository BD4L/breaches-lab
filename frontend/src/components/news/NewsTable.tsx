import React, { useState, useEffect, useMemo } from 'react'
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
import { getNewsArticles, type NewsArticle } from '../../lib/supabase'
import { formatDate, getSourceTypeColor, truncateText } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface NewsTableProps {
  filters: {
    search: string
    selectedSources: number[]
    scrapedDateRange: string
    publicationDateRange: string
  }
}

export function NewsTable({ filters }: NewsTableProps) {
  const [data, setData] = useState<NewsArticle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(0)
  const [sorting, setSorting] = useState<SortingState>([{ id: 'publication_date', desc: true }])
  const [expanded, setExpanded] = useState<ExpandedState>({})

  const pageSize = 25

  const columns = useMemo<ColumnDef<NewsArticle>[]>(() => [
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
          {row.getIsExpanded() ?'':''}
        </Button>
      ),
      size: 40,
    },
    {
      accessorKey: 'organization_name',
      header: 'Article Title',
      cell: ({ row }) => (
        <div className="space-y-1">
          <div className="font-medium text-gray-900 dark:text-white">
            {row.original.item_url ? (
              <a
                href={row.original.item_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-blue-600 dark:hover:text-blue-400 hover:underline"
              >
                {truncateText(row.original.organization_name, 80)}
              </a>
            ) : (
              truncateText(row.original.organization_name, 80)
            )}
          </div>
          {row.original.summary_text && (
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {truncateText(row.original.summary_text, 120)}
            </div>
          )}
        </div>
      ),
      size: 400,
    },
    {
      accessorKey: 'source_name',
      header: 'Source',
      cell: ({ row }) => (
        <div className="space-y-1">
          <Badge className={getSourceTypeColor(row.original.source_type)}>
            {row.original.source_name}
          </Badge>
          {row.original.tags_keywords && row.original.tags_keywords.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {row.original.tags_keywords.slice(0, 3).map((tag, index) => (
                <Badge key={index} variant="outline" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {row.original.tags_keywords.length > 3 && (
                <Badge variant="outline" className="text-xs">
                  +{row.original.tags_keywords.length - 3}
                </Badge>
              )}
            </div>
          )}
        </div>
      ),
      size: 200,
    },
    {
      accessorKey: 'publication_date',
      header: 'Published',
      cell: ({ row }) => (
        <div className="text-sm">
          <div className="font-medium text-gray-900 dark:text-white">
            {formatDate(row.original.publication_date)}
          </div>
          <div className="text-gray-500 dark:text-gray-400">
            Scraped: {formatDate(row.original.scraped_at)}
          </div>
        </div>
      ),
      size: 150,
    },
  ], [])

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
    manualSorting: true,
    manualPagination: true,
  })

  // Load data when filters or sorting change
  useEffect(() => {
    loadData()
  }, [filters, currentPage, sorting])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const sortBy = sorting[0]?.id || 'publication_date'
      const sortOrder = sorting[0]?.desc ? 'desc' : 'asc'

      const queryParams = {
        page: currentPage,
        limit: pageSize,
        selectedSources: filters.selectedSources,
        search: filters.search,
        sortBy,
        sortOrder,
        scrapedDateRange: filters.scrapedDateRange,
        publicationDateRange: filters.publicationDateRange,
      }

      console.log('Loading news articles with params:', queryParams)

      const result = await getNewsArticles(queryParams)
      const { data: articles, error, count } = result

      if (error) {
        console.error('Error loading news articles:', error)
        console.error('Error details:', JSON.stringify(error, null, 2))
        throw error
      }

      console.log('Loaded news articles:', articles?.length || 0,'Total:', count)

      setData(articles || [])
      setTotalCount(count || 0)
    } catch (err) {
      console.error('Failed to load news articles:', err)
      setError(err instanceof Error ? err.message : 'Failed to load news articles')
    } finally {
      setLoading(false)
    }
  }

  const totalPages = Math.ceil(totalCount / pageSize)

  if (loading && data.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading news articles...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
        <div className="flex items-center">
          <span className="text-red-500 mr-2"></span>
          <div>
            <h3 className="text-red-800 dark:text-red-200 font-medium">Error Loading News</h3>
            <p className="text-red-600 dark:text-red-300 text-sm mt-1">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Results Summary */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600 dark:text-gray-400">
          Showing {data.length} of {totalCount.toLocaleString()} news articles
          {filters.search && ` matching "${filters.search}"`}
        </div>
        {loading && (
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span>Updating...</span>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              {table.getHeaderGroups().map(headerGroup => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map(header => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600"
                      style={{ width: header.getSize() }}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <div className="flex items-center space-x-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() && (
                          <span className="text-blue-600 dark:text-blue-400">
                            {header.column.getIsSorted() ==='desc'?'':''}
                          </span>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {table.getRowModel().rows.map(row => (
                <React.Fragment key={row.id}>
                  <tr className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="px-4 py-4 whitespace-nowrap">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                  {row.getIsExpanded() && (
                    <tr>
                      <td colSpan={columns.length} className="px-4 py-4 bg-gray-50 dark:bg-gray-700/50">
                        <div className="space-y-3">
                          {row.original.summary_text && (
                            <div>
                              <h4 className="font-medium text-gray-900 dark:text-white mb-2">Full Summary</h4>
                              <div className="text-sm text-gray-700 dark:text-gray-300 max-h-40 overflow-y-auto">
                                {row.original.summary_text}
                              </div>
                            </div>
                          )}
                          <div className="flex items-center space-x-4 text-xs text-gray-500 dark:text-gray-400">
                            <span>Article ID: {row.original.id}</span>
                            <span>Source ID: {row.original.source_id}</span>
                            {row.original.item_url && (
                              <a
                                href={row.original.item_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 dark:text-blue-400 hover:underline"
                              >
                                View Original
                              </a>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Page {currentPage + 1} of {totalPages}
          </div>
          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(0)}
              disabled={currentPage === 0}
            >
              First
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(currentPage - 1)}
              disabled={currentPage === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={currentPage >= totalPages - 1}
            >
              Next
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(totalPages - 1)}
              disabled={currentPage >= totalPages - 1}
            >
              Last
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

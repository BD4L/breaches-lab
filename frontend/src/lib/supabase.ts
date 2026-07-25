import { createClient } from '@supabase/supabase-js'

// Get Supabase configuration from environment variables
const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL
const supabaseAnonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY

// Fallback configuration for development/demo purposes
// In production, these should be set via GitHub Secrets
const fallbackConfig = {
  url: 'https://hilbbjnnxkitxbptektg.supabase.co',
  key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpbGJiam5ueGtpdHhicHRla3RnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxOTYwNDIsImV4cCI6MjA2Mzc3MjA0Mn0.vk8AJ2pofRAy5y26WQeMYgEFudU1plXnYa6sMFyATFM'
}

const finalUrl = supabaseUrl || fallbackConfig.url
const finalKey = supabaseAnonKey || fallbackConfig.key

if (!finalUrl || !finalKey) {
  console.error('Missing Supabase configuration')
  throw new Error('Supabase configuration is required')
}

// Only log in development
if (import.meta.env.MODE === 'development') {
  console.log('Supabase configuration:', {
    url: finalUrl,
    keyLength: finalKey.length,
    environment: import.meta.env.MODE,
    usingFallback: !supabaseUrl || !supabaseAnonKey
  })
}

export const supabase = createClient(finalUrl, finalKey, {
  auth: {
    persistSession: false, // Disable session persistence for static sites
    autoRefreshToken: false, // Disable auto refresh for anonymous usage
  },
  global: {
    headers: {
      'X-Client-Info': 'breach-dashboard@1.0.0',
    },
  },
  functions: {
    region: 'us-east-1', // Match your Supabase region
  }
})

// Centralized source type configuration to ensure consistency across all functions
export const SOURCE_TYPE_CONFIG = {
  // Raw source types to display categories mapping
  CATEGORY_MAPPING: {
    'State AG': 'State AG Sites',
    'Government Portal': 'Government Portals',
    'News Feed': 'RSS News Feeds',
    'Breach Database': 'Specialized Breach Sites',
    'Company IR': 'Company IR Sites',
    'State Cybersecurity': 'State AG Sites', // Group with State AG
    'State Agency': 'State AG Sites' // Group with State AG
  } as Record<string, string>,

  // Source types that are considered breach sources (not news)
  BREACH_SOURCE_TYPES: new Set([
    'State AG',
    'Government Portal',
    'Breach Database',
    'State Cybersecurity',
    'State Agency',
    'API'
  ]),

  // Source types that are considered news sources
  NEWS_SOURCE_TYPES: new Set([
    'News Feed',
    'Company IR'
  ]),

  // Get display category for a source type
  getDisplayCategory: (sourceType: string): string => {
    return SOURCE_TYPE_CONFIG.CATEGORY_MAPPING[sourceType] || sourceType
  },

  // Check if source type is a breach source
  isBreachSource: (sourceType: string): boolean => {
    return SOURCE_TYPE_CONFIG.BREACH_SOURCE_TYPES.has(sourceType)
  },

  // Check if source type is a news source
  isNewsSource: (sourceType: string): boolean => {
    return SOURCE_TYPE_CONFIG.NEWS_SOURCE_TYPES.has(sourceType)
  },

  // Get all breach source types as array
  getBreachSourceTypes: (): string[] => {
    return Array.from(SOURCE_TYPE_CONFIG.BREACH_SOURCE_TYPES)
  },

  // Get all news source types as array
  getNewsSourceTypes: (): string[] => {
    return Array.from(SOURCE_TYPE_CONFIG.NEWS_SOURCE_TYPES)
  }
}

// Helper functions to distinguish between news and breach sources (backward compatibility)
export const isNewsSource = (sourceType: string): boolean => {
  return SOURCE_TYPE_CONFIG.isNewsSource(sourceType)
}

// Types for saved breaches
export interface SavedBreachRecord extends BreachRecord {
  saved_id: number
  collection_name: string
  priority_level: 'low' | 'medium' | 'high' | 'critical'
  notes?: string
  tags?: string[]
  review_status: 'pending' | 'in_progress' | 'reviewed' | 'escalated' | 'closed'
  assigned_to?: string
  due_date?: string
  saved_at: string
  last_updated: string
}

export const isBreachSource = (sourceType: string): boolean => {
  return SOURCE_TYPE_CONFIG.isBreachSource(sourceType)
}

// Database types
export interface BreachRecord {
  id: number
  organization_name: string
  breach_date: string | null
  reported_date: string | null
  affected_individuals: number | null
  what_was_leaked: string | null
  data_types_compromised: string[] | null
  notice_document_url: string | null
  source_id: number
  source_name: string
  source_type: string
  publication_date: string | null
  summary_text: string | null
  tags_keywords: string[] | null
  incident_nature_text: string | null
  incident_discovery_date: string | null
  is_cybersecurity_related: boolean | null
  item_url: string | null
  created_at: string
  scraped_at: string | null
}

export interface NewsArticle {
  id: number
  organization_name: string
  source_id: number
  source_name: string
  source_type: string
  publication_date: string | null
  summary_text: string | null
  item_url: string | null
  tags_keywords: string[] | null
  created_at: string
  scraped_at: string | null
}

export interface DataSource {
  id: number
  name: string
  url: string | null
  type: string | null
  description: string | null
  created_at: string
}

export interface UserPrefs {
  user_id: string
  threshold: number
  sources: string[]
  source_types: string[]
  data_types: string[]
  keywords: string[]
  created_at: string
  updated_at: string
}

export interface ResearchJob {
  id: string
  scraped_item: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  report_url: string | null
  requested_by: string
  created_at: string
  completed_at: string | null
  error_message: string | null
  // Enhanced AI report fields
  report_type?: 'ai_breach_analysis' | 'manual_research' | 'automated_summary'
  markdown_content?: string
  html_content?: string
  processing_time_ms?: number
  cost_estimate?: number
  metadata?: any
  search_results_count?: number
  scraped_urls_count?: number
  ai_model_used?: string
  updated_at?: string
}

export interface AIReportUsage {
  id: string
  user_id: string
  date: string
  report_count: number
  total_cost: number
  total_processing_time_ms: number
  created_at: string
  updated_at: string
}

// API functions
export async function getBreaches(params: {
  page?: number
  limit?: number
  sourceTypes?: string[]
  selectedSources?: number[]
  minAffected?: number
  affectedKnown?: boolean
  noticesSent?: boolean
  search?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  scrapedDateRange?: string
  breachDateRange?: string
  publicationDateRange?: string
} = {}) {
  const {
    page = 0,
    limit = 50,
    sourceTypes = [],
    selectedSources = [],
    minAffected = 0,
    affectedKnown,
    noticesSent,
    search = '',
    sortBy = 'publication_date',
    sortOrder = 'desc',
    scrapedDateRange = '',
    breachDateRange = '',
    publicationDateRange = ''
  } = params

  console.log('getBreaches called with params:', {
    page, limit, sourceTypes, selectedSources, minAffected, affectedKnown, noticesSent,
    search, sortBy, sortOrder, scrapedDateRange, breachDateRange, publicationDateRange
  })

  let query = supabase
    .from('v_breach_dashboard')
    .select('*', { count: 'exact' })

  // Filter to only breach sources (exclude news feeds)
  const breachSourceTypes = SOURCE_TYPE_CONFIG.getBreachSourceTypes()
  query = query.in('source_type', breachSourceTypes)

  // Apply filters
  if (sourceTypes.length > 0) {
    // Map source types to the new categorization for filtering
    const typeMapping: Record<string, string[]> = {
      'State AG Sites': ['State AG', 'State Cybersecurity', 'State Agency'],
      'Government Portals': ['Government Portal'],
      'Specialized Breach Sites': ['Breach Database'],
      'API Services': ['API']
    }

    const mappedTypes: string[] = []
    sourceTypes.forEach(type => {
      if (typeMapping[type]) {
        mappedTypes.push(...typeMapping[type])
      }
    })

    if (mappedTypes.length > 0) {
      // Intersect with breach source types
      const filteredTypes = mappedTypes.filter(type => breachSourceTypes.includes(type))
      if (filteredTypes.length > 0) {
        query = query.in('source_type', filteredTypes)
      }
    }
  }

  // Apply specific source filtering (takes precedence over source types)
  if (selectedSources.length > 0) {
    query = query.in('source_id', selectedSources)
  }

  if (minAffected > 0) {
    query = query.gte('affected_individuals', minAffected)
  }

  // Filter for records where affected individuals count is known/unknown
  if (affectedKnown !== undefined) {
    console.log('Applying affectedKnown filter:', affectedKnown)
    if (affectedKnown) {
      console.log('Filtering for records WITH affected_individuals count')
      query = query.not('affected_individuals', 'is', null)
    } else {
      console.log('Filtering for records WITHOUT affected_individuals count')
      query = query.is('affected_individuals', null)
    }
  }

  // Filter for records where victim notices have been sent
  if (noticesSent !== undefined) {
    console.log('Applying noticesSent filter:', noticesSent)
    if (noticesSent) {
      console.log('Filtering for records WITH notice documents (victims notified)')
      query = query.not('notice_document_url', 'is', null)
    } else {
      console.log('Filtering for records WITHOUT notice documents (victims not notified)')
      query = query.is('notice_document_url', null)
    }
  }

  if (search) {
    query = query.or(`organization_name.ilike.%${search}%,what_was_leaked.ilike.%${search}%`)
  }

  // Apply date filters
  if (scrapedDateRange) {
    const dateFilter = parseDateRange(scrapedDateRange)
    if (dateFilter.start) {
      query = query.gte('scraped_at', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('scraped_at', dateFilter.end)
    }
  }

  if (breachDateRange) {
    const dateFilter = parseDateRange(breachDateRange)
    if (dateFilter.start) {
      query = query.gte('breach_date', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('breach_date', dateFilter.end)
    }
  }

  if (publicationDateRange) {
    const dateFilter = parseDateRange(publicationDateRange)
    if (dateFilter.start) {
      query = query.gte('publication_date', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('publication_date', dateFilter.end)
    }
  }

  // Apply sorting
  query = query.order(sortBy, { ascending: sortOrder === 'asc' })

  // Apply pagination
  const from = page * limit
  const to = from + limit - 1
  query = query.range(from, to)

  return query
}

// Get news articles (RSS feeds, Company IR, etc.)
export async function getNewsArticles(params: {
  page?: number
  limit?: number
  selectedSources?: number[]
  search?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  scrapedDateRange?: string
  publicationDateRange?: string
} = {}) {
  const {
    page = 0,
    limit = 50,
    selectedSources = [],
    search = '',
    sortBy = 'publication_date',
    sortOrder = 'desc',
    scrapedDateRange = '',
    publicationDateRange = ''
  } = params

  console.log('getNewsArticles called with params:', params)

  let query = supabase
    .from('v_breach_dashboard')
    .select('id, organization_name, source_id, source_name, source_type, publication_date, summary_text, item_url, tags_keywords, created_at, scraped_at', { count: 'exact' })

  // Filter to only news sources
  const newsSourceTypes = SOURCE_TYPE_CONFIG.getNewsSourceTypes()
  query = query.in('source_type', newsSourceTypes)

  console.log('Applied news source filter:', newsSourceTypes)

  // Apply specific source filtering
  if (selectedSources.length > 0) {
    query = query.in('source_id', selectedSources)
  }

  if (search) {
    query = query.or(`organization_name.ilike.%${search}%,summary_text.ilike.%${search}%`)
  }

  // Apply date filters
  if (scrapedDateRange) {
    const dateFilter = parseDateRange(scrapedDateRange)
    if (dateFilter.start) {
      query = query.gte('scraped_at', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('scraped_at', dateFilter.end)
    }
  }

  if (publicationDateRange) {
    const dateFilter = parseDateRange(publicationDateRange)
    if (dateFilter.start) {
      query = query.gte('publication_date', dateFilter.start)
    }
    if (dateFilter.end) {
      query = query.lte('publication_date', dateFilter.end)
    }
  }

  // Apply sorting
  query = query.order(sortBy, { ascending: sortOrder === 'asc' })

  // Apply pagination
  const from = page * limit
  const to = from + limit - 1
  query = query.range(from, to)

  console.log('Final query range:', { from, to, page, limit })
  console.log('About to execute news query...')

  return query
}

// Helper function to parse date range strings
function parseDateRange(range: string): { start?: string; end?: string } {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  switch (range) {
    case 'today':
      return {
        start: today.toISOString(),
        end: new Date(today.getTime() + 24 * 60 * 60 * 1000).toISOString()
      }

    case 'yesterday':
      const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
      return {
        start: yesterday.toISOString(),
        end: today.toISOString()
      }

    case 'last-3-days':
      return {
        start: new Date(today.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-week':
    case 'last-7-days':
      return {
        start: new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-2-weeks':
      return {
        start: new Date(today.getTime() - 14 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-month':
    case 'last-30-days':
      return {
        start: new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-3-months':
      return {
        start: new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-6-months':
      return {
        start: new Date(today.getTime() - 180 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'last-year':
      return {
        start: new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000).toISOString(),
        end: now.toISOString()
      }

    case 'all-time':
      return {}

    default:
      // Handle pipe-separated date ranges (format: "YYYY-MM-DD|YYYY-MM-DD")
      if (range.includes('|')) {
        const [startDate, endDate] = range.split('|')
        console.log('Parsing pipe-separated date range:', { startDate, endDate, originalRange: range })

        try {
          const result = {
            start: startDate ? new Date(startDate + 'T00:00:00.000Z').toISOString() : undefined,
            end: endDate ? new Date(endDate + 'T23:59:59.999Z').toISOString() : undefined
          }
          console.log('Parsed date range result:', result)
          return result
        } catch (error) {
          console.error('Error parsing date range:', error)
          return {}
        }
      }

      // Handle custom date ranges (format: custom-type-YYYY-MM-DD)
      if (range.startsWith('custom-')) {
        const parts = range.split('-')
        if (parts.length >= 4) {
          const dateStr = parts.slice(2).join('-')
          try {
            const customDate = new Date(dateStr)
            return {
              start: customDate.toISOString(),
              end: new Date(customDate.getTime() + 24 * 60 * 60 * 1000).toISOString()
            }
          } catch {
            return {}
          }
        }
      }
      return {}
  }
}

export async function getDataSources() {
  return supabase
    .from('data_sources')
    .select('id, name, type')
    .order('name')
}

export async function getSourceTypes() {
  const { data, error } = await supabase
    .from('data_sources')
    .select('type')
    .not('type', 'is', null)

  if (error) throw error

  // Use centralized mapping
  const mappedTypes = data
    .map(item => SOURCE_TYPE_CONFIG.getDisplayCategory(item.type))
    .filter(type => type !== 'API') // Remove API category

  const uniqueTypes = [...new Set(mappedTypes)]
  return uniqueTypes.filter(Boolean)
}

// Get sources by category for hierarchical filtering with proper item counts (fixed v3 - cache bust)
export async function getSourcesByCategory() {
  const { data: sourcesData, error: sourcesError } = await supabase
    .from('data_sources')
    .select('id, name, type')
    .not('type', 'is', null)
    .neq('type', 'API') // Exclude API sources

  if (sourcesError) throw sourcesError

  // Get all items per source with proper categorization
  const { data: allItems, error: itemsError } = await supabase
    .from('v_breach_dashboard')
    .select('source_id, source_name, source_type')
    .limit(10000) // Ensure we get all records, not just first 1000

  if (itemsError) throw itemsError

  // Count items per source, separating breaches from news
  const sourceItemCounts = allItems.reduce((acc, item) => {
    const sourceId = item.source_id
    const isBreachSource = SOURCE_TYPE_CONFIG.isBreachSource(item.source_type)

    if (!acc[sourceId]) {
      acc[sourceId] = { breaches: 0, news: 0, total: 0 }
    }

    acc[sourceId].total++
    if (isBreachSource) {
      acc[sourceId].breaches++
    } else {
      acc[sourceId].news++
    }

    return acc
  }, {} as Record<number, { breaches: number; news: number; total: number }>)

  console.log('getSourcesByCategory v3 - sourceItemCounts sample:', Object.entries(sourceItemCounts).slice(0, 5))
  console.log('Function called at:', new Date().toISOString())

  // Group sources by new categorization
  const categories: Record<string, Array<{id: number, name: string, originalType: string, itemCount: number, itemType: string}>> = {
    'Government Portals': [],
    'State AG Sites': [],
    'RSS News Feeds': [],
    'Specialized Breach Sites': [],
    'Company IR Sites': []
  }

  sourcesData.forEach(source => {
    let category = ''
    let itemType = 'breaches' // Default for breach notification sources
    let itemCount = 0

    switch (source.type) {
      case 'State AG':
      case 'State Cybersecurity':
      case 'State Agency':
        category = 'State AG Sites'
        itemType = 'breaches'
        itemCount = sourceItemCounts[source.id]?.breaches || 0
        break
      case 'Government Portal':
        category = 'Government Portals'
        itemType = 'breaches'
        itemCount = sourceItemCounts[source.id]?.breaches || 0
        break
      case 'News Feed':
        category = 'RSS News Feeds'
        itemType = 'articles'
        itemCount = sourceItemCounts[source.id]?.news || 0
        break
      case 'Breach Database':
        category = 'Specialized Breach Sites'
        itemType = 'breaches'
        itemCount = sourceItemCounts[source.id]?.breaches || 0
        break
      case 'Company IR':
        category = 'Company IR Sites'
        itemType = 'reports'
        itemCount = sourceItemCounts[source.id]?.news || 0
        break
      default:
        return // Skip API and unknown types
    }

    if (categories[category]) {
      categories[category].push({
        id: source.id,
        name: source.name,
        originalType: source.type,
        itemCount: itemCount,
        itemType: itemType
      })
    }
  })

  // Sort sources within each category by item count (descending), then by name
  Object.keys(categories).forEach(category => {
    categories[category].sort((a, b) => {
      if (b.itemCount !== a.itemCount) {
        return b.itemCount - a.itemCount // Sort by item count first
      }
      return a.name.localeCompare(b.name) // Then by name
    })
  })

  return categories
}

export async function getSourceTypeCounts() {
  const { data, error } = await supabase
    .from('v_breach_dashboard')
    .select('source_type')
    .limit(10000) // Ensure we get all records, not just first 1000

  if (error) throw error

  if (!data || data.length === 0) {
    return {}
  }

  // Simple count of entries by source type
  const rawCounts = data.reduce((acc, item) => {
    acc[item.source_type] = (acc[item.source_type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // Convert raw counts to category counts using centralized mapping
  const categoryCounts: Record<string, number> = {}

  Object.entries(rawCounts).forEach(([sourceType, count]) => {
    const category = SOURCE_TYPE_CONFIG.getDisplayCategory(sourceType)
    if (category && category !== 'API') { // Exclude API category
      categoryCounts[category] = (categoryCounts[category] || 0) + count
    }
  })

  return categoryCounts
}

export async function getDataTypes() {
  const { data, error } = await supabase
    .from('scraped_items')
    .select('data_types_compromised')
    .not('data_types_compromised', 'is', null)

  if (error) throw error

  // Flatten and get unique data types
  const allTypes = data.flatMap(item => item.data_types_compromised || [])
  return [...new Set(allTypes)].filter(Boolean)
}

// Saved Breaches Functions
export async function saveBreach(breachId: number, data: {
  collection_name: string
  priority_level: 'low' | 'medium' | 'high' | 'critical'
  notes: string
  tags: string[]
  review_status: 'pending' | 'in_progress' | 'reviewed' | 'escalated' | 'closed'
  assigned_to: string
  due_date: string
}) {
  console.log('Saving breach:', { breachId, data })

  // Clean the data to ensure it matches database expectations
  const cleanData = {
    user_id: 'anonymous',
    breach_id: breachId,
    collection_name: data.collection_name || 'Default',
    priority_level: data.priority_level || 'medium',
    notes: data.notes || null,
    tags: data.tags && data.tags.length > 0 ? data.tags : null,
    review_status: data.review_status || 'pending',
    assigned_to: data.assigned_to || null,
    due_date: data.due_date || null
  }

  console.log('Cleaned data:', cleanData)

  const { data: result, error } = await supabase
    .from('saved_breaches')
    .insert(cleanData)
    .select()

  console.log('Save result:', { result, error })
  return { data: result, error }
}

export async function getSavedBreaches(params: {
  collection?: string
  priority?: string
  status?: string
  assignedTo?: string
} = {}) {
  let query = supabase
    .from('v_saved_breaches')
    .select('*')
    .eq('user_id', 'anonymous') // For now, using anonymous user
    .order('saved_at', { ascending: false })

  if (params.collection) {
    query = query.eq('collection_name', params.collection)
  }
  if (params.priority) {
    query = query.eq('priority_level', params.priority)
  }
  if (params.status) {
    query = query.eq('review_status', params.status)
  }
  if (params.assignedTo) {
    query = query.eq('assigned_to', params.assignedTo)
  }

  const { data, error } = await query

  return { data, error }
}

export async function removeSavedBreach(savedId: number) {
  console.log('Removing saved breach:', savedId)

  const { error } = await supabase
    .from('saved_breaches')
    .delete()
    .eq('id', savedId)
    .eq('user_id', 'anonymous') // For now, using anonymous user

  console.log('Remove result:', { error })
  return { error }
}

export async function updateSavedBreach(savedId: number, updates: {
  collection_name?: string
  priority_level?: 'low' | 'medium' | 'high' | 'critical'
  notes?: string
  tags?: string[]
  review_status?: 'pending' | 'in_progress' | 'reviewed' | 'escalated' | 'closed'
  assigned_to?: string
  due_date?: string
}) {
  const { data, error } = await supabase
    .from('saved_breaches')
    .update({
      ...updates,
      updated_at: new Date().toISOString()
    })
    .eq('id', savedId)
    .eq('user_id', 'anonymous') // For now, using anonymous user
    .select()

  return { data, error }
}

export async function checkIfBreachSaved(breachId: number) {
  console.log('Checking if breach is saved:', breachId)

  const { data, error } = await supabase
    .from('saved_breaches')
    .select('id, collection_name, priority_level, review_status')
    .eq('breach_id', breachId)
    .eq('user_id', 'anonymous') // For now, using anonymous user
    .maybeSingle() // Use maybeSingle instead of single to handle no results

  console.log('Check result:', { data, error, breachId })
  return { data, error }
}

// Helper function to get today's 1am timestamp (or yesterday's 1am if before 1am)
function getToday1am(): Date {
  const now = new Date()
  const today1am = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 1, 0, 0, 0)

  // If it's currently before 1am, use yesterday's 1am
  if (now.getHours() < 1) {
    today1am.setDate(today1am.getDate() - 1)
  }

  return today1am
}

export interface DailyStats {
  totalNewItems: number
  newBreaches: number
  newNews: number
  newAffectedTotal: number
  sourceBreakdown: Array<{
    sourceType: string
    sourceName: string
    newItems: number
    newAffected: number
    isBreachSource: boolean
  }>
  topBreaches: Array<{
    id: number
    organizationName: string
    affectedIndividuals: number | null
    sourceName: string
    breachDate: string | null
    reportedDate: string | null
  }>
  timeRange: {
    start: string
    end: string
  }
}

export async function getSourceSummary() {
  try {
    const { data, error } = await supabase
      .from('v_breach_dashboard')
      .select('source_type, source_name, affected_individuals, publication_date')
      .limit(10000) // Ensure we get all records, not just first 1000

    if (error) throw error

    // Use centralized mapping for display categories
    const summary = data.reduce((acc, item) => {
      const mappedType = SOURCE_TYPE_CONFIG.getDisplayCategory(item.source_type)

      if (!acc[mappedType]) {
        acc[mappedType] = {
          count: 0,
          affectedTotal: 0,
          sources: new Set()
        }
      }

      acc[mappedType].count++
      acc[mappedType].sources.add(item.source_name)

      if (item.affected_individuals) {
        acc[mappedType].affectedTotal += item.affected_individuals
      }

      return acc
    }, {} as Record<string, { count: number; affectedTotal: number; sources: Set<string> }>)

    // Convert sets to arrays and add source counts
    const result = Object.entries(summary).map(([type, data]) => ({
      type,
      count: data.count,
      affectedTotal: data.affectedTotal,
      sourceCount: data.sources.size
    }))

    return { data: result, error: null }
  } catch (error) {
    console.error('Error fetching source summary:', error)
    return { data: [], error: error as Error }
  }
}

export async function getDailyStats(): Promise<{ data: DailyStats | null; error: Error | null }> {
  try {
    const startTime = getToday1am()
    const endTime = new Date()

    const startIso = startTime.toISOString()
    const endIso = endTime.toISOString()

    console.log('Getting daily stats from:', startIso,'to:', endIso)

    // Get all daily items for general stats
    const { data, error } = await supabase
      .from('v_breach_dashboard')
      .select('source_type, source_name, affected_individuals')
      .gte('scraped_at', startIso)
      .lt('scraped_at', endIso)
      .limit(10000) // Ensure we get all records, not just first 1000

    if (error) throw error

    // Get top breaches for today (only breach sources with affected individuals data)
    const { data: topBreachesData, error: topBreachesError } = await supabase
      .from('v_breach_dashboard')
      .select('id, organization_name, affected_individuals, source_name, breach_date, reported_date')
      .gte('scraped_at', startIso)
      .lt('scraped_at', endIso)
      .in('source_type', SOURCE_TYPE_CONFIG.getBreachSourceTypes())
      .not('affected_individuals', 'is', null)
      .order('affected_individuals', { ascending: false })
      .limit(3)

    if (topBreachesError) {
      console.warn('Error fetching top breaches:', topBreachesError)
    }

    console.log('Daily stats raw data:', data?.length || 0,'items')
    console.log('Top breaches data:', topBreachesData?.length || 0,'breaches')

    // Categorize sources as breach vs news using centralized config
    let newBreaches = 0
    let newNews = 0
    let newAffectedTotal = 0
    const sourceStats = new Map<string, { newItems: number; newAffected: number; isBreachSource: boolean; sourceType: string }>()

    data.forEach(item => {
      const isBreachSource = SOURCE_TYPE_CONFIG.isBreachSource(item.source_type)
      const key = item.source_name

      if (isBreachSource) {
        newBreaches++
      } else {
        newNews++
      }

      if (item.affected_individuals) {
        newAffectedTotal += item.affected_individuals
      }

      if (!sourceStats.has(key)) {
        sourceStats.set(key, {
          newItems: 0,
          newAffected: 0,
          isBreachSource,
          sourceType: item.source_type
        })
      }

      const stats = sourceStats.get(key)!
      stats.newItems++
      if (item.affected_individuals) {
        stats.newAffected += item.affected_individuals
      }
    })

    const sourceBreakdown = Array.from(sourceStats.entries())
      .map(([sourceName, stats]) => ({
        sourceName,
        sourceType: stats.sourceType,
        newItems: stats.newItems,
        newAffected: stats.newAffected,
        isBreachSource: stats.isBreachSource
      }))
      .sort((a, b) => b.newItems - a.newItems) // Sort by most new items

    // Format top breaches data
    const topBreaches = (topBreachesData || []).map(breach => ({
      id: breach.id,
      organizationName: breach.organization_name,
      affectedIndividuals: breach.affected_individuals,
      sourceName: breach.source_name,
      breachDate: breach.breach_date,
      reportedDate: breach.reported_date
    }))

    const dailyStats: DailyStats = {
      totalNewItems: data.length,
      newBreaches,
      newNews,
      newAffectedTotal,
      sourceBreakdown,
      topBreaches,
      timeRange: {
        start: startIso,
        end: endIso
      }
    }

    console.log('Daily stats computed:', dailyStats)
    return { data: dailyStats, error: null }
  } catch (error) {
    console.error('Error fetching daily stats:', error)
    return { data: null, error: error as Error }
  }
}

// AI Report Functions
export async function generateAIReport(breachId: number, userId?: string) {
  console.log('Generating AI report for breach:', breachId)

  try {
    const { data, error } = await supabase.functions.invoke('generate-ai-report', {
      body: {
        breachId,
        userId: userId || null
      }
    })

    if (error) {
      console.error('Error generating AI report:', error)
      throw error
    }

    console.log('AI report generation initiated:', data)
    return { data, error: null }
  } catch (error) {
    console.error('Failed to generate AI report:', error)
    return { data: null, error: error as Error }
  }
}

export async function getAIReport(reportId: string) {
  console.log('Fetching AI report:', reportId)

  try {
    const { data, error } = await supabase
      .from('v_ai_reports')
      .select('*')
      .eq('id', reportId)
      .single()

    if (error) {
      console.error('Error fetching AI report:', error)
      throw error
    }

    console.log('AI report fetched successfully')
    return { data, error: null }
  } catch (error) {
    console.error('Failed to fetch AI report:', error)
    return { data: null, error: error as Error }
  }
}

export async function getAIReportsByBreach(breachId: number) {
  console.log('Fetching AI reports for breach:', breachId)

  try {
    const { data, error } = await supabase
      .from('research_jobs')
      .select('id, status, processing_time_ms, search_results_count, scraped_urls_count, error_message, created_at, completed_at')
      .eq('scraped_item', breachId)
      .eq('report_type', 'ai_breach_analysis')
      .order('created_at', { ascending: false })

    if (error) {
      console.error('Error fetching AI reports for breach:', error)
      throw error
    }

    console.log('AI reports for breach fetched successfully:', data?.length || 0,'reports')
    return { data, error: null }
  } catch (error) {
    console.error('Failed to fetch AI reports for breach:', error)
    return { data: null, error: error as Error }
  }
}

export async function getUserAIReportUsage(userId: string, days: number = 7) {
  console.log('Fetching AI report usage for user:', userId)

  try {
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - days)

    const { data, error } = await supabase
      .from('ai_report_usage')
      .select('*')
      .eq('user_id', userId)
      .gte('date', startDate.toISOString().split('T')[0])
      .order('date', { ascending: false })

    if (error) {
      console.error('Error fetching AI report usage:', error)
      throw error
    }

    console.log('AI report usage fetched successfully:', data?.length || 0,'records')
    return { data, error: null }
  } catch (error) {
    console.error('Failed to fetch AI report usage:', error)
    return { data: null, error: error as Error }
  }
}

export async function checkDailyRateLimit(userId: string, maxReports: number = 10) {
  console.log('Checking daily rate limit for user:', userId)

  try {
    const { data, error } = await supabase.rpc('check_daily_rate_limit', {
      p_user_id: userId,
      p_max_reports: maxReports
    })

    if (error) {
      console.error('Error checking rate limit:', error)
      throw error
    }

    console.log('Rate limit check result:', data)
    return { data, error: null }
  } catch (error) {
    console.error('Failed to check rate limit:', error)
    return { data: null, error: error as Error }
  }
}

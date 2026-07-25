import React, { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, TrendingUp, Calendar } from 'lucide-react'
import { supabase, getDailyStats, type DailyStats, SOURCE_TYPE_CONFIG } from '../../lib/supabase'
import { formatNumber, formatAffectedCount } from '../../lib/utils'
import { LastScraperRun } from './LastScraperRun'

interface OverallStats {
  totalSources: number
  totalBreaches: number
  totalAffected: number
  totalNews: number
  lastUpdated: string
}

export function SourceSummaryHero() {
  const [stats, setStats] = useState<OverallStats | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [dailyExpanded, setDailyExpanded] = useState(false)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      setLoading(true)

      // Load overall stats and daily stats in parallel
      const [overallStatsResult, dailyStatsResult] = await Promise.all([
        loadOverallStats(),
        getDailyStats()
      ])

      if (dailyStatsResult.data) {
        setDailyStats(dailyStatsResult.data)
      }

      setStats(overallStatsResult)
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadOverallStats = async (): Promise<OverallStats> => {
    // Get breach count (excluding news feeds) using centralized config
    const { count: totalBreaches } = await supabase
      .from('v_breach_dashboard')
      .select('*', { count: 'exact', head: true })
      .in('source_type', SOURCE_TYPE_CONFIG.getBreachSourceTypes())

    // Get news count using centralized config
    const { count: totalNews } = await supabase
      .from('v_breach_dashboard')
      .select('*', { count: 'exact', head: true })
      .in('source_type', SOURCE_TYPE_CONFIG.getNewsSourceTypes())

    // Get total affected individuals
    const { data: affectedData } = await supabase
      .from('v_breach_dashboard')
      .select('affected_individuals')
      .not('affected_individuals', 'is', null)
      .limit(10000) // Ensure we get all records, not just first 1000

    const totalAffected = affectedData?.reduce((sum, item) => sum + (item.affected_individuals || 0), 0) || 0

    // Get source count (exclude API sources)
    const { data: sourcesData } = await supabase
      .from('data_sources')
      .select('id')
      .neq('type', 'API')

    // Get latest scraped date
    const { data: latestData } = await supabase
      .from('v_breach_dashboard')
      .select('scraped_at')
      .not('scraped_at', 'is', null)
      .order('scraped_at', { ascending: false })
      .limit(1)

    const lastUpdated = latestData?.[0]?.scraped_at || new Date().toISOString()

    return {
      totalSources: sourcesData?.length || 0,
      totalBreaches: totalBreaches || 0,
      totalAffected,
      totalNews: totalNews || 0,
      lastUpdated
    }
  }

  if (loading) {
    return (
      <div className="mb-12">
        {/* Loading Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 p-6 rounded-2xl border border-gray-200 dark:border-gray-700">
              <div className="animate-pulse">
                <div className="w-12 h-12 bg-gray-300 dark:bg-gray-600 rounded-2xl mb-4"></div>
                <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-3/4 mb-2"></div>
                <div className="h-8 bg-gray-300 dark:bg-gray-600 rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-gray-300 dark:bg-gray-600 rounded w-2/3"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="mb-12">
      {/* Last Scraper Run Status */}
      <LastScraperRun className="mb-6" />

      {/* Daily Activity Banner */}
      {dailyStats && (
        <div className="mb-8">
          <div
            className="group relative overflow-hidden bg-gradient-to-br from-purple-50 to-violet-100 dark:from-purple-900/20 dark:to-violet-900/20 p-6 rounded-2xl border border-purple-200/50 dark:border-purple-800/50 hover:shadow-xl hover:shadow-purple-500/10 transition-all duration-300 cursor-pointer"
            onClick={() => setDailyExpanded(!dailyExpanded)}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-violet-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <div className="relative">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/25">
                    <TrendingUp className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="text-lg font-bold text-gray-900 dark:text-white">Today's Activity</h3>
                      <span className="px-2 py-1 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 text-xs font-semibold rounded-full">
                        LIVE
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Since 1:00 AM • {formatNumber(dailyStats.totalNewItems)} total items
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-6">
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {formatNumber(dailyStats.newBreaches)}
                    </p>
                    <p className="text-sm text-purple-600 dark:text-purple-400 font-semibold">
                      New Breaches
                    </p>
                  </div>
                  {dailyStats.newNews > 0 && (
                    <div className="text-right">
                      <p className="text-2xl font-bold text-gray-900 dark:text-white">
                        {formatNumber(dailyStats.newNews)}
                      </p>
                      <p className="text-sm text-purple-600 dark:text-purple-400 font-semibold">
                        News Articles
                      </p>
                    </div>
                  )}
                  {dailyStats.newAffectedTotal > 0 && (
                    <div className="text-right">
                      <p className="text-2xl font-bold text-gray-900 dark:text-white">
                        {formatAffectedCount(dailyStats.newAffectedTotal)}
                      </p>
                      <p className="text-sm text-purple-600 dark:text-purple-400 font-semibold">
                        People Affected
                      </p>
                    </div>
                  )}
                  <div className="flex items-center">
                    {dailyExpanded ? (
                      <ChevronUp className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                </div>
              </div>

              {/* Expandable Details */}
              {dailyExpanded && (
                <div className="mt-6 pt-6 border-t border-purple-200/50 dark:border-purple-800/50 space-y-8">

                  {/* Top 3 Breaches Today */}
                  {dailyStats.topBreaches && dailyStats.topBreaches.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wide mb-4">
                        Top Breaches Today
                      </h4>
                      <div className="space-y-3">
                        {dailyStats.topBreaches.map((breach, index) => (
                          <div key={breach.id} className="bg-white/70 dark:bg-gray-800/70 p-4 rounded-xl border border-purple-200/40 dark:border-purple-800/40 hover:bg-white/90 dark:hover:bg-gray-800/90 transition-colors">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-3">
                                <div className="w-8 h-8 bg-gradient-to-br from-red-500 to-red-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                                  {index + 1}
                                </div>
                                <div>
                                  <p className="font-semibold text-gray-900 dark:text-white">
                                    {breach.organizationName}
                                  </p>
                                  <p className="text-sm text-gray-500 dark:text-gray-400">
                                    via {breach.sourceName}
                                  </p>
                                </div>
                              </div>
                              <div className="text-right">
                                <p className="text-xl font-bold text-red-600 dark:text-red-400">
                                  {breach.affectedIndividuals ? formatAffectedCount(breach.affectedIndividuals) : 'Unknown'}
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  people affected
                                </p>
                              </div>
                            </div>
                            {(breach.breachDate || breach.reportedDate) && (
                              <div className="mt-2 pt-2 border-t border-gray-200/50 dark:border-gray-700/50">
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  {breach.breachDate && (
                                    <span>Breach: {new Date(breach.breachDate).toLocaleDateString()}</span>
                                  )}
                                  {breach.breachDate && breach.reportedDate && <span> • </span>}
                                  {breach.reportedDate && (
                                    <span>Reported: {new Date(breach.reportedDate).toLocaleDateString()}</span>
                                  )}
                                </p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Source Breakdown */}
                  <div>
                    <h4 className="text-sm font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wide mb-4">
                      Source Activity
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {dailyStats.sourceBreakdown.slice(0, 6).map((source, index) => (
                        <div key={index} className="bg-white/50 dark:bg-gray-800/50 p-4 rounded-xl border border-purple-200/30 dark:border-purple-800/30">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-gray-900 dark:text-white text-sm">
                                {source.sourceName}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                {source.isBreachSource ? 'Breach Source' : 'News Source'}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
                                {formatNumber(source.newItems)}
                              </p>
                              {source.newAffected > 0 && (
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  {formatAffectedCount(source.newAffected)} affected
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    {dailyStats.sourceBreakdown.length > 6 && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-4 text-center">
                        + {dailyStats.sourceBreakdown.length - 6} more sources with activity
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="group relative overflow-hidden bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/20 dark:to-indigo-900/20 p-6 rounded-2xl border border-blue-200/50 dark:border-blue-800/50 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-indigo-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/25">
                <span className="text-white text-xl"></span>
              </div>
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">Breach Notifications</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {formatNumber(stats?.totalBreaches || 0)}
              </p>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                + {formatNumber(stats?.totalNews || 0)} news articles
              </p>
            </div>
          </div>
        </div>

        <div className="group relative overflow-hidden bg-gradient-to-br from-red-50 to-pink-100 dark:from-red-900/20 dark:to-pink-900/20 p-6 rounded-2xl border border-red-200/50 dark:border-red-800/50 hover:shadow-xl hover:shadow-red-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-red-500 to-red-600 rounded-2xl flex items-center justify-center shadow-lg shadow-red-500/25">
                <span className="text-white text-xl"></span>
              </div>
              <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide">People Affected</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {formatAffectedCount(stats?.totalAffected || 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="group relative overflow-hidden bg-gradient-to-br from-green-50 to-emerald-100 dark:from-green-900/20 dark:to-emerald-900/20 p-6 rounded-2xl border border-green-200/50 dark:border-green-800/50 hover:shadow-xl hover:shadow-green-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center shadow-lg shadow-green-500/25">
                <span className="text-white text-xl"></span>
              </div>
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-green-600 dark:text-green-400 uppercase tracking-wide">Active Sources</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">{stats?.totalSources}</p>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Government & News</p>
            </div>
          </div>
        </div>

        <div className="group relative overflow-hidden bg-gradient-to-br from-orange-50 to-amber-100 dark:from-orange-900/20 dark:to-amber-900/20 p-6 rounded-2xl border border-orange-200/50 dark:border-orange-800/50 hover:shadow-xl hover:shadow-orange-500/10 transition-all duration-300 hover:scale-105">
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-amber-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg shadow-orange-500/25">
                <span className="text-white text-xl"></span>
              </div>
              <div className="w-2 h-2 bg-orange-400 rounded-full animate-pulse"></div>
            </div>
            <div>
              <p className="text-sm font-semibold text-orange-600 dark:text-orange-400 uppercase tracking-wide">Last Updated</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {stats?.lastUpdated ? new Date(stats.lastUpdated).toLocaleDateString() : 'Today'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

import React from 'react'
import { type BreachRecord } from '../../lib/supabase'
import { formatDate, formatNumber, getSourceTypeColor, extractDomain } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface BreachDetailProps {
  breach: BreachRecord
}

export function BreachDetail({ breach }: BreachDetailProps) {
  const timelineEvents = [
    { label:'Incident Discovered', date: breach.incident_discovery_date, icon:''},
    { label:'Breach Occurred', date: breach.breach_date, icon:''},
    { label:'Reported', date: breach.reported_date, icon:''},
    { label:'Published', date: breach.publication_date, icon:''},
    { label:'Found by Scraper', date: breach.scraped_at, icon:''},
  ].filter(event => event.date)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {breach.organization_name}
          </h3>
          <div className="flex items-center space-x-2 mt-1">
            <Badge className={getSourceTypeColor(breach.source_type)}>
              {breach.source_type}
            </Badge>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              via {breach.source_name}
            </span>
          </div>
        </div>
        <div className="flex space-x-2">
          {breach.notice_document_url && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(breach.notice_document_url!, '_blank')}
              className="border-gray-200 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/20"
            >
               Official Notice
            </Button>
          )}
          {breach.item_url && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(breach.item_url!, '_blank')}
              className="border-gray-200 dark:border-gray-600 hover:bg-purple-50 dark:hover:bg-purple-900/20"
            >
               View Source
            </Button>
          )}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg border border-gray-100 dark:border-gray-600/30 shadow-sm">
          <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Affected Individuals</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">
            {breach.affected_individuals ? formatNumber(breach.affected_individuals) : 'Unknown'}
          </div>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg border border-gray-100 dark:border-gray-600/30 shadow-sm">
          <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Breach Date</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">
            {formatDate(breach.breach_date)}
          </div>
        </div>
        <div className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg border border-gray-100 dark:border-gray-600/30 shadow-sm">
          <div className="text-sm font-medium text-gray-500 dark:text-gray-400">Source Domain</div>
          <div className="text-lg font-semibold text-gray-900 dark:text-white">
            {extractDomain(breach.item_url)}
          </div>
        </div>
      </div>

      {/* Timeline */}
      {timelineEvents.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Timeline</h4>
          <div className="flex space-x-4 overflow-x-auto pb-2">
            {timelineEvents.map((event, index) => (
              <div key={index} className="flex-shrink-0 text-center">
                <div className="w-10 h-10 bg-gradient-to-br from-teal-100 to-purple-100 dark:from-teal-900/30 dark:to-purple-900/30 rounded-full flex items-center justify-center text-sm shadow-sm border border-gray-100 dark:border-gray-700/50">
                  {event.icon}
                </div>
                <div className="mt-2 text-xs font-medium text-gray-900 dark:text-white">
                  {event.label}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {formatDate(event.date)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Compromised */}
      {(breach.what_was_leaked || breach.data_types_compromised) && (
        <div className="bg-white/50 dark:bg-gray-800/50 p-4 rounded-lg border border-gray-100 dark:border-gray-700/30">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Data Compromised</h4>
          <div className="space-y-3">
            {breach.what_was_leaked && (
              <div>
                <div className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                  {breach.what_was_leaked}
                </div>
              </div>
            )}
            {breach.data_types_compromised && breach.data_types_compromised.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Data Types:</div>
                <div className="flex flex-wrap gap-1">
                  {breach.data_types_compromised.map((type, index) => (
                    <Badge key={index} variant="secondary" className="text-xs">
                      {type}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Incident Details */}
      {breach.incident_nature_text && (
        <div className="bg-white/50 dark:bg-gray-800/50 p-4 rounded-lg border border-gray-100 dark:border-gray-700/30">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Incident Details</h4>
          <div className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
            {breach.incident_nature_text}
          </div>
        </div>
      )}

      {/* Summary */}
      {breach.summary_text && (
        <div className="bg-white/50 dark:bg-gray-800/50 p-4 rounded-lg border border-gray-100 dark:border-gray-700/30">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Summary</h4>
          <div className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
            {breach.summary_text}
          </div>
        </div>
      )}

      {/* Tags */}
      {breach.tags_keywords && breach.tags_keywords.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Tags</h4>
          <div className="flex flex-wrap gap-1">
            {breach.tags_keywords.map((tag, index) => (
              <Badge key={index} variant="outline" className="text-xs bg-white/50 dark:bg-gray-800/50">
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="pt-4 border-t border-gray-200 dark:border-gray-700/50">
        <div className="grid grid-cols-2 gap-4 text-xs text-gray-500 dark:text-gray-400">
          <div>
            <span className="font-medium">Record ID:</span> {breach.id}
          </div>
          <div>
            <span className="font-medium">Scraped:</span> {formatDate(breach.scraped_at)}
          </div>
          <div>
            <span className="font-medium">Created:</span> {formatDate(breach.created_at)}
          </div>
          {breach.is_cybersecurity_related && (
            <div>
              <span className="font-medium">Cybersecurity Related:</span> Yes
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

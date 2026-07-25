import React from 'react'
import { Button } from '../ui/Button'

export type ViewType = 'breaches' | 'news' | 'saved' | 'reports'

interface ViewToggleProps {
  currentView: ViewType
  onViewChange: (view: ViewType) => void
  breachCount?: number
  newsCount?: number
  savedCount?: number
  reportsCount?: number
}

export function ViewToggle({ currentView, onViewChange, breachCount, newsCount, savedCount, reportsCount }: ViewToggleProps) {
  return (
    <div className="flex items-center space-x-1 bg-gray-100 dark:bg-gray-700 p-1 rounded-lg">
      <Button
        variant={currentView === 'breaches' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('breaches')}
        className={`flex items-center space-x-2 ${
          currentView === 'breaches'
            ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white'
            : 'hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
        }`}
      >
        <span>Breach Notifications</span>
        {breachCount !== undefined && (
          <span className="ml-1 px-2 py-0.5 text-xs bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 rounded-full">
            {breachCount.toLocaleString()}
          </span>
        )}
      </Button>
      
      <Button
        variant={currentView === 'news' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('news')}
        className={`flex items-center space-x-2 ${
          currentView === 'news'
            ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white'
            : 'hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
        }`}
      >
        <span>Cybersecurity News</span>
        {newsCount !== undefined && (
          <span className="ml-1 px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
            {newsCount.toLocaleString()}
          </span>
        )}
      </Button>

      <Button
        variant={currentView === 'saved' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('saved')}
        className={`flex items-center space-x-2 ${
          currentView === 'saved'
            ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white'
            : 'hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
        }`}
      >
        <span>Saved Breaches</span>
        {savedCount !== undefined && (
          <span className="ml-1 px-2 py-0.5 text-xs bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200 rounded-full">
            {savedCount.toLocaleString()}
          </span>
        )}
      </Button>

      <Button
        variant={currentView === 'reports' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('reports')}
        className={`flex items-center space-x-2 ${
          currentView === 'reports'
            ? 'bg-white dark:bg-gray-800 shadow-sm text-gray-900 dark:text-white'
            : 'hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'
        }`}
      >
        <span>AI Reports</span>
        {reportsCount !== undefined && (
          <span className="ml-1 px-2 py-0.5 text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 rounded-full">
            {reportsCount.toLocaleString()}
          </span>
        )}
      </Button>
    </div>
  )
}

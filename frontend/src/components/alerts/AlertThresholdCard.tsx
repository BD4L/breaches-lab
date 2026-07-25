import React, { useState, useEffect } from 'react'
import { Bell, Mail, Settings, Save, AlertCircle, CheckCircle, Users } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { supabase } from '../../lib/supabase'

interface AlertThresholdCardProps {
  className?: string
}

interface AlertPreferences {
  email: string
  threshold: number
  email_verified: boolean
  alert_frequency: 'immediate' | 'daily' | 'weekly'
  notify_high_impact: boolean
  notify_critical_sectors: boolean
}

export function AlertThresholdCard({ className = '' }: AlertThresholdCardProps) {
  const [preferences, setPreferences] = useState<AlertPreferences>({
    email: '',
    threshold: 0,
    email_verified: false,
    alert_frequency: 'immediate',
    notify_high_impact: true,
    notify_critical_sectors: true
  })
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    loadPreferences()
  }, [])

  const loadPreferences = async () => {
    try {
      setLoading(true)
      const { data, error } = await supabase
        .from('user_prefs')
        .select('email, threshold, email_verified, alert_frequency, notify_high_impact, notify_critical_sectors')
        .eq('user_id', 'anonymous')
        .maybeSingle()

      if (error && error.code !== 'PGRST116') {
        throw error
      }

      if (data) {
        setPreferences({
          email: data.email || '',
          threshold: data.threshold || 0,
          email_verified: data.email_verified || false,
          alert_frequency: data.alert_frequency || 'immediate',
          notify_high_impact: data.notify_high_impact ?? true,
          notify_critical_sectors: data.notify_critical_sectors ?? true
        })
      }
    } catch (error) {
      console.error('Error loading preferences:', error)
    } finally {
      setLoading(false)
    }
  }

  const savePreferences = async () => {
    try {
      setSaving(true)
      setMessage(null)

      const { error } = await supabase
        .from('user_prefs')
        .upsert({
          user_id: 'anonymous',
          email: preferences.email,
          threshold: preferences.threshold,
          alert_frequency: preferences.alert_frequency,
          notify_high_impact: preferences.notify_high_impact,
          notify_critical_sectors: preferences.notify_critical_sectors,
          updated_at: new Date().toISOString()
        }, {
          onConflict: 'user_id' // Use user_id for conflict resolution
        })

      if (error) throw error

      setMessage({ type:'success', text:'Email alert preferences saved! Alerts will be sent automatically when new breaches are detected by the scrapers.'})
      setTimeout(() => setMessage(null), 5000)
    } catch (error) {
      console.error('Error saving preferences:', error)
      setMessage({ type: 'error', text: 'Failed to save preferences' })
    } finally {
      setSaving(false)
    }
  }

  const getThresholdLabel = (threshold: number) => {
    if (threshold === 0) return 'Any breach'
    if (threshold >= 1000000) return `${(threshold / 1000000).toFixed(1)}M+ people`
    if (threshold >= 1000) return `${(threshold / 1000).toFixed(0)}K+ people`
    return `${threshold.toLocaleString()}+ people`
  }

  const getImpactLevel = (threshold: number) => {
    if (threshold === 0) return { label: 'All', color: 'gray' }
    if (threshold >= 100000) return { label: 'Critical', color: 'red' }
    if (threshold >= 10000) return { label: 'High', color: 'orange' }
    if (threshold >= 1000) return { label: 'Medium', color: 'yellow' }
    return { label: 'Low', color: 'green' }
  }

  const impact = getImpactLevel(preferences.threshold)

  if (loading) {
    return (
      <div className={`bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 ${className}`}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-1/2"></div>
          <div className="h-3 bg-gray-300 dark:bg-gray-600 rounded w-3/4"></div>
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <Bell className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Email Alerts
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Get notified of significant breaches
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Current Settings Summary */}
      <div className="p-4 space-y-3">
        {preferences.email ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Mail className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {preferences.email}
              </span>
              {preferences.email_verified ? (
                <Badge className="bg-green-100 text-green-800 border-green-200 text-xs">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Verified
                </Badge>
              ) : (
                <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 text-xs">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  Unverified
                </Badge>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center space-x-2 text-gray-500 dark:text-gray-400">
            <Mail className="w-4 h-4" />
            <span className="text-sm">No email configured</span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Alert threshold: {getThresholdLabel(preferences.threshold)}
            </span>
          </div>
          <Badge className={`text-xs ${
            impact.color === 'red' ? 'bg-red-100 text-red-800 border-red-200' :
            impact.color === 'orange' ? 'bg-orange-100 text-orange-800 border-orange-200' :
            impact.color === 'yellow' ? 'bg-yellow-100 text-yellow-800 border-yellow-200' :
            impact.color === 'green' ? 'bg-green-100 text-green-800 border-green-200' :
            'bg-gray-100 text-gray-800 border-gray-200'
          }`}>
            {impact.label} Impact
          </Badge>
        </div>

        <div className="text-xs text-gray-500 dark:text-gray-400">
          Frequency: {preferences.alert_frequency} •
          {preferences.notify_high_impact ?'High impact':'High impact'} •
          {preferences.notify_critical_sectors ?'Critical sectors':'Critical sectors'}
        </div>

        {preferences.email && (
          <div className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 p-2 rounded border border-blue-200 dark:border-blue-800">
             Email alerts are processed automatically when scrapers detect new breaches matching your criteria.
          </div>
        )}
      </div>

      {/* Expanded Settings */}
      {isExpanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 space-y-4">
          {message && (
            <div className={`p-3 rounded-lg flex items-center space-x-2 text-sm ${
              message.type === 'success' 
                ? 'bg-green-50 text-green-800 border border-green-200' 
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}>
              {message.type === 'success' ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <AlertCircle className="w-4 h-4" />
              )}
              <span>{message.text}</span>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Email Address
              </label>
              <Input
                type="email"
                value={preferences.email}
                onChange={(e) => setPreferences(prev => ({ ...prev, email: e.target.value }))}
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Alert Threshold
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Any', value: 0 },
                  { label: '1K+', value: 1000 },
                  { label: '10K+', value: 10000 },
                  { label: '100K+', value: 100000 }
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setPreferences(prev => ({ ...prev, threshold: option.value }))}
                    className={`p-2 text-sm rounded-lg border transition-all ${
                      preferences.threshold === option.value
                        ? 'bg-blue-100 border-blue-300 text-blue-800 dark:bg-blue-900/30 dark:border-blue-700 dark:text-blue-200'
                        : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-600'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Frequency
              </label>
              <select
                value={preferences.alert_frequency}
                onChange={(e) => setPreferences(prev => ({ 
                  ...prev, 
                  alert_frequency: e.target.value as 'immediate' | 'daily' | 'weekly' 
                }))}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              >
                <option value="immediate">Immediate</option>
                <option value="daily">Daily Digest</option>
                <option value="weekly">Weekly Summary</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.notify_high_impact}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    notify_high_impact: e.target.checked 
                  }))}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  High impact breaches (10K+ people)
                </span>
              </label>

              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.notify_critical_sectors}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    notify_critical_sectors: e.target.checked 
                  }))}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Critical sectors (Healthcare, Finance)
                </span>
              </label>
            </div>

            <Button 
              onClick={savePreferences} 
              disabled={saving}
              className="w-full flex items-center justify-center space-x-2"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Alert Settings'}</span>
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

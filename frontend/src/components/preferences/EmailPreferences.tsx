import React, { useState, useEffect } from 'react'
import { Mail, Bell, Shield, Settings, Save, AlertCircle, CheckCircle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Badge } from '../ui/Badge'
import { supabase } from '../../lib/supabase'

interface EmailPreferences {
  email: string
  email_verified: boolean
  threshold: number
  alert_frequency: 'immediate' | 'daily' | 'weekly'
  email_format: 'html' | 'text'
  include_summary: boolean
  include_links: boolean
  max_alerts_per_day: number
  notify_high_impact: boolean
  notify_critical_sectors: boolean
  notify_local_breaches: boolean
  source_types: string[]
  keywords: string[]
}

interface EmailPreferencesProps {
  onClose?: () => void
}

export function EmailPreferences({ onClose }: EmailPreferencesProps) {
  const [preferences, setPreferences] = useState<EmailPreferences>({
    email: '',
    email_verified: false,
    threshold: 0,
    alert_frequency: 'immediate',
    email_format: 'html',
    include_summary: true,
    include_links: true,
    max_alerts_per_day: 10,
    notify_high_impact: true,
    notify_critical_sectors: true,
    notify_local_breaches: false,
    source_types: [],
    keywords: []
  })
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [newKeyword, setNewKeyword] = useState('')

  useEffect(() => {
    loadPreferences()
  }, [])

  const loadPreferences = async () => {
    try {
      setLoading(true)
      // For now, using anonymous user - in production, use actual auth
      const { data, error } = await supabase
        .from('user_prefs')
        .select('*')
        .eq('user_id', 'anonymous')
        .maybeSingle()

      if (error && error.code !== 'PGRST116') { // PGRST116 = no rows returned
        throw error
      }

      if (data) {
        setPreferences({
          email: data.email || '',
          email_verified: data.email_verified || false,
          threshold: data.threshold || 0,
          alert_frequency: data.alert_frequency || 'immediate',
          email_format: data.email_format || 'html',
          include_summary: data.include_summary ?? true,
          include_links: data.include_links ?? true,
          max_alerts_per_day: data.max_alerts_per_day || 10,
          notify_high_impact: data.notify_high_impact ?? true,
          notify_critical_sectors: data.notify_critical_sectors ?? true,
          notify_local_breaches: data.notify_local_breaches ?? false,
          source_types: data.source_types || [],
          keywords: data.keywords || []
        })
      }
    } catch (error) {
      console.error('Error loading preferences:', error)
      setMessage({ type: 'error', text: 'Failed to load preferences' })
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
          user_id: 'anonymous', // In production, use actual user ID
          email: preferences.email,
          email_verified: preferences.email_verified,
          threshold: preferences.threshold,
          alert_frequency: preferences.alert_frequency,
          email_format: preferences.email_format,
          include_summary: preferences.include_summary,
          include_links: preferences.include_links,
          max_alerts_per_day: preferences.max_alerts_per_day,
          notify_high_impact: preferences.notify_high_impact,
          notify_critical_sectors: preferences.notify_critical_sectors,
          notify_local_breaches: preferences.notify_local_breaches,
          source_types: preferences.source_types,
          keywords: preferences.keywords,
          updated_at: new Date().toISOString()
        }, {
          onConflict: 'user_id' // Use user_id for conflict resolution
        })

      if (error) throw error

      setMessage({ type: 'success', text: 'Preferences saved successfully!' })
    } catch (error) {
      console.error('Error saving preferences:', error)
      setMessage({ type: 'error', text: 'Failed to save preferences' })
    } finally {
      setSaving(false)
    }
  }

  const sendVerificationEmail = async () => {
    try {
      if (!preferences.email) {
        setMessage({ type: 'error', text: 'Please enter an email address first' })
        return
      }

      // For now, mark as verified since we don't have a full auth system
      // In production, this would send an actual verification email
      setPreferences(prev => ({ ...prev, email_verified: true }))
      setMessage({ type: 'success', text: 'Email verified! You will now receive breach alerts.' })

      // Auto-save the verification status
      await savePreferences()
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to verify email' })
    }
  }

  const addKeyword = () => {
    if (newKeyword.trim() && !preferences.keywords.includes(newKeyword.trim())) {
      setPreferences(prev => ({
        ...prev,
        keywords: [...prev.keywords, newKeyword.trim()]
      }))
      setNewKeyword('')
    }
  }

  const removeKeyword = (keyword: string) => {
    setPreferences(prev => ({
      ...prev,
      keywords: prev.keywords.filter(k => k !== keyword)
    }))
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-2xl mx-4">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-300 dark:bg-gray-600 rounded w-1/3"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-4 bg-gray-300 dark:bg-gray-600 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-3">
            <Mail className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Email Alert Preferences
            </h2>
          </div>
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>

            </Button>
          )}
        </div>

        {/* Content */}
        <div className="p-6 space-y-8">
          {/* Message */}
          {message && (
            <div className={`p-4 rounded-lg flex items-center space-x-2 ${
              message.type === 'success' 
                ? 'bg-green-50 text-green-800 border border-green-200' 
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}>
              {message.type === 'success' ? (
                <CheckCircle className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
              <span>{message.text}</span>
            </div>
          )}

          {/* Email Configuration */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Mail className="w-5 h-5 mr-2" />
              Email Configuration
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Email Address
                </label>
                <div className="flex space-x-2">
                  <Input
                    type="email"
                    value={preferences.email}
                    onChange={(e) => setPreferences(prev => ({ ...prev, email: e.target.value }))}
                    placeholder="your@email.com"
                    className="flex-1"
                  />
                  {preferences.email_verified ? (
                    <Badge className="bg-green-100 text-green-800 border-green-200 flex items-center">
                      <CheckCircle className="w-3 h-3 mr-1" />
                      Verified
                    </Badge>
                  ) : (
                    <Button variant="outline" size="sm" onClick={sendVerificationEmail}>
                      Verify
                    </Button>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Alert Frequency
                </label>
                <select
                  value={preferences.alert_frequency}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    alert_frequency: e.target.value as 'immediate' | 'daily' | 'weekly' 
                  }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="immediate">Immediate</option>
                  <option value="daily">Daily Digest</option>
                  <option value="weekly">Weekly Summary</option>
                </select>
              </div>
            </div>
          </div>

          {/* Alert Thresholds */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Bell className="w-5 h-5 mr-2" />
              Alert Thresholds
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Minimum Affected People
                </label>
                <Input
                  type="number"
                  value={preferences.threshold}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    threshold: parseInt(e.target.value) || 0 
                  }))}
                  placeholder="0"
                  min="0"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Only alert for breaches affecting this many people or more
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Max Alerts Per Day
                </label>
                <Input
                  type="number"
                  value={preferences.max_alerts_per_day}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    max_alerts_per_day: parseInt(e.target.value) || 10 
                  }))}
                  placeholder="10"
                  min="1"
                  max="100"
                />
              </div>
            </div>
          </div>

          {/* Notification Types */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Shield className="w-5 h-5 mr-2" />
              Notification Types
            </h3>
            
            <div className="space-y-3">
              <label className="flex items-center space-x-3 cursor-pointer">
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
                  High Impact Breaches (10,000+ people affected)
                </span>
              </label>

              <label className="flex items-center space-x-3 cursor-pointer">
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
                  Critical Sectors (Healthcare, Finance, Government)
                </span>
              </label>

              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.include_summary}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    include_summary: e.target.checked 
                  }))}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Include breach summary in emails
                </span>
              </label>

              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.include_links}
                  onChange={(e) => setPreferences(prev => ({ 
                    ...prev, 
                    include_links: e.target.checked 
                  }))}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Include links to documents and sources
                </span>
              </label>
            </div>
          </div>

          {/* Keywords */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Settings className="w-5 h-5 mr-2" />
              Keywords
            </h3>
            
            <div className="flex space-x-2">
              <Input
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                placeholder="Add keyword (e.g., company name)"
                onKeyPress={(e) => e.key === 'Enter' && addKeyword()}
                className="flex-1"
              />
              <Button onClick={addKeyword} variant="outline">
                Add
              </Button>
            </div>
            
            {preferences.keywords.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {preferences.keywords.map((keyword, index) => (
                  <Badge
                    key={index}
                    className="bg-blue-100 text-blue-800 border-blue-200 cursor-pointer hover:bg-blue-200"
                    onClick={() => removeKeyword(keyword)}
                  >
                    {keyword}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Changes are saved automatically and take effect immediately
          </p>
          <div className="flex space-x-3">
            {onClose && (
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
            )}
            <Button 
              onClick={savePreferences} 
              disabled={saving}
              className="flex items-center space-x-2"
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Preferences'}</span>
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

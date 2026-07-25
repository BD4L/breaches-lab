import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { ExternalLink, AlertTriangle, RefreshCw, CheckCircle, XCircle } from 'lucide-react'

interface NonWorkingSite {
  id: number
  name: string
  url: string
  type: string
  description: string
  reason: string
  lastChecked?: string
  status: 'not-working' | 'checking' | 'working' | 'unknown'
}

interface NonWorkingSitesProps {
  onClose: () => void
}

export function NonWorkingSites({ onClose }: NonWorkingSitesProps) {
  const [sites, setSites] = useState<NonWorkingSite[]>([])
  const [loading, setLoading] = useState(true)

  // Non-working sites data based on GitHub Actions and scraper status
  const nonWorkingSitesData: NonWorkingSite[] = [
    {
      id: 10,
      name: "Maryland AG",
      url: "https://www.marylandattorneygeneral.gov/Pages/IdentityTheft/breachnotice.aspx",
      type: "State AG",
      description: "Maryland Attorney General data breach notifications",
      reason: "Website structure issues - table parsing fails. Site may have yearly pages (e.g., breachnotices2023.aspx) that need to be discovered and parsed differently.",
      status: 'not-working'
    },
    {
      id: 13,
      name: "New Hampshire AG",
      url: "https://www.doj.nh.gov/citizens/consumer-protection-antitrust-bureau/security-breach-notifications",
      type: "State AG",
      description: "New Hampshire Attorney General data breach notifications",
      reason: "WAF (Web Application Firewall) protection blocking scraper access. Returns 403 Forbidden errors. May need browser automation or alternative access methods.",
      status: 'not-working'
    },
    {
      id: 14,
      name: "New Jersey Cybersecurity",
      url: "https://www.cyber.nj.gov/threat-landscape/public-data-breaches",
      type: "State AG",
      description: "New Jersey cybersecurity data breach notifications",
      reason: "Incapsula WAF protection blocking scraper access. Advanced bot detection prevents automated access. Requires sophisticated bypass techniques.",
      status: 'not-working'
    },
    {
      id: 16,
      name: "Oklahoma Cybersecurity",
      url: "https://www.ok.gov/cybersecurity/",
      type: "State AG",
      description: "Oklahoma cybersecurity data breach notifications",
      reason: "Website structure changes - scraper needs updates. The breach notification section may have moved or changed format since implementation.",
      status: 'not-working'
    }
  ]

  useEffect(() => {
    // Initialize sites data
    setSites(nonWorkingSitesData)
    setLoading(false)
  }, [])

  const handleCheckSite = async (siteId: number) => {
    setSites(prev => prev.map(site => 
      site.id === siteId 
        ? { ...site, status: 'checking', lastChecked: new Date().toISOString() }
        : site
    ))

    // Simulate checking the site (in a real implementation, this would make an actual request)
    setTimeout(() => {
      setSites(prev => prev.map(site => 
        site.id === siteId 
          ? { ...site, status: 'unknown', lastChecked: new Date().toISOString() }
          : site
      ))
    }, 2000)
  }

  const handleVisitSite = (url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'working':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'not-working':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'checking':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />
      default:
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'working':
        return <Badge variant="success">Working</Badge>
      case 'not-working':
        return <Badge variant="destructive">Not Working</Badge>
      case 'checking':
        return <Badge variant="default">Checking...</Badge>
      default:
        return <Badge variant="secondary">Unknown</Badge>
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin mr-2" />
            Loading non-working sites...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center">
              <AlertTriangle className="h-6 w-6 text-yellow-500 mr-2" />
              Non-Working Sites
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Manual review and status checking for problematic breach portals
            </p>
          </div>
          <Button variant="outline" onClick={onClose}>
             Close
          </Button>
        </div>

        {/* Sites List */}
        <div className="space-y-4">
          {sites.map((site) => (
            <div
              key={site.id}
              className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    {getStatusIcon(site.status)}
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {site.name}
                    </h3>
                    {getStatusBadge(site.status)}
                    <Badge variant="outline">{site.type}</Badge>
                  </div>
                  
                  <p className="text-gray-600 dark:text-gray-400 mb-2">
                    {site.description}
                  </p>
                  
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-3 mb-3">
                    <p className="text-red-800 dark:text-red-200 text-sm">
                      <strong>Issue:</strong> {site.reason}
                    </p>
                  </div>

                  <div className="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400">
                    <span>URL:</span>
                    <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs">
                      {site.url}
                    </code>
                    {site.lastChecked && (
                      <span className="ml-4">
                        Last checked: {new Date(site.lastChecked).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col space-y-2 ml-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleVisitSite(site.url)}
                    className="flex items-center"
                  >
                    <ExternalLink className="h-4 w-4 mr-1" />
                    Visit Site
                  </Button>
                  
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => handleCheckSite(site.id)}
                    disabled={site.status === 'checking'}
                    className="flex items-center"
                  >
                    <RefreshCw className={`h-4 w-4 mr-1 ${site.status === 'checking' ? 'animate-spin' : ''}`} />
                    Check Status
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <h4 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">
             Manual Review Guidelines
          </h4>
          <ul className="text-blue-800 dark:text-blue-200 text-sm space-y-1">
            <li>• <strong>Visit Site:</strong> Check if the breach notification page is accessible</li>
            <li>• <strong>Check Status:</strong> Test basic connectivity and page structure</li>
            <li>• <strong>WAF Issues:</strong> Sites with WAF protection may need alternative approaches</li>
            <li>• <strong>Structure Changes:</strong> Sites may have updated their HTML structure</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

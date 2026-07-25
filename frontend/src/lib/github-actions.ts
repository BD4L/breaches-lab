// GitHub Actions API integration for scraper management
// Note: This requires a GitHub Personal Access Token with workflow permissions

interface WorkflowRun {
  id: number
  name: string
  status: 'queued' | 'in_progress' | 'completed'
  conclusion: 'success' | 'failure' | 'cancelled' | 'skipped' | null
  created_at: string
  updated_at: string
  workflow_id: number
}

interface Workflow {
  id: number
  name: string
  path: string
  state: 'active' | 'deleted'
  created_at: string
  updated_at: string
}

class GitHubActionsAPI {
  // Target repository. Defaults to production; the staging mirror overrides these so its
  // controls drive its own workflows rather than production's.
  //
  // 'HackerManMarlin' was the account's previous name. Calls still resolved because GitHub
  // redirects renamed owners, but a rename redirect is not something to depend on, and
  // browsers do not reliably preserve the method across a 301 for the POST dispatch calls.
  private owner = import.meta.env.PUBLIC_GITHUB_OWNER || 'BD4L'
  private repo = import.meta.env.PUBLIC_GITHUB_REPO || 'Breaches'
  private baseUrl = 'https://api.github.com'
  
  // Note: In production, this should be handled server-side for security
  private getHeaders() {
    const token = import.meta.env.PUBLIC_GITHUB_TOKEN
    if (!token) {
      throw new Error('GitHub token not configured. Please add PUBLIC_GITHUB_TOKEN to repository secrets and redeploy.')
    }

    // Validate token format
    if (!token.startsWith('ghp_') && !token.startsWith('github_pat_')) {
      throw new Error('Invalid GitHub token format. Token should start with "ghp_" or "github_pat_".')
    }

    return {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'X-GitHub-Api-Version': '2022-11-28'
    }
  }

  async getWorkflows(): Promise<Workflow[]> {
    try {
      const response = await fetch(
        `${this.baseUrl}/repos/${this.owner}/${this.repo}/actions/workflows`,
        { headers: this.getHeaders() }
      )
      
      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status}`)
      }
      
      const data = await response.json()
      return data.workflows
    } catch (error) {
      console.error('Failed to fetch workflows:', error)
      return []
    }
  }

  async getWorkflowRuns(workflowId: number, limit = 10): Promise<WorkflowRun[]> {
    try {
      const response = await fetch(
        `${this.baseUrl}/repos/${this.owner}/${this.repo}/actions/workflows/${workflowId}/runs?per_page=${limit}`,
        { headers: this.getHeaders() }
      )
      
      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status}`)
      }
      
      const data = await response.json()
      return data.workflow_runs
    } catch (error) {
      console.error('Failed to fetch workflow runs:', error)
      return []
    }
  }

  async triggerWorkflow(workflowId: number, ref = 'main', inputs?: Record<string, any>): Promise<boolean> {
    try {
      // Convert boolean inputs to strings as required by GitHub Actions API
      const stringInputs: Record<string, string> = {}
      if (inputs) {
        Object.entries(inputs).forEach(([key, value]) => {
          stringInputs[key] = String(value)
        })
      }

      console.log('Triggering workflow with inputs:', stringInputs)

      const response = await fetch(
        `${this.baseUrl}/repos/${this.owner}/${this.repo}/actions/workflows/${workflowId}/dispatches`,
        {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify({
            ref,
            inputs: stringInputs
          })
        }
      )

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`GitHub API error: ${response.status} - ${errorText}`)
      }

      return true
    } catch (error) {
      console.error('Failed to trigger workflow:', error)
      throw error
    }
  }

  async triggerWorkflowByName(workflowName: string, inputs?: Record<string, any>): Promise<boolean> {
    try {
      const workflows = await this.getWorkflows()

      // Specifically target the paralell.yml workflow for scraper operations
      let workflow = workflows.find(w => w.path.includes('paralell.yml'))

      // Fallback to name matching if paralell.yml not found
      if (!workflow) {
        workflow = workflows.find(w =>
          w.name === workflowName ||
          w.path.includes(workflowName) ||
          w.name.toLowerCase().includes(workflowName.toLowerCase())
        )
      }

      if (!workflow) {
        console.error('Available workflows:', workflows.map(w => ({ name: w.name, path: w.path })))
        throw new Error(`Workflow "${workflowName}" not found. Available: ${workflows.map(w => w.name).join(', ')}`)
      }

      console.log(`Triggering workflow: ${workflow.name} (ID: ${workflow.id}, Path: ${workflow.path})`)
      return this.triggerWorkflow(workflow.id, 'main', inputs)
    } catch (error) {
      console.error('Failed to trigger workflow by name:', error)
      throw error
    }
  }



  // Predefined workflow triggers for your scraper groups
  async triggerMainScraperWorkflow(): Promise<boolean> {
    return this.triggerWorkflowByName('Run All Scrapers (Parallel)')
  }

  async triggerParallelScrapers(inputs?: Record<string, any>): Promise<boolean> {
    return this.triggerWorkflowByName('Run All Scrapers (Parallel)', inputs)
  }

  // Get status of all scraper-related workflows
  async getScraperStatus(): Promise<{
    workflow: string
    status: string
    lastRun?: string
    conclusion?: string
  }[]> {
    try {
      const workflows = await this.getWorkflows()
      const scraperWorkflows = workflows.filter(w => 
        w.name.toLowerCase().includes('scraper') || 
        w.name.toLowerCase().includes('ag') ||
        w.path.includes('scraper') ||
        w.path.includes('ag')
      )

      const statusPromises = scraperWorkflows.map(async workflow => {
        const runs = await this.getWorkflowRuns(workflow.id, 1)
        const lastRun = runs[0]
        
        return {
          workflow: workflow.name,
          status: lastRun?.status || 'unknown',
          lastRun: lastRun?.created_at,
          conclusion: lastRun?.conclusion || undefined
        }
      })

      return Promise.all(statusPromises)
    } catch (error) {
      console.error('Failed to get scraper status:', error)
      return []
    }
  }
}

export const githubActions = new GitHubActionsAPI()

// Workflow mapping for the UI - matches paralell.yml structure exactly
export const WORKFLOW_GROUPS = {
  'government-scrapers': {
    name: 'Government & Federal Scrapers',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'SEC EDGAR 8-K, HHS OCR',
    scrapers: ['SEC EDGAR 8-K', 'HHS OCR'],
    workflowFile: 'paralell.yml'
  },
  'state-ag-group-1': {
    name: 'State AG Group 1 (DE, CA, WA, HI)',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'Delaware, California, Washington, Hawaii',
    scrapers: ['Delaware AG', 'California AG', 'Washington AG', 'Hawaii AG'],
    workflowFile: 'paralell.yml'
  },
  'state-ag-group-2': {
    name: 'State AG Group 2 (IN, IA, ME)',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'Indiana, Iowa, Maine',
    scrapers: ['Indiana AG', 'Iowa AG', 'Maine AG'],
    workflowFile: 'paralell.yml'
  },
  'state-ag-group-3': {
    name: 'State AG Group 3 (MA, MT, NH, NJ)',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'Massachusetts, Montana, New Hampshire, New Jersey',
    scrapers: ['Massachusetts AG', 'Montana AG', 'New Hampshire AG', 'New Jersey AG'],
    workflowFile: 'paralell.yml'
  },
  'state-ag-group-4': {
    name: 'State AG Group 4 (ND, OK, VT, WI, TX)',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'North Dakota, Oklahoma, Vermont, Wisconsin, Texas',
    scrapers: ['North Dakota AG', 'Oklahoma Cyber', 'Vermont AG', 'Wisconsin DATCP', 'Texas AG'],
    workflowFile: 'paralell.yml'
  },
  'news-and-api-scrapers': {
    name: 'News & API Scrapers',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'BreachSense, Cybersecurity News, Company IR, HIBP API',
    scrapers: ['BreachSense', 'Cybersecurity News RSS', 'Company IR', 'HIBP API'],
    workflowFile: 'paralell.yml'
  },
  'problematic-scrapers': {
    name: 'Problematic Scrapers (MD)',
    workflow: 'Run All Scrapers (Parallel)',
    description: 'Maryland AG (known website issues)',
    scrapers: ['Maryland AG'],
    workflowFile: 'paralell.yml'
  }
} as const

export type WorkflowGroupId = keyof typeof WORKFLOW_GROUPS

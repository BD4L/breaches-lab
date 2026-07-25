import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

// OpenRouter Kimi-K2 integration
const OPENROUTER_KEY = Deno.env.get('OPENROUTER_API_KEY') ?? ''

// Simple prompt function
function buildKimiPrompt(organizationName: string): string {
  return `Conduct MULTIPLE targeted web searches to thoroughly research the ${organizationName} data breach. Do separate searches for different aspects:

SEARCH 1: Basic breach information
- Search: "${organizationName} data breach 2024 2025"
- Search: "${organizationName} cybersecurity incident"

SEARCH 2: Official government sources
- Search: "${organizationName} SEC filing 8-K cybersecurity"
- Search: "${organizationName} HHS breach report"
- Search: "${organizationName} attorney general notification"

SEARCH 3: News and media coverage
- Search: "${organizationName} breach news Reuters Bloomberg"
- Search: "${organizationName} cybersecurity KrebsOnSecurity BleepingComputer"

SEARCH 4: Legal developments
- Search: "${organizationName} class action lawsuit breach"
- Search: "${organizationName} settlement fine penalty"

SEARCH 5: Company and customer demographics
- Search: "${organizationName} customer demographics target market"
- Search: "${organizationName} user base statistics"

SEARCH 6: Breach notifications and response
- Search: "${organizationName} breach notification letter"
- Search: "${organizationName} credit monitoring offer"

For each search, find:
- Exact number of people affected
- What specific data was stolen/leaked
- Timeline of events
- Company's response and notifications
- Legal consequences
- Customer demographics for marketing targeting

Compile all findings into a comprehensive report with direct links to sources. Use clear headings and organize logically.`;
}

// Kimi-K2 API call with web search
async function runWithKimi(messages: any[]) {
  if (!OPENROUTER_KEY) throw new Error('OPENROUTER_API_KEY not set');
  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${OPENROUTER_KEY}`,
      'HTTP-Referer': 'localhost',
      'X-Title': 'breach-report'
    },
    body: JSON.stringify({
      model: 'moonshotai/kimi-k2:online',
      messages,
      max_tokens: 4096,
      temperature: 0.7,
      plugins: [
        {
          id: 'web',
          max_results: 50,
          search_prompt: 'Conduct multiple targeted web searches to gather comprehensive information. Search different aspects separately for better results. Use all search results to create a thorough breach analysis report. Cite all sources as clickable markdown links like [Source Name](https://example.com).'
        }
      ]
    })
  });
  if (!res.ok) throw new Error(`Kimi-K2 request failed: ${res.status}`);
  const data = await res.json();

  // Return both content and full response for annotations
  return {
    content: data.choices?.[0]?.message?.content ?? 'No content',
    response: data.choices?.[0] ?? null
  };
}

// Extract markdown links for sources
function extractMarkdownLinks(md: string): {title: string; url: string}[] {
  const re = /\[([^\]]+)\]\((https?:[^)]+)\)/g;
  const out = [] as {title:string;url:string}[];
  let match;
  while ((match = re.exec(md)) !== null) {
    out.push({ title: match[1], url: match[2] });
  }
  return out;
}

// Extract web search results from OpenRouter response annotations
function extractWebSearchResults(response: any): {title: string; url: string; content?: string}[] {
  const sources = [] as {title: string; url: string; content?: string}[];

  if (response.message?.annotations) {
    for (const annotation of response.message.annotations) {
      if (annotation.type === 'url_citation' && annotation.url_citation) {
        sources.push({
          title: annotation.url_citation.title || annotation.url_citation.url,
          url: annotation.url_citation.url,
          content: annotation.url_citation.content || ''
        });
      }
    }
  }

  return sources;
}

// Simple markdown cleanup - focus on basic formatting
function cleanMarkdown(content: string): string {
  return content
    // Remove excessive whitespace
    .replace(/\n{3,}/g, '\n\n')
    // Clean up trailing whitespace
    .replace(/[ \t]+$/gm, '')
    // Convert bare URLs to markdown links
    .replace(/(?<![\[\(])(https?:\/\/[^\s\)\]]+)(?![\]\)])/g, '[$1]($1)')
    // Fix basic spacing around headers
    .replace(/^(#{1,6})\s*(.+)$/gm, '$1 $2')
    .trim();
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Content-Type': 'application/json'
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: corsHeaders
    })
  }

  try {
    console.log('AI Report function called')
    
    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if (!supabaseUrl || !supabaseServiceKey) {
      console.error('Missing Supabase configuration')
      return new Response(JSON.stringify({
        error: 'Missing Supabase configuration',
        details: 'SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set'
      }), {
        status: 500,
        headers: corsHeaders
      })
    }
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey)
    console.log('Supabase client initialized')
    
    // Parse request
    let breachId, userId
    try {
      const body = await req.json()
      breachId = body.breachId
      userId = body.userId
      console.log(`Request parsed - breachId: ${breachId}, userId: ${userId}`)
    } catch (error) {
      console.error('Invalid JSON in request body:', error)
      return new Response(JSON.stringify({
        error: 'Invalid JSON in request body',
        details: error.message
      }), {
        status: 400,
        headers: corsHeaders
      })
    }
    
    if (!breachId) {
      console.error('breachId is required')
      return new Response(JSON.stringify({
        error: 'breachId is required',
        details: 'Please provide a valid breachId in the request body'
      }), {
        status: 400,
        headers: corsHeaders
      })
    }
    
    console.log(`Starting AI report generation for breach ${breachId}`)
    
    // Check API key availability
    const apiKeys = {
      openrouter: !!OPENROUTER_KEY,
      gemini: !!Deno.env.get('GEMINI_API_KEY')
    }

    console.log('API Keys availability:', apiKeys)

    if (!apiKeys.openrouter && !apiKeys.gemini) {
      console.error('No AI API keys configured')
      return new Response(JSON.stringify({
        error: 'No AI API keys configured',
        details: 'Please set OPENROUTER_API_KEY or GEMINI_API_KEY in Supabase Edge Function environment variables.',
        apiKeysStatus: apiKeys
      }), {
        status: 500,
        headers: corsHeaders
      })
    }

    // Get breach data
    const { data: breach, error: breachError } = await supabase
      .from('v_breach_dashboard')
      .select('*')
      .eq('id', breachId)
      .single()
      
    if (breachError || !breach) {
      console.error('Breach not found:', breachError)
      return new Response(JSON.stringify({
        error: 'Breach not found',
        details: breachError?.message || 'No breach found with the provided ID'
      }), {
        status: 404,
        headers: corsHeaders
      })
    }

    console.log(`Found breach: ${breach.organization_name}`)

    // Check if report already exists
    const { data: existingReport } = await supabase
      .from('research_jobs')
      .select('id, status, markdown_content')
      .eq('scraped_item', breachId)
      .eq('report_type', 'ai_breach_analysis')
      .maybeSingle()
      
    if (existingReport && existingReport.status === 'completed') {
      console.log(`Returning existing report for breach ${breachId}`)
      return new Response(JSON.stringify({
        reportId: existingReport.id,
        status: 'completed',
        cached: true,
        message: 'Report already exists and is completed'
      }), {
        status: 200,
        headers: corsHeaders
      })
    }
    
    if (existingReport && existingReport.status === 'processing') {
      console.log(`Report already processing for breach ${breachId}`)
      return new Response(JSON.stringify({
        reportId: existingReport.id,
        status: 'processing',
        message: 'Report generation in progress. Please check back in a few moments.'
      }), {
        status: 200,
        headers: corsHeaders
      })
    }

    // Create new report record
    const { data: reportRecord, error: reportError } = await supabase
      .from('research_jobs')
      .insert({
        scraped_item: breachId,
        status: 'processing',
        report_type: 'ai_breach_analysis',
        requested_by: userId || null,
        ai_model_used: OPENROUTER_KEY ? 'moonshotai/kimi-k2' : 'gemini-2.5-flash',
        created_at: new Date().toISOString(),
        metadata: {
          breach_data: breach,
          api_keys_available: apiKeys
        }
      })
      .select()
      .single()
      
    if (reportError) {
      console.error('Failed to create report record:', reportError)
      return new Response(JSON.stringify({
        error: 'Failed to create report record',
        details: reportError.message
      }), {
        status: 500,
        headers: corsHeaders
      })
    }

    console.log(`Created report record ${reportRecord.id}`)

    // Generate AI report immediately
    try {
      console.log('Starting AI report generation...')
      const startTime = Date.now()

      let reportContent = ''
      let sources: {title: string; url: string}[] = []
      let modelUsed = 'unknown'

      if (OPENROUTER_KEY) {
        console.log('Using Kimi-K2 with web search for report generation')
        modelUsed = 'moonshotai/kimi-k2:online'

        const kimiResult = await runWithKimi([
          {
            role: 'system',
            content: 'You are an expert cybersecurity and legal intelligence analyst. Research thoroughly and provide well-structured markdown reports with proper source citations.'
          },
          {
            role: 'user',
            content: buildKimiPrompt(breach.organization_name)
          }
        ])

        reportContent = cleanMarkdown(kimiResult.content)

        // Extract sources from both web search annotations and markdown links
        const webSources = extractWebSearchResults(kimiResult.response)
        const markdownSources = extractMarkdownLinks(reportContent)

        // Combine and deduplicate sources
        const allSources = [...webSources, ...markdownSources]
        sources = allSources.filter((source, index, self) =>
          index === self.findIndex(s => s.url === source.url)
        )

        console.log(`Web search results: ${webSources.length} sources from annotations`)
        console.log(`Markdown links: ${markdownSources.length} sources from content`)
        console.log(`Total unique sources: ${sources.length}`)

      } else if (apiKeys.gemini) {
        console.log('Using Gemini as fallback')
        modelUsed = 'gemini-2.5-flash'

        // Simple Gemini fallback
        const { GoogleGenerativeAI } = await import("https://esm.sh/@google/generative-ai@0.21.0")
        const genAI = new GoogleGenerativeAI(Deno.env.get('GEMINI_API_KEY'))
        const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" })

        const prompt = `You are an expert cybersecurity and legal intelligence analyst. ${buildKimiPrompt(breach.organization_name)}`
        const result = await model.generateContent(prompt)
        reportContent = cleanMarkdown(result.response.text())
        sources = extractMarkdownLinks(reportContent)
      } else {
        throw new Error('No AI API keys available')
      }

      const endTime = Date.now()
      const processingTime = endTime - startTime

      console.log(`Report generated in ${processingTime}ms with ${sources.length} sources`)

      // Update database with completed report
      await supabase.from('research_jobs').update({
        status: 'completed',
        completed_at: new Date().toISOString(),
        markdown_content: reportContent,
        processing_time_ms: processingTime,
        search_results_count: sources.length,
        ai_model_used: modelUsed,
        metadata: {
          research_method: OPENROUTER_KEY ? 'kimi-k2' : 'gemini-basic',
          search_enabled: true,
          searched_sources: sources.map(s => ({
            title: s.title,
            url: s.url,
            snippet: '',
            search_query: 'AI research',
            timestamp: new Date().toISOString(),
            confidence: 'high'
          })),
          total_sources_found: sources.length
        }
      }).eq('id', reportRecord.id)

      // Return success response
      return new Response(JSON.stringify({
        reportId: reportRecord.id,
        status: 'completed',
        processingTimeMs: processingTime,
        searchResultsCount: sources.length,
        modelUsed: modelUsed,
        cached: false
      }), {
        status: 200,
        headers: corsHeaders
      })

    } catch (aiError) {
      console.error('AI generation failed:', aiError)

      // Update database with failed status
      await supabase.from('research_jobs').update({
        status: 'failed',
        completed_at: new Date().toISOString(),
        error_message: aiError.message
      }).eq('id', reportRecord.id)

      return new Response(JSON.stringify({
        error: 'AI report generation failed',
        details: aiError.message,
        reportId: reportRecord.id
      }), {
        status: 500,
        headers: corsHeaders
      })
    }

  } catch (error) {
    console.error('Error in AI report function:', error)
    
    return new Response(JSON.stringify({
      error: error.message || 'Unknown error occurred',
      details: error.stack || 'No stack trace available',
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: corsHeaders
    })
  }
})

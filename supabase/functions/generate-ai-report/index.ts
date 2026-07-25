// Advanced AI Research Agent with Google Search Grounding
// Dynamic multi-source investigation with comprehensive search capabilities
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { GoogleGenerativeAI } from "https://esm.sh/@google/generative-ai@0.21.0";

// ===== OpenRouter Kimi-K2 helper =====
const OPENROUTER_KEY = (typeof Deno !== 'undefined') ? (Deno.env.get('OPENROUTER_API_KEY') ?? '') : '';

// -------------------
// Helper: Build minimal prompt for Kimi-K2
// -------------------
function buildKimiPrompt(breach: any): string {
  return `search the web for information on this ${breach.organization_name} databreach pull from sources that are reputable and any news sources you can find, sources from government sites etc find pdfs with information. Find out what the company that experienced the databreaches target demographic is so we can target the people affected in marketing strategy. Find out exact numbers (people affected), what was leaked, when, if they have sent out an email/notification yet etc. Link all sources

Ensure the company is the one i asked for`;
}

async function runWithKimi(messages) {
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
      model: 'moonshotai/kimi-k2',
      messages,
      max_tokens: 4096,
      temperature: 0.7
    })
  });
  if (!res.ok) throw new Error(`Kimi-K2 request failed: ${res.status}`);
  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? 'No content';
}

function extractMarkdownLinks(md: string): {title: string; url: string}[] {
  const re = /\[([^\]]+)\]\((https?:[^)]+)\)/g;
  const out = [] as {title:string;url:string}[];
  let match;
  while ((match = re.exec(md)) !== null) {
    out.push({ title: match[1], url: match[2] });
  }
  return out;
}
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Content-Type': 'application/json'
};
// Simplified research function - let Kimi-K2 handle the complexity
async function conductComprehensiveResearch(breach, geminiApiKey) {
  const organization = breach.organization_name;
  const startTime = Date.now();
  console.log(`Starting research for ${organization}`);

  try {
    // ----- Use Kimi-K2 if available (preferred) -----
    if (OPENROUTER_KEY) {
      console.log('Using Kimi-K2 for comprehensive research');
      const kimiText = await runWithKimi([
        {
          role: 'system',
          content: 'You are an expert cybersecurity and legal intelligence analyst. Research thoroughly and provide well-structured markdown reports with proper source citations.'
        },
        {
          role: 'user',
          content: buildKimiPrompt(breach)
        }
      ]);

      // Extract sources from markdown links
      const sources = extractMarkdownLinks(kimiText).map(link => ({
        title: link.title,
        url: link.url,
        snippet: '',
        search_query: 'Kimi-K2 research',
        timestamp: new Date().toISOString(),
        confidence: 'high'
      }));

      const endTime = Date.now();
      return {
        organization,
        research_method: 'kimi-k2',
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        duration_ms: endTime - startTime,
        research_report: kimiText,
        model_used: 'moonshotai/kimi-k2',
        search_enabled: true,
        searched_sources: sources,
        sources_count: sources.length
      };
    }

    // ----- Fallback to basic Gemini without complex templates -----
    console.log('Using Gemini as fallback (no OpenRouter key)');
    const genAI = new GoogleGenerativeAI(geminiApiKey);
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

    const simplePrompt = `Research the ${organization} data breach and provide a comprehensive analysis covering what happened, when, how many people were affected, what data was compromised, and the company's response. Include any legal or regulatory implications.`;

    const result = await model.generateContent(simplePrompt);
    const text = result.response.text();

    const endTime = Date.now();
    return {
      organization,
      research_method: 'gemini-basic',
      start_time: new Date(startTime).toISOString(),
      end_time: new Date(endTime).toISOString(),
      duration_ms: endTime - startTime,
      research_report: text,
      model_used: 'gemini-2.5-flash',
      search_enabled: false,
      searched_sources: [],
      sources_count: 0
    };
  } catch (error) {
    console.error('Research failed:', error);
    throw new Error(`Research failed: ${error.message}`);
  }
}


serve(async (req)=>{
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: corsHeaders
    });
  }
  try {
    console.log('AI Research Agent initiated - Kimi-K2 preferred, Gemini fallback');
    const supabaseUrl = Deno.env.get('SUPABASE_URL');
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if (!supabaseUrl || !supabaseServiceKey) {
      return new Response(JSON.stringify({
        error: 'Missing Supabase configuration'
      }), {
        status: 500,
        headers: corsHeaders
      });
    }
    const supabase = createClient(supabaseUrl, supabaseServiceKey);
    const body = await req.json();
    const breachId = body.breachId;
    const userId = body.userId;
    if (!breachId) {
      return new Response(JSON.stringify({
        error: 'breachId is required'
      }), {
        status: 400,
        headers: corsHeaders
      });
    }
    // Check API key
    const geminiApiKey = Deno.env.get('GEMINI_API_KEY');
    if (!geminiApiKey && !OPENROUTER_KEY) {
      return new Response(JSON.stringify({
        error: 'No AI API key configured (set GEMINI_API_KEY or OPENROUTER_API_KEY)'
      }), { status: 500, headers: corsHeaders });
    }
    // Get breach data
    const { data: breach, error: breachError } = await supabase.from('v_breach_dashboard').select('*').eq('id', breachId).single();
    if (breachError || !breach) {
      return new Response(JSON.stringify({
        error: 'Breach not found'
      }), {
        status: 404,
        headers: corsHeaders
      });
    }
    console.log(`Starting comprehensive research for: ${breach.organization_name}`);
    // Check for existing completed report
    const { data: existingReport } = await supabase.from('research_jobs').select('id, status, markdown_content, processing_time_ms, search_results_count').eq('scraped_item', breachId).eq('report_type', 'ai_breach_analysis').eq('status', 'completed').maybeSingle();
    if (existingReport?.markdown_content) {
      console.log(`Returning cached report for breach ${breachId}`);
      return new Response(JSON.stringify({
        reportId: existingReport.id,
        status: 'completed',
        cached: true,
        processingTimeMs: existingReport.processing_time_ms,
        searchResultsCount: existingReport.search_results_count || 100
      }), {
        status: 200,
        headers: corsHeaders
      });
    }
    const startTime = Date.now();
    // Create new report record
    const { data: reportRecord, error: reportError } = await supabase.from('research_jobs').insert({
      scraped_item: breachId,
      status: 'processing',
      report_type: 'ai_breach_analysis',
      requested_by: userId || null,
      ai_model_used: OPENROUTER_KEY ? 'moonshotai/kimi-k2' : 'gemini-2.5-flash',
      created_at: new Date().toISOString()
    }).select().single();
    if (reportError) {
      console.error('Failed to create report record:', reportError);
      return new Response(JSON.stringify({
        error: 'Failed to create report record'
      }), {
        status: 500,
        headers: corsHeaders
      });
    }
    console.log(`Created report record ${reportRecord.id}`);
    try {
      // Conduct research - Kimi-K2 handles everything, Gemini is basic fallback
      console.log('Starting AI research...');
      const researchData = await conductComprehensiveResearch(breach, geminiApiKey);

      // Use the research report directly - Kimi-K2 is comprehensive, Gemini is simple
      const intelligenceReport = researchData.research_report;
      // Get sources from research
      const allSources = researchData.searched_sources || [];
      console.log(`Total sources captured: ${allSources.length}`);
      const endTime = Date.now();
      const processingTimeMs = endTime - startTime;

      // Update report with results
      await supabase.from('research_jobs').update({
        status: 'completed',
        completed_at: new Date().toISOString(),
        markdown_content: intelligenceReport,
        processing_time_ms: processingTimeMs,
        search_results_count: allSources.length,
        scraped_urls_count: allSources.filter((s)=>s.url && s.url !== 'Google Search Result').length,
        ai_model_used: researchData.model_used,
        metadata: {
          research_method: researchData.research_method,
          search_enabled: researchData.search_enabled,
          model_used: researchData.model_used,
          searched_sources: allSources,
          total_sources_found: allSources.length
        }
      }).eq('id', reportRecord.id);
      console.log(`AI research completed: ${processingTimeMs}ms`);
      return new Response(JSON.stringify({
        reportId: reportRecord.id,
        status: 'completed',
        processingTimeMs,
        searchResultsCount: allSources.length,
        researchMethod: researchData.research_method,
        modelUsed: researchData.model_used,
        cached: false
      }), {
        status: 200,
        headers: corsHeaders
      });
    } catch (processingError) {
      console.error('Research processing failed:', processingError);
      await supabase.from('research_jobs').update({
        status: 'failed',
        error_message: processingError.message,
        completed_at: new Date().toISOString()
      }).eq('id', reportRecord.id);
      return new Response(JSON.stringify({
        error: 'Research processing failed',
        details: processingError.message
      }), {
        status: 500,
        headers: corsHeaders
      });
    }
  } catch (error) {
    console.error('System error:', error);
    return new Response(JSON.stringify({
      error: error.message || 'Unknown error occurred'
    }), {
      status: 500,
      headers: corsHeaders
    });
  }
});

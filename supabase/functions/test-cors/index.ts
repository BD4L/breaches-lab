import { serve } from "https://deno.land/std@0.168.0/http/server.ts"

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
    console.log('Test CORS function called')
    
    // Parse request
    let body
    try {
      body = await req.json()
    } catch (error) {
      console.error('Invalid JSON:', error)
      return new Response(JSON.stringify({
        error: 'Invalid JSON in request body',
        details: error.message
      }), {
        status: 400,
        headers: corsHeaders
      })
    }

    console.log('Request body:', body)

    // Return success response
    return new Response(JSON.stringify({
      success: true,
      message: 'CORS test successful!',
      receivedData: body,
      timestamp: new Date().toISOString()
    }), {
      status: 200,
      headers: corsHeaders
    })

  } catch (error) {
    console.error('Error in test function:', error)
    
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

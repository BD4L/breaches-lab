#!/bin/bash

# AI Agent System Test Script
# Run this script to verify your AI agent system is working correctly

echo"AI Agent System Test Script"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_REF="hilbbjnnxkitxbptektg"
ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpbGJiam5ueGtpdHhicHRla3RnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxOTYwNDIsImV4cCI6MjA2Mzc3MjA0Mn0.vk8AJ2pofRAy5y26WQeMYgEFudU1plXnYa6sMFyATFM"
SUPABASE_URL="https://${PROJECT_REF}.supabase.co"

# Test 1: Check Supabase CLI
echo -e "${BLUE}Test 1: Checking Supabase CLI...${NC}"
if command -v supabase &> /dev/null; then
    echo -e"${GREEN} Supabase CLI is installed${NC}"
    supabase --version
else
    echo -e"${RED} Supabase CLI not found. Install with: npm install -g supabase${NC}"
    exit 1
fi
echo ""

# Test 2: Check if project is linked
echo -e "${BLUE}Test 2: Checking project link...${NC}"
if supabase status &> /dev/null; then
    echo -e"${GREEN} Project is linked${NC}"
else
    echo -e"${YELLOW} Project not linked. Run: supabase link --project-ref ${PROJECT_REF}${NC}"
fi
echo ""

# Test 3: Check secrets
echo -e "${BLUE}Test 3: Checking environment variables...${NC}"
secrets_output=$(supabase secrets list 2>/dev/null)
if echo "$secrets_output" | grep -q "GEMINI_API_KEY"; then
    echo -e"${GREEN} GEMINI_API_KEY is set${NC}"
else
    echo -e"${RED} GEMINI_API_KEY not found. Set with: supabase secrets set GEMINI_API_KEY=your_key${NC}"
fi
echo ""

# Test 4: Check function deployment
echo -e "${BLUE}Test 4: Checking Edge Function deployment...${NC}"
functions_output=$(supabase functions list 2>/dev/null)
if echo "$functions_output" | grep -q "generate-ai-report"; then
    echo -e"${GREEN} generate-ai-report function is deployed${NC}"
else
    echo -e"${RED} Function not deployed. Run: supabase functions deploy generate-ai-report${NC}"
fi
echo ""

# Test 5: Test database connection
echo -e "${BLUE}Test 5: Testing database connection...${NC}"
response=$(curl -s -X POST "${SUPABASE_URL}/rest/v1/rpc/check_daily_rate_limit" \
  -H "apikey: ${ANON_KEY}" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"p_user_id": "00000000-0000-0000-0000-000000000000", "p_max_reports": 10}')

if [[ $response == *"true"* ]] || [[ $response == *"false"* ]]; then
    echo -e"${GREEN} Database connection working${NC}"
    echo "Rate limit check result: $response"
else
    echo -e"${RED} Database connection failed${NC}"
    echo "Response: $response"
fi
echo ""

# Test 6: Test Edge Function
echo -e "${BLUE}Test 6: Testing Edge Function...${NC}"
echo "Sending test request to generate-ai-report function..."

response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "${SUPABASE_URL}/functions/v1/generate-ai-report" \
  -H "Authorization: Bearer ${ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"breachId": 1}')

http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
response_body=$(echo "$response" | sed '/HTTP_CODE:/d')

if [[ $http_code == "200" ]]; then
    echo -e"${GREEN} Edge Function is working${NC}"
    echo "Response: $response_body"
elif [[ $http_code == "429" ]]; then
    echo -e"${YELLOW} Rate limit reached (this is normal)${NC}"
    echo "Response: $response_body"
elif [[ $http_code == "500" ]]; then
    echo -e"${RED} Edge Function error (check logs)${NC}"
    echo "Response: $response_body"
    echo "Check logs with: supabase functions logs generate-ai-report"
else
    echo -e"${RED} Unexpected response code: $http_code${NC}"
    echo "Response: $response_body"
fi
echo ""

# Test 7: Check frontend deployment
echo -e "${BLUE}Test 7: Checking frontend deployment...${NC}"
frontend_response=$(curl -s -o /dev/null -w "%{http_code}" "https://bd4l.github.io/Breaches/")
if [[ $frontend_response == "200" ]]; then
    echo -e"${GREEN} Frontend is accessible${NC}"
    echo "URL: https://bd4l.github.io/Breaches/"
else
    echo -e"${RED} Frontend not accessible (HTTP $frontend_response)${NC}"
fi
echo ""

# Test 8: Check for AI components in frontend
echo -e "${BLUE}Test 8: Checking for AI components...${NC}"
frontend_content=$(curl -s "https://bd4l.github.io/Breaches/")
if echo"$frontend_content"| grep -q"AI Report\|"; then
    echo -e"${GREEN} AI components appear to be deployed${NC}"
else
    echo -e"${YELLOW} AI components not found in frontend (may need redeployment)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}================================${NC}"

echo ""
echo -e"${GREEN} = Working correctly${NC}"
echo -e"${YELLOW} = Needs attention${NC}"
echo -e"${RED} = Requires fixing${NC}"
echo ""

echo "Next steps:"
echo"1. Fix any issues above"
echo"2. Address any warnings"
echo "3. Test the system manually at https://bd4l.github.io/Breaches/"
echo"4. Look for the AI Report buttons in the breach table"
echo "5. Try generating a report and verify it works end-to-end"
echo ""

echo -e"${GREEN} If all tests pass, your AI agent system is ready!${NC}"

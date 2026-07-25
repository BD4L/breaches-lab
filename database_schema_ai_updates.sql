-- AI Agent System Database Schema Updates
-- Run this in your Supabase SQL Editor to create AI report functionality

-- ============================================================================
-- 1. CREATE AI REPORTS TABLE (research_jobs)
-- ============================================================================

-- Create the research_jobs table for AI report generation
CREATE TABLE IF NOT EXISTS research_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scraped_item BIGINT NOT NULL REFERENCES scraped_items(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','completed','failed','cancelled')),
    report_url TEXT,
    requested_by UUID REFERENCES auth.users ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    -- AI-specific fields
    report_type TEXT DEFAULT 'ai_breach_analysis' CHECK (report_type IN ('ai_breach_analysis', 'manual_research', 'automated_summary')),
    markdown_content TEXT,
    html_content TEXT,
    processing_time_ms INTEGER,
    cost_estimate DECIMAL(10,4),
    metadata JSONB DEFAULT '{}',
    search_results_count INTEGER DEFAULT 0,
    scraped_urls_count INTEGER DEFAULT 0,
    ai_model_used TEXT DEFAULT 'gemini-2.5-flash',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_research_jobs_breach_id ON research_jobs(scraped_item);
CREATE INDEX IF NOT EXISTS idx_research_jobs_status ON research_jobs(status);
CREATE INDEX IF NOT EXISTS idx_research_jobs_report_type ON research_jobs(report_type);
CREATE INDEX IF NOT EXISTS idx_research_jobs_created_at ON research_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_research_jobs_requested_by ON research_jobs(requested_by);
CREATE INDEX IF NOT EXISTS idx_research_jobs_metadata ON research_jobs USING GIN(metadata);

-- ============================================================================
-- 3. CREATE AI REPORT USAGE TRACKING TABLE
-- ============================================================================

-- Track usage for rate limiting and analytics
CREATE TABLE IF NOT EXISTS ai_report_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users ON DELETE CASCADE,
    date DATE DEFAULT CURRENT_DATE,
    report_count INTEGER DEFAULT 0,
    total_cost DECIMAL(10,4) DEFAULT 0.00,
    total_processing_time_ms BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure one record per user per day
    UNIQUE(user_id, date)
);

-- Index for usage tracking
CREATE INDEX IF NOT EXISTS idx_ai_report_usage_user_date ON ai_report_usage(user_id, date);
CREATE INDEX IF NOT EXISTS idx_ai_report_usage_date ON ai_report_usage(date);

-- ============================================================================
-- 4. UPDATE ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Update RLS policies for research_jobs (they should already exist)
-- Allow users to view their own reports and anonymous reports
DROP POLICY IF EXISTS "Users can manage their own research jobs" ON research_jobs;
CREATE POLICY "Users can manage their own research jobs" ON research_jobs
    FOR ALL USING (
        auth.uid() = requested_by OR 
        requested_by IS NULL  -- Allow anonymous reports for now
    );

-- RLS for usage tracking
ALTER TABLE ai_report_usage ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own usage" ON ai_report_usage
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own usage" ON ai_report_usage
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can modify their own usage" ON ai_report_usage
    FOR UPDATE USING (auth.uid() = user_id);

-- ============================================================================
-- 5. CREATE HELPER FUNCTIONS
-- ============================================================================

-- Function to get or create daily usage record
CREATE OR REPLACE FUNCTION get_or_create_daily_usage(p_user_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    usage_id UUID;
BEGIN
    -- Try to get existing record for today
    SELECT id INTO usage_id
    FROM ai_report_usage
    WHERE user_id = p_user_id AND date = CURRENT_DATE;
    
    -- If not found, create new record
    IF usage_id IS NULL THEN
        INSERT INTO ai_report_usage (user_id, date, report_count, total_cost)
        VALUES (p_user_id, CURRENT_DATE, 0, 0.00)
        RETURNING id INTO usage_id;
    END IF;
    
    RETURN usage_id;
END;
$$;

-- Function to increment usage stats
CREATE OR REPLACE FUNCTION increment_usage_stats(
    p_user_id UUID,
    p_cost DECIMAL DEFAULT 0.00,
    p_processing_time_ms INTEGER DEFAULT 0
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Get or create today's usage record
    PERFORM get_or_create_daily_usage(p_user_id);
    
    -- Update the stats
    UPDATE ai_report_usage
    SET 
        report_count = report_count + 1,
        total_cost = total_cost + p_cost,
        total_processing_time_ms = total_processing_time_ms + p_processing_time_ms,
        updated_at = NOW()
    WHERE user_id = p_user_id AND date = CURRENT_DATE;
END;
$$;

-- Function to check daily rate limits
CREATE OR REPLACE FUNCTION check_daily_rate_limit(
    p_user_id UUID,
    p_max_reports INTEGER DEFAULT 10
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    current_count INTEGER;
BEGIN
    -- Get current report count for today
    SELECT COALESCE(report_count, 0) INTO current_count
    FROM ai_report_usage
    WHERE user_id = p_user_id AND date = CURRENT_DATE;
    
    -- Return true if under limit
    RETURN current_count < p_max_reports;
END;
$$;

-- ============================================================================
-- 6. CREATE VIEW FOR AI REPORTS DASHBOARD
-- ============================================================================

-- Enhanced view for AI reports with breach data
CREATE OR REPLACE VIEW v_ai_reports AS
SELECT 
    rj.id,
    rj.scraped_item as breach_id,
    rj.status,
    rj.report_type,
    rj.markdown_content,
    rj.html_content,
    rj.processing_time_ms,
    rj.cost_estimate,
    rj.metadata,
    rj.search_results_count,
    rj.scraped_urls_count,
    rj.ai_model_used,
    rj.requested_by,
    rj.created_at,
    rj.completed_at,
    rj.updated_at,
    rj.error_message,
    -- Include breach data
    vbd.organization_name,
    vbd.affected_individuals,
    vbd.source_name,
    vbd.source_type,
    vbd.breach_date,
    vbd.reported_date,
    vbd.what_was_leaked
FROM research_jobs rj
LEFT JOIN v_breach_dashboard vbd ON rj.scraped_item = vbd.id
WHERE rj.report_type = 'ai_breach_analysis';

-- ============================================================================
-- 7. CREATE TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================================================

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to research_jobs
DROP TRIGGER IF EXISTS update_research_jobs_updated_at ON research_jobs;
CREATE TRIGGER update_research_jobs_updated_at
    BEFORE UPDATE ON research_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to ai_report_usage
DROP TRIGGER IF EXISTS update_ai_report_usage_updated_at ON ai_report_usage;
CREATE TRIGGER update_ai_report_usage_updated_at
    BEFORE UPDATE ON ai_report_usage
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SCHEMA UPDATES COMPLETE
-- ============================================================================
--
-- Summary of changes:
-- Enhanced research_jobs table with AI-specific fields
-- Added ai_report_usage table for tracking and rate limiting
-- Created performance indexes
-- Updated RLS policies for security
-- Added helper functions for usage tracking and rate limiting
-- Created v_ai_reports view for dashboard
-- Added automatic timestamp triggers
--
-- The database is now ready for AI agent integration!

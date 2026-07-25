#!/usr/bin/env python3
"""
Setup Scraper Logging System

This script creates the necessary database tables for comprehensive scraper logging.
Run this script to set up the logging infrastructure in your Supabase database.

Usage:
    python setup_scraper_logging.py
"""

import os
import sys
import logging
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_scraper_logging_tables():
    """
    Create the scraper logging tables in Supabase.
    """
    try:
        # Initialize Supabase client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not url or not key:
            logger.error("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set")
            return False
            
        supabase = create_client(url, key)
        logger.info("Connected to Supabase")
        
        # Read the SQL schema file
        schema_file = "database_schema_scraper_logging.sql"
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
            
        with open(schema_file, 'r') as f:
            sql_content = f.read()
        
        logger.info("Loaded SQL schema file")
        
        # Split the SQL into individual statements
        statements = []
        current_statement = []
        
        for line in sql_content.split('\n'):
            # Skip comments and empty lines
            line = line.strip()
            if not line or line.startswith('--'):
                continue
                
            current_statement.append(line)
            
            # If line ends with semicolon, it's the end of a statement
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement.strip():
                    statements.append(statement)
                current_statement = []
        
        logger.info(f"Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        success_count = 0
        for i, statement in enumerate(statements, 1):
            try:
                # Skip certain statements that might not work via the API
                if any(skip_phrase in statement.upper() for skip_phrase in [
                    'CREATE OR REPLACE VIEW',
                    'CREATE OR REPLACE FUNCTION', 
                    'CREATE TRIGGER',
                    'DROP TRIGGER'
                ]):
                    logger.info(f"Skipping statement {i} (view/function/trigger): {statement[:50]}...")
                    continue
                    
                logger.info(f"Executing statement {i}: {statement[:50]}...")
                
                # Use the RPC function to execute raw SQL
                result = supabase.rpc('exec_sql', {'sql': statement}).execute()
                
                if result.data is not None:
                    success_count += 1
                    logger.info(f"Statement {i} executed successfully")
                else:
                    logger.warning(f"Statement {i} returned no data (might be normal)")
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to execute statement {i}: {e}")
                logger.error(f"   Statement: {statement[:100]}...")
                # Continue with other statements
        
        logger.info(f"Setup completed: {success_count}/{len(statements)} statements executed successfully")
        
        # Test the setup by trying to insert a test record
        try:
            test_data = {
                'scraper_name': 'setup_test',
                'status': 'completed',
                'items_processed': 0,
                'items_inserted': 0,
                'items_skipped': 0,
                'success': True
            }
            
            result = supabase.table('scraper_runs').insert(test_data).execute()
            
            if result.data:
                test_id = result.data[0]['id']
                logger.info("Test record inserted successfully")
                
                # Clean up test record
                supabase.table('scraper_runs').delete().eq('id', test_id).execute()
                logger.info("Test record cleaned up")
                
                return True
            else:
                logger.error("Failed to insert test record")
                return False
                
        except Exception as e:
            logger.error(f"Test insertion failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return False

def create_exec_sql_function():
    """
    Create a helper function in Supabase to execute raw SQL.
    This needs to be done manually in the Supabase SQL Editor.
    """
    sql_function = """
-- Create a function to execute raw SQL (run this in Supabase SQL Editor)
CREATE OR REPLACE FUNCTION exec_sql(sql TEXT)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    EXECUTE sql;
    RETURN 'OK';
EXCEPTION
    WHEN OTHERS THEN
        RETURN SQLERRM;
END;
$$;
"""
    
    logger.info("To complete the setup, run this function in your Supabase SQL Editor:")
    logger.info("=" * 60)
    logger.info(sql_function)
    logger.info("=" * 60)

if __name__ == "__main__":
    logger.info("Setting up Scraper Logging System...")
    
    # Check if we need to create the exec_sql function first
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if url and key:
            supabase = create_client(url, key)
            # Try to call the function to see if it exists
            try:
                supabase.rpc('exec_sql', {'sql': 'SELECT 1'}).execute()
                logger.info("exec_sql function is available")
                
                # Proceed with setup
                if setup_scraper_logging_tables():
                    logger.info("Scraper logging system setup completed successfully!")
                    logger.info("You can now use the ScraperLogger class in your scrapers.")
                else:
                    logger.error("Setup failed")
                    sys.exit(1)
                    
            except Exception:
                logger.warning("exec_sql function not found")
                create_exec_sql_function()
                logger.info("Please run the function above in Supabase SQL Editor, then run this script again.")
                
        else:
            logger.error("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Setup check failed: {e}")
        sys.exit(1)

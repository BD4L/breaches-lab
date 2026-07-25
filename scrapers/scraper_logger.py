#!/usr/bin/env python3
"""
Centralized Scraper Logging System

This module provides comprehensive logging for all scraper activities to Supabase,
including run tracking, performance metrics, and error reporting.

Usage:
    from scraper_logger import ScraperLogger
    
    logger = ScraperLogger("california_ag")
    logger.start_run()
    # ... scraper logic ...
    logger.end_run(success=True, items_processed=50, items_inserted=45)
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ScraperLogger:
    """
    Centralized logging system for scraper activities.
    Tracks runs, performance, errors, and statistics in Supabase.
    """
    
    def __init__(self, scraper_name: str, source_id: Optional[int] = None):
        """
        Initialize the scraper logger.
        
        Args:
            scraper_name: Name of the scraper (e.g., "california_ag", "delaware_ag")
            source_id: Optional source ID from data_sources table
        """
        self.scraper_name = scraper_name
        self.source_id = source_id
        self.run_id = None
        self.start_time = None
        self.supabase = None
        
        # Initialize Supabase client
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY")
            if url and key:
                self.supabase = create_client(url, key)
                logger.info(f"ScraperLogger initialized for {scraper_name}")
            else:
                logger.warning("Supabase credentials not found - logging will be disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
    
    def start_run(self, workflow_run_id: Optional[str] = None, 
                  github_actor: Optional[str] = None) -> Optional[str]:
        """
        Start a new scraper run and log it to the database.
        
        Args:
            workflow_run_id: GitHub Actions workflow run ID
            github_actor: GitHub username who triggered the run
            
        Returns:
            Run ID if successful, None if failed
        """
        if not self.supabase:
            logger.warning("Supabase not available - skipping run logging")
            return None
            
        try:
            self.start_time = datetime.now(timezone.utc)
            
            # Get GitHub Actions context
            github_context = self._get_github_context()
            if workflow_run_id:
                github_context['workflow_run_id'] = workflow_run_id
            if github_actor:
                github_context['github_actor'] = github_actor
            
            run_data = {
                'scraper_name': self.scraper_name,
                'source_id': self.source_id,
                'status': 'running',
                'started_at': self.start_time.isoformat(),
                'github_context': github_context,
                'environment': self._get_environment_info()
            }
            
            response = self.supabase.table('scraper_runs').insert(run_data).execute()
            
            if response.data:
                self.run_id = response.data[0]['id']
                logger.info(f"Started scraper run tracking: {self.scraper_name} (ID: {self.run_id})")
                return self.run_id
            else:
                logger.error("Failed to create scraper run record")
                return None
                
        except Exception as e:
            logger.error(f"Failed to start run logging: {e}")
            return None
    
    def log_progress(self, message: str, items_processed: int = 0, 
                    items_inserted: int = 0, items_skipped: int = 0,
                    current_page: Optional[int] = None, 
                    total_pages: Optional[int] = None) -> bool:
        """
        Log progress during scraper execution.
        
        Args:
            message: Progress message
            items_processed: Number of items processed so far
            items_inserted: Number of items successfully inserted
            items_skipped: Number of items skipped
            current_page: Current page being processed
            total_pages: Total pages to process
            
        Returns:
            True if logged successfully, False otherwise
        """
        if not self.supabase or not self.run_id:
            return False
            
        try:
            progress_data = {
                'run_id': self.run_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message': message,
                'items_processed': items_processed,
                'items_inserted': items_inserted,
                'items_skipped': items_skipped,
                'current_page': current_page,
                'total_pages': total_pages
            }
            
            response = self.supabase.table('scraper_progress').insert(progress_data).execute()
            
            if response.data:
                logger.info(f"Progress: {message} (Processed: {items_processed}, Inserted: {items_inserted})")
                return True
            else:
                logger.warning("Failed to log progress")
                return False
                
        except Exception as e:
            logger.error(f"Failed to log progress: {e}")
            return False
    
    def log_error(self, error_message: str, error_type: str = "general", 
                  context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Log an error during scraper execution.
        
        Args:
            error_message: Error message
            error_type: Type of error (e.g., "network", "parsing", "database")
            context: Additional context about the error
            
        Returns:
            True if logged successfully, False otherwise
        """
        if not self.supabase or not self.run_id:
            return False
            
        try:
            error_data = {
                'run_id': self.run_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error_type': error_type,
                'error_message': error_message,
                'context': context or {}
            }
            
            response = self.supabase.table('scraper_errors').insert(error_data).execute()
            
            if response.data:
                logger.error(f"Error logged: {error_type} - {error_message}")
                return True
            else:
                logger.warning("Failed to log error")
                return False
                
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
            return False
    
    def end_run(self, success: bool = True, items_processed: int = 0, 
               items_inserted: int = 0, items_skipped: int = 0,
               error_message: Optional[str] = None,
               performance_metrics: Optional[Dict[str, Any]] = None) -> bool:
        """
        End the scraper run and update the database with final statistics.
        
        Args:
            success: Whether the run was successful
            items_processed: Total items processed
            items_inserted: Total items successfully inserted
            items_skipped: Total items skipped
            error_message: Error message if run failed
            performance_metrics: Additional performance metrics
            
        Returns:
            True if logged successfully, False otherwise
        """
        if not self.supabase or not self.run_id:
            return False
            
        try:
            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - self.start_time).total_seconds() if self.start_time else 0
            
            update_data = {
                'status': 'completed' if success else 'failed',
                'completed_at': end_time.isoformat(),
                'duration_seconds': duration_seconds,
                'items_processed': items_processed,
                'items_inserted': items_inserted,
                'items_skipped': items_skipped,
                'success': success,
                'error_message': error_message,
                'performance_metrics': performance_metrics or {}
            }
            
            response = self.supabase.table('scraper_runs').update(update_data).eq('id', self.run_id).execute()
            
            if response.data:
                status_emoji =""if success else""
                logger.info(f"{status_emoji} Scraper run completed: {self.scraper_name}")
                logger.info(f"Final stats: {items_processed} processed, {items_inserted} inserted, {items_skipped} skipped")
                logger.info(f"Duration: {duration_seconds:.1f} seconds")
                return True
            else:
                logger.error("Failed to update scraper run record")
                return False
                
        except Exception as e:
            logger.error(f"Failed to end run logging: {e}")
            return False
    
    def _get_github_context(self) -> Dict[str, Any]:
        """Get GitHub Actions context information."""
        return {
            'github_actions': os.environ.get('GITHUB_ACTIONS') == 'true',
            'github_workflow': os.environ.get('GITHUB_WORKFLOW'),
            'github_run_id': os.environ.get('GITHUB_RUN_ID'),
            'github_run_number': os.environ.get('GITHUB_RUN_NUMBER'),
            'github_actor': os.environ.get('GITHUB_ACTOR'),
            'github_repository': os.environ.get('GITHUB_REPOSITORY'),
            'github_ref': os.environ.get('GITHUB_REF'),
            'github_sha': os.environ.get('GITHUB_SHA')
        }
    
    def _get_environment_info(self) -> Dict[str, Any]:
        """Get environment information."""
        return {
            'python_version': sys.version,
            'platform': sys.platform,
            'cwd': os.getcwd(),
            'env_vars': {
                key: value for key, value in os.environ.items() 
                if key.startswith(('CA_AG_', 'WA_AG_', 'HI_AG_', 'IN_AG_', 'IA_AG_', 'ME_AG_', 'MA_AG_', 'MT_AG_', 'ND_AG_', 'NH_AG_', 'NJ_AG_', 'OK_AG_', 'VT_AG_', 'WI_AG_', 'TX_AG_', 'MD_AG_'))
            }
        }

# Convenience function for simple logging
def log_scraper_activity(scraper_name: str, action: str, details: Dict[str, Any] = None):
    """
    Simple function to log scraper activity without full run tracking.
    
    Args:
        scraper_name: Name of the scraper
        action: Action being performed
        details: Additional details
    """
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            return
            
        supabase = create_client(url, key)
        
        activity_data = {
            'scraper_name': scraper_name,
            'action': action,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': details or {},
            'github_context': {
                'github_actions': os.environ.get('GITHUB_ACTIONS') == 'true',
                'github_workflow': os.environ.get('GITHUB_WORKFLOW'),
                'github_run_id': os.environ.get('GITHUB_RUN_ID')
            }
        }
        
        supabase.table('scraper_activities').insert(activity_data).execute()
        logger.info(f"Logged activity: {scraper_name} - {action}")
        
    except Exception as e:
        logger.error(f"Failed to log scraper activity: {e}")

#!/usr/bin/env python3
"""
California AG Breach Date Fix Script

This script fixes the breach date issue in existing California AG records by:
1. Extracting the original breach date text from tier_1_csv_data
2. Parsing the dates using the same logic as the scraper
3. Updating the breach_date field and raw_data_json with proper information

The issue: Most CA AG records have breach date info in the CSV data but it's not
being captured in the breach_date field due to field name variations and parsing issues.
"""

import os
import sys
import logging
from datetime import datetime
import re

# Add the parent directory to the path so we can import from utils and scrapers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.supabase_client import SupabaseClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_date_flexible(date_str):
    """
    Parse date string in various formats to YYYY-MM-DD format.
    Handles MM/DD/YYYY format from California AG CSV.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if not date_str or date_str.lower() in ['n/a', 'unknown', '']:
        return None

    # Handle multiple dates (take the first one)
    if ',' in date_str:
        date_str = date_str.split(',')[0].strip()

    # Common date formats for California AG
    date_formats = [
        '%m/%d/%Y',    # 03/03/2025 (most common in CA AG CSV)
        '%Y-%m-%d',    # 2025-03-03
        '%m-%d-%Y',    # 03-03-2025
        '%Y/%m/%d',    # 2025/03/03
    ]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}")
    return None

def parse_breach_dates(date_str):
    """
    Parse multiple breach dates from a comma-separated string.
    Returns list of YYYY-MM-DD formatted dates.
    """
    if not date_str or not isinstance(date_str, str):
        return []

    date_str = date_str.strip()
    if not date_str or date_str.lower() in ['n/a', 'unknown', '']:
        return []

    dates = []
    for date_part in date_str.split(','):
        date_part = date_part.strip()
        if date_part:
            parsed_date = parse_date_flexible(date_part)
            if parsed_date:
                dates.append(parsed_date)

    return dates

def fix_california_ag_breach_dates():
    """
    Fix breach date issues in existing California AG records.
    """
    logger.info("Starting California AG breach date fix...")
    
    # Initialize Supabase client
    supabase_client = SupabaseClient()
    
    # Get all California AG records that need fixing
    logger.info("Fetching California AG records from database...")
    
    try:
        # Get records in batches to avoid memory issues
        batch_size = 100
        offset = 0
        total_processed = 0
        total_fixed = 0
        
        while True:
            response = supabase_client.client.table("scraped_items").select(
                "id, title, breach_date, raw_data_json"
            ).eq("source_id", 4).range(offset, offset + batch_size - 1).execute()
            
            records = response.data if response.data else []
            if not records:
                break
                
            logger.info(f"Processing batch {offset//batch_size + 1}: {len(records)} records")
            
            for record in records:
                total_processed += 1
                record_id = record['id']
                title = record['title']
                current_breach_date = record['breach_date']
                raw_data_json = record.get('raw_data_json', {})
                
                # Extract original breach date text from CSV data
                tier_1_csv_data = raw_data_json.get('tier_1_csv_data', {})
                
                # Check both field name variants (with and without double space)
                original_breach_date_text = (
                    tier_1_csv_data.get('Date(s) of Breach  (if known)', '') or  # Double space
                    tier_1_csv_data.get('Date(s) of Breach (if known)', '') or   # Single space
                    ''
                )
                
                if not original_breach_date_text:
                    continue  # No breach date info available
                
                # Parse the breach dates
                parsed_breach_dates = parse_breach_dates(original_breach_date_text)
                
                # Determine if we need to update
                needs_update = False
                update_data = {}
                update_reasons = []
                
                # Check if we need to update the breach_date field
                if not current_breach_date and parsed_breach_dates:
                    update_data['breach_date'] = parsed_breach_dates[0]  # Use first parsed date
                    needs_update = True
                    update_reasons.append(f"added breach_date: {parsed_breach_dates[0]}")
                
                # Always update raw_data_json with enhanced breach date info
                if 'tier_2_enhanced' not in raw_data_json:
                    raw_data_json['tier_2_enhanced'] = {}
                
                # Update the enhanced data with breach date information
                raw_data_json['tier_2_enhanced']['breach_dates_original_text'] = original_breach_date_text
                raw_data_json['tier_2_enhanced']['breach_dates_all'] = parsed_breach_dates
                raw_data_json['tier_2_enhanced']['breach_dates_parsing_success'] = len(parsed_breach_dates) > 0
                raw_data_json['tier_2_enhanced']['breach_date_fix_timestamp'] = datetime.now().isoformat()
                
                # Update scraper version to indicate this fix
                raw_data_json['scraper_version'] = '4.2_breach_date_fix'
                
                update_data['raw_data_json'] = raw_data_json
                needs_update = True
                update_reasons.append("updated raw_data_json with breach date info")
                
                if needs_update:
                    try:
                        update_response = supabase_client.client.table("scraped_items").update(update_data).eq("id", record_id).execute()
                        if update_response.data:
                            total_fixed += 1
                            logger.info(f"Fixed record {record_id} ({title}): {','.join(update_reasons)}")
                            if original_breach_date_text and parsed_breach_dates:
                                logger.debug(f"   Original: '{original_breach_date_text}' -> Parsed: {parsed_breach_dates}")
                        else:
                            logger.warning(f"Failed to update record {record_id}")
                    except Exception as e:
                        logger.error(f"Error updating record {record_id}: {e}")
                
                # Log progress every 100 records
                if total_processed % 100 == 0:
                    logger.info(f"Progress: {total_processed} processed, {total_fixed} fixed")
            
            offset += batch_size
        
        logger.info(f"California AG breach date fix completed!")
        logger.info(f"Total records processed: {total_processed}")
        logger.info(f"Total records fixed: {total_fixed}")
        logger.info(f"Fix rate: {total_fixed/total_processed*100:.1f}%")
        
    except Exception as e:
        logger.error(f"Error during breach date fix: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = fix_california_ag_breach_dates()
    if success:
        logger.info("California AG breach date fix completed successfully!")
    else:
        logger.error("California AG breach date fix failed!")
        sys.exit(1)

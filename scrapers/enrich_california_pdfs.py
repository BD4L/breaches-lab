#!/usr/bin/env python3
"""
California AG PDF Enrichment Service

This service runs separately from the main scraper to analyze PDFs for breaches
that have already been collected. It finds records with PDF URLs and enriches
them with detailed analysis.

Usage:
    python3 scrapers/enrich_california_pdfs.py [--limit N] [--org-name "Name"]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import time
import random

# Add the parent directory to the path so we can import from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_client import SupabaseClient
from scrapers.fetch_california_ag import analyze_pdf_content, rate_limit_delay

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_records_with_pdfs(supabase_client: SupabaseClient, limit: int = None, org_name: str = None) -> list:
    """
    Find California AG breach records that have PDF URLs but haven't been analyzed yet.
    """
    try:
        # Build query to find records with PDF URLs that need analysis
        query = supabase_client.client.table("scraped_items").select("*")

        # Filter for California AG records (source_id = 4)
        query = query.eq("source_id", 4)

        # Filter for records that have PDF URLs in raw_data_json
        # This is a bit complex with Supabase, so we'll fetch and filter in Python

        if org_name:
            query = query.ilike("title", f"%{org_name}%")

        if limit:
            query = query.limit(limit)

        response = query.execute()

        # Filter for records that have PDF URLs but haven't been fully analyzed
        records_with_pdfs = []
        for record in response.data:
            raw_data = record.get('raw_data_json', {})

            # Check if this record has PDF URLs that need analysis
            tier_2_data = raw_data.get('tier_2_enhanced', {}).get('tier_2_detail', {})
            pdf_links = tier_2_data.get('pdf_links', [])

            # Check if PDFs exist but haven't been analyzed
            tier_3_data = raw_data.get('tier_2_enhanced', {}).get('tier_3_pdf_analysis', [])
            needs_analysis = False

            if pdf_links:
                # Check if any PDFs haven't been analyzed
                for i in range(len(pdf_links)):
                    if i >= len(tier_3_data) or not tier_3_data[i].get('pdf_analyzed', False):
                        needs_analysis = True
                        break

            if needs_analysis:
                record['_pdf_links'] = pdf_links  # Add for easy access
                records_with_pdfs.append(record)

        logger.info(f"Found {len(records_with_pdfs)} records with PDFs needing analysis")
        return records_with_pdfs

    except Exception as e:
        logger.error(f"Error finding records with PDFs: {e}")
        return []

def enrich_record_with_pdf_analysis(supabase_client: SupabaseClient, record: dict) -> bool:
    """
    Enrich a single record with PDF analysis.
    """
    try:
        record_id = record['id']
        org_name = record['title']
        pdf_links = record.get('_pdf_links', [])

        logger.info(f"Enriching {org_name} with {len(pdf_links)} PDF(s)")

        # Get current raw_data_json
        raw_data = record.get('raw_data_json', {})

        # Ensure the structure exists
        if 'tier_2_enhanced' not in raw_data:
            raw_data['tier_2_enhanced'] = {}

        # Analyze each PDF with robust error handling
        pdf_analyses = []
        successful_analyses = 0
        failed_analyses = 0

        for i, pdf_link in enumerate(pdf_links):
            logger.info(f"  Analyzing PDF {i+1}/{len(pdf_links)}: {pdf_link.get('title', 'Unknown')}")

            try:
                # Add rate limiting
                rate_limit_delay()

                # Analyze the PDF
                pdf_analysis = analyze_pdf_content(pdf_link['url'])
                pdf_analysis['pdf_title'] = pdf_link.get('title', 'Unknown')
                pdf_analysis['pdf_url'] = pdf_link['url']
                pdf_analysis['analysis_timestamp'] = datetime.now().isoformat()

                pdf_analyses.append(pdf_analysis)

                # Log results
                if pdf_analysis.get('pdf_analyzed', False):
                    data_types = pdf_analysis.get('data_types_compromised', [])
                    logger.info(f"Analysis complete. Data types: {data_types}")
                    successful_analyses += 1
                else:
                    error = pdf_analysis.get('error', 'Unknown error')
                    logger.warning(f"Analysis failed but PDF info preserved: {error}")
                    failed_analyses += 1

            except Exception as pdf_error:
                # CRITICAL: Even if PDF analysis completely fails, we preserve the PDF info
                logger.error(f"PDF analysis exception: {pdf_error}")
                failed_analyses += 1

                # Still add the PDF info but mark as failed
                pdf_analyses.append({
                    'pdf_analyzed': False,
                    'pdf_title': pdf_link.get('title', 'Unknown'),
                    'pdf_url': pdf_link['url'],
                    'analysis_timestamp': datetime.now().isoformat(),
                    'error': str(pdf_error),
                    'skip_reason': 'PDF analysis exception - info preserved'
                })

        logger.info(f"  PDF analysis summary: {successful_analyses} successful, {failed_analyses} failed")

        # Update the record with PDF analysis
        raw_data['tier_2_enhanced']['tier_3_pdf_analysis'] = pdf_analyses
        raw_data['tier_2_enhanced']['pdf_enrichment_timestamp'] = datetime.now().isoformat()

        # Update the record in the database
        update_data = {
            'raw_data_json': raw_data,
            'updated_at': datetime.now().isoformat()
        }

        # Also extract key data to top-level fields if available
        all_data_types = set()
        for analysis in pdf_analyses:
            if analysis.get('data_types_compromised'):
                all_data_types.update(analysis['data_types_compromised'])

        if all_data_types:
            update_data['data_types_compromised'] = list(all_data_types)

        # Update the record
        response = supabase_client.client.table("scraped_items").update(update_data).eq("id", record_id).execute()

        if response.data:
            logger.info(f"Successfully enriched {org_name}")
            return True
        else:
            logger.error(f"Failed to update {org_name}")
            return False

    except Exception as e:
        logger.error(f"Error enriching record {record.get('title', 'Unknown')}: {e}")
        return False

def main():
    """
    Main function for PDF enrichment service.
    """
    parser = argparse.ArgumentParser(description='California AG PDF Enrichment Service')
    parser.add_argument('--limit', type=int, help='Limit number of records to process')
    parser.add_argument('--org-name', type=str, help='Filter by organization name (partial match)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without doing it')

    args = parser.parse_args()

    logger.info("California AG PDF Enrichment Service Started")
    logger.info(f"Limit: {args.limit or 'No limit'}")
    logger.info(f"Organization filter: {args.org_name or 'None'}")
    logger.info(f"Dry run: {args.dry_run}")

    try:
        # Initialize Supabase client
        supabase_client = SupabaseClient()
        logger.info("Supabase client initialized")

        # Find records that need PDF analysis
        records = find_records_with_pdfs(supabase_client, args.limit, args.org_name)

        if not records:
            logger.info("No records found that need PDF analysis")
            return

        if args.dry_run:
            logger.info("DRY RUN - Would process these records:")
            for record in records:
                pdf_count = len(record.get('_pdf_links', []))
                logger.info(f"  - {record['title']} ({pdf_count} PDFs)")
            return

        # Process each record
        success_count = 0
        for i, record in enumerate(records, 1):
            logger.info(f"Processing record {i}/{len(records)}")

            if enrich_record_with_pdf_analysis(supabase_client, record):
                success_count += 1

            # Add delay between records to be respectful
            if i < len(records):
                time.sleep(random.uniform(3, 7))

        logger.info(f"PDF enrichment complete: {success_count}/{len(records)} records successfully processed")

    except Exception as e:
        logger.error(f"PDF enrichment service failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

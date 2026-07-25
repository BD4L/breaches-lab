#!/usr/bin/env python3
"""
Database Change Tracker for Breach Scraping

This script tracks database changes before and after scraper runs to provide
comprehensive reporting on new breaches, news articles, and affected individuals.

Usage:
  python database_change_tracker.py --snapshot    # Take pre-scraping snapshot
  python database_change_tracker.py --report      # Generate post-scraping report
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Snapshot file location - can be overridden via environment variable
SNAPSHOT_FILE = os.environ.get('SNAPSHOT_FILE', '/tmp/scraper_snapshot.json')

# Source types that count as breaches vs news when categorising the dashboard view.
BREACH_SOURCE_TYPES = [
    'State AG', 'Government Portal', 'Breach Database',
    'State Cybersecurity', 'State Agency', 'API',
    'Federal Portal', 'Regulatory Filing'
]
NEWS_SOURCE_TYPES = ['News Feed', 'Company IR', 'RSS Feed']


def _summarise_source_groups(groups):
    """
    Turn per-source aggregates into the dashboard statistics.

    groups is a list of {source_type, source_name, item_count, affected_sum}. Every strategy in
    fetch_source_groups() produces this same shape, so the resulting numbers do not depend on
    which one ran.
    """
    source_type_counts = {}
    source_counts = {}
    breach_count = 0
    news_count = 0
    total_affected = 0

    for group in groups:
        source_type = group.get('source_type') or 'Unknown'
        source_name = group.get('source_name') or 'Unknown'
        item_count = group.get('item_count') or 0
        affected_sum = group.get('affected_sum') or 0

        source_type_counts[source_type] = source_type_counts.get(source_type, 0) + item_count
        source_counts[source_name] = source_counts.get(source_name, 0) + item_count

        if source_type in BREACH_SOURCE_TYPES:
            breach_count += item_count
            total_affected += affected_sum
        elif source_type in NEWS_SOURCE_TYPES:
            news_count += item_count
        else:
            logger.warning(f"Unknown source type: '{source_type}' from {source_name}")

    return {
        'breach_count': breach_count,
        'news_count': news_count,
        'total_affected': total_affected,
        'by_source_type': source_type_counts,
        'by_source': source_counts,
    }


def fetch_source_groups(supabase):
    """
    Fetch per-source counts and affected-individual sums.

    Tries progressively cheaper-to-support strategies and returns on the first that works:

      1. The get_dashboard_stats() RPC, if it has been created. One round trip.
      2. A PostgREST grouped aggregate, which returns one row per source rather than one row
         per item. Supported on current Supabase.
      3. Paginating the whole view and grouping client-side.

    Strategy 3 is the original behaviour and is kept only as a last resort. It downloads every
    row in the view on every call, and this function is called twice per workflow run across
    three scheduled workflows, which is the single largest consumer of the free tier's 5 GB
    monthly egress allowance.
    """
    # 1. Purpose-built RPC.
    try:
        response = supabase.rpc('get_dashboard_stats', {}).execute()
        if response.data:
            rows = response.data if isinstance(response.data, list) else [response.data]
            groups = [
                {
                    'source_type': r.get('source_type'),
                    'source_name': r.get('source_name'),
                    'item_count': r.get('item_count'),
                    'affected_sum': r.get('affected_sum'),
                }
                for r in rows
            ]
            logger.info(f"Source groups via get_dashboard_stats() RPC ({len(groups)} groups)")
            return groups
    except Exception as e:
        logger.debug(f"get_dashboard_stats() RPC unavailable, falling back: {e}")

    # 2. Grouped aggregate. Non-aggregate columns in the select form the GROUP BY.
    try:
        response = supabase.table("v_breach_dashboard").select(
            "source_type, source_name, item_count:count(), affected_sum:affected_individuals.sum()"
        ).execute()
        if response.data:
            logger.info(f"Source groups via grouped aggregate ({len(response.data)} groups)")
            return response.data
    except Exception as e:
        logger.debug(f"Grouped aggregate unavailable, falling back to full scan: {e}")

    # 3. Full scan. Correct, but downloads the entire view.
    logger.warning(
        "Falling back to a full scan of v_breach_dashboard. This transfers every row on every "
        "call. Create the get_dashboard_stats() RPC from database_schema_dashboard_stats.sql "
        "to avoid it."
    )
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        response = supabase.table("v_breach_dashboard").select(
            "source_type, source_name, affected_individuals"
        ).order("source_name").range(offset, offset + page_size - 1).execute()
        rows = response.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    grouped = {}
    for item in all_rows:
        key = (item.get('source_type'), item.get('source_name'))
        entry = grouped.setdefault(key, {
            'source_type': key[0], 'source_name': key[1], 'item_count': 0, 'affected_sum': 0
        })
        entry['item_count'] += 1
        entry['affected_sum'] += item.get('affected_individuals') or 0

    logger.info(f"Source groups via full scan ({len(all_rows)} rows -> {len(grouped)} groups)")
    return list(grouped.values())


def get_database_stats():
    """
    Get comprehensive database statistics.
    """
    try:
        # Import here to avoid issues if not available
        from supabase import create_client, Client
        
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        stats = {}
        
        logger.info("Fetching database statistics...")
        
        # Overall counts from scraped_items table
        response = supabase.table("scraped_items").select("*", count="exact", head=True).execute()
        stats['total_items'] = response.count or 0
        logger.info(f"Total items in database: {stats['total_items']}")
        
        # Per-source aggregates, computed in the database where possible.
        logger.info("Fetching breach dashboard aggregates for categorization...")

        source_groups = fetch_source_groups(supabase)

        if not source_groups:
            logger.warning("No data returned from v_breach_dashboard")
            stats['breach_count'] = 0
            stats['news_count'] = 0
            stats['total_affected'] = 0
            stats['by_source_type'] = {}
            stats['by_source'] = {}
        else:
            stats.update(_summarise_source_groups(source_groups))
            logger.info(
                f"Categorized: {stats['breach_count']} breaches, {stats['news_count']} news, "
                f"{stats['total_affected']} affected"
            )
        
        # Recent items (last 24 hours)
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        response = supabase.table("scraped_items").select("*", count="exact", head=True).gte('scraped_at', yesterday).execute()
        stats['recent_items'] = response.count or 0
        
        # Today's items
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        response = supabase.table("scraped_items").select("*", count="exact", head=True).gte('scraped_at', today).execute()
        stats['today_items'] = response.count or 0
        
        stats['timestamp'] = datetime.now().isoformat()
        
        logger.info("Database statistics collected successfully")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def take_snapshot():
    """
    Take a snapshot of current database state.
    """
    logger.info("Taking database snapshot...")
    
    stats = get_database_stats()
    if not stats:
        logger.error("Failed to get database statistics")
        return False
        
    try:
        with open(SNAPSHOT_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Snapshot saved to {SNAPSHOT_FILE}")
        logger.info(f"Current totals: {stats['total_items']} items, {stats['breach_count']} breaches, {stats['news_count']} news")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}")
        return False

def generate_report():
    """
    Generate a report comparing current state to snapshot.
    """
    logger.info("Generating database change report...")
    
    # Load snapshot
    try:
        with open(SNAPSHOT_FILE, 'r') as f:
            before_stats = json.load(f)
    except FileNotFoundError:
        logger.error("No snapshot file found. Run with --snapshot first.")
        return False
    except Exception as e:
        logger.error(f"Failed to load snapshot: {e}")
        return False
    
    # Get current stats
    after_stats = get_database_stats()
    if not after_stats:
        logger.error("Failed to get current database statistics")
        return False
    
    # Calculate changes
    changes = {
        'total_items': after_stats['total_items'] - before_stats['total_items'],
        'breach_count': after_stats['breach_count'] - before_stats['breach_count'],
        'news_count': after_stats['news_count'] - before_stats['news_count'],
        'total_affected': after_stats['total_affected'] - before_stats['total_affected'],
        'recent_items': after_stats['recent_items'] - before_stats.get('recent_items', 0),
        'today_items': after_stats['today_items'] - before_stats.get('today_items', 0)
    }
    
    # Calculate source-specific changes
    source_changes = {}
    for source, after_count in after_stats['by_source'].items():
        before_count = before_stats['by_source'].get(source, 0)
        change = after_count - before_count
        if change > 0:
            source_changes[source] = change
    
    # Calculate source type changes
    source_type_changes = {}
    for source_type, after_count in after_stats['by_source_type'].items():
        before_count = before_stats['by_source_type'].get(source_type, 0)
        change = after_count - before_count
        if change > 0:
            source_type_changes[source_type] = change
    
    # Generate report
    print("\n" + "="*80)
    print("BREACH SCRAPING RESULTS SUMMARY")
    print("="*80)
    
    print(f"Scraping Period: {before_stats['timestamp']} {after_stats['timestamp']}")
    print()
    
    # Overall changes
    print("OVERALL CHANGES:")
    print(f"Total Items: {before_stats['total_items']:,} {after_stats['total_items']:,} (+{changes['total_items']:,})")
    print(f"Breach Records: {before_stats['breach_count']:,} {after_stats['breach_count']:,} (+{changes['breach_count']:,})")
    print(f"News Articles: {before_stats['news_count']:,} {after_stats['news_count']:,} (+{changes['news_count']:,})")
    print(f"People Affected: {before_stats['total_affected']:,} {after_stats['total_affected']:,} (+{changes['total_affected']:,})")
    print()
    
    # Source type breakdown
    if source_type_changes:
        print("NEW ITEMS BY CATEGORY:")
        for source_type, count in sorted(source_type_changes.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source_type}: +{count:,}")
        print()
    
    # Individual source breakdown
    if source_changes:
        print("NEW ITEMS BY SOURCE:")
        for source, count in sorted(source_changes.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source}: +{count:,}")
        print()
    
    # Summary
    if changes['total_items'] > 0:
        print("SCRAPING SUCCESS!")
        print(f"{changes['total_items']:,} new items discovered")
        if changes['breach_count'] > 0:
            print(f"{changes['breach_count']:,} new breach notifications")
        if changes['news_count'] > 0:
            print(f"{changes['news_count']:,} new news articles")
        if changes['total_affected'] > 0:
            print(f"{changes['total_affected']:,} additional people affected")
    elif changes['total_items'] < 0:
        print("DATABASE CLEANUP DETECTED")
        print(f"{abs(changes['total_items']):,} items removed (likely duplicates)")
        if changes['breach_count'] < 0:
            print(f"{abs(changes['breach_count']):,} duplicate breaches removed")
        if changes['news_count'] > 0:
            print(f"{changes['news_count']:,} new news articles added")
        if changes['total_affected'] > 0:
            print(f"{changes['total_affected']:,} people affected (from new items)")
    else:
        print("ℹ NO NEW ITEMS FOUND")
        print("   All sources appear to be up-to-date")
    
    print("="*80)
    
    # Set GitHub Actions output with improved validation
    if os.environ.get('GITHUB_ACTIONS'):
        try:
            github_output_file = os.environ.get('GITHUB_OUTPUT', '/dev/null')
            logger.info(f"Writing GitHub Actions outputs to: {github_output_file}")
            
            # Ensure all values are integers
            new_items = int(changes.get('total_items', 0))
            new_breaches = int(changes.get('breach_count', 0))
            new_news = int(changes.get('news_count', 0))
            new_affected = int(changes.get('total_affected', 0))
            
            with open(github_output_file, 'a') as f:
                f.write(f"new_items={new_items}\n")
                f.write(f"new_breaches={new_breaches}\n")
                f.write(f"new_news={new_news}\n")
                f.write(f"new_affected={new_affected}\n")
            
            logger.info(f"GitHub outputs set: items={new_items}, breaches={new_breaches}, news={new_news}, affected={new_affected}")
            
        except Exception as e:
            logger.error(f"Failed to write GitHub Actions outputs: {e}")
            # Write default values to prevent workflow failures
            with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
                f.write("new_items=0\n")
                f.write("new_breaches=0\n")
                f.write("new_news=0\n")
                f.write("new_affected=0\n")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python database_change_tracker.py --snapshot    # Take pre-scraping snapshot")
        print("  python database_change_tracker.py --report      # Generate post-scraping report")
        sys.exit(1)
    
    if sys.argv[1] == "--snapshot":
        success = take_snapshot()
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "--report":
        success = generate_report()
        sys.exit(0 if success else 1)
    else:
        print("Invalid argument. Use --snapshot or --report")
        sys.exit(1)

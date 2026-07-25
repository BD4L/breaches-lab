#!/usr/bin/env python3
"""
Daily Change Tracker for Breach Scraping

This script tracks database changes for a 24-hour period from 1am to 1am,
providing comprehensive daily reporting on new breaches and affected individuals.

Usage:
  python daily_change_tracker.py --today      # Show today's changes (1am to now)
  python daily_change_tracker.py --yesterday  # Show yesterday's changes (1am to 1am)
  python daily_change_tracker.py --report     # Show both today and yesterday
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

def get_daily_stats(start_time: datetime, end_time: datetime):
    """
    Get database statistics for a specific time period.
    """
    try:
        # Import here to avoid issues if not available
        from supabase import create_client, Client
        
        SUPABASE_URL = os.environ.get("SUPABASE_URL")
        SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()
        
        stats = {
            'period_start': start_iso,
            'period_end': end_iso,
            'period_hours': (end_time - start_time).total_seconds() / 3600
        }
        
        # Items added during this period
        response = supabase.table("scraped_items").select("*", count="exact", head=True).gte('scraped_at', start_iso).lt('scraped_at', end_iso).execute()
        stats['new_items'] = response.count or 0
        
        # Get detailed breakdown by source type for this period
        response = supabase.table("v_breach_dashboard").select("source_type, source_name, affected_individuals").gte('scraped_at', start_iso).lt('scraped_at', end_iso).execute()
        
        source_type_counts = {}
        source_counts = {}
        total_affected = 0
        breach_count = 0
        news_count = 0
        
        for item in response.data or []:
            source_type = item.get('source_type', 'Unknown')
            source_name = item.get('source_name', 'Unknown')
            affected = item.get('affected_individuals', 0) or 0
            
            # Count by source type
            source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
            
            # Count by individual source
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
            
            # Track affected individuals
            total_affected += affected
            
            # Categorize as breach or news
            if source_type in ['State AG', 'Government Portal', 'Breach Database', 'State Cybersecurity', 'State Agency', 'API']:
                breach_count += 1
            elif source_type in ['News Feed', 'Company IR']:
                news_count += 1
        
        stats['by_source_type'] = source_type_counts
        stats['by_source'] = source_counts
        stats['new_breaches'] = breach_count
        stats['new_news'] = news_count
        stats['new_affected'] = total_affected
        
        # Get top affected breaches for this period
        response = supabase.table("v_breach_dashboard").select("organization_name, affected_individuals, source_name").gte('scraped_at', start_iso).lt('scraped_at', end_iso).order('affected_individuals', desc=True).limit(10).execute()
        
        stats['top_breaches'] = []
        for item in response.data or []:
            affected = item.get('affected_individuals', 0)
            if affected and affected > 0:  # Only include breaches with affected individuals
                stats['top_breaches'].append({
                    'organization': item.get('organization_name', 'Unknown'),
                    'affected': affected,
                    'source': item.get('source_name', 'Unknown')
                })

        # Limit to top 5
        stats['top_breaches'] = stats['top_breaches'][:5]
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get daily stats: {e}")
        return None

def get_today_1am():
    """Get today's 1am timestamp."""
    now = datetime.now()
    today_1am = now.replace(hour=1, minute=0, second=0, microsecond=0)
    
    # If it's currently before 1am, use yesterday's 1am
    if now.hour < 1:
        today_1am = today_1am - timedelta(days=1)
    
    return today_1am

def get_yesterday_period():
    """Get yesterday's 1am to 1am period."""
    today_1am = get_today_1am()
    yesterday_1am = today_1am - timedelta(days=1)
    return yesterday_1am, today_1am

def get_today_period():
    """Get today's 1am to now period."""
    today_1am = get_today_1am()
    now = datetime.now()
    return today_1am, now

def format_daily_report(stats: Dict[str, Any], title: str):
    """Format a daily report for display."""
    if not stats:
        return f"\n {title}: No data available\n"
    
    period_hours = stats.get('period_hours', 0)
    
    report = f"\n{'='*80}\n"
    report += f"{title}\n"
    report += f"{'='*80}\n"
    report += f"Period: {stats['period_start'][:19]} {stats['period_end'][:19]} ({period_hours:.1f} hours)\n\n"
    
    # Overall summary
    report += f"DAILY SUMMARY:\n"
    report += f"Total New Items: {stats['new_items']:,}\n"
    report += f"New Breaches: {stats['new_breaches']:,}\n"
    report += f"New News: {stats['new_news']:,}\n"
    report += f"People Affected: {stats['new_affected']:,}\n\n"
    
    # Source type breakdown
    if stats['by_source_type']:
        report += f"BY CATEGORY:\n"
        for source_type, count in sorted(stats['by_source_type'].items(), key=lambda x: x[1], reverse=True):
            report += f"   {source_type}: {count:,}\n"
        report += "\n"
    
    # Top sources
    if stats['by_source']:
        report += f"TOP SOURCES:\n"
        top_sources = sorted(stats['by_source'].items(), key=lambda x: x[1], reverse=True)[:10]
        for source, count in top_sources:
            report += f"   {source}: {count:,}\n"
        report += "\n"
    
    # Top affected breaches
    if stats['top_breaches']:
        report += f"LARGEST BREACHES:\n"
        for breach in stats['top_breaches']:
            report += f"   {breach['organization']}: {breach['affected']:,} people ({breach['source']})\n"
        report += "\n"
    
    # Performance metrics
    if stats['new_items'] > 0:
        items_per_hour = stats['new_items'] / max(period_hours, 1)
        report += f"METRICS:\n"
        report += f"   Items per hour: {items_per_hour:.1f}\n"
        if stats['new_affected'] > 0:
            avg_affected = stats['new_affected'] / max(stats['new_breaches'], 1)
            report += f"   Avg affected per breach: {avg_affected:,.0f}\n"
        report += "\n"
    
    return report

def show_today():
    """Show today's changes (1am to now)."""
    logger.info("Generating today's change report...")
    
    start_time, end_time = get_today_period()
    stats = get_daily_stats(start_time, end_time)
    
    if not stats:
        print("Failed to get today's statistics")
        return False
    
    report = format_daily_report(stats, "TODAY'S BREACH ACTIVITY")
    print(report)
    
    # Set GitHub Actions output if running in CI
    if os.environ.get('GITHUB_ACTIONS'):
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"today_new_items={stats['new_items']}\n")
            f.write(f"today_new_breaches={stats['new_breaches']}\n")
            f.write(f"today_new_news={stats['new_news']}\n")
            f.write(f"today_new_affected={stats['new_affected']}\n")
    
    return True

def show_yesterday():
    """Show yesterday's changes (1am to 1am)."""
    logger.info("Generating yesterday's change report...")
    
    start_time, end_time = get_yesterday_period()
    stats = get_daily_stats(start_time, end_time)
    
    if not stats:
        print("Failed to get yesterday's statistics")
        return False
    
    report = format_daily_report(stats, "YESTERDAY'S BREACH ACTIVITY")
    print(report)
    
    return True

def show_report():
    """Show both today and yesterday reports."""
    logger.info("Generating comprehensive daily report...")
    
    success = True
    
    # Yesterday's report
    success &= show_yesterday()
    
    # Today's report
    success &= show_today()
    
    # Summary comparison
    yesterday_start, yesterday_end = get_yesterday_period()
    today_start, today_end = get_today_period()
    
    yesterday_stats = get_daily_stats(yesterday_start, yesterday_end)
    today_stats = get_daily_stats(today_start, today_end)
    
    if yesterday_stats and today_stats:
        print("\n" + "="*80)
        print("DAY-OVER-DAY COMPARISON")
        print("="*80)
        print(f"Items: {yesterday_stats['new_items']:,} {today_stats['new_items']:,} ({today_stats['new_items'] - yesterday_stats['new_items']:+,})")
        print(f"Breaches: {yesterday_stats['new_breaches']:,} {today_stats['new_breaches']:,} ({today_stats['new_breaches'] - yesterday_stats['new_breaches']:+,})")
        print(f"News: {yesterday_stats['new_news']:,} {today_stats['new_news']:,} ({today_stats['new_news'] - yesterday_stats['new_news']:+,})")
        print(f"Affected: {yesterday_stats['new_affected']:,} {today_stats['new_affected']:,} ({today_stats['new_affected'] - yesterday_stats['new_affected']:+,})")
        print("="*80)
    
    return success

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python daily_change_tracker.py --today      # Show today's changes (1am to now)")
        print("  python daily_change_tracker.py --yesterday  # Show yesterday's changes (1am to 1am)")
        print("  python daily_change_tracker.py --report     # Show both today and yesterday")
        sys.exit(1)
    
    if sys.argv[1] == "--today":
        success = show_today()
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "--yesterday":
        success = show_yesterday()
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "--report":
        success = show_report()
        sys.exit(0 if success else 1)
    else:
        print("Invalid argument. Use --today, --yesterday, or --report")
        sys.exit(1)

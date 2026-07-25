#!/usr/bin/env python3
"""
Setup email preferences for GitHub Actions - run this once to enable email alerts
"""

import os
import sys
from datetime import datetime

def setup_github_email_preferences():
    """Set up email preferences for the repository owner"""
    
    try:
        from utils.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Email from environment or default
        email = os.getenv('ALERT_TO_EMAIL', 'autsy42@gmail.com')  # Your email
        
        print(f"Setting up email preferences for GitHub Actions")
        print(f"Email: {email}")
        
        # Create comprehensive user preferences for all breach types
        user_prefs = {
            'user_id': 'github_actions',
            'email': email,
            'email_verified': True,  # Mark as verified
            'threshold': 0,  # Alert for ALL breaches (no minimum threshold)
            'alert_frequency': 'immediate',
            'email_format': 'html',
            'include_summary': True,
            'include_links': True,
            'max_alerts_per_day': 100,  # High limit for comprehensive coverage
            'notify_high_impact': True,
            'notify_critical_sectors': True,
            'notify_local_breaches': True,
            'source_types': [
                'State AG',
                'Government Portal', 
                'News Feed',
                'RSS Feed',
                'API Feed',
                'Breach Database',
                'State Cybersecurity',
                'State Agency',
                'Federal Portal',
                'Regulatory Filing',
                'Company IR'
            ],  # ALL source types
            'keywords': [],  # No keyword filtering - get all breaches
            'updated_at': datetime.now().isoformat()
        }
        
        # Insert/update preferences
        response = supabase.table('user_prefs').upsert(user_prefs).execute()
        
        if response.data:
            print(f"Email preferences set successfully!")
            print(f"Configuration:")
            print(f"   • Email: {email}")
            print(f"   • Threshold: 0 (all breaches)")
            print(f"   • All source types enabled")
            print(f"   • Max alerts per day: 100")
            
            # Test the matching function
            print(f"\n Testing alert matching function...")
            test_response = supabase.rpc('match_alert_recipients', {
                'p_source_id': 1,
                'p_source_type': 'State AG',
                'p_affected': 1000,
                'p_title': 'Test Organization Data Breach',
                'p_data_types': ['PII', 'SSN'],
                'p_what_leaked': 'Personal information including names, addresses, SSNs'
            }).execute()
            
            if test_response.data and len(test_response.data) > 0:
                print(f"Alert matching works! Found {len(test_response.data)} recipients")
                for recipient in test_response.data:
                    print(f"{recipient.get('user_email')} (threshold: {recipient.get('threshold')})")
            else:
                print(f"Alert matching test found no recipients")
                print(f"   This might indicate an issue with the match_alert_recipients function")
            
            return True
        else:
            print(f"Failed to create user preferences")
            return False
            
    except Exception as e:
        print(f"Error setting up preferences: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("GitHub Actions Email Preferences Setup")
    print("=" * 60)
    
    if setup_github_email_preferences():
        print(f"\n Email preferences setup complete!")
        print(f"\n Email alerts will now be sent when:")
        print(f"New breaches are found by any scraper")
        print(f"new_breaches > 0 in GitHub Actions output")
        print(f"RESEND_API_KEY is valid")
        print(f"Breach matches user preferences (currently: ALL)")
        
        print(f"\n Monitor at:")
        print(f"   • GitHub Actions: https://github.com/BD4L/Breaches/actions")
        print(f"   • Workflow: 'Parallel State Portal Scrapers'")
        print(f"• Look for'Email Alert Notifications'job")
    else:
        print(f"\n Setup failed!")
        sys.exit(1)
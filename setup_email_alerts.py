#!/usr/bin/env python3
"""
Email Alerts Setup Script

This script helps you set up and test the email alert system for your breach dashboard.
It will guide you through:
1. Setting up environment variables
2. Testing the Resend API
3. Creating user preferences
4. Testing the complete email flow

Usage:
    python setup_email_alerts.py
"""

import os
import sys
import json
import logging
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment_variables():
    """Check if all required environment variables are set"""
    logger.info("Checking environment variables...")
    
    required_vars = {
        'SUPABASE_URL': os.environ.get('SUPABASE_URL'),
        'SUPABASE_SERVICE_KEY': os.environ.get('SUPABASE_SERVICE_KEY'),
        'RESEND_API_KEY': os.environ.get('RESEND_API_KEY'),
    }
    
    optional_vars = {
        'ALERT_FROM_EMAIL': os.environ.get('ALERT_FROM_EMAIL', 'alerts@yourdomain.com'),
        'DASHBOARD_URL': os.environ.get('DASHBOARD_URL', 'https://bd4l.github.io/Breaches/')
    }
    
    missing_vars = []
    for var, value in required_vars.items():
        if not value:
            missing_vars.append(var)
            logger.error(f"{var} is not set")
        else:
            logger.info(f"{var} is set: {value[:10]}...")
    
    for var, value in optional_vars.items():
        logger.info(f"ℹ {var}: {value}")
    
    if missing_vars:
        logger.error(f"\n Missing required environment variables: {','.join(missing_vars)}")
        logger.info("\n To set them:")
        logger.info("export SUPABASE_URL='your-supabase-url'")
        logger.info("export SUPABASE_SERVICE_KEY='your-service-key'")
        logger.info("export RESEND_API_KEY='your-resend-api-key'")
        logger.info("export ALERT_FROM_EMAIL='alerts@yourdomain.com'  # Optional")
        return False
    
    return True

def test_resend_api(test_email: str):
    """Test if Resend API is working"""
    logger.info("Testing Resend API...")
    
    resend_api_key = os.environ.get('RESEND_API_KEY')
    from_email = os.environ.get('ALERT_FROM_EMAIL', 'alerts@yourdomain.com')
    
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": from_email,
        "to": [test_email],
        "subject":"Breach Dashboard Email Setup Test",
        "html": f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;"> Email System Test</h2>
            <p>This is a test email from your Breach Dashboard email alert system.</p>
            <div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin: 16px 0;">
                <p><strong>Timestamp:</strong> {datetime.now().isoformat()}</p>
                <p><strong>From Email:</strong> {from_email}</p>
                <p><strong>Test Email:</strong> {test_email}</p>
            </div>
            <p>If you received this email, your Resend integration is working correctly! </p>
            <hr style="margin: 24px 0; border: none; border-top: 1px solid #e5e7eb;">
            <p style="color: #6b7280; font-size: 14px;">
                This is an automated test email from your Breach Dashboard setup.
            </p>
        </div>
        """,
        "text": f"""
Email System Test - {datetime.now().isoformat()}

From Email: {from_email}
Test Email: {test_email}

If you received this email, your Resend integration is working correctly!

This is an automated test email from your Breach Dashboard setup.
        """
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Test email sent successfully!")
            logger.info(f"Message ID: {result.get('id')}")
            return True
        else:
            logger.error(f"Email failed to send (Status: {response.status_code})")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        return False

def test_database_connection():
    """Test database connection and functions"""
    logger.info("Testing database connection...")
    
    try:
        from utils.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Test basic connection
        response = supabase.table('data_sources').select('id, name').limit(1).execute()
        logger.info(f"Database connection successful")
        
        # Test match_alert_recipients function
        logger.info("Testing match_alert_recipients function...")
        response = supabase.rpc('match_alert_recipients', {
            'p_source_id': 1,
            'p_source_type': 'State AG',
            'p_affected': 1000,
            'p_title': 'Test Organization',
            'p_data_types': ['PII'],
            'p_what_leaked': 'Personal information'
        }).execute()
        
        logger.info(f"match_alert_recipients function works")
        logger.info(f"Found {len(response.data)} potential recipients")
        
        return True
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return False

def create_test_user_preferences(email: str):
    """Create test user preferences for email alerts"""
    logger.info(f"Creating test user preferences for {email}...")
    
    try:
        from utils.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        # Create or update user preferences
        user_prefs = {
            'user_id': 'anonymous',  # Using anonymous for testing
            'email': email,
            'email_verified': True,  # Mark as verified for testing
            'threshold': 0,  # Alert for all breaches
            'alert_frequency': 'immediate',
            'email_format': 'html',
            'include_summary': True,
            'include_links': True,
            'max_alerts_per_day': 10,
            'notify_high_impact': True,
            'notify_critical_sectors': True,
            'notify_local_breaches': False,
            'source_types': ['State AG', 'Government Portal', 'News Feed'],  # All types
            'keywords': [],
            'updated_at': datetime.now().isoformat()
        }
        
        response = supabase.table('user_prefs').upsert(user_prefs).execute()
        
        if response.data:
            logger.info(f"Test user preferences created successfully")
            logger.info(f"Preferences: threshold=0, all source types, verified email")
            return True
        else:
            logger.error(f"Failed to create user preferences")
            return False
            
    except Exception as e:
        logger.error(f"Error creating user preferences: {e}")
        return False

def test_email_alert_flow(test_email: str):
    """Test the complete email alert flow"""
    logger.info("Testing complete email alert flow...")
    
    try:
        from scrapers.email_alerts import BreachEmailAlerts
        
        # Initialize email alerts system
        alerts = BreachEmailAlerts()
        
        # Get recent breaches (last 24 hours)
        new_breaches = alerts.get_new_breaches_for_alerts(since_minutes=1440)  # 24 hours
        
        logger.info(f"Found {len(new_breaches)} recent breaches")
        
        if not new_breaches:
            logger.warning("No recent breaches found to test with")
            logger.info("Try running some scrapers first to get test data")
            return False
        
        # Test with the first breach
        test_breach = new_breaches[0]
        logger.info(f"Testing with breach: {test_breach.get('organization_name','Unknown')}")
        
        # Get alert recipients
        recipients = alerts.get_alert_recipients(test_breach)
        logger.info(f"Found {len(recipients)} potential recipients")
        
        if not recipients:
            logger.warning("No recipients found - check user preferences")
            return False
        
        # Test email creation
        user_prefs = {'email_format': 'html', 'include_summary': True, 'include_links': True}
        email_content = alerts.create_email_content(test_breach, user_prefs)
        
        logger.info("Email content created successfully")
        logger.info(f"Subject: {email_content['subject']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Email alert flow test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("Breach Dashboard Email Alerts Setup")
    print("=" * 50)
    
    # Get test email from user
    test_email = input("\n Enter your email address for testing:").strip()
    if not test_email or '@' not in test_email:
        print("Invalid email address")
        sys.exit(1)
    
    print(f"\n Setting up email alerts for: {test_email}")
    
    # Step 1: Check environment variables
    print("\n1⃣ Checking Environment Variables...")
    if not check_environment_variables():
        print("\n Environment setup incomplete. Please set the required variables and try again.")
        sys.exit(1)
    
    # Step 2: Test Resend API
    print("\n2⃣ Testing Resend API...")
    if not test_resend_api(test_email):
        print("\n Resend API test failed. Check your API key and from email.")
        sys.exit(1)
    
    # Step 3: Test database connection
    print("\n3⃣ Testing Database Connection...")
    if not test_database_connection():
        print("\n Database test failed. Check your Supabase credentials.")
        sys.exit(1)
    
    # Step 4: Create test user preferences
    print("\n4⃣ Creating Test User Preferences...")
    if not create_test_user_preferences(test_email):
        print("\n Failed to create user preferences.")
        sys.exit(1)
    
    # Step 5: Test complete email flow
    print("\n5⃣ Testing Complete Email Flow...")
    test_email_alert_flow(test_email)  # This might fail if no recent breaches
    
    # Success!
    print("\n Email Alert System Setup Complete!")
    print("\n Summary:")
    print(f"Environment variables configured")
    print(f"Resend API working")
    print(f"Database connection successful")
    print(f"Test user preferences created for {test_email}")
    print(f"Test email sent successfully")
    
    print("\n Next Steps:")
    print("   1. Wait for scrapers to find new breaches")
    print("   2. Check your email for breach alerts")
    print("   3. Use the frontend to manage your preferences")
    print("   4. Add the email workflow to your GitHub Actions")
    
    print(f"\n Dashboard URL: {os.environ.get('DASHBOARD_URL','https://bd4l.github.io/Breaches/')}")

if __name__ == "__main__":
    main()

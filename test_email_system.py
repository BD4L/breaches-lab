#!/usr/bin/env python3
"""
Test script to verify Resend email system is working
"""

import os
import sys
import requests
from datetime import datetime

def test_resend_api():
    """Test if Resend API is working with current configuration"""
    
    # Check environment variables
    resend_api_key = os.getenv('RESEND_API_KEY')
    from_email = os.getenv('ALERT_FROM_EMAIL', 'alerts@yourdomain.com')
    
    if not resend_api_key:
        print("RESEND_API_KEY environment variable not found")
        return False
    
    print(f"RESEND_API_KEY found: {resend_api_key[:10]}...")
    print(f"FROM_EMAIL: {from_email}")
    
    # Test email payload
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": from_email,
        "to": ["autsy42@gmail.com"],  # Your test email
        "subject":"Breach Dashboard Email Test",
        "html": """
        <h2> Email System Test</h2>
        <p>This is a test email from your Breach Dashboard email alert system.</p>
        <p><strong>Timestamp:</strong> {}</p>
        <p>If you received this email, your Resend integration is working correctly!</p>
        """.format(datetime.now().isoformat()),
        "text": f"Email System Test - {datetime.now().isoformat()}\n\nIf you received this email, your Resend integration is working correctly!"
    }
    
    try:
        print("Sending test email...")
        response = requests.post(url, headers=headers, json=payload)
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Email sent successfully!")
            print(f"Message ID: {result.get('id')}")
            return True
        else:
            print(f"Email failed to send")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def test_database_functions():
    """Test if database functions are working"""
    try:
        from utils.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        
        print("Testing database functions...")
        
        # Test match_alert_recipients function
        response = supabase.rpc('match_alert_recipients', {
            'p_source_id': 1,
            'p_source_type': 'State AG',
            'p_affected': 1000,
            'p_title': 'Test Organization',
            'p_data_types': ['PII'],
            'p_what_leaked': 'Personal information'
        }).execute()
        
        print(f"match_alert_recipients function works")
        print(f"Found {len(response.data)} potential recipients")
        
        for recipient in response.data:
            print(f"{recipient.get('user_email')} (threshold: {recipient.get('threshold')})")
        
        return True
        
    except Exception as e:
        print(f"Database function test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Breach Dashboard Email System")
    print("=" * 50)
    
    # Test 1: Resend API
    print("\n1⃣ Testing Resend API...")
    resend_works = test_resend_api()
    
    # Test 2: Database functions
    print("\n2⃣ Testing Database Functions...")
    db_works = test_database_functions()
    
    # Summary
    print("\n TEST SUMMARY:")
    print(f"Resend API: {'Working'if resend_works else'Failed'}")
    print(f"Database Functions: {'Working'if db_works else'Failed'}")
    
    if resend_works and db_works:
        print("\n Email system is ready to work!")
        print("Next steps:")
        print("   1. Make sure your email (autsy42@gmail.com) is verified in user_prefs")
        print("   2. Wait for new breaches to be detected by scrapers")
        print("   3. Check your email for breach alerts")
    else:
        print("\n Email system needs fixes before it will work")
        
    sys.exit(0 if (resend_works and db_works) else 1)

#!/usr/bin/env python3
"""
Email Alert System for Breach Dashboard
Integrates with Resend for email delivery and Supabase for user preferences
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests

# Import SupabaseClient with fallback path handling
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BreachEmailAlerts:
    def __init__(self):
        self.supabase_client = SupabaseClient()
        self.supabase = self.supabase_client.client
        self.resend_api_key = os.getenv('RESEND_API_KEY')
        self.from_email = os.getenv('ALERT_FROM_EMAIL', 'alerts@yourdomain.com')
        self.dashboard_url = os.getenv('DASHBOARD_URL', 'https://bd4l.github.io/Breaches/')
        
        if not self.resend_api_key:
            raise ValueError("RESEND_API_KEY environment variable is required")
    
    def get_new_breaches_for_alerts(self, since_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get new breaches that might trigger alerts"""
        since_time = datetime.now() - timedelta(minutes=since_minutes)
        
        try:
            response = self.supabase.table('v_breach_dashboard').select(
                'id, organization_name, affected_individuals, source_name, source_type, '
                'breach_date, reported_date, what_was_leaked, notice_document_url, '
                'item_url, scraped_at, publication_date'
            ).gte('scraped_at', since_time.isoformat()).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching new breaches: {e}")
            return []
    
    def get_alert_recipients(self, breach: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get users who should receive alerts for this breach"""
        try:
            # Use the existing match_alert_recipients function
            response = self.supabase.rpc('match_alert_recipients', {
                'p_source_id': breach.get('source_id'),
                'p_source_type': breach.get('source_type'),
                'p_affected': breach.get('affected_individuals', 0),
                'p_title': breach.get('organization_name', ''),
                'p_data_types': breach.get('data_types_compromised', []),
                'p_what_leaked': breach.get('what_was_leaked', '')
            }).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting alert recipients: {e}")
            return []
    
    def check_alert_already_sent(self, user_id: str, breach_id: int, alert_type: str = 'immediate') -> bool:
        """Check if alert was already sent to prevent duplicates"""
        try:
            response = self.supabase.table('alert_history').select('id').eq(
                'user_id', user_id
            ).eq('breach_id', breach_id).eq('alert_type', alert_type).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking alert history: {e}")
            return False
    
    def create_email_content(self, breach: Dict[str, Any], user_prefs: Dict[str, Any]) -> Dict[str, str]:
        """Create email content based on breach data and user preferences"""
        org_name = breach.get('organization_name', 'Unknown Organization')
        affected = breach.get('affected_individuals')
        source = breach.get('source_name', 'Unknown Source')
        
        # Subject line
        if affected and affected > 0:
            subject = f"Breach Alert: {org_name} - {self.format_affected_count(affected)} people affected"
        else:
            subject = f"Breach Alert: {org_name} - New incident reported"
        
        # HTML email content
        html_content = self.create_html_email(breach, user_prefs)
        
        # Text email content
        text_content = self.create_text_email(breach, user_prefs)
        
        return {
            'subject': subject,
            'html': html_content,
            'text': text_content
        }
    
    def format_affected_count(self, count: Optional[int]) -> str:
        """Format affected individuals count for display"""
        if not count:
            return "Unknown number of"
        
        if count >= 1000000:
            return f"{count/1000000:.1f}M"
        elif count >= 1000:
            return f"{count/1000:.0f}K"
        else:
            return f"{count:,}"
    
    def create_html_email(self, breach: Dict[str, Any], user_prefs: Dict[str, Any]) -> str:
        """Create HTML email template"""
        org_name = breach.get('organization_name', 'Unknown Organization')
        affected = breach.get('affected_individuals')
        source = breach.get('source_name', 'Unknown Source')
        breach_date = breach.get('breach_date')
        reported_date = breach.get('reported_date')
        what_leaked = breach.get('what_was_leaked', '')
        notice_url = breach.get('notice_document_url')
        item_url = breach.get('item_url')
        
        # Severity color based on affected count
        if affected and affected >= 100000:
            severity_color = "#dc2626"  # red
            severity_text = "CRITICAL"
        elif affected and affected >= 10000:
            severity_color = "#ea580c"  # orange
            severity_text = "HIGH"
        elif affected and affected >= 1000:
            severity_color = "#ca8a04"  # yellow
            severity_text = "MEDIUM"
        else:
            severity_color = "#059669"  # green
            severity_text = "LOW"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Breach Alert</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                <h1 style="margin: 0; font-size: 24px;"> Breach Alert</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">New security incident detected</p>
            </div>
            
            <!-- Severity Badge -->
            <div style="text-align: center; margin-bottom: 30px;">
                <span style="background-color: {severity_color}; color: white; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px;">
                    {severity_text} IMPACT
                </span>
            </div>
            
            <!-- Main Content -->
            <div style="background: #f8f9fa; padding: 30px; border-radius: 10px; margin-bottom: 30px;">
                <h2 style="margin: 0 0 20px 0; color: #1f2937; font-size: 20px;">{org_name}</h2>
                
                <div style="display: grid; gap: 15px;">
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                        <strong>People Affected:</strong>
                        <span style="color: {severity_color}; font-weight: bold;">
                            {self.format_affected_count(affected) if affected else 'Unknown'}
                        </span>
                    </div>
                    
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb;">
                        <strong>Source:</strong>
                        <span>{source}</span>
                    </div>
                    
                    {f'<div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb;"><strong>Breach Date:</strong><span>{breach_date}</span></div>' if breach_date else ''}
                    
                    {f'<div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb;"><strong>Reported Date:</strong><span>{reported_date}</span></div>' if reported_date else ''}
                </div>
                
                {f'<div style="margin-top: 20px;"><strong>Data Compromised:</strong><p style="margin: 10px 0; padding: 15px; background: white; border-radius: 5px; border-left: 4px solid {severity_color};">{what_leaked}</p></div>' if what_leaked else ''}
            </div>
            
            <!-- Action Buttons -->
            <div style="text-align: center; margin-bottom: 30px;">
                <a href="{self.dashboard_url}" style="background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 0 10px; display: inline-block;">
                    View Dashboard
                </a>
                
                {f'<a href="{notice_url}" style="background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 0 10px; display: inline-block;">View Notice</a>' if notice_url else ''}
                
                {f'<a href="{item_url}" style="background: #0891b2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 0 10px; display: inline-block;">Source Page</a>' if item_url else ''}
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px;">
                <p>You're receiving this alert because you've subscribed to breach notifications.</p>
                <p>
                    <a href="{self.dashboard_url}#preferences" style="color: #4f46e5;">Manage Preferences</a> | 
                    <a href="{self.dashboard_url}#unsubscribe" style="color: #4f46e5;">Unsubscribe</a>
                </p>
                <p style="margin-top: 15px; font-size: 12px;">
                    Breach Dashboard • Automated Security Intelligence
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def create_text_email(self, breach: Dict[str, Any], user_prefs: Dict[str, Any]) -> str:
        """Create plain text email content"""
        org_name = breach.get('organization_name', 'Unknown Organization')
        affected = breach.get('affected_individuals')
        source = breach.get('source_name', 'Unknown Source')
        breach_date = breach.get('breach_date', 'Unknown')
        what_leaked = breach.get('what_was_leaked', 'Details not available')
        
        text = f"""
 BREACH ALERT

Organization: {org_name}
People Affected: {self.format_affected_count(affected) if affected else 'Unknown'}
Source: {source}
Breach Date: {breach_date}

Data Compromised:
{what_leaked}

View full details: {self.dashboard_url}

---
You're receiving this alert because you've subscribed to breach notifications.
Manage preferences: {self.dashboard_url}#preferences
Unsubscribe: {self.dashboard_url}#unsubscribe
        """
        
        return text.strip()

    def send_email_via_resend(self, to_email: str, subject: str, html_content: str, text_content: str) -> Dict[str, Any]:
        """Send email using Resend API"""
        url = "https://api.resend.com/emails"

        headers = {
            "Authorization": f"Bearer {self.resend_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
            "tags": [
                {"name": "category", "value": "breach-alert"},
                {"name": "source", "value": "automated"}
            ]
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Email sent successfully to {to_email}, Message ID: {result.get('id')}")
            return {"success": True, "message_id": result.get('id'), "error": None}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return {"success": False, "message_id": None, "error": str(e)}

    def record_alert_sent(self, user_id: str, breach_id: int, message_id: str, alert_type: str = 'immediate'):
        """Record that an alert was sent to prevent duplicates"""
        try:
            self.supabase.table('alert_history').insert({
                'user_id': user_id,
                'breach_id': breach_id,
                'alert_type': alert_type,
                'resend_message_id': message_id,
                'email_status': 'sent'
            }).execute()
        except Exception as e:
            logger.error(f"Error recording alert history: {e}")

    def process_breach_alerts(self, since_minutes: int = 30) -> Dict[str, int]:
        """Main function to process and send breach alerts"""
        logger.info(f"Processing breach alerts for last {since_minutes} minutes")

        stats = {
            'new_breaches': 0,
            'alerts_sent': 0,
            'errors': 0
        }

        # Get new breaches
        new_breaches = self.get_new_breaches_for_alerts(since_minutes)
        stats['new_breaches'] = len(new_breaches)

        if not new_breaches:
            logger.info("No new breaches found")
            return stats

        logger.info(f"Found {len(new_breaches)} new breaches")

        for breach in new_breaches:
            try:
                # Get users who should receive alerts for this breach
                recipients = self.get_alert_recipients(breach)

                for recipient in recipients:
                    user_id = recipient.get('user_id')
                    user_email = recipient.get('user_email')

                    if not user_email:
                        continue

                    # Check if alert already sent
                    if self.check_alert_already_sent(user_id, breach['id']):
                        logger.info(f"Alert already sent to {user_email} for breach {breach['id']}")
                        continue

                    # Get user preferences
                    user_prefs = self.get_user_preferences(user_id)
                    if not user_prefs or not user_prefs.get('email_verified'):
                        continue

                    # Create email content
                    email_content = self.create_email_content(breach, user_prefs)

                    # Send email
                    result = self.send_email_via_resend(
                        user_email,
                        email_content['subject'],
                        email_content['html'],
                        email_content['text']
                    )

                    if result['success']:
                        # Record alert sent
                        self.record_alert_sent(user_id, breach['id'], result['message_id'])
                        stats['alerts_sent'] += 1
                        logger.info(f"Alert sent to {user_email} for breach: {breach.get('organization_name')}")
                    else:
                        stats['errors'] += 1
                        logger.error(f"Failed to send alert to {user_email}: {result['error']}")

            except Exception as e:
                logger.error(f"Error processing breach {breach.get('id')}: {e}")
                stats['errors'] += 1

        logger.info(f"Alert processing complete: {stats}")
        return stats

    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user email preferences"""
        try:
            response = self.supabase.table('user_prefs').select('*').eq('user_id', user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return None


def main():
    """Main function for running email alerts"""
    import argparse

    parser = argparse.ArgumentParser(description='Send breach email alerts')
    parser.add_argument('--since-minutes', type=int, default=30,
                       help='Check for breaches in the last N minutes (default: 30)')
    parser.add_argument('--test-email', type=str,
                       help='Send a test email to specified address')
    parser.add_argument('--source', help='Source name for logging (used by GitHub Actions)')
    parser.add_argument('--new-count', type=int, help='Number of new breaches (used by GitHub Actions)')

    args = parser.parse_args()

    try:
        alerts = BreachEmailAlerts()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Make sure RESEND_API_KEY environment variable is set")
        return

    if args.test_email:
        # Send test email
        test_breach = {
            'id': 999999,
            'organization_name': 'Test Organization',
            'affected_individuals': 50000,
            'source_name': 'Test Source',
            'source_type': 'State AG',
            'breach_date': '2025-01-01',
            'what_was_leaked': 'Names, email addresses, phone numbers, and encrypted passwords',
            'notice_document_url': 'https://example.com/notice.pdf',
            'item_url': 'https://example.com/breach-details'
        }

        email_content = alerts.create_email_content(test_breach, {})
        result = alerts.send_email_via_resend(
            args.test_email,
            email_content['subject'],
            email_content['html'],
            email_content['text']
        )

        if result['success']:
            print(f"Test email sent successfully to {args.test_email}")
            print(f"Message ID: {result.get('message_id')}")
        else:
            print(f"Failed to send test email: {result['error']}")
    else:
        # Process real alerts
        if args.source and args.new_count:
            print(f"Processing alerts for {args.new_count} new breaches from {args.source}")

        stats = alerts.process_breach_alerts(args.since_minutes)
        print(f"Alert Summary:")
        print(f"   New breaches: {stats['new_breaches']}")
        print(f"   Alerts sent: {stats['alerts_sent']}")
        print(f"   Errors: {stats['errors']}")

        if stats['new_breaches'] == 0:
            print("ℹ No new breaches found - no alerts to send")
        elif stats['alerts_sent'] == 0:
            print("ℹ No users matched alert criteria - no alerts sent")
        else:
            print(f"Successfully sent {stats['alerts_sent']} email alerts!")


if __name__ == "__main__":
    main()

# Email Alert System Setup Guide

This guide walks you through setting up the email alert system for your breach dashboard using Resend and Supabase.

## Quick Setup

### 1. Create Resend Account

1. Go to [resend.com](https://resend.com) and sign up
2. Verify your domain (or use their test domain for development)
3. Create an API key in the dashboard
4. Note your API key (starts with `re_`)

### 2. Configure GitHub Secrets

Add these secrets to your GitHub repository:

```
RESEND_API_KEY=re_your_api_key_here
ALERT_FROM_EMAIL=alerts@yourdomain.com
```

**To add secrets:**
1. Go to your GitHub repo Settings Secrets and variables Actions
2. Click "New repository secret"
3. Add each secret

### 3. Update Database Schema

Run the enhanced database schema in your Supabase SQL editor:

```sql
-- The schema has been updated in database_schema.sql
-- Run the new user_prefs, alert_history, and email_verification_tokens tables
```

### 4. Test the System

Test email sending:

```bash
# Test email (replace with your email)
python scrapers/email_alerts.py --test-email your@email.com
```

## How It Works

### Email Alert Flow

1. **Scrapers run** every 30 minutes via GitHub Actions
2. **New breaches detected** by database change tracker
3. **Email alerts job** processes new breaches
4. **User preferences checked** for each breach
5. **Emails sent** via Resend API
6. **Alert history recorded** to prevent duplicates

### User Preference Matching

The system uses your existing `match_alert_recipients()` function to determine who gets alerts based on:

- **Threshold**: Minimum affected people count
- **Source types**: State AG, Government Portal, etc.
- **Keywords**: Organization names or data types
- **Data types**: PII, PHI, financial data, etc.

### Email Templates

- **HTML emails**: Rich formatting with severity colors
- **Text emails**: Plain text fallback
- **Responsive design**: Works on mobile and desktop
- **Unsubscribe links**: GDPR compliant

## Frontend Integration

### Add Email Preferences to Dashboard

1. Import the EmailPreferences component:

```typescript
import { EmailPreferences } from '../components/preferences/EmailPreferences'
```

2. Add to your admin controls or user menu:

```typescript
const [showEmailPrefs, setShowEmailPrefs] = useState(false)

// In your JSX:
<Button onClick={() => setShowEmailPrefs(true)}>
  Email Preferences
</Button>

{showEmailPrefs && (
  <EmailPreferences onClose={() => setShowEmailPrefs(false)} />
)}
```

### User Authentication (Future)

Currently uses 'anonymous' user. For production:

1. Implement Supabase Auth
2. Replace 'anonymous' with actual user IDs
3. Add email verification flow
4. Add user registration/login

## Configuration Options

### Alert Frequency

- **Immediate**: Send alerts as breaches are discovered
- **Daily**: Send digest of daily breaches
- **Weekly**: Send weekly summary

### Notification Types

- **High Impact**: Breaches affecting 10,000+ people
- **Critical Sectors**: Healthcare, finance, government
- **Keywords**: Custom organization or data type alerts

### Rate Limiting

- **Max alerts per day**: Prevent spam (default: 10)
- **Duplicate prevention**: Alert history tracking
- **Bounce handling**: Resend handles automatically

## Monitoring & Analytics

### Email Delivery Tracking

Resend provides:
- Delivery confirmations
- Bounce notifications
- Click tracking
- Open rates

### Alert Statistics

Monitor in your dashboard:
- Alerts sent per day
- Most common breach types
- User engagement metrics

## Security & Compliance

### Email Verification

- Required before sending alerts
- Verification token system
- Secure token expiration

### GDPR Compliance

- Unsubscribe links in all emails
- User data deletion on request
- Consent tracking

### Rate Limiting

- Per-user daily limits
- API rate limiting
- Abuse prevention

## Testing

### Test Email Templates

```bash
# Send test email
python scrapers/email_alerts.py --test-email test@example.com
```

### Test Alert Logic

```bash
# Process alerts for last hour
python scrapers/email_alerts.py --since-minutes 60
```

### Verify Database

```sql
-- Check alert history
SELECT * FROM alert_history ORDER BY created_at DESC LIMIT 10;

-- Check user preferences
SELECT * FROM user_prefs;

-- Check email verification status
SELECT email, email_verified FROM user_prefs;
```

## Advanced Features (Future)

### Digest Emails

- Daily breach summaries
- Weekly trend reports
- Monthly statistics

### Multi-Channel Alerts

- Slack webhooks
- Discord notifications
- SMS alerts (via Twilio)

### Smart Filtering

- AI-powered relevance scoring
- Industry-specific alerts
- Geographic filtering

### Analytics Dashboard

- Email performance metrics
- User engagement tracking
- Alert effectiveness analysis

## Troubleshooting

### Common Issues

**Emails not sending:**
- Check RESEND_API_KEY is set
- Verify domain configuration
- Check Resend dashboard for errors

**No alerts received:**
- Verify email preferences are saved
- Check threshold settings
- Ensure email is verified

**Duplicate alerts:**
- Alert history should prevent this
- Check database constraints
- Review alert logic

### Debug Commands

```bash
# Check recent breaches
python -c "
from scrapers.email_alerts import BreachEmailAlerts
alerts = BreachEmailAlerts()
breaches = alerts.get_new_breaches_for_alerts(60)
print(f'Found {len(breaches)} breaches in last hour')
"

# Check user preferences
python -c "
from utils.supabase_client import get_supabase_client
supabase = get_supabase_client()
prefs = supabase.table('user_prefs').select('*').execute()
print(f'Found {len(prefs.data)} user preferences')
"
```

## Support

For issues:
1. Check GitHub Actions logs
2. Review Resend dashboard
3. Check Supabase logs
4. Test with debug commands above

The email alert system is designed to be reliable, scalable, and user-friendly while integrating seamlessly with your existing breach monitoring infrastructure.

#!/usr/bin/env python3
"""
events_alerts.py
- Connects to PostgreSQL via db_utils
- Queries events matching specific criteria
- Sends results as professional HTML email
- Logs to rotating logfile
"""

from src.db_utils import get_db_connection
from decouple import config
from sqlalchemy import text
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import smtplib
from email.message import EmailMessage
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
import pymsteams
from typing import Union, List

# -----------------------------
# Project Structure
# -----------------------------
# Get the project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = PROJECT_ROOT / 'queries'
LOGS_DIR = PROJECT_ROOT / 'logs'
DATA_DIR = PROJECT_ROOT / 'data'
MEDIA_DIR = PROJECT_ROOT / 'media'

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

# -----------------------------
# Configuration from .env
# -----------------------------
SMTP_HOST = config('SMTP_HOST')
SMTP_PORT = int(config('SMTP_PORT', default=465))
SMTP_USER = config('SMTP_USER')
SMTP_PASS = config('SMTP_PASS')

INTERNAL_RECIPIENTS = [s.strip() for s in config('INTERNAL_RECIPIENTS', '').split(',') if s.strip()]
ENABLE_SPECIAL_TEAMS_EMAIL_ALERT = config('ENABLE_SPECIAL_TEAMS_EMAIL_ALERT', default=False)
SPECIAL_TEAMS_EMAIL = config('SPECIAL_TEAMS_EMAIL', '').strip()

TEAMS_WEBHOOK_URL = config('TEAMS_WEBHOOK_URL', default='')
ENABLE_TEAMS_ALERTS = config('ENABLE_TEAMS_ALERTS', default=False, cast=bool)
ENABLE_EMAIL_ALERTS = config('ENABLE_EMAIL_ALERTS', default=True, cast=bool)

COMPANY_NAME = config('COMPANY_NAME', default='Company')
COMPANY_LOGO = MEDIA_DIR / config('COMPANY_LOGO', default='')
ST_COMPANY_LOGO = MEDIA_DIR / config('ST_COMPANY_LOGO', default='')

LOG_FILE = LOGS_DIR / config('LOG_FILE', default='events_alerts.log')
LOG_MAX_BYTES = int(config('LOG_MAX_BYTES', default=10_485_760))  # 10MB
LOG_BACKUP_COUNT = int(config('LOG_BACKUP_COUNT', default=5))

# Query configuration (can be moved to .env if needed)
EVENT_TYPE_ID = int(config('EVENT_TYPE_ID', default=18))
EVENT_NAME_FILTER = config('EVENT_NAME_FILTER', default='hot')
EVENT_LOOKBACK_DAYS = int(config('EVENT_LOOKBACK_DAYS', default=17))

# Automation Scheduler Frequency (hours)
SCHEDULE_FREQUENCY = int(config('SCHEDULE_FREQUENCY', default=1))

# Timezone for scheduling & timestamps (Greece)
LOCAL_TZ = ZoneInfo('Europe/Athens')

# -----------------------------
# Logging Setup
# -----------------------------
logger = logging.getLogger('events_alerts')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Also log to console for debugging
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# -----------------------------
# Image Handling
# -----------------------------
def load_logo(logo_path):
    """
    Load logo file for email attachment.
    Returns tuple of (file_data, mime_type, filename) or (None, None, None) if not found.

    Args:
        logo_path: Path object pointing to the logo file
    """
    if not logo_path.exists():
        logger.warning(f"Logo not found at: {logo_path}")
        return None, None, None

    try:
        with open(logo_path, 'rb') as f:
            logo_data = f.read()

        # Determine MIME type from extension
        ext = logo_path.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        mime_type = mime_types.get(ext, 'image/png')

        return logo_data, mime_type, logo_path.name

    except Exception as e:
        logger.error(f"Failed to load logo from {logo_path}: {e}")
        return None, None, None

# -----------------------------
# SQL Query Loader
# -----------------------------
def load_sql_query(query_file='EventHotWork.sql'):
    """Load SQL query from queries directory"""
    query_path = QUERIES_DIR / query_file
    if not query_path.exists():
        raise FileNotFoundError(f"SQL query file not found: {query_path}")

    with open(query_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# -----------------------------
# Teams Message Function
# -----------------------------
def send_teams_message(df, run_time):
    """Send formatted message to Microsoft Teams channel"""
    if not TEAMS_WEBHOOK_URL:
        logger.warning("Teams webhook URL not configured. Skipping Teams notification.")
        return

    try:
        # Create Teams message card
        teams_message = pymsteams.connectorcard(TEAMS_WEBHOOK_URL)

        # Set title based on results
        if df.empty:
            teams_message.title(f"AlertDev | No Events Found")
            teams_message.color("FFC107")  # Yellow/warning color
            teams_message.text("No events matching criteria were found in the last {} days.".format(EVENT_LOOKBACK_DAYS))
        else:
            teams_message.title(f"AlertDev | {len(df)} Permit Event{'s' if len(df) != 1 else ''} Found")
            teams_message.color("2EA9DE")  # Light blue brand color

            # Create summary section
            summary_section = pymsteams.cardsection()
            summary_section.activityTitle("Report Summary")
            summary_section.activitySubtitle(run_time.strftime('%A, %B %d, %Y at %H:%M %Z'))
            summary_section.addFact("Type", "Permit")
            summary_section.addFact("Period", f"Last {EVENT_LOOKBACK_DAYS} days")
            summary_section.addFact("Frequency", f"{SCHEDULE_FREQUENCY} hours")
            summary_section.addFact("Results", f"**{len(df)}** event{'s' if len(df) != 1 else ''}")
            teams_message.addSection(summary_section)

            # Create events section
            events_section = pymsteams.cardsection()
            events_section.activityTitle("Event Details")

            # Add events (limit to first 10 to avoid message size limits)
            event_text = ""
            for idx, row in df.head(10).iterrows():
                event_text += f"**{idx + 1}. {row['name']}**  \n"
                event_text += f"Created: {row['created_at']}  \n\n"

            if len(df) > 10:
                event_text += f"_...and {len(df) - 10} more event(s)_"

            events_section.text(event_text)
            teams_message.addSection(events_section)

        # Add footer
        footer_section = pymsteams.cardsection()
        footer_section.text(f"*Automated report from {COMPANY_NAME}*")
        teams_message.addSection(footer_section)

        # Send the message and capture response
        logger.info(f"Sending to webhook: {TEAMS_WEBHOOK_URL[:50]}...")  # Log first 50 chars only
        response = teams_message.send()

        # Log response details
        logger.info(f"Teams API response: {response}")

        if response:
            logger.info(f"✓ Teams message sent successfully to webhook (HTTP {response}, status code {teams_message.last_http_response.status_code})")
        else:
            logger.warning(f"⚠ Teams returned success but no response code - message may not have been delivered")

    except Exception as e:
        logger.exception(f"✗ Failed to send Teams message: {e}")
        raise


# -----------------------------
# Email Template Functions
# -----------------------------
def make_subject(event_count):
    """Generate email subject line"""
    return f"AlertDev | {event_count} Permit Event{'s' if event_count != 1 else ''} Found"

def make_plain_text(df, run_time):
    """Generate plain text version of email"""
    if df.empty:
        return f"""AlertDev | {run_time.strftime('%Y-%m-%d %H:%M %Z')}

No events matching criteria were found in the last {EVENT_LOOKBACK_DAYS} days.

---
This is an automated email from {COMPANY_NAME}.
If you have questions about this report, please contact data@prominencemaritime.com.
"""
    
    text = f"""AlertDev | {run_time.strftime('%Y-%m-%d %H:%M %Z')}

Found {len(df)} event(s) matching events:
- Type: 'Permit'
- Last {EVENT_LOOKBACK_DAYS} days
- Frequency: {SCHEDULE_FREQUENCY} hours

Events:
"""
    for idx, row in df.iterrows():
        text += f"\n{idx + 1}. {row['name']}"
        text += f"\n   Created: {row['created_at']}\n"
    
    text += f"\n---\nThis is an automated report from {COMPANY_NAME}.\nIf you have questions about this report, please contact data@prominencemaritime.com."
    return text

def make_html(df, run_time, has_company_logo=False, has_st_logo=False):
    """Generate HTML email with results table"""

    # Build logo HTML for both logos
    logos_html = ''
    if has_company_logo:
        logos_html += f'<img src="cid:company_logo" alt="{COMPANY_NAME} logo" style="max-height:25px;">'
    if has_company_logo and has_st_logo and 1 == 0:
        logos_html += '<span style="font-size:30px; font-weight:bold; color:#2EA9DE; margin:0 15px; vertical-align:middle;">&amp;</span>'
    if has_st_logo:
        logos_html += f'<img src="cid:st_company_logo" alt="ST Company logo" style="max-height:22px;">'

    # Header section
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            border-bottom: 3px solid #2EA9DE;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .logo {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        h1 {{
            color: #2EA9DE;
            margin: 0;
            font-size: 24px;
        }}
        .metadata {{
            background-color: #f5f5f5;
            padding: 12px;
            border-radius: 5px;
            margin: 20px 0;
            font-size: 14px;
        }}
        .metadata strong {{
            color: #555;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        thead {{
            background-color: #0B4877;
            color: white;
        }}
        th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tbody tr:hover {{
            background-color: #f9f9f9;
        }}
        tbody tr:last-child td {{
            border-bottom: none;
        }}
        .no-results {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
        }}
        .count-badge {{
            display: inline-block;
            background-color: #2EA9DE;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            {logos_html}
            <h1>Permit Events</h1>
        </div>
    </div>
    
    <div class="metadata">
        <strong>Report Generated:</strong> {run_time.strftime('%A, %B %d, %Y at %H:%M %Z')}<br>
        <strong>Query Criteria:</strong> Type: 'Permit', Last {EVENT_LOOKBACK_DAYS} days<br>
        <strong>Frequency:</strong> {SCHEDULE_FREQUENCY} hours<br>
        <strong>Results Found:</strong> <span class="count-badge">{len(df)}</span>
    </div>
"""
    
    # Results section
    if df.empty:
        html += """
    <div class="no-results">
        <strong>No Results</strong><br>
        No events matching the specified criteria were found in this time period.
    </div>
"""
    else:
        # Convert DataFrame to HTML table with custom styling
        html += """
    <table>
        <thead>
            <tr>
                <th style="width: 60px;">#</th>
                <th>Event Name</th>
                <th style="width: 200px;">Created At</th>
            </tr>
        </thead>
        <tbody>
"""
        for idx, row in df.iterrows():
            html += f"""
            <tr>
                <td style="text-align: center; color: #888;">{idx + 1}</td>
                <td><strong>{row['name']}</strong></td>
                <td style="font-family: monospace; font-size: 13px;">{row['created_at']}</td>
            </tr>
"""
        html += """
        </tbody>
    </table>
"""
    
    # Footer
    html += f"""
    <div class="footer">
        This is an automated email generated by {COMPANY_NAME}.<br>
        If you have questions about this report, please contact data@prominencemaritime.com.<br>
    </div>
</body>
</html>
"""
    return html

# -----------------------------
# Email Sending Function
# -----------------------------
def send_email(subject: str, plain_text: str, html_content: str, recipients: list[str]) -> None:
    """Send email with both plain text and HTML versions, and embedded logo"""
    if not recipients:
        logger.warning("No recipients configured. Skipping email send.")
        return

    # Create multipart message
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage

    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = ', '.join(recipients)

    # Create alternative part for text and HTML
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    # Attach plain text version
    part_text = MIMEText(plain_text, 'plain', 'utf-8')
    msg_alternative.attach(part_text)

    # Attach HTML version
    part_html = MIMEText(html_content, 'html', 'utf-8')
    msg_alternative.attach(part_html)

    # Attach company logo as embedded image with CID
    company_logo_data, company_mime_type, company_filename = load_logo(COMPANY_LOGO)
    if company_logo_data:
        maintype, subtype = company_mime_type.split('/')
        img = MIMEImage(company_logo_data, _subtype=subtype)
        img.add_header('Content-ID', '<company_logo>')
        img.add_header('Content-Disposition', 'inline', filename=company_filename)
        msg.attach(img)

    # Attach ST company logo as embedded image with CID
    st_logo_data, st_mime_type, st_filename = load_logo(ST_COMPANY_LOGO)
    if st_logo_data:
        maintype, subtype = st_mime_type.split('/')
        img = MIMEImage(st_logo_data, _subtype=subtype)
        img.add_header('Content-ID', '<st_company_logo>')
        img.add_header('Content-Disposition', 'inline', filename=st_filename)
        msg.attach(img)

    # Connect and send
    try:
        if SMTP_PORT == 465:
            # SSL connection
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.send_message(msg)
        else:
            # STARTTLS connection (ports 587/25)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.send_message(msg)

        logger.info(f"✓ Email sent successfully to {len(recipients)} recipient{'' if len(recipients) == 1 else 's'}: {', '.join(recipients)}")
    except Exception as e:
        logger.exception(f"✗ Failed to send email: {e}")
        raise

# -----------------------------
# Main Logic
# -----------------------------
def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("Events Alerts - Run Started")
    logger.info("=" * 60)
    
    run_time = datetime.now(tz=LOCAL_TZ)
    logger.info(f"Current time (Europe/Athens): {run_time.isoformat()}")
    
    try:
        # Connect to database
        logger.info("Establishing database connection...")
        with get_db_connection() as conn:
            logger.info("Database connection established successfully")
            
            # Load query from file
            query_sql = load_sql_query(config('SQL_QUERY_FILE'))
            query = text(query_sql) 

            # Execute query
            logger.info(f"Executing query: type_id={EVENT_TYPE_ID}, name_filter='%{EVENT_NAME_FILTER}%', lookback_days={EVENT_LOOKBACK_DAYS}")
            
            df = pd.read_sql_query(
                query, 
                conn, 
                params={
                    'type_id': EVENT_TYPE_ID,
                    'name_filter': f'%{EVENT_NAME_FILTER}%',
                    'lookback_days': EVENT_LOOKBACK_DAYS
                }
            )
            
            logger.info(f"Query executed successfully.")
            
            # Format created_at for display
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Generate email content
            subject = make_subject(len(df))
            plain_text = make_plain_text(df, run_time)

            # Check if logos exist for HTML
            company_logo_data, _, _ = load_logo(COMPANY_LOGO)
            st_logo_data, _, _ = load_logo(ST_COMPANY_LOGO)
            has_company_logo = company_logo_data is not None
            has_st_logo = st_logo_data is not None
            html_content = make_html(df, run_time, has_company_logo=has_company_logo, has_st_logo=has_st_logo)
            trimmed_html_content = make_html(df, run_time, has_company_logo=None, has_st_logo=None)
            
            # Only sent notifications when events have been found
            if not df.empty:
                logger.info(f"{len(df)} events found.")

                # Send email if enabled
                if ENABLE_EMAIL_ALERTS:
                    logger.info(f"Preparing to send email to: {', '.join(INTERNAL_RECIPIENTS)}")
                    send_email(subject, plain_text, html_content, INTERNAL_RECIPIENTS)
                    logger.info("✓ Email sent successfully")
                else:
                    # Don't send email
                    logger.info("Email alerts disabled: no email sent.")
                if ENABLE_SPECIAL_TEAMS_EMAIL_ALERT:
                    logger.info(f"Preparing to send Email to Teams Alert Channel: {SPECIAL_TEAMS_EMAIL}")
                    special_email = [SPECIAL_TEAMS_EMAIL]
                    send_email(subject, plain_text, trimmed_html_content, special_email)
                    logger.info("✓ Email sent to Teams 'Alerts' channel successfully")
                else:
                    logger.info("Special Teams email alerts disabled: no channel email sent")

                # Send Teams message if enables
                if ENABLE_TEAMS_ALERTS:
                    logger.info("Preparing to send Teams notification...")
                    send_teams_message(df, run_time)
                    logger.info("✓ Teams message sent successfully.")
                else:
                    logger.info("Teams alerts disabled: no Teams notification sent.")

            else:
                logger.info("No events found matching specified criteria.")
                # Optional: send "no results notification to Teams"
                # if ENABLE_TEAMS_ALERTS:
                #   send_teams_message(df, run_time)
                #          

            
    except Exception as e:
        logger.exception(f"Error during execution: {e}")
        sys.exit(1)
    
    finally:
        logger.info("=" * 60)
        logger.info("Events Alerts - Run Completed")
        logger.info("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logger.exception(f"Exception occurred: {e}")
        sys.exit(1)

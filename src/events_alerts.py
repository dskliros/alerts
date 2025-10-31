#!/usr/bin/env python3
"""
events_alerts.py
- Connects to PostgreSQL via db_utils
- Queries events matching specific criteria
- Sends results as an HTML email
- Logs to rotating logfile
- Tracks sent event IDs to prevent duplicate notifications
"""

from src.db_utils import get_db_connection
from decouple import config
from sqlalchemy import text
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import smtplib
from email.message import EmailMessage
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
import pymsteams
from typing import Union, List, Set, Dict
import json
import time
import signal

# -----------------------------
# Project Structure
# -----------------------------
# Get the project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = PROJECT_ROOT / 'queries'
LOGS_DIR = PROJECT_ROOT / 'logs'
DATA_DIR = PROJECT_ROOT / 'data'
MEDIA_DIR = PROJECT_ROOT / 'media'

# Ensure required directories exist
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Sent events tracking file
SENT_EVENTS_FILE = DATA_DIR / 'sent_events.json'

# -----------------------------
# Configuration from .env
# -----------------------------
SMTP_HOST = config('SMTP_HOST')
SMTP_PORT = int(config('SMTP_PORT', default=465))
SMTP_USER = config('SMTP_USER')
SMTP_PASS = config('SMTP_PASS')

INTERNAL_RECIPIENTS = [s.strip() for s in config('INTERNAL_RECIPIENTS', '').split(',') if s.strip()]
ENABLE_SPECIAL_TEAMS_EMAIL_ALERT = config('ENABLE_SPECIAL_TEAMS_EMAIL_ALERT', default=False, cast=bool)
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
EVENT_TYPE_ID = int(config('EVENT_TYPE_ID', default=18))    # 18 -> label = permits
EVENT_STATUS_ID = int(config('EVENT_STATUS_ID', default=3))       # 3 -> progress = for-review
EVENT_NAME_FILTER = config('EVENT_NAME_FILTER', default='hot')
EVENT_EXCLUDE = config('EVENT_EXCLUDE', default='vessel')
EVENT_LOOKBACK_DAYS = int(config('EVENT_LOOKBACK_DAYS', default=17))

# Automation Scheduler Frequency (hours)
SCHEDULE_FREQUENCY = int(config('SCHEDULE_FREQUENCY', default=1))

# Automated Reminder Frequency (days)
REMINDER_FREQUENCY_DAYS = int(config('REMINDER_FREQUENCY_DAYS', default=30))

# Timezone for scheduling & timestamps (Greece)
LOCAL_TZ = ZoneInfo('Europe/Athens')

# Handle gracefully if required config values are missing
required_configs = {
    'SMTP_HOST': SMTP_HOST,
    'SMTP_USER': SMTP_USER,
    'SMTP_PASS': SMTP_PASS,
}

for key, value in required_configs.items():
    if not value:
        raise ValueError(f"Required configuration '{key}' is missing from .env file")

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
# Graceful Shutdown Handler
# -----------------------------
shutdown_flag = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_flag
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_flag = True

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# -----------------------------
# Sent Events Tracking
# -----------------------------
def load_sent_events() -> dict:
    """
    Load the dictionary of event IDs that have already been sent with timestamps.
    Automatically removes events older than REMINDER_FREQUENCY_DAYS.
    Returns dict with event_id as key and sent_at timestamp as value.
    Returns an empty dict if file doesn't exist or is corrupted.
    """
    if not SENT_EVENTS_FILE.exists():
        logger.info(f"Sent events file not found at {SENT_EVENTS_FILE}. Starting with empty history.")
        return {}

    try:
        with open(SENT_EVENTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Handle both old format (list) and new format (dict with timestamps)
            sent_events_data = data.get('sent_events', {})

            # Backward compatibility: if old format with sent_event_ids list
            if not sent_events_data and 'sent_event_ids' in data:
                logger.info("Converting old format to new format with timestamps")
                # Convert old list format to new dict format with current time
                current_time = datetime.now(tz=LOCAL_TZ).isoformat()
                sent_events_data = {str(event_id): current_time for event_id in data['sent_event_ids']}

            # Convert string keys to integers
            sent_events = {int(k): v for k, v in sent_events_data.items()}

            logger.info(f"Loaded {len(sent_events)} event ID(s) from {SENT_EVENTS_FILE}")

            # Filter out events older than REMINDER_FREQUENCY_DAYS
            cutoff_date = datetime.now(tz=LOCAL_TZ) - timedelta(days=REMINDER_FREQUENCY_DAYS)
            filtered_events = {}
            removed_count = 0

            for event_id, timestamp_str in sent_events.items():
                try:
                    # Parse the ISO format timestamp
                    event_timestamp = datetime.fromisoformat(timestamp_str)
                    
                    # Keep only events within the reminder frequency window
                    if event_timestamp >= cutoff_date:
                        filtered_events[event_id] = timestamp_str
                    else:
                        removed_count += 1
                        logger.debug(f"Removing event ID {event_id} (sent at {timestamp_str}, older than {REMINDER_FREQUENCY_DAYS} days)")
                
                except (ValueError, TypeError) as e:
                    # If timestamp is invalid, remove it
                    logger.warning(f"Invalid timestamp for event ID {event_id}: {timestamp_str}. Removing from tracking.")
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Removed {removed_count} event(s) older than {REMINDER_FREQUENCY_DAYS} days from tracking")
                # Save the filtered events immediately to persist the cleanup
                save_sent_events(filtered_events)
            
            logger.info(f"Tracking {len(filtered_events)} recent event ID(s) (sent within last {REMINDER_FREQUENCY_DAYS} days)")
            return filtered_events

    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {SENT_EVENTS_FILE}: {e}. Starting with empty history.")
        return {}
    except Exception as e:
        logger.error(f"Error loading sent events from {SENT_EVENTS_FILE}: {e}. Starting with empty history.")
        return {}


def save_sent_events(sent_events: dict) -> None:
    """
    Save the dictionary of sent event IDs with timestamps to JSON file.
    Includes metadata about last update.

    Args:
        sent_events: Dict mapping event_id (int) -> sent_at timestamp (str)
    """
    try:
        # Convert int keys to strings for JSON compatibility, sort by event ID
        sent_events_sorted = {str(k): v for k, v in sorted(sent_events.items())}

        data = {
            'sent_events': sent_events_sorted,
            'last_updated': datetime.now(tz=LOCAL_TZ).isoformat()
            #'total_count': len(sent_events)
        }

        with open(SENT_EVENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(sent_events)} event IDs with timestamps to {SENT_EVENTS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save sent events to {SENT_EVENTS_FILE}: {e}")
        raise


def filter_unsent_events(df: pd.DataFrame, sent_events: dict) -> pd.DataFrame:
    """
    Filter DataFrame to only include events that haven't been sent yet.
    Returns a new DataFrame with only unsent events.
    """
    if df.empty:
        return df
    
    if 'id' not in df.columns:
        logger.warning("DataFrame missing 'id' column. Cannot filter sent events. Returning all events.")
        return df
    
    # Filter out events that have already been sent (use keys from dict)
    unsent_df = df[~df['id'].isin(sent_events.keys())].copy()
    
    filtered_count = len(df) - len(unsent_df)
    if filtered_count > 0:
        logger.info(f"Filtered out {filtered_count} previously sent event(s). {len(unsent_df)} new event(s) remain.")
    
    return unsent_df


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
                event_text += f"**{idx + 1}. {row['event_name']}**  \n"
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
        logger.info("Sending message to Teams webhook...")
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
def get_event_id_name(type_id: int, filename='get_events_name.sql') -> tuple:
    """
    Fetch event type name from event_types table for a given type_id.
    Returns tuple of (event_id, event_name)
    """
    query_sql = load_sql_query(filename)
    query = text(query_sql)
    
    with get_db_connection() as conn:
        result = conn.execute(query, {"type_id": type_id}).fetchone()
        if result:
            return result[0] if len(result) > 0 else '', result[1] if len(result) > 1 else 'Unknown Event'
        return '', 'Unknown Event'


def make_subject(event_count, type_id: int = EVENT_TYPE_ID):
    """Generate email subject line"""
    event_id, event_name = get_event_id_name(type_id)
    return f"AlertDev | {event_count} {event_name.title()} Event{'s' if event_count != 1 else ''} Found"


def make_plain_text(df, run_time):
    """Generate plain text email dynamically based on available columns"""
    header = f"""AlertDev | {run_time.strftime('%Y-%m-%d %H:%M %Z')}

Found {len(df)} event(s) matching criteria.
"""

    if df.empty:
        return header + f"\nNo results found.\n\n---\nAutomated report from {COMPANY_NAME}."

    text = header + "\nEvents:\n"

    for idx, row in df.iterrows():
        text += f"\n{idx + 1}."
        # Add link if ID is available
        if 'id' in df.columns:
            event_url = f"https://prominence.orca.tools/events/{row['id']}"
            text += f"\n   Link: {event_url}"
        for col in df.columns:
            text += f"\n   {col}: {row[col]}"
        text += "\n"

    text += f"\n---\nThis is an automated message from {COMPANY_NAME}.\nIf you have questions about this report, please contact data@prominencemaritime.com."
    return text


def make_html(df, run_time, has_company_logo=False, has_st_logo=False):
    """Generate a rich, dynamically formatted HTML email for events."""
    event_id, event_name = get_event_id_name(type_id=EVENT_TYPE_ID)
    
    # Initialize event_ids to avoid NameError when df is empty
    event_ids = []

    logos_html = ""
    if has_company_logo:
        logos_html += f"""
        <img src="cid:company_logo" alt="{COMPANY_NAME} logo"
             style="max-height:50px; margin-right:15px; vertical-align:middle;">
        """
    if has_st_logo:
        logos_html += f"""
        <img src="cid:st_company_logo" alt="ST logo"
             style="max-height:45px; vertical-align:middle;">
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        background-color: #f9fafc;
        color: #333;
        line-height: 1.6;
        margin: 0;
        padding: 0;
    }}
    .container {{
        max-width: 900px;
        margin: 30px auto;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        overflow: hidden;
        padding: 20px 40px;
    }}
    .header {{
        background-color: #0B4877;
        color: white;
        padding: 15px 25px;
        border-radius: 12px 12px 0 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .header h1 {{
        margin: 0;
        font-size: 22px;
        font-weight: 600;
    }}
    .header p {{
        margin: 0;
        font-size: 14px;
        color: #d7e7f5;
    }}
    .metadata {{
        background-color: #f5f5f5;
        padding: 12px;
        border-radius: 5px;
        margin: 20px 0;
        font-size: 14px;
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
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        font-size: 14px;
    }}
    th {{
        background-color: #0B4877;
        color: white;
        text-align: left;
        padding: 10px;
    }}
    td {{
        padding: 8px 10px;
        border-bottom: 1px solid #e0e6ed;
    }}
    tr:nth-child(even) {{
        background-color: #f5f8fb;
    }}
    tr:hover {{
        background-color: #eef5fc;
    }}
    a {{
        color: #2EA9DE;
        text-decoration: none;
    }}
    a:hover {{
        text-decoration: underline;
    }}
    .footer {{
        font-size: 12px;
        color: #888;
        text-align: center;
        padding: 10px;
        border-top: 1px solid #eee;
        margin-top: 20px;
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>{logos_html}</div>
        <div style="text-align:right;">
            <h1>{event_name} Alerts</h1>
            <p>{run_time.strftime('%A, %d %B %Y %H:%M %Z')}</p>
        </div>
    </div>
"""

    # Table or "no results" message
    if df.empty:
        html += """
        <p style="margin-top:25px; font-size:15px;">
            <strong>No events found for the current query.</strong>
        </p>
        """
    else:
        html += f"""
        <div class="metadata">
            <strong>Report Generated:</strong> {run_time.strftime('%A, %B %d, %Y at %H:%M %Z')}<br>
            <strong>Query Criteria:</strong> Type ID: {EVENT_TYPE_ID}, Status ID: {EVENT_STATUS_ID}, Lookback: {EVENT_LOOKBACK_DAYS} day{'' if EVENT_LOOKBACK_DAYS == 1 else 's'}<br>
            <strong>Frequency:</strong> {SCHEDULE_FREQUENCY} hours<br>
            <strong>Results Found:</strong> <span class="count-badge">{len(df)}</span>
        </div>
        <table>
            <thead><tr>"""
        
        for col in df.columns:
            html += f"<th>{col.replace('_', ' ').title()}</th>"
        
        html += "</tr></thead><tbody>"

        for idx, row in df.iterrows():
            html += "<tr>"
            for col in df.columns:
                if col == 'event_name' and 'id' in df.columns:
                    # Make event_name a clickable link
                    event_url = f"https://prominence.orca.tools/events/{row['id']}"
                    html += f"""<td>
                        <strong>
                            <a href="{event_url}" 
                               style="color: #2EA9DE; text-decoration: none;"
                               target="_blank">
                                {row[col]}
                            </a>
                        </strong>
                    </td>"""
                    event_ids.append(row['id'])
                else:
                    html += f"<td>{row[col]}</td>"
            html += "</tr>"

        html += "</tbody></table>"

    html += f"""
    <div class="footer">
        This is an automated report generated by {COMPANY_NAME}.
    </div>
</div>
</body>
</html>
"""
    return event_ids, html


# -----------------------------
# Email Sending Function
# -----------------------------
def send_email(subject: str, plain_text: str, html_content: str, recipients: List[str]) -> None:
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
        # Load previously sent event IDs with timestamps
        sent_events = load_sent_events()
        
        # Connect to database
        logger.info("Establishing database connection...")
        with get_db_connection() as conn:
            logger.info("Database connection established successfully")
            
            # Load query from file
            query_sql = load_sql_query(config('SQL_QUERY_FILE'))
            query = text(query_sql) 

            # Execute query
            logger.info(f"Executing query: type_id={EVENT_TYPE_ID}, status_id={EVENT_STATUS_ID}, name_filter='%{EVENT_NAME_FILTER}%', name_excluded='%{EVENT_EXCLUDE}%', lookback_days={EVENT_LOOKBACK_DAYS}")
            
            df = pd.read_sql_query(
                query, 
                conn, 
                params={
                    'type_id': EVENT_TYPE_ID,
                    'status_id': EVENT_STATUS_ID,
                    'name_filter': f'%{EVENT_NAME_FILTER}%',
                    'name_excluded': f'%{EVENT_EXCLUDE}%',
                    'lookback_days': EVENT_LOOKBACK_DAYS
                }
            )
            
            logger.info(f"Query executed successfully. Found {len(df)} event(s) from database.")
            
            # Validate that ID column exists for link generation and deduplication
            if not df.empty and 'id' not in df.columns:
                logger.warning("Query result missing 'id' column - event links and deduplication will not work")
            
            # Filter out events that have already been sent
            original_count = len(df)
            df = filter_unsent_events(df, sent_events)

            # Format created_at for display
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if we have new events to send
            if df.empty:
                if original_count > 0:
                    logger.info(f"All {original_count} event(s) have been sent previously. No new events to notify.")
                else:
                    logger.info("No events found matching specified criteria.")
                return  # Exit without sending notifications
            
            # We have new events - prepare notifications
            logger.info(f"{len(df)} new event(s) to be sent.")
            
            # Generate email content
            subject = make_subject(len(df))
            plain_text = make_plain_text(df, run_time)

            # Check if logos exist for HTML
            has_company_logo = COMPANY_LOGO.exists()
            has_st_logo = ST_COMPANY_LOGO.exists()
            event_ids, html_content = make_html(df, run_time, has_company_logo=has_company_logo, has_st_logo=has_st_logo)
            trimmed_event_ids, trimmed_html_content = make_html(df, run_time, has_company_logo=False, has_st_logo=False)
            
            # Track if any notification was sent successfully
            notifications_sent = False
            
            # Send email if enabled
            if ENABLE_EMAIL_ALERTS:
                try:
                    logger.info(f"Preparing to send email to: {', '.join(INTERNAL_RECIPIENTS)}")
                    send_email(subject, plain_text, html_content, INTERNAL_RECIPIENTS)
                    notifications_sent = True
                except Exception as e:
                    logger.error(f"Email sending failed: {e}")
            else:
                logger.info("Email alerts disabled: no email sent.")
            
            # Send special Teams email if enabled
            if ENABLE_SPECIAL_TEAMS_EMAIL_ALERT:
                try:
                    logger.info(f"Preparing to send Email to Teams Alert Channel: {SPECIAL_TEAMS_EMAIL}")
                    special_email = [SPECIAL_TEAMS_EMAIL]
                    send_email(subject, plain_text, trimmed_html_content, special_email)
                    notifications_sent = True
                except Exception as e:
                    logger.error(f"Special Teams email sending failed: {e}")
            else:
                logger.info("Special Teams email alerts disabled: no channel email sent")

            # Send Teams message if enabled
            if ENABLE_TEAMS_ALERTS:
                try:
                    logger.info("Preparing to send Teams notification...")
                    send_teams_message(df, run_time)
                    notifications_sent = True
                except Exception as e:
                    logger.error(f"Teams notification failed: {e}")
            else:
                logger.info("Teams alerts disabled: no Teams notification sent.")
            
            # Only mark events as sent if at least one notification was successful
            if notifications_sent and event_ids:
                current_timestamp = run_time.isoformat()
                logger.info(f"Marking {len(event_ids)} event(s) as sent at {current_timestamp}: {event_ids}")

                # Add new events with current timestamp
                for event_id in event_ids:
                    sent_events[event_id] = current_timestamp

                save_sent_events(sent_events)
            elif not notifications_sent:
                logger.warning("No notifications were sent successfully. Event IDs will NOT be marked as sent.")

            
    except Exception as e:
        logger.exception(f"Error during execution: {e}")
        sys.exit(1)
    
    finally:
        logger.info("=" * 60)
        logger.info("Events Alerts - Run Completed")
        logger.info("=" * 60)


def run_scheduler():
    """
    Continuously run the alerts system at intervals specified by SCHEDULE_FREQUENCY.
    Runs immediately on startup, then waits SCHEDULE_FREQUENCY hours between runs.
    """
    global shutdown_flag

    logger.info("=" * 60)
    logger.info(f"Scheduler Started - Running every {SCHEDULE_FREQUENCY} hour(s)")
    logger.info("=" * 60)

    while not shutdown_flag:
        try:
            # Run the main alerts logic
            main()

            # Check shutdown flag before sleeping
            if shutdown_flag:
                break

            # Calculate sleep time in seconds
            sleep_seconds = SCHEDULE_FREQUENCY * 3600
            logger.info(f"Sleeping for {SCHEDULE_FREQUENCY} hour(s) ({sleep_seconds} seconds)...")
            logger.info(f"Next run scheduled at: {(datetime.now(tz=LOCAL_TZ) + timedelta(hours=SCHEDULE_FREQUENCY)).strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # Sleep in smaller intervals to check shutdown flag
            sleep_interval = 60  # Check every minute
            elapsed = 0
            while elapsed < sleep_seconds and not shutdown_flag:
                time.sleep(min(sleep_interval, sleep_seconds - elapsed))
                elapsed += sleep_interval

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down...")
            break
        except Exception as e:
            logger.exception(f"Unhandled exception in scheduler loop: {e}")
            # Wait a bit before retrying to avoid rapid failure loops
            if not shutdown_flag:
                logger.info("Waiting 5 minutes before retry...")
                time.sleep(300)

    logger.info("=" * 60)
    logger.info("Scheduler Stopped")
    logger.info("=" * 60)


# -------------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Events Alerts System')
    parser.add_argument('--dry-run', action='store_true', help='Run without sending notifications')
    parser.add_argument('--run-once', action='store_true', help='Run once and exit (no scheduling)')
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - No notifications will be sent")
        ENABLE_EMAIL_ALERTS = False
        ENABLE_TEAMS_ALERTS = False
        ENABLE_SPECIAL_TEAMS_EMAIL_ALERT = False

    try:
        if args.run_once:
            logger.info("RUN-ONCE MODE - Executing single run without scheduling")
            main()
        else:
            run_scheduler()
    except Exception:
        logger.exception("Unhandled exception occurred")
        sys.exit(1)

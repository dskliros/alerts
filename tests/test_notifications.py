# tests/test_notifications.py
"""
Tests for notification sending functionality
"""
import pytest
from unittest.mock import patch, MagicMock, Mock, call
import smtplib


def test_send_email_success_ssl(mock_smtp):
    """Test successful email sending via SSL"""
    from src.events_alerts import send_email

    with patch('src.events_alerts.SMTP_PORT', 465):
        with patch('src.events_alerts.SMTP_HOST', 'smtp.test.com'):
            with patch('src.events_alerts.SMTP_USER', 'test@test.com'):
                with patch('src.events_alerts.SMTP_PASS', 'password'):
                    with patch('smtplib.SMTP_SSL', return_value=mock_smtp):
                        with patch('src.events_alerts.load_logo', return_value=(None, None, None)):

                            send_email(
                                'Test Subject',
                                'Plain text',
                                '<html>HTML content</html>',
                                ['recipient@test.com']
                            )

                            mock_smtp.login.assert_called_once()
                            mock_smtp.send_message.assert_called_once()


def test_send_email_success_starttls(mock_smtp):
    """Test successful email sending via STARTTLS"""
    from src.events_alerts import send_email

    with patch('src.events_alerts.SMTP_PORT', 587):
        with patch('src.events_alerts.SMTP_HOST', 'smtp.test.com'):
            with patch('src.events_alerts.SMTP_USER', 'test@test.com'):
                with patch('src.events_alerts.SMTP_PASS', 'password'):
                    with patch('smtplib.SMTP', return_value=mock_smtp):
                        with patch('src.events_alerts.load_logo', return_value=(None, None, None)):

                            send_email(
                                'Test Subject',
                                'Plain text',
                                '<html>HTML content</html>',
                                ['recipient@test.com']
                            )

                            mock_smtp.ehlo.assert_called()
                            mock_smtp.starttls.assert_called_once()
                            mock_smtp.login.assert_called_once()
                            mock_smtp.send_message.assert_called_once()


def test_send_email_no_recipients():
    """Test email sending with no recipients"""
    from src.events_alerts import send_email

    # Should not raise exception, just log warning
    send_email(
        'Test Subject',
        'Plain text',
        '<html>HTML content</html>',
        []
    )


def test_send_email_with_logos(mock_smtp, temp_project_root):
    """Test email sending with embedded logos"""
    from src.events_alerts import send_email

    # Create fake logo file
    logo_file = temp_project_root / 'media' / 'logo.png'
    logo_file.write_bytes(b'fake image data')

    with patch('src.events_alerts.SMTP_PORT', 465):
        with patch('src.events_alerts.SMTP_HOST', 'smtp.test.com'):
            with patch('src.events_alerts.SMTP_USER', 'test@test.com'):
                with patch('src.events_alerts.SMTP_PASS', 'password'):
                    with patch('src.events_alerts.COMPANY_LOGO', logo_file):
                        with patch('src.events_alerts.ST_COMPANY_LOGO', logo_file):
                            with patch('smtplib.SMTP_SSL', return_value=mock_smtp):

                                send_email(
                                    'Test Subject',
                                    'Plain text',
                                    '<html>HTML content</html>',
                                    ['recipient@test.com']
                                )

                                mock_smtp.send_message.assert_called_once()


def test_send_email_connection_failure():
    """Test email sending with connection failure"""
    from src.events_alerts import send_email

    with patch('src.events_alerts.SMTP_PORT', 465):
        with patch('src.events_alerts.SMTP_HOST', 'smtp.test.com'):
            with patch('src.events_alerts.SMTP_USER', 'test@test.com'):
                with patch('src.events_alerts.SMTP_PASS', 'password'):
                    with patch('smtplib.SMTP_SSL', side_effect=smtplib.SMTPException('Connection failed')):
                        with patch('src.events_alerts.load_logo', return_value=(None, None, None)):

                            with pytest.raises(smtplib.SMTPException):
                                send_email(
                                    'Test Subject',
                                    'Plain text',
                                    '<html>HTML content</html>',
                                    ['recipient@test.com']
                                )


def test_send_teams_message_success(sample_event_data, fixed_datetime):
    """Test successful Teams message sending"""
    from src.events_alerts import send_teams_message

    mock_card = MagicMock()
    mock_card.send.return_value = True
    mock_card.last_http_response = MagicMock()
    mock_card.last_http_response.status_code = 200

    with patch('src.events_alerts.TEAMS_WEBHOOK_URL', 'https://test.webhook.url'):
        with patch('pymsteams.connectorcard', return_value=mock_card):
            with patch('src.events_alerts.COMPANY_NAME', 'Test Company'):
                with patch('src.events_alerts.EVENT_LOOKBACK_DAYS', 17):
                    with patch('src.events_alerts.SCHEDULE_FREQUENCY', 1):

                        send_teams_message(sample_event_data, fixed_datetime)

                        mock_card.title.assert_called()
                        mock_card.addSection.assert_called()
                        mock_card.send.assert_called_once()


def test_send_teams_message_empty_df(empty_event_data, fixed_datetime):
    """Test Teams message with empty DataFrame"""
    from src.events_alerts import send_teams_message

    mock_card = MagicMock()
    mock_card.send.return_value = True
    mock_card.last_http_response = MagicMock()
    mock_card.last_http_response.status_code = 200

    with patch('src.events_alerts.TEAMS_WEBHOOK_URL', 'https://test.webhook.url'):
        with patch('pymsteams.connectorcard', return_value=mock_card):
            with patch('src.events_alerts.EVENT_LOOKBACK_DAYS', 17):

                send_teams_message(empty_event_data, fixed_datetime)

                mock_card.send.assert_called_once()


def test_send_teams_message_no_webhook():
    """Test Teams message when webhook URL not configured"""
    from src.events_alerts import send_teams_message
    import pandas as pd
    from datetime import datetime
    from zoneinfo import ZoneInfo

    with patch('src.events_alerts.TEAMS_WEBHOOK_URL', ''):
        # Should not raise exception, just log warning
        send_teams_message(pd.DataFrame(), datetime.now(tz=ZoneInfo('Europe/Athens')))

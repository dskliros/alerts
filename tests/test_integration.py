# tests/test_integration.py
"""
Integration tests for the complete workflow
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


def test_main_flow_with_new_events(
    temp_project_root,
    sample_event_data,
    mock_db_connection,
    mock_smtp,
    mock_smtp_class,
    fixed_datetime,
    local_tz
):
    """Test complete main() flow with new events"""
    from src.events_alerts import main

    sent_events_file = temp_project_root / 'data' / 'sent_events.json'

    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
            with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
                with patch('src.events_alerts.LOCAL_TZ', local_tz):
                    with patch('pandas.read_sql_query', return_value=sample_event_data):
                        with patch('smtplib.SMTP_SSL', mock_smtp_class):
                            with patch('src.events_alerts.load_logo', return_value=(None, None, None)):
                                with patch('src.events_alerts.ENABLE_EMAIL_ALERTS', True):
                                    with patch('src.events_alerts.ENABLE_TEAMS_ALERTS', False):
                                        with patch('src.events_alerts.ENABLE_SPECIAL_TEAMS_EMAIL_ALERT', False):
                                            with patch('src.events_alerts.INTERNAL_RECIPIENTS', ['test@test.com']):
                                                with patch('src.events_alerts.SMTP_PORT', 465):
                                                    with patch('src.events_alerts.SMTP_HOST', 'smtp.test.com'):
                                                        with patch('src.events_alerts.SMTP_USER', 'test@test.com'):
                                                            with patch('src.events_alerts.SMTP_PASS', 'password'):
                                                                with patch('src.events_alerts.EVENT_STATUS_ID', 3):
                                                                    main()

                                                                    # Verify email was sent
                                                                    mock_smtp.send_message.assert_called_once()

                                                                    # Verify sent_events.json was created
                                                                    assert sent_events_file.exists()

                                                                    # Verify the content of sent_events.json
                                                                    import json
                                                                    with open(sent_events_file, 'r') as f:
                                                                        data = json.load(f)
                                                                    assert '101' in data['sent_events']
                                                                    assert '102' in data['sent_events']
                                                                    # Verify total_count is NOT in the file
                                                                    assert 'total_count' not in data


def test_main_flow_all_events_already_sent(
    temp_project_root,
    sample_event_data,
    sent_events_json,
    mock_db_connection,
    fixed_datetime,
    local_tz
):
    """Test main() flow when all events already sent"""
    from src.events_alerts import main
    
    # Add sample event IDs to sent events
    sent_events = {101: '2025-10-29T08:00:00+02:00', 102: '2025-10-29T09:30:00+02:00'}
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_json):
        with patch('src.events_alerts.load_sent_events', return_value=sent_events):
            with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
                with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
                    with patch('src.events_alerts.LOCAL_TZ', local_tz):
                        with patch('pandas.read_sql_query', return_value=sample_event_data):
                            with patch('datetime.datetime') as mock_datetime:
                                mock_datetime.now.return_value = fixed_datetime
                                
                                # Should exit early without sending notifications
                                main()


def test_main_flow_no_events_found(
    temp_project_root,
    empty_event_data,
    mock_db_connection,
    fixed_datetime,
    local_tz
):
    """Test main() flow when query returns no events"""
    from src.events_alerts import main
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
            with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
                with patch('src.events_alerts.LOCAL_TZ', local_tz):
                    with patch('pandas.read_sql_query', return_value=empty_event_data):
                        with patch('datetime.datetime') as mock_datetime:
                            mock_datetime.now.return_value = fixed_datetime
                            
                            # Should exit early without sending notifications
                            main()


def test_main_flow_notification_failure(
    temp_project_root,
    sample_event_data,
    mock_db_connection,
    fixed_datetime,
    local_tz
):
    """Test main() flow when notification fails"""
    from src.events_alerts import main
    import smtplib
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
            with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
                with patch('src.events_alerts.LOCAL_TZ', local_tz):
                    with patch('pandas.read_sql_query', return_value=sample_event_data):
                        with patch('smtplib.SMTP_SSL', side_effect=smtplib.SMTPException('Failed')):
                            with patch('src.events_alerts.load_logo', return_value=(None, None, None)):
                                with patch('src.events_alerts.ENABLE_EMAIL_ALERTS', True):
                                    with patch('src.events_alerts.ENABLE_TEAMS_ALERTS', False):
                                        with patch('src.events_alerts.ENABLE_SPECIAL_TEAMS_EMAIL_ALERT', False):
                                            with patch('src.events_alerts.INTERNAL_RECIPIENTS', ['test@test.com']):
                                                with patch('datetime.datetime') as mock_datetime:
                                                    mock_datetime.now.return_value = fixed_datetime
                                                    
                                                    main()
                                                    
                                                    # Events should NOT be marked as sent
                                                    # sent_events.json should either not exist or be empty

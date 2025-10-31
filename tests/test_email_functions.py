# tests/test_email_functions.py
"""
Tests for email template generation functions
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


def test_make_subject_single_event(mock_db_connection):
    """Test subject line generation for single event"""
    from src.events_alerts import make_subject

    with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
        with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
            subject = make_subject(1, type_id=18)

            assert 'AlertDev' in subject
            assert '1' in subject
            assert 'Event' in subject
            assert 'Events' not in subject  # Singular


def test_make_subject_multiple_events(mock_db_connection):
    """Test subject line generation for multiple events"""
    from src.events_alerts import make_subject

    with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
        with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
            subject = make_subject(5, type_id=18)

            assert 'AlertDev' in subject
            assert '5' in subject
            assert 'Events' in subject  # Plural


def test_make_plain_text_with_events(sample_event_data, fixed_datetime):
    """Test plain text email generation with events"""
    from src.events_alerts import make_plain_text

    with patch('src.events_alerts.COMPANY_NAME', 'Test Company'):
        text = make_plain_text(sample_event_data, fixed_datetime)

        assert 'AlertDev' in text
        assert '2 event(s)' in text
        assert 'Hot Work Permit - Deck Maintenance' in text
        assert 'Hot Work Permit - Engine Room' in text
        assert 'https://prominence.orca.tools/events/101' in text
        assert 'Test Company' in text


def test_make_plain_text_empty(empty_event_data, fixed_datetime):
    """Test plain text email generation with no events"""
    from src.events_alerts import make_plain_text

    with patch('src.events_alerts.COMPANY_NAME', 'Test Company'):
        text = make_plain_text(empty_event_data, fixed_datetime)

        assert 'No results found' in text
        assert 'Test Company' in text


def test_make_html_with_events(sample_event_data, fixed_datetime, mock_db_connection):
    """Test HTML email generation with events"""
    from src.events_alerts import make_html

    with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
        with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
            with patch('src.events_alerts.COMPANY_NAME', 'Test Company'):
                with patch('src.events_alerts.EVENT_TYPE_ID', 18):
                    with patch('src.events_alerts.EVENT_STATUS_ID', 3):
                        with patch('src.events_alerts.EVENT_LOOKBACK_DAYS', 17):
                            event_ids, html = make_html(sample_event_data, fixed_datetime)

                            assert len(event_ids) == 2
                            assert 101 in event_ids
                            assert 102 in event_ids
                            assert 'Hot Work Permit - Deck Maintenance' in html
                            assert 'https://prominence.orca.tools/events/101' in html
                            assert 'Test Company' in html
                            assert '<!DOCTYPE html>' in html
                            assert 'Status: Default Status' in html
                            assert 'Type: Default Type' in html


def test_make_html_empty(empty_event_data, fixed_datetime, mock_db_connection):
    """Test HTML email generation with no events"""
    from src.events_alerts import make_html

    with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
        with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
            event_ids, html = make_html(empty_event_data, fixed_datetime)

            assert event_ids == []
            assert 'No events found' in html
            assert '<!DOCTYPE html>' in html


def test_make_html_with_logos(sample_event_data, fixed_datetime, mock_db_connection, temp_project_root):
    """Test HTML generation with logo flags"""
    from src.events_alerts import make_html

    with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
        with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
            with patch('src.events_alerts.COMPANY_NAME', 'Test Company'):
                event_ids, html = make_html(
                    sample_event_data,
                    fixed_datetime,
                    has_company_logo=True,
                    has_st_logo=True
                )

                assert 'cid:company_logo' in html
                assert 'cid:st_company_logo' in html


def test_make_html_lookback_days_plural(sample_event_data, fixed_datetime, mock_db_connection):
    """Test HTML shows correct singular/plural for lookback days"""
    from src.events_alerts import make_html
    
    with patch('src.events_alerts.get_db_connection', return_value=mock_db_connection):
        with patch('src.events_alerts.load_sql_query', return_value='SELECT * FROM events'):
            with patch('src.events_alerts.COMPANY_NAME', 'Test Company'):
                with patch('src.events_alerts.EVENT_TYPE_ID', 18):
                    with patch('src.events_alerts.EVENT_STATUS_ID', 3):
                        # Test plural (17 days)
                        with patch('src.events_alerts.EVENT_LOOKBACK_DAYS', 17):
                            event_ids, html = make_html(sample_event_data, fixed_datetime)
                            assert '17 days' in html
                        
                        # Test singular (1 day)
                        with patch('src.events_alerts.EVENT_LOOKBACK_DAYS', 1):
                            event_ids, html = make_html(sample_event_data, fixed_datetime)
                            assert '1 day' in html
                            assert '1 days' not in html

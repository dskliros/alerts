# tests/test_tracking.py
"""
Tests for event tracking and deduplication functionality
"""
import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd


def test_load_sent_events_empty_file(temp_project_root):
    """Test loading when sent_events.json doesn't exist"""
    from src.events_alerts import load_sent_events
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', temp_project_root / 'data' / 'sent_events.json'):
        result = load_sent_events()
        assert result == {}


def test_load_sent_events_with_data(sent_events_json, sample_sent_events):
    from src.events_alerts import load_sent_events

    with patch('src.events_alerts.SENT_EVENTS_FILE', Path(sent_events_json)), \
         patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 10):
        result = load_sent_events()
        assert len(result) == 2
        assert 99 in result
        assert 100 in result


def test_load_sent_events_corrupted_json(temp_project_root):
    """Test handling of corrupted JSON file"""
    from src.events_alerts import load_sent_events
    
    corrupted_file = temp_project_root / 'data' / 'sent_events.json'
    with open(corrupted_file, 'w') as f:
        f.write('{ invalid json content')
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', corrupted_file):
        result = load_sent_events()
        assert result == {}


def test_load_sent_events_backward_compatibility(temp_project_root, local_tz):
    """Test backward compatibility with old list format"""
    from src.events_alerts import load_sent_events
    
    old_format_file = temp_project_root / 'data' / 'sent_events.json'
    old_data = {
        'sent_event_ids': [99, 100, 101],
        'last_updated': '2025-10-28T15:30:00+02:00',
        'total_count': 3
    }
    with open(old_format_file, 'w') as f:
        json.dump(old_data, f)
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', old_format_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            result = load_sent_events()
            assert len(result) == 3
            assert all(isinstance(k, int) for k in result.keys())
            assert all(isinstance(v, str) for v in result.values())


def test_load_sent_events_removes_old_events(temp_project_root, local_tz):
    """Test that events older than REMINDER_FREQUENCY_DAYS are automatically removed"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta

    # Create test data with events at different ages
    now = datetime.now(tz=local_tz)
    old_event_time = (now - timedelta(days=35)).isoformat()  # 35 days old
    recent_event_time = (now - timedelta(days=5)).isoformat()  # 5 days old

    test_data = {
        'sent_events': {
            '100': old_event_time,      # Should be removed (>30 days)
            '101': recent_event_time,   # Should be kept (<30 days)
            '102': old_event_time,      # Should be removed (>30 days)
            '103': recent_event_time    # Should be kept (<30 days)
        },
        'last_updated': now.isoformat()
    }

    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)

    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 30):
                result = load_sent_events()

    # Should only have the 2 recent events
    assert len(result) == 2
    assert 101 in result
    assert 103 in result
    assert 100 not in result
    assert 102 not in result


def test_load_sent_events_boundary_condition(temp_project_root, local_tz):
    """Test events exactly at the REMINDER_FREQUENCY_DAYS boundary"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta

    now = datetime.now(tz=local_tz)
    exactly_30_days = (now - timedelta(days=30, seconds=1)).isoformat()  # Just over 30 days
    just_under_30 = (now - timedelta(days=29, hours=23)).isoformat()     # Just under 30 days

    test_data = {
        'sent_events': {
            '200': exactly_30_days,  # Should be removed (>30 days)
            '201': just_under_30     # Should be kept (<30 days)
        },
        'last_updated': now.isoformat()
    }

    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)

    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 30):
                result = load_sent_events()

    assert len(result) == 1
    assert 201 in result
    assert 200 not in result


def test_load_sent_events_invalid_timestamps(temp_project_root, local_tz):
    """Test that events with invalid timestamps are removed"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta
    
    now = datetime.now(tz=local_tz)
    valid_time = (now - timedelta(days=5)).isoformat()
    
    test_data = {
        'sent_events': {
            '300': 'invalid-timestamp',        # Invalid format
            '301': valid_time,                 # Valid
            '302': 'not-a-date',              # Invalid format
            '303': valid_time,                # Valid
            '304': '2025-13-45T99:99:99'      # Invalid date
        },
        'last_updated': now.isoformat()
    }
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 30):
                result = load_sent_events()
    
    # Should only keep the 2 valid recent events
    assert len(result) == 2
    assert 301 in result
    assert 303 in result
    assert 300 not in result
    assert 302 not in result
    assert 304 not in result


def test_load_sent_events_saves_cleanup(temp_project_root, local_tz):
    """Test that cleaned-up events are immediately saved back to file"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta

    now = datetime.now(tz=local_tz)
    old_time = (now - timedelta(days=40)).isoformat()
    recent_time = (now - timedelta(days=10)).isoformat()

    test_data = {
        'sent_events': {
            '400': old_time,      # Should be removed
            '401': recent_time,   # Should be kept
            '402': old_time       # Should be removed
        },
        'last_updated': now.isoformat()
    }

    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)

    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 30):
                load_sent_events()

    # Verify the file was updated with cleaned data
    with open(sent_events_file, 'r') as f:
        saved_data = json.load(f)

    assert 'sent_events' in saved_data
    assert len(saved_data['sent_events']) == 1
    assert '401' in saved_data['sent_events']
    assert '400' not in saved_data['sent_events']
    assert '402' not in saved_data['sent_events']


def test_load_sent_events_all_recent(temp_project_root, local_tz):
    """Test that all events are kept when none are older than threshold"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta
    
    now = datetime.now(tz=local_tz)
    recent_times = [
        (now - timedelta(days=1)).isoformat(),
        (now - timedelta(days=10)).isoformat(),
        (now - timedelta(days=20)).isoformat(),
        (now - timedelta(days=29)).isoformat()
    ]
    
    test_data = {
        'sent_events': {
            '500': recent_times[0],
            '501': recent_times[1],
            '502': recent_times[2],
            '503': recent_times[3]
        },
        'last_updated': now.isoformat()
    }
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 30):
                result = load_sent_events()
    
    # All 4 events should be kept
    assert len(result) == 4
    assert all(event_id in result for event_id in [500, 501, 502, 503])


def test_load_sent_events_all_old(temp_project_root, local_tz):
    """Test that all events are removed when all exceed threshold"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta

    now = datetime.now(tz=local_tz)
    old_times = [
        (now - timedelta(days=31)).isoformat(),
        (now - timedelta(days=45)).isoformat(),
        (now - timedelta(days=60)).isoformat()
    ]

    test_data = {
        'sent_events': {
            '600': old_times[0],
            '601': old_times[1],
            '602': old_times[2]
        },
        'last_updated': now.isoformat()
    }

    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)

    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 30):
                result = load_sent_events()

    # All events should be removed
    assert len(result) == 0
    assert result == {}


def test_load_sent_events_custom_reminder_frequency(temp_project_root, local_tz):
    """Test that REMINDER_FREQUENCY_DAYS is respected"""
    from src.events_alerts import load_sent_events
    from datetime import datetime, timedelta
    
    now = datetime.now(tz=local_tz)
    event_8_days_old = (now - timedelta(days=8)).isoformat()
    event_6_days_old = (now - timedelta(days=6)).isoformat()
    
    test_data = {
        'sent_events': {
            '700': event_8_days_old,   # Should be removed with 7-day window
            '701': event_6_days_old    # Should be kept with 7-day window
        },
        'last_updated': now.isoformat()
    }
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    with open(sent_events_file, 'w') as f:
        json.dump(test_data, f)
    
    # Test with 7-day reminder frequency
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            with patch('src.events_alerts.REMINDER_FREQUENCY_DAYS', 7):
                result = load_sent_events()
    
    assert len(result) == 1
    assert 701 in result
    assert 700 not in result


def test_save_sent_events(temp_project_root, fixed_datetime, local_tz):
    """Test saving sent events to JSON"""
    from src.events_alerts import save_sent_events
    
    sent_events = {
        101: '2025-10-29T09:00:00+02:00',
        102: '2025-10-29T09:30:00+02:00'
    }
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            save_sent_events(sent_events)
    
    # Verify file was created
    assert sent_events_file.exists()
    
    # Verify content
    with open(sent_events_file, 'r') as f:
        data = json.load(f)
    
    assert 'sent_events' in data
    assert 'last_updated' in data
    assert 'total_count' not in data
    assert '101' in data['sent_events']
    assert '102' in data['sent_events']


def test_filter_unsent_events_all_new(sample_event_data):
    """Test filtering when all events are new"""
    from src.events_alerts import filter_unsent_events
    
    sent_events = {99: '2025-10-28T10:00:00+02:00'}
    
    result = filter_unsent_events(sample_event_data, sent_events)
    
    assert len(result) == 2
    assert 101 in result['id'].values
    assert 102 in result['id'].values


def test_filter_unsent_events_some_sent(sample_event_data):
    """Test filtering when some events already sent"""
    from src.events_alerts import filter_unsent_events
    
    sent_events = {
        101: '2025-10-29T08:00:00+02:00'
    }
    
    result = filter_unsent_events(sample_event_data, sent_events)
    
    assert len(result) == 1
    assert 102 in result['id'].values
    assert 101 not in result['id'].values


def test_filter_unsent_events_all_sent(sample_event_data):
    """Test filtering when all events already sent"""
    from src.events_alerts import filter_unsent_events
    
    sent_events = {
        101: '2025-10-29T08:00:00+02:00',
        102: '2025-10-29T09:30:00+02:00'
    }
    
    result = filter_unsent_events(sample_event_data, sent_events)
    
    assert len(result) == 0
    assert result.empty


def test_filter_unsent_events_empty_dataframe(empty_event_data):
    """Test filtering with empty DataFrame"""
    from src.events_alerts import filter_unsent_events
    
    sent_events = {99: '2025-10-28T10:00:00+02:00'}
    
    result = filter_unsent_events(empty_event_data, sent_events)
    
    assert result.empty


def test_filter_unsent_events_missing_id_column():
    """Test filtering when DataFrame missing 'id' column"""
    from src.events_alerts import filter_unsent_events
    
    df = pd.DataFrame([
        {'event_name': 'Test Event', 'created_at': '2025-10-29'}
    ])
    
    sent_events = {99: '2025-10-28T10:00:00+02:00'}
    
    result = filter_unsent_events(df, sent_events)
    
    # Should return original DataFrame when id column missing
    assert len(result) == 1


def test_save_sent_events_no_total_count(temp_project_root, fixed_datetime, local_tz):
    """Test that total_count is not saved in JSON (removed field)"""
    from src.events_alerts import save_sent_events
    
    sent_events = {
        101: '2025-10-29T09:00:00+02:00',
        102: '2025-10-29T09:30:00+02:00'
    }
    
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_file):
        with patch('src.events_alerts.LOCAL_TZ', local_tz):
            save_sent_events(sent_events)
    
    # Verify file was created
    assert sent_events_file.exists()
    
    # Verify content
    with open(sent_events_file, 'r') as f:
        data = json.load(f)
    
    assert 'sent_events' in data
    assert 'last_updated' in data
    assert 'total_count' not in data  # Verify it's been removed

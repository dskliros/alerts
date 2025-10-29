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
    """Test loading existing sent events"""
    from src.events_alerts import load_sent_events
    
    with patch('src.events_alerts.SENT_EVENTS_FILE', sent_events_json):
        result = load_sent_events()
        assert len(result) == 2
        assert 99 in result
        assert 100 in result
        assert result[99] == '2025-10-28T10:00:00+02:00'


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
    assert 'total_count' in data
    assert data['total_count'] == 2
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

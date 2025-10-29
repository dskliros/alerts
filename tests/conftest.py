# tests/test_config.py
"""
Pytest configuration and shared fixtures for events_alerts tests
"""
import pytest
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock
import tempfile
import shutil

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_project_root(tmp_path):
    """Create a temporary project structure for testing"""
    # Create directory structure
    (tmp_path / 'data').mkdir()
    (tmp_path / 'logs').mkdir()
    (tmp_path / 'queries').mkdir()
    (tmp_path / 'media').mkdir()
    
    return tmp_path


@pytest.fixture
def sample_event_data():
    """Sample event data matching database query results"""
    return pd.DataFrame([
        {
            'id': 101,
            'event_name': 'Hot Work Permit - Deck Maintenance',
            'created_at': '2025-10-29 08:00:00',
            'status': 'active'
        },
        {
            'id': 102,
            'event_name': 'Hot Work Permit - Engine Room',
            'created_at': '2025-10-29 09:30:00',
            'status': 'active'
        }
    ])


@pytest.fixture
def empty_event_data():
    """Empty DataFrame for no-results tests"""
    return pd.DataFrame(columns=['id', 'event_name', 'created_at', 'status'])


@pytest.fixture
def sample_sent_events():
    """Sample sent events dictionary"""
    return {
        99: '2025-10-28T10:00:00+02:00',
        100: '2025-10-28T15:30:00+02:00'
    }


@pytest.fixture
def sent_events_json(temp_project_root, sample_sent_events):
    """Create a sent_events.json file"""
    sent_events_file = temp_project_root / 'data' / 'sent_events.json'
    data = {
        'sent_events': {str(k): v for k, v in sample_sent_events.items()},
        'last_updated': '2025-10-28T15:30:00+02:00',
        'total_count': len(sample_sent_events)
    }
    with open(sent_events_file, 'w') as f:
        json.dump(data, f, indent=2)
    return sent_events_file


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = ('permit_id', 'Hot Work Permit')
    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    return mock_conn


@pytest.fixture
def mock_smtp():
    """Mock SMTP server"""
    mock_server = MagicMock()
    mock_server.__enter__ = Mock(return_value=mock_server)
    mock_server.__exit__ = Mock(return_value=False)
    return mock_server


@pytest.fixture
def mock_teams_webhook():
    """Mock Teams webhook response"""
    mock_card = MagicMock()
    mock_card.send.return_value = True
    mock_card.last_http_response = MagicMock()
    mock_card.last_http_response.status_code = 200
    return mock_card


@pytest.fixture
def local_tz():
    """Europe/Athens timezone"""
    return ZoneInfo('Europe/Athens')


@pytest.fixture
def fixed_datetime(local_tz):
    """Fixed datetime for testing"""
    return datetime(2025, 10, 29, 9, 41, 19, tzinfo=local_tz)


@pytest.fixture
def mock_smtp_class(mock_smtp):
    """Mock SMTP class that returns configured mock_smtp instance"""
    return MagicMock(return_value=mock_smtp)

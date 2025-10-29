# tests/test_utils.py
"""
Tests for utility functions
"""
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open


def test_load_logo_exists(temp_project_root):
    """Test loading existing logo file"""
    from src.events_alerts import load_logo

    logo_file = temp_project_root / 'media' / 'test_logo.png'
    logo_file.write_bytes(b'fake png data')

    data, mime_type, filename = load_logo(logo_file)

    assert data == b'fake png data'
    assert mime_type == 'image/png'
    assert filename == 'test_logo.png'


def test_load_logo_not_exists(temp_project_root):
    """Test loading non-existent logo file"""
    from src.events_alerts import load_logo

    logo_file = temp_project_root / 'media' / 'nonexistent.png'

    data, mime_type, filename = load_logo(logo_file)

    assert data is None
    assert mime_type is None
    assert filename is None


def test_load_logo_different_formats(temp_project_root):
    """Test loading different image formats"""
    from src.events_alerts import load_logo

    test_formats = [
        ('test.jpg', 'image/jpeg'),
        ('test.jpeg', 'image/jpeg'),
        ('test.gif', 'image/gif'),
        ('test.svg', 'image/svg+xml'),
    ]

    for filename, expected_mime in test_formats:
        logo_file = temp_project_root / 'media' / filename
        logo_file.write_bytes(b'fake image data')

        data, mime_type, name = load_logo(logo_file)

        assert mime_type == expected_mime


def test_load_sql_query(temp_project_root):
    """Test loading SQL query from file"""
    from src.events_alerts import load_sql_query

    query_file = temp_project_root / 'queries' / 'test_query.sql'
    query_content = "SELECT * FROM events WHERE id = :id"
    query_file.write_text(query_content)

    with patch('src.events_alerts.QUERIES_DIR', temp_project_root / 'queries'):
        result = load_sql_query('test_query.sql')

        assert result == query_content


def test_load_sql_query_not_found(temp_project_root):
    """Test loading non-existent SQL query file"""
    from src.events_alerts import load_sql_query

    with patch('src.events_alerts.QUERIES_DIR', temp_project_root / 'queries'):
        with pytest.raises(FileNotFoundError):
            load_sql_query('nonexistent.sql')

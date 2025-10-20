#!/usr/bin/env python3
"""Test Teams webhook directly"""

from decouple import config
import pymsteams
import sys

TEAMS_WEBHOOK_URL = config('TEAMS_WEBHOOK_URL', default='')

if not TEAMS_WEBHOOK_URL:
    print("❌ TEAMS_WEBHOOK_URL not configured in .env")
    sys.exit(1)

print(f"Testing webhook: {TEAMS_WEBHOOK_URL[:50]}...")

try:
    # Create simple test message
    test_message = pymsteams.connectorcard(TEAMS_WEBHOOK_URL)
    test_message.title("🧪 Test Message from Python")
    test_message.text("If you can see this message, your webhook is working correctly!")
    test_message.color("00FF00")  # Green
    
    # Send
    response = test_message.send()
    
    print(f"✓ Response: {response}")
    print(f"✓ Message sent! Check your Teams channel.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

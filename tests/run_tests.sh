#!/bin/bash
# Run all tests with coverage report

echo "Running events_alerts test suite..."
echo "=================================="

# Run pytest with coverage
pytest tests/ \
    --cov=src \
    --cov-report=html \
    --cov-report=term \
    --verbose \
    --tb=short \
    -v

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ All tests passed!"
    echo "Coverage report generated in htmlcov/index.html"
else
    echo ""
    echo "✗ Some tests failed"
    exit 1
fi

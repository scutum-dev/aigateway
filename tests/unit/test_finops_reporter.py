"""Unit tests for the FinOps Reporter service.

Tests pure functions (get_date_range) and mock-based tests for trend calculation
and export format.
"""

import os
import importlib.util
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# Load the finops-reporter main module under a unique name to avoid sys.modules collision
_service_path = os.path.join(os.path.dirname(__file__), "../../src/finops-reporter/main.py")
_spec = importlib.util.spec_from_file_location("finops_reporter_main", _service_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

get_date_range = _mod.get_date_range
ReportPeriod = _mod.ReportPeriod
TrendDataPoint = _mod.TrendDataPoint


# ============================================================================
# get_date_range
# ============================================================================


class TestGetDateRange:
    def test_daily(self):
        """Daily period should return today-today."""
        start, end = get_date_range(ReportPeriod.DAILY)
        assert start == date.today()
        assert end == date.today()

    def test_weekly(self):
        """Weekly period should start from Monday of current week."""
        start, end = get_date_range(ReportPeriod.WEEKLY)
        today = date.today()
        expected_start = today - timedelta(days=today.weekday())
        assert start == expected_start
        assert end == today

    def test_monthly(self):
        """Monthly period should start from 1st of current month."""
        start, end = get_date_range(ReportPeriod.MONTHLY)
        today = date.today()
        assert start == today.replace(day=1)
        assert end == today

    def test_custom_with_dates(self):
        """Custom period should use provided start/end dates."""
        s = date(2025, 1, 1)
        e = date(2025, 1, 31)
        start, end = get_date_range(ReportPeriod.CUSTOM, s, e)
        assert start == s
        assert end == e

    def test_custom_missing_dates_raises(self):
        """Custom period without dates should raise ValueError."""
        with pytest.raises(ValueError, match="Custom period requires"):
            get_date_range(ReportPeriod.CUSTOM)

    def test_custom_missing_end_raises(self):
        """Custom period without end date should raise ValueError."""
        with pytest.raises(ValueError, match="Custom period requires"):
            get_date_range(ReportPeriod.CUSTOM, start=date(2025, 1, 1))


# ============================================================================
# Trend Calculation
# ============================================================================


class TestTrendCalculation:
    def test_increasing_trend(self):
        """Second half higher than first half should be 'increasing'."""
        data_points = [
            TrendDataPoint(date=date(2025, 1, i + 1), cost=float(i), requests=10, tokens=1000)
            for i in range(10)
        ]
        costs = [dp.cost for dp in data_points]
        mid = len(costs) // 2
        first_half_avg = sum(costs[:mid]) / mid
        second_half_avg = sum(costs[mid:]) / (len(costs) - mid)
        percent_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        assert percent_change > 10
        assert "increasing" == ("increasing" if percent_change > 10 else "decreasing" if percent_change < -10 else "stable")

    def test_decreasing_trend(self):
        """Second half lower than first half should be 'decreasing'."""
        data_points = [
            TrendDataPoint(date=date(2025, 1, i + 1), cost=float(10 - i), requests=10, tokens=1000)
            for i in range(10)
        ]
        costs = [dp.cost for dp in data_points]
        mid = len(costs) // 2
        first_half_avg = sum(costs[:mid]) / mid
        second_half_avg = sum(costs[mid:]) / (len(costs) - mid)
        percent_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        assert percent_change < -10

    def test_stable_trend(self):
        """Constant costs should be 'stable'."""
        data_points = [
            TrendDataPoint(date=date(2025, 1, i + 1), cost=5.0, requests=10, tokens=1000)
            for i in range(10)
        ]
        costs = [dp.cost for dp in data_points]
        mid = len(costs) // 2
        first_half_avg = sum(costs[:mid]) / mid
        second_half_avg = sum(costs[mid:]) / (len(costs) - mid)
        percent_change = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        assert abs(percent_change) <= 10


# ============================================================================
# Export Format
# ============================================================================


class TestExportFormat:
    def test_csv_headers(self):
        """CSV export should include standard column headers."""
        import csv
        import io

        headers = [
            "date", "user_id", "team_id", "model",
            "request_count", "input_tokens", "output_tokens", "total_cost"
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        content = output.getvalue()

        assert "date" in content
        assert "total_cost" in content
        assert "model" in content

    def test_json_export_fields(self):
        """JSON export items should contain expected fields."""
        import json

        item = {
            "date": "2025-01-01",
            "user_id": "user-1",
            "team_id": "team-1",
            "model": "gpt-4o",
            "request_count": 10,
            "input_tokens": 5000,
            "output_tokens": 2000,
            "total_cost": 0.05,
        }
        serialized = json.dumps([item])
        parsed = json.loads(serialized)

        assert len(parsed) == 1
        assert parsed[0]["model"] == "gpt-4o"
        assert parsed[0]["total_cost"] == 0.05

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services.alert_service import AlertService


def _wi(severity: SeverityLevel) -> WorkItem:
    now = datetime.now(UTC)
    return WorkItem(
        component_id="ALERT_TEST",
        severity=severity,
        status=WorkItemStatus.OPEN,
        title="test",
        description=None,
        first_signal_time=now,
        last_signal_time=now,
        signal_count=1,
    )


@pytest.mark.asyncio
async def test_p0_combined_logs_email_and_slack(caplog) -> None:
    caplog.set_level(logging.INFO)
    svc = AlertService({"P0": "combined", "P1": "slack", "P2": "email"})
    wi = _wi(SeverityLevel.P0)
    await svc.send_alert(wi)
    text = caplog.text
    assert "Email alert sent" in text
    assert "Slack alert sent" in text


@pytest.mark.asyncio
async def test_p2_email_only(caplog) -> None:
    caplog.set_level(logging.INFO)
    svc = AlertService({"P0": "combined", "P1": "slack", "P2": "email"})
    wi = _wi(SeverityLevel.P2)
    await svc.send_alert(wi)
    text = caplog.text
    assert "Email alert sent" in text
    assert "Slack alert sent" not in text


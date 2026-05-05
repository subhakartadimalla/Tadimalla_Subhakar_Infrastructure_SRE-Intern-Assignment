from __future__ import annotations

import pytest

from app.models.enums import WorkItemStatus
from app.services.workflow_engine import InvalidTransitionError, WorkItemStateContext


def test_valid_happy_path() -> None:
    ctx = WorkItemStateContext(WorkItemStatus.OPEN)
    s1 = ctx.transition_to_investigating()
    assert s1 == WorkItemStatus.INVESTIGATING

    ctx2 = WorkItemStateContext(s1)
    s2 = ctx2.transition_to_resolved()
    assert s2 == WorkItemStatus.RESOLVED

    ctx3 = WorkItemStateContext(s2)
    s3 = ctx3.transition_to_closed()
    assert s3 == WorkItemStatus.CLOSED


def test_invalid_open_to_closed() -> None:
    ctx = WorkItemStateContext(WorkItemStatus.OPEN)
    with pytest.raises(InvalidTransitionError) as e:
        ctx.transition_to_closed()
    assert "Cannot move from OPEN to CLOSED" in str(e.value)


def test_invalid_resolved_to_investigating() -> None:
    ctx = WorkItemStateContext(WorkItemStatus.RESOLVED)
    with pytest.raises(InvalidTransitionError) as e:
        ctx.transition_to_investigating()
    assert "Cannot move from RESOLVED to INVESTIGATING" in str(e.value)

